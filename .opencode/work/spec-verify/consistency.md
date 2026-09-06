# S4 — Internal-consistency review: SPEC.md cross-referenced against README.md

**Scope:** SPEC.md (all 1,228 lines read) vs README.md (182 lines), per brief items 1–14 plus
own findings. S1–S3 artifacts existed at review time and are cited only where relevant
(non-blocking). All line refs are `SPEC.md:<line>` unless prefixed `README.md:`.

**Verdict: CHANGES REQUESTED.** The spec is unusually self-aware and mostly coherent, but the
header claim — "Every decision below is settled" (SPEC.md:7-10) — does not hold. Three
internal contradictions force an implementer to deviate from "settled" decisions on
documented paths, and a set of behaviors the spec's own workflows exercise are simply
undefined.

**Tally:** 3 blockers · 16 should-fix · 12 cosmetic · 4 items clean ("no issue found").

---

## Finding index

| ID | Brief item | Severity | One-line summary |
|---|---|---|---|
| F1 | 1 | cosmetic | "Every decision is settled" is overstated; §16 discloses two assumptions |
| F2 | 1 | should-fix | The trafilatura assumption has no defined fallback if verification fails |
| F3 | 2 | should-fix | §3 diagram shows three workflow commands; §9/§11 have `build` do everything |
| F4 | 2 | should-fix | `latest.epub` "newest issue" undefined when the just-built issue isn't newest |
| F5 | 3 | cosmetic | Exit-3 short-circuit point in the §9 pipeline not explicit (intent recoverable) |
| F6 | 5 | cosmetic | Validation formula undercounts by one (future-dated slot transient: 29, not 28) |
| F7 | 6 | should-fix | `--dry-run` / first run with no `./public`: prune+catalog behavior undefined |
| F8 | 7 | **blocker** | `--slot ""` is always passed by the workflow; §7.1 precedence never defines it |
| F9 | 8 | **blocker** | Pipeline order (unwrap → sanitize) strips `class="code"`; stylesheet/tests expect it |
| F10 | 8 | should-fix | Self-post path never runs `unwrap_pre`; HN self-post HTML can contain `<pre>` |
| F11 | 9 | cosmetic | "Chapter count" in test_epub ambiguous (does `nav.xhtml` count?) |
| F12 | 11 | should-fix | "Publish push rejected → 1" conflates CLI exit codes with job outcomes |
| F13 | 11 | should-fix | Infra failures (EPUB write, prune, catalog) untabulated; partial-file state undefined |
| F14 | 12 | cosmetic | README hardcodes "top 20" vs configurable feed/story_count |
| F15 | 12 | **blocker** | §6.1 forbids non-https `base_url`; §14.4/README instruct `http://localhost:8000/` |
| F16 | 12/13 | should-fix | README declares MIT; §4's "create exactly this structure" has no LICENSE |
| F17 | 13 | should-fix | `scripts/serve.sh` required by §14.4, referenced by README, absent from §4 tree |
| F18 | 13 | should-fix | §4 annotates `ci.yml` with "(section 14.4)"; ci.yml is specified in §11.2 |
| F19 | 14 | should-fix | §6.4 one-request-per-host vs §8.1's 5-concurrent HN detail fetches — contradiction |
| F20 | 14 | should-fix | §10.2 says the device shows the summary; 40 lines earlier it says the device ignores it |
| F21 | 14 | should-fix | (merged into F10) |
| F22 | 14 | should-fix | `.nojekyll` creator ambiguous: §14.3.4 says build produces it; §9/§11 say otherwise |
| F23 | 14 | should-fix | `include_hn_discussion_link` config key has no consumer in any module spec |
| F24 | 14 | should-fix | §14.2 requires pytest `addopts` in pyproject; §5's template omits the section |
| F25 | 14 | should-fix | `${{ github.event.inputs.slot }}` interpolated into `run:` shell — injection anti-pattern |
| F26 | 14 | cosmetic | Allowlist called "the set the device actually recognizes"; §12.3 lists 6 more tags |
| F27 | 14 | cosmetic | Nearest-slot tie at exactly 12:00:00 / 00:00:00 UTC undefined |
| F28 | 14 | cosmetic | Manifest `counts` keys vs possible statuses; `requested` semantics undefined |
| F29 | 14 | cosmetic | Catalog `<updated>`/`<dc:issued>` and nav.xml `<updated>` sources only inferable |
| F30 | 14 | cosmetic | "HN Daily" title prefix hardcoded while `site.title` is configurable |
| F31 | 14 | cosmetic | `doctor`'s build.yml discovery path unspecified |
| F32 | 14 | cosmetic | Retry rule "5xx" + "never 503" requires reading two clauses together |
| F33 | 12 | cosmetic | (merged into F14) |

---

## Item 1 — §2 "settled" vs self-declared unverified assumptions

**F1 (cosmetic).** The claim at SPEC.md:7-10 ("Every decision below is settled — where you
see a value, use that value") is a framing statement about *decisions*, and §16:1216-1222
does disclose the residual *factual* assumptions. Enumerated, the spec carries exactly:

1. **`github.event.schedule` carries the triggering cron expression** — stated as fact at
   §7.1:383-385, disclosed as an assumption at §16:1218-1219. Mitigated: the nearest-slot
   fallback (§7.1:395-396) makes it non-fatal. S1 (research-Q1.md) live-confirmed the
   payload field exists, so this assumption is now empirically supported.
2. **`trafilatura.extract()` accepts the §8.2 kwargs at the pinned version** — hedged at
   §5:222-224 ("Verify library signatures against the installed version before writing
   against them") and §16:1220-1222. S2 (research-Q2.md item a) could not verify locally
   ("NOT FOUND (locally), likely CONFIRMED") — still empirically open.

Two further unknowns are disclosed without the word "assumption": the stock Xteink OPDS
client is uninspected (§10.3:862-864, mitigated by publishing `nav.xml`), and a hand-built
EPUB must still be tested on hardware (§12.2:1044-1048). No issue with the disclosure
mechanism itself; the wording "every decision is settled" is defensible. Cosmetic.

**F2 (should-fix).** The trafilatura assumption — self-declared the most dangerous — has a
verification instruction but **no Plan B**. §5:222-224 and §16:1220-1222 say "confirm the
kwargs exist"; neither says what to do if they don't (pin an older trafilatura? shim the
call? change the extraction approach?). An implementer who hits the failure at 03:00 has no
settled decision to fall back on, which is exactly what §2 promises.
**Fix:** add one sentence to §5: "If any §8.2 kwarg is absent from the resolved version,
stop and record the deviation in the final summary before writing extract.py" — or name the
acceptable fallback (e.g., drop `favor_precision` and accept noisier output).

---

## Item 2 — `xtpages build` ordering: §9 vs §3, and §8.4/§8.5 requirements

**F3 (should-fix).** §3's architecture diagram (SPEC.md:96-104) shows the workflow running
**three separate commands**: step 3 `xtpages build`, step 4 `xtpages prune`, step 5
`xtpages catalog`. But §9:686-688 says `build` is "the whole pipeline … write EPUB, write
manifest, refresh `latest.epub`, then prune, then regenerate catalog + nav + index. One
command does everything the workflow needs", and §11's workflow (SPEC.md:960-965) invokes
only `uv run xtpages build`. Read literally, §3 describes a workflow that does not exist.
**Fix:** relabel §3's steps 4–5 as sub-steps of step 3 (e.g., "3. xtpages build — …
├── prune >14 days └── regenerate catalog.xml/nav.xml/index.html"), or note that steps 4–5
run *inside* the build command.

**F4 (should-fix).** `latest.epub` is defined as "a byte copy … of the newest issue's EPUB,
refreshed after every build" (§8.5:671-673), and §9:686-688 orders the refresh immediately
after the manifest write, *before* prune and catalog. The spec never says **which issue is
copied when the issue just built is not the newest**. This is reachable: a manual run with
`--cron "0 3 * * *"` at 01:00 UTC builds a future-dated `hn-<today>-0300`; a second manual
run at 01:30 with `--cron "0 21 * * *"` resolves to *yesterday's* 2100 slot (§7.1:398-401
nearest-instant rule) and builds an issue older than the existing one. A natural
implementation ("copy the EPUB I just wrote") then leaves `latest.epub` pointing at the
older issue, violating §8.5's definition; a scan-based implementation must be told to scan.
**Fix:** one sentence in §8.5: "After writing the issue, `latest.epub` is refreshed by
copying the EPUB with the greatest slot instant among all manifests in `public/issues/` —
which may not be the issue just built."

**Clean sub-checks (no issue found):**
- Prune → catalog order is correct and required: §8.4:630-632 regenerates the catalog by
  scanning `public/issues/*.json`, so prune must run first or expired entries would linger.
- `latest.epub`-before-prune is safe: prune never deletes `latest.epub` (§8.5:668-670) and
  can never delete the just-built issue (its slot is within 6 hours of now by §7.1's
  nearest-instant rule, so it is never "older than retention_days").
- `latest.epub` vs catalog ordering has no dependency (catalog does not read `latest.epub`).

---

## Item 3 — `latest.epub` refresh on the zero-story exit-3 path

**F5 (cosmetic).** §13:1108 says the zero-story path writes "no EPUB, no manifest; leave the
existing site untouched", which implies `latest.epub` is not refreshed and prune/catalog do
not run. But §9's pipeline list (686-688) never states where the exit-3 short-circuit
happens, so a literal implementer could wonder whether prune still runs (it must not —
pruning modifies the site). The intent is recoverable from "leave the existing site
untouched"; cosmetic.
**Fix:** append to §13's zero-story row: "the run stops immediately after selection; no
prune, no catalog regeneration, no `latest.epub` refresh."

---

## Item 4 — First run with no previous manifest: dedupe no-op

**No issue found.** Covered three times: §13:1110 ("Previous manifest missing or corrupt |
Warn; treat deduplication as a no-op for that manifest | 0"); §11:952-958 (workflow creates
an empty `./public` when `gh-pages` doesn't exist); §8.5:654-657 (exclusion set built from
manifests that exist, excluding the current slug). A first run therefore dedupes against an
empty set and builds normally.

---

## Item 5 — §6.1's 62-entry validation vs retention 14 × 2 = 28

**Core check: consistent.** One issue per slot per day means steady-state catalog entries =
retention_days × slots/day = 14 × 2 = 28 (§6.1:298-300, §4.1:185 "28 pairs at steady
state"), comfortably under the device's 62-entry cap (§12.3:1059, CONFIRMED by S3's
explore.md — no refuted claims there). The validation is **not redundant** despite the
confirmed cap: it is the config-time guard that stops a forker from raising retention to a
value the device would silently truncate; the device-side behavior (drop oldest, set a
truncated flag) is merely the graceful degradation behind it.

**F6 (cosmetic).** The formula slightly undercounts. A build that runs *before* its slot
time (allowed by §7.1:398-401 — e.g., a run at 00:40 builds the 0300 slot, which is 2h20m in
the future) leaves a future-dated issue that prune never deletes (it is not "older than
retention_days before now", §8.5:668-669). The catalog then transiently holds
retention_days × slots **+ 1** = 29 entries. Harmless at shipped values, but a forker at
exactly 31 days × 2 slots = 62 passes §6.1's `> 62` check and transiently emits 63 entries,
which the device truncates by one.
**Fix:** validate `retention_days × len(schedule.slots) + 1 > 62`, or document the +1 slack.

---

## Item 6 — `--dry-run` on a first run with no `./public`

**F7 (should-fix).** §9:690-691 defines dry-run only as "do everything except write files;
print what would be written." Undefined for a fresh clone (no `./public` — the normal state
after §14.3.1's "clean checkout", and README:133-134 explicitly recommends dry-run as the
first way to check extraction changes):
- `read_manifests` on a nonexistent directory — empty list or crash? (§13:1110 covers a
  *missing manifest*, arguably not a missing directory).
- `prune` on a nonexistent directory — no-op or error?
- catalog regeneration scans `public/issues/*.json` (§8.4:630-631) — on a nonexistent dir,
  and with no EPUB written (dry-run), does it print an empty catalog, the would-be single
  entry, or nothing?
- Does dry-run create `./public` as a side effect? ("except write files" suggests no, but
  `mkdir` is not a file write — ambiguous.)
**Fix:** one paragraph in §9: "A missing `--public-dir` is treated as an empty site:
dedupe is a no-op, prune reports nothing, and the catalog step prints the single entry the
new issue would contribute. `--dry-run` never creates directories."

---

## Item 7 — `--slot ""` on schedule events

**F8 (BLOCKER).** The workflow (§11:961-965) *always* passes both flags:

```
uv run xtpages build \
  --cron "${{ github.event.schedule }}" \
  --slot "${{ github.event.inputs.slot }}" \
```

On a `schedule` event, `github.event.inputs` does not exist, so the expression evaluates to
the **empty string** — the flag is present with value `""`. The same is true on manual
dispatch with the input left blank (default `""`, §11:919-924). §7.1's precedence
(SPEC.md:390-396) says:

1. "An explicit `--slot LABEL` flag wins outright." — no emptiness carve-out.
2. `--cron` is guarded by "and matches a `schedule.slots[].cron`" — an empty `--cron`
   safely falls through.
3. "(manual dispatch with no input, or a local run)" — but the workflow *never* omits the
   flag, so this branch is unreachable as literally described.

So the spec never defines what `--slot ""` does. A literal implementation looks up label
`""`, matches nothing (labels are `^[0-9]{4}$`, §6.1:296), and then behavior is undefined —
error, or silent nearest-slot. This lands on **every scheduled run** and on the documented
first-run setup step (§12.1:1021-1023 "leaving the slot input blank"; README:59-61). Note
the asymmetry that proves the omission is real: `--cron` got a match guard, `--slot` got
"wins outright".
**Fix (pick one, state it):** (a) add to §7.1: "An empty `--slot` value is treated exactly
as if the flag were absent" (this is also what §11:922's input description — "Blank picks
the nearest slot" — already promises); or (b) change the workflow to omit the flag when
empty (shell conditional), which §7.1 then matches.

---

## Item 8 — `p.code` styling vs the sanitizer allowlist

**F9 (BLOCKER).** The spec's own pipeline destroys the `p.code` class it elsewhere relies on:

- §8.2:488-492 fixes the order: absolutize → **unwrap `<pre>`** → **sanitize** → truncate,
  with the rationale that unwrap must run before sanitize ("the sanitizer would otherwise
  have flattened" the `<pre>`).
- §8.3.1:609 says unwrap emits each line as `<p class="code">…</p>`.
- The sanitizer strips **all** `class` attributes (§8.3:549-550), and the only exemption
  (§8.3:559-561) is for meta/notice classes that "are added by our own chapter template
  **afterwards**" — i.e., after sanitize. `p.code` is generated *before* sanitize, so its
  class is stripped.
- Yet the stylesheet styles `p.code` (§8.3:572) — dead rule — and §14.1:1137 requires
  unwrap output of "one `<p class="code">` per line" to survive into the artifact.

Consequences beyond styling: with the class gone, every code line gets the generic `p`
margin (`0 0 0.7em`, §8.3:569) instead of `margin: 0` — the code block renders double-spaced,
and the blank-line convention (a paragraph containing a single U+00A0, §8.3.1:610) loses its
visual distinction. The spec's acceptance test cannot pass under the spec's own ordering, so
the implementer must silently deviate from a "settled" decision.
**Fix (state one explicitly):** (a) scope the sanitizer to preserve `class` on `p` when the
value is exactly `code` (nh3 supports per-tag attribute filters); or (b) re-apply
`class="code"` to the unwrap-generated paragraphs *after* sanitizing, in the same
template-postprocessing step that adds `meta`/`notice`. Option (a) is cleaner.

**F10 (should-fix).** The self-post path skips unwrap entirely: §8.2:493-494 — "Self-posts
skip fetching entirely: `story.text` is HN-supplied HTML, so sanitize it and set
`self_post`." No `unwrap_pre` is specified, yet HN self-post text (Ask HN Show HN bodies)
routinely contains `<pre>` — the exact case §8.3.1:597-600 says would "wreck" the output.
**Fix:** "Self-posts: run `unwrap_pre` on `story.text`, then sanitize" — same order as
articles.

---

## Item 9 — §8.3 document list vs §14.1 `test_epub.py`

**Consistent, with one ambiguity.** §8.3:517-524 fixes spine order: `title.xhtml`, then
`ch001…chNNN` (one per story), then `nav.xhtml` — explicitly "not in the reading spine."
§14.1:1138 expects "chapter count equals story count plus title page" (= N + 1), and
§14.3.5:1159-1160 expects "20 chapters plus a contents page." These agree **provided**
"chapter count" means spine documents, excluding `nav.xhtml` (and `toc.ncx`, which is not a
content document at all).

**F11 (cosmetic).** Make the counting basis explicit so the test can't be written to count
all manifest documents (which would yield N + 2 and "fail" a correct implementation).
**Fix:** in §14.1's test_epub row: "chapter count (spine documents, excluding `nav.xhtml`)
equals story count plus the title page."

---

## Item 10 — Committed `uv.lock` vs `uv sync --frozen`

**No issue found.** §5:219-220 requires committing `uv.lock` (§4:159 lists it); `--frozen`
is used everywhere it matters: the build workflow (§11:945), CI (§11.2:1009), and the
acceptance criterion (§14.3.1:1153). Because CI itself runs `uv sync --frozen`, a lockfile
that has drifted from `pyproject.toml` fails CI — the loop is closed without needing a
separate `uv lock --check` step. README:123's plain `uv sync` for local development is
consistent (local runs may update the lock; CI catches it before merge).

---

## Item 11 — §13 failure table vs §9 exit codes

All eight rows (§13:1104-1113) carry an exit value, and the CLI-facing ones (0, 2, 3) are
consistent with §9:697-698. Two gaps:

**F12 (should-fix).** The row "Publish push rejected | Fail the job | 1" (§13:1113)
conflates two different things. The push is a workflow bash step (§11:967-981), not part of
`xtpages build` — the CLI never pushes, so "exit 1" is not an xtpages exit code here; the
step fails with git's own nonzero code. Harmless in practice but the table's Exit column
promises CLI semantics.
**Fix:** reword the row's Exit cell to "job fails (workflow step)" or move the row out of
the exit-code table.

**F13 (should-fix).** Infrastructure failures after selection succeeds are untabulated: EPUB
write failure (disk full, ebooklib error), manifest write failure, `latest.epub` copy
failure, prune or catalog failure after a successful build. By §9:697-698 they fall into "1
unexpected error," which is defensible, but the spec's governing principle ("a partial issue
always beats no issue," §13:1101) makes the EPUB-write case worth a row, and the partial-file
question is open: if the EPUB write dies midway, is a truncated `hn-…-epub` left in
`public/issues/` for the catalog to pick up? (The workflow aborts before publish, so the
live site is untouched and self-heals per §13:1119-1121 — but the local `./public` is left
dirty.)
**Fix:** add a row: "EPUB/manifest/catalog write fails | exit 1; write to a temp file and
rename so no partial artifact is ever visible; site untouched (workflow aborts before
publish); next run self-heals."

---

## Item 12 — README vs SPEC contradictions

**Clean sub-checks (no issue found):**
- README's setup steps (README:57-64) match §12.1:1018-1026 step for step (public repo →
  workflow permissions → one manual run → Pages source → verify).
- README's schedule two-places rule (README:104-116) matches §7:352-361, including the
  test_schedule_sync enforcement and the 5–30-minute-delay framing.
- README's fetch-conduct claims (README:151-154: identifying UA, five concurrent overall,
  one per host, stop on 429/503) match §6.4:333-338 — *textually*; see F19 for the §8.1
  conflict that makes the README's "one per host" promise unsound as specified.
- README's `nav.xml` insurance (README:90-92), heap note (156-159), idle-fork note
  (161-162), and gh-pages-rewrite note (164-167) all match §10.3, §12.3:1085-1095, §12.1:1028-1030,
  and §11.1 respectively.
- "Expect a handful per issue" of extraction failures (README:149) is a soft expectation,
  not a spec claim; §13:1107 allows "many" to fail. No conflict.

**F14 (cosmetic).** README:5 and README:29 hardcode "top 20 stories" / "fetch HN top 20",
while the spec makes both the feed (`top|best|new`, config:239) and the count
(`story_count`, config:240) configurable. Fine as shorthand for defaults, but §4:161 says
the README must be "kept in sync" — a forker who changes `story_count` gets a stale README.
**Fix:** "reads Hacker News' configured number of top stories (default 20)" or similar.

**F15 (BLOCKER).** §6.1:297 rejects any non-blank `site.base_url` that does not start with
`https://`. But §14.4:1173-1176 instructs: "With `site.base_url` set to
`http://localhost:8000/`, this lets the catalog be opened in a desktop OPDS client, or by
the device itself over the local network" — and README:129-131 gives the same instruction
for the local test loop. Setting that value makes **every** command exit 2 (validation runs
at the start of every command, §6.1:302-303), including `doctor`. The spec's own §6.2:314-317
localhost fallback is `http://…` too, and survives only because derivation happens after
config validation. As written, the documented local device test is impossible.
**Fix:** exempt private/local origins from the https rule — e.g., "must start with
`https://`, except `http://localhost[:port]`, `http://127.0.0.1[:port]`, or
`http://<private-LAN-IP>[:port]`" — and note in §14.4 that the device test needs the
machine's LAN IP, not `localhost` (a device fetching `http://localhost:8000/` fetches from
itself; see also the cross-stage note below).

**F16 (should-fix).** README:179-182 declares the project MIT. §4's repo tree (SPEC.md:122-163)
— introduced by "Create exactly this structure" (§4:120) — contains **no LICENSE file**, so
an implementer following §4 literally ships a repo whose README claims a license that no
file grants. This is the class of omission the brief flags: §4's tree is the authority on
what exists, and every file referenced anywhere must be in it.
**Fix:** add `├── LICENSE # MIT (README asserts it)` to the §4 tree.

---

## Item 13 — §4 repo-layout tree completeness vs cross-references

Sweep of every file referenced anywhere in SPEC.md and README.md against the §4 tree
(SPEC.md:122-163):

| Referenced by | File | In §4 tree? |
|---|---|---|
| §11, §7 | `.github/workflows/build.yml` | ✅ (line 126) |
| §11.2 | `.github/workflows/ci.yml` | ✅ (line 127) — but **wrong section annotation** → F18 |
| §6 | `config.yaml` | ✅ (line 157) |
| §5 | `pyproject.toml`, `uv.lock` | ✅ (lines 158-159) |
| §8.x | all 11 `src/xtpages/*.py` modules | ✅ (lines 129-140) |
| §14.1 | all 7 test files + `conftest.py` | ✅ (lines 142-156) |
| §14.1 | all 6 `tests/fixtures/*` files | ✅ (lines 144-149) |
| §14.4:1173, README:126 | `scripts/serve.sh` | ❌ **missing** → F17 |
| README:179-182 | `LICENSE` | ❌ **missing** → F16 |

**F17 (should-fix).** `scripts/serve.sh` is required by §14.4:1173 ("Provide
`scripts/serve.sh`") and referenced by README:126, but the §4 tree has no `scripts/`
directory at all. Under "Create exactly this structure" (§4:120), it will not be created.
**Fix:** add to the tree:
`├── scripts/` + `│   └── serve.sh      # local preview server (section 14.4)`.

**F18 (should-fix).** §4:127 annotates `ci.yml` as "lint + tests on push/PR (section
14.4)" — but §14.4 is the serve.sh section; ci.yml is specified in §11.2:1007-1010. A wrong
cross-reference inside the authoritative tree misdirects the implementer.
**Fix:** change the annotation to "(section 11.2)".

---

## Item 14 — Own findings

**F19 (should-fix). §6.4's per-host rule contradicts §8.1's concurrent HN fetches.**
§6.4:335-336: "`max_concurrency` is a global ceiling of 5 across the whole run, and
additionally **never more than one in-flight request per host**." §8.1:437-438: "Fetch item
detail concurrently, bounded by `fetch.max_concurrency`" — and every item-detail request
goes to the single host `hacker-news.firebaseio.com` (§8.1:414). Five concurrent requests
to one host violates §6.4 read literally, and README:152-154 repeats "one per host" as an
unconditional promise. The two module specs cannot both be satisfied as written; the
implementer must pick (serialize HN → §8.1's "concurrently" and §14.1:1136's
order-preserved-through-concurrent-fetch test become dead letters; or exempt HN → README's
promise is false).
**Fix:** scope the rule explicitly in §6.4: "never more than one in-flight request per
article host; the HN API (`hacker-news.firebaseio.com`) is exempt — it is a CDN with no
documented rate limit — and is bounded only by `max_concurrency`." Then align README:153.

**F20 (should-fix). §10.2 contradicts itself about the summary.** §10.2:849-851: the
summary "is what the device shows under each catalog row, so leading with the count then
the headlines makes the list scannable." Forty lines earlier, §10.2:800's XML comment says
"summary is ignored by the Xteink; it is here for desktop OPDS clients," and §10.2:836-838
says "The device shows the entry's title and author, and nothing else — `summary` … never
read by CrossPoint's parser." The 849-851 sentence is a stale draft remnant (pre-§12.3
verification). It doesn't change the output, but it is a direct self-contradiction in the
"reproduce exactly" section and could mislead a forker into relying on summary display.
**Fix:** delete or reword 849-851's second sentence to match 836-838 ("For desktop clients,
leading with the count then the headlines makes the list scannable").

**F21 (should-fix).** Merged into F10 (self-post `<pre>` handling).

**F22 (should-fix). Who creates `.nojekyll`?** Three places disagree:
§14.3.4:1156-1158 says running `xtpages build --slot 0300 --public-dir ./public` (a *local*
command, no workflow) "produces … `.nojekyll`"; §9's build pipeline list (686-688) does not
include creating it; §11:973 has the *workflow's publish step* `touch .nojekyll`; §8.5:668-670
only says prune never deletes it. An implementer following §9 + §11 fails acceptance
criterion 4 on a local run.
**Fix:** assign it to the build (e.g., publish.py ensures `.nojekyll` exists in
`public_dir` after every build); the workflow's `touch` then becomes belt-and-braces, which
§11.1:1004-1005 already frames it as.

**F23 (should-fix). `include_hn_discussion_link` has no consumer.** The config key exists
(§6:245) and §6:230-232 promises config is "the forker's entire control panel," but no
module spec reads it: §8.3:530's chapter template emits the `Discussion` anchor
unconditionally, and neither §8.3 nor §10.1 mentions the flag. A forker setting it to false
gets no defined behavior.
**Fix:** one sentence in §8.3: "When `content.include_hn_discussion_link` is false, omit
the `Discussion` anchor from the meta paragraph (the score and domain remain)."

**F24 (should-fix). §14.2's pytest `addopts` is missing from §5's pyproject template.**
§14.2:1144-1146 requires `addopts = "-m 'not live'"` in `pyproject.toml`, but §5:194-217
presents the pyproject content with no `[tool.pytest.ini_options]` section (and no
`[tool.ruff]`). Since §5's block reads as the file's content, the live-test deselection —
which keeps `uv run pytest` (§11.2:1010, §14.3.1) from hitting the network — has no home.
**Fix:** append to §5's TOML:
`[tool.pytest.ini_options]` / `addopts = "-m 'not live'"`.

**F25 (should-fix). Shell-injection anti-pattern in the workflow.** §11:961-965
interpolates `${{ github.event.inputs.slot }}` and `${{ github.event.schedule }}` directly
into a `run:` block. `github.event.schedule` is the workflow's own cron string (safe), but
`inputs.slot` is typed free-form by whoever dispatches, and a value like `"; rm -rf .; echo "`
executes on the runner. Practical risk is low (dispatch requires write access), but this is
GitHub's documented script-injection hazard and the fix is free.
**Fix:** pass via env and quote the variable:
```yaml
env:
  SLOT: ${{ github.event.inputs.slot }}
  CRON: ${{ github.event.schedule }}
run: uv run xtpages build --cron "$CRON" --slot "$SLOT" --public-dir public
```

**F26 (cosmetic). The allowlist rationale misstates §12.3.** §8.3:552-553 calls the
sanitizer tag list "the set the device actually recognizes, read from
ChapterHtmlSlimParser.cpp and recorded in section 12.3." But §12.3:1075 records the device
also recognizing `div`, `span`, `ins`, `strike`, `ruby`, `rt` — none of which are in the
§8.3:546-547 allowlist. The list is a conservative *subset*; the behavior is safe (stripped
tags keep their text), but the sentence is false by the spec's own table and could provoke
an implementer to "correct" the allowlist.
**Fix:** reword to "a conservative subset of the set the device recognizes."

**F27 (cosmetic). Nearest-slot ties undefined.** The two slots are 18h/6h apart (0300→2100,
2100→0300), so the equal-distance midpoints are exactly 12:00:00 UTC (between 0300 and
2100) and 00:00:00 UTC (between 2100 and next-day 0300). §7.1:395-401's "pick the slot
whose time is nearest" and "pick the one closest to now" give no tie-break. A run landing
exactly on the microsecond boundary is vanishingly unlikely (and scheduled runs are
delayed), so this is cosmetic — but §2 promises settledness.
**Fix:** "ties resolve to the later slot."

**F28 (cosmetic). Manifest `counts` shape undefined.** §10.1:753's example shows
`{"ok": 18, "self_post": 1, "extraction_failed": 1, "requested": 20}` — three of the six
possible statuses (§8.2:449-457). Unspecified: are zero-count statuses omitted or always
present? Is `requested` the configured `story_count` or the number of stories actually
selected (which can be lower per §8.5:665-666)? Consumers today only debug with it, so
cosmetic.
**Fix:** "counts has a key for every status that occurred, plus `requested` = the number of
stories selected for the issue; consumers must not assume all status keys are present."

**F29 (cosmetic). Catalog timestamp sources only inferable.** §10.2:795-796's example entry
has `<updated>2026-09-06T03:07:41Z` and `<dc:issued>2026-09-06T03:00:00Z`, which match
§10.1's `built_at` and `slot_at` respectively — but the prose (§10.2:843-852) never states
the mapping, and `nav.xml`'s `<updated>` (§10.3:871) has no defined source at all (build
time? newest manifest's `built_at`?). §10 says "Reproduce the structure exactly" — the
mapping should be prose, not inference.
**Fix:** "entry `<updated>` = manifest `built_at`; `<dc:issued>` = manifest `slot_at`;
`nav.xml` `<updated>` = the newest manifest's `built_at`."

**F30 (cosmetic). "HN Daily" title prefix is hardcoded.** The EPUB title (§8.3:511) and
catalog entry titles (§10.2:794) are `HN Daily <date> <slot> UTC`, while `site.title`
("Hacker News Daily", §6:268) is configurable and feeds only the feed-level `<title>`. A
forker who rebrands `site.title` still ships "HN Daily" issues. Probably intentional
(filename-sort rules, §10.2:827-834), but the derivation is unstated.
**Fix:** state whether the entry/EPUB title prefix is fixed or derived from `site.title`.

**F31 (cosmetic). `doctor`'s build.yml discovery path unspecified.** §9:692-693 says doctor
must "confirm cron/config schedule agreement," which requires reading
`.github/workflows/build.yml` — but doctor takes only `--config PATH` (§9:683), and no rule
says where to find the workflow file (repo root relative to CWD? relative to config?).
**Fix:** "doctor reads `.github/workflows/build.yml` relative to the current directory."

**F32 (cosmetic). Retry rule needs two clauses read together.** §8.2:467-468: retry "only
on timeouts, connection errors, and 5xx. Never retry a 4xx, a `429`, or a `503`." Since 503
*is* a 5xx, the second sentence carves an exception out of the first. Consistent when read
carefully (and with §6.4:337-338), but easy to misimplement as "retry all 5xx."
**Fix:** "…and 5xx other than 503."

---

## Cross-stage notes (non-blocking, for S5)

- **S1 refuted one §11 pin:** `actions/checkout@v4` is not the current major (v7 per
  research-Q1.md, live-fetched 2026-09-06); `astral-sh/setup-uv@v5` exists but is also not
  current. §11:938/940 hardcode both. Not an internal inconsistency — flagging so S5 can
  decide whether "pinned and known-good" or "current major" is the policy.
- **S2 could not empirically confirm** the trafilatura kwargs (research-Q2.md item (a):
  "NOT FOUND (locally), likely CONFIRMED") — F2's missing fallback therefore still matters.
- **S3 found no refuted §12.3 claims** (explore.md), so item 5's confirmed-62 premise and
  F26's §12.3 tag list stand as written.

---

## Bottom line

The spec's engineering content (device constraints, OPDS shape, EPUB structure, workflow
mechanics) is internally consistent in the large. The failures are concentrated where the
spec's *own machinery* interacts with its *own rules*: the workflow's always-present
`--slot ""` vs §7.1's precedence (F8), the unwrap→sanitize order vs the `p.code` class
(F9), the https-only `base_url` rule vs the localhost test loop (F15), and the per-host
conduct rule vs HN's concurrent fetches (F19). All four are one-to-three-sentence fixes;
none requires redesign. Until they are fixed, §2's "every decision below is settled" should
be read as "settled except where this document contradicts itself."
