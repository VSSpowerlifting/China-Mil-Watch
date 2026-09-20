"""
Singapore MINDEF extraction: HTML entity decoding, and the charset the
ministry does not declare.

Two defects live in the same data path and are easy to confuse, so they are
tested apart:

  * `&#x27;` — the ministry's CMS emits the *hexadecimal* spelling of the
    apostrophe. `visible_text()` used to carry a hand-written table of six
    entities that knew only `&#39;`, so 84 literal `&#x27;` sequences survived
    into the bodies of 29 of the 59 shadow records, and four titles kept
    `&#x27;`, `&quot;` or `&amp;` because the `og:title` branch decoded nothing
    at all.

  * the charset — mindef.gov.sg serves `Content-Type: text/html` with no
    charset parameter. RFC 2616 tells `requests` to fall back to ISO-8859-1
    for `text/*`, so `response.text` mis-decodes every non-ASCII byte even
    though the page's own `<meta charset>` says UTF-8. That is a *separate*
    defect from entity decoding and no amount of unescaping repairs it.

The fixtures are trimmed recordings of real pages, kept as bytes, because a
`str` fixture would silently erase the second defect.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scraper.sources import sg_mindef as sg                     # noqa: E402

FIX = REPO_ROOT / "tests" / "fixtures" / "sg_mindef"
CURLY = "’"
MOJIBAKE = CURLY.encode("utf-8").decode("latin-1")


def recorded(name: str) -> bytes:
    return (FIX / name).read_bytes()


def as_utf8(name: str) -> str:
    return recorded(name).decode("utf-8")


class HexApostropheIsDecoded(unittest.TestCase):
    """The defect that put 84 `&#x27;` into the corpus."""

    def test_the_fixture_really_carries_the_defect(self):
        # Guard the evidence: if a re-recording loses the entity, every test
        # below would pass vacuously.
        raw = recorded("entity_hex_apostrophe.html")
        self.assertGreater(raw.count(b"&#x27;"), 0)

    def test_hex_apostrophe_is_decoded_in_a_body(self):
        body = sg.document_body(as_utf8("entity_hex_apostrophe.html"))
        self.assertNotIn("&#x27;", body)
        self.assertIn("'", body)

    def test_hex_apostrophe_is_decoded_in_the_second_recording(self):
        body = sg.document_body(as_utf8("entity_body_apostrophes.html"))
        self.assertNotIn("&#x27;", body)

    def test_no_undecoded_entity_token_survives_either_recording(self):
        token = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
        for name in ("entity_hex_apostrophe.html", "entity_body_apostrophes.html"):
            with self.subTest(name):
                self.assertIsNone(token.search(sg.document_body(as_utf8(name))))

    def test_both_spellings_of_the_apostrophe_agree(self):
        self.assertEqual(sg.visible_text("<p>it&#x27;s</p>"), "it's")
        self.assertEqual(sg.visible_text("<p>it&#39;s</p>"), "it's")
        self.assertEqual(sg.visible_text("<p>it&#X27;s</p>"), "it's")

    def test_named_and_numeric_entities_generally(self):
        # `&nbsp;` is the odd one out: it decodes to U+00A0, which the final
        # whitespace collapse flattens to an ordinary space — the same text
        # the old six-entity table produced.
        cases = [("&rsquo;", CURLY), ("&mdash;", "—"), ("&quot;", '"'),
                 ("&nbsp;", " "), ("&#8217;", CURLY), ("&#x2019;", CURLY),
                 ("&lt;", "<"), ("&gt;", ">")]
        for ent, want in cases:
            with self.subTest(ent):
                got = sg.visible_text("<p>a" + ent + "b</p>")
                self.assertEqual(got, "a" + want + "b")


class DecodingHappensExactlyOnce(unittest.TestCase):
    """The old table decoded `&amp;` first and then re-read its own output."""

    def test_an_escaped_entity_stays_text(self):
        # A page that wants to *show* the characters "&#39;" writes "&amp;#39;".
        # One pass yields "&#39;". The old table yielded "'".
        self.assertEqual(sg.visible_text("<p>&amp;#39;</p>"), "&#39;")
        self.assertEqual(sg.visible_text("<p>&amp;#x27;</p>"), "&#x27;")

    def test_an_escaped_ampersand_stays_one_ampersand(self):
        self.assertEqual(sg.visible_text("<p>&amp;amp;</p>"), "&amp;")

    def test_a_bare_ampersand_is_preserved(self):
        self.assertEqual(sg.visible_text("<p>R&D spending</p>"), "R&D spending")
        self.assertEqual(sg.visible_text("<p>50 & 60</p>"), "50 & 60")

    def test_escaped_markup_is_not_promoted_into_markup(self):
        # Entities are decoded *after* tags are stripped, so text that merely
        # looks like a tag can never become one and be stripped as one.
        self.assertEqual(sg.visible_text("<p>&lt;script&gt;x()&lt;/script&gt;</p>"),
                         "<script>x()</script>")


class StructureIsStillRemoved(unittest.TestCase):

    def test_script_and_style_never_become_prose(self):
        html = ("<p>keep</p><script>var a=1;</script><style>p{color:red}</style>"
                "<nav>menu</nav><header>top</header><footer>bot</footer>")
        got = sg.visible_text(html)
        for gone in ("var a=1", "color:red", "menu", "top", "bot"):
            self.assertNotIn(gone, got)
        self.assertIn("keep", got)

    def test_cjk_and_punctuation_survive(self):
        self.assertEqual(sg.visible_text("<p>国防部 — 「演习」</p>"),
                         "国防部 — 「演习」")

    def test_whitespace_including_nbsp_is_collapsed(self):
        self.assertEqual(sg.visible_text("<p>a&nbsp;&nbsp;\n\t b</p>"), "a b")


class TitlesAreDecodedToo(unittest.TestCase):
    """`og:title` is an attribute value, so it is escaped by definition."""

    def test_og_title_entities_are_decoded(self):
        html = ('<meta property="og:title" content="Singapore&#x27;s Defence '
                '&amp; the &quot;Call&quot;">')
        self.assertEqual(sg.document_title(html),
                         'Singapore\'s Defence & the "Call"')

    def test_recorded_title_has_no_entity_left(self):
        token = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
        title = sg.document_title(as_utf8("entity_hex_apostrophe.html"))
        self.assertIsNotNone(title)
        self.assertIsNone(token.search(title))

    def test_the_h1_fallback_still_works(self):
        self.assertEqual(sg.document_title("<h1>Plain&#x27;s Title</h1>"),
                         "Plain's Title")


class TheCharsetDefectIsSeparateAndStillOpen(unittest.TestCase):
    """Recorded evidence that unescaping does not repair mis-decoded bytes.

    These tests describe the *bytes* and what each decoding produces. They do
    not assert that the adapter decodes correctly, because that fix is not in
    this change. They exist so the defect cannot be lost, and so that whoever
    fixes it has a failing-to-passing target already written down.
    """

    def test_the_recording_declares_utf8_in_the_document(self):
        raw = recorded("entity_hex_apostrophe.html")
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw, re.I)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1).decode().lower(), "utf-8")

    def test_the_served_content_type_carries_no_charset(self):
        meta = json.loads((FIX / "entity_fixtures.json").read_text(encoding="utf-8"))
        for name, rec in meta.items():
            with self.subTest(name):
                self.assertNotIn("charset", (rec["content_type"] or "").lower())

    def test_latin1_decoding_is_what_produces_the_mojibake(self):
        raw = recorded("entity_hex_apostrophe.html")
        self.assertIn(CURLY, raw.decode("utf-8"))
        self.assertNotIn(MOJIBAKE, raw.decode("utf-8"))
        self.assertIn(MOJIBAKE, raw.decode("latin-1"))

    def test_unescaping_cannot_repair_a_mis_decoded_byte(self):
        mangled = sg.visible_text("<p>" + MOJIBAKE + "</p>")
        self.assertIn(MOJIBAKE, mangled)
        self.assertNotIn(CURLY, mangled)


if __name__ == "__main__":
    unittest.main()
