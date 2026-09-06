# spec-verify S5 — Reconciled summary and final verdict

**Verdict: SPEC.md is implementable after ~20 targeted text corrections — no design changes.**
All 23 firmware claims (S3), 9 of 10 platform claims (S1), and every library API assumption
except one (S2, settled by the orchestrator's smoke tests) hold as written. The real work is
S4's three internal contradictions (F8/F9/F15), which every implementation path hits.
Sources: `research-Q1.md`, `research-Q2.md`, `explore.md`, `consistency.md`; this file stands alone.

## 1. Claims CONFIRMED as written

**Platform — S1 (live docs.github.com + curl, 2026-09-06)**
- `github.event.schedule` carries the triggering cron string (§7.1:383, §16:1218) — events page #schedule; §16 assumption now empirically retired.
- Scheduled runs are delayed under high load, worst at the top of the hour (§7/§11 comments) — documented (the "5–30 min" figure itself is community-only; see §2.3).
- `GITHUB_TOKEN` can push `gh-pages` under read/write workflow permissions (§12.1:1019) — docs workflow-syntax #permissions; the workflow's own `permissions: contents: write` is the operative grant.
- Pages serves `.xml` as `application/xml` (§14.3.8:1165) — new official "MIME types on GitHub Pages" section (mime-db) + live curl on a literal `*.github.io` host.
- Scheduled workflows auto-disable after 60 days of repo inactivity, with email beforehand (§12.1:1028) — docs; email fires ~7 days prior (community #137768 quoting GitHub's email).
- Free plan requires a public repo (§2:84, §12.1:1018) — docs "creating a GitHub Pages site"; the "Repo visibility: Public" decision is load-bearing.
- `concurrency {group, cancel-in-progress: false}` queues pending runs (§11:929, §11.1:1001) — docs; default one-pending cap irrelevant at two crons 18 h apart.
- Orphan single-commit force-push to `gh-pages` is a known-good pattern (§11.1:984) — peaceiris README `force_orphan` (third-party-documented), incl. the first-push 403 → select Pages branch ordering matching §12.1.
- `astral-sh/setup-uv@v5` exists with `python-version` + `enable-cache` inputs (§11:940) — v5/action.yml live-fetched (but stale; see §2.2).

**Libraries — S2 + orchestrator smoke tests (definitive, at resolved versions)**
- trafilatura **2.2.0**: all 7 §8.2 kwargs present in `extract()`; the spec's exact call produced 3059-char HTML with `<h1>` preserved → §8.2 kwargs CONFIRMED and the ≥2.2 pin CONFIRMED; §5/§16's "most dangerous assumption" is settled.
- httpx 0.28.1 (installed-source evidence): `max_redirects=5` tightens the default 20 and raises `TooManyRedirects` on the 6th redirect; `iter_bytes` streams lazily and aborts mid-body — §8.2 CONFIRMED.
- nh3 **0.3.7**: `clean()` takes a `tags` set + per-tag `attributes` dict exactly as §8.3 assumes; `Cleaner` exists; smoke test passed → §8.3 CONFIRMED (with the `link_rel` caveat in §2.5).
- ebooklib **0.20**: zip's first entry is `mimetype`, STORED uncompressed, in both test variants; package version attr = 3.0 (EPUB3) → §8.3/§14.1 mimetype+EPUB3 claims CONFIRMED.
- S2 residual note: httpx timeouts are per-operation, not a total budget (feeds §3.4).

**Firmware — S3 (all 23 §12.3 claims vs local source; zero contradictions; file:line in explore.md)**
- Parser: 62-entry cap (64−2, OpdsParser.cpp:8-11,124-125); field limits title 160/author 120/id 128/href 768 (:11-14,215-221); acquisition-rel + exact `application/epub+zip` strcmp (:149-151); empty-title/no-link entries dropped (:191-193); `rel="next"` pagination (:142-144); `kind=`/`<summary>` ignored.
- Filename: `author - title.epub` composition and 100-byte sanitization charset with UTF-8 boundary handling (OpdsFilename.cpp:5-22, StringUtils.cpp:23-33).
- Chapter parser: exact recognized-tag list incl. real table support; `<pre>` nowhere handled (ChapterHtmlSlimParser.cpp:54-60); whitespace collapse (:63-88); `li` self-bullet (:1389-1392); 1024-anchor cap (:41-46).
- CSS: property set confirmed; `font-size`/`line-height`/`color`/`font-family` absent; only element/`.class`/`element.class` selectors (CssParser.cpp:615+, .h:19-24).
- Network/store: `esp_crt_bundle_attach` TLS (HttpDownloader.cpp:152-159); 5-redirect cap (:35,186-197); 60 s timeout (:33); 40 KB-free/20 KB-largest-block heap gate (HttpDownloader.h:30); preemptive basic auth (:168-172); max 8 servers (OpdsServerStore.h:24).
- S4 clean items (no issue found): first-run dedupe no-op (§13:1110, §11:952, §8.5:654); committed `uv.lock` + `uv sync --frozen` loop closed (§5:219, §11:945, §11.2:1009); §8.3 spine order vs §14.1 counts consistent (mod F11 wording); README setup steps match §12.1.

## 2. Claims REFUTED / wrong — SPEC.md corrections

**External (S1/S2 smoke tests)**
1. **`actions/checkout@v4` is not the current major** — §11:938. Latest is v7.0.1 (v4 alive but three majors stale; the v4.4+ safety change only affects `pull_request_target`, unused here). → Bump to `@v7` (or SHA pin) at implementation.
2. **`setup-uv@v5` is not current** — §11:940-943. Latest v10.0.1; since v8 only immutable tags are published; v5 is frozen on node20. → Pin `@v10.0.1` (or SHA), re-verifying inputs.
3. **Workflow comments outdated** — §7:373-375, §11:914-916. The "5–30 minutes" figure is undocumented folklore; "GitHub does not honour timezones in cron" is false (an IANA `timezone:` key is now documented; cron still defaults to UTC); and under extreme load queued schedule runs may be **dropped**, not just delayed. → Reword to the documented claim + add "recovery = manual workflow_dispatch re-run". No design change.
4. **ebooklib does NOT write `nav.xhtml`/`toc.ncx` "by default"** — §8.3:502-504, §8.3:1082, §14.1:1138. Smoke test: with no items added, nav: False, ncx: False; with `EpubNcx`+`EpubNav` added, nav: True but **toc.ncx still absent** (see §3.1). → Replace with: "`epub.py` explicitly adds `EpubNcx` and `EpubNav` — ebooklib does not generate them by default." §14.1's zip assertions stay unchanged.
5. **nh3 injects `rel="noopener noreferrer"` into output `<a>` tags** — §8.3:545-550. `link_rel` default adds an attribute outside the spec's allowlist (harmless: the device ignores unknown attributes, per confirmed §12.3). → Either set `link_rel=None` in sanitize() or add a one-line note accepting the injected rel.
6. **§12.1 step 2 rationale overstated** — §12.1:1019-1020. "Without this, the publish step gets a read-only token and fails" is wrong: the workflow's `permissions: contents: write` already grants the push. → Reword as belt-and-braces (covers future removal of the block).

**Internal contradictions — S4 blockers**
7. **F8 — `--slot ""` undefined** (§11:961-965 always passes `--slot "${{ github.event.inputs.slot }}"`; on schedule events that's the empty string; §7.1:390-396 precedence has no emptiness rule — `--cron` got a match guard, `--slot` got "wins outright"). Hits every scheduled run and the documented first setup (§12.1:1021). → Add to §7.1: "An empty `--slot` value is treated exactly as if the flag were absent" (matches §11:922's own promise); or omit the flag when empty via shell conditional.
8. **F9 — pipeline order strips the `p.code` class** (§8.2:488-492 orders unwrap→sanitize; §8.3.1:609 unwrap emits `<p class="code">`; §8.3:549-561 sanitizer strips all `class`, exempting only classes added *after* sanitize; yet §8.3:572 styles `p.code` and §14.1:1137 requires it in the artifact). The spec's own acceptance test cannot pass. → Pick (a) sanitizer preserves `class="code"` on `p` (nh3 per-tag attributes support this) — cleaner; or (b) re-apply the class post-sanitize in the template step that adds `meta`/`notice`.
9. **F15 — https-only `base_url` forbids the documented localhost test** (§6.1:297 rejects non-https; §14.4:1173-1176 and README:129-131 instruct `http://localhost:8000/`; validation runs on every command, §6.1:302-303, so every command exits 2). → Exempt `http://localhost[:port]`, `http://127.0.0.1[:port]`, and private-LAN origins; note the device test needs the machine's LAN IP, not `localhost`.

**S4 should-fix — complete, condensed (16)**
- **F2** §5:222-224/§16:1220 — trafilatura assumption has no Plan B (risk now low post-smoke-test; still add "stop and record the deviation if any kwarg is missing").
- **F3** §3:96-104 vs §9:686-688/§11:960-965 — diagram shows three workflow commands; `build` does all three. Relabel steps 4–5 as sub-steps of 3.
- **F4** §8.5:671-673/§9:686-688 — `latest.epub` copy rule undefined when the just-built issue isn't newest (reachable via manual `--cron` runs). State: copy the EPUB with the greatest slot instant among all manifests.
- **F7** §9:690-691 — `--dry-run` on a missing `./public` undefined (manifest read, prune, catalog, mkdir?). State: missing dir = empty site; dry-run never creates directories.
- **F10** §8.2:493-494 — self-posts skip `unwrap_pre`, yet HN self-post HTML routinely contains `<pre>` (the exact §8.3.1:597 "wreck" case). Same order as articles: unwrap, then sanitize.
- **F12** §13:1113 — "Publish push rejected → exit 1" conflates CLI exit codes with workflow job failure; the CLI never pushes. Reword the Exit cell.
- **F13** §13 table/§9:697-698 — post-selection infra failures (EPUB/manifest/catalog write) untabulated; partial-file state open. Add a row; write to temp + rename.
- **F16** README:179-182 vs §4:120-163 — README declares MIT; §4 tree has no LICENSE. Add `LICENSE` to the tree.
- **F17** §14.4:1173/README:126 vs §4 tree — `scripts/serve.sh` required but absent from "create exactly this structure". Add `scripts/serve.sh`.
- **F18** §4:127 — `ci.yml` annotated "(section 14.4)"; it is §11.2. Fix annotation.
- **F19** §6.4:335-336 vs §8.1:437-438 — "never more than one in-flight request per host" vs 5 concurrent detail fetches to `hacker-news.firebaseio.com`: mutually exclusive as written. Exempt the HN API host in §6.4 (bounded by `max_concurrency` only); align README:152-154.
- **F20** §10.2:849-851 vs :800/:836-838 — self-contradiction on whether the device shows the summary (it ignores it). Delete the stale sentence.
- **F22** §14.3.4:1156-1158 vs §9:686-688/§11:973 — three conflicting owners for `.nojekyll`. Assign to build; the workflow `touch` is belt-and-braces.
- **F23** §6:245 — `include_hn_discussion_link` has no consumer in any module spec. One sentence in §8.3 defining the false behavior.
- **F24** §14.2:1144-1146 vs §5:194-217 — pytest `addopts = "-m 'not live'"` missing from §5's pyproject template. Append `[tool.pytest.ini_options]`.
- **F25** §11:961-965 — `${{ github.event.inputs.slot }}` interpolated into `run:` is GitHub's documented script-injection hazard. Pass via `env:` and quote.

**S4 cosmetic (12, batch-acceptable):** F1 §2:7-10 "settled" framing; F5 §13:1108 exit-3 short-circuit point; F6 §6.1:298 validation should be `retention×slots+1 > 62`; F11 §14.1:1138 counting basis (exclude `nav.xhtml`); F14 README:5/:29 hardcoded "top 20"; F26 §8.3:552 allowlist is a *subset* of §12.3's tag list (device also takes div/span/ins/strike/ruby/rt); F27 §7.1:395 tie-break ("ties → later slot"); F28 §10.1:753 manifest `counts` shape; F29 §10.2:795 timestamp mapping (entry `<updated>`=built_at, `<dc:issued>`=slot_at, nav.xml `<updated>`=newest built_at); F30 §8.3:511 "HN Daily" prefix vs configurable `site.title`; F31 §9:692 doctor's build.yml discovery path; F32 §8.2:467 "5xx other than 503" wording.

## 3. Claims UNVERIFIABLE before implementation (+ cheapest settling experiment)

1. **toc.ncx generation in ebooklib 0.20** — smoke test: `EpubNcx` was added yet `toc.ncx` never appeared in the zip, even with `add_nav=True` (the test's own expectation was contradicted; cause unknown — serialization trigger, spine/toc coupling, or naming). → While writing epub.py: read ebooklib's `_write_ncx` trigger in installed source, try a variant with `book.spine`/`book.toc` fully set, then assert `"toc.ncx" in zipfile.ZipFile(path).namelist()` in test_epub.py.
2. **Real-device rendering + OPDS behavior** (§12.2:1044-1048; the stock Xteink OPDS client is uninspected, §10.3:862-864). → After §16 build-order step 4: copy one built EPUB to the device via SD card and open it; after first deploy: open `catalog.xml` from the device.
3. **Our own deployed file's content-type in situ** (docs+curl settled the platform claim; only *our* file remains). → Keep the one-line post-deploy check from §14.3.8: `curl -sI …/catalog.xml | grep -i content-type`.
4. **Total fetch wall-clock** — httpx timeouts are per-operation, so a slow-drip body has no duration bound; §8.2's `timeout_seconds` semantics are unpinned. → If a total budget is wanted, add a `time.monotonic()` deadline in the chunk loop; test against a local 1-byte-per-second server.
5. **Real-world extraction yield** ("expect a handful per issue", README:149/§13:1107). → First `--dry-run` over the real HN top-20: read `extraction_failed` from the manifest; revisit `favor_precision` only if worse than "a handful".

## 4. Decisions the user must resolve or explicitly accept before implementation

1. **F8 — define `--slot ""` semantics** — every scheduled run executes this path; without a decision the most-executed behavior is undefined.
2. **F9 — pick the `p.code` fix: (a) preserve in sanitizer or (b) re-apply after** — §14.1's acceptance test cannot pass until one is chosen.
3. **F15 — accept the localhost/LAN exemption to the https rule** — §14.4's documented device test is impossible as written.
4. **F19 — accept exempting the HN API host from the per-host rule** (recommended) or serialize HN fetches — §6.4 and §8.1 cannot both hold; the implementer would otherwise have to choose silently.
5. **S2(d) — accept the §8.3 amendment: `epub.py` explicitly adds `EpubNcx` + `EpubNav`** — trivial code change; keep §14.1's zip assertions; toc.ncx anomaly resolved per §3.1.
6. **Pin policy — bump checkout@v4→v7 and setup-uv@v5→v10.0.1/SHA, or explicitly keep stale-but-working pins** — decides "current" vs "pinned and known-good" for §11.
7. **F25 — accept the env-var rewrite of the workflow's build step** — free fix for a documented injection hazard.
8. **F2 — accept adding the trafilatura fallback sentence** — closes the last "no Plan B" gap the spec itself flags as most dangerous.
9. **Should-fix batch F3, F4, F7, F10, F12, F13, F16, F17, F18, F20, F22, F23, F24 — accept as specified in §2** — all are one-to-three-sentence edits; none requires redesign.
10. **Cosmetic batch F1, F5, F6, F11, F14, F26, F27, F28, F29, F30, F31, F32 — accept a batch pass** — wording precision only; safe to fold into the same spec revision.

**Bottom line:** external facts are settled (S1 live, S2 smoke tests, S3 source — nothing architectural fails). Apply §2's corrections — blockers F8/F9/F15 are one-to-three-sentence edits — then start implementation at §16's build order; the only remaining unknowns are the five post-implementation experiments in §3.
