from datetime import UTC, datetime, timedelta

from lxml import etree

from xtpages import catalog
from xtpages.models import Manifest

ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/terms/}"


def manifest(day=6, label="0300", title=None, entries=None, built=None):
    slot_at = datetime(2026, 9, day, int(label[:2]), 0, tzinfo=UTC)
    slug = f"hn-2026090{day}-{label}"
    return Manifest(
        schema=1,
        slug=slug,
        slot_label=label,
        slot_at=slot_at,
        built_at=built or (slot_at + timedelta(minutes=7)),
        feed="top",
        xtpages_version="1.0.0",
        story_ids=[1, 2],
        entries=entries if entries is not None else [{"title": "One"}, {"title": "Two"}],
        counts={"returned": 2},
        epub={
            "filename": f"{slug}.epub",
            "bytes": 4242,
            "title": title or f"HN Daily 2026-09-0{day} {label} UTC",
        },
    )


def parse(xml):
    return etree.fromstring(xml.encode("utf-8"))


def test_feed_has_required_atom_elements(cfg):
    feed = parse(catalog.build_catalog(cfg, [manifest()]))
    for tag in ("id", "title", "updated", "author"):
        assert feed.find(f"{ATOM}{tag}") is not None, tag


def test_self_and_start_links_are_acquisition(cfg):
    feed = parse(catalog.build_catalog(cfg, [manifest()]))
    rels = {ln.get("rel"): ln for ln in feed.findall(f"{ATOM}link")}
    for rel in ("self", "start"):
        assert rels[rel].get("type") == catalog.ACQ_TYPE
        assert rels[rel].get("href").startswith("https://")


def test_entry_required_elements_and_acquisition_link(cfg):
    feed = parse(catalog.build_catalog(cfg, [manifest()]))
    entry = feed.find(f"{ATOM}entry")
    for tag in ("id", "title", "updated"):
        assert entry.find(f"{ATOM}{tag}") is not None, tag
    link = entry.find(f"{ATOM}link")
    assert link.get("rel") == "http://opds-spec.org/acquisition"
    # exact strcmp on the device: no parameters, no charset
    assert link.get("type") == "application/epub+zip"
    assert link.get("length") == "4242"


def test_entries_are_newest_first(cfg):
    older, newer = manifest(day=5), manifest(day=7)
    feed = parse(catalog.build_catalog(cfg, [newer, older]))
    titles = [e.find(f"{ATOM}title").text for e in feed.findall(f"{ATOM}entry")]
    assert titles[0].endswith("2026-09-07 0300 UTC")


def test_all_hrefs_absolute(cfg):
    feed = parse(catalog.build_catalog(cfg, [manifest()]))
    for link in feed.iter(f"{ATOM}link"):
        assert link.get("href").startswith("https://owner.github.io/repo/")


def test_timestamps_map_to_the_right_fields(cfg):
    m = manifest()
    entry = parse(catalog.build_catalog(cfg, [m])).find(f"{ATOM}entry")
    assert entry.find(f"{ATOM}updated").text == "2026-09-06T03:07:00Z"
    assert entry.find(f"{DC}issued").text == "2026-09-06T03:00:00Z"


def test_hostile_title_round_trips(cfg):
    m = manifest(title='Fish & <Chips> "quoted"')
    entry = parse(catalog.build_catalog(cfg, [m])).find(f"{ATOM}entry")
    assert entry.find(f"{ATOM}title").text == 'Fish & <Chips> "quoted"'


def test_control_characters_stripped(cfg):
    m = manifest(title="Bad\x00Title\x08Here")
    xml = catalog.build_catalog(cfg, [m])
    entry = parse(xml).find(f"{ATOM}entry")
    assert entry.find(f"{ATOM}title").text == "BadTitleHere"


def test_summary_truncated_to_400(cfg):
    entries = [{"title": "A rather long story headline here"} for _ in range(60)]
    m = manifest(entries=entries)
    summary = parse(catalog.build_catalog(cfg, [m])).find(f"{ATOM}entry/{ATOM}summary")
    assert len(summary.text) <= catalog.SUMMARY_MAX
    assert summary.text.endswith("…")


def test_fields_within_device_limits(cfg):
    feed = parse(catalog.build_catalog(cfg, [manifest()]))
    entry = feed.find(f"{ATOM}entry")
    assert len(entry.find(f"{ATOM}title").text.encode()) <= 160
    assert len(entry.find(f"{ATOM}author/{ATOM}name").text.encode()) <= 120
    assert len(entry.find(f"{ATOM}id").text.encode()) <= 128
    assert len(entry.find(f"{ATOM}link").get("href").encode()) <= 768


def test_entry_title_is_ascii_without_colon(cfg):
    entry = parse(catalog.build_catalog(cfg, [manifest()])).find(f"{ATOM}entry")
    title = entry.find(f"{ATOM}title").text
    assert title.isascii() and ":" not in title


def test_nav_feed_points_at_the_catalog(cfg):
    feed = parse(catalog.build_nav(cfg, [manifest()]))
    link = feed.find(f"{ATOM}entry/{ATOM}link")
    assert link.get("rel") == "subsection"
    assert link.get("type") == catalog.ACQ_TYPE
    assert link.get("href") == "https://owner.github.io/repo/catalog.xml"


def test_empty_catalog_is_still_valid(cfg):
    feed = parse(catalog.build_catalog(cfg, []))
    assert feed.find(f"{ATOM}updated") is not None
    assert feed.findall(f"{ATOM}entry") == []


def test_write_all_creates_every_file(cfg, tmp_path):
    catalog.write_all(cfg, [manifest()], tmp_path)
    for name in ("catalog.xml", "nav.xml", "index.html", ".nojekyll"):
        assert (tmp_path / name).exists(), name
    assert "catalog.xml" in (tmp_path / "index.html").read_text()


def test_index_lists_issues(cfg, tmp_path):
    html = catalog.build_index(cfg, [manifest(day=6), manifest(day=7)])
    assert html.count("<tr>") == 3  # header + two issues
    assert "latest.epub" in html


def test_feed_updated_is_newest_built_at(cfg):
    older = manifest(day=5)
    newer = manifest(day=7)
    feed = parse(catalog.build_catalog(cfg, [newer, older]))
    assert feed.find(f"{ATOM}updated").text == "2026-09-07T03:07:00Z"


def test_now_is_used_when_no_manifests(cfg):
    feed = parse(catalog.build_catalog(cfg, []))
    stamp = feed.find(f"{ATOM}updated").text
    assert stamp.endswith("Z") and datetime.now(UTC).strftime("%Y") in stamp
