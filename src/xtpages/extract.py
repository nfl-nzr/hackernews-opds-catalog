"""Article fetch and readability. See SPEC.md section 8.2.

An Article always comes back: failure is a status, never an exception and never
a dropped story.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import httpx
import trafilatura

from xtpages.config import Config
from xtpages.html import (
    absolutize,
    normalize_pre,
    sanitize,
    text_length,
    truncate,
    unwrap_pre,
)
from xtpages.models import Article, Status, Story

HTML_TYPES = ("text/html", "application/xhtml+xml")
MIN_BODY_CHARS = 500
MAX_REDIRECTS = 5

_host_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


def _client(cfg: Config) -> httpx.Client:
    """Honest identification, standard content negotiation, never browser mimicry."""
    return httpx.Client(
        headers={
            "User-Agent": cfg.fetch.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=cfg.fetch.timeout_seconds,
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
    )


def _skipped(story: Story, cfg: Config) -> bool:
    host = (urlparse(story.url or "").hostname or "").lower()
    return any(
        host == bad.lower() or host.endswith("." + bad.lower()) for bad in cfg.content.skip_domains
    )


def _shape(cfg: Config, html: str, base_url: str | None) -> str:
    """absolutize -> unwrap <pre> -> sanitize -> truncate. Order matters (SPEC 8.2)."""
    shaped = absolutize(html, base_url)
    shaped = unwrap_pre(shaped)
    shaped = sanitize(shaped, include_images=cfg.content.include_images)
    return truncate(shaped, cfg.content.max_article_chars)


def _get_impersonated(cfg: Config, url: str) -> tuple[str, str] | str:
    """Fetch with a browser TLS fingerprint. See SPEC.md section 6.4.

    Bot walls fingerprint the TLS ClientHello, so they reject a Python client
    before it sends a single header. curl_cffi presents a real browser's
    handshake, which is the only thing that gets these pages at all.
    """
    from curl_cffi import requests as curl_requests

    last = "unknown error"
    for attempt in range(cfg.fetch.retries + 1):
        try:
            response = curl_requests.get(
                url,
                impersonate=cfg.fetch.impersonate,
                timeout=cfg.fetch.timeout_seconds,
                allow_redirects=True,
                max_redirects=MAX_REDIRECTS,
            )
            status = response.status_code
            if status >= 400:
                if status < 500 or status == 503:
                    return f"HTTP {status}"
                last = f"HTTP {status}"
                raise RuntimeError(last)
            ctype = response.headers.get("content-type", "").split(";")[0].strip()
            if ctype and ctype not in HTML_TYPES:
                return f"non-html content-type: {ctype}"
            body = response.content
            if len(body) > cfg.fetch.max_bytes:
                return f"body exceeded {cfg.fetch.max_bytes} bytes"
            return response.text, str(response.url)
        except Exception as exc:  # noqa: BLE001 - curl_cffi raises its own hierarchy
            last = f"{type(exc).__name__}: {exc}"
            if attempt < cfg.fetch.retries:
                time.sleep(cfg.fetch.retry_backoff_seconds * (attempt + 1))
    return last


def _get(cfg: Config, url: str, client: httpx.Client) -> tuple[str, str] | str:
    """Return (html, final_url), or an error string."""
    last = "unknown error"
    for attempt in range(cfg.fetch.retries + 1):
        try:
            with client.stream("GET", url) as response:
                status = response.status_code
                if status >= 400:
                    # 4xx, 429 and 503 are the host asking us to stop: never retry.
                    if status < 500 or status == 503:
                        return f"HTTP {status}"
                    last = f"HTTP {status}"
                    raise httpx.HTTPError(last)
                ctype = response.headers.get("content-type", "").split(";")[0].strip()
                if ctype and ctype not in HTML_TYPES:
                    return f"non-html content-type: {ctype}"
                chunks, total = [], 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > cfg.fetch.max_bytes:
                        return f"body exceeded {cfg.fetch.max_bytes} bytes"
                    chunks.append(chunk)
                body = b"".join(chunks)
                return body.decode(response.encoding or "utf-8", errors="replace"), str(
                    response.url
                )
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError) as exc:
            last = f"{type(exc).__name__}: {exc}"
            if attempt < cfg.fetch.retries:
                time.sleep(cfg.fetch.retry_backoff_seconds * (attempt + 1))
    return last


def fetch_article(cfg: Config, story: Story, client: httpx.Client | None = None) -> Article:
    # Self-posts skip fetching but not the rest of the pipeline: Ask HN and Show
    # HN bodies routinely contain <pre> (SPEC 8.2).
    if story.is_self_post:
        body = _shape(cfg, story.text or "", story.hn_url)
        return Article(
            story=story, status=Status.SELF_POST, body_html=body, chars=text_length(body)
        )

    if _skipped(story, cfg):
        return Article(
            story=story, status=Status.SKIPPED_DOMAIN, error="host in content.skip_domains"
        )

    scheme = urlparse(story.url or "").scheme
    if scheme not in ("http", "https"):
        return Article(story=story, status=Status.FETCH_ERROR, error=f"scheme {scheme!r}")

    # An explicit client (tests) always uses the httpx path.
    if client is None and cfg.fetch.impersonate:
        result = _get_impersonated(cfg, story.url)
    else:
        owned = client is None
        client = client or _client(cfg)
        try:
            result = _get(cfg, story.url, client)
        finally:
            if owned:
                client.close()

    if isinstance(result, str):
        status = Status.NON_HTML if "non-html" in result else Status.FETCH_ERROR
        return Article(story=story, status=status, error=result)

    html, final_url = result
    # Rebuild <pre> newlines before readability flattens them (SPEC 8.3.1).
    extracted = trafilatura.extract(
        normalize_pre(html),
        output_format="html",
        include_comments=False,
        include_tables=True,
        include_images=cfg.content.include_images,
        include_links=True,
        favor_precision=True,
        url=final_url,
    )
    if not extracted or text_length(extracted) < MIN_BODY_CHARS:
        return Article(
            story=story,
            status=Status.EXTRACTION_FAILED,
            error=f"body under {MIN_BODY_CHARS} chars after extraction",
        )

    body = _shape(cfg, extracted, final_url)
    return Article(story=story, status=Status.OK, body_html=body, chars=text_length(body))


def fetch_articles(cfg: Config, stories: list[Story]) -> list[Article]:
    """Concurrent, order-preserving, at most one in-flight request per article host."""
    if not stories:
        return []

    def one(story: Story) -> Article:
        host = (urlparse(story.url or "").hostname or "").lower()
        if host:
            with _host_locks[host]:
                return fetch_article(cfg, story)
        return fetch_article(cfg, story)

    with ThreadPoolExecutor(max_workers=cfg.fetch.max_concurrency) as pool:
        return list(pool.map(one, stories))
