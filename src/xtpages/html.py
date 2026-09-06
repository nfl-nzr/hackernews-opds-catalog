"""HTML shaping for a renderer that is much less capable than a browser.

The device recognizes a fixed, small set of tags, has no <pre> support at all,
and collapses every run of ASCII whitespace. See SPEC.md sections 8.3 and 8.3.1.
"""

from __future__ import annotations

import lxml.etree
import lxml.html
import nh3

NBSP = "\u00a0"

# Exactly what the device renders, minus the tags that add nothing to a digest
# (div, span, ins, strike, ruby, rt). See SPEC.md 8.3 and 12.3.
ALLOWED_TAGS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "blockquote",
    "em",
    "strong",
    "b",
    "i",
    "u",
    "del",
    "s",
    "a",
    "br",
    "hr",
    "table",
    "tr",
    "th",
    "td",
    "sub",
    "sup",
}


def _container(html: str) -> lxml.html.HtmlElement:
    """Parse into one element whose children are the content."""
    if not html or not html.strip():
        return lxml.html.fromstring("<div></div>")
    doc = lxml.html.fromstring(html)
    if doc.tag == "html":
        body = doc.find("body")
        if body is not None:
            return body
        return doc
    if doc.tag in ("body", "div", "span"):
        return doc
    holder = lxml.html.fromstring("<div></div>")
    holder.append(doc)
    return holder


def _serialize(container: lxml.html.HtmlElement) -> str:
    parts = [container.text or ""]
    parts += [lxml.html.tostring(child, encoding="unicode") for child in container]
    return "".join(parts).strip()


# Inside <pre>, these mark a line boundary. Syntax highlighters emit one <div>
# or <br> per line, and text_content() alone would run those lines together.
PRE_LINE_BREAKERS = {"br", "div", "p", "li", "tr"}


def _pre_text(pre) -> str:
    """Text of a <pre>, with nested line-level markup turned back into newlines."""
    parts: list[str] = []

    def newline() -> None:
        if parts and not parts[-1].endswith("\n"):
            parts.append("\n")

    def walk(element, root: bool = False) -> None:
        if not root and element.tag in PRE_LINE_BREAKERS:
            newline()
        if element.text:
            parts.append(element.text)
        for child in element:
            walk(child)
        if not root and element.tag in PRE_LINE_BREAKERS:
            newline()
        if element.tail:
            parts.append(element.tail)

    walk(pre, root=True)
    return "".join(parts)


def normalize_pre(html: str) -> str:
    """Rebuild newlines inside <pre>, on the source HTML, before readability runs.

    Syntax highlighters wrap every line in its own <div>. Extractors flatten that
    markup and join the lines, so by the time unwrap_pre() sees the block the line
    structure is already gone — the reconstruction has to happen first.
    """
    if "<pre" not in html.lower():
        return html
    try:
        doc = lxml.html.fromstring(html)
    except (ValueError, lxml.etree.ParserError):
        return html
    changed = False
    for pre in doc.xpath("//pre"):
        text = _pre_text(pre)
        if "\n" in text:
            for child in list(pre):
                pre.remove(child)
            pre.text = text
            changed = True
    return lxml.html.tostring(doc, encoding="unicode") if changed else html


def unwrap_pre(html: str) -> str:
    """Turn every <pre> into one <p class="code"> per source line.

    The device has no <pre> support and collapses ASCII whitespace, so a code
    block would otherwise arrive as one run-on paragraph. Leading indentation is
    re-encoded as U+00A0, which survives because the firmware's whitespace test
    is a byte-level check for ' ', '\\r', '\\n' and '\\t' — and U+00A0 encodes as
    0xC2 0xA0, matching neither byte.
    """
    if "<pre" not in html.lower():
        return html
    container = _container(html)
    for pre in container.xpath(".//pre"):
        lines = _pre_text(pre).expandtabs(4).split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        parent = pre.getparent()
        if parent is None:
            continue
        index = parent.index(pre)
        made = []
        for line in lines:
            body = line.rstrip()
            indent = len(body) - len(body.lstrip(" "))
            text = NBSP * indent + body.lstrip(" ")
            node = lxml.etree.Element("p")
            node.set("class", "code")
            node.text = text if text else NBSP
            made.append(node)
        for offset, node in enumerate(made):
            parent.insert(index + offset, node)
        if pre.tail and made:
            made[-1].tail = pre.tail
        parent.remove(pre)
    return _serialize(container)


def absolutize(html: str, base_url: str | None) -> str:
    """Resolve relative href/src against base_url.

    A safety net: trafilatura already absolutizes when passed url=.
    """
    if not base_url or not html.strip():
        return html
    container = _container(html)
    try:
        container.make_links_absolute(base_url, handle_failures="ignore")
    except ValueError:
        return html
    return _serialize(container)


def _strip_foreign_classes(html: str) -> str:
    """Keep only class="code", which we assign ourselves.

    nh3 filters attribute names, not values, so allowing class on <p> would also
    admit a source article's own class="meta" and let it inherit our stylesheet.
    """
    if "class=" not in html:
        return html
    container = _container(html)
    for element in container.xpath(".//*[@class]"):
        if element.get("class") != "code":
            del element.attrib["class"]
    return _serialize(container)


def sanitize(html: str, *, include_images: bool = False) -> str:
    """Reduce to the tag subset the device renders (SPEC 8.3)."""
    if not html or not html.strip():
        return ""
    tags = set(ALLOWED_TAGS)
    attributes = {"a": {"href"}, "p": {"class"}}
    if include_images:
        tags.add("img")
        attributes["img"] = {"src", "alt"}
    # link_rel=None: nh3 otherwise injects rel="noopener noreferrer", an
    # attribute outside our allowlist.
    cleaned = nh3.clean(html, tags=tags, attributes=attributes, link_rel=None)
    return _strip_foreign_classes(cleaned)


def text_length(html: str) -> int:
    """Length of the visible text, used for the 500-character extraction floor."""
    if not html or not html.strip():
        return 0
    return len(" ".join(_container(html).text_content().split()))


def truncate(html: str, max_chars: int) -> str:
    """Cut to max_chars and repair the markup, so a chapter never ends mid-tag."""
    if len(html) <= max_chars:
        return html
    return _serialize(_container(html[:max_chars]))


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
