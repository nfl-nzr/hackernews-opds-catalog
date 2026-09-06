"""Hacker News API client. See SPEC.md section 8.1.

Base URL https://hacker-news.firebaseio.com/v0/ — no auth, no documented rate
limit. This host is exempt from the one-request-per-host rule (SPEC 6.4): it is
the only way to read the feed, and it is bounded by fetch.max_concurrency.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import httpx

from xtpages.config import Config
from xtpages.models import Story

BASE = "https://hacker-news.firebaseio.com/v0"


def _client(cfg: Config) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": cfg.fetch.user_agent},
        timeout=cfg.fetch.timeout_seconds,
        follow_redirects=True,
    )


def fetch_story_ids(cfg: Config, limit: int, client: httpx.Client | None = None) -> list[int]:
    """Ranked story IDs from the configured feed, at most `limit` of them."""
    owned = client is None
    client = client or _client(cfg)
    try:
        response = client.get(f"{BASE}/{cfg.content.feed}stories.json")
        response.raise_for_status()
        ids = response.json() or []
    finally:
        if owned:
            client.close()
    return [int(i) for i in ids[:limit]]


def fetch_story(cfg: Config, story_id: int, client: httpx.Client | None = None) -> Story | None:
    """One story, or None if it is unusable (deleted, dead, not a story, low score)."""
    owned = client is None
    client = client or _client(cfg)
    try:
        response = client.get(f"{BASE}/item/{story_id}.json")
        response.raise_for_status()
        item = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    finally:
        if owned:
            client.close()

    if not item or item.get("deleted") or item.get("dead"):
        return None
    if item.get("type") != "story":
        return None
    score = int(item.get("score") or 0)
    if score < cfg.content.min_score:
        return None

    return Story(
        id=int(item["id"]),
        title=str(item.get("title") or "").strip(),
        url=item.get("url") or None,
        score=score,
        by=str(item.get("by") or ""),
        time=int(item.get("time") or 0),
        descendants=int(item.get("descendants") or 0),
        text=item.get("text"),
    )


def fetch_stories(cfg: Config, ids: list[int]) -> list[Story]:
    """Story details, concurrently, dropping unusable ones and preserving input order."""
    if not ids:
        return []
    with _client(cfg) as client:
        with ThreadPoolExecutor(max_workers=cfg.fetch.max_concurrency) as pool:
            results = list(pool.map(lambda i: fetch_story(cfg, i, client), ids))
    return [story for story in results if story is not None]
