"""Structural contracts for Japan space-security SOURCE DISCOVERY only.

There are no archived source-body fixtures and no human-reviewed labels here.
"""
from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import validate_topic_v2_japan_space as audit  # noqa: E402


class JapanSpaceProspectus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        cls.packet = json.loads(audit.PACKET.read_text(encoding="utf-8"))
        cls.vocab = json.loads(audit.VOCAB.read_text(encoding="utf-8"))

    def clone(self):
        return copy.deepcopy(self.packet)

    def assert_rejected(self, packet, phrase):
        with self.assertRaisesRegex(audit.AdmissionError, phrase):
            audit.validate(packet, self.vocab)

    def test_authored_leads_are_unarchived_and_unapproved(self):
        result = audit.validate(self.clone(), self.vocab)
        self.assertEqual(result["candidate_source_documents"], 6)
        self.assertEqual(result["distinct_event_or_policy_contexts"], 5)
        self.assertEqual(result["source_bodies_pinned"], 0)
        self.assertFalse(result["authoritative_archive_coverage_verified"])
        self.assertEqual(result["records_human_approved"], 0)

    def test_documented_cli_direct_script(self):
        run = subprocess.run(
            [sys.executable, str(audit.ROOT / "scripts/validate_topic_v2_japan_space.py")],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('"source_bodies_pinned": 0', run.stdout)

    def test_every_source_is_structurally_unique(self):
        rows = self.clone()["candidates"]
        self.assertEqual(len({r["id"] for r in rows}), 6)
        self.assertEqual(len({r["url"] for r in rows}), 6)
        self.assertTrue(all(r["archive_identity"] is None and
                            r["body_sha256"] is None and
                            r["owner_approval"] is None for r in rows))

    def test_event_grouping_does_not_double_count_formation(self):
        rows = self.clone()["candidates"]
        a = next(r for r in rows if r["id"] == "JSP02")
        b = next(r for r in rows if r["id"] == "JSP03")
        self.assertEqual(a["review_context_key"], b["review_context_key"])
        b["review_context_key"] = "fake_second_independent_event"
        self.assert_rejected({**self.clone(), "candidates": rows}, "pinned source/role/context drift")

    def test_tampered_source_urls_roles_or_issuers_fail(self):
        for key, value in (
            ("url", "https://not-official.example/file"),
            ("candidate_role", "approved_positive"),
            ("review_context_key", "independent_duplicate"),
            ("issuer_key", "fabricated_unit"),
        ):
            packet = self.clone()
            packet["candidates"][0][key] = value
            with self.subTest(key=key):
                self.assert_rejected(packet, "pinned source/role/context drift")

    def test_no_human_approval_or_collection_permission(self):
        for field in ("collection_authorized", "topic_assignments_authorized",
                      "human_review_complete"):
            packet = self.clone()
            packet[field] = True
            with self.subTest(field=field):
                self.assert_rejected(packet, "authorization or human review")
        packet = self.clone()
        packet["human_approvals"] = ["SYNTHETIC ONLY"]
        self.assert_rejected(packet, "no human approvals")
        packet = self.clone()
        packet["candidates"][0]["owner_approval"] = "SYNTHETIC ONLY"
        self.assert_rejected(packet, "no archival identity or approvals")

    def test_archive_evidence_cannot_be_fabricated(self):
        for key, value in (("archive_identity", "made_up_record_100"),
                           ("body_sha256", "1" * 64),
                           ("review_state", "approved")):
            packet = self.clone()
            packet["candidates"][0][key] = value
            with self.subTest(key=key):
                self.assert_rejected(packet, "no archival identity or approvals")

    def test_exact_record_count_and_unique_ids(self):
        packet = self.clone()
        packet["candidates"].append(copy.deepcopy(packet["candidates"][0]))
        self.assert_rejected(packet, "six exact sources")
        packet = self.clone()
        packet["candidates"][1]["id"] = "JSP01"
        self.assert_rejected(packet, "duplicate or unknown candidate")
        packet = self.clone()
        packet["record_count"] = 7
        self.assert_rejected(packet, "incorrect sample/event totals")

    def test_version_and_subject_are_pinned(self):
        for field,value in (("subject_topic","economic_security"),
                            ("taxonomy_version",1),
                            ("archive_status","production_verified")):
            packet = self.clone()
            packet[field] = value
            with self.subTest(field=field):
                self.assert_rejected(
                    packet, "topic scope or taxonomy version|archival status")
        vocab = copy.deepcopy(self.vocab)
        vocab["taxonomy_version"] = 1
        with self.assertRaisesRegex(audit.AdmissionError, "version 2"):
            audit.validate(self.clone(), vocab)

    def test_undated_whitepaper_must_not_invent_exact_publication_date(self):
        for ident in ("JSP01", "JSP04"):
            packet = self.clone()
            record = next(r for r in packet["candidates"] if r["id"] == ident)
            record["source_date"] = "2026-01-01"
            record["date_precision"] = "day"
            with self.subTest(id=ident):
                self.assert_rejected(packet, "missing day date")

    def test_future_source_date_cannot_be_verified_past_cutoff(self):
        packet = self.clone()
        record = next(r for r in packet["candidates"] if r["id"] == "JSP06")
        record["source_date"] = "2026-10-20"
        self.assert_rejected(packet, "future or wrong-year")

    def test_no_extra_fields_can_claim_ingestion_or_accuracy(self):
        packet = self.clone()
        packet["classifier_accuracy"] = 1.0
        self.assert_rejected(packet, "packet schema")
        packet = self.clone()
        packet["candidates"][0]["gold_label"] = "space_security"
        self.assert_rejected(packet, "candidate schema")


if __name__ == "__main__":
    unittest.main()
