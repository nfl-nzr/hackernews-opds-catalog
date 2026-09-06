"""Load and validate config.yaml. See SPEC.md section 6.

Validation runs at the start of every command, before any network call: a bad
config must fail in under a second, not after twenty article downloads.
"""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

FEEDS = {"top", "best", "new"}
LABEL_RE = re.compile(r"^[0-9]{4}$")
FILENAME_ILLEGAL = set('/\\:*?"<>|')

# The device's OPDS parser stores at most 62 entries per feed (SPEC 12.3).
MAX_CATALOG_ENTRIES = 62
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ConfigError(Exception):
    """Raised with a message naming the offending key."""


@dataclass
class Content:
    feed: str = "top"
    story_count: int = 20
    min_score: int = 0
    skip_domains: list[str] = field(default_factory=list)
    include_images: bool = False
    max_article_chars: int = 200_000
    include_hn_discussion_link: bool = True


@dataclass
class Dedupe:
    enabled: bool = True
    lookback_issues: int = 1
    candidate_pool: int = 100


@dataclass
class Fetch:
    timeout_seconds: float = 20
    max_concurrency: int = 5
    retries: int = 2
    retry_backoff_seconds: float = 2
    max_bytes: int = 5_000_000
    impersonate: str = "chrome"
    user_agent: str = "xtpages/1.0 (+https://github.com/nfl-nzr/hackernews-opds-catalog)"


@dataclass
class Site:
    base_url: str = ""
    title: str = "Hacker News Daily"
    title_short: str = "HN Daily"
    author: str = "Hacker News"
    language: str = "en"


@dataclass
class SlotSpec:
    cron: str
    label: str


@dataclass
class Config:
    content: Content = field(default_factory=Content)
    dedupe: Dedupe = field(default_factory=Dedupe)
    fetch: Fetch = field(default_factory=Fetch)
    site: Site = field(default_factory=Site)
    retention_days: int = 14
    slots: list[SlotSpec] = field(default_factory=list)
    path: Path | None = None
    _base_url: str | None = field(default=None, repr=False, compare=False)

    @property
    def base_url(self) -> str:
        """Resolved site root, always with a trailing slash (SPEC 6.2)."""
        if self._base_url is not None:
            return self._base_url
        self._base_url = self._resolve_base_url()
        return self._base_url

    def _resolve_base_url(self) -> str:
        if self.site.base_url:
            return self.site.base_url.rstrip("/") + "/"
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in repo:
            owner, name = repo.split("/", 1)
            return f"https://{owner.lower()}.github.io/{name}/"
        print(
            "warning: site.base_url is blank and GITHUB_REPOSITORY is unset; "
            "falling back to http://localhost:8000/ — this catalog is not publishable",
            file=sys.stderr,
        )
        return "http://localhost:8000/"

    def url_for(self, rel: str) -> str:
        return self.base_url + rel.lstrip("/")


def _is_local_origin(url: str) -> bool:
    """True for http:// on localhost, loopback, or a private-LAN address (SPEC 6.1)."""
    host = urlparse(url).hostname or ""
    if host in LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def _section(raw: dict, key: str) -> dict:
    value = raw.get(key) or {}
    if not isinstance(value, dict):
        raise ConfigError(f"{key}: expected a mapping, got {type(value).__name__}")
    return value


def _build(raw: dict, path: Path | None) -> Config:
    known = {
        "content": Content,
        "dedupe": Dedupe,
        "fetch": Fetch,
        "site": Site,
    }
    kwargs = {}
    for key, cls in known.items():
        data = _section(raw, key)
        allowed = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - allowed
        if unknown:
            raise ConfigError(f"{key}: unknown key(s) {sorted(unknown)}")
        kwargs[key] = cls(**data)

    slots_raw = _section(raw, "schedule").get("slots") or []
    slots = []
    for i, entry in enumerate(slots_raw):
        if not isinstance(entry, dict) or "cron" not in entry or "label" not in entry:
            raise ConfigError(f"schedule.slots[{i}]: needs both 'cron' and 'label'")
        slots.append(SlotSpec(cron=str(entry["cron"]), label=str(entry["label"])))

    return Config(
        **kwargs,
        retention_days=int(raw.get("retention_days", 14)),
        slots=slots,
        path=path,
    )


def validate(cfg: Config) -> None:
    """Raise ConfigError on the first rule broken. See SPEC.md section 6.1."""
    c, d, f, s = cfg.content, cfg.dedupe, cfg.fetch, cfg.site

    if c.feed not in FEEDS:
        raise ConfigError(f"content.feed: {c.feed!r} is not one of {sorted(FEEDS)}")
    if not 1 <= c.story_count <= 100:
        raise ConfigError(f"content.story_count: {c.story_count} is not in 1..100")
    if d.candidate_pool < c.story_count:
        raise ConfigError(
            f"dedupe.candidate_pool ({d.candidate_pool}) is below content.story_count "
            f"({c.story_count}); backfill would be impossible"
        )
    if d.lookback_issues < 0:
        raise ConfigError(f"dedupe.lookback_issues: {d.lookback_issues} is negative")
    if cfg.retention_days < 1:
        raise ConfigError(f"retention_days: {cfg.retention_days} is below 1")
    if f.impersonate and not re.match(r"^[a-z0-9._]+$", f.impersonate):
        raise ConfigError(
            f"fetch.impersonate: {f.impersonate!r} is not a curl_cffi target "
            "(e.g. 'chrome', 'safari', or '' to disable)"
        )
    if not 1 <= f.max_concurrency <= 10:
        raise ConfigError(f"fetch.max_concurrency: {f.max_concurrency} is not in 1..10")
    if not cfg.slots:
        raise ConfigError("schedule.slots: at least one slot is required")

    labels = [sl.label for sl in cfg.slots]
    for label in labels:
        if not LABEL_RE.match(label):
            raise ConfigError(f"schedule.slots: label {label!r} is not four digits")
    if len(set(labels)) != len(labels):
        raise ConfigError(f"schedule.slots: duplicate labels in {labels}")

    if not s.title_short:
        raise ConfigError("site.title_short: must not be empty")
    if len(s.title_short) > 40:
        raise ConfigError(f"site.title_short: {len(s.title_short)} chars exceeds 40")
    if not s.title_short.isascii():
        raise ConfigError(f"site.title_short: {s.title_short!r} must be ASCII")
    bad = FILENAME_ILLEGAL & set(s.title_short)
    if bad:
        raise ConfigError(
            f"site.title_short: contains {sorted(bad)}, which become '_' in the downloaded filename"
        )

    if s.base_url and not s.base_url.startswith("https://"):
        if not (s.base_url.startswith("http://") and _is_local_origin(s.base_url)):
            raise ConfigError(
                f"site.base_url: {s.base_url!r} must start with https:// "
                "(http:// is allowed only for localhost or a private-LAN address)"
            )

    entries = cfg.retention_days * len(cfg.slots) + 1
    if entries > MAX_CATALOG_ENTRIES:
        raise ConfigError(
            f"retention_days ({cfg.retention_days}) x {len(cfg.slots)} slots + 1 = "
            f"{entries} catalog entries, above the device's limit of "
            f"{MAX_CATALOG_ENTRIES}; lower retention_days"
        )


def load(path: str | Path = "config.yaml") -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"{path}: no such file")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    cfg = _build(raw, path)
    validate(cfg)
    return cfg


def find_repo_root(start: str | Path) -> Path | None:
    """Walk up looking for .github/workflows (SPEC 9, doctor)."""
    start = Path(start).resolve()
    if start.is_file():
        start = start.parent
    for candidate in [start, *start.parents]:
        if (candidate / ".github" / "workflows").is_dir():
            return candidate
    return None


def workflow_crons(workflow: str | Path) -> list[str]:
    """Cron expressions declared in a workflow's on.schedule, whitespace-collapsed.

    PyYAML reads the bare key `on` as the boolean True (YAML 1.1), so both forms
    are checked.
    """
    raw = yaml.safe_load(Path(workflow).read_text(encoding="utf-8")) or {}
    triggers = raw.get("on")
    if triggers is None:
        triggers = raw.get(True) or {}
    schedule = (triggers or {}).get("schedule") or []
    return [
        " ".join(str(entry["cron"]).split())
        for entry in schedule
        if isinstance(entry, dict) and "cron" in entry
    ]


def config_crons(cfg: Config) -> list[str]:
    return [" ".join(spec.cron.split()) for spec in cfg.slots]
