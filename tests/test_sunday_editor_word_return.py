"""Offline Word-return intake; original citations and research stay immutable."""
from __future__ import annotations

from io import BytesIO
import unittest

from docx import Document

from scripts.import_sunday_editor_docx import reconstruct_return
from scripts.sunday_editor_docx import render_editor_docx
from scripts.validate_editorial_return import ReturnValidationError, _split
from tests.test_sunday_editor_readable import reviewed_packet


class WordReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = reviewed_packet()

    def editing_copy(self):
        return Document(BytesIO(render_editor_docx(self.original)))

    @staticmethod
    def save(document):
        stream = BytesIO()
        document.save(stream)
        return stream.getvalue()

    def test_prose_edits_restore_immutable_source_references(self):
        document = self.editing_copy()
        for n, p in enumerate(document.paragraphs):
            if p.style.name == "Heading 2" and p.text == "Why it matters":
                document.paragraphs[n + 1].add_run(" This editorial qualification matters.")
                break
        else:
            self.fail("missing Why it matters section")
        candidate, receipt = reconstruct_return(self.original, self.save(document))
        self.assertEqual(receipt["review_status"], "STRUCTURAL REVIEW ONLY — UNAPPROVED")
        self.assertGreater(receipt["changed_sections"], 0)
        _, _, original_appendix = _split(self.original)
        _, _, returned_appendix = _split(candidate)
        self.assertEqual(original_appendix, returned_appendix)
        self.assertIn("This editorial qualification matters.", candidate)
        self.assertIn("EXTERNAL SOURCE IDS:", candidate)

    def test_unchanged_word_is_not_an_editorial_return(self):
        with self.assertRaisesRegex(ReturnValidationError, "no edits"):
            reconstruct_return(self.original, render_editor_docx(self.original))

    def test_deleted_or_reordered_word_heading_refused(self):
        doc = self.editing_copy()
        for p in doc.paragraphs:
            if p.style.name == "Heading 2" and p.text == "Why it matters":
                p.text = "Rewritten section label"
                break
        with self.assertRaisesRegex(ReturnValidationError, "unknown"):
            reconstruct_return(self.original, self.save(doc))

    def test_word_cannot_add_source_citation_lines(self):
        document = self.editing_copy()
        for n, p in enumerate(document.paragraphs):
            if p.style.name == "Heading 2" and p.text == "Why it matters":
                document.paragraphs[n + 1].add_run(" SOURCE RECORD IDS: 999")
                break
        with self.assertRaisesRegex(ReturnValidationError, "protected"):
            reconstruct_return(self.original, self.save(document))


if __name__ == "__main__":
    unittest.main()
