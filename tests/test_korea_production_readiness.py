"""Synthetic, offline contracts for a truthful Korea Desk readiness witness."""
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from core.korea_english_publication import (
    REGISTER, verify_review,
)
from core.korea_published_originals import SCHEMA as ORIGINAL_SCHEMA
from scripts.audit_korea_production_readiness import (
    AuditHold, SCHEMA, assess,
)
from scripts.send_korea_english_owner_drafts import SCHEMA as DELIVERY_SCHEMA
from tests.test_korea_english_publication import (
    ID, TEXT, make_review, make_source,
)


class KoreaProductionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.research = self.root / "research"
        (self.research / "korea_published_original_texts").mkdir(parents=True)
        (self.research / "korea_english_reviewed").mkdir()
        self.originals = []
        self.reviews = []
        self.receipts = []
        self.save()

    def save(self):
        (self.research / "korea_published_original_texts.json").write_text(
            json.dumps({"schema": ORIGINAL_SCHEMA, "records": self.originals}))
        (self.research / "korea_english_publications.json").write_text(
            json.dumps({"schema": REGISTER, "releases": self.reviews}))
        (self.research / "korea_english_draft_handoff_receipts.json").write_text(
            json.dumps({"schema": DELIVERY_SCHEMA, "delivered": self.receipts}))

    def add_original(self, number="156784297", text=TEXT):
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        row = {
            "source_identity": "korea-policy:" + number,
            "official_url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + number,
            "publisher_posted_date": "2026-10-15",
            "source_git_commit": "a" * 40,
            "original_text_sha256": digest,
            "policy_sha256": "b" * 64,
            "source_html_sha256": "c" * 64,
            "release_decision_sha256": "d" * 64,
            "released_at_utc": "2026-10-16T01:00:00Z",
        }
        self.originals.append(row)
        (self.research / "korea_published_original_texts" /
         (number + ".txt")).write_text(text, encoding="utf-8")
        self.save()
        return row

    def deliver(self, row):
        self.receipts.append({
            "source_identity": row["source_identity"],
            "source_sha256": row["original_text_sha256"],
            "draft_sha256": "e" * 64,
            "model_id": "synthetic-test-model",
            "delivered_at_utc": "2026-10-16T02:00:00Z",
        })
        self.save()

    def release(self, row):
        review = make_review()
        self.assertEqual(row["source_identity"], ID)
        digest = verify_review(review, make_source())["review_sha256"]
        (self.research / "korea_english_reviewed" / "156784297.json").write_text(
            json.dumps(review, ensure_ascii=False), encoding="utf-8")
        self.reviews.append({
            "source_identity": row["source_identity"],
            "source_sha256": row["original_text_sha256"],
            "review_sha256": digest,
            "owner_run_id": "38962141958",
            "released_at_utc": "2026-10-16T03:00:00Z",
        })
        self.save()

    def run_audit(self):
        return assess(self.root, as_of=date(2026, 10, 16))

    def test_empty_registry_never_claims_full_production(self):
        got = self.run_audit()
        self.assertEqual(got["schema"], SCHEMA)
        self.assertEqual(got["status"], "NO_PUBLISHED_ORIGINALS")
        self.assertEqual(got["reviewed_coverage_pct"], 0)
        self.assertFalse(got["full_desk_production_ready"])

    def test_offline_ledger_reconciliation_tracks_each_editorial_stage(self):
        first = self.add_original()
        self.add_original("156785286", TEXT + "\n" + TEXT)
        got = self.run_audit()
        self.assertEqual(got["private_drafts_not_delivered"], 2)
        self.deliver(first)
        got = self.run_audit()
        self.assertEqual(got["private_drafts_delivered_pending_review"], 1)
        self.assertEqual(got["private_drafts_not_delivered"], 1)
        self.assertEqual(got["reviewed_english_published"], 0)
        self.assertEqual(got["reviewed_coverage_pct"], 0)
        self.release(first)
        got = self.run_audit()
        self.assertEqual(got["reviewed_english_published"], 1)
        self.assertEqual(got["private_drafts_delivered_pending_review"], 0)
        self.assertEqual(got["private_drafts_not_delivered"], 1)
        self.assertEqual(got["reviewed_coverage_pct"], 50.0)
        self.assertEqual(got["online_https_readback"], "NOT_CHECKED")
        self.assertFalse(got["full_desk_production_ready"])

    def test_unregistered_machine_file_never_counts_as_reviewed(self):
        row = self.add_original()
        self.deliver(row)
        (self.research / "korea_english_reviewed" /
         "156784297.json").write_text(json.dumps(make_review()))
        got = self.run_audit()
        self.assertEqual(got["reviewed_english_published"], 0)
        self.assertEqual(got["private_drafts_delivered_pending_review"], 1)

    def test_drifted_receipt_is_a_hold_not_a_pending_label(self):
        row = self.add_original()
        self.deliver(row)
        self.receipts[0]["source_sha256"] = "f" * 64
        self.save()
        with self.assertRaisesRegex(
                AuditHold, "korea_readiness_receipt_source_version_mismatch"):
            self.run_audit()

    def test_orphan_receipt_does_not_manufacture_a_published_source(self):
        row = self.add_original()
        self.deliver(row)
        self.receipts[0]["source_identity"] = "korea-policy:123456789"
        self.save()
        with self.assertRaisesRegex(AuditHold, "korea_readiness_orphan_delivery"):
            self.run_audit()

    def test_changed_original_bytes_fail_instead_of_reporting_coverage(self):
        self.add_original()
        path = self.research / "korea_published_original_texts" / "156784297.txt"
        path.write_text(TEXT + "tampered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "korea_public_original_text_hash_drift"):
            self.run_audit()

    def test_output_is_metadata_only(self):
        row = self.add_original()
        self.deliver(row)
        report = json.dumps(self.run_audit(), ensure_ascii=False)
        self.assertIn(row["source_identity"], report)
        self.assertNotIn(TEXT, report)
        self.assertNotIn("translation", report)
        self.assertNotIn("text_en", report)
        self.assertNotIn("analysis_en", report)


if __name__ == "__main__":
    unittest.main()
