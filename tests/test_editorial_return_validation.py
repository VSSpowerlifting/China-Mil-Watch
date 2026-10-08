"""No-network, no-write tests for returned IPR editorial worksheet intake."""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.validate_editorial_return import (
    ReturnValidationError, _load, main, validate_return,
)
from scripts.weekly_editorial_handoff import render_packet


def sidecar():
    return {
        "editorial_status": "draft",
        "issue_number": None,
        "week_start": "2026-09-27",
        "week_ending": "2026-10-03",
        "desks": ["china", "singapore"],
        "coverage_by_desk": {
            "china": {"records": 1, "by_screening": {"analyzed": 1}},
            "singapore": {"records": 1, "by_screening": {"awaiting_screening": 1}},
        },
        "source_trail": [
            {"record_id": 101, "desk": "china", "date": "2026-10-01",
             "source": "Agency A", "title": "Official development",
             "title_original": "Original", "lang": "zh",
             "url": "https://example.com/a", "screening": "analyzed"},
            {"record_id": 202, "desk": "singapore", "date": "2026-10-02",
             "source": "Agency B", "title": "Singapore development",
             "title_original": "Singapore development", "lang": "en",
             "url": "https://example.com/b", "screening": "awaiting_screening"},
        ],
    }


def manuscript():
    sections = {
        "title": "A verified opening note for the weekly Briefs draft",
        "dek": "This is a provisional editorial draft with source-linked claims.",
        "development": "The sources contain attributed statements, not proof of intent.",
        "opening_note": "This opening note introduces an attributed source-specific development.",
        "what_stood_out": "Each desk presents a different official account of a development.",
        "why_it_matters": "Records illuminate official claims, not confirmed institutional intent.",
        "what_was_routine": "Routine details are recorded with attribution and restraint.",
        "what_im_watching_next": "The editor should verify follow-up statements from the agencies.",
        "cross_desk_comparison": "The records can be compared without alleging coordination.",
        "editorial_questions": "Check translations and any updates published on Saturday.",
    }
    sections["citations"] = {
        "development": [101],
        "opening_note": [101],
        "what_stood_out": [101, 202],
        "why_it_matters": [101],
        "what_was_routine": [202],
        "what_im_watching_next": [101],
        "cross_desk_comparison": [101, 202],
    }
    return sections


def original_packet():
    return render_packet(sidecar(), manuscript=manuscript(), as_of="2026-10-02")


def edited_packet():
    return original_packet().replace(
        "A verified opening note for the weekly Briefs draft",
        "An edited opening note reviewed by Dylan for the weekly Brief",
        1,
    )


class ReturnedEditorialValidationTests(unittest.TestCase):
    def test_valid_edit_preserves_origins_and_never_approves(self):
        result = validate_return(original_packet(), edited_packet())
        self.assertEqual(result["source_records"], 2)
        self.assertEqual(result["sections"], 10)
        self.assertEqual(result["changed_sections"], 1)
        self.assertEqual(result["citation_lines"], 7)
        self.assertEqual(result["review_status"], "STRUCTURAL REVIEW ONLY — UNAPPROVED")

    def test_original_and_edited_must_differ(self):
        with self.assertRaisesRegex(ReturnValidationError, "no edits"):
            validate_return(original_packet(), original_packet())

    def test_header_mutations_refused(self):
        for old, new in (
            ("Packet: IPR-2026-10-03", "Packet: IPR-2026-10-10"),
            ("Desks: china, singapore", "Desks: china, vietnam"),
            ("UNNUMBERED DRAFT", "APPROVED ISSUE 17"),
        ):
            with self.subTest(change=old):
                tampered = edited_packet().replace(old, new, 1)
                with self.assertRaises(ReturnValidationError):
                    validate_return(original_packet(), tampered)

    def test_source_appendix_mutations_refused(self):
        edits = (
            ("https://example.com/a", "https://bad.example/a"),
            ("Record 101 |", "Record 999 |"),
            ("END OF SOURCE APPENDIX", "END OF ALTERED APPENDIX"),
        )
        for old, new in edits:
            with self.subTest(change=old):
                with self.assertRaises(ReturnValidationError):
                    validate_return(original_packet(), edited_packet().replace(old, new, 1))

    def test_source_appendix_duplication_refused(self):
        tampered = edited_packet().replace(
            "=== SOURCE APPENDIX — DO NOT EDIT ===",
            "=== SOURCE APPENDIX — DO NOT EDIT ===\n"
            "=== SOURCE APPENDIX — DO NOT EDIT ===", 1)
        with self.assertRaisesRegex(ReturnValidationError, "marker"):
            validate_return(original_packet(), tampered)

    def test_heading_deleted_or_added_refused(self):
        for tampered in (
            edited_packet().replace("## WHAT STOOD OUT", "## EXTRA HEADLINE", 1),
            edited_packet().replace("## WHAT STOOD OUT",
                                    "## WHAT STOOD OUT\n## EXTRA HEADLINE", 1),
        ):
            with self.assertRaisesRegex(ReturnValidationError, "heading"):
                validate_return(original_packet(), tampered)

    def test_bad_or_missing_citation_refused(self):
        for old, new in (
            ("SOURCE RECORD IDS: 101", "SOURCE RECORD IDS: 999"),
            ("SOURCE RECORD IDS: 101", "SOURCE RECORD IDS: 101, 101"),
            ("SOURCE RECORD IDS: 101", "SOURCE RECORD IDS: invented"),
            ("SOURCE RECORD IDS: 101", "DELETED SOURCE RECORD IDS: 101"),
        ):
            with self.subTest(new=new):
                tampered = edited_packet().replace(old, new, 1)
                with self.assertRaises(ReturnValidationError):
                    validate_return(original_packet(), tampered)

    def test_blank_heading_content_refused(self):
        value = edited_packet().replace(
            "An edited opening note reviewed by Dylan for the weekly Brief",
            "", 1)
        with self.assertRaisesRegex(ReturnValidationError, "no prose|blank"):
            validate_return(original_packet(), value)

    def test_legacy_manual_worksheet_has_same_structural_guard(self):
        original = render_packet(sidecar(), as_of="2026-10-02")
        returned = original.replace(
            "[One concrete development, not a regional roundup]",
            "An edited and attributed title", 1,
        )
        result = validate_return(original, returned)
        self.assertEqual(result["sections"], 11)
        self.assertEqual(result["citation_lines"], 0)

    def test_crlf_and_bom_from_text_editors_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_path = Path(tmp) / "original.txt"
            edited_path = Path(tmp) / "reply.txt"
            old_path.write_bytes(original_packet().encode("utf-8"))
            edited_path.write_bytes(b"\xef\xbb\xbf" +
                                    edited_packet().replace("\n", "\r\n").encode("utf-8"))
            result = validate_return(_load(old_path), _load(edited_path))
            self.assertEqual(result["changed_sections"], 1)

    def test_cli_is_read_only_and_silent_on_manuscript_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original.txt"
            returned = Path(tmp) / "reply.txt"
            original.write_text(original_packet(), encoding="utf-8")
            returned.write_text(edited_packet(), encoding="utf-8")
            first, second = original.read_bytes(), returned.read_bytes()
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["--original", str(original),
                                       "--edited", str(returned)]), 0)
            self.assertEqual((first, second), (original.read_bytes(), returned.read_bytes()))
            self.assertIn("UNAPPROVED", stdout.getvalue())
            self.assertNotIn("An edited opening note", stdout.getvalue())
            self.assertNotIn("https://example.com/a", stdout.getvalue())
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             ["original.txt", "reply.txt"])


if __name__ == "__main__":
    unittest.main()
