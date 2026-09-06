"""OPDS feeds and the landing page. See SPEC.md sections 10.2, 10.3 and 10.4.

Regenerated from scratch on every run by reading the manifests on disk, never
patched incrementally: a corrupted or half-written catalog self-heals next run.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree

from xtpages.config import Config
from xtpages.models import Manifest
from xtpages.publish import iso, write_atomic

ATOM = "http://www.w3.org/2005/Atom"
DC = "http://purl.org/dc/terms/"
NSMAP = {None: ATOM, "dc": DC}

ACQ_TYPE = "application/atom+xml;profile=opds-catalog;kind=acquisition"
NAV_TYPE = "application/atom+xml;profile=opds-catalog;kind=navigation"
EPUB_TYPE = "application/epub+zip"
ACQ_REL = "http://opds-spec.org/acquisition"

SUMMARY_MAX = 400
# XML 1.0 forbids most C0 controls; titles come from the open web.
ILLEGAL = re.compile(r"[^\x09\x0a\x0d\x20-퟿-�]")


def clean(text: str) -> str:
    return ILLEGAL.sub("", text or "")


def _repo_url() -> str | None:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    return f"https://github.com/{repo}" if "/" in repo else None


def _sub(parent, tag, text=None):
    element = etree.SubElement(parent, tag)
    if text is not None:
        element.text = clean(text)
    return element


def _link(parent, rel, href, type_, length=None):
    attrs = {"rel": rel, "href": href, "type": type_}
    if length is not None:
        attrs["length"] = str(length)
    etree.SubElement(parent, "link", attrib=attrs)


def _summary(manifest: Manifest) -> str:
    titles = [e.get("title", "") for e in manifest.entries]
    text = f"{len(titles)} stories"
    if titles:
        text += " · " + " · ".join(titles)
    if len(text) > SUMMARY_MAX:
        text = text[: SUMMARY_MAX - 1].rstrip() + "…"
    return text


def _issue_title(manifest: Manifest) -> str:
    return manifest.epub.get("title") or manifest.slug


def _updated(manifests: list[Manifest]) -> str:
    newest = max((m.built_at for m in manifests), default=None)
    return iso(newest) if newest else iso(datetime.now(UTC))


def _serialize(root) -> str:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode(
        "utf-8"
    )


def build_catalog(cfg: Config, manifests: list[Manifest]) -> str:
    feed = etree.Element("feed", nsmap=NSMAP)
    _sub(feed, "id", "urn:xtpages:catalog")
    _sub(feed, "title", cfg.site.title)
    _sub(feed, "updated", _updated(manifests))
    author = _sub(feed, "author")
    _sub(author, "name", "xtpages")
    repo = _repo_url()
    if repo:
        _sub(author, "uri", repo)

    self_url = cfg.url_for("catalog.xml")
    _link(feed, "self", self_url, ACQ_TYPE)
    _link(feed, "start", self_url, ACQ_TYPE)

    for manifest in manifests:
        entry = etree.SubElement(feed, "entry")
        _sub(
            entry,
            "id",
            f"urn:xtpages:issue:{manifest.slot_at:%Y%m%d}-{manifest.slot_label}",
        )
        _sub(entry, "title", _issue_title(manifest))
        _sub(entry, "updated", iso(manifest.built_at))
        _sub(entry, f"{{{DC}}}issued", iso(manifest.slot_at))
        _sub(entry, f"{{{DC}}}language", cfg.site.language)
        entry_author = _sub(entry, "author")
        _sub(entry_author, "name", cfg.site.author)
        summary = _sub(entry, "summary", _summary(manifest))
        summary.set("type", "text")
        filename = manifest.epub.get("filename") or f"{manifest.slug}.epub"
        _link(
            entry,
            ACQ_REL,
            cfg.url_for(f"issues/{filename}"),
            EPUB_TYPE,
            length=manifest.epub.get("bytes"),
        )
    return _serialize(feed)


def build_nav(cfg: Config, manifests: list[Manifest]) -> str:
    """Navigation feed. CrossPoint does not need it; the stock firmware is uninspected."""
    feed = etree.Element("feed", nsmap={None: ATOM})
    _sub(feed, "id", "urn:xtpages:nav")
    _sub(feed, "title", cfg.site.title)
    updated = _updated(manifests)
    _sub(feed, "updated", updated)
    author = _sub(feed, "author")
    _sub(author, "name", "xtpages")
    nav_url = cfg.url_for("nav.xml")
    _link(feed, "self", nav_url, NAV_TYPE)
    _link(feed, "start", nav_url, NAV_TYPE)

    entry = etree.SubElement(feed, "entry")
    _sub(entry, "id", "urn:xtpages:nav:issues")
    _sub(entry, "title", "Recent issues")
    _sub(entry, "updated", updated)
    content = _sub(entry, "content", f"The last {len(manifests)} issues")
    content.set("type", "text")
    _link(entry, "subsection", cfg.url_for("catalog.xml"), ACQ_TYPE)
    return _serialize(feed)


def build_index(cfg: Config, manifests: list[Manifest]) -> str:
    from xtpages.html import escape

    rows = "".join(
        f"<tr><td>{escape(_issue_title(m))}</td>"
        f"<td>{m.counts.get('returned', len(m.entries))}</td>"
        f"<td>{m.epub.get('bytes', 0) // 1024} KB</td>"
        f'<td><a href="issues/{escape(m.epub.get("filename") or m.slug + ".epub")}">'
        f"download</a></td></tr>"
        for m in manifests
    )
    css = """
body { font: 16px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 46rem;
       padding: 0 1rem; color: #222; }
code { background: #f4f4f4; padding: .15em .4em; border-radius: 3px;
       word-break: break-all; }
table { border-collapse: collapse; width: 100%; margin-top: 1.5rem; }
th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #e5e5e5; }
@media (prefers-color-scheme: dark) {
  body { background: #111; color: #ddd; }
  code { background: #222; }
  th, td { border-color: #333; }
}
"""
    return f"""<!doctype html>
<html lang="{escape(cfg.site.language)}">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(cfg.site.title)}</title>
<style>{css}</style>
<h1>{escape(cfg.site.title)}</h1>
<p>A Hacker News digest, rebuilt twice a day and published as EPUB.</p>
<h2>Read it on an e-reader</h2>
<p>Add this URL as an OPDS server on your device
(CrossPoint: Settings &#8594; System &#8594; OPDS Servers &#8594; Add Server):</p>
<p><code>{escape(cfg.url_for("catalog.xml"))}</code></p>
<p>If your reader shows an empty catalog, try
<code>{escape(cfg.url_for("nav.xml"))}</code> instead.
The newest issue is always at <a href="latest.epub">latest.epub</a>.</p>
<h2>Issues</h2>
<table><tr><th>Issue</th><th>Stories</th><th>Size</th><th></th></tr>{rows}</table>
</html>
"""


def write_all(cfg: Config, manifests: list[Manifest], public_dir: Path) -> None:
    write_atomic(public_dir / "catalog.xml", build_catalog(cfg, manifests))
    write_atomic(public_dir / "nav.xml", build_nav(cfg, manifests))
    write_atomic(public_dir / "index.html", build_index(cfg, manifests))
    # build owns .nojekyll; the workflow's touch is redundant insurance (SPEC 9).
    write_atomic(public_dir / ".nojekyll", "")
