"""Formal Japan Coast Guard review receipts remain pinned and never approve."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.japan_jcg_pinned_review_receipt import make_receipt, main

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40
TREE = "b" * 40


def report():
    return {
        "mode": "formal_commit_snapshot",
        "desk": "japan_jcg",
        "state_ref": "shadow/japan-jcg",
        "state_commit": COMMIT,
        "state_tree": TREE,
        "as_of": "2026-10-08",
        "records": 3,
        "ledgers": 1,
        "findings": [],
        "review_holds": ["Human to verify publisher datetime template"],
        "missing_successful_days": [],
        "human_review_completed": False,
        "promotion_authorized": False,
        "input_hashes": {"state/shadow.db": "c" * 64},
    }


class JCGPinnedReviewReceiptTests(unittest.TestCase):
    def test_successful_integrity_check_is_not_human_approval(self):
        receipt = make_receipt(report(), COMMIT, "2026-10-08", "12345")
        self.assertEqual(receipt["state_commit"], COMMIT)
        self.assertEqual(receipt["state_tree"], TREE)
        self.assertEqual(receipt["reviewed_record_count"], 3)
        self.assertEqual(receipt["human_review_holds_count"], 1)
        self.assertEqual(receipt["machine_findings_count"], 0)
        self.assertEqual(receipt["machine_integrity_verdict"],
                         "checks_clear_not_human_approved")
        self.assertFalse(receipt["human_review_completed"])
        self.assertFalse(receipt["promotion_authorized"])
        self.assertFalse(receipt["production_database_changed"])
        self.assertFalse(receipt["editorial_release_authorized"])

    def test_machine_findings_stay_visible_and_unapproved(self):
        item = report()
        item["findings"] = ["Original-text hash mismatch"]
        receipt = make_receipt(item, COMMIT, "2026-10-08", "12345")
        self.assertEqual(receipt["machine_integrity_verdict"],
                         "integrity_findings_require_disposition")
        self.assertEqual(receipt["machine_findings_count"], 1)
        self.assertFalse(receipt["human_review_completed"])

    def test_zero_official_publications_can_be_reviewed_without_claiming_coverage(self):
        item = report()
        item["records"] = 0
        item["ledgers"] = 1
        receipt = make_receipt(item, COMMIT, "2026-10-08", "12345")
        self.assertEqual(receipt["reviewed_record_count"], 0)
        self.assertEqual(receipt["machine_integrity_verdict"],
                         "no_records_not_a_coverage_attestation")
        self.assertFalse(receipt["human_review_completed"])
        self.assertFalse(receipt["promotion_authorized"])

    def test_rejects_wrong_ref_wrong_head_wrong_cutoff(self):
        for key, value in (
            ("state_ref", "shadow/japan-mod"),
            ("desk", "japan"),
            ("state_commit", "d" * 40),
            ("state_tree", "not-a-commit"),
            ("as_of", "2026-10-09"),
            ("mode", "rehearsal"),
        ):
            item = report()
            item[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                make_receipt(item, COMMIT, "2026-10-08", "12345")

    def test_rejects_fabricated_human_attestation_and_empty_data(self):
        for key, value in (
            ("human_review_completed", True),
            ("promotion_authorized", True),
            ("records", -1),
            ("ledgers", -1),
            ("findings", "approved"),
            ("review_holds", None),
            ("missing_successful_days", 0),
        ):
            item = report()
            item[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                make_receipt(item, COMMIT, "2026-10-08", "12345")

    def test_sha_date_and_run_id_are_strict(self):
        for sha, day, run in (
            ("A" * 40, "2026-10-08", "123"),
            ("x" * 40, "2026-10-08", "123"),
            (COMMIT, "2026-02-30", "123"),
            (COMMIT, "2026-10-8", "123"),
            (COMMIT, "2026-10-08", "not-a-run"),
        ):
            with self.subTest(sha=sha, day=day, run=run), self.assertRaises(ValueError):
                make_receipt(report(), sha, day, run)

    def test_cli_outputs_only_receipt_and_never_source_records(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            src, output = root / "report.json", root / "receipt.json"
            src.write_text(json.dumps(report()) + "\n", encoding="utf-8")
            result = main([
                "--report", str(src), "--state-commit", COMMIT,
                "--as-of", "2026-10-08", "--actions-run-id", "12345",
                "--output", str(output),
            ])
            self.assertEqual(result, 0)
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(receipt["report_sha256"].__len__(), 64)
            self.assertNotIn("input_hashes", receipt)
            self.assertNotIn("text_original", json.dumps(receipt))
            with self.assertRaises(SystemExit):
                main([
                    "--report", str(src), "--state-commit", COMMIT,
                    "--as-of", "2026-10-08", "--actions-run-id", "12345",
                    "--output", str(output),
                ])

    def test_workflow_is_main_only_manual_and_metadata_only(self):
        workflow = (ROOT / ".github/workflows/japan_jcg_shadow_review_manual.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertNotIn("  schedule:", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("shadow/japan-jcg", workflow)
        self.assertIn("scripts/review_desk_shadow.py", workflow)
        self.assertIn("--state-commit", workflow)
        self.assertIn("records.jsonl", workflow)  # explicit exclusion comment
        artifact = workflow.split("path: |", 1)[1].split(
            "retention-days:", 1)[0]
        self.assertNotIn("records.jsonl", artifact)
        self.assertNotIn(".bin", artifact)
        self.assertIn("receipt.json", artifact)
        self.assertIn("formal/report.json", artifact)
        self.assertIn("formal/report.md", artifact)
        self.assertNotIn("git push ", workflow)
        self.assertNotIn("pla_watch.db", workflow)


if __name__ == "__main__":
    unittest.main()
