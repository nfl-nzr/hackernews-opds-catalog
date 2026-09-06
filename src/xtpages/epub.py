"""EPUB generation. See SPEC.md section 8.3.

Every stylesheet declaration here is one the device's CSS parser implements, and
CSS carries no meaning: honouring embedded stylesheets is a user-toggleable
setting, so the book must read correctly with it ignored entirely.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ebooklib import epub

from xtpages.config import Config
from xtpages.html import escape
from xtpages.models import Article, EpubResult, Slot, Status

STYLESHEET = """body { margin: 0; padding: 0; }
h1 { margin: 0 0 0.3em; }
p { margin: 0 0 0.7em; text-indent: 0; }
p.meta { margin-bottom: 0.5em; font-style: italic; }
p.notice { font-style: italic; }
p.code { margin: 0; text-indent: 0; }
blockquote { margin: 0 0 0.7em 1em; }
"""


def issue_title(cfg: Config, slot: Slot) -> str:
    """ASCII, no colon: this string becomes part of the SD card filename (SPEC 10.2)."""
    return f"{cfg.site.title_short} {slot.at:%Y-%m-%d} {slot.label} UTC"


def issue_identifier(slot: Slot) -> str:
    return f"urn:xtpages:issue:{slot.at:%Y%m%d}-{slot.label}"


def _meta_line(cfg: Config, article: Article) -> str:
    story = article.story
    bits = [f"{story.score} points", escape(story.domain)]
    line = " &#183; ".join(bits)
    if cfg.content.include_hn_discussion_link:
        line += f' &#183; <a href="{escape(story.hn_url)}">Discussion</a>'
    return f'<p class="meta">{line}</p>'


def _chapter_html(cfg: Config, article: Article) -> str:
    story = article.story
    parts = [f"<h1>{escape(story.title)}</h1>", _meta_line(cfg, article), "<hr/>"]
    if article.status in (Status.OK, Status.SELF_POST) and article.body_html:
        parts.append(article.body_html)
    else:
        link = escape(story.link)
        parts.append(
            f'<p class="notice">The full text could not be included '
            f"({article.status.value}). Open the original: "
            f'<a href="{link}">{link}</a></p>'
        )
    return "".join(parts)


def _title_page(cfg: Config, slot: Slot, articles: list[Article], built_at) -> str:
    rows = "".join(
        f"<li>{escape(a.story.title)} <span>&#8212; {a.story.score} points</span></li>"
        for a in articles
    )
    return (
        f"<h1>{escape(issue_title(cfg, slot))}</h1>"
        f'<p class="meta">Built {built_at:%Y-%m-%d %H:%M} UTC &#183; '
        f"{len(articles)} stories</p><hr/><ol>{rows}</ol>"
    )


def build_epub(
    cfg: Config, slot: Slot, articles: list[Article], out_path: Path, built_at
) -> EpubResult:
    book = epub.EpubBook()
    book.set_identifier(issue_identifier(slot))
    book.set_title(issue_title(cfg, slot))
    book.set_language(cfg.site.language)
    book.add_author(cfg.site.author)
    book.add_metadata("DC", "date", built_at.strftime("%Y-%m-%dT%H:%M:%SZ"))

    css = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=STYLESHEET.encode("utf-8"),
    )
    book.add_item(css)

    title_page = epub.EpubHtml(
        title=issue_title(cfg, slot), file_name="title.xhtml", lang=cfg.site.language
    )
    title_page.content = _title_page(cfg, slot, articles, built_at)
    title_page.add_item(css)
    book.add_item(title_page)

    chapters = []
    for index, article in enumerate(articles, start=1):
        chapter = epub.EpubHtml(
            title=article.story.title or f"Story {index}",
            file_name=f"ch{index:03d}.xhtml",
            lang=cfg.site.language,
        )
        chapter.content = _chapter_html(cfg, article)
        chapter.add_item(css)
        book.add_item(chapter)
        chapters.append(chapter)

    # ebooklib generates neither of these by default (SPEC 8.3): without the
    # explicit adds the book ships with no nav.xhtml and no toc.ncx at all.
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.toc = [title_page, *chapters]
    # nav.xhtml is a manifest item, not a spine entry (SPEC 14.1).
    book.spine = [title_page, *chapters]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp = out_path.with_suffix(out_path.suffix + ".tmp")
    epub.write_epub(str(temp), book)
    temp.replace(out_path)

    data = out_path.read_bytes()
    return EpubResult(
        filename=out_path.name,
        bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
