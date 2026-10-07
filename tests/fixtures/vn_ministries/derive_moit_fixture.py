"""
How the derived-moit-*.html fixtures were made from captured moit.gov.vn bytes.

moit.gov.vn's reuse notice asks for written consent, which this project does
not have, so its pages are never committed as received. This rewrite keeps the
page's markup, scripts, links, identifiers, dates and every byte between them
exactly where they were, and replaces only prose:

  * every text node outside <script>/<style>, except the text of
    `span.post-date` and `span.article-date` and text made only of digits and
    date punctuation;
  * `alt` and `title` attribute values;
  * the `content` of the prose meta tags listed in PROSE_META.

A replaced string becomes `Văn bản thay thế <10 hex>`, where the hex is the
SHA-256 of the original after HTML unescaping and whitespace squashing, and its
leading and trailing whitespace is kept. So two strings that were equal stay
equal (a listing title and the page's own title still match) and two that
differed still differ, without the text itself surviving.

Usage: derive_moit_fixture.py CAPTURE.bin OUT.html
"""

import hashlib
import html
import re
import sys
from html.parser import HTMLParser

PROSE_META = frozenset((
    "description", "keywords", "title", "og:title", "og:description", "dc.title",
    "dc.description", "dc.creator", "dc.subject", "twitter:title", "twitter:description",
    "news_keywords",
))
KEEP_SPAN_CLASSES = frozenset(("post-date", "article-date"))
_DATELIKE = re.compile(r"^[\s\d/:|,.\-]*$")
_ATTR = re.compile(r"""(\s(?:alt|title)\s*=\s*)("[^"]*"|'[^']*')""", re.IGNORECASE)
_CONTENT = re.compile(r"""(\scontent\s*=\s*)("[^"]*"|'[^']*')""", re.IGNORECASE)


def placeholder(original: str) -> str:
    key = " ".join(html.unescape(original).split())
    if not key:
        return original
    lead = original[:len(original) - len(original.lstrip())]
    trail = original[len(original.rstrip()):]
    return "%sVăn bản thay thế %s%s" % (
        lead, hashlib.sha256(key.encode("utf-8")).hexdigest()[:10], trail)


def _swap_value(match) -> str:
    quoted = match.group(2)
    return match.group(1) + quoted[0] + placeholder(quoted[1:-1]) + quoted[0]


class _Rewriter(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.text = text
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
        self.events = []            # (offset, kind, payload)
        self.keep_depth = 0
        self.cdata = None

    def _offset(self) -> int:
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text()
        new = _ATTR.sub(_swap_value, raw)
        if tag == "meta":
            names = {(v or "").lower() for k, v in attrs if k in ("name", "property")}
            if names & PROSE_META:
                new = _CONTENT.sub(_swap_value, new)
        self.events.append((self._offset(), "tag", (raw, new)))
        classes = set((dict(attrs).get("class") or "").split())
        if tag == "span" and (classes & KEEP_SPAN_CLASSES or self.keep_depth):
            self.keep_depth += 1
        if tag in ("script", "style"):
            self.cdata = tag

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        self.events.append((self._offset(), "mark", None))
        if tag == "span" and self.keep_depth:
            self.keep_depth -= 1
        if tag == self.cdata:
            self.cdata = None

    def handle_data(self, data):
        keep = self.cdata is not None or self.keep_depth or _DATELIKE.match(data)
        self.events.append((self._offset(), "keep" if keep else "data", None))

    def _mark(self, *_):
        self.events.append((self._offset(), "mark", None))

    handle_comment = handle_decl = handle_pi = unknown_decl = _mark


def derive(text: str) -> str:
    parser = _Rewriter(text)
    parser.feed(text)
    parser.close()
    events = parser.events + [(len(text), "mark", None)]
    out, cursor = [], 0
    for (offset, kind, payload), (end, _, _) in zip(events, events[1:]):
        assert offset >= cursor, "parser offsets went backwards"
        out.append(text[cursor:offset])
        chunk = text[offset:end]
        if kind == "tag":
            raw, new = payload
            assert chunk.startswith(raw)
            chunk = new + chunk[len(raw):]
        elif kind == "data":
            chunk = placeholder(chunk)
        out.append(chunk)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


if __name__ == "__main__":
    source, target = sys.argv[1], sys.argv[2]
    with open(source, "rb") as fh:
        captured = fh.read().decode("utf-8")
    with open(target, "wb") as fh:
        fh.write(derive(captured).encode("utf-8"))
