"""
PDF text extraction.

Most of these tests are about what extraction refuses to call success. A PDF
that carries no text layer parses cleanly and yields nothing, and so does a
damaged one — if both reached a collector as `""`, both would be stored as an
article with an empty body. `PROJECT_STATE.md` records what that costs:
article id=2678 has a 0-character body, was stored anyway, and passed relevance
screening on its title alone.

Fixtures are built here rather than committed as binaries. A PDF is a text
format for documents this simple, so the generator below is readable, exact
about what it puts on each page, and deterministic — which a scanned sample
found on the web would not be.
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processing import pdf_text as pt                              # noqa: E402

BODY = ("Joint Staff Press Release\n"
        "Chinese aircraft activity in the East China Sea was observed on "
        "22 July, and fighters were scrambled in response.")


def build_pdf(page_texts, *, font="Helvetica") -> bytes:
    """
    A minimal valid PDF. `page_texts` is one entry per page; `None` draws a page
    with an empty content stream, which is what a scan looks like structurally —
    a real page carrying no text operators at all.
    """
    objs = {}
    n_pages = len(page_texts)
    page_ids = [4 + i * 2 for i in range(n_pages)]
    kids = " ".join("%d 0 R" % i for i in page_ids)
    objs[1] = "<< /Type /Catalog /Pages 2 0 R >>"
    objs[2] = "<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n_pages)
    objs[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /%s >>" % font
    for i, txt in enumerate(page_texts):
        pid, cid = page_ids[i], page_ids[i] + 1
        objs[pid] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     "/Contents %d 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
                     % cid)
        if txt is None:
            stream = ""
        else:
            parts = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
            for line in txt.split("\n"):
                esc = (line.replace("\\", r"\\")
                           .replace("(", r"\(").replace(")", r"\)"))
                parts.append("(%s) Tj T*" % esc)
            parts.append("ET")
            stream = "\n".join(parts)
        objs[cid] = ("<< /Length %d >>\nstream\n%s\nendstream"
                     % (len(stream), stream))

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += ("%d 0 obj\n%s\nendobj\n" % (num, objs[num])).encode("latin-1")
    xref_at = len(out)
    top = max(objs) + 1
    out += ("xref\n0 %d\n" % top).encode()
    out += b"0000000000 65535 f \n"
    for num in range(1, top):
        out += ("%010d 00000 n \n" % offsets.get(num, 0)).encode()
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (top, xref_at)).encode()
    return bytes(out)


def encrypted_pdf(password: str, body: str = BODY) -> bytes:
    from pypdf import PdfWriter
    writer = PdfWriter(clone_from=io.BytesIO(build_pdf([body])))
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class TestATextLayerIsRead(unittest.TestCase):

    def test_a_press_release_yields_its_body(self):
        r = pt.extract_pdf_text(build_pdf([BODY]))
        self.assertEqual(r.status, pt.OK)
        self.assertTrue(r.ok)
        self.assertIn("East China Sea", r.text)
        self.assertEqual(r.page_count, 1)
        self.assertEqual(r.pages_with_text, 1)
        self.assertEqual(r.pages_failed, 0)

    def test_line_breaks_become_a_paragraph(self):
        """
        PDF text carries a hard break wherever the source laid out a line.
        Preserving them would store a column of fragments instead of prose, and
        would not compare with an HTML body from the same desk.
        """
        r = pt.extract_pdf_text(build_pdf([BODY]))
        self.assertNotIn("\n", r.text)
        self.assertIn("Press Release Chinese aircraft", r.text)

    def test_multiple_pages_are_joined(self):
        r = pt.extract_pdf_text(build_pdf([BODY, "Annex A. " + BODY]))
        self.assertEqual(r.status, pt.OK)
        self.assertEqual(r.page_count, 2)
        self.assertEqual(r.pages_with_text, 2)
        self.assertIn("Annex A.", r.text)

    def test_extraction_is_deterministic(self):
        data = build_pdf([BODY])
        self.assertEqual(pt.extract_pdf_text(data).text,
                         pt.extract_pdf_text(data).text)


class TestEmptyIsNeverSilent(unittest.TestCase):
    """The defect class this module exists to prevent."""

    def test_a_page_with_no_text_is_not_a_successful_empty_body(self):
        r = pt.extract_pdf_text(build_pdf([None]))
        self.assertEqual(r.status, pt.NO_TEXT_LAYER)
        self.assertFalse(r.ok)
        self.assertEqual(r.text, "")
        self.assertIn("text layer", r.detail)

    def test_scanner_residue_does_not_count_as_a_text_layer(self):
        """A page number left behind by a scanner is not a document body."""
        r = pt.extract_pdf_text(build_pdf(["7"]))
        self.assertEqual(r.status, pt.NO_TEXT_LAYER)
        self.assertEqual(r.text, "")

    def test_the_floor_is_a_parameter_not_a_hidden_constant(self):
        tiny = build_pdf(["Scrambled."])
        self.assertEqual(pt.extract_pdf_text(tiny).status, pt.NO_TEXT_LAYER)
        self.assertEqual(pt.extract_pdf_text(tiny, min_chars=4).status, pt.OK)

    def test_text_cannot_accompany_a_non_ok_status(self):
        """The invariant is enforced, not merely documented."""
        with self.assertRaises(ValueError):
            pt.PdfExtraction(pt.NO_TEXT_LAYER, text="something")

    def test_only_ok_is_text_bearing(self):
        self.assertEqual(pt.TEXT_BEARING, frozenset({pt.OK}))
        for status in pt.TERMINAL:
            self.assertNotIn(status, pt.TEXT_BEARING)


class TestRefusals(unittest.TestCase):

    def test_an_error_page_served_at_a_pdf_url_is_malformed(self):
        """
        The realistic failure: a listing links `p20260722_01e.pdf`, the server
        returns an HTML 404 with status 200, and the bytes are not a PDF.
        """
        r = pt.extract_pdf_text(b"<html><body>404 Not Found</body></html>")
        self.assertEqual(r.status, pt.MALFORMED)
        self.assertIn("%PDF-", r.detail)

    def test_a_truncated_download_is_malformed(self):
        r = pt.extract_pdf_text(build_pdf([BODY])[:40])
        self.assertEqual(r.status, pt.MALFORMED)
        self.assertEqual(r.text, "")

    def test_an_empty_body_is_malformed(self):
        self.assertEqual(pt.extract_pdf_text(b"").status, pt.MALFORMED)

    def test_a_password_protected_pdf_is_refused_not_mangled(self):
        r = pt.extract_pdf_text(encrypted_pdf("hunter2"))
        self.assertEqual(r.status, pt.ENCRYPTED)
        self.assertEqual(r.text, "")

    def test_permissions_only_encryption_is_still_readable(self):
        """
        Many ministries encrypt to set printing permissions, with no password.
        Refusing those would lose documents we are entitled to read.
        """
        r = pt.extract_pdf_text(encrypted_pdf(""))
        self.assertEqual(r.status, pt.OK)
        self.assertIn("East China Sea", r.text)

    def test_an_oversized_document_is_refused_before_parsing(self):
        r = pt.extract_pdf_text(build_pdf([BODY]), max_bytes=64)
        self.assertEqual(r.status, pt.TOO_LARGE)
        self.assertIn("ceiling", r.detail)

    def test_a_page_bomb_is_refused(self):
        r = pt.extract_pdf_text(build_pdf([BODY] * 5), max_pages=2)
        self.assertEqual(r.status, pt.TOO_MANY_PAGES)
        self.assertEqual(r.page_count, 5)

    def test_bad_input_never_raises_for_the_caller(self):
        for junk in (b"", b"%PDF-", b"%PDF-1.4\ngarbage", bytes(range(256))):
            with self.subTest(junk=junk[:12]):
                self.assertIn(pt.extract_pdf_text(junk).status, pt.TERMINAL)

    def test_a_wrong_type_is_programmer_error_and_does_raise(self):
        with self.assertRaises(TypeError):
            pt.extract_pdf_text("not bytes")


class TestTheLogStaysHonest(unittest.TestCase):

    def test_pypdf_complaints_do_not_reach_the_run_log(self):
        """
        pypdf logs damaged input at ERROR level. Every such input becomes a
        recorded MALFORMED result, so an unactioned error line beside a handled
        outcome would make the log disagree with the record.
        """
        import logging
        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("pypdf")
        handler = Capture()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        r = pt.extract_pdf_text(build_pdf([BODY])[:40])
        self.assertEqual(r.status, pt.MALFORMED)
        self.assertEqual(records, [])

    def test_the_suppression_is_scoped_and_restored(self):
        import logging
        logger = logging.getLogger("pypdf")
        logger.setLevel(logging.INFO)
        self.addCleanup(logger.setLevel, logging.NOTSET)
        pt.extract_pdf_text(build_pdf([BODY])[:40])
        self.assertEqual(logger.level, logging.INFO,
                         "the parse left pypdf's logger muted")


class TestNormalisation(unittest.TestCase):

    def test_whitespace_collapses(self):
        self.assertEqual(pt.normalise("a  \n\t b \n\n c "), "a b c")

    def test_hyphenated_line_breaks_rejoin(self):
        self.assertEqual(pt.normalise("recon-\nnaissance"), "reconnaissance")

    def test_soft_hyphens_are_dropped(self):
        self.assertEqual(pt.normalise("recon­naissance"), "reconnaissance")
