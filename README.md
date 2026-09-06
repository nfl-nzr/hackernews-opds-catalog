# xtpages

A daily Hacker News reading digest, delivered to an e-ink reader over WiFi.

Twice a day a GitHub Action reads Hacker News' top stories — twenty by default, and
configurable — downloads each linked article, strips it down to readable text, and packs the lot into a single EPUB. The file
is published to a free GitHub Pages site along with an **OPDS catalog** — a standard
Atom XML file listing publications and where to download them, which e-reader firmware
knows how to browse. Point the reader at the catalog URL once; after that, each new
issue is waiting at the top of the list.

Built for the [Xteink X4](https://www.xteink.com/products/xteink-x4) on
[CrossPoint firmware](https://github.com/crosspoint-reader/crosspoint-reader), but the
output is a plain OPDS catalog of plain EPUBs, so it works with any reader or app that
speaks OPDS — KOReader, Calibre, Thorium, Foliate, and others.

No server, no database, no API keys, no cost.

> **Status: specified, not yet built.** [`SPEC.md`](SPEC.md) is the complete build
> contract. If you are implementing this, start there and read this file only for the
> setup steps.

---

## How it works

```
cron 03:00 UTC ─┐
                ├─→ GitHub Actions ─→ fetch HN top stories
cron 21:00 UTC ─┘                     download + extract each article
                                      build one EPUB
                                      publish to gh-pages, prune past 14 days
                                                │
                          https://YOU.github.io/xtpages/catalog.xml
                                                │
                                       Xteink X4, over WiFi
```

The 21:00 issue skips anything that was already in the 03:00 issue and backfills further
down the front page, so you never get the same article twice in a day.

**One thing to be clear about:** the reader *pulls*, it does not subscribe. No firmware
feature downloads on a schedule. "Daily delivery" means the file is reliably waiting for
you — collecting it is one tap in the OPDS browser.

---

## Setup

### 1. The repository

Fork or clone this repo, and make sure it is **public** — GitHub Pages on a free account
requires it.

Then, in your fork:

1. **Settings → Actions → General → Workflow permissions** → select
   **Read and write permissions**. The build cannot publish without this.
2. **Actions → Build issue → Run workflow**, with the slot input left blank. This first
   run creates the `gh-pages` branch, which you cannot select in settings until it
   exists.
3. **Settings → Pages → Source: Deploy from a branch → Branch: `gh-pages` / `(root)`**.
4. Wait for the `pages-build-deployment` job to finish, then open
   `https://YOUR-USERNAME.github.io/xtpages/` and check that an issue is listed.

Your catalog URL is:

```
https://YOUR-USERNAME.github.io/xtpages/catalog.xml
```

### 2. The device

On CrossPoint firmware: **Settings → System → OPDS Servers → Add Server**

| Field | Value |
|---|---|
| Server Name | `HN Daily` |
| OPDS Server URL | `https://YOUR-USERNAME.github.io/xtpages/catalog.xml` |
| Username / Password | leave blank |

Typing a URL on a 4-inch screen is unpleasant. CrossPoint can also manage servers from a
browser: put the device in **File Transfer** mode and visit `http://<device-ip>/settings`
from a computer on the same network.

Stock Xteink firmware has the same feature in its own OPDS settings screen.

CrossPoint's OPDS client has been read directly to confirm this works: it verifies HTTPS
against bundled CA roots, which GitHub Pages' certificate chains to, and it accepts our
catalog's feed shape. A second feed, `nav.xml`, is published on every build as insurance
for the stock firmware, which has not been inspected — if a device shows an empty
catalog, enter that URL instead.

---

## Configuring it

Everything except the schedule lives in [`config.yaml`](config.yaml): which HN feed to
read, how many stories, minimum score, domains to never fetch, how many days to keep,
timeouts and concurrency, and the site's title and language.

### Changing the schedule

The schedule lives in **two** places and they must agree:

1. the `cron:` lines in `.github/workflows/build.yml` — the actual trigger
2. `schedule.slots` in `config.yaml` — the cron-to-label mapping used to name each issue

GitHub parses the workflow file itself to decide when to run, before any of this
project's code executes, so a cron expression genuinely cannot be read from
`config.yaml`. Edit both. `tests/test_schedule_sync.py` fails if you edit only one.

Times default to **UTC**; a `timezone:` key can be set per schedule entry if you would
rather write local times. Scheduled runs are delayed when GitHub is busy — worst at the
top of the hour — and under heavy load can be **dropped entirely**. Each issue is named
for its scheduled slot rather than the time the job actually started, so a late run still
produces a correctly named file, and a dropped one is recovered by running the workflow
manually for that slot.

---

## Running it locally

```bash
uv sync
uv run xtpages doctor                              # validate config, print your OPDS URL
uv run xtpages build --slot 0300 --public-dir ./public
./scripts/serve.sh                                 # http://localhost:8000
```

With `site.base_url` set to `http://localhost:8000/` in `config.yaml`, you can point a
desktop OPDS client — or the reader itself, over your local network — at
`http://localhost:8000/catalog.xml` and test the whole loop before publishing anything.

`--dry-run` runs the full pipeline without writing files, which is the fast way to check
whether an extraction change improved things.

---

## Things worth knowing

**Code blocks are rebuilt, not passed through.** The reader has no support for `<pre>`
and collapses all whitespace, which would turn every code sample on Hacker News into one
run-on paragraph. The build detects those blocks and re-emits them line by line, using
non-breaking spaces to hold the indentation. You get line structure and indentation, but
not a monospace font — the device picks the typeface.

**Some articles will not extract.** Paywalls, JavaScript-only sites, and Cloudflare
challenges all defeat text extraction, and GitHub Actions' IP ranges are blocked by more
sites than a home connection is. Those stories still appear in the issue as a titled
chapter with a link, never silently dropped — expect a handful per issue.

**This fetches other people's pages on a schedule.** The build sends a User-Agent that
identifies the project and links back to the repository, holds itself to five concurrent
requests overall and one per article host, and stops on `429`/`503` rather than retrying
through it. (Hacker News' own JSON API is exempt from the per-host limit — it is a public
API with no published rate limit, and it is the only way to read the feed.) If you fork
this, leave those limits alone.

**A download that fails may be a memory problem, not a network one.** The reader needs
40 KB of free heap to open a TLS connection, and refuses the transfer below that with a
generic "Download failed". A device that has been reading for a while can drift under the
bar. Reboot it and try again — nothing in this repository can affect it.

**Idle forks stop building.** GitHub disables scheduled workflows in a repository with 60
days of no activity. It emails you first; any commit re-enables them.

**The `gh-pages` branch is rewritten on every run.** It carries exactly one commit, by
design — appending would grow the repository by roughly 350 MB a year with no way to
reclaim it, since deleting old files does not remove them from git history. Anything you
put on that branch by hand will be erased on the next build.

---

## Not included

No comments, no images, no formats other than EPUB, no reading-progress sync, and
nothing that runs on the device. See [`SPEC.md` section 15](SPEC.md#15-non-goals) for the
reasoning and what v2 would add.

---

## License

MIT. Article text belongs to its publishers; this tool reformats publicly available pages
for personal reading and redistributes nothing beyond your own GitHub Pages site.
