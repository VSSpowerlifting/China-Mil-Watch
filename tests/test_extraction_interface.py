"""
The document extraction interface — behaviour, and dormancy.

`processing/extraction.py` puts one entry point in front of the HTML and PDF
paths so a future collector chooses a backend once, in a place that can be
tested, instead of inside whichever adapter is written first.

Two things have to hold.

The first is the fail-closed contract, inherited from `processing.pdf_text` and
extended one level up: a caller that receives `str` cannot tell an empty
document from a failed extraction, so this returns a status too, and a result
that is not `OK` cannot carry text at all. A scan stays `no_text_layer` rather
than becoming an empty article — the defect behind article id=2678, where a body
that was never captured was stored anyway and then passed relevance screening on
its title alone.

The second is that none of it is switched on. Adding an extraction interface
does not enable a source, build a collector, or change what the pipeline does
tonight, and the tests at the bottom assert that mechanically rather than
asking the reader to believe it.

No network. No database. No writes.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processing import extraction as ex                          # noqa: E402
from processing import pdf_text as pt                            # noqa: E402

HTML = b"<html><head><style>p{color:red}</style></head><body>" \
       b"<script>var x=1;</script><p>Hello   world</p></body></html>"


def build_pdf(pages):
    """A minimal PDF, reusing the fixture builder the PDF tests already trust."""
    from tests.test_pdf_text import build_pdf as _build
    return _build(pages)


def body_page():
    """A page long enough to clear the minimum-text floor."""
    from tests.test_pdf_text import BODY
    return BODY


class TestMediaTypeSelection(unittest.TestCase):

    def test_a_declared_content_type_wins_over_the_url(self):
        """
        A server that says `text/html` for a file named `.pdf` is telling us
        something. Guessing past it is how a challenge page gets stored as a
        document.
        """
        self.assertEqual(
            ex.media_type_of("text/html; charset=utf-8", "https://x/a.pdf"),
            "text/html")

    def test_the_url_suffix_is_used_only_when_no_type_is_declared(self):
        self.assertEqual(ex.media_type_of(None, "https://x/js/p1e.pdf"),
                         "application/pdf")
        self.assertEqual(ex.media_type_of(None, "https://x/a.htm"), "text/html")
        self.assertEqual(ex.media_type_of(None, "https://x/a"), "")

    def test_an_undeclared_document_is_sniffed_only_for_pdf(self):
        """
        The PDF magic number is unambiguous; HTML is not. An unsniffable
        document is refused rather than parsed as markup and stored as whatever
        fell out.
        """
        self.assertTrue(ex.extract(build_pdf([body_page()])).ok)
        self.assertEqual(ex.extract(HTML).status, ex.UNSUPPORTED_MEDIA_TYPE)

    def test_an_unhandled_type_is_unread_not_empty(self):
        result = ex.extract(b"\x00\x01\x02", "image/png")
        self.assertEqual(result.status, ex.UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(result.text, "")
        self.assertIn("image/png", result.detail)


class TestExtractionResults(unittest.TestCase):

    def test_markup_yields_visible_text_without_script_or_style(self):
        result = ex.extract(HTML, "text/html")
        self.assertTrue(result.ok)
        self.assertEqual(result.text, "Hello world")
        self.assertNotIn("var x", result.text)
        self.assertNotIn("color:red", result.text)

    def test_markup_with_no_visible_text_is_recorded_as_unread(self):
        result = ex.extract(b"<html><body><img src=x></body></html>",
                            "text/html")
        self.assertEqual(result.status, ex.NO_TEXT_LAYER)
        self.assertEqual(result.text, "")

    def test_plain_text_is_normalised_like_every_other_body(self):
        result = ex.extract(b"one\n  two\tthree ", "text/plain")
        self.assertEqual(result.text, "one two three")

    def test_the_same_bytes_give_the_same_result(self):
        self.assertEqual(ex.extract(HTML, "text/html"),
                         ex.extract(HTML, "text/html"))

    def test_a_wrong_argument_type_still_raises(self):
        """Programmer error is not a document outcome."""
        with self.assertRaises(TypeError):
            ex.extract("not bytes", "text/html")


class TestFailClosedStatusesSurviveTheWrapper(unittest.TestCase):
    """
    The PDF statuses pass through unchanged. Collapsing any two of them here
    would undo the whole point of the layer below.
    """

    def test_a_scan_is_not_an_empty_article(self):
        result = ex.extract(build_pdf([None]), "application/pdf")
        self.assertEqual(result.status, ex.NO_TEXT_LAYER)
        self.assertEqual(result.text, "")

    def test_malformed_and_encrypted_stay_distinguishable(self):
        malformed = ex.extract(b"not a pdf at all", "application/pdf")
        self.assertEqual(malformed.status, ex.MALFORMED)
        from tests.test_pdf_text import encrypted_pdf
        encrypted = ex.extract(encrypted_pdf("hunter2"), "application/pdf")
        self.assertEqual(encrypted.status, ex.ENCRYPTED)
        self.assertNotEqual(malformed.status, encrypted.status)

    def test_a_resource_ceiling_is_a_refusal_carrying_no_text(self):
        for status, kwargs in ((ex.TOO_LARGE, {"max_bytes": 64}),
                               (ex.TOO_MANY_PAGES, {"max_pages": 1})):
            with self.subTest(status=status):
                result = ex.extract(build_pdf([body_page()] * 3),
                                    "application/pdf", **kwargs)
                self.assertEqual(result.status, status)
                self.assertEqual(result.text, "")

    def test_a_non_ok_result_cannot_carry_text(self):
        with self.assertRaises(ValueError):
            ex.Extraction(ex.NO_TEXT_LAYER, text="something")

    def test_an_unknown_status_is_refused(self):
        with self.assertRaises(ValueError):
            ex.Extraction("probably_fine")

    def test_page_failures_stay_visible_alongside_ok(self):
        result = ex.extract(build_pdf([body_page()]), "application/pdf")
        self.assertTrue(result.ok)
        self.assertEqual(result.pages_failed, 0)
        self.assertGreaterEqual(result.page_count, 1)
        self.assertEqual(result.backend, "pdf_text")

    def test_every_status_has_reader_facing_prose(self):
        self.assertEqual(sorted(ex.STATUS_PROSE), sorted(ex.STATUSES))
        for code, prose in ex.STATUS_PROSE.items():
            with self.subTest(status=code):
                self.assertTrue(prose.strip())

    def test_only_ok_may_carry_text(self):
        self.assertEqual(set(ex.TEXT_BEARING), {ex.OK})
        self.assertEqual(set(pt.TEXT_BEARING), {pt.OK})


class TestThisEnablesNothing(unittest.TestCase):
    """
    Adding an interface is not switching a collector on. Asserted mechanically,
    because "dormant" is a claim that decays the moment someone imports it.
    """

    def source_files(self):
        skip = {"tests", ".git", "output", "preview", ".venv", "__pycache__"}
        for path in REPO_ROOT.rglob("*.py"):
            if any(part in skip for part in path.parts):
                continue
            yield path
        for path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
            yield path

    def test_no_collector_workflow_or_adapter_imports_the_interface(self):
        for path in self.source_files():
            if path.name == "extraction.py":
                continue
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=str(path.relative_to(REPO_ROOT))):
                self.assertNotIn("processing.extraction", text)
                self.assertNotIn("from processing import extraction", text)

    def test_the_pdf_extractor_reaches_no_collector_either(self):
        for path in self.source_files():
            if path.parent.name == "processing":
                continue
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=str(path.relative_to(REPO_ROOT))):
                self.assertNotIn("pdf_text", text)

    def test_the_view_layer_is_not_on_the_collection_path(self):
        """
        `core.viewmodel` and `core.desk_registry` are read-only rendering
        support. If the pipeline or a workflow ever imports one, a rendering
        concern has reached collection.
        """
        collection = [REPO_ROOT / "pipeline.py"]
        collection += list((REPO_ROOT / "scraper").rglob("*.py"))
        collection += list((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        for path in collection:
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=str(path.relative_to(REPO_ROOT))):
                self.assertNotIn("core.viewmodel", text)
                self.assertNotIn("desk_registry", text)

    def test_the_desk_registry_cannot_be_discovered_as_a_manifest(self):
        """
        `load_all_desks()` globs `desks/*/manifest.json`. The registry sits one
        level above that glob on purpose: declaring a desk in it must not make
        `sync_desk_config()` write a row into the tracked database.
        """
        from core.manifests import load_all_desks
        self.assertEqual(sorted(load_all_desks()), ["china"])
        self.assertTrue((REPO_ROOT / "desks" / "registry.json").is_file())
        self.assertFalse((REPO_ROOT / "desks" / "registry"
                          / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
