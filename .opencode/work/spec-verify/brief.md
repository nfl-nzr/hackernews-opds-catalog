# xtpages SPEC Verification Plan

Goal: verify SPEC.md (1228 lines) before implementation. Repo has only SPEC.md, README.md,
.gitignore. Firmware source for §12.3 claims is at `/Users/nflnzr/Documents/crosspoint/crosspoint-reader`.

Ground rules (all sub-stages):
- Verdict vocabulary per claim: `CONFIRMED` / `REFUTED` / `NOT FOUND` / `UNVERIFIABLE` (with why).
- Every verdict cites evidence: URL (S1/S2), `file:line` (S3), or spec line/section refs (S4).
- Read-only on project files. S2 may create throwaway venvs only under `/var/folders/ht/ywhzbt5n02z_k8kwgj1h8vnm0000gn/T/opencode`.
- Artifacts are written into this directory (`.opencode/work/spec-verify/`).

## Sub-stages

### S1 — GitHub Actions / Pages platform facts
- **ID**: S1 · **Name**: Platform claim verification (web)
- **Scope**: Spec §7.1, §11, §11.1, §12.1, §16 vs GitHub official docs; artifact `research-Q1.md`
- **Depends on**: none
- **Spec** — verify each against docs.github.com (prefer official docs over blog posts; label anything only supported by community anecdotes):
  - (a) `github.event.schedule` carries the exact cron string that triggered a scheduled run (spec admits unverified — §7.1/§16). Source: "Events that trigger workflows" + `github` context docs.
  - (b) Scheduled runs are routinely 5–30 min late. Official docs say "may be delayed" during high load — determine if the 5–30 min figure is documented or anecdotal.
  - (c) Default `GITHUB_TOKEN` can push to `gh-pages` when Settings → Workflow permissions → "Read and write" is set (§12.1).
  - (d) GitHub Pages serves `.xml` with an XML content type (`application/xml` or `text/xml` — acceptance criterion §14.3.8). Likely undocumented per-extension: mark UNVERIFIABLE unless found; suggest empirical curl of a known `github.io/.xml` URL as the definitive check.
  - (e) Scheduled workflows auto-disabled after 60 days of repo inactivity, with email notice ("Disabling and enabling a workflow").
  - (f) Free-plan GitHub Pages requires the repo to be public ("About GitHub Pages").
  - (g) `concurrency` group with `cancel-in-progress: false` queues (not drops) pending runs — check the >1 pending run behavior too.
  - (h) Single-commit force-push (orphan branch) to `gh-pages` is a known-good pattern (e.g. peaceiris/actions-gh-pages docs, GitHub community threads); note documented tradeoffs.
  - (i) `astral-sh/setup-uv@v5` exists and supports `python-version` + `enable-cache` inputs as used in §11 — check the action's `action.yml`.
  - (j) `actions/checkout@v4` is the current major (check latest release; v5 may exist).
- **Definition of done**: `research-Q1.md` lists (a)–(j), each with verdict + citation URL + one-sentence consequence for the spec if refuted.

### S2 — Python library API facts
- **ID**: S2 · **Name**: Library API verification at today's resolved versions
- **Scope**: Spec §5, §8.2, §8.3 vs PyPI/docs/source of trafilatura, httpx, nh3, ebooklib; artifact `research-Q2.md`
- **Depends on**: none
- **Spec**:
  - (a) `trafilatura.extract()` accepts exactly the kwargs of §8.2: `output_format="html"`, `include_comments`, `include_tables`, `include_images`, `include_links`, `favor_precision`, `url`. This is the spec's self-declared most dangerous assumption — check current signature in source/docs; confirm `"html"` is a valid `output_format`.
  - (b) httpx supports capping redirects at 5 (`follow_redirects` + `max_redirects`) and streaming a body with a max-bytes abort (e.g. `iter_bytes` chunk loop) per §8.2.
  - (c) nh3 ≥ 0.2 exposes `clean()` and/or `Cleaner` with tag + attribute allowlists as §8.3 assumes — check nh3 docs (ammonia binding) for the exact parameter names.
  - (d) ebooklib ≥ 0.20 writes EPUB3 with `mimetype` as the first uncompressed ZIP entry and generates both `nav.xhtml` and `toc.ncx` by default (§8.3).
  - (e) trafilatura ≥ 2.2 exists and is the current major/minor on PyPI.
  - If web docs are ambiguous on any item, say explicitly: "a local `uv` smoke test in a temp dir is the definitive check", and give a ready-to-run one-liner (e.g. `uv run --with trafilatura python -c ...` under the tmp dir) instead of guessing.
- **Definition of done**: `research-Q2.md` lists (a)–(e) with verdicts, exact version numbers checked, and citations; ambiguities carry a concrete smoke-test command.

### S3 — Firmware source verification
- **ID**: S3 · **Name**: Verify §12.3 against local CrossPoint firmware source
- **Scope**: `/Users/nflnzr/Documents/crosspoint/crosspoint-reader` (all read-only); artifact `explore.md`
- **Depends on**: none
- **Spec** — file map (confirmed present): `lib/OpdsParser/OpdsParser.cpp` (+`OpdsStream.cpp`), `src/util/OpdsFilename.cpp`, `src/util/StringUtils.cpp`, `lib/Epub/Epub/parsers/ChapterHtmlSlimParser.cpp/.h`, `lib/Epub/Epub/css/CssParser.cpp/.h`, `src/network/HttpDownloader.cpp/.h`, `src/OpdsServerStore.cpp` (+ locate its header). For every claim in spec §12.3 (lines 1050–1098), report CONFIRMED/REFUTED/NOT FOUND with `file:line` evidence:
  - OpdsParser.cpp: 62-entry cap derived from `ENTRY_STORAGE_CAPACITY` 64 minus 2; field limits title 160 / author 120 / id 128 / href 768; entry accepted only if rel indicates acquisition AND exact `strcmp` on type `"application/epub+zip"`; empty-title or no-link entries dropped; `rel="next"` pagination followed; `kind=` profile ignored.
  - OpdsFilename.cpp + StringUtils.cpp: filename composed from author+title; exact sanitization character set; 100-byte cap.
  - ChapterHtmlSlimParser.cpp: complete recognized-tag list; `<pre>` NOT recognized (drives §8.3.1 unwrap); `trimAndNormalize` whitespace collapsing; `li` renders self-bullet; table tag support (or absence); 1024 anchor cap.
  - CssParser.cpp/.h: full supported property list; confirm absence of `font-size`, `line-height`, `color`, `font-family`; which selector forms parse.
  - HttpDownloader.cpp: `esp_crt_bundle_attach` for TLS verification; 5-redirect cap; 60 s timeout; `MIN_TLS_FREE_HEAP` — 40 KB free and 20 KB largest block; preemptive (not challenge) basic auth.
  - OpdsServerStore: max 8 servers.
  - Bonus: anything in §12.3 the spec claims but the source contradicts, and any nearby constraint (e.g. content-type handling) the spec should have claimed.
- **Definition of done**: `explore.md` has one row per §12.3 claim with verdict + `file:line`; zero claims left unchecked; contradictions called out at top.

### S4 — Spec-internal consistency review
- **ID**: S4 · **Name**: Contradictions, undefined behaviors, and gaps within SPEC.md + README.md
- **Scope**: SPEC.md itself, cross-referenced against README.md; artifact `consistency.md`
- **Depends on**: none (may cite S1–S3 results if available, but must not block on them)
- **Spec** — examine each numbered item, plus findings of your own; spec §2 claims "every decision is settled": find where it isn't:
  1. §2 "settled" vs §7.1/§16 self-declared unverified assumptions — list them all.
  2. `xtpages build` prune+catalog ordering in §9 vs §3's numbered steps — same order?
  3. `latest.epub` refresh: defined for the zero-story exit-3 path?
  4. First run with no previous manifest: is dedupe no-op behavior stated?
  5. §6.1 62-entry validation vs retention 14 days × 2 slots = 28 — does the bound interact correctly (and does S3's confirmed 62 make the validation redundant)?
  6. `--dry-run` fully specified for a first run with no `./public` dir?
  7. Workflow passes `--slot "${{ github.event.inputs.slot }}"` — empty string on schedule events; does `resolve_slot` treat `""` identically to `None`?
  8. `p.code` styled in §10 CSS while `code` is absent from §8.3 sanitizer allowlist — consistent?
  9. §8.3 title-page spec vs §14.1 `test_epub.py` expectations — do they match?
  10. Committed `uv.lock` requirement vs `uv sync --frozen` usage — consistent and sufficient?
  11. §13 exit codes: is every failure row in the table assigned a code, and are codes used consistently in §9/§11?
  12. README vs SPEC: README says "top 20 stories" (spec makes count configurable?); README's `./scripts/serve.sh` and `config.yaml`/`schedule.slots` claims vs spec.
  13. §4 repo-layout tree completeness vs everything referenced elsewhere: `config.yaml`, `scripts/serve.sh` (required by §14.4 but absent from §4 tree — flag this class of omission), `tests/fixtures/*`, `.github/workflows/ci.yml` (§11.2).
  14. Own findings: any other undefined behavior, ordering ambiguity, or gap; note sections §10.2–§10.4 (catalog/nav/index) vs §8.4 for drift.
- **Definition of done**: `consistency.md` numbers every finding with spec line refs, a severity (blocker / should-fix / cosmetic), and a suggested resolution; explicit "no issue found" where an item checks out clean.

### S5 — Reconciled summary and verdict
- **ID**: S5 · **Name**: Merge S1–S4 into final verdict
- **Scope**: All prior artifacts; final deliverable `summary.md` (+ this plan's resolution for the user)
- **Depends on**: S1, S2, S3, S4
- **Spec**: merge into four buckets: (1) spec claims CONFIRMED as written; (2) claims REFUTED/wrong with the correction to make in SPEC.md; (3) claims UNVERIFIABLE before implementation (empirical-only), each with the cheapest experiment that will settle it post-implementation; (4) gaps/contradictions from S4. End with a prioritized (blockers first) list of decisions the user must make — resolve or explicitly accept — before implementation begins.
- **Definition of done**: `summary.md` is self-contained (no need to read S1–S4 to act), every item traces back to its source artifact, and the prioritized list is ordered with a one-line rationale per item.
