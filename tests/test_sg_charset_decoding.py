"""
Singapore MINDEF: choosing the encoding by declaration, not by default.

mindef.gov.sg serves `Content-Type: text/html` with no charset parameter. RFC
2616 tells `requests` to fall back to ISO-8859-1 for `text/*`, so `resp.text`
mis-decoded every multi-byte character on the site even though each document's
own `<meta charset>` says UTF-8. Measured on the 59 captured shadow records:
544 mojibake sequences across 56 bodies, plus 11 titles.

`declared_encoding()` answers from declarations only, in the HTML standard's
order — HTTP header, byte-order mark, `<meta charset>` in the first 1024
bytes, then a documented default — and always reports *which* of those it
used, so a fallback is visible rather than inferred. Nothing sniffs the
payload to guess.

Fixtures whose point is the bytes are stored as bytes. Where a case cannot be
recorded from this ministry — Latin-1 pages, CJK, conflicting declarations —
the bytes are constructed explicitly and labelled as such.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scraper.sources import sg_mindef as sg                    # noqa: E402

FIX = REPO_ROOT / "tests" / "fixtures" / "sg_mindef"
RECORDED = "charset_undeclared_utf8.html"

CURLY = "’"
LEFT_CURLY = "‘"
EMDASH = "—"
ENDASH = "–"
LDQUO = "“"
RDQUO = "”"
MOJIBAKE = CURLY.encode("utf-8").decode("latin-1")


class FakeResponse:
    """Just enough of `requests.Response` for the decoder."""

    def __init__(self, content, content_type=None, url="https://x/"):
        self.content = content
        self.headers = {"Content-Type": content_type} if content_type else {}
        self.url = url


def recorded() -> bytes:
    return (FIX / RECORDED).read_bytes()


class TheRecordingCarriesTheDefect(unittest.TestCase):
    """Guard the evidence: none of this proves anything if the bytes are ASCII."""

    def test_the_excerpt_contains_multi_byte_punctuation(self):
        self.assertIn(CURLY.encode("utf-8"), recorded())

    def test_the_document_declares_utf8(self):
        meta = sg.declared_encoding(recorded(), "text/html")
        self.assertEqual(meta, ("utf-8", "meta"))

    def test_the_server_declared_no_charset(self):
        m = json.loads((FIX / "entity_fixtures.json").read_text(encoding="utf-8"))
        rec = m[RECORDED]
        self.assertNotIn("charset", (rec["content_type"] or "").lower())
        self.assertEqual(rec["requests_would_say"], "ISO-8859-1")


class DeclarationOrder(unittest.TestCase):

    def test_the_http_header_outranks_the_document(self):
        enc, src = sg.declared_encoding(b'<meta charset="utf-8">',
                                        "text/html; charset=iso-8859-1")
        self.assertEqual((enc, src), ("iso-8859-1", "http-header"))

    def test_a_bom_outranks_a_meta_tag(self):
        raw = b"\xef\xbb\xbf" + b'<meta charset="iso-8859-1">'
        self.assertEqual(sg.declared_encoding(raw, "text/html"), ("utf-8-sig", "bom"))

    def test_meta_is_used_when_the_header_is_silent(self):
        self.assertEqual(sg.declared_encoding(b'<meta charset="utf-8">', "text/html"),
                         ("utf-8", "meta"))

    def test_a_declaration_past_the_prescan_window_is_not_honoured(self):
        raw = b"<!-- " + b"x" * sg.META_PRESCAN_BYTES + b' --><meta charset="utf-8">'
        enc, src = sg.declared_encoding(raw, "text/html")
        self.assertEqual(src, "undeclared")

    def test_nothing_declared_falls_back_observably(self):
        enc, src = sg.declared_encoding(b"<html>plain ascii</html>", "text/html")
        self.assertEqual(enc, sg.UNDECLARED_DEFAULT)
        self.assertEqual(src, "undeclared")     # the caller can see it guessed

    def test_the_source_is_always_one_of_the_documented_four(self):
        for raw, ct in ((b"", "text/html; charset=utf-8"),
                        (b"\xef\xbb\xbfx", None),
                        (b'<meta charset="utf-8">', "text/html"),
                        (b"<html></html>", "text/html")):
            with self.subTest(ct):
                self.assertIn(sg.declared_encoding(raw, ct)[1],
                              ("http-header", "bom", "meta", "undeclared"))


class UtfEightWithoutAnHttpCharset(unittest.TestCase):
    """The defect this change exists for."""

    def test_the_recorded_page_decodes_without_mojibake(self):
        text = sg.decode_response(recorded(), "text/html").text
        self.assertIn(CURLY, text)
        self.assertNotIn(MOJIBAKE, text)

    def test_the_old_default_is_what_produced_the_mojibake(self):
        # Recorded so the regression is self-explaining, not folklore.
        self.assertIn(MOJIBAKE, recorded().decode("iso-8859-1"))
        self.assertNotIn(MOJIBAKE, recorded().decode("utf-8"))

    def test_the_extracted_body_carries_no_mojibake(self):
        body = sg.document_body(sg.decode_response(recorded(), "text/html").text)
        self.assertNotIn(MOJIBAKE, body)
        self.assertIn(CURLY, body)

    def test_response_text_routes_through_the_decoder(self):
        resp = FakeResponse(recorded(), "text/html")
        self.assertEqual(sg.response_text(resp),
                         sg.decode_response(recorded(), "text/html").text)
        self.assertNotIn(MOJIBAKE, sg.response_text(resp))


class EveryEvidencedCharacter(unittest.TestCase):
    """Constructed bytes: the ministry's pages do not carry all of these."""

    CASES = (("right single quote", CURLY), ("left single quote", LEFT_CURLY),
             ("left double quote", LDQUO), ("right double quote", RDQUO),
             ("em dash", EMDASH), ("en dash", ENDASH),
             ("ellipsis", "…"), ("non-breaking space", " "),
             ("e acute", "é"), ("degree sign", "°"))

    def test_each_character_survives_the_decode(self):
        for label, ch in self.CASES:
            with self.subTest(label):
                raw = ('<meta charset="utf-8"><p>a' + ch + 'b</p>').encode("utf-8")
                self.assertIn(ch, sg.decode_response(raw, "text/html").text)

    def test_each_character_survives_extraction(self):
        for label, ch in self.CASES:
            if ch == " ":
                continue        # collapses to a space by design
            with self.subTest(label):
                raw = ('<meta charset="utf-8"><p>a' + ch + 'b</p>').encode("utf-8")
                text = sg.visible_text(sg.decode_response(raw, "text/html").text)
                self.assertIn(ch, text)


class CjkSurvives(unittest.TestCase):

    def test_cjk_decodes_and_extracts_intact(self):
        s = "国防部 — 「演习」 台海"
        raw = ('<meta charset="utf-8"><p>' + s + "</p>").encode("utf-8")
        self.assertEqual(sg.visible_text(sg.decode_response(raw, "text/html").text), s)

    def test_cjk_in_a_title_survives(self):
        raw = ('<meta charset="utf-8">'
               '<meta property="og:title" content="新加坡国防部">').encode("utf-8")
        self.assertEqual(sg.document_title(sg.decode_response(raw, "text/html").text),
                         "新加坡国防部")


class LegitimateLatin1IsHonoured(unittest.TestCase):
    """A page that really is Latin-1 must not be forced into UTF-8."""

    def test_a_declared_latin1_page_decodes_as_latin1(self):
        raw = "<p>café résumé</p>".encode("iso-8859-1")
        out = sg.decode_response(raw, "text/html; charset=iso-8859-1")
        self.assertEqual(out.encoding, "iso-8859-1")
        self.assertEqual(out.source, "http-header")
        self.assertIn("café", out.text)
        self.assertEqual(out.replacements, 0)

    def test_a_meta_declared_latin1_page_decodes_as_latin1(self):
        raw = ('<meta charset="iso-8859-1"><p>café</p>').encode("iso-8859-1")
        out = sg.decode_response(raw, "text/html")
        self.assertEqual(out.encoding, "iso-8859-1")
        self.assertIn("café", out.text)

    def test_latin1_bytes_are_not_reinterpreted_as_utf8(self):
        # These bytes are valid Latin-1 and invalid UTF-8. Honouring the
        # declaration is the whole point; guessing would mangle them.
        raw = b'<meta charset="iso-8859-1"><p>\xe9\xe8\xea</p>'
        self.assertIn("éèê", sg.decode_response(raw, "text/html").text)


class DecodingHappensOnceAndOnly(unittest.TestCase):

    def test_already_correct_text_is_not_transformed_again(self):
        # No mojibake-repair pass exists in the prospective path. Text that is
        # already right must come through untouched.
        raw = ('<meta charset="utf-8"><p>it' + CURLY + "s fine</p>").encode("utf-8")
        text = sg.decode_response(raw, "text/html").text
        self.assertEqual(sg.visible_text(text), "it" + CURLY + "s fine")

    def test_text_that_looks_like_mojibake_is_left_alone(self):
        # Latin-1 content can legitimately contain the byte sequence that
        # mojibake produces. Nothing may "helpfully" repair it.
        raw = ('<meta charset="iso-8859-1"><p>' + MOJIBAKE + "</p>").encode("iso-8859-1")
        out = sg.decode_response(raw, "text/html")
        self.assertIn(MOJIBAKE, out.text)
        self.assertNotIn(CURLY, out.text)

    def test_entities_still_decode_exactly_once(self):
        raw = b'<meta charset="utf-8"><p>&amp;#x27; and &#x27;</p>'
        self.assertEqual(sg.visible_text(sg.decode_response(raw, "text/html").text),
                         "&#x27; and '")

    def test_decoding_is_idempotent_over_repeated_calls(self):
        a = sg.decode_response(recorded(), "text/html").text
        b = sg.decode_response(recorded(), "text/html").text
        self.assertEqual(a, b)


class TitlesAndBodiesAgree(unittest.TestCase):

    def test_both_come_from_the_same_decoded_string(self):
        text = sg.decode_response(recorded(), "text/html").text
        title, body = sg.document_title(text), sg.document_body(text)
        self.assertIsNotNone(title)
        for part in (title, body):
            self.assertNotIn(MOJIBAKE, part)

    def test_a_title_and_body_sharing_a_character_agree_on_it(self):
        raw = ('<meta charset="utf-8">'
               '<meta property="og:title" content="Singapore' + CURLY + 's Defence">'
               "<h1>h</h1><p>Singapore" + CURLY + "s Defence</p>").encode("utf-8")
        text = sg.decode_response(raw, "text/html").text
        self.assertIn(CURLY, sg.document_title(text))
        self.assertIn(CURLY, sg.document_body(text))


class BadBytesFailObservably(unittest.TestCase):

    def test_undecodable_bytes_are_replaced_and_counted(self):
        raw = b'<meta charset="utf-8"><p>ok \xff\xfe\xfd</p>'
        out = sg.decode_response(raw, "text/html")
        self.assertTrue(out.lossy)
        self.assertGreater(out.replacements, 0)
        self.assertIn("ok", out.text)

    def test_a_clean_decode_reports_no_replacements(self):
        out = sg.decode_response(recorded(), "text/html")
        self.assertFalse(out.lossy)
        self.assertEqual(out.replacements, 0)

    def test_an_unknown_declared_encoding_falls_back_observably(self):
        raw = b'<meta charset="definitely-not-a-charset"><p>hi</p>'
        out = sg.decode_response(raw, "text/html")
        self.assertEqual(out.encoding, "definitely-not-a-charset")
        self.assertEqual(out.source, "meta")
        self.assertIn("hi", out.text)

    def test_the_declared_encoding_is_reported_even_when_it_fails(self):
        raw = b'<meta charset="utf-8"><p>\xff</p>'
        out = sg.decode_response(raw, "text/html")
        self.assertEqual((out.encoding, out.source), ("utf-8", "meta"))


class StructureStillNeverBecomesProse(unittest.TestCase):

    def test_scripts_styles_and_navigation_are_removed(self):
        raw = ('<meta charset="utf-8"><h1>t</h1>'
               "<script>var a=1;</script><style>p{color:red}</style>"
               "<nav>menu</nav><header>top</header><footer>bot</footer>"
               "<p>real prose" + CURLY + "s here</p>").encode("utf-8")
        body = sg.document_body(sg.decode_response(raw, "text/html").text)
        for gone in ("var a=1", "color:red", "menu", "top", "bot"):
            self.assertNotIn(gone, body)
        self.assertIn("real prose" + CURLY + "s here", body)

    def test_a_caption_is_not_promoted_by_decoding(self):
        raw = ('<meta charset="utf-8"><h1>t</h1>'
               "<script>caption = 'hidden'</script><p>visible</p>").encode("utf-8")
        body = sg.document_body(sg.decode_response(raw, "text/html").text)
        self.assertNotIn("hidden", body)
        self.assertIn("visible", body)


if __name__ == "__main__":
    unittest.main()
