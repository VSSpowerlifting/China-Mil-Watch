"""Offline verified-receipt → regional source HOLD reconciliation; no AI/SMTP."""
from __future__ import annotations

import copy
import json
import unittest

from core.regional_typed_machine_receipts import (
    MachineReceiptError, reconcile_machine_receipts,
)
from core.regional_typed_research_holds import audit_typed_holds
from scripts.attest_japan_sunday_research import attest
from scripts.prepare_vietnam_briefs_evidence import canonical_json
from tests.test_japan_sunday_source_attestation import approved_snapshot
from tests.test_regional_typed_research_holds import fixture
from tests.test_vietnam_briefs_evidence_feeder import queue as fake_queue, NOTES

WEEK = "2026-10-10"
OCT5 = "46f6a0e59e25b03868bf7ad600963d6921ee5124"
OCT7 = "c7c13dc7c15d855412afff99db23695dd50e51a5"


def holds_and_rows():
    inventory, raw = fixture()
    return audit_typed_holds(inventory, raw), raw


def japan_receipt():
    return attest(week_ending=WEEK, as_of=WEEK,
                  snapshot=approved_snapshot())


def seal(queue):
    import hashlib
    q = copy.deepcopy(queue)
    q.pop("queue_sha256", None)
    q["queue_sha256"] = hashlib.sha256(canonical_json(q).encode()).hexdigest()
    return q


def queue_at(commit, identity):
    q = fake_queue()
    q["state_commit"] = commit
    q["records"] = [r for r in q["records"]
                    if r["source_identity"] in identity]
    if "mps-vi:1791366010" in identity:
        note = next(n for n in NOTES["entries"]
                    if n["source_identity"] == "mps-vi:1791366010")
        q["records"].append({
            "source_slug": "vn_mps_foreign_affairs_vi",
            "source_identity": note["source_identity"],
            "canonical_url": note["source_url"],
            "published_date": note["published_date"],
            "title_original": "Thông tin Bộ Công an",
            "content_sha256": note["content_sha256"],
            "body_status": "text", "machine_review_candidate": True,
            "machine_blockers": [], "human_source_reviewed": False,
            "reuse_rights_reviewed": False,
            "production_publication_authorized": False,
        })
    q["record_count"] = len(q["records"])
    return seal(q)


class RegionalMachineReceiptTests(unittest.TestCase):
    def test_every_missing_external_receipt_stays_held(self):
        holds, raw = holds_and_rows()
        report = reconcile_machine_receipts(holds)
        self.assertEqual(len(report["items"]), 6)
        self.assertFalse(report["model_input_authorized"])
        self.assertFalse(report["editor_email_authorized"])
        self.assertFalse(report["production_desk_promoted"])
        self.assertFalse(report["publication_authorized"])
        self.assertTrue(all(x["eligible_for_regional_model"] is False
                            for x in report["items"]))
        self.assertTrue(all(x["machine_reconciliation"] ==
                            "independent_machine_receipt_missing" or
                            "review_queue_not_supplied" in x["machine_reconciliation"]
                            for x in report["items"]))
        data = json.dumps(report, ensure_ascii=False)
        for item in raw:
            self.assertNotIn(item["source_url"], data)
            self.assertNotIn(item["summary"], data)
            self.assertNotIn(item["title_original"], data)

    def test_japan_checked_historical_extraction_not_pdf_bytes_or_rights(self):
        holds, _ = holds_and_rows()
        report = reconcile_machine_receipts(holds, japan=japan_receipt())
        japan = [x for x in report["items"] if x["desk"] == "japan"]
        self.assertEqual(len(japan), 3)
        self.assertEqual(sum(x["machine_reconciliation"] ==
            "historical_extracted_text_digest_machine_checked_only"
            for x in japan), 1)
        self.assertEqual(sum(x["machine_reconciliation"] ==
            "publisher_metadata_only_original_body_missing"
            for x in japan), 2)
        self.assertTrue(report["original_publisher_current_version_not_proven"])
        self.assertTrue(report["source_reuse_approval_pending"])
        self.assertFalse(report["model_input_authorized"])

    def test_japan_receipt_identity_drift_and_forged_approvals_refused(self):
        holds, _ = holds_and_rows()
        jp = japan_receipt()
        for field, value in [
            ("status", "no_japan_packet_for_this_week"),
            ("week_ending", "2026-10-17"),
            ("human_source_review_completed", True),
            ("editorial_inclusion_approved", True),
            ("japan_production_eligible", True),
            ("archived_original_pdf_bytes_verified", True),
            ("smtp_or_production_writes", 1),
        ]:
            altered = copy.deepcopy(jp)
            altered[field] = value
            with self.subTest(field=field), self.assertRaises(MachineReceiptError):
                reconcile_machine_receipts(holds, japan=altered)
        for field, value in [
            ("publisher_url", "https://www.mod.go.jp/en/altered.html"),
            ("publication_date", "2026-10-04"),
        ]:
            altered = copy.deepcopy(jp)
            altered["evidence"][0][field] = value
            with self.subTest(field=field), self.assertRaises(MachineReceiptError):
                reconcile_machine_receipts(holds, japan=altered)
        altered = copy.deepcopy(jp)
        pdf = next(x for x in altered["evidence"] if x["id"] == "JP-W41-06")
        pdf["text_sha256"] = "0" * 64
        with self.assertRaises(MachineReceiptError):
            reconcile_machine_receipts(holds, japan=altered)

    def test_two_distinct_vietnam_state_commit_queues_can_reconcile_week(self):
        holds, _ = holds_and_rows()
        q5 = queue_at(OCT5, ("mps-vi:1791199100", "mps-vi:1791199677"))
        q7 = queue_at(OCT7, ("mps-vi:1791366010",))
        report = reconcile_machine_receipts(
            holds, japan=japan_receipt(), vietnam_queues=[q5, q7])
        self.assertEqual(report["vietnam_queue_commits_supplied"],
                         sorted([OCT5, OCT7]))
        vn = [x for x in report["items"] if x["desk"] == "vietnam"]
        self.assertEqual(len(vn), 3)
        self.assertTrue(all(x["machine_reconciliation"] ==
                "queue_version_machine_eligible_not_human_approved" for x in vn))
        self.assertFalse(report["model_input_authorized"])
        self.assertTrue(report["human_original_language_review_pending"])

    def test_missing_oct7_queue_is_explicitly_missing_not_backfilled(self):
        holds, _ = holds_and_rows()
        q5 = queue_at(OCT5, ("mps-vi:1791199100", "mps-vi:1791199677"))
        report = reconcile_machine_receipts(holds, vietnam_queues=[q5])
        vn = {x["id"]: x for x in report["items"] if x["desk"] == "vietnam"}
        self.assertEqual(
            vn["VN-MPS-1791366010"]["machine_reconciliation"],
            "exact_historical_commit_review_queue_not_supplied")
        self.assertFalse(vn["VN-MPS-1791366010"]["eligible_for_regional_model"])

    def test_queue_tampering_and_false_rights_rejected(self):
        holds, _ = holds_and_rows()
        q5 = queue_at(OCT5, ("mps-vi:1791199100", "mps-vi:1791199677"))
        corrupt = copy.deepcopy(q5)
        corrupt["records"][0]["content_sha256"] = "0" * 64
        with self.assertRaises(MachineReceiptError):
            reconcile_machine_receipts(holds, vietnam_queues=[corrupt])
        corrupt = seal(corrupt)
        with self.assertRaisesRegex(MachineReceiptError, "stale"):
            reconcile_machine_receipts(holds, vietnam_queues=[corrupt])
        for flag in ("human_source_reviewed", "reuse_rights_reviewed",
                     "production_publication_authorized"):
            corrupt = copy.deepcopy(q5)
            corrupt["records"][0][flag] = True
            with self.subTest(flag=flag), self.assertRaises(MachineReceiptError):
                reconcile_machine_receipts(
                    holds, vietnam_queues=[seal(corrupt)])

    def test_duplicate_foreign_vietnam_state_and_unmatched_source_refused(self):
        holds, _ = holds_and_rows()
        q5 = queue_at(OCT5, ("mps-vi:1791199100", "mps-vi:1791199677"))
        with self.assertRaisesRegex(MachineReceiptError, "duplicated"):
            reconcile_machine_receipts(holds, vietnam_queues=[q5, q5])
        foreign = copy.deepcopy(q5)
        foreign["state_commit"] = "0" * 40
        with self.assertRaisesRegex(MachineReceiptError, "unrelated"):
            reconcile_machine_receipts(holds, vietnam_queues=[seal(foreign)])
        missing = queue_at(OCT5, ("mps-vi:1791199100",))
        with self.assertRaisesRegex(MachineReceiptError, "absent"):
            reconcile_machine_receipts(holds, vietnam_queues=[missing])

    def test_fake_approval_holds_are_rejected_before_receipts(self):
        holds, _ = holds_and_rows()
        for field, val in (
            ("model_input_authorized", True),
            ("publication_authorized", True),
            ("editor_email_authorized", True),
            ("japan_vietnam_production_activated", True),
        ):
            altered = copy.deepcopy(holds)
            altered[field] = val
            with self.subTest(field=field), self.assertRaises(MachineReceiptError):
                reconcile_machine_receipts(altered)

    def test_no_other_week_can_inherit_oct10_japan_attestation(self):
        holds, _ = holds_and_rows()
        altered = copy.deepcopy(holds)
        altered["week_ending"] = "2026-10-17"
        with self.assertRaises(MachineReceiptError):
            reconcile_machine_receipts(altered, japan=japan_receipt())


if __name__ == "__main__":
    unittest.main()
