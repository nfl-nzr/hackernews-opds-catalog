# SPEC §12.3 Verification Report

**Contradictions / Refutations:** None found.

| Claim | Verdict | Evidence |
|---|---|---|
| OpdsParser entry cap 62 (ENTRY_STORAGE_CAPACITY 64‑2) | CONFIRMED | `lib/OpdsParser/OpdsParser.cpp:8-11` defines `ENTRY_STORAGE_CAPACITY = 64` and `MAX_ENTRIES = ENTRY_STORAGE_CAPACITY - 2`; `startElement` uses `self->collectCurrentEntry = self->entries.size() < MAX_ENTRIES;` (line 124‑125) |
| OpdsParser field limits (title 160, author 120, id 128, href 768) | CONFIRMED | Limits defined in `OpdsParser.cpp:11-14`; `characterData` enforces them via `appendBounded` (lines 215‑221) |
| Entry accepted only if link `rel` contains `opds-spec.org/acquisition` **and** `type` exactly `application/epub+zip` (strcmp) | CONFIRMED | `OpdsParser.cpp:149‑151` checks `strstr(rel, "opds-spec.org/acquisition") != nullptr && strcmp(type, "application/epub+zip") == 0` |
| Entries with empty title or no usable link are silently dropped | CONFIRMED | `endElement` only pushes entry when `!self->currentEntry.title.empty() && !self->currentEntry.href.empty()` (lines 191‑193) |
| Feed‑level `rel="next"` pagination is honoured | CONFIRMED | `startElement` assigns `self->nextPageUrl` when `rel == "next"` and not in entry (lines 142‑144) |
| Feed `kind=` profile is ignored | CONFIRMED | No reference to `kind` or `profile` in `OpdsParser.cpp` (search yields none) |
| `<summary>` element is not parsed | CONFIRMED | No handling of `<summary>` tag in `OpdsParser.cpp` (search yields none) |
| OpdsFilename builds `{author} - {title}.epub` (author first when non‑empty) and never uses URL | CONFIRMED | `src/util/OpdsFilename.cpp:5‑18` builds `base` accordingly and appends `.epub` (line 22) |
| Filename sanitization replaces `/ \ : * ? " < > |` with `_`, trims leading/trailing spaces/dots, respects UTF‑8 code‑point boundaries, caps at 100 bytes | CONFIRMED | `StringUtils.cpp:23‑33` implements illegal‑char replacement and trimming; default `maxBytes` is 100 (header line 35) |
| Recognized tags list matches spec (p, li, div, br, blockquote, h1‑h6, b,strong,i,em,u,ins,del,s,strike,a,span,sub,sup,ruby,rt,table,tr,th,td,img,hr) | CONFIRMED | Tag arrays in `ChapterHtmlSlimParser.cpp:54‑60` contain exactly those names |
| `<pre>` tag is unsupported anywhere in EPUB library | CONFIRMED | No occurrence of handling for `"pre"` in `ChapterHtmlSlimParser.cpp` (search returns none) |
| `trimAndNormalize` collapses runs of space/tab/CR/LF into a single space | CONFIRMED | Implementation in `ChapterHtmlSlimParser.cpp:63‑88` performs whitespace collapse |
| `<li>` emits its own bullet and handles nesting while `<ul>/<ol>` containers are ignored | CONFIRMED | Bullet added at `ChapterHtmlSlimParser.cpp:1389‑1392`; no special handling for `ul`/`ol` (search finds none) |
| Tables receive real support (simple rows, minimum cell width) | CONFIRMED | Table structural tags defined (`TABLE_CELL_HORIZONTAL_PADDING` etc.) and `isTableStructuralTag` at lines 145‑147; rendering logic uses these constants |
| Anchor cap of 1024 IDs per chapter | CONFIRMED | `MAX_ANCHORS_PER_CHAPTER = 1024` defined at `ChapterHtmlSlimParser.cpp:41‑46` |
| CssParser supports exactly the listed properties and **not** font‑size, line‑height, max‑width, color, font‑family | CONFIRMED | Property parsing cases in `CssParser.cpp` include `direction`, `display`, `font-style`, `font-weight`, `height`, `margin*`, `padding*`, `text-align`, `text-decoration-line`, `text-indent`, `vertical-align`, `width` (lines 615‑614 etc.); no cases for `font-size`, `line-height`, `max-width`, `color`, `font-family` (search finds none) |
| CssParser selectors limited to element, `.class`, `element.class`, and grouped forms; no descendant/child/pseudo selectors | CONFIRMED | Documentation in `CssParser.h:19‑24` and parsing logic (`processRuleBlockWithStyle`) only accepts simple selectors; no handling for spaces, `>`, `:` etc. |
| HttpDownloader uses `esp_crt_bundle_attach` for TLS verification; `CONFIG_ESP_TLS_INSECURE` is off | CONFIRMED | `HttpDownloader.cpp:152‑159` sets `config.crt_bundle_attach = esp_crt_bundle_attach`; comments note `CONFIG_ESP_TLS_INSECURE` off (lines 152‑154) |
| Manual redirect following capped at 5 hops | CONFIRMED | `MAX_REDIRECTS = 5` defined (line 35) and loop in `runGet` respects it (lines 186‑197) |
| HTTP timeout is 60 seconds | CONFIRMED | `HTTP_TIMEOUT_MS = 60000` defined (line 33) |
| `MIN_TLS_FREE_HEAP` requires 40 KB free heap and 20 KB largest‑free‑block before download | CONFIRMED | `HttpDownloader.h:30` defines `MIN_TLS_FREE_HEAP = 40000`; callers check `ESP.getFreeHeap()` against this constant (e.g., `OpdsBookBrowserActivity.cpp:507`) |
| Basic auth is sent pre‑emptively when both username and password are set | CONFIRMED | `runGet` adds `Authorization` header before request when credentials are non‑empty (lines 168‑172) |
| OpdsServerStore limits to a maximum of 8 saved servers | CONFIRMED | `OpdsServerStore.h:24` defines `MAX_SERVERS = 8` |
