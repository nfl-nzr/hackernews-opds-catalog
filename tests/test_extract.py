from conftest import fixture, html_response, make_client
from xtpages import extract, html
from xtpages.models import Status, Story


def fetch(cfg, story, body, **kw):
    return extract.fetch_article(cfg, story, make_client(html_response(body, **kw)))


def test_clean_article_extracts(cfg, story):
    article = fetch(cfg, story, fixture("article_clean.html"))
    assert article.status is Status.OK
    assert article.chars > 500
    assert "The Clean Title" in article.body_html or "substantive paragraph" in article.body_html


def test_messy_article_drops_chrome(cfg, story):
    article = fetch(cfg, story, fixture("article_messy.html"))
    assert article.status is Status.OK
    assert "SIDEBARJUNK" not in article.body_html
    assert "FOOTERJUNK" not in article.body_html
    assert "Subscribe Login" not in article.body_html


def test_paywall_hits_the_character_floor(cfg, story):
    article = fetch(cfg, story, fixture("article_paywall.html"))
    assert article.status is Status.EXTRACTION_FAILED
    assert "500" in article.error


def test_non_html_content_type(cfg, story):
    article = fetch(cfg, story, "%PDF-1.4", ctype="application/pdf")
    assert article.status is Status.NON_HTML


def test_http_error_is_a_status_not_an_exception(cfg, story):
    article = fetch(cfg, story, "nope", status=404)
    assert article.status is Status.FETCH_ERROR
    assert "404" in article.error


def test_skip_domains(cfg, story):
    cfg.content.skip_domains = ["example.com"]
    article = extract.fetch_article(cfg, story)
    assert article.status is Status.SKIPPED_DOMAIN


def test_skip_domains_matches_subdomain(cfg):
    cfg.content.skip_domains = ["example.com"]
    story = Story(1, "t", "https://www.example.com/x", 10, "u", 0)
    assert extract.fetch_article(cfg, story).status is Status.SKIPPED_DOMAIN


def test_relative_links_absolutized(cfg, story):
    article = fetch(cfg, story, fixture("article_clean.html"))
    assert "/relative-link" not in article.body_html.replace(
        "https://example.com/relative-link", ""
    )


def test_self_post_goes_through_unwrap(cfg):
    story = Story(2, "Ask HN", None, 100, "u", 0, text="<p>x</p><pre>def f():\n    return 1</pre>")
    article = extract.fetch_article(cfg, story)
    assert article.status is Status.SELF_POST
    assert "<pre" not in article.body_html
    assert 'class="code"' in article.body_html


# --- html.py -----------------------------------------------------------------


def test_unwrap_pre_one_paragraph_per_line():
    out = html.unwrap_pre("<pre>a\nb\nc</pre>")
    assert out.count('<p class="code">') == 3


def test_unwrap_pre_leading_spaces_become_nbsp():
    out = html.unwrap_pre("<pre>def f():\n    return 1</pre>")
    assert html.NBSP * 4 + "return 1" in out
    assert " return" in out


def test_unwrap_pre_leaves_interior_spaces_as_ascii():
    out = html.unwrap_pre("<pre>    a b c</pre>")
    assert "a b c" in out  # interior single spaces untouched


def test_unwrap_pre_preserves_blank_lines():
    out = html.unwrap_pre("<pre>a\n\nb</pre>")
    assert out.count('<p class="code">') == 3
    assert html.NBSP in out


def test_unwrap_pre_expands_tabs_to_four():
    out = html.unwrap_pre("<pre>\tx</pre>")
    assert html.NBSP * 4 + "x" in out


def test_unwrap_pre_noop_without_pre():
    assert html.unwrap_pre("<p>a</p>") == "<p>a</p>"


def test_no_pre_survives_sanitizing():
    assert "<pre" not in html.sanitize("<pre>code</pre>")


def test_sanitizer_strips_script_style_and_handlers():
    dirty = '<p onclick="x()">a</p><script>1</script><style>b{}</style>'
    clean = html.sanitize(dirty)
    assert "script" not in clean and "style" not in clean and "onclick" not in clean


def test_sanitizer_keeps_only_class_code():
    assert html.sanitize('<p class="code">a</p>') == '<p class="code">a</p>'
    assert html.sanitize('<p class="meta">a</p>') == "<p>a</p>"


def test_sanitizer_does_not_inject_rel():
    assert "rel=" not in html.sanitize('<a href="https://e.com">l</a>')


def test_disallowed_tag_keeps_its_text():
    assert "kept" in html.sanitize("<div><span>kept</span></div>")


def test_unwrap_pre_respects_br_line_breaks():
    out = html.unwrap_pre("<pre>a<br/>b<br/>c</pre>")
    assert out.count('<p class="code">') == 3


def test_unwrap_pre_respects_highlighter_line_divs():
    """Syntax highlighters emit one div per line; text_content alone runs them together."""
    out = html.unwrap_pre(
        "<pre><div><span>const a = 1;</span></div><div><span>const b = 2;</span></div></pre>"
    )
    assert out.count('<p class="code">') == 2
    assert "const a = 1;const b = 2;" not in out


def test_unwrap_pre_highlighter_spans_within_a_line_stay_joined():
    out = html.unwrap_pre("<pre><div><span>if</span> <span>(x)</span></div></pre>")
    assert out.count('<p class="code">') == 1
    assert "if (x)" in out


def test_normalize_pre_rebuilds_highlighter_newlines():
    """The real-world case: one <div> per line inside <pre>, as Prism emits."""
    source = (
        '<html><body><pre class="prism"><code>'
        '<div class="token-line"><span>const a = 1;</span></div>'
        '<div class="token-line"><span>const b = 2;</span></div>'
        "</code></pre></body></html>"
    )
    out = html.normalize_pre(source)
    assert "const a = 1;\nconst b = 2;" in out


def test_normalize_pre_is_a_noop_without_pre():
    assert html.normalize_pre("<p>a</p>") == "<p>a</p>"


def test_normalize_pre_leaves_already_plain_blocks_alone():
    source = "<pre>a\nb</pre>"
    assert "a\nb" in html.normalize_pre(source)
