"""Offline real-HWPX reviewer-package privacy and fail-closed contracts."""
import copy
import hashlib
import json
import stat
import tempfile
import unittest
from pathlib import Path

from core import korea_reference_gate as gate
from scripts import prepare_korea_human_review as pkg
from tests.test_korea_source_fidelity import KoreaSourceFidelityTests

ROOT = Path(__file__).resolve().parents[1]


class LocalKoreaReviewerPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-korea-review-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state, self.record = KoreaSourceFidelityTests().make_record(self.root)
        self.candidate = {
            "source_identity": self.record["source_identity"],
            "source_slug": self.record["source_slug"],
            "source_url": self.record["url"],
            "title_original": self.record["title_original"],
            "language": "ko",
            "published_date": self.record["published_date"],
            "document_distribution_date": "2026-10-04",
            "content_sha256": self.record["content_sha256"],
            "document_capture_sha256": self.record["metadata"]["document_capture_sha256"],
            "issuer": "국방부", "publisher": "대한민국 정책브리핑",
        }

    def test_genuine_fixture_hwpx_parity_and_local_handoff(self):
        hwpx, text = pkg.confirm_original(self.candidate, self.record, self.state)
        self.assertEqual(pkg.sha(hwpx), self.candidate["document_capture_sha256"])
        self.assertEqual(pkg.sha(text.encode("utf-8")), self.candidate["content_sha256"])
        self.assertGreater(len(hwpx), 200)
        check = pkg.checklist(self.candidate)
        self.assertIn("10월 4일", check)
        self.assertIn("10월 6일", check)
        self.assertIn("실제 요격", check)
        self.assertIn(self.candidate["document_capture_sha256"], check)

    def test_local_bundle_never_prepopulates_approvals(self):
        blank = pkg.make_blank(self.candidate)
        self.assertFalse(blank["human_korean_review"]["rendered_hwpx_compared"])
        self.assertFalse(blank["source_rights_review"]["intended_use_approved"])
        self.assertFalse(blank["owner_publication_approval"]["explicit_approval_for_reference_only"])
        self.assertEqual(blank["human_korean_review"]["reviewer"], "")
        self.assertIsNone(blank["human_korean_review"]["reviewed_at_utc"])
        self.assertEqual(blank["english_description"], "")
        self.assertEqual(blank["evidence_anchors"], [])
        self.assertFalse(blank["human_korean_review"]["evidence_anchors_checked"])
        self.assertEqual(set(blank), {
            "source_identity", "content_sha256", "document_capture_sha256",
            "human_korean_review", "source_rights_review",
            "owner_publication_approval", "evidence_anchors",
            "english_description",
        })
        # No paper-thin "reviewer exists" shortcut can make this admissible.
        packet = self.root / "unapproved.json"
        packet.write_text(json.dumps({
            "schema": gate.APPROVAL_SCHEMA,
            "state_commit": gate.STATE_SHA, "entries": [blank],
        }))
        with self.assertRaises(gate.KoreaGateHold):
            gate.approve(gate.load_candidates(), packet)

    def test_line_index_is_private_metadata_only(self):
        text = "첫 문장\n\n두번째 문장\n"
        index = pkg.original_line_index(self.candidate, text)
        self.assertEqual([x["line_number"] for x in index["lines"]], [1, 3])
        self.assertEqual(index["lines"][0]["line_sha256"], pkg.sha("첫 문장".encode("utf-8")))
        self.assertEqual(index["lines"][1]["line_sha256"], pkg.sha("두번째 문장".encode("utf-8")))
        self.assertEqual(index["content_sha256"], self.candidate["content_sha256"])
        self.assertNotIn("첫 문장", json.dumps(index, ensure_ascii=False))
        with self.assertRaises(gate.KoreaGateHold):
            pkg.original_line_index(self.candidate, " \n")

    def test_tampering_or_mismatched_original_blocked(self):
        cases = [
            {"title_original": "허위 보도자료"},
            {"document_capture_sha256": "a"*64},
            {"content_sha256": "a"*64},
            {"source_url": "https://www.mnd.go.kr/press"},
            {"published_date": "2026-10-07"},
        ]
        for changed in cases:
            with self.subTest(changed=changed):
                candidate = dict(self.candidate, **changed)
                with self.assertRaises(gate.KoreaGateHold):
                    pkg.confirm_original(candidate, self.record, self.state)

    def test_private_dest_only_outside_repo_and_never_overwrites(self):
        for bad in (ROOT / "illegal-source-review", self.root):
            with self.subTest(destination=str(bad)), self.assertRaises(gate.KoreaGateHold):
                pkg.output_ok(bad)
        filename = self.root / "private.txt"
        pkg.private_write(filename, b"private original bytes")
        self.assertEqual(stat.S_IMODE(filename.stat().st_mode), 0o600)
        with self.assertRaises(gate.KoreaGateHold):
            pkg.private_write(filename, b"overwritten")
        symlink = self.root / "symlinked"
        symlink.symlink_to(filename)
        with self.assertRaises(gate.KoreaGateHold):
            pkg.output_ok(symlink)

    def test_metadata_receipt_contains_no_document_bodies(self):
        source = pkg.checklist(self.candidate)
        self.assertNotIn(self.record["text_original"], source)
        self.assertNotIn("text_original", json.dumps(pkg.make_blank(self.candidate)))


if __name__ == "__main__":
    unittest.main()
