"""Japan Oct10 typed research attests exact shadow text, never publication."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import audit_japan_oct05_brief_source as original
from scripts.attest_japan_sunday_research import (
    attest, main, JapanSundayAuditError, WEEK,
)

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "research/briefs_editorial_evidence/2026-10-10.json"


def approved_snapshot():
    # This represents a MACHINE evidence report, NOT editorial approval.
    return {
        "state_commit": original.STATE_COMMIT,
        "state_db_blob_sha1": original.DB_BLOB_SHA1,
        "archived_text_sha256_verified": True,
        "source_url": original.PDF_URL,
        "source_published_date": "2026-10-05",
        "archive_current_week_records_through_oct08": 1,
        "archived_original_pdf_bytes_verified": False,
        "full_pdf_human_fidelity_review_complete": False,
        "editorial_inclusion_approved": False,
    }


def packet_at(folder, transform=None):
    target = Path(folder) / (WEEK + ".json")
    doc = json.loads(PACK.read_text(encoding="utf-8"))
    if transform:
        transform(doc)
    target.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


class JapanSundaySourceAttestation(unittest.TestCase):
    def test_real_packet_matches_three_ids_but_not_human_approval(self):
        report = attest(week_ending=WEEK, as_of=WEEK,
                        snapshot=approved_snapshot())
        self.assertEqual(report["japan_records"], 3)
        self.assertEqual({e["id"] for e in report["evidence"]},
                         {"JP-W41-01", "JP-W41-02", "JP-W41-06"})
        self.assertTrue(next(x for x in report["evidence"]
                             if x["id"] == "JP-W41-06")["archived_extracted_text_verified"])
        self.assertFalse(next(x for x in report["evidence"]
                              if x["id"] == "JP-W41-01")["original_html_body_pinned"])
        for key in ("archived_original_pdf_bytes_verified",
                    "human_source_review_completed", "editorial_inclusion_approved",
                    "japan_production_eligible"):
            self.assertIs(report[key], False)
        self.assertEqual(report["smtp_or_production_writes"], 0)
        self.assertNotIn("CH-47", json.dumps(report))
        self.assertNotIn("キーン", json.dumps(report))

    def test_future_week_never_inherits_oct10_packet(self):
        later = attest(week_ending="2026-10-17", as_of="2026-10-17")
        self.assertEqual(later["status"], "no_japan_packet_for_this_week")
        self.assertEqual(later["japan_records"], 0)
        self.assertEqual(later["evidence"], [])
        self.assertFalse(later["editorial_inclusion_approved"])

    def test_invalid_week_dates_refused(self):
        for week, cutoff in (
            ("2026-10-09", "2026-10-09"),
            ("2026-10-10", "2026-10-08"),
            ("2026-10-10", "2026-10-11"),
            ("2026-10-10", "2026-10-9"),
            ("2026-10-17", "2026-10-14"),
        ):
            with self.subTest(week=week, cutoff=cutoff):
                with self.assertRaises(JapanSundayAuditError):
                    attest(week_ending=week, as_of=cutoff,
                           snapshot=approved_snapshot())

    def test_altered_pdf_hash_or_state_pin_refused(self):
        for field, bad in (
            ("state_commit", "0" * 40),
            ("source_content_sha256", "0" * 64),
            ("hash_rule", "mps-vi-content-v1"),
            ("published_date", "2026-09-17"),
        ):
            def mutate(doc):
                next(x for x in doc["items"] if x["id"] == "JP-W41-06")[field] = bad
            with tempfile.TemporaryDirectory() as tmp:
                packet_at(tmp, mutate)
                with self.subTest(field=field), self.assertRaises(ValueError):
                    attest(week_ending=WEEK, as_of=WEEK,
                           directory=tmp, snapshot=approved_snapshot())

    def test_html_cannot_pretend_to_be_archived_pdf(self):
        for field, bad in (
            ("source_url", "https://www.mod.go.jp/en/article/2026/10/fake.html"),
            ("published_date", "2026-10-04"),
            ("source_kind", "shadow-extracted-original"),
            ("source_content_sha256", "f" * 64),
        ):
            def mutate(doc):
                next(x for x in doc["items"] if x["id"] == "JP-W41-01")[field] = bad
            with tempfile.TemporaryDirectory() as tmp:
                packet_at(tmp, mutate)
                with self.subTest(field=field), self.assertRaises(ValueError):
                    attest(week_ending=WEEK, as_of=WEEK,
                           directory=tmp, snapshot=approved_snapshot())

    def test_pinned_receipt_no_fidelity_or_human_signoff(self):
        for field, new in (
            ("state_commit", "f" * 40),
            ("state_db_blob_sha1", "f" * 40),
            ("archive_current_week_records_through_oct08", 2),
            ("archived_text_sha256_verified", False),
            ("archived_original_pdf_bytes_verified", True),
            ("full_pdf_human_fidelity_review_complete", True),
            ("editorial_inclusion_approved", True),
        ):
            receipt = approved_snapshot()
            receipt[field] = new
            with self.subTest(field=field), self.assertRaisesRegex(
                JapanSundayAuditError, "nonapproval contract"
            ):
                attest(week_ending=WEEK, as_of=WEEK, snapshot=receipt)

    def test_missing_immutable_git_snapshot_fails_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(JapanSundayAuditError):
                attest(week_ending=WEEK, as_of=WEEK,
                       state_repo=Path(temp))

    def test_duplicate_or_missing_research_ids_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet_at(tmp, lambda doc: doc["items"].pop(0))
            with self.assertRaises(JapanSundayAuditError):
                attest(week_ending=WEEK, as_of=WEEK,
                       directory=tmp, snapshot=approved_snapshot())

    def test_cli_refuses_overwrite_before_opening_git_source(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "receipt.json"
            output.write_text("hold")
            with self.assertRaises(SystemExit):
                main(["--week-ending", WEEK, "--as-of", WEEK,
                      "--state-repo", temp, "--output", str(output)])
            self.assertEqual(output.read_text(), "hold")


if __name__ == "__main__":
    unittest.main()
