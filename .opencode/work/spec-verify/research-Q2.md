# S2 — Python library API verification (`research-Q2.md`)

Spec sections checked: §5 (lines 190–224), §8.2 (lines 459–491), §8.3 (lines 496–561), §14.1 (line 1138), §16 (line 1220).
Date: 2026-09-06.

## Method and evidence tiers (read first)

**Environment constraint:** in this subagent run the `iem-research` MCP tools
(`search` / `fetch` / `cache_grep` / `cache_stats`) are not wired into the toolset, and
there is no `bash` tool, so (1) no live web fetch and (2) no local `uv` smoke test were
possible. Evidence actually used, in decreasing strength:

- **E1 — installed package source on disk** (strongest available; equivalent to reading
  the released wheel). Found for exactly one package: **httpx 0.28.1**, unpacked in the
  uv cache at `/Users/nflnzr/.cache/uv/archive-v0/LpHeL38vaMhtHzHKDP6tq/lib/python3.13/site-packages/httpx/` (three further identical-version copies exist under other archive hashes). All
  `file:line` citations below are to that copy, which corresponds line-for-line to the
  0.28.1 sdist on GitHub (`github.com/encode/httpx`, tag `0.28.1`).
- **E2 — training knowledge of the library**, clearly labeled, **not** a citation. Must
  be re-verified empirically before implementation. Per the brief's ground rules these
  are marked `NOT FOUND (locally)` rather than `CONFIRMED`.

**Searches performed for the other packages (all negative):** uv cache `archive-v0/`,
`sdists-v9/`, `wheels-v5/pypi/` (440 cached packages, no trafilatura/ebooklib/nh3),
`simple-v16/` index, `environments-v2/`, `~/.local/lib`, `~/Documents/**/.venv`,
`~/research`, `/opt`, `/Library/Frameworks/Python.framework`, brew python site-packages,
`~/.cache` (no fetch cache present). Conclusion: those three packages have never been
installed on this machine, and no cached web pages exist.

**Verdict vocabulary:** `CONFIRMED` / `REFUTED` / `NOT FOUND` / `UNVERIFIABLE`, per the brief.

---

## (a) `trafilatura.extract()` accepts exactly the §8.2 kwargs

**Claim (SPEC.md:472–483):** `extract()` accepts `output_format="html"`,
`include_comments=False`, `include_tables=True`, `include_images=<bool>`,
`include_links=True`, `favor_precision=True`, `url=story.url`.

**Verdict: `NOT FOUND (locally)` — knowledge-based assessment: likely CONFIRMED, but the
spec itself (§5 line 222–224, §16 line 1220) demands empirical verification at the
resolved version, and a local `uv` smoke test is the definitive check.**

Evidence tier: E2 (training knowledge, trafilatura 1.x→2.x API history).

Knowledge-based detail, to be re-verified:

- All seven kwargs are long-standing first-class parameters of
  `trafilatura.extract(filecontent, ...)` and none of them was renamed in the 1.x→2.x
  transition to my knowledge. The parameters that **were** deprecated/renamed around
  2.0 are ones the spec does **not** use: `no_fallback` (→ `favor_recall` / settings),
  `with_metadata` / `only_with_metadata` (→ settings), `settingsfile` (→ `config`).
  So the spec's choice of kwargs happens to avoid every known rename trap.
- `output_format="html"` is a valid value in the 2.x line (valid set includes
  `txt`, `markdown`, `csv`, `json`, `jsonl`, `xml`, `xmltei`, `html`); an invalid value
  does not raise but logs and yields `None`-ish behavior, so the smoke test must assert
  on the *result*, not on exceptions.
- Default values of `include_images` (False) and `include_links` (False) differ from the
  spec's call — irrelevant since §8.2 passes them explicitly, but implementers must not
  "simplify" by dropping kwargs.
- First positional parameter is `filecontent` (str or bytes); `url=` additionally
  enables relative-URL resolution, matching the spec's comment.

**Definitive check (run from the throwaway dir):**

```bash
cd /var/folders/ht/ywhzbt5n02z_k8kwgj1h8vnm0000gn/T/opencode && uv run --with 'trafilatura>=2.2' python - <<'EOF'
import inspect, trafilatura
print("version:", trafilatura.__version__)
sig = inspect.signature(trafilatura.extract)
print(sig)
for kw in ("output_format","include_comments","include_tables","include_images",
           "include_links","favor_precision","url"):
    assert kw in sig.parameters, f"MISSING: {kw}"
html = "<html><body><article><h1>T</h1><p>" + "word "*600 + "</p></article></body></html>"
out = trafilatura.extract(html, output_format="html", include_comments=False,
                          include_tables=True, include_images=False,
                          include_links=True, favor_precision=True,
                          url="https://example.com/a")
print("extract ok, len:", len(out or ""), "has h1:", "<h1" in (out or ""))
EOF
```

Acceptance: the assert loop passes (all 7 kwargs accepted) and `extract ok` shows non-None
HTML output. Any `TypeError: unexpected keyword argument` refutes (a).

---

## (b) httpx: redirect cap + streaming abort past a byte cap

**Claim (SPEC.md:463–466):** GET with `follow_redirects=True`, max 5 redirects; stream
and abort past `fetch.max_bytes`; per-request timeout.

**Verdict: CONFIRMED** — evidence tier **E1**, httpx **0.28.1** installed source (exact
floor version of the spec's `httpx>=0.28`):

- `BaseClient.__init__` accepts `timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG`,
  `follow_redirects: bool = False`, `max_redirects: int = DEFAULT_MAX_REDIRECTS`
  (`_client.py:189–203`, stored at `:212–214`). Also accepted per-request on
  `client.get(...)` / `client.send(...)` (`_client.py:784+`).
- `DEFAULT_MAX_REDIRECTS = 20` (`_config.py:248`), so `max_redirects=5` *tightens* the
  default — the spec's "max 5 redirects" is directly expressible.
- The redirect loop raises `httpx.TooManyRedirects` when
  `len(history) > self.max_redirects` (`_client.py:971–972`; async twin `:1686–1687`);
  exported at top level (`httpx/__init__.py:91`, class at `_exceptions.py:249`,
  subclass of `RequestError`). Note: it fires on the *6th* redirect response (5 followed,
  then the count check trips), which matches "max 5 redirects".
  `TooManyRedirects` only occurs when `follow_redirects=True`; with it off you simply get
  the 3xx response — the spec's pairing of both settings is the correct one.
- Streaming: `Response.iter_bytes(chunk_size)` is a lazy generator that decodes
  gzip/deflate/brotli/zstd **per chunk** and yields incrementally (`_models.py:884–905`);
  `Response.iter_raw(chunk_size)` is the raw lazy generator (`:935–959`) that maintains
  `response.num_bytes_downloaded` (property, `:856`; updated per chunk at `:947,:952`).
  Neither pre-buffers the body (only `response.read()` does, `:876–882`). A loop like

  ```python
  total = 0
  for chunk in resp.iter_bytes(65536):
      total += len(chunk)
      if total > max_bytes:
          resp.close()   # _models.py:961–972 closes the stream, releases the connection
          raise FetchTooLarge
      buf.append(chunk)
  ```

  aborts the download mid-body. `Content-Length` pre-check is additionally possible via
  `resp.headers`.
- Nuance worth carrying into the spec: httpx timeouts are **per operation**
  (connect/read/write/pool), not a total deadline — default total guard is
  `Timeout(timeout=5.0)` (`_config.py:246`) per operation. A slow-drip body can stretch
  wall-clock time arbitrarily while never exceeding the read timeout; the byte cap bounds
  size but not duration. If §8.2's `timeout_seconds` is meant as a total fetch budget,
  the chunk loop needs an explicit `time.monotonic()` deadline check. (Not refuting the
  spec — its text is silent on total-vs-per-op semantics; S4 may want to pin this down.)

---

## (c) nh3 ≥ 0.2: `clean()` / `Cleaner` with tag + attribute allowlists

**Claim (SPEC.md:545–550):** sanitize via nh3 allowing tags `p h1–h6 ul ol li blockquote
em strong b i u del s a br hr table tr th td sub sup` (+ `img` conditionally), with
attributes `href` on `a`, `src`/`alt` on `img` — i.e. per-tag attribute allowlists.

**Verdict: `NOT FOUND (locally)` — knowledge-based assessment: CONFIRMED with high
confidence; smoke test below is definitive.** Evidence tier: E2.

Knowledge-based detail, to be re-verified:

- `nh3.clean(html, *, tags: set[str] | None, clean_content_tags, attributes:
  dict[str, set[str]] | None, attribute_filter, strip_comments: bool = True, link_rel:
  str | None = "noopener noreferrer", url_schemes, url_relative,
  generic_attribute_prefixes, tag_attribute_values, allowed_classes)` — `attributes` is
  **exactly the per-tag shape the spec wants**: `{"a": {"href"}, "img": {"src", "alt"}}`.
  `tags` is a flat set allowlist, matching §8.3's tag list verbatim; dropping `img` when
  `include_images` is false is just set membership.
- `nh3.Cleaner(**same kwargs)` exists since 0.2.0 and lets you build the ammonia config
  once — relevant because §8.3's `sanitize()` runs per chapter; a module-level
  `Cleaner` avoids rebuilding the sanitizer per call.
- Two default-behavior notes for the spec (not refutations):
  1. `link_rel` defaults to `"noopener noreferrer"`, so output `<a>` tags gain a `rel`
     attribute not in the spec's allowlist. Harmless for the device parser (unknown
     attributes are ignored per §12.3) but set `link_rel=None` if byte-exact output
     matters.
  2. Ammonia's default URL schemes exclude `data:`; image `src` with data URIs will be
     stripped. HN-linked articles occasionally use them; acceptable, but worth knowing.

**Definitive check:**

```bash
cd /var/folders/ht/ywhzbt5n02z_k8kwgj1h8vnm0000gn/T/opencode && uv run --with 'nh3>=0.2' python - <<'EOF'
import inspect, nh3
print("version:", nh3.__version__)
print("clean:", inspect.signature(nh3.clean))
print("Cleaner:", hasattr(nh3, "Cleaner"))
out = nh3.clean('<p onclick="x" style="y">hi <a href="/x">l</a><img src="s.jpg" alt="a"><script>bad()</script></p>',
                tags={"p","a","img"},
                attributes={"a": {"href"}, "img": {"src","alt"}})
print(out)
assert "onclick" not in out and "script" not in out and 'href="/x"' in out and 'src="s.jpg"' in out
EOF
```

---

## (d) ebooklib ≥ 0.20: mimetype-first STORED entry + nav.xhtml + toc.ncx by default

**Claim (SPEC.md:502–504, 1082, 1138):** EPUB 3 with NCX included, "which is what
`ebooklib` does by default"; §14.1 asserts the zip's first entry is `mimetype` stored
uncompressed and both `toc.ncx` and `nav.xhtml` exist.

**Verdict: SPLIT — `NOT FOUND (locally)` for both halves; knowledge-based:**

- **(d1) `mimetype` as first, STORED zip entry: likely CONFIRMED (high confidence).**
  `EpubWriter.write()` writes `mimetype` (`application/epub+zip`, no newline) with
  `compress_type=zipfile.ZIP_STORED` as the very first `writestr` on the fresh
  `ZipFile` — this is the OCF requirement and ebooklib has gotten it right across
  0.17→0.18+ to my knowledge. Low residual risk.
- **(d2) both `nav.xhtml` and `toc.ncx` generated *by default*: UNRELIABLE AS STATED —
  this is the highest-risk sub-claim in (d).** The canonical ebooklib usage in its own
  docs/README always **explicitly adds** both items:
  ```python
  book.add_item(epub.EpubNcx())
  book.add_item(epub.EpubNav())
  ```
  My recollection of the writer is that `_write_ncx()` / `_write_nav()` serialize the
  `EpubNcx`/`EpubNav` **items found in `book.get_items()`**; whether the writer silently
  fabricates them when the user forgot, or skips them, I cannot vouch for at any version.
  Community threads report missing-NAV EPUBs when the items were not added, which
  suggests **the writer does not reliably auto-generate them** — i.e. the spec's "which
  is what `ebooklib` does by default" may be wrong as a causal claim (right outcome,
  wrong reason: you get both because you add both, one line each). Either way the
  practical fix is identical and trivial: unconditionally
  `book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav())`.
  Related unverified default: whether `EpubBook()` defaults to `version="3.0"` (EPUB 3
  packaging) or needs `book.set_version(...)` — print it in the smoke test.
- A local `uv` smoke test is the definitive check for both halves; run **both** variants
  (items added / not added) so the "default" question is settled directly:

```bash
cd /var/folders/ht/ywhzbt5n02z_k8kwgj1h8vnm0000gn/T/opencode && uv run --with 'ebooklib>=0.20' python - <<'EOF'
import zipfile, ebooklib
from ebooklib import epub
print("version:", ebooklib.VERSION)

def build(add_nav):
    b = epub.EpubBook()
    b.set_identifier("urn:xtpages:issue:test"); b.set_title("T"); b.set_language("en")
    c = epub.EpubHtml(title="C1", file_name="ch001.xhtml"); c.content = "<h1>x</h1><p>y</p>"
    b.add_item(c); b.toc = (epub.Link("ch001.xhtml","C1","ch001"),)
    if add_nav:
        b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav())
    epub.write_epub(f"t{add_nav}.epub", b)
    z = zipfile.ZipFile(f"t{add_nav}.epub")
    names = z.namelist()
    first = z.infolist()[0]
    print(f"add_nav={add_nav}: first={first.filename!r} stored={first.compress_type==zipfile.ZIP_STORED}",
          "nav:", any(n.endswith("nav.xhtml") for n in names), "ncx:", "toc.ncx" in names)
    opf = z.read([n for n in names if n.endswith(".opf")][0]).decode()
    print("  package version attr:", opf.split('version="')[1].split('"')[0])

build(False)  # does ebooklib DEFAULT to nav+ncx?
build(True)
EOF
```

- Acceptance: `add_nav=False` row shows first=`'mimetype'`, `stored=True`, `nav: True`,
  `ncx: True` → spec's "by default" CONFIRMED. If `nav: False`/`ncx: False`, the spec
  sentence at line 502–504 needs rewording (and §14.1's test stays valid only if the
  implementation adds the items — make that explicit in §8.3).

---

## (e) trafilatura ≥ 2.2 exists and is current on PyPI

**Claim (SPEC.md:201, 1220):** pin `trafilatura>=2.2`.

**Verdict: `NOT FOUND (locally)` — unverifiable without network; no cached copy exists
on this machine.** Evidence tier: E2 only.

- Knowledge-based: the 2.x line has been the current major series since mid-2024
  (2.0.0 released June 2024, breaking changes vs 1.x as described under (a)); I cannot
  pin from memory whether the series has reached ≥ 2.2 or what the latest patch is as of
  2026-09. Nothing I found locally contradicts the claim; nothing confirms it.
- The pin's resolver *is* the check — the command below fails loudly if no ≥2.2 release
  exists, and its output doubles as evidence for (a)'s exact-version signature check:

```bash
cd /var/folders/ht/ywhzbt5n02z_k8kwgj1h8vnm0000gn/T/opencode && uv run --with 'trafilatura>=2.2' python -c "import trafilatura; print(trafilatura.__version__)"
```

- Web sources to consult if run manually: `https://pypi.org/project/trafilatura/`
  (latest version + release date) and the changelog
  `https://github.com/adbar/trafilatura/blob/master/CHANGELOG.md` (2.x series history).

---

## Summary table

| # | Claim | Verdict | Evidence | Residual risk |
|---|---|---|---|---|
| (a) | trafilatura.extract() accepts the 7 §8.2 kwargs; "html" valid output_format | NOT FOUND locally; knowledge: likely CONFIRMED | E2 + smoke cmd | Low-medium; settles in <1 min with uv |
| (b) | httpx follow_redirects + max_redirects=5 + streaming byte-cap abort | **CONFIRMED** | E1: httpx 0.28.1 source, file:line cited | None for API; spec silent on total-time deadline (per-op timeouts) |
| (c) | nh3 ≥0.2 clean/Cleaner, tags + per-tag attributes | NOT FOUND locally; knowledge: CONFIRMED (high conf.) | E2 + smoke cmd | Low; note link_rel default adds rel attr |
| (d1) | mimetype first, STORED | NOT FOUND locally; knowledge: CONFIRMED (high conf.) | E2 + smoke cmd | Low |
| (d2) | nav.xhtml + toc.ncx **by default** | NOT FOUND locally; knowledge: **doubtful as stated** — may require explicit `add_item(EpubNcx/EpubNav)` | E2 + smoke cmd (both variants) | **Medium — verify before writing epub.py** |
| (e) | trafilatura ≥ 2.2 current on PyPI | NOT FOUND locally; UNVERIFIABLE offline | resolver cmd | Low; resolver fails loudly |

## Recommended approach for the orchestrator

1. Treat (b) as settled (installed-source evidence at the exact floor version).
2. Run the four smoke-test snippets above (they are self-contained; each prints version +
   acceptance assertions) — total cost ~1 minute; they settle (a), (c), (d), (e) at the
   versions uv actually resolves, which is precisely what SPEC.md §5 (lines 222–224)
   requires before implementation.
3. If (d2) comes back "not default", amend SPEC.md §8.3 (line 502–504) to state that
   `epub.py` explicitly adds `EpubNcx` + `EpubNav` (and consider `book.set_version` per
   the printed package version), keeping §14.1's assertions unchanged.
4. S4 follow-ups surfaced here: (i) total-time deadline vs per-op httpx timeouts for the
   §8.2 fetch loop; (ii) nh3 `link_rel` default injecting `rel` attributes outside the
   §8.3 allowlist description.
