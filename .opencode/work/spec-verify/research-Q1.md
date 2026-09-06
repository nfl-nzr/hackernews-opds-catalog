# research-Q1.md — S1: GitHub Actions / Pages platform claims

**Stage:** S1 of the spec-verify plan (`.opencode/work/spec-verify/brief.md`)
**Spec under verification:** `SPEC.md` (claims drawn from §7.1, §11, §11.1, §12.1, §14.3.8, §16)
**Date:** 2026-09-06 · **Pass 2 (live verification) — supersedes all provisional verdicts from Pass 1**

## Environment note (live pass completed)

A live pass was completed on 2026-09-06 using `webfetch` for documentation pages and
`curl -sI` for empirical HTTP-header checks. All 10 claims received live evidence; none
remain UNVERIFIABLE. Source classes to keep in mind when weighing the citations:

- **Official docs** (docs.github.com) settle a, b(documented part), c, d, e(60-day rule),
  f, g. Note that docs.github.com has been restructured since Pass 1's URLs were
  written: several canonical URLs still resolve via redirect, and the Pages
  plan-requirement sentence has *moved* (see claim f for the new location).
- **Third-party README** (peaceiris/actions-gh-pages) settles h — labeled
  third-party-documented, not GitHub-official-docs.
- **Community-documented GitHub behavior** settles the two folklore-sized pieces:
  the "5–30 minutes" figure in b (verified as *absent* from official docs) and the
  pre-disable email in e (a GitHub community bug report quoting GitHub's actual email
  text; the current official doc pages no longer mention the email at all).
- **Empirical HTTP** (live `curl` against real Pages sites, including one on a literal
  `*.github.io` host) settles d, now backed by a *newly present* official docs section
  on Pages MIME types.

## Summary table

| # | Claim (spec ref) | Live verdict | Key citation |
|---|---|---|---|
| a | `github.event.schedule` carries the triggering cron string (§7.1, §16) | **CONFIRMED** | events-that-trigger-workflows `#schedule` |
| b | Runs "often 5–30 min late" (§7 comment, §11 comment) | **Split: CONFIRMED (delay documented) / community-only (the 5–30 min figure)** | events-that-trigger-workflows `#schedule` |
| c | `GITHUB_TOKEN` pushes `gh-pages` under "Read and write" setting (§12.1) | **CONFIRMED, with refinement: the workflow's `permissions: contents: write` is the operative grant** | workflow-syntax `#permissions` |
| d | Pages serves `.xml` with an XML content type (§14.3.8) | **CONFIRMED (docs + empirical)** | "MIME types on GitHub Pages" docs section + live `curl` |
| e | Scheduled workflows auto-disabled after 60 days idle, email notice (§12.1) | **CONFIRMED; email is genuinely sent *before* (~7 days)** | disabling-and-enabling-a-workflow + community discussion #137768 |
| f | Free-plan Pages requires a public repo (§2, §12.1) | **CONFIRMED** | creating-a-github-pages-site |
| g | `concurrency` with `cancel-in-progress: false` queues pending runs (§11) | **CONFIRMED, incl. the one-pending default cap (now a documented `queue` property)** | control-the-concurrency-of-workflows-and-jobs |
| h | Single-commit force-push (orphan) to `gh-pages` is a known-good pattern (§11.1) | **CONFIRMED (third-party-documented)** | peaceiris/actions-gh-pages README, `force_orphan` |
| i | `astral-sh/setup-uv@v5` exists; supports `python-version` + `enable-cache` (§11) | **CONFIRMED for existence/inputs; v5 is NOT current (v10.0.1 latest)** | live fetch of `v5/action.yml` + releases page |
| j | `actions/checkout@v4` is the current major (§11) | **REFUTED — current major is v7 (v7.0.1 latest)** | actions/checkout releases page |

---

## Claim detail

### (a) `github.event.schedule` carries the exact cron string that fired the run — SPEC §7.1 (line 383), §16 (line 1218)

- **Final verdict: CONFIRMED** (live fetch).
- **Citation:** https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
  (fetched 2026-09-06). The page states verbatim: *"A single workflow can be triggered by
  multiple `schedule` events. Access the `schedule` event that triggered the workflow
  through the `github.event.schedule` context."* Its example compares against a cron
  literal: `if: github.event.schedule != '30 5 * * 1,3'`. The same wording appears in
  the workflow-syntax reference (`on.schedule` section,
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule).
- **Spec fit:** the spec already defends the one residual risk — whitespace variance — by
  matching "the exact string after collapsing internal whitespace" (§7.1 step 2).
- **Consequence if it had been refuted:** non-fatal by the spec's own mitigation
  (nearest-slot fallback §7.1 step 3) — moot now.

### (b) "Scheduled runs are often 5–30 minutes late under load" — SPEC §7 comment (lines 374–375), §11 comment (lines 915–916)

- **Final verdict: Split — CONFIRMED for the documented claim; the "5–30 minutes" figure
  is community-only (verified absent from official docs).**
- **Citation:** events-that-trigger-workflows `#schedule` (fetched 2026-09-06). Documented
  wording, captured verbatim: *"The `schedule` event can be delayed during periods of high
  loads of GitHub Actions workflow runs. High load times include the start of every hour.
  If the load is sufficiently high enough, some queued jobs may be dropped. To decrease
  the chance of delay, schedule your workflow to run at a different time of the hour."*
- **Two live findings beyond the Pass 1 provisional:**
  1. The docs now also warn that **queued scheduled jobs may be dropped entirely** under
     sufficiently high load — a stronger caveat than the spec's comments state. The spec's
     design already tolerates this (§7.1 names issues by slot; manual re-run via
     workflow_dispatch is the recovery path), but the comment could say so.
  2. **The spec's "GitHub does not honour timezones in cron" comments (§7 line 373,
     §11 line 914) are now outdated.** The fetched `schedule` docs and workflow-syntax
     reference both document an optional per-entry `timezone` key taking an IANA timezone
     string (e.g. `- cron: '30 5 * * 1-5'` + `timezone: "America/New_York"`). The cron
     expression itself still defaults to UTC, so the shipped config is unaffected, but
     those two comment lines should be reworded.
- **Consequence:** none operationally (§7.1 names the issue by slot, not actual start
  time). Recommended rewording of the workflow comments: to the documented claim
  ("often delayed, worst at the top of the hour; under extreme load queued runs can be
  dropped") and to the timezone comment ("cron defaults to UTC; an optional `timezone:`
  key is also supported").

### (c) Default `GITHUB_TOKEN` can push to `gh-pages` when Settings → Workflow permissions → "Read and write" is set — SPEC §12.1 step 2 (lines 1019–1020)

- **Final verdict: CONFIRMED — and the Pass 1 refinement is live-confirmed: the
  workflow's explicit `permissions: contents: write` block is the operative grant, so
  §12.1 step 2 is belt-and-braces, not a hard dependency.**
- **Citations (fetched 2026-09-06):**
  - Workflow syntax reference (`#permissions`,
    https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions):
    *"You can use `permissions` to modify the default permissions granted to the
    `GITHUB_TOKEN`, adding or removing access as required"*; *"When you add the
    `permissions` key within a specific job, all actions and run commands within that job
    that use the `GITHUB_TOKEN` gain the access rights you specify"*; *"If you specify
    the access for any of these permissions, all of those that are not specified are set
    to `none`."*
  - The token-authentication tutorial
    (https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication,
    now titled "Use GITHUB_TOKEN for authentication in workflows"): *"Use the
    `permissions` key in your workflow file to modify permissions for the `GITHUB_TOKEN`
    for an entire workflow or for individual jobs."*
  - peaceiris/actions-gh-pages README (live-fetched, see (h)): documents the exact 403
    "Write access to repository not granted" push failure and prescribes adding
    `permissions: contents: write` as the fix, describing the repo-default "read and
    write permissions" setting as the *alternative* — the two are interchangeable paths
    to the same grant.
- **Spec impact:** §12.1's stated reason — "Without this, the publish step gets a
  read-only token and fails" — is over-stated as written: the workflow's own top-level
  `permissions: contents: write` (§11 lines 926–927) grants the push even if step 2 is
  skipped. The setting remains worth keeping as defense-in-depth (it covers the case
  where someone removes the `permissions:` block), but it should be described as such.
  One residual limit noted in the docs: org owners can restrict `GITHUB_TOKEN` write
  access at the organization level — irrelevant for a personal-account fork, which is
  the spec's deployment model.

### (d) GitHub Pages serves `.xml` with an XML content type (`application/xml` or `text/xml`) — SPEC §14.3.8 (lines 1165–1167)

- **Final verdict: CONFIRMED — upgraded from empirical-only.** The Pass 1 prediction that
  this would be undocumented is out of date: the docs now have an official section.
- **Citations:**
  - **Official docs (new):** "MIME types on GitHub Pages", in
    https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
    (fetched 2026-09-06): *"GitHub Pages supports more than 750 MIME types across
    thousands of file extensions. The list of supported MIME types is generated from the
    [mime-db project](https://github.com/jshttp/mime-db)."* mime-db maps `.xml` to
    `application/xml`, and the section confirms there is no per-file override mechanism.
  - **Empirical (live `curl -sI`, 2026-09-06):**
    - `https://mmistakes.github.io/minimal-mistakes/feed.xml` → `HTTP/2 200`,
      `content-type: application/xml` (a literal `*.github.io` host)
    - `https://jekyllrb.com/feed.xml` and `/sitemap.xml` → `200`, `application/xml`
    - `https://choosealicense.com/sitemap.xml` → `200`, `application/xml`
    - (Negative controls: nonexistent `.xml` paths returned 404 with `text/html`,
      confirming the header varies with the file, not the host.)
- **Spec fit:** the spec's own §12.3 reading of `HttpDownloader.cpp` says the device
  fetches by URL without MIME validation, so real-world risk was already low; it is now
  settled as correct on all fronts. Keeping the post-deploy
  `curl -sI …/catalog.xml | grep -i content-type` check in acceptance §14.3.8 is still
  worthwhile (it costs one command and confirms *our* file), but the claim no longer
  depends on it.

### (e) Scheduled workflows auto-disabled after 60 days of repo inactivity, with email notice — SPEC §12.1 note (lines 1028–1030)

- **Final verdict: CONFIRMED.** The Pass 1 provisional assessment was wrong in one
  direction and is corrected here: the email is genuinely sent **before** the disable,
  so the spec's "GitHub emails the owner before doing it" is accurate — arguably
  understated.
- **Citations (fetched 2026-09-06):**
  - **60-day rule, official docs, verbatim on two live pages:**
    - disabling-and-enabling-a-workflow
      (https://docs.github.com/en/actions/using-workflows/disabling-and-enabling-a-workflow):
      *"In a public repository, scheduled workflows are automatically disabled when no
      repository activity has occurred in 60 days."* The same sentence appears in the
      schedule-event notes on the events page.
    - Same pages: *"When a public repository is forked, scheduled workflows are disabled
      by default"* — directly relevant to the spec's fork-based deployment model.
  - **Email timing, community-documented:** GitHub community discussion #137768
    (https://github.com/orgs/community/discussions/137768, Sep 2024, filed as a bug)
    quotes GitHub's actual email text: *"Scheduled workflows are disabled automatically
    after 60 days of repository inactivity. … You can prevent `workflow` from being
    disabled on the workflows page."* The reporter's observation: the email fires
    **~7 days before** disable (around day 53), though the "continue running workflow"
    button only appears later (~day 58). The current official doc pages no longer mention
    the email at all, so the "before" claim rests on this community evidence — but it is
    a direct quote of GitHub's own email, not folklore.
- **Wording nuances for the spec:** (1) the rule applies to *public* repositories — the
  spec's note doesn't say so, but §12.1 step 1 makes the repo public anyway, so no
  change is needed; (2) the trigger is *repository* activity, not workflow success — a
  fork with any commits keeps schedules alive, matching the spec's "a single commit
  re-enables it"; (3) the events page notes notifications for scheduled workflows go to
  the user who last modified the cron syntax — for a fork, effectively the owner.

### (f) Free-plan GitHub Pages requires the repo to be public — SPEC §2 (line 84), §12.1 step 1 (line 1018)

- **Final verdict: CONFIRMED** (live fetch, 2026-09-06). The Pass 1 [time-sensitive]
  worry that plan terms might have changed by 2026 did not materialize.
- **Citation:** https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
  — verbatim: *"If the account that owns the repository uses GitHub Free or GitHub Free
  for organizations, the repository must be public."*
- **Documentation-location note:** the "About GitHub Pages" URL from Pass 1 now
  redirects to a trimmed "What is GitHub Pages?" page that no longer carries the plan
  requirement; the sentence lives on the creating-a-site page above. A corroborating
  statement appears on the publishing-source page: Pages sites *"are publicly available
  on the internet, even if the repository for the site is private (if your plan or
  organization allows it)"* — i.e. private-repo Pages exists only on paid plans.
- **Consequence:** the spec's settled decision "Repo visibility: Public" is correct and
  load-bearing for a free-account deployment; no spec change needed.

### (g) `concurrency: {group, cancel-in-progress: false}` queues (not drops) pending runs — SPEC §11 (lines 929–931), §11.1 (lines 1001–1003)

- **Final verdict: CONFIRMED** (live fetch, 2026-09-06).
- **Citation:** https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs
  — verbatim: *"This means that there can be at most one running job or workflow in a
  concurrency group at any time. When a concurrent job or workflow is queued, if another
  job or workflow using the same concurrency group in the repository is in progress, the
  queued job or workflow will be `pending`."*
- **The one-pending cap, now a documented `queue` property (new since Pass 1's model
  knowledge):** *"To allow more than one `pending` job or workflow run to wait in the
  same concurrency group, use the optional `queue` property"* — `single` (default):
  *"At most one job or workflow run can be `pending` … any existing `pending` … is
  canceled and replaced"*; `max`: *"Up to 100 jobs or workflow runs can be `pending` …
  once the queue is full, any additional jobs or workflow runs are canceled."* Also
  documented: runs in a group are processed **FIFO by time-started-waiting** (ordering
  not guaranteed), group names are case-insensitive, and `queue: max` +
  `cancel-in-progress: true` is a validation error.
- **Spec fit:** the spec's config (`group: xtpages-publish`, `cancel-in-progress: false`)
  queues overlapping runs with a default queue depth of one pending — exactly as §11.1
  assumes. With two crons 18 h apart plus rare manual dispatch, the cap is operationally
  irrelevant; serialization of the force-push (the reason §11.1 calls the group
  mandatory) holds. No spec change needed.

### (h) Single-commit force-push (orphan branch) to `gh-pages` is a known-good pattern — SPEC §11.1 (lines 984–1005)

- **Final verdict: CONFIRMED as third-party-documented** (live fetch of the README,
  2026-09-06) — not GitHub-official-docs, as Pass 1 expected.
- **Citation:** peaceiris/actions-gh-pages README (current major `v4`),
  https://github.com/peaceiris/actions-gh-pages — "Force orphan" section, verbatim:
  *"We can set the `force_orphan: true` option. This allows you to make your publish
  branch with only the latest commit."* Documented tradeoffs match the spec's §11.1:
  default behavior removes existing files in the publish branch (i.e. hand-placed files
  are erased), and the action adds/touches `.nojekyll` by default — mirroring the spec's
  publish-step `touch .nojekyll`.
- **Bonus confirmation for §12.1:** the README's "First Deployment with `GITHUB_TOKEN`"
  section documents that the first push can 403 until the Pages branch is selected in
  repository settings — matching the spec's setup ordering (run once by hand → then
  select `gh-pages` in Settings → Pages).
- **Consequence if it had been refuted:** moot — the pattern is documented and matches
  the spec's size argument (git retains every blob ever committed; rebuilding the
  branch bounds repo growth).

### (i) `astral-sh/setup-uv@v5` exists and supports `python-version` + `enable-cache` inputs — SPEC §11 (lines 940–943)

- **Final verdict: CONFIRMED for existence and inputs (live-fetched); v5 is **not**
  the current major — the current major is v10 (v10.0.1 latest, released 2026-08-14).**
- **Citations (fetched 2026-09-06):**
  - **Existence/inputs:** `https://raw.githubusercontent.com/astral-sh/setup-uv/v5/action.yml`
    fetched successfully — the `v5` tag resolves today. Its inputs include verbatim
    `python-version` (*"The version of Python to set UV_PYTHON to"*, matching the spec's
    `python-version: "3.12"`) and `enable-cache` (*"Enable uploading of the uv cache"*,
    default `"auto"`, matching the spec's `enable-cache: true`).
  - **Current major:** https://github.com/astral-sh/setup-uv/releases — latest release
    v10.0.1 (2026-08-14); majors v6, v7, v8, v9, v10 all shipped after v5.
- **New risk factor discovered:** since **v8.0.0** the project publishes only immutable
  exact-version tags (*"No more major and minor tags … You won't be able to use `@v8` or
  `@v8.0` any longer"*), citing supply-chain attacks. The historical `v5` tag still
  exists (live-verified) but is frozen and unmaintained, and runs on the `node20`
  runtime. It works today — the workflow as written in §11 would function — but it is
  five majors behind.
- **Recommendation:** at implementation time, replace `@v5` with an immutable pin per
  the action's own release strategy (e.g. `astral-sh/setup-uv@v10.0.1` or a commit
  SHA), re-checking that the inputs still exist (v10 changed `enable-cache: auto`
  semantics for `pull_request_target`/`workflow_run`/`release` events — irrelevant to
  this schedule/dispatch-only workflow, and the spec sets `true` explicitly).
- **Consequence of the claim as written:** none functional — `@v5` resolves and the two
  inputs exist, so §11's workflow is valid; the pin is merely stale.

### (j) `actions/checkout@v4` is the current major — SPEC §11 (line 938)

- **Final verdict: REFUTED** (live fetch, 2026-09-06).
- **Citation:** https://github.com/actions/checkout/releases — latest release
  **v7.0.1** (released 20 Jul 2026); the release list shows v7.0.x, v6.1.0, v5.1.0,
  v4.4.0 as concurrently-maintained majors. v7.0.0 shipped 18 Jun 2026 (changelog:
  "safer pull_request_target defaults for GitHub Actions checkout", linked from the
  v6/v5/v4 backport notes).
- **What this means for the spec:** cosmetic only. The `v4` major tag persists (it even
  received a backport patch, v4.4.0, on 2026-07-20), and `ubuntu-latest` runners still
  execute it, so §11's workflow runs unchanged. The breaking change in the v4.4.0/v5/v6
  backports concerns `pull_request_target` fork-checkout safety — this workflow uses
  only `schedule`/`workflow_dispatch`, so it is unaffected either way.
- **Recommendation:** bump `uses: actions/checkout@v4` to the current major (v7) at
  implementation time for future-proofing; do not treat "v4 is current" as a reason the
  workflow depends on v4 — it isn't, and now provably never was.

---

## Incidental findings (new this pass — not in the original 10 claims)

1. **Schedule timezone support (affects spec text):** both the events page and the
   workflow-syntax reference document an optional IANA `timezone` key on `schedule`
   entries. The spec's comments "GitHub does not honour timezones in cron" (§7 line 373,
   §11 line 914) are outdated as blanket statements; the cron *expression* still
   defaults to UTC, so the shipped config is correct, but the comment should be reworded.
2. **Dropped-run warning:** the schedule docs warn that under sufficiently high load
   *"some queued jobs may be dropped"* — stronger than the spec's lateness-only comments;
   worth a one-line mention in the §7/§11 comments since recovery is a manual re-run.
3. **Checkout v4 is alive but three majors stale** — see (j).
4. **setup-uv moved to immutable-only tags from v8** — see (i).

## Recommended follow-up (for the orchestrator)

1. **Spec text tweaks now backed by live citations (apply at next spec revision):**
   - §12.1 step 2 rationale (c): soften "Without this, the publish step gets a read-only
     token and fails" to belt-and-braces framing (the workflow's `permissions: contents:
     write` is the operative grant; the setting covers a future removal of that block).
   - §7/§11 comments (b): reword the "5–30 minutes" comment to the documented claim, add
     the dropped-run warning, and fix both "no timezone support" comments (see
     incidental finding 1).
   - §11 workflow pins (i)+(j): bump `actions/checkout@v4` → v7 and `setup-uv@v5` → an
     immutable v10 pin (re-verifying inputs), per the actions' own release-strategy docs.
2. **No design changes required:** (a), (d)–(h) all confirmed as the spec assumes;
   (f) in particular confirms the "Repo visibility: Public" settled decision is
   load-bearing, not merely conservative.
3. **Keep the post-deploy `curl -sI …/catalog.xml | grep -i content-type` check** in
   acceptance §14.3.8 — the claim is now docs-confirmed (see (d)), but the one-command
   live check on our own file is still the cheapest definitive proof at deploy time.
