"""Slots, manifests, retention. See SPEC.md sections 7.1, 8.5 and 10.1."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from xtpages import __version__
from xtpages.config import Config
from xtpages.models import Article, EpubResult, Manifest, Slot, Status

SCHEMA = 1
KEEP_ALWAYS = {"catalog.xml", "nav.xml", "index.html", "latest.epub", ".nojekyll"}


class SlotError(Exception):
    """An explicit --slot named a label that is not configured."""


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_atomic(path: Path, data: str | bytes) -> None:
    """Write via a temp file and os.replace, so a crash leaves the previous good file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    if isinstance(data, str):
        temp.write_text(data, encoding="utf-8")
    else:
        temp.write_bytes(data)
    temp.replace(path)


def _candidates(label: str, now: datetime):
    hour, minute = int(label[:2]), int(label[2:])
    for delta in (-1, 0, 1):
        day = (now + timedelta(days=delta)).date()
        yield datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def _nearest_instant(label: str, now: datetime) -> datetime:
    return min(_candidates(label, now), key=lambda c: abs((c - now).total_seconds()))


def resolve_slot(
    cfg: Config, cron: str | None, slot: str | None, now: datetime | None = None
) -> Slot:
    """Which slot this run belongs to. See SPEC.md section 7.1.

    Rule 0 governs the most-executed path in the system: the workflow always
    passes --slot, and on a scheduled run that value is the empty string.
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)
    slot = (slot or "").strip()
    cron = (cron or "").strip()
    labels = {spec.label: spec for spec in cfg.slots}

    if slot:
        if slot not in labels:
            raise SlotError(
                f"--slot {slot!r} is not a configured label ({sorted(labels)}); "
                "a typo must not become a guess"
            )
        return Slot(label=slot, at=_nearest_instant(slot, now))

    if cron:
        wanted = " ".join(cron.split())
        for spec in cfg.slots:
            if " ".join(spec.cron.split()) == wanted:
                return Slot(label=spec.label, at=_nearest_instant(spec.label, now))
        print(f"warning: --cron {cron!r} matches no configured slot", file=sys.stderr)

    chosen = min(
        cfg.slots,
        key=lambda spec: (
            abs((_nearest_instant(spec.label, now) - now).total_seconds()),
            -_nearest_instant(spec.label, now).timestamp(),  # tie: the later slot
        ),
    )
    print(f"warning: slot not given; using nearest slot {chosen.label}", file=sys.stderr)
    return Slot(label=chosen.label, at=_nearest_instant(chosen.label, now))


def issue_slug(slot: Slot) -> str:
    return slot.slug


def manifest_path(public_dir: Path, slug: str) -> Path:
    return public_dir / "issues" / f"{slug}.json"


def epub_path(public_dir: Path, slug: str) -> Path:
    return public_dir / "issues" / f"{slug}.epub"


def build_manifest(
    cfg: Config, slot: Slot, articles: list[Article], result: EpubResult, built_at: datetime
) -> Manifest:
    counts = {"requested": cfg.content.story_count, "returned": len(articles)}
    for status in Status:
        counts[status.value] = sum(1 for a in articles if a.status is status)
    return Manifest(
        schema=SCHEMA,
        slug=slot.slug,
        slot_label=slot.label,
        slot_at=slot.at,
        built_at=built_at,
        feed=cfg.content.feed,
        xtpages_version=__version__,
        story_ids=[a.story.id for a in articles],
        entries=[
            {
                "id": a.story.id,
                "title": a.story.title,
                "url": a.story.url,
                "hn_url": a.story.hn_url,
                "domain": a.story.domain,
                "score": a.story.score,
                "by": a.story.by,
                "time": a.story.time,
                "status": a.status.value,
                "chars": a.chars,
                "error": a.error,
            }
            for a in articles
        ],
        counts=counts,
        epub={
            "filename": result.filename,
            "bytes": result.bytes,
            "sha256": result.sha256,
            "title": None,
        },
    )


def write_manifest(manifest: Manifest, public_dir: Path, title: str) -> None:
    payload = {
        "schema": manifest.schema,
        "slug": manifest.slug,
        "slot_label": manifest.slot_label,
        "slot_at": iso(manifest.slot_at),
        "built_at": iso(manifest.built_at),
        "feed": manifest.feed,
        "xtpages_version": manifest.xtpages_version,
        "story_ids": manifest.story_ids,
        "entries": manifest.entries,
        "counts": manifest.counts,
        "epub": {**manifest.epub, "title": title},
    }
    write_atomic(
        manifest_path(public_dir, manifest.slug),
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    )


def read_manifests(public_dir: Path) -> list[Manifest]:
    """Every readable manifest, newest slot first. Corrupt files are skipped."""
    issues = public_dir / "issues"
    if not issues.is_dir():
        return []
    found = []
    for path in sorted(issues.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if int(raw.get("schema", 0)) != SCHEMA:
                print(f"warning: {path.name}: unknown schema, skipping", file=sys.stderr)
                continue
            found.append(
                Manifest(
                    schema=raw["schema"],
                    slug=raw["slug"],
                    slot_label=raw["slot_label"],
                    slot_at=datetime.fromisoformat(raw["slot_at"].replace("Z", "+00:00")),
                    built_at=datetime.fromisoformat(raw["built_at"].replace("Z", "+00:00")),
                    feed=raw.get("feed", "top"),
                    xtpages_version=raw.get("xtpages_version", "?"),
                    story_ids=[int(i) for i in raw.get("story_ids", [])],
                    entries=raw.get("entries", []),
                    counts=raw.get("counts", {}),
                    epub=raw.get("epub", {}),
                )
            )
        except (ValueError, KeyError, OSError) as exc:
            print(f"warning: {path.name}: unreadable ({exc}), skipping", file=sys.stderr)
    return sorted(found, key=lambda m: m.slot_at, reverse=True)


def previous_story_ids(manifests: list[Manifest], current_slug: str, lookback: int) -> set[int]:
    """Story IDs to exclude. Excluding the current slug is what makes a re-run safe."""
    if lookback <= 0:
        return set()
    others = [m for m in manifests if m.slug != current_slug][:lookback]
    return {story_id for m in others for story_id in m.story_ids}


def prune(cfg: Config, public_dir: Path, now: datetime | None = None) -> list[str]:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    cutoff = now - timedelta(days=cfg.retention_days)
    removed = []
    for manifest in read_manifests(public_dir):
        if manifest.slot_at < cutoff:
            for path in (
                manifest_path(public_dir, manifest.slug),
                epub_path(public_dir, manifest.slug),
            ):
                if path.name in KEEP_ALWAYS:
                    continue
                path.unlink(missing_ok=True)
            removed.append(manifest.slug)
    return removed


def refresh_latest(public_dir: Path) -> str | None:
    """Copy the issue with the greatest slot instant to latest.epub (SPEC 8.5).

    Not necessarily the issue just built: a manual --slot run can rebuild an
    older slot, and that must not demote the newest issue.
    """
    manifests = read_manifests(public_dir)
    for manifest in manifests:
        source = epub_path(public_dir, manifest.slug)
        if source.exists():
            shutil.copyfile(source, public_dir / "latest.epub")
            return manifest.slug
    return None
