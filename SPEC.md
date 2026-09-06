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
                 │       ├── prune       drop >14 days      │
                 │       └── catalog     regenerate XML     │
                 │  4. force-push ./public → gh-pages       │
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
│       └── ci.yml              # lint + tests on push/PR (section 11.2)
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
│   ├── fixtures/               # hand-written, not scraped: keep them small and
│   │   │                        # committed, and never fetch at test time
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
├── scripts/
│   └── serve.sh                # local static server for testing (section 14.4)
├── config.yaml                 # the forker's control panel (section 6)
├── pyproject.toml
├── uv.lock                     # committed
├── .gitignore
├── LICENSE                     # MIT, as the README declares
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

[tool.pytest.ini_options]
addopts = "-m 'not live'"
markers = ["live: hits the network; deselected by default (section 14.2)"]
```

Use `uv sync` to install and **commit `uv.lock`** — a scheduled job that silently picks
up a breaking library release at 03:00 is exactly the failure mode a lockfile prevents.

**Library APIs used here have been smoke-tested at the resolved versions** — trafilatura
2.2.0, EbookLib 0.20, nh3 0.3.7, httpx 0.28.1 — and every call in sections 8.2 and 8.3
was confirmed against them. Still re-check signatures if `uv` resolves something newer.
If any keyword argument named in section 8.2 is missing, **stop and record the deviation
in your summary** rather than guessing a replacement: extraction quality is the single
thing that decides whether an issue is worth reading.

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
  title: "Hacker News Daily"    # catalog + landing page name
  title_short: "HN Daily"       # leads each issue title, so it becomes part of the
                                # SD card filename: ASCII, no colon (section 10.2)
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
- `site.title_short` empty, longer than 40 characters, non-ASCII, or containing any of
  `/ \ : * ? " < > |` — it is composed into the entry title and therefore into the
  downloaded filename (sections 10.2 and 12.3), where those characters become `_`.
- `site.base_url` non-blank and not starting with `https://`, **except** that
  `http://localhost[:port]`, `http://127.0.0.1[:port]`, and `http://` on a private-LAN
  address (10/8, 172.16/12, 192.168/16) are all permitted. Local testing (section 14.4)
  cannot use HTTPS, and section 6.2's own no-`GITHUB_REPOSITORY` fallback is an
  `http://localhost` URL — without this exemption every local command would exit 2.
- `retention_days` x `len(schedule.slots)` + 1 > **62** — the device's OPDS parser stores
  at most 62 entries per feed and silently discards the rest (section 12.3). The `+ 1`
  covers the issue just built, which exists before pruning runs. At the shipped values
  this is 29. Fail with a message naming the computed entry count.

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
  **never more than one in-flight request per host** — with one exemption: the Hacker
  News API host (`hacker-news.firebaseio.com`). It is a public JSON API with no
  documented rate limit, it is the only way to read the feed, and one story detail per
  round trip would make the fetch stage needlessly slow. It is bounded by
  `max_concurrency` alone (section 8.1). The per-host rule exists to protect the article
  hosts, which did not ask for our traffic.
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

(A `schedule` entry also accepts an optional IANA `timezone:` key, so a forker who wants
07:00 local rather than 07:00 UTC can set one. It lives in the workflow file with the
cron, and changes nothing about the two-places problem below.)

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
    # │ cron defaults to UTC. An optional IANA `timezone:` key may be   │
    # │ set per entry (e.g. timezone: "America/New_York").              │
    # │ Scheduled runs are delayed under load, worst at the top of the  │
    # │ hour, and may be DROPPED entirely. The issue is always named    │
    # │ for its slot, never the actual run time; a dropped run is       │
    # │ recovered with a manual workflow_dispatch.                      │
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

0. **An empty or whitespace-only `--slot` value is treated exactly as if the flag were
   absent, and likewise for `--cron`.** This is not a corner case: the workflow passes
   `--slot` unconditionally, and on every scheduled run `github.event.inputs.slot` is the
   empty string, so this rule governs the most frequently executed path in the system —
   including the first-run setup in section 12.1.
1. An explicit non-empty `--slot LABEL` wins outright. Fail with exit code 2 if the label
   matches no configured slot; a typo must not silently fall through to a guess.
2. Otherwise, if a non-empty `--cron` matches a `schedule.slots[].cron`, use that slot's
   label. Match on the exact string after collapsing internal whitespace.
3. Otherwise (manual dispatch with no input, or a local run) pick the slot whose time is
   nearest to the current UTC time, and warn which one was chosen. On an exact tie,
   choose the **later** slot.

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
   connection errors, and 5xx responses other than `503`. Never retry any 4xx (`429`
   included) and never retry a `503` — both are the host asking you to stop.
6. **Rebuild `<pre>` newlines on the source HTML first** — `html.normalize_pre()`, see
   section 8.3.1 — then extract with trafilatura, requesting HTML output, comments off,
   tables on, images per config, and links preserved:

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
   **unwrap `<pre>` blocks (section 8.3.1)**, then sanitize (section 8.3), then truncate
   to `content.max_article_chars` at a tag boundary. That order matters: the unwrap needs
   the original `<pre>` element, which the sanitizer would otherwise have flattened.
   Passing `url=` in step 6 already absolutizes most links, so this step is a safety net
   for anything trafilatura left relative, not the primary mechanism.

Self-posts skip fetching but **not the rest of the pipeline**: `story.text` is HN-supplied
HTML, so run it through the same unwrap-then-sanitize sequence and set `self_post`. Ask HN
and Show HN posts routinely contain `<pre>` code blocks — precisely the case section 8.3.1
exists to rescue — so skipping the unwrap here would reintroduce the bug for the posts
most likely to hit it.

### 8.3 `epub.py` — EPUB generation

```python
def build_epub(cfg: Config, issue: Issue, articles: list[Article], out_path: Path) -> EpubResult: ...
```

Use `ebooklib`. Produce EPUB 3 and include an NCX table of contents for EPUB 2
compatibility. **`ebooklib` generates neither by default** — a book built without them
ships with no `nav.xhtml` and no `toc.ncx` at all. `epub.py` must explicitly
`book.add_item(epub.EpubNcx())` and `book.add_item(epub.EpubNav())`, set `book.toc` and
`book.spine` (with `"nav"` first in the spine), and only then does the writer emit
`EPUB/toc.ncx` and `EPUB/nav.xhtml`. Both were verified present at EbookLib 0.20 with
that setup. Shipping both is deliberate: the device prefers the EPUB 3 nav and falls back
to the NCX (section 12.3).

**Metadata**

| field | value |
|---|---|
| identifier | `urn:xtpages:issue:20260906-0300` |
| title | `{site.title_short} {date} {slot} UTC`, e.g. `HN Daily 2026-09-06 0300 UTC` — ASCII only, no colon; see section 10.2. Add `site.title_short` to `config.yaml`, defaulting to `HN Daily`, so a forker renaming the site renames the issues too |
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

When `content.include_hn_discussion_link` is `false`, the meta line drops the
` · <a href="{hn_url}">Discussion</a>` fragment and keeps the score and domain. That is
the setting's only effect anywhere in the build.

For any non-`ok`, non-`self_post` status, the body is exactly:

```html
<p class="notice">The full text could not be included ({status}).
Open the original: <a href="{url}">{url}</a></p>
```

Never omit a story because extraction failed. A 20-item issue always has 20 chapters;
the user decides whether a link is worth opening later.

**Sanitizing** — `html.py` exposes `sanitize(html: str) -> str` using `nh3`, allowing
only: `p h1 h2 h3 h4 h5 h6 ul ol li blockquote em strong b i u del s a br hr table tr th
td sub sup` plus `img` when `content.include_images` is true. Allowed attributes: `href`
on `a`, `src`/`alt` on `img`. Everything else — `script`, `style`, `iframe`, `form`,
`svg`, `video`, `audio`, inline event handlers, and all `class`/`id`/`style` attributes —
is stripped.

That list is not a guess at what a constrained renderer might tolerate. It is the set the
device actually recognizes, read from `ChapterHtmlSlimParser.cpp` and recorded in section
12.3. Tags outside it are not errors — the parser ignores the element and keeps its text
— so `code`, `small`, `figure`, `figcaption`, `thead`, and `tbody` are harmless but
accomplish nothing, which is why they are not on the list. `ul` and `ol` are kept even
though the device ignores the containers themselves, because `li` renders its own bullet.

**Two settings on `nh3.clean()` are not optional.**

`link_rel=None` — nh3's default injects `rel="noopener noreferrer"` into every `<a>`,
which is an attribute outside our allowlist. The device ignores unknown attributes so it
is harmless on hardware, but it contradicts this section and would fail a strict test.

`attributes={"a": {"href"}, "p": {"class"}}` — `class` must survive on `<p>`, because
section 8.3.1 emits `<p class="code">` *before* the sanitizer runs, and the stylesheet
and section 14.1 both depend on that class reaching the artifact. nh3 filters attribute
*names*, not values, so allowing `class` on `p` would also let a source article's own
`<p class="meta">` through — and that would silently inherit our stylesheet's italic
rule. **After sanitizing, drop every `class` attribute whose value is not exactly
`code`.** Values we assign ourselves (`meta`, `notice`) are added by the chapter template
afterwards and never come from a source page.

The tag allowlist is deliberately a *subset* of what the device recognizes (section
12.3): `div`, `span`, `ins`, `strike`, `ruby`, and `rt` are all supported by the renderer
but add nothing to an article digest, so they are stripped to keep the markup uniform.

**Stylesheet** — one small `style.css`, sizes in `em` only, never `px`, because the
device controls font size and a fixed pixel size fights it:

```css
body { margin: 0; padding: 0; }
h1 { margin: 0 0 0.3em; }
p { margin: 0 0 0.7em; text-indent: 0; }
p.meta { margin-bottom: 0.5em; font-style: italic; }
p.notice { font-style: italic; }
p.code { margin: 0; text-indent: 0; }
blockquote { margin: 0 0 0.7em 1em; }
```

Every declaration above is one the device's CSS parser implements. It supports exactly
`direction`, `display` (only `none` and `block`), `font-style`, `font-weight`, `height`,
`margin`/`margin-*`, `padding`/`padding-*`, `text-align`, `text-decoration-line`,
`text-indent`, `vertical-align`, and `width` — and among selectors, only element,
`.class`, `element.class`, and grouped forms. **`font-size`, `line-height`, `max-width`,
`color`, and `font-family` are not implemented and are silently ignored**, which is why
no rule here sets a size. Headings still look like headings: the renderer styles `h1`-`h6`
itself, without needing CSS.

Two rules follow from this. Do not write a stylesheet declaration the device drops on the
floor — it creates the illusion of control. And do not let CSS carry meaning, because
**honouring embedded stylesheets is a user-toggleable setting**: the EPUB must read
correctly with the stylesheet ignored entirely.

### 8.3.1 Unwrapping `<pre>` — required, not optional

The device has **no support for `<pre>` whatsoever.** The tag appears nowhere in its EPUB
library, it is absent from the parser's block-tag list, and there is no `white-space` CSS
property to fall back on. Text runs through `trimAndNormalize()`, which collapses every
run of space, tab, carriage return, and newline into a single space.

The consequence for a Hacker News reader specifically: a code block arrives as one
run-on paragraph with every line break and every level of indentation destroyed. HN links
to a great deal of code, so left alone this would quietly wreck a meaningful share of
every issue.

The rescue is **two stages, on opposite sides of the extractor**, and both are required.

**Stage one — `normalize_pre(html)`, on the raw page, before trafilatura.** Syntax
highlighters wrap every line of a code block in its own `<div>` (Prism emits
`<div class="token-line">`), with no newline characters anywhere. Readability extractors
flatten that markup and join the lines, so by the time the extracted HTML comes back the
line structure is already gone — no later pass can recover it. `normalize_pre` walks each
`<pre>` in the *source*, treating `br`, `div`, `p`, `li` and `tr` as line boundaries,
and replaces the block's children with plain text carrying real newlines. Verified
against a live Prism-highlighted article: without this the extractor returns
`const osc = ctx.createOscillator();osc.frequency.value = 440;` as one line.

**Stage two — `unwrap_pre(html)`, on the extracted HTML, before sanitizing.** For each
`<pre>` element:

1. Take its full text content, including any nested `<code>`.
2. Expand tabs to four spaces, then split on `\n`.
3. For each line, convert the **leading** run of spaces to U+00A0 NO-BREAK SPACE, one for
   one, leaving interior spaces alone.
4. Emit each line as `<p class="code">…</p>`, XML-escaped. Represent a blank line as a
   single U+00A0 so it survives as a blank line rather than collapsing away.
5. Replace the original `<pre>` with that run of paragraphs.

Both stages share the same line-boundary walk, so a `<pre>` that survives extraction
with its markup intact is handled identically either way.

The U+00A0 substitution is what makes indentation survive, and it works because the
firmware's whitespace test is a byte-level ASCII check — `' '`, `'\r'`, `'\n'`, `'\t'`
— while U+00A0 encodes as the two bytes `0xC2 0xA0`, neither of which matches. It is
therefore invisible to whitespace collapsing and reaches the page intact.

This does not give you a monospace font — the device chooses the face, and the user can
change it — so columns will not align. Line structure and indentation are preserved,
which is the difference between readable code and a wall of words.

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
inconsistently — refreshed after every build. It always mirrors the issue with the
**greatest slot instant among all surviving manifests**, which is not necessarily the
issue just built: a manual `--slot`/`--cron` run can rebuild an older slot, and that must
not demote the newest issue. Compute it after pruning, from the manifests on disk.

---

## 9. Command-line interface

```
xtpages build   [--cron EXPR] [--slot LABEL] [--public-dir DIR] [--config PATH] [--dry-run]
xtpages catalog [--public-dir DIR] [--config PATH]
xtpages prune   [--public-dir DIR] [--config PATH]
xtpages doctor  [--config PATH]
```

- `build` — the whole pipeline for one issue: select, fetch, extract, write EPUB, write
  manifest, refresh `latest.epub`, then prune, then regenerate catalog + nav + index +
  `.nojekyll`. **`build` owns `.nojekyll`**; the workflow's `touch` is redundant
  insurance, not the source of truth.
  One command does everything the workflow needs; `catalog` and `prune` exist separately
  for local repair.
- `--dry-run` — do everything except write files; print what would be written. Used to
  test extraction changes without touching the site. A missing `--public-dir` is treated
  as an empty site (no manifests, so no deduplication), and **a dry run never creates
  directories** — including the public directory itself.
- `doctor` — validate `config.yaml`, confirm cron/config schedule agreement, resolve
  `site.base_url`, and print the OPDS URL to enter on the device. No network calls. It
  reads the workflow at `.github/workflows/build.yml` relative to the repository root,
  located by walking up from `--config`; if the file is absent, report that as a warning
  rather than an error, so `doctor` still works outside a checkout.

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
  "counts": { "requested": 20, "returned": 20, "ok": 18, "self_post": 1,
              "extraction_failed": 1, "non_html": 0, "fetch_error": 0,
              "skipped_domain": 0 },
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
    <title>HN Daily 2026-09-06 0300 UTC</title>
    <updated>2026-09-06T03:07:41Z</updated>
    <dc:issued>2026-09-06T03:00:00Z</dc:issued>
    <dc:language>en</dc:language>
    <author><name>Hacker News</name></author>
    <summary type="text">20 stories · A thing someone built · Something behind a paywall · …</summary>
    <!-- summary is ignored by the Xteink; it is here for desktop OPDS clients -->
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

**The entry title and author are not just labels — they become the filename on the SD
card.** CrossPoint composes the downloaded file's name from the OPDS entry's `author` and
`title`, never from the URL, defaulting to `"{author} - {title}.epub"`
(`src/util/OpdsFilename.cpp`). The name is then sanitized: `/ \ : * ? " < > |` each
become `_`, leading and trailing spaces and dots are trimmed, and the result is capped at
100 bytes (`src/util/StringUtils.cpp`).

Three rules follow, and they are why the title above looks the way it does:

- **No colons.** `03:00` would land on the SD card as `03_00`.
- **ASCII only.** Non-ASCII survives sanitizing, but an em dash in a filename is a
  liability in the device's file browser and over USB. Do not use one here, even though
  the EPUB's own text may contain any Unicode.
- **Sort order is filename order.** Because every entry shares the author prefix, a
  `YYYY-MM-DD HHMM` title makes the SD card sort chronologically for free.

The device shows the entry's **title and author, and nothing else** — `summary` is parsed
by desktop clients but never read by CrossPoint's parser. Keep the summary for Calibre and
KOReader, but do not put anything in it the reader needs to see.

Field limits enforced by the device's parser: title 160 bytes, author 120, id 128, href
768. An entry with an empty title or no usable link is dropped silently.

Generation details:

- Build the XML with `lxml.etree`, never string concatenation. Titles come from the open
  web and will eventually contain `&`, `<`, and stray control characters.
- All timestamps are ISO 8601 UTC with a literal `Z`, seconds precision, no microseconds.
- Which timestamp goes where: an entry's `<updated>` is that issue's `built_at`, its
  `<dc:issued>` is its `slot_at`, and both `catalog.xml`'s and `nav.xml`'s `feed/updated`
  are the greatest `built_at` across all retained issues.
- The `summary` lists the story titles joined by ` · `, truncated to **400 characters**
  with a trailing `…`. The Xteink never displays it (section 12.3); it is there so
  desktop OPDS clients like Calibre and Thorium show something useful.
- Strip characters illegal in XML 1.0 (most C0 controls) from every text node.

The `start` link points at this same acquisition feed. The specification associates
`start` with a navigation feed, but this catalog's root *is* the acquisition feed, and
pointing `start` anywhere else would send a client that follows it into a second
document for no benefit.

### 10.3 `public/nav.xml` — navigation feed, kept as a fallback

**CrossPoint does not need this** — its parser never inspects the feed's `kind=` profile
and happily takes an acquisition feed as the root (section 12.3). Publish it anyway: it
costs about a kilobyte and one function, and the stock Xteink firmware's OPDS client has
not been inspected. If a device shows an empty catalog, this is the URL to try instead.

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
    # cron defaults to UTC; an optional IANA `timezone:` key may be set per entry.
    # Scheduled runs are delayed under load and may be dropped entirely. The issue
    # is named for its slot, never the run time. Recover a dropped run with a
    # manual workflow_dispatch for that slot.
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
      - uses: actions/checkout@v7

      - uses: astral-sh/setup-uv@v10.0.1
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
        env:
          # Never interpolate ${{ }} directly into a run: script — that is GitHub's
          # documented script-injection hazard. Bind to env and quote instead.
          XT_CRON: ${{ github.event.schedule }}
          XT_SLOT: ${{ github.event.inputs.slot }}
        run: |
          uv run xtpages build \
            --cron "$XT_CRON" \
            --slot "$XT_SLOT" \
            --public-dir public

      - name: Publish to gh-pages
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          cd public
          touch .nojekyll   # belt-and-braces; `xtpages build` already wrote it
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
   permissions". The workflow's own `permissions: contents: write` block is what
   actually grants the push, so this is belt-and-braces — but it keeps the repository
   working if that block is ever removed, and costs nothing.
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

Both of the questions this design originally hung on have been **confirmed against the
CrossPoint firmware source** (section 12.3): HTTPS against GitHub Pages works, and a flat
acquisition feed is accepted as the catalog root. Still do one hand-built test EPUB
end-to-end before trusting the pipeline — confirming source-reading against real hardware
is cheap and the whole design rests on it.

### 12.3 Device constraints, confirmed from firmware source

Read from `crosspoint-reader` at the versions cited. Re-verify if the firmware moves.

| Constraint | Finding | Source |
|---|---|---|
| **HTTPS** | Works and is *required* for public servers. The HTTP client sets `config.crt_bundle_attach = esp_crt_bundle_attach`, verifying against the bundled Mozilla CA roots — which GitHub Pages' certificate chains to. `CONFIG_ESP_TLS_INSECURE` is off, so there is no unverified fallback | `src/network/HttpDownloader.cpp` |
| **Root feed shape** | The parser never looks at the feed's `kind=acquisition` / `kind=navigation` profile. It walks `<entry>` elements and classifies each one. A flat acquisition feed at the root is fine | `lib/OpdsParser/OpdsParser.cpp` |
| **What makes an entry a book** | A link whose `rel` *contains* `opds-spec.org/acquisition` **and** whose `type` is **exactly** `application/epub+zip` (`strcmp`, so no parameters, no charset, no whitespace) | `OpdsParser.cpp` `startElement` |
| **Entry cap** | **62 entries per feed** (`ENTRY_STORAGE_CAPACITY 64` minus 2). Extra entries are dropped and a `truncated` flag is set. Because we emit newest-first, truncation drops the *oldest* — the safe direction, but it is why section 6.1 validates the count | `OpdsParser.cpp` |
| **Field limits** | title 160 bytes, author 120, id 128, href 768, all truncated on a UTF-8 codepoint boundary | `OpdsParser.cpp` |
| **Entries silently dropped** | Any entry with an empty title or no usable link | `OpdsParser.cpp` `endElement` |
| **Filename on the SD card** | Composed from the entry's `author` and `title`, default `"{author} - {title}.epub"`, never from the URL. Sanitized: `/ \ : * ? " < > \|` become `_`, leading/trailing spaces and dots trimmed, capped at 100 bytes | `src/util/OpdsFilename.cpp`, `src/util/StringUtils.cpp` |
| **`summary` is ignored** | Not parsed at all. The device displays title and author only | `OpdsParser.cpp` |
| **Absolute hrefs** | Passed through untouched; relative ones are resolved against the feed URL. Our absolute-URL choice is the safe one either way | `src/util/UrlUtils.cpp` `buildUrl` |
| **Redirects** | Followed manually, **max 5 hops**, matching the limit in section 6.4. The OPDS path does *not* use the `downgradeRedirectsToHttp` shortcut — that is the OTA updater's trick — so GitHub Pages' HTTP→HTTPS redirect is never an issue | `HttpDownloader.cpp`, `OpdsBookBrowserActivity.cpp` |
| **HTTP timeout** | 60 s per request | `HttpDownloader.cpp` |
| **Pagination** | A feed-level `rel="next"` link is honoured, if a fork ever exceeds 62 entries | `OpdsParser.cpp` |
| **Basic auth** | Sent preemptively when both username and password are set. We use neither | `HttpDownloader.cpp` |
| **OPDS server URL length** | A `std::string`, no fixed cap. Max 8 saved servers | `src/OpdsServerStore.h` |

Constraints on the EPUB itself, which decide what the chapters may contain:

| Constraint | Finding | Source |
|---|---|---|
| **Recognized tags** | Blocks `p li div br blockquote`; headings `h1`-`h6`; bold `b strong`; italic `i em`; underline `u ins`; strikethrough `del s strike`; also `a span sub sup ruby rt table tr th td img hr`. Unrecognized tags are ignored but their text is kept | `lib/Epub/Epub/parsers/ChapterHtmlSlimParser.cpp` |
| **`<pre>` — unsupported** | Absent from the entire EPUB library. Whitespace is collapsed by `trimAndNormalize()` (space, `\t`, `\r`, `\n` → one space), so a code block becomes one run-on paragraph. Section 8.3.1 is the mandatory workaround | `ChapterHtmlSlimParser.cpp` |
| **CSS properties** | Only `direction`, `display` (`none`/`block`), `font-style`, `font-weight`, `height`, `margin*`, `padding*`, `text-align`, `text-decoration-line`, `text-indent`, `vertical-align`, `width`. **No `font-size`, `line-height`, `max-width`, `color`, or `font-family`** | `lib/Epub/Epub/css/CssParser.cpp` |
| **CSS selectors** | Element, `.class`, `element.class`, and grouped. **No descendant, child, or pseudo-selectors** | `lib/Epub/Epub/css/CssParser.h` |
| **CSS is optional** | Honouring embedded stylesheets is a user setting (`embeddedStyle` cache key). The book must read correctly with it off | `docs/file-formats.md` |
| **Lists** | `<li>` emits its own bullet and handles nesting; `<ul>`/`<ol>` containers are ignored | `ChapterHtmlSlimParser.cpp` |
| **Tables** | Real support — simple rows laid out as positioned columns, with a minimum cell width of 3 line-heights. Wide tables will still be cramped on a 4-inch screen | `ChapterHtmlSlimParser.cpp` |
| **Table of contents** | EPUB 3 `nav.xhtml` is preferred, `toc.ncx` is the fallback, and a book with neither still opens. Shipping both, as `ebooklib` does, is correct | `lib/Epub/Epub.cpp` |
| **Anchor cap** | 1024 IDs per chapter, beyond which anchors are dropped. We generate no IDs; do not start | `ChapterHtmlSlimParser.cpp` |

**One real failure mode this surfaced.** Starting a download requires **40 KB free heap
and a 20 KB largest-free-block** (`MIN_TLS_FREE_HEAP`, `MIN_TLS_MAX_ALLOC`). Below that
the firmware refuses the transfer outright, because a TLS session and its ~17 KB record
buffer would otherwise die mid-stream or abort the device. It drops SD font caches first
to try to get under the bar. The user-visible symptom is a generic "Download failed" with
nothing about memory in it.

This is not proportional to our file size — the check is pre-flight — but it is one more
reason to keep issues lean: images off, `max_article_chars` at its default, and 20
stories rather than 50. If downloads fail on a device that has been reading for a while,
rebooting it before downloading is the workaround, not a change to this repository.

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
| `--slot` names a label not in config | Fail immediately; a typo must not become a guess | 2 |
| An issue for this slot already exists | Overwrite EPUB, manifest, and catalog entry | 0 |
| EPUB, manifest, or catalog write fails | Fail after selection; see the atomicity rule below | 1 |
| A scheduled run is delayed or dropped by GitHub | Nothing to do. The next run dedupes against whatever manifest is newest, so a gap self-corrects. Recover a specific slot with a manual `workflow_dispatch` | — |

The zero-stories check short-circuits **after story selection and before any article
fetch** — there is no point downloading twenty articles to discover the feed was empty.

**Writing is atomic.** Write the EPUB, each manifest, and each catalog file to a
temporary file in the destination directory and `os.replace()` it into place. A crash or
a full disk then leaves the previous good file, never a truncated one that the next run
would read back as a corrupt manifest.

Publishing is the workflow's job, not the CLI's — `xtpages` never pushes. A rejected
push fails the *job* while leaving the site as it was; because every run regenerates the
whole site from the manifests, the next successful run repairs it with no intervention.

On exit codes 1, 2, and 3 the workflow fails, and GitHub emails the repository owner
about a failed scheduled run — which is the intended and only alerting mechanism. Do not
add notification integrations.

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
| `test_config.py` | Each validation rule in 6.1 raises with the offending key named, including the 62-entry catalog cap; `base_url` derivation from `GITHUB_REPOSITORY`, including the lowercased owner and the localhost fallback |
| `test_hn.py` | Deleted/dead/non-story items dropped; self-posts detected from a missing `url`; `min_score` filter; input ID order preserved through concurrent fetch |
| `test_extract.py` | `article_clean.html` extracts to `ok`; `article_messy.html` extracts body without nav or sidebar text; `article_paywall.html` yields `extraction_failed` via the 500-character floor; non-HTML content-type yields `non_html`; relative links absolutized; sanitizer strips `<script>`, `<style>`, `class`, and `onclick`; **`unwrap_pre` turns a multi-line indented `<pre>` into one `<p class="code">` per line, converts leading spaces to U+00A0 while leaving interior spaces as ASCII, preserves blank lines, expands tabs to four spaces, and leaves a document with no `<pre>` unchanged**; and no `<pre>` survives sanitizing |
| `test_epub.py` | Output opens with `ebooklib.epub.read_epub`; the spine holds exactly `story_count` chapters plus the title page (`nav.xhtml` is a manifest item, not a spine entry, and is excluded from that count); metadata identifier/title/language correct; failed articles produce a notice chapter, never a missing one; **the zip's first entry is `mimetype`, stored uncompressed** — an EPUB that violates this opens on a laptop and fails on hardware; both `toc.ncx` and `nav.xhtml` are present; and the stylesheet declares no property outside the supported set in 12.3 |
| `test_catalog.py` | Feed parses; required elements from 10.2 present; entries newest-first; all hrefs absolute; a title containing `&` and `<` round-trips; a control character is stripped; summary truncated at 400 chars; **entry titles are pure ASCII and contain no colon**, and every field is inside the device limits in 12.3 (title 160 bytes, author 120, id 128, href 768) |
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

Provide `scripts/serve.sh`: `python -m http.server 8000 --directory public`. Section
6.1 exempts local addresses from the HTTPS rule precisely so this works.

For a **desktop** OPDS client, set `site.base_url` to `http://localhost:8000/`. For the
**device**, `localhost` is the device itself and will fail — use the serving machine's
LAN address, `http://192.168.x.x:8000/`, and set `base_url` to match, because the
catalog's acquisition hrefs are absolute and must resolve from the reader's side of the
network. This is the cheapest way to test a real download without publishing anything.

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

Assumptions still carried by this document:

- `github.event.schedule` carries the triggering cron expression. The nearest-slot
  fallback in section 7.1 makes this non-fatal if it does not.

Everything else has been checked. Confirmed from the CrossPoint firmware source and
recorded in section 12.3: HTTPS against GitHub Pages, and an acquisition feed as the
catalog root — plus two corrections, that the SD card filename comes from the entry's
author and title rather than the URL, and that a feed cannot exceed 62 entries.
Confirmed by smoke test at the resolved versions: trafilatura 2.2.0's seven keyword
arguments, nh3 0.3.7's `clean()` signature and its `rel` injection, EbookLib 0.20's
`mimetype`-first-and-stored zip layout, and that EbookLib emits `nav.xhtml` and
`toc.ncx` only when explicitly asked.

What remains genuinely unknown is the hardware itself: whether a real X4 renders these
EPUBs well, and how the *stock* firmware's OPDS client behaves. Settle both the first
time you sideload an issue, before trusting the pipeline.
