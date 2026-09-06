"""Command-line interface. See SPEC.md section 9.

Exit codes: 0 success, 1 unexpected error, 2 config invalid, 3 zero usable stories.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from xtpages import __version__, catalog, epub, extract, hn, publish
from xtpages.config import (
    ConfigError,
    config_crons,
    find_repo_root,
    load,
    workflow_crons,
)
from xtpages.models import Status
from xtpages.publish import SlotError

EXIT_OK, EXIT_ERROR, EXIT_CONFIG, EXIT_EMPTY = 0, 1, 2, 3


def _select(cfg, public_dir: Path, slug: str):
    """Story selection with deduplication. See SPEC.md section 8.5."""
    manifests = publish.read_manifests(public_dir)
    excluded = (
        publish.previous_story_ids(manifests, slug, cfg.dedupe.lookback_issues)
        if cfg.dedupe.enabled
        else set()
    )
    if excluded:
        print(f"dedupe: excluding {len(excluded)} stories from recent issues")

    ids = hn.fetch_story_ids(cfg, cfg.dedupe.candidate_pool)
    print(f"feed: {len(ids)} candidate ids from {cfg.content.feed}stories")
    candidates = [i for i in ids if i not in excluded]
    stories = hn.fetch_stories(cfg, candidates)
    selected = stories[: cfg.content.story_count]
    if len(selected) < cfg.content.story_count:
        print(
            f"warning: only {len(selected)} of {cfg.content.story_count} stories "
            f"survived the candidate pool",
            file=sys.stderr,
        )
    return selected


def cmd_build(args) -> int:
    cfg = load(args.config)
    slot = publish.resolve_slot(cfg, args.cron, args.slot)
    public_dir = Path(args.public_dir)
    built_at = datetime.now(UTC)
    print(f"xtpages {__version__} building {slot.slug} (slot {publish.iso(slot.at)})")

    stories = _select(cfg, public_dir, slot.slug)
    # Short-circuit before any article fetch: no point downloading twenty
    # articles to discover the feed was empty (SPEC 13).
    if not stories:
        print("error: zero usable stories; leaving the existing site untouched", file=sys.stderr)
        return EXIT_EMPTY

    print(f"fetching {len(stories)} articles")
    started = time.monotonic()
    articles = extract.fetch_articles(cfg, stories)
    for article in articles:
        print(f"  [{article.status.value:18}] {article.chars:>6} chars  {article.story.link}")
    print(f"fetched in {time.monotonic() - started:.1f}s")

    tally = {s.value: sum(1 for a in articles if a.status is s) for s in Status}
    print("summary: " + "  ".join(f"{k}={v}" for k, v in tally.items() if v))

    if args.dry_run:
        print("dry-run: no files written")
        return EXIT_OK

    result = epub.build_epub(
        cfg, slot, articles, publish.epub_path(public_dir, slot.slug), built_at
    )
    print(f"wrote {result.filename} ({result.bytes // 1024} KB)")

    manifest = publish.build_manifest(cfg, slot, articles, result, built_at)
    publish.write_manifest(manifest, public_dir, epub.issue_title(cfg, slot))

    removed = publish.prune(cfg, public_dir)
    if removed:
        print(f"pruned {len(removed)}: {', '.join(removed)}")
    latest = publish.refresh_latest(public_dir)
    if latest:
        print(f"latest.epub -> {latest}")

    catalog.write_all(cfg, publish.read_manifests(public_dir), public_dir)
    print(f"catalog: {cfg.url_for('catalog.xml')}")
    return EXIT_OK


def cmd_catalog(args) -> int:
    cfg = load(args.config)
    public_dir = Path(args.public_dir)
    manifests = publish.read_manifests(public_dir)
    catalog.write_all(cfg, manifests, public_dir)
    print(f"catalog rebuilt with {len(manifests)} entries")
    return EXIT_OK


def cmd_prune(args) -> int:
    cfg = load(args.config)
    public_dir = Path(args.public_dir)
    removed = publish.prune(cfg, public_dir)
    print(f"pruned {len(removed)}" + (f": {', '.join(removed)}" if removed else ""))
    catalog.write_all(cfg, publish.read_manifests(public_dir), public_dir)
    return EXIT_OK


def cmd_doctor(args) -> int:
    cfg = load(args.config)
    print(f"xtpages {__version__}")
    print(f"config:   {Path(args.config).resolve()}")
    print(f"feed:     {cfg.content.feed}, {cfg.content.story_count} stories")
    print(f"retention:{cfg.retention_days} days")
    entries = cfg.retention_days * len(cfg.slots) + 1
    print(f"catalog:  up to {entries} entries (device limit 62)")

    root = find_repo_root(args.config)
    workflow = root / ".github" / "workflows" / "build.yml" if root else None
    if workflow and workflow.exists():
        found, wanted = workflow_crons(workflow), config_crons(cfg)
        if sorted(found) == sorted(wanted):
            print(f"schedule: in sync {wanted}")
        else:
            print(f"schedule: OUT OF SYNC — workflow {found} vs config {wanted}", file=sys.stderr)
            return EXIT_CONFIG
    else:
        print("schedule: warning, no .github/workflows/build.yml found to compare", file=sys.stderr)

    print()
    print("Add this to your reader as an OPDS server:")
    print(f"  {cfg.url_for('catalog.xml')}")
    print(f"  (fallback feed: {cfg.url_for('nav.xml')})")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xtpages", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command", required=True)

    def common(sub, public=True):
        sub.add_argument("--config", default="config.yaml")
        if public:
            sub.add_argument("--public-dir", default="public")

    build = subs.add_parser("build", help="build one issue and republish the site")
    common(build)
    build.add_argument("--cron", default="", help="cron expression that triggered this run")
    build.add_argument("--slot", default="", help="slot label, e.g. 0300")
    build.add_argument("--dry-run", action="store_true")
    build.set_defaults(func=cmd_build)

    cat = subs.add_parser("catalog", help="regenerate catalog.xml, nav.xml, index.html")
    common(cat)
    cat.set_defaults(func=cmd_catalog)

    pr = subs.add_parser("prune", help="delete issues past retention_days")
    common(pr)
    pr.set_defaults(func=cmd_prune)

    doc = subs.add_parser("doctor", help="validate config and print the OPDS URL")
    common(doc, public=False)
    doc.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except SlotError as exc:
        print(f"slot error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except KeyboardInterrupt:
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
