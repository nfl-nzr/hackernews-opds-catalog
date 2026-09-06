import re
import zipfile

import ebooklib
from ebooklib import epub as ebooklib_epub

from conftest import NOW
from xtpages import epub
from xtpages.models import Article, Slot, Status, Story

# Exactly what the device's CSS parser implements (SPEC 12.3).
SUPPORTED_CSS = {
    "direction",
    "display",
    "font-style",
    "font-weight",
    "height",
    "margin",
    "margin-top",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "padding",
    "padding-top",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "text-align",
    "text-decoration-line",
    "text-indent",
    "vertical-align",
    "width",
}


def make(n=3, statuses=None):
    out = []
    for i in range(n):
        story = Story(i, f"Story {i}", f"https://e{i}.com/x", 100 + i, "u", 0)
        status = (statuses or {}).get(i, Status.OK)
        out.append(
            Article(
                story=story,
                status=status,
                body_html="<p>body</p>" if status is Status.OK else "",
                chars=4,
            )
        )
    return out


def build(tmp_path, cfg, articles, label="0300"):
    slot = Slot(label=label, at=NOW.replace(hour=3, minute=0, second=0, microsecond=0))
    path = tmp_path / "out.epub"
    result = epub.build_epub(cfg, slot, articles, path, NOW)
    return path, result, slot


def test_mimetype_is_first_and_stored(tmp_path, cfg):
    path, _, _ = build(tmp_path, cfg, make())
    with zipfile.ZipFile(path) as zf:
        first = zf.infolist()[0]
    assert first.filename == "mimetype"
    assert first.compress_type == zipfile.ZIP_STORED


def test_opens_with_ebooklib(tmp_path, cfg):
    path, _, slot = build(tmp_path, cfg, make())
    book = ebooklib_epub.read_epub(str(path))
    assert book.get_metadata("DC", "title")[0][0] == epub.issue_title(cfg, slot)
    assert book.get_metadata("DC", "language")[0][0] == cfg.site.language
    assert epub.issue_identifier(slot) in [i[0] for i in book.get_metadata("DC", "identifier")]


def test_spine_is_stories_plus_title_page(tmp_path, cfg):
    path, _, _ = build(tmp_path, cfg, make(5))
    book = ebooklib_epub.read_epub(str(path))
    spine_files = {i[0] for i in book.spine}
    docs = [
        d
        for d in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
        if d.id in spine_files or d.file_name in spine_files
    ]
    names = sorted(d.file_name for d in docs)
    assert names == [
        "ch001.xhtml",
        "ch002.xhtml",
        "ch003.xhtml",
        "ch004.xhtml",
        "ch005.xhtml",
        "title.xhtml",
    ]
    assert "nav.xhtml" not in names  # a manifest item, not a spine entry


def test_both_toc_formats_present(tmp_path, cfg):
    path, _, _ = build(tmp_path, cfg, make())
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    assert any(n.endswith("toc.ncx") for n in names), names
    assert any(n.endswith("nav.xhtml") for n in names), names


def test_failed_article_gets_a_notice_chapter_not_a_gap(tmp_path, cfg):
    articles = make(3, {1: Status.FETCH_ERROR})
    path, _, _ = build(tmp_path, cfg, articles)
    with zipfile.ZipFile(path) as zf:
        chapter = zf.read("EPUB/ch002.xhtml").decode()
    assert "could not be included" in chapter
    assert "fetch_error" in chapter
    assert "https://e1.com/x" in chapter


def test_discussion_link_toggles_off(tmp_path, cfg):
    cfg.content.include_hn_discussion_link = False
    path, _, _ = build(tmp_path, cfg, make(1))
    with zipfile.ZipFile(path) as zf:
        chapter = zf.read("EPUB/ch001.xhtml").decode()
    assert "Discussion" not in chapter
    assert "100 points" in chapter


def test_stylesheet_uses_only_supported_properties():
    props = set(re.findall(r"^\s*([a-z-]+)\s*:", epub.STYLESHEET, re.MULTILINE))
    assert props <= SUPPORTED_CSS, f"unsupported: {sorted(props - SUPPORTED_CSS)}"


def test_issue_title_is_ascii_and_filename_safe(cfg):
    slot = Slot(label="0300", at=NOW)
    title = epub.issue_title(cfg, slot)
    assert title.isascii()
    assert not set(title) & set('/\\:*?"<>|')
    assert title == "HN Daily 2026-09-06 0300 UTC"


def test_title_page_lists_every_story(tmp_path, cfg):
    path, _, _ = build(tmp_path, cfg, make(4))
    with zipfile.ZipFile(path) as zf:
        page = zf.read("EPUB/title.xhtml").decode()
    for i in range(4):
        assert f"Story {i}" in page


def test_result_reports_size_and_digest(tmp_path, cfg):
    path, result, _ = build(tmp_path, cfg, make())
    assert result.bytes == path.stat().st_size
    assert len(result.sha256) == 64
