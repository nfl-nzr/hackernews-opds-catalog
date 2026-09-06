# xtpages — Build Specification

**Status:** approved for implementation
**Audience:** the engineer or coding agent implementing this repository from scratch
**Version:** 1.0

This document is the complete build contract. Every decision below is settled — where
you see a value, use that value. If you hit something genuinely not covered here, prefer
the simplest choice consistent with the surrounding rules and note it in your final
summary; do not redesign a settled decision.

---

## 1. What this repository does

`xtpages` publishes a Hacker News reading digest as EPUB files to a public website, and
publishes a catalog file that an e-reader can browse and download from over WiFi.

Twice a day, a GitHub Actions job:

1. asks Hacker News for its current top stories,
2. downloads each linked article and extracts the readable text,
3. packs the extracted articles into a single EPUB file (one "issue"),
4. copies that EPUB onto a public GitHub Pages site,
5. regenerates a catalog listing the last 14 days of issues,
6. deletes issues older than 14 days.

The reader device is configured once with the catalog's URL. From then on, opening the
catalog on the device shows the newest issue at the top, and the user taps it to download.

### Terms used throughout

- **OPDS** — Open Publication Distribution System. A published catalog format: an Atom
  XML file listing publications, each with a download link. It is a plain static file;
  there is no server process. E-reader firmware that "supports OPDS" is an HTTP client
  that fetches such a file, renders the entry list, and downloads the file behind an
  entry when the user selects it.
- **Issue** — one EPUB file containing one batch of articles. Two issues per day.
- **Slot** — the scheduled time an issue belongs to, `0300` or `2100`, always UTC. An
  issue's identity comes from its slot, not from the wall-clock time the job actually
  ran, because scheduled GitHub Actions runs are frequently delayed.
- **Manifest** — a JSON file published next to each EPUB recording which stories went
  into it. The next run reads it to avoid repeating stories.
- **Public directory** — the working copy of the published website during a build,
  checked out at `./public`. Its contents become the `gh-pages` branch.

### The target device

The Xteink X4 (and X3 / X4 Pro), on either stock firmware or CrossPoint firmware. Both
support adding an OPDS server by URL. On CrossPoint: **Settings → System → OPDS Servers
→ Add Server**, which takes an optional display name, a URL, and optional HTTP Basic
credentials (leave the credentials blank — our catalog is public). The device stores up
to 8 servers.

Constraints that follow from the hardware, and that shape the EPUB output:

- 4-inch greyscale e-ink panel. Images are close to worthless and cost file size and
  render time, so **images are stripped by default**.
- Supported document formats are EPUB and TXT. We emit EPUB.
- The renderer is an embedded one. Keep markup to a conservative subset (section 8.3);
  do not rely on CSS beyond basic block layout.

### What the user does daily

Opens the OPDS catalog on the device, taps the newest issue, waits for the download.
**The device does not poll or auto-sync.** No firmware feature downloads on a schedule.
"Daily delivery" means the file is reliably waiting; fetching it is one deliberate tap.
Do not design around a background-sync capability that does not exist.

---

## 2. Settled decisions

| Decision | Value | Why |
|---|---|---|
| Content | Top 20 stories, article text only | Roughly a 45-minute read; smallest and most reliable build |
| Comments | **Not in v1** | Deferred to v2. Do not write comment-fetching code. See section 15 |
| Schedule | 03:00 and 21:00 UTC, twice daily | Set by the owner; must be forker-configurable (section 7) |
| Overlap | **Deduplicate against the previous issue** | HN's front page barely moves in 18 hours; without this the 21:00 issue is mostly a reprint |
| Retention | Rolling 14 days | 28 issues in the catalog; site stays small and scannable |
| Language | Python 3.12, `uv` for dependency management | `trafilatura` is the strongest extraction library in any language |
| robots.txt | **Ignored**, with an identifying User-Agent | Owner's explicit choice. See section 6.4 for the obligations that replace it |
| Hosting | GitHub Pages from a `gh-pages` branch | Static, free, HTTPS, no server to run |
| Repo visibility | Public | Required for free GitHub Pages on a free account |

---

## 3. Architecture

```
                 ┌──────────────────────────────────────────┐
   cron 03:00 →  │  GitHub Actions: build.yml               │
   cron 21:00 →  │                                          │
                 │  1. checkout code (main)                 │
                 │  2. checkout site (gh-pages → ./public)  │
                 │  3. xtpages build                        │
                 │       ├── hn.py       fetch story list   │──→ hacker-news.firebaseio.com
                 │       ├── dedupe      read prev manifest │
                 │       ├── extract.py  fetch + readability│──→ the open web
                 │       ├── epub.py     build the EPUB     │
                 │       └── writes public/issues/*.epub    │
                 │  4. xtpages prune     drop >14 days      │
                 │  5. xtpages catalog   regenerate XML     │
                 │  6. force-push ./public → gh-pages       │
                 └──────────────────────────────────────────┘
                                     ↓
                     https://OWNER.github.io/REPO/catalog.xml
                                     ↓  (user taps, over WiFi)
                              Xteink X4
```

The build is a **pure function of (HN's current state, the previous issue's manifest)**.
It holds no state anywhere except the published site itself. There is no database, no
secret, and no external service beyond HN and the article hosts.

---

## 4. Repository layout

Create exactly this structure.

```
.
├── .github/
│   └── workflows/
│       ├── build.yml           # the scheduled build (section 11)
│       └── ci.yml              # lint + tests on push/PR (section 14.4)
├── src/
│   └── xtpages/
│       ├── __init__.py         # __version__ = "1.0.0"
│       ├── __main__.py         # enables `python -m xtpages`
│       ├── cli.py              # argparse entry point (section 9)
│       ├── config.py           # load + validate config.yaml (section 6)
│       ├── models.py           # dataclasses: Story, Article, Issue, Manifest
│       ├── hn.py               # Hacker News API client (section 8.1)
│       ├── extract.py          # article fetch + readability (section 8.2)
│       ├── epub.py             # EPUB generation (section 8.3)
│       ├── catalog.py          # OPDS + index.html generation (section 8.4)
│       ├── publish.py          # slug/slot logic, manifests, pruning (section 8.5)
│       └── html.py             # sanitizing + URL absolutizing helpers
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── hn_topstories.json
│   │   ├── hn_item_story.json
│   │   ├── hn_item_selfpost.json
│   │   ├── article_clean.html      # a well-structured article page
│   │   ├── article_messy.html      # nav/ads/sidebars around the body
│   │   └── article_paywall.html    # near-empty body behind a wall
│   ├── test_config.py
│   ├── test_hn.py
│   ├── test_extract.py
│   ├── test_epub.py
│   ├── test_catalog.py
│   ├── test_publish.py
│   └── test_schedule_sync.py
├── config.yaml                 # the forker's control panel (section 6)
├── pyproject.toml
├── uv.lock                     # committed
├── .gitignore
├── README.md                   # human setup guide (already written — keep in sync)
└── SPEC.md                     # this file
```

Nothing is generated into the repo root at build time. All build output goes to
`./public`, which is git-ignored on `main` and force-pushed to `gh-pages`.

### 4.1 The published site layout

This is what lives on the `gh-pages` branch and is served at
`https://OWNER.github.io/REPO/`:

```
public/
├── .nojekyll                       # REQUIRED: stops Pages running Jekyll on our files
├── catalog.xml                     # the OPDS acquisition feed — the URL for the device
├── nav.xml                         # OPDS navigation feed (fallback, section 10.3)
├── index.html                      # human-readable landing page
├── latest.epub                     # byte-copy of the newest issue, stable URL
└── issues/
    ├── hn-20260906-0300.epub
    ├── hn-20260906-0300.json       # manifest
    ├── hn-20260906-2100.epub
    ├── hn-20260906-2100.json
    └── …                           # 28 pairs at steady state
```

---

## 5. Dependencies

`pyproject.toml`, targeting Python 3.12:

```toml
[project]
name = "xtpages"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.28",         # HTTP client, sync API with explicit timeouts
    "trafilatura>=2.2",    # article body extraction
    "ebooklib>=0.20",      # EPUB writing
    "nh3>=0.2",            # HTML sanitizing (Rust ammonia bindings, maintained)
    "pyyaml>=6.0",         # config.yaml
    "lxml>=5.0",           # OPDS XML generation and HTML repair
]

[project.scripts]
xtpages = "xtpages.cli:main"

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Use `uv sync` to install and **commit `uv.lock`** — a scheduled job that silently picks
up a breaking library release at 03:00 is exactly the failure mode a lockfile prevents.

**Verify library signatures against the installed version before writing against them.**
In particular `trafilatura.extract()` has gained and renamed keyword arguments across
releases; confirm the ones in section 8.2 exist in the version `uv` resolves.

---

## 6. Configuration

`config.yaml` is the forker's entire control panel. Anything a reasonable forker would
want to change lives here, **except the schedule times themselves** — see section 7 for
why, and for what to do about it.

Ship this file with exactly these values:

```yaml
# ─── Content ────────────────────────────────────────────────────────────────
content:
  feed: top              # top | best | new  → HN's topstories/beststories/newstories
  story_count: 20        # articles per issue
  min_score: 0           # skip stories below this point total (0 = no filter)
  skip_domains: []       # e.g. ["twitter.com", "x.com"] — never fetched, link-only
  include_images: false  # true is untested on a 4-inch greyscale panel
  max_article_chars: 200000   # truncate absurdly long extractions
  include_hn_discussion_link: true

# ─── Deduplication ──────────────────────────────────────────────────────────
dedupe:
  enabled: true
  lookback_issues: 1     # how many previous issues' stories to exclude
  candidate_pool: 100    # story IDs pulled from the feed to backfill from

# ─── Retention ──────────────────────────────────────────────────────────────
retention_days: 14

# ─── Fetching ───────────────────────────────────────────────────────────────
fetch:
  timeout_seconds: 20
  max_concurrency: 5     # be a polite neighbour; do not raise casually
  retries: 2
  retry_backoff_seconds: 2
  max_bytes: 5000000     # abort a download past 5 MB
  user_agent: "xtpages/1.0 (+https://github.com/OWNER/REPO)"

# ─── Site identity ──────────────────────────────────────────────────────────
site:
  base_url: ""           # blank → derived from $GITHUB_REPOSITORY at build time
  title: "Hacker News Daily"
  author: "Hacker News"
  language: "en"

# ─── Schedule (MUST match .github/workflows/build.yml — see section 7) ───────
schedule:
  slots:
    - cron: "0 3 * * *"
      label: "0300"
    - cron: "0 21 * * *"
      label: "2100"

# ─── Reserved for v2 — do not implement ─────────────────────────────────────
# comments:
#   enabled: false
#   per_story: 10
```

### 6.1 Validation rules

`config.py` loads the file and raises `ConfigError` with a message naming the offending
key on any of these:

- `content.feed` not in `{top, best, new}`
- `content.story_count` not in `1..100`
- `dedupe.candidate_pool` < `content.story_count` (backfill would be impossible)
- `retention_days` < 1
- `fetch.max_concurrency` not in `1..10`
- `schedule.slots` empty, or any `label` not matching `^[0-9]{4}$`, or duplicate labels
- `site.base_url` non-blank and not starting with `https://`

Validation runs at the very start of every command, before any network call. A bad
config must fail in under a second, not after twenty article downloads.

### 6.2 Deriving `site.base_url`

If `site.base_url` is blank, build it from the `GITHUB_REPOSITORY` environment variable,
which Actions sets to `owner/repo`:

```
https://<owner-lowercased>.github.io/<repo>/
```

Always normalize to a trailing slash. If `site.base_url` is blank **and**
`GITHUB_REPOSITORY` is unset (a local run), fall back to `http://localhost:8000/` and
emit a warning — this keeps local builds working, and the resulting catalog is obviously
not for publishing.

A custom domain, or a repo named `OWNER.github.io` (served at the domain root, not a
subpath), is handled by the forker setting `site.base_url` explicitly.

### 6.3 Precedence

Command-line flags override config values, which override defaults. No environment
variables configure behaviour except `GITHUB_REPOSITORY` (above) and the git identity
used by the publish step.

### 6.4 Fetch conduct

The owner has chosen not to consult `robots.txt`. That decision stands, and it makes the
following non-negotiable, because they are what keeps this from being abusive:

- The User-Agent **must** identify the project and carry a URL a site owner can visit to
  see what is hitting them. Never impersonate a browser.
- `max_concurrency` is a global ceiling of 5 across the whole run, and additionally
  **never more than one in-flight request per host**.
- Honour HTTP `429` and `503` by giving up on that URL for this run. Do not retry
  through a rate-limit response; a link-only entry is the correct outcome.
- Never follow more than 5 redirects, and never fetch a non-`http(s)` scheme.
- Requests are `GET` only, article URLs only, one pass, no crawling. The build must
  never follow links found inside an article.

---

## 7. The schedule, and the one thing config cannot control

GitHub Actions reads `on.schedule.cron` from the workflow YAML file itself. It is parsed
by GitHub before any of our code runs, so **a cron expression cannot be read from
`config.yaml`.** There is no workaround short of a self-modifying workflow, which is not
worth it.

So the schedule lives in two places, and they must agree:

1. `.github/workflows/build.yml` — the real trigger.
2. `config.yaml` → `schedule.slots` — the mapping from cron expression to slot label,
   which the build uses to name the issue.

To keep a forker from silently desynchronizing them, **`tests/test_schedule_sync.py`
parses `build.yml`, extracts its cron list, and asserts it equals the set of
`schedule.slots[].cron` in `config.yaml`.** This test failing is the intended way a
forker discovers they edited only one of the two. `ci.yml` runs it on every push.

`build.yml` carries this comment block immediately above the cron lines:

```yaml
on:
  schedule:
    # ┌─────────────────────────────────────────────────────────────────┐
    # │ TO CHANGE THE SCHEDULE, EDIT BOTH PLACES:                       │
    # │   1. the cron lines below                                       │
    # │   2. schedule.slots in config.yaml (cron + a 4-digit label)     │
    # │ tests/test_schedule_sync.py fails if they disagree.             │
    # │ Times are UTC. GitHub does not honour timezones in cron.        │
    # │ Scheduled runs are often 5-30 minutes late under load; the      │
    # │ issue is still named for its slot, not the actual run time.     │
    # └─────────────────────────────────────────────────────────────────┘
    - cron: "0 3 * * *"
    - cron: "0 21 * * *"
```

### 7.1 Resolving which slot a run belongs to

For a `schedule` event, the webhook payload carries the cron expression that fired it,
available as `${{ github.event.schedule }}`. The workflow passes it through:

```
xtpages build --cron "${{ github.event.schedule }}"
```

`publish.resolve_slot()` implements this precedence:

1. An explicit `--slot LABEL` flag wins outright.
2. Otherwise, if `--cron` is given and matches a `schedule.slots[].cron`, use that
   slot's label. Match on the exact string after collapsing internal whitespace.
3. Otherwise (manual dispatch with no input, or a local run) pick the slot whose time is
   nearest to the current UTC time, and warn which one was chosen.

The **issue date** is the UTC date of the slot instant nearest to the run time, so a
21:00 job that actually runs at 00:40 the next day is still `…-2100` of the previous
day. Concretely: build candidate datetimes for the resolved slot on yesterday, today,
and tomorrow, and pick the one closest to now.

Re-running a slot that already exists **overwrites** it, in every artifact: EPUB,
manifest, and catalog entry. Runs are idempotent by design.

---

## 8. Module specifications

Signatures below are the contract. Types are indicative; use dataclasses in `models.py`.

### 8.1 `hn.py` — Hacker News client

Base URL `https://hacker-news.firebaseio.com/v0/`. No authentication, no documented rate
limit. Two endpoints are used:

- `GET /v0/{feed}stories.json` → a JSON array of up to 500 integer story IDs, already in
  the site's ranked order. `feed` is `top`, `best`, or `new`.
- `GET /v0/item/{id}.json` → one item object.

Story item fields used: `id`, `by`, `time` (Unix seconds), `title`, `url`, `score`,
`descendants`, `text`, `type`, `deleted`, `dead`.

```python
def fetch_story_ids(cfg: Config, limit: int) -> list[int]: ...
def fetch_story(cfg: Config, story_id: int) -> Story | None: ...
def fetch_stories(cfg: Config, ids: list[int]) -> list[Story]: ...   # concurrent, order preserved
```

Rules:

- Drop any item with `deleted` or `dead` true, or `type != "story"`. Return `None`.
- A story with no `url` is a **self-post** (Ask HN, Show HN with body text). It is kept:
  its `text` field is the article body. Its "link" is its HN discussion page.
- The HN discussion URL is `https://news.ycombinator.com/item?id={id}`.
- Apply `content.min_score` here.
- Fetch item detail concurrently, bounded by `fetch.max_concurrency`, preserving the
  input ID order in the returned list.

### 8.2 `extract.py` — article fetch and readability

```python
def fetch_article(cfg: Config, story: Story) -> Article: ...
def fetch_articles(cfg: Config, stories: list[Story]) -> list[Article]: ...
```

`Article` always comes back — **failure is a status, never an exception and never a
dropped story.** `Article.status` is one of:

| status | meaning | what goes in the EPUB |
|---|---|---|
| `ok` | body extracted | the article |
| `self_post` | HN self-post, `story.text` used | the post text |
| `extraction_failed` | fetched, but no usable body (paywall, JS-only) | link-only chapter |
| `non_html` | content-type is PDF/image/video/etc. | link-only chapter |
| `fetch_error` | timeout, DNS, TLS, 4xx/5xx, too large | link-only chapter |
| `skipped_domain` | matched `content.skip_domains` | link-only chapter |

Fetch procedure per article:

1. Skip if the host matches `content.skip_domains` (suffix match, so `x.com` matches
   `www.x.com`) → `skipped_domain`.
2. `GET` with the configured User-Agent, `timeout_seconds`, `follow_redirects=True`,
   max 5 redirects.
3. Reject on `Content-Type` not `text/html` or `application/xhtml+xml` → `non_html`.
4. Stream and abort past `fetch.max_bytes` → `fetch_error`.
5. Retry `fetch.retries` times with `retry_backoff_seconds` backoff **only** on timeouts,
   connection errors, and 5xx. Never retry a 4xx, a `429`, or a `503`.
6. Extract with trafilatura, requesting HTML output, comments off, tables on, images per
   config, and links preserved:

   ```python
   trafilatura.extract(
       html,
       output_format="html",
       include_comments=False,
       include_tables=True,
       include_images=cfg.content.include_images,
       include_links=True,
       favor_precision=True,
       url=story.url,          # lets trafilatura resolve relative URLs
   )
   ```

7. If the result is `None` or its text content is under **500 characters**, treat it as
   `extraction_failed`. That floor is what catches paywall stubs and cookie walls, which
   do return markup.
8. Absolutize any remaining relative `href` against the final response URL, then
   sanitize (section 8.3), then truncate to `content.max_article_chars` at a tag
   boundary.

Self-posts skip fetching entirely: `story.text` is HN-supplied HTML, so sanitize it and
set `self_post`.

### 8.3 `epub.py` — EPUB generation

```python
def build_epub(cfg: Config, issue: Issue, articles: list[Article], out_path: Path) -> EpubResult: ...
```

Use `ebooklib`. Produce EPUB 3 with an NCX table of contents included for EPUB 2
compatibility, which is what `ebooklib` does by default and what the device's renderer
is happiest with.

**Metadata**

| field | value |
|---|---|
| identifier | `urn:xtpages:issue:20260906-0300` |
| title | `Hacker News — 2026-09-06 03:00 UTC` (en dash, U+2013) |
| language | `config.site.language` |
| creator | `config.site.author` |
| date | the slot instant, ISO 8601 with `Z` |

**Documents, in spine order**

1. `title.xhtml` — the issue title, the build timestamp, and a numbered contents list of
   all story titles with their point totals. This is a real page, not just navigation:
   the device's own nav UI is cramped, and a contents page is the fastest way to decide
   what to read.
2. `ch001.xhtml` … `chNNN.xhtml` — one per story, in HN rank order, numbered from 1 with
   three digits.
3. `nav.xhtml` — the EPUB navigation document, not in the reading spine.

**Chapter structure**

```html
<h1>{story title}</h1>
<p class="meta">{score} points · {domain} · <a href="{hn_url}">Discussion</a></p>
<hr/>
{sanitized article body}
```

For any non-`ok`, non-`self_post` status, the body is exactly:

```html
<p class="notice">The full text could not be included ({status}).
Open the original: <a href="{url}">{url}</a></p>
```

Never omit a story because extraction failed. A 20-item issue always has 20 chapters;
the user decides whether a link is worth opening later.

**Sanitizing** — `html.py` exposes `sanitize(html: str) -> str` using `nh3`, allowing
only: `p h1 h2 h3 h4 h5 h6 ul ol li blockquote pre code em strong b i a br hr table
thead tbody tr th td figure figcaption sub sup small` plus `img` when
`content.include_images` is true. Allowed attributes: `href` on `a`, `src`/`alt` on
`img`. Everything else — `script`, `style`, `iframe`, `form`, `svg`, `video`, `audio`,
inline event handlers, and all `class`/`id`/`style` attributes — is stripped. This is not
paranoia about hostile content; constrained e-ink renderers stall or mis-paint on markup
they do not expect.

**Stylesheet** — one small `style.css`, sizes in `em` only, never `px`, because the
device controls font size and a fixed pixel size fights it:

```css
body { margin: 0; padding: 0; }
h1 { font-size: 1.3em; margin: 0 0 0.3em; }
p { margin: 0 0 0.7em; text-indent: 0; }
p.meta { font-size: 0.85em; margin-bottom: 0.5em; }
p.notice { font-style: italic; }
pre { white-space: pre-wrap; word-wrap: break-word; font-size: 0.85em; }
blockquote { margin: 0 0 0.7em 1em; }
img { max-width: 100%; }
```

`pre { white-space: pre-wrap }` matters: HN links to a lot of code, and a 4-inch screen
cannot scroll horizontally out of a wide `<pre>`.

### 8.4 `catalog.py` — OPDS and landing page

```python
def write_catalog(cfg: Config, issues: list[IssueRecord], public_dir: Path) -> None: ...
def write_nav(cfg: Config, public_dir: Path) -> None: ...
def write_index_html(cfg: Config, issues: list[IssueRecord], public_dir: Path) -> None: ...
```

The catalog is regenerated from scratch on every run by scanning `public/issues/*.json`.
It is never patched incrementally — a full rebuild from the manifests on disk means a
corrupted or half-written catalog self-heals on the next run.

Order: **newest issue first**, by slot instant descending.

All `href` values are **absolute**, built from `site.base_url`. Relative URLs are legal
OPDS and most clients resolve them correctly, but embedded firmware clients are the
least reliable place to depend on correct base-URI resolution, and absolute URLs cost
nothing.

See section 10 for the exact XML.

### 8.5 `publish.py` — slots, manifests, retention

```python
def resolve_slot(cfg: Config, cron: str | None, slot: str | None, now: datetime) -> Slot: ...
def issue_slug(slot: Slot) -> str: ...                      # "hn-20260906-0300"
def write_manifest(issue: Issue, articles: list[Article], epub: EpubResult, public_dir: Path) -> None: ...
def read_manifests(public_dir: Path) -> list[Manifest]: ...  # sorted newest-first, corrupt files skipped with a warning
def previous_story_ids(manifests: list[Manifest], current_slug: str, lookback: int) -> set[int]: ...
def prune(cfg: Config, public_dir: Path, now: datetime) -> list[str]: ...
```

**Deduplication** — `previous_story_ids` takes the union of `story_ids` from the most
recent `lookback` manifests, **excluding any manifest whose slug equals the issue being
built right now.** That exclusion is what makes re-running a slot safe; without it, a
re-run would exclude its own stories and produce a completely different issue.

Selection then works like this:

1. Fetch `dedupe.candidate_pool` (100) story IDs from the feed.
2. Drop IDs in the exclusion set.
3. Fetch item details in order, dropping deleted/dead/non-story and sub-`min_score` items.
4. Take the first `content.story_count` survivors.
5. If fewer than `story_count` survive the whole pool, build the issue with what there
   is and record the shortfall in the manifest. Do not fail the run.

**Pruning** deletes both files of any issue whose slot instant is older than
`retention_days` before now. It never deletes `latest.epub`, `catalog.xml`, `nav.xml`,
`index.html`, or `.nojekyll`. It returns the list of deleted slugs for the log.

**`latest.epub`** is a byte copy — not a symlink, which git and static hosting handle
inconsistently — of the newest issue's EPUB, refreshed after every build.

---

## 9. Command-line interface

```
xtpages build   [--cron EXPR] [--slot LABEL] [--public-dir DIR] [--config PATH] [--dry-run]
xtpages catalog [--public-dir DIR] [--config PATH]
xtpages prune   [--public-dir DIR] [--config PATH]
xtpages doctor  [--config PATH]
```

- `build` — the whole pipeline for one issue: select, fetch, extract, write EPUB, write
  manifest, refresh `latest.epub`, then prune, then regenerate catalog + nav + index.
  One command does everything the workflow needs; `catalog` and `prune` exist separately
  for local repair.
- `--dry-run` — do everything except write files; print what would be written. Used to
  test extraction changes without touching the site.
- `doctor` — validate `config.yaml`, confirm cron/config schedule agreement, resolve
  `site.base_url`, and print the OPDS URL to enter on the device. No network calls.

Defaults: `--config ./config.yaml`, `--public-dir ./public`.

**Exit codes:** `0` success; `1` unexpected error; `2` config invalid; `3` build produced
zero usable stories (see section 13).

**Logging** goes to stdout, one line per article as it completes, plus a final summary
table of statuses. Actions logs are the only debugging surface for a 03:00 failure, so
log the URL, status, elapsed time, and extracted character count for every story.

---

## 10. Data formats

These are contracts, not sketches. Reproduce the structure exactly.

### 10.1 Manifest — `public/issues/hn-20260906-0300.json`

Written next to every EPUB. It exists for three jobs: deduplication input for the next
run, catalog regeneration input, and post-mortem debugging of a bad issue.

```json
{
  "schema": 1,
  "slug": "hn-20260906-0300",
  "slot_label": "0300",
  "slot_at": "2026-09-06T03:00:00Z",
  "built_at": "2026-09-06T03:07:41Z",
  "feed": "top",
  "xtpages_version": "1.0.0",
  "story_ids": [45123456, 45123401],
  "entries": [
    {
      "id": 45123456,
      "title": "A thing someone built",
      "url": "https://example.com/a-thing",
      "hn_url": "https://news.ycombinator.com/item?id=45123456",
      "domain": "example.com",
      "score": 412,
      "by": "someuser",
      "time": 1788657600,
      "status": "ok",
      "chars": 18234,
      "error": null
    },
    {
      "id": 45123401,
      "title": "Something behind a paywall",
      "url": "https://paper.example/story",
      "hn_url": "https://news.ycombinator.com/item?id=45123401",
      "domain": "paper.example",
      "score": 288,
      "by": "another",
      "time": 1788651000,
      "status": "extraction_failed",
      "chars": 0,
      "error": "body under 500 chars after extraction"
    }
  ],
  "counts": { "ok": 18, "self_post": 1, "extraction_failed": 1, "requested": 20 },
  "epub": {
    "filename": "hn-20260906-0300.epub",
    "bytes": 412345,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  }
}
```

`story_ids` is the deduplication key and must list **every** story in the issue,
including the ones whose extraction failed — the user saw the headline either way, so a
repeat in the next issue is still a repeat.

`schema` is a version integer. If a future manifest format diverges, `read_manifests`
skips manifests whose `schema` it does not understand, with a warning, rather than
crashing the build on files written by an older version still inside the 14-day window.

### 10.2 `public/catalog.xml` — the OPDS acquisition feed

**This is the URL the user enters on the device.** Generate it exactly like this, one
`<entry>` per retained issue, newest first:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:dc="http://purl.org/dc/terms/">
  <id>urn:xtpages:catalog</id>
  <title>Hacker News Daily</title>
  <updated>2026-09-06T03:07:41Z</updated>
  <author>
    <name>xtpages</name>
    <uri>https://github.com/OWNER/REPO</uri>
  </author>
  <link rel="self"
        href="https://owner.github.io/REPO/catalog.xml"
        type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
  <link rel="start"
        href="https://owner.github.io/REPO/catalog.xml"
        type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
  <entry>
    <id>urn:xtpages:issue:20260906-0300</id>
    <title>Hacker News — 2026-09-06 03:00 UTC</title>
    <updated>2026-09-06T03:07:41Z</updated>
    <dc:issued>2026-09-06T03:00:00Z</dc:issued>
    <dc:language>en</dc:language>
    <author><name>Hacker News</name></author>
    <summary type="text">20 stories · A thing someone built · Something behind a paywall · …</summary>
    <link rel="http://opds-spec.org/acquisition"
          href="https://owner.github.io/REPO/issues/hn-20260906-0300.epub"
          type="application/epub+zip"
          length="412345"/>
  </entry>
</feed>
```

Requirements, from the OPDS 1.2 specification:

- The feed needs `atom:id`, `atom:title`, `atom:updated`, and `atom:author`.
- Every entry needs `atom:id`, `atom:title`, `atom:updated`, and at least one link whose
  `rel` begins with `http://opds-spec.org/acquisition`.
- The acquisition-feed media type is
  `application/atom+xml;profile=opds-catalog;kind=acquisition`. Emit it with no spaces
  around the semicolons, as written above.
- `length` is the EPUB's size in bytes. It is optional in the spec, but a device that
  knows the size before downloading can show a progress bar instead of a spinner.

Generation details:

- Build the XML with `lxml.etree`, never string concatenation. Titles come from the open
  web and will eventually contain `&`, `<`, and stray control characters.
- All timestamps are ISO 8601 UTC with a literal `Z`, seconds precision, no microseconds.
- `feed/updated` is the newest entry's `updated`.
- The `summary` lists the story titles joined by ` · `, truncated to **400 characters**
  with a trailing `…`. This is what the device shows under each catalog row, so leading
  with the count then the headlines makes the list scannable without opening anything.
- Strip characters illegal in XML 1.0 (most C0 controls) from every text node.

The `start` link points at this same acquisition feed. The specification associates
`start` with a navigation feed, but this catalog's root *is* the acquisition feed, and
pointing `start` anywhere else would send a client that follows it into a second
document for no benefit.

### 10.3 `public/nav.xml` — navigation feed, kept as a fallback

Most OPDS clients accept an acquisition feed as the catalog root. If the Xteink's client
turns out to reject one and insist on a navigation feed, the fix must not require a code
change at 6am — so publish this alongside, and the fallback is the user re-entering a
different URL on the device.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:xtpages:nav</id>
  <title>Hacker News Daily</title>
  <updated>2026-09-06T03:07:41Z</updated>
  <author><name>xtpages</name></author>
  <link rel="self"
        href="https://owner.github.io/REPO/nav.xml"
        type="application/atom+xml;profile=opds-catalog;kind=navigation"/>
  <link rel="start"
        href="https://owner.github.io/REPO/nav.xml"
        type="application/atom+xml;profile=opds-catalog;kind=navigation"/>
  <entry>
    <id>urn:xtpages:nav:issues</id>
    <title>Recent issues</title>
    <updated>2026-09-06T03:07:41Z</updated>
    <content type="text">The last 14 days of Hacker News digests</content>
    <link rel="subsection"
          href="https://owner.github.io/REPO/catalog.xml"
          type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
  </entry>
</feed>
```

Section 12.2 covers testing which of the two the device prefers.

### 10.4 `public/index.html`

A plain, dependency-free landing page: the site title, the OPDS URL in a `<code>` block
with setup instructions, a link to `latest.epub`, and a table of the retained issues
(date, story count, size, download link). No JavaScript, no external assets, no CDN.
This page is how a human confirms the pipeline ran without opening the device.

---

## 11. The GitHub Actions workflow

`.github/workflows/build.yml`:

```yaml
name: Build issue

on:
  schedule:
    # See SPEC.md section 7 — the schedule lives in TWO places.
    # To change it, edit BOTH the cron lines here AND schedule.slots in config.yaml.
    # tests/test_schedule_sync.py fails if they disagree.
    # Times are UTC; GitHub cron has no timezone support.
    # Scheduled runs are commonly 5-30 minutes late; the issue is still named
    # for its slot, not for the time the job actually started.
    - cron: "0 3 * * *"
    - cron: "0 21 * * *"
  workflow_dispatch:
    inputs:
      slot:
        description: "Slot label to build, e.g. 0300. Blank picks the nearest slot."
        required: false
        default: ""

permissions:
  contents: write

concurrency:
  group: xtpages-publish
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"
          enable-cache: true

      - run: uv sync --frozen

      - name: Fetch published site into ./public
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          if git ls-remote --exit-code --heads origin gh-pages >/dev/null 2>&1; then
            git clone --depth 1 --branch gh-pages \
              "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" public
          else
            echo "gh-pages does not exist yet; starting a fresh site"
            mkdir -p public
          fi

      - name: Build issue
        run: |
          uv run xtpages build \
            --cron "${{ github.event.schedule }}" \
            --slot "${{ github.event.inputs.slot }}" \
            --public-dir public

      - name: Publish to gh-pages
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          cd public
          touch .nojekyll
          rm -rf .git
          git init -q -b gh-pages
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          git commit -q -m "Build $(date -u +%Y-%m-%dT%H:%MZ)"
          git push -q --force \
            "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" gh-pages
```

### 11.1 Why the site branch is rebuilt, not appended to

`rm -rf .git && git init` in the publish step means **`gh-pages` always has exactly one
commit**, and every push replaces its history.

The reason is repository size. Two issues a day at roughly half a megabyte each adds
around 350 MB of git objects per year, and deleting old EPUBs at the 14-day mark does
not reclaim any of it — git keeps every blob it has ever committed, forever, reachable
from history. A repository that grows without bound until clones time out is a slow
failure that would not show up for months. Replacing the branch each run instead means
the repository stores only the ~28 files currently live, permanently.

The trade-off is that the published site has no git history. That is the right trade:
every file on it is regenerable, and the manifests carry the provenance that matters.

Three consequences to respect:

- The `concurrency` group is mandatory. Two overlapping runs force-pushing this branch
  would lose one run's issue entirely.
- Never put anything on `gh-pages` by hand. It will be erased on the next run.
- `.nojekyll` must be recreated every run, which is why the publish step `touch`es it
  rather than relying on it surviving.

### 11.2 `ci.yml`

On `push` and `pull_request`: `uv sync --frozen`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv run pytest`. No network access, no publishing.

---

## 12. One-time setup

### 12.1 Repository settings, by a human, in this order

1. Push the code to a **public** repository. Private repos need a paid plan for Pages.
2. **Settings → Actions → General → Workflow permissions** → "Read and write
   permissions". Without this, the publish step gets a read-only token and fails.
3. Run the workflow once by hand: **Actions → Build issue → Run workflow**, leaving the
   slot input blank. This creates the `gh-pages` branch, which cannot be selected in
   settings until it exists.
4. **Settings → Pages → Source: Deploy from a branch → Branch: `gh-pages` / `(root)`**.
5. Wait for the `pages-build-deployment` run to go green, then open
   `https://OWNER.github.io/REPO/` and confirm the landing page lists an issue.

Note that scheduled workflows are disabled automatically in a repository with **60 days
of no activity**, and GitHub emails the owner before doing it. A fork that sits idle
stops building; a single commit re-enables it.

### 12.2 The device, once

On CrossPoint firmware: **Settings → System → OPDS Servers → Add Server**

- Server Name: `HN Daily`
- OPDS Server URL: `https://OWNER.github.io/REPO/catalog.xml`
- Username / Password: leave blank

Stock Xteink firmware exposes the same concept; consult its OPDS settings screen.
CrossPoint can also manage servers from a browser at `http://<device-ip>/settings` while
the device is in File Transfer mode, which is easier than typing a URL on the device.

**Two things to verify on the first real download, because both are assumptions:**

1. **HTTPS.** GitHub Pages is HTTPS-only and redirects plain HTTP, so the device's TLS
   stack has to work against it. The firmware does HTTPS elsewhere, so this is expected
   to be fine — but if the catalog fails to load, this is the first suspect, and the
   symptom is an immediate connection failure rather than an empty list.
2. **Root feed shape.** If the device rejects `catalog.xml`, re-enter the server URL as
   `https://OWNER.github.io/REPO/nav.xml` (section 10.3) and browse into "Recent issues".
   The symptom here is the opposite: the server is reachable but shows nothing.

Confirm both with a hand-built test EPUB before trusting the pipeline, and record the
outcome in the README.

---

## 13. Failure policy

The governing principle: **a partial issue always beats no issue.** At 03:00 nobody is
watching, and an issue with three link-only entries is still a good morning's reading.

| Situation | Behaviour | Exit |
|---|---|---|
| One article fails to fetch or extract | Link-only chapter, status recorded in manifest | 0 |
| Many articles fail | Same. Build proceeds | 0 |
| **Zero** stories usable (HN unreachable, feed empty) | Write no EPUB, no manifest; leave the existing site untouched; log loudly | 3 |
| `config.yaml` invalid | Fail before any network call | 2 |
| Previous manifest missing or corrupt | Warn; treat deduplication as a no-op for that manifest | 0 |
| Slot cannot be resolved from `--cron` | Fall back to nearest-slot, warn | 0 |
| An issue for this slot already exists | Overwrite EPUB, manifest, and catalog entry | 0 |
| Publish push rejected | Fail the job; the next run republishes the full site anyway | 1 |

On exit code 3 the workflow fails, and GitHub emails the repository owner about a failed
scheduled run — which is the intended and only alerting mechanism. Do not add
notification integrations.

The site is regenerated wholesale from the manifests on every run, so a single failed
run is self-healing: the next successful run rebuilds a correct catalog with no manual
intervention.

---

## 14. Testing and acceptance

### 14.1 Unit tests — no network

Every test runs offline against `tests/fixtures/`. Stub HTTP at the `httpx` client
boundary. A test suite that reaches the live web is a test suite that fails on a plane
and lies about why.

| File | Must cover |
|---|---|
| `test_config.py` | Each validation rule in 6.1 raises with the offending key named; `base_url` derivation from `GITHUB_REPOSITORY`, including the lowercased owner and the localhost fallback |
| `test_hn.py` | Deleted/dead/non-story items dropped; self-posts detected from a missing `url`; `min_score` filter; input ID order preserved through concurrent fetch |
| `test_extract.py` | `article_clean.html` extracts to `ok`; `article_messy.html` extracts body without nav or sidebar text; `article_paywall.html` yields `extraction_failed` via the 500-character floor; non-HTML content-type yields `non_html`; relative links absolutized; sanitizer strips `<script>`, `<style>`, `class`, and `onclick` |
| `test_epub.py` | Output opens with `ebooklib.epub.read_epub`; chapter count equals story count plus title page; metadata identifier/title/language correct; failed articles produce a notice chapter, never a missing one; **the zip's first entry is `mimetype`, stored uncompressed** — an EPUB that violates this opens on a laptop and fails on hardware |
| `test_catalog.py` | Feed parses; required elements from 10.2 present; entries newest-first; all hrefs absolute; a title containing `&` and `<` round-trips; a control character is stripped; summary truncated at 400 chars |
| `test_publish.py` | Slot resolution by `--slot`, by `--cron`, and by nearest-time; the day-boundary case where a 21:00 run happens at 00:40 the next day; deduplication excludes the previous issue but **not** the issue being rebuilt; backfill reaches `story_count`; pruning drops exactly the issues past `retention_days` and never touches `catalog.xml`, `nav.xml`, `index.html`, `latest.epub`, or `.nojekyll` |
| `test_schedule_sync.py` | Cron list in `build.yml` equals `schedule.slots[].cron` in `config.yaml` |

### 14.2 One live test, opt-in

A single test marked `@pytest.mark.live`, deselected by default via
`addopts = "-m 'not live'"` in `pyproject.toml`, that fetches the real HN top-stories
list and asserts it returns integers. Run it by hand when HN's API shape is in question.

### 14.3 Acceptance criteria — the definition of done

The build is complete when every one of these is true:

1. `uv sync --frozen && uv run pytest` passes from a clean checkout.
2. `uv run ruff check . && uv run ruff format --check .` is clean.
3. `uv run xtpages doctor` prints the resolved OPDS URL and reports the schedule in sync.
4. `uv run xtpages build --slot 0300 --public-dir ./public` against live HN produces:
   `public/issues/hn-<date>-0300.epub`, a matching `.json` manifest, `latest.epub`,
   `catalog.xml`, `nav.xml`, `index.html`, and `.nojekyll`.
5. That EPUB opens in a desktop reader with a working table of contents, 20 chapters
   plus a contents page, and readable body text on at least 15 of the 20.
6. Running the same command a second time overwrites cleanly and leaves the catalog with
   the same number of entries, not a duplicate.
7. Running `--slot 2100` immediately after `--slot 0300` produces an issue sharing **no**
   story IDs with the 03:00 issue, and still containing 20 stories.
8. A manually dispatched Actions run publishes a `gh-pages` branch with exactly one
   commit, and `https://OWNER.github.io/REPO/catalog.xml` returns the feed with
   `Content-Type: application/xml` or `text/xml`.
9. The catalog loads on the Xteink X4 and an issue downloads and opens. This is the only
   criterion that cannot be automated, and it is the only one that actually matters.

### 14.4 Manual verification script

Provide `scripts/serve.sh`: `python -m http.server 8000 --directory public`. With
`site.base_url` set to `http://localhost:8000/`, this lets the catalog be opened in a
desktop OPDS client, or by the device itself over the local network, before anything is
published.

---

## 15. Non-goals

Do not build these. Each was considered and deliberately excluded from v1.

- **Comments.** The `comments:` key stays commented out in `config.yaml`. No
  comment-fetching code, no `include_comments` plumbing. v2 will fetch trees from the
  Algolia endpoint (`https://hn.algolia.com/api/v1/items/<id>`), which returns a whole
  thread in one request rather than one call per comment.
- **Images.** The config flag exists and defaults off. Do not add image downloading,
  resizing, or greyscale conversion.
- **Formats other than EPUB.** No TXT, PDF, or MOBI output.
- **Device-side automation.** No auto-download, no push. The firmware cannot do it.
- **Reading-progress sync.** CrossPoint's KOReader sync is a device-side feature and has
  nothing to do with this repository.
- **A server, a database, or any hosted component.** Static files only.
- **Full-text search, tagging, or per-topic feeds.**
- **Retries across runs.** A story that failed extraction is not queued for a later
  attempt. It appears once, as a link, and the run ends.

---

## 16. Handoff summary

Build order that keeps you testable at each step:

1. `config.py` + `models.py` + `test_config.py` — nothing else works until config loads.
2. `hn.py` + fixtures + `test_hn.py` — you now have real story data to work with.
3. `extract.py` + `html.py` + `test_extract.py` — the hardest part, and the one that
   decides whether the output is worth reading.
4. `epub.py` + `test_epub.py` — verify on a desktop reader before going further.
5. `publish.py` + `test_publish.py` — slots, manifests, dedupe, pruning.
6. `catalog.py` + `test_catalog.py` — validate against a desktop OPDS client.
7. `cli.py` — wire it together; `doctor` first, it is the fastest feedback loop.
8. `build.yml` + `ci.yml` + `test_schedule_sync.py`.
9. Human setup from section 12, then the device test.

Assumptions carried by this document that a first run will confirm or refute:

- The device's TLS stack works against GitHub Pages (section 12.2).
- The device accepts an acquisition feed as the catalog root (section 10.3 is the hedge).
- `github.event.schedule` carries the triggering cron expression, which the nearest-slot
  fallback in section 7.1 makes non-fatal if it does not.
- `trafilatura.extract()` accepts the keyword arguments in section 8.2 at the pinned
  version. Verify before writing against them.
