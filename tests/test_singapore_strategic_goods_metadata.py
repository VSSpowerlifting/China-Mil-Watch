"""Synthetic, offline mutation tests: no source bodies or human labels."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import validate_singapore_strategic_goods_metadata as v  # noqa: E402


class SingaporeGazetteMetadataReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(v.PACKET.read_text(encoding="utf-8"))
        cls.vocab = json.loads(v.VOCAB.read_text(encoding="utf-8"))

    def packet_copy(self):
        return copy.deepcopy(self.packet)

    def rejected(self, packet, phrase):
        with self.assertRaisesRegex(v.MetadataReviewError, phrase):
            v.validate(packet, self.vocab)

    def test_exact_two_document_one_succession_scope(self):
        out = v.validate(self.packet_copy(), self.vocab)
        self.assertEqual((out["source_documents"], out["regulatory_successions"]), (2, 1))
        self.assertEqual(out["source_bodies_stored"], 0)
        self.assertEqual(out["human_approvals"], 0)
        self.assertFalse(out["collection_enabled"])

    def test_cli(self):
        run = subprocess.run(
            [sys.executable, str(v.ROOT / "scripts/validate_singapore_strategic_goods_metadata.py")],
            cwd=v.ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('"source_documents": 2', run.stdout)

    def test_source_identity_and_original_pdf(self):
        for key, value in (("official_pdf_url", "https://other.example/fake.pdf"),
                           ("gazette_number", "S 1/2025"),
                           ("revokes_gazette_number", "S 660/2025")):
            p = self.packet_copy()
            p["documents"][0][key] = value
            with self.subTest(key=key):
                self.rejected(p, "pinned original Gazette")

    def test_2026_future_commencement_cannot_be_backdated(self):
        p = self.packet_copy()
        p["documents"][1]["commences_on"] = "2026-10-01"
        self.rejected(p, "pinned original Gazette")
        p = self.packet_copy()
        p["documents"][1]["status_as_of_research_date"] = "effective_predecessor"
        self.rejected(p, "pinned original Gazette")

    def test_rights_permission_is_conditional(self):
        p = self.packet_copy()
        p["source_use_review"]["relevant_clauses"] = ["11"]
        self.rejected(p, "Gazette terms gate")
        p = self.packet_copy()
        p["source_use_review"]["observed_conditions"].remove(
            "permission_revocable_or_modifiable")
        self.rejected(p, "Gazette terms gate")

    def test_rights_have_no_ipr_signoff(self):
        for key in ("ipr_use_compliance_adjudicated", "full_body_retention_approved",
                    "public_body_display_approved", "automated_collection_approved"):
            p = self.packet_copy()
            p["source_use_review"][key] = True
            with self.subTest(key=key):
                self.rejected(p, "source-use signoff")

    def test_no_collector_or_editorial_approval(self):
        for key in ("human_source_review_complete", "topic_attachments_authorized",
                    "production_or_shadow_collection_authorized"):
            p = self.packet_copy()
            p[key] = True
            with self.subTest(key=key):
                self.rejected(p, "approval/archive")
        p = self.packet_copy()
        p["human_topic_approvals"] = ["fictional"]
        self.rejected(p, "approval/archive")

    def test_no_fabricated_immutable_evidence(self):
        for key, value in (("archive_record_id", "made-up"),
                           ("captured_pdf_sha256", "a" * 64),
                           ("captured_at_utc", "2026-10-08T12:00:00Z"),
                           ("human_topic_approval", "synthetic"),
                           ("archived_quote_offsets", [[0, 5]])):
            p = self.packet_copy()
            p["documents"][0][key] = value
            with self.subTest(key=key):
                self.rejected(p, "fabricated evidence/approval")

    def test_source_document_not_new_event(self):
        p = self.packet_copy()
        p["distinct_regulatory_succession_count"] = 2
        self.rejected(p, "two orders one succession")
        p = self.packet_copy()
        p["documents"][1]["regulatory_context_key"] = "invented_independent_event"
        self.rejected(p, "context grouping")

    def test_extra_claims_and_source_body_fail(self):
        p = self.packet_copy()
        p["collection_success"] = True
        self.rejected(p, "packet schema")
        p = self.packet_copy()
        p["documents"][0]["complete_pdf_text"] = "unapproved content"
        self.rejected(p, "document schema")

    def test_taxonomy_v2_required(self):
        vocab = copy.deepcopy(self.vocab)
        vocab["taxonomy_version"] = 1
        with self.assertRaisesRegex(v.MetadataReviewError, "v2 taxonomy"):
            v.validate(self.packet_copy(), vocab)


if __name__ == "__main__":
    unittest.main()
