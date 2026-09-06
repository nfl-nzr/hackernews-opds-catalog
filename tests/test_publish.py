import json
from datetime import UTC, datetime

import pytest

from xtpages import publish
from xtpages.config import SlotSpec
from xtpages.models import Manifest, Slot
from xtpages.publish import SlotError, resolve_slot

UTC_ = UTC


def at(y=2026, mo=9, d=6, h=3, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=UTC_)


# --- slot resolution (SPEC 7.1) ----------------------------------------------


def test_explicit_slot_wins(cfg):
    slot = resolve_slot(cfg, cron="0 3 * * *", slot="2100", now=at(h=3))
    assert slot.label == "2100"


def test_unknown_slot_label_is_an_error_not_a_guess(cfg):
    with pytest.raises(SlotError):
        resolve_slot(cfg, cron="", slot="9999", now=at())


@pytest.mark.parametrize("blank", ["", "   ", "\t", None])
def test_empty_slot_is_treated_as_absent(cfg, blank):
    """The workflow always passes --slot; on a scheduled run it is the empty string."""
    slot = resolve_slot(cfg, cron="0 21 * * *", slot=blank, now=at(h=21, mi=5))
    assert slot.label == "2100"


def test_cron_match_is_whitespace_insensitive(cfg):
    slot = resolve_slot(cfg, cron="0   21  *  *  *", slot="", now=at(h=21))
    assert slot.label == "2100"


def test_unmatched_cron_falls_back_to_nearest(cfg):
    slot = resolve_slot(cfg, cron="30 7 * * *", slot="", now=at(h=3, mi=10))
    assert slot.label == "0300"


def test_nearest_slot_when_nothing_given(cfg):
    assert resolve_slot(cfg, None, None, now=at(h=20, mi=30)).label == "2100"
    assert resolve_slot(cfg, None, None, now=at(h=4)).label == "0300"


def test_exact_tie_picks_the_later_slot(cfg):
    # 12:00 is nine hours from both 03:00 and 21:00.
    assert resolve_slot(cfg, None, None, now=at(h=12)).label == "2100"


def test_day_boundary_keeps_the_previous_day(cfg):
    """A 21:00 job that actually runs at 00:40 is still 2100 of the previous day."""
    slot = resolve_slot(cfg, cron="0 21 * * *", slot="", now=at(d=7, h=0, mi=40))
    assert slot.label == "2100"
    assert slot.at == at(d=6, h=21)
    assert slot.slug == "hn-20260906-2100"


def test_late_run_still_names_its_own_slot(cfg):
    slot = resolve_slot(cfg, cron="0 3 * * *", slot="", now=at(h=3, mi=28))
    assert slot.slug == "hn-20260906-0300"


# --- deduplication (SPEC 8.5) ------------------------------------------------


def mani(slug, slot_at, ids):
    return Manifest(
        schema=1,
        slug=slug,
        slot_label=slug[-4:],
        slot_at=slot_at,
        built_at=slot_at,
        feed="top",
        xtpages_version="1.0.0",
        story_ids=ids,
        epub={"filename": f"{slug}.epub"},
    )


def test_dedupe_excludes_the_previous_issue():
    manifests = [mani("hn-20260906-0300", at(h=3), [1, 2, 3])]
    assert publish.previous_story_ids(manifests, "hn-20260906-2100", 1) == {1, 2, 3}


def test_dedupe_never_excludes_the_issue_being_rebuilt():
    """Without this, a re-run would dedupe against itself and build a different issue."""
    slug = "hn-20260906-0300"
    manifests = [mani(slug, at(h=3), [1, 2, 3])]
    assert publish.previous_story_ids(manifests, slug, 1) == set()


def test_dedupe_lookback_window():
    manifests = [
        mani("hn-20260906-2100", at(h=21), [4, 5]),
        mani("hn-20260906-0300", at(h=3), [1, 2]),
    ]
    assert publish.previous_story_ids(manifests, "hn-20260907-0300", 1) == {4, 5}
    assert publish.previous_story_ids(manifests, "hn-20260907-0300", 2) == {1, 2, 4, 5}


def test_dedupe_disabled_by_zero_lookback():
    manifests = [mani("hn-20260906-0300", at(h=3), [1, 2])]
    assert publish.previous_story_ids(manifests, "other", 0) == set()


# --- manifests and pruning ---------------------------------------------------


def write_issue(public, slug, slot_at):
    (public / "issues").mkdir(parents=True, exist_ok=True)
    (public / "issues" / f"{slug}.epub").write_bytes(b"PK\x03\x04fake")
    (public / "issues" / f"{slug}.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "slug": slug,
                "slot_label": slug[-4:],
                "slot_at": publish.iso(slot_at),
                "built_at": publish.iso(slot_at),
                "feed": "top",
                "xtpages_version": "1.0.0",
                "story_ids": [1],
                "entries": [],
                "counts": {},
                "epub": {"filename": f"{slug}.epub", "bytes": 9},
            }
        )
    )


def test_read_manifests_newest_first(tmp_path):
    write_issue(tmp_path, "hn-20260905-0300", at(d=5))
    write_issue(tmp_path, "hn-20260907-0300", at(d=7))
    assert [m.slug for m in publish.read_manifests(tmp_path)] == [
        "hn-20260907-0300",
        "hn-20260905-0300",
    ]


def test_missing_public_dir_reads_as_empty(tmp_path):
    assert publish.read_manifests(tmp_path / "nope") == []


def test_corrupt_manifest_is_skipped_not_fatal(tmp_path, capsys):
    write_issue(tmp_path, "hn-20260906-0300", at())
    (tmp_path / "issues" / "broken.json").write_text("{not json")
    assert len(publish.read_manifests(tmp_path)) == 1
    assert "unreadable" in capsys.readouterr().err


def test_unknown_schema_is_skipped(tmp_path):
    write_issue(tmp_path, "hn-20260906-0300", at())
    (tmp_path / "issues" / "future.json").write_text(json.dumps({"schema": 99}))
    assert len(publish.read_manifests(tmp_path)) == 1


def test_prune_drops_only_what_is_past_retention(cfg, tmp_path):
    cfg.retention_days = 14
    write_issue(tmp_path, "hn-20260906-0300", at(d=6))  # older than the cutoff
    write_issue(tmp_path, "hn-20260919-0300", at(d=19))  # fresh
    removed = publish.prune(cfg, tmp_path, now=at(d=20, h=4))
    assert removed == ["hn-20260906-0300"]
    assert not (tmp_path / "issues" / "hn-20260906-0300.epub").exists()
    assert not (tmp_path / "issues" / "hn-20260906-0300.json").exists()
    assert (tmp_path / "issues" / "hn-20260919-0300.epub").exists()


def test_prune_boundary_is_exclusive(cfg, tmp_path):
    """An issue exactly retention_days old is kept; a second older goes."""
    cfg.retention_days = 14
    write_issue(tmp_path, "hn-20260906-0300", at(d=6))
    assert publish.prune(cfg, tmp_path, now=at(d=20, h=3)) == []
    assert publish.prune(cfg, tmp_path, now=at(d=20, h=3, mi=1)) == ["hn-20260906-0300"]


def test_prune_never_touches_the_site_files(cfg, tmp_path):
    for name in ("catalog.xml", "nav.xml", "index.html", "latest.epub", ".nojekyll"):
        (tmp_path / name).write_text("x")
    write_issue(tmp_path, "hn-20260906-0300", at(d=6))
    publish.prune(cfg, tmp_path, now=at(d=30))
    for name in ("catalog.xml", "nav.xml", "index.html", "latest.epub", ".nojekyll"):
        assert (tmp_path / name).exists(), name


def test_refresh_latest_uses_greatest_slot_not_last_built(tmp_path):
    """A manual rebuild of an older slot must not demote the newest issue."""
    write_issue(tmp_path, "hn-20260906-0300", at(d=6))
    write_issue(tmp_path, "hn-20260907-2100", at(d=7, h=21))
    (tmp_path / "issues" / "hn-20260907-2100.epub").write_bytes(b"NEWEST")
    assert publish.refresh_latest(tmp_path) == "hn-20260907-2100"
    assert (tmp_path / "latest.epub").read_bytes() == b"NEWEST"


def test_write_atomic_leaves_no_temp_file(tmp_path):
    target = tmp_path / "x.txt"
    publish.write_atomic(target, "hello")
    assert target.read_text() == "hello"
    assert list(tmp_path.glob("*.tmp")) == []


def test_slot_slug_format():
    assert Slot("0300", at()).slug == "hn-20260906-0300"


def test_config_crons_normalizes_whitespace(cfg):
    from xtpages.config import config_crons

    cfg.slots = [SlotSpec("0   3 * * *", "0300")]
    assert config_crons(cfg) == ["0 3 * * *"]
