"""Data types shared across the pipeline. See SPEC.md sections 8 and 10."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

HN_ITEM_URL = "https://news.ycombinator.com/item?id={id}"


class Status(StrEnum):
    """Per-article outcome. Failure is a status, never an exception (SPEC 8.2)."""

    OK = "ok"
    SELF_POST = "self_post"
    EXTRACTION_FAILED = "extraction_failed"
    NON_HTML = "non_html"
    FETCH_ERROR = "fetch_error"
    SKIPPED_DOMAIN = "skipped_domain"


@dataclass(frozen=True)
class Slot:
    """A scheduled issue slot, resolved to a concrete instant."""

    label: str
    at: datetime  # tz-aware UTC

    @property
    def slug(self) -> str:
        return f"hn-{self.at:%Y%m%d}-{self.label}"


@dataclass
class Story:
    id: int
    title: str
    url: str | None  # None => self-post
    score: int
    by: str
    time: int
    descendants: int = 0
    text: str | None = None  # self-post body, HN-supplied HTML

    @property
    def hn_url(self) -> str:
        return HN_ITEM_URL.format(id=self.id)

    @property
    def is_self_post(self) -> bool:
        return not self.url

    @property
    def domain(self) -> str:
        if not self.url:
            return "news.ycombinator.com"
        from urllib.parse import urlparse

        return urlparse(self.url).netloc.removeprefix("www.")

    @property
    def link(self) -> str:
        """The URL a reader should open: the article, or the HN thread for a self-post."""
        return self.url or self.hn_url


@dataclass
class Article:
    story: Story
    status: Status
    body_html: str = ""
    chars: int = 0
    error: str | None = None


@dataclass
class EpubResult:
    filename: str
    bytes: int
    sha256: str


@dataclass
class Manifest:
    """The published record of one issue (SPEC 10.1)."""

    schema: int
    slug: str
    slot_label: str
    slot_at: datetime
    built_at: datetime
    feed: str
    xtpages_version: str
    story_ids: list[int]
    entries: list[dict] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    epub: dict = field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.epub.get("title", self.slug)
