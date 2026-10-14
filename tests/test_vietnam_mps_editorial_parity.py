"""Synthetic-only Vietnam MPS live/parity screening tests (no source prose)."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import probe_vietnam_mps_editorial_parity as parity


def doc(title="Synthetic ministry title", body="Synthetic article prose", day="2026-10-05",
        original_hash="a" * 64, byline=None):
    return SimpleNamespace(
        title_original=title, text_original=body, published_date=day,
        extra={"content_sha256":original_hash, "byline":byline},
    )


REC = {
    "source_identity": "mps-vi:1791199100",
    "canonical_url": "https://bocongan.gov.vn/bai-viet/synthetic-1791199100",
    "published_date": "2026-10-05",
}
VERS = {
    "content_sha256": "a" * 64,
    "first_capture_sha256": "b" * 64,
    "title_original": "Synthetic ministry title",
    "text_original": "Synthetic article prose",
}


class TestMPSParity(unittest.TestCase):
    def test_true_machine_parity_is_not_human_approval(self):
        result = parity.compare_record(REC, VERS, doc(), doc())
        self.assertTrue(result["archive_title_matches_stored"])
        self.assertTrue(result["archive_body_matches_stored"])
        self.assertTrue(result["archive_date_matches_stored"])
        self.assertTrue(result["archive_version_digest_matches_stored"])
        self.assertTrue(result["live_title_matches_pinned"])
        self.assertTrue(result["live_body_matches_pinned"])
        self.assertTrue(result["live_published_date_matches_pinned"])
        self.assertTrue(result["live_version_digest_matches_pinned"])
        self.assertFalse(result["human_integrity_review_complete"])
        self.assertFalse(result["reuse_rights_approved"])
        self.assertFalse(result["production_publication_authorized"])
        self.assertNotIn("Synthetic article prose", str(result))
        self.assertNotIn("Synthetic ministry title", str(result))

    def test_live_changed_prose_is_preserved_as_negative_not_approved(self):
        mismatch = parity.compare_record(REC, VERS, doc(), doc(body="Revised prose"))
        self.assertTrue(mismatch["archive_body_matches_stored"])
        self.assertFalse(mismatch["live_body_matches_pinned"])
        self.assertFalse(mismatch["human_integrity_review_complete"])
        self.assertEqual(mismatch["live_metrics"]["body_characters"], len("Revised prose"))

    def test_mismatched_archived_snapshot_also_a_hold(self):
        mismatch = parity.compare_record(REC, VERS, doc(title="Wrong archived title"), None)
        self.assertFalse(mismatch["archive_title_matches_stored"])
        self.assertIsNone(mismatch["live_body_matches_pinned"])
        self.assertEqual(mismatch["live_access_and_extraction"], "not_run")

    def test_absent_parsing_cannot_be_claimed_as_true(self):
        result = parity.compare_record(REC, VERS, None, None)
        self.assertFalse(result["archived_capture_reparse_complete"])
        self.assertIsNone(result["archive_body_matches_stored"])
        self.assertIsNone(result["live_body_matches_pinned"])

    def test_metrics_include_only_hashes_and_lengths(self):
        parsed = doc(byline="Synthetic reporter name")
        result = parity.compare_record(REC, VERS, parsed, parsed)
        self.assertEqual(
            result["live_metrics"]["body_sha256"],
            hashlib.sha256(b"Synthetic article prose").hexdigest())
        self.assertEqual(result["live_metrics"]["body_characters"],
                         len("Synthetic article prose"))
        self.assertNotIn("Synthetic reporter name", str(result))
        self.assertTrue(result["live_metrics"]["source_byline_meta_sha256"])

    def test_foreign_urls_are_refused_before_transport(self):
        session = SimpleNamespace()
        for url in ("http://bocongan.gov.vn/robots.txt",
                    "https://other.example/robots.txt",
                    "https://bocongan.gov.vn/test?bypass=1",
                    "https://bocongan.gov.vn/test#x"):
            with self.subTest(url=url), self.assertRaisesRegex(parity.ScreeningRefused, "host/path"):
                parity.safe_fetch(session, url)

    def test_output_inside_repo_or_existing_refused_before_git(self):
        with tempfile.TemporaryDirectory() as path:
            dest = Path(path) / "existing.json"
            dest.write_text("keep")
            with self.assertRaisesRegex(parity.ScreeningRefused, "new and outside"):
                parity.screen(path, parity.PINNED, dest)
            with self.assertRaisesRegex(parity.ScreeningRefused, "new and outside"):
                parity.screen(path, parity.PINNED, parity.ROOT / "mps-report.json")

    def test_different_commit_refused_before_git(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaisesRegex(parity.ScreeningRefused, "pinned"):
                parity.screen(path, "0" * 40, Path(path) / "new.json")


if __name__ == "__main__":
    unittest.main()
