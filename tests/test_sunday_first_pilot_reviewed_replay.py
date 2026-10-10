"""Offline, no SMTP and no model tests for the first-edition approved-file replay."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_first_pilot_reviewed_replay import (
    ReplayRefused, inspect_file, replay,
)
from scripts.sunday_pilot_owner_review import OwnerReviewRequired
from tests.test_sunday_editor_readable import reviewed_packet

SAT = "2026-10-10"


class FirstSundayPrivateReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "owner-reviewed.txt"
        self.original = reviewed_packet().encode("utf-8")
        self.path.write_bytes(self.original)

    def test_preview_read_only_does_not_call_smtp_or_writer(self):
        with patch("scripts.sunday_editorial_handoff.send_packet") as send, \
             patch("scripts.sunday_briefs_auto_writer.compose") as model:
            result = replay(self.path)
        self.assertEqual(result["state"], "review-only")
        self.assertEqual(result["sha256"], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(self.path.read_bytes(), self.original)
        send.assert_not_called()
        model.assert_not_called()

    def test_explicit_send_is_exact_original_and_no_model_generation(self):
        env = {
            "IPR_SUNDAY_REPLAY_DELIVERY_APPROVED": "true",
            "IPR_SUNDAY_OWNER_REVIEWED_WEEK": SAT,
            "IPR_SUNDAY_OWNER_REVIEWED_SHA256": hashlib.sha256(self.original).hexdigest(),
        }
        with patch.dict(os.environ, env, clear=True), \
             patch("scripts.sunday_editorial_handoff.send_packet") as smtp, \
             patch("scripts.sunday_briefs_auto_writer.compose") as model:
            result = replay(self.path, send=True)
        self.assertEqual(result["state"], "handed-to-SMTP")
        smtp.assert_called_once_with(self.path, SAT, full_week=True)
        model.assert_not_called()
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_missing_opt_in_fails_before_sender(self):
        env = {
            "IPR_SUNDAY_OWNER_REVIEWED_WEEK": SAT,
            "IPR_SUNDAY_OWNER_REVIEWED_SHA256": hashlib.sha256(self.original).hexdigest(),
        }
        with patch.dict(os.environ, env, clear=True), \
             patch("scripts.sunday_editorial_handoff.send_packet") as smtp:
            with self.assertRaisesRegex(ReplayRefused, "opt-in"):
                replay(self.path, send=True)
        smtp.assert_not_called()

    def test_wrong_owner_week_or_sha_rejected_before_sender(self):
        correct = hashlib.sha256(self.original).hexdigest()
        for approved_week, digest in (
            ("", correct), ("2026-10-03", correct), (SAT, "0" * 64), (SAT, "")
        ):
            env = {
                "IPR_SUNDAY_REPLAY_DELIVERY_APPROVED": "true",
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": approved_week,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": digest,
            }
            with self.subTest(week=approved_week, digest=digest[:5]), \
                 patch.dict(os.environ, env, clear=True), \
                 patch("scripts.sunday_editorial_handoff.send_packet") as smtp:
                with self.assertRaises(OwnerReviewRequired):
                    replay(self.path, send=True)
                smtp.assert_not_called()

    def test_tampering_with_reviewed_text_refuses_original_hash(self):
        original_digest = hashlib.sha256(self.original).hexdigest()
        edited = self.original.replace(b"## WHAT STOOD OUT", b"## WHAT STOOD OUT\nNew paragraph.")
        self.path.write_bytes(edited)
        env = {
            "IPR_SUNDAY_REPLAY_DELIVERY_APPROVED": "true",
            "IPR_SUNDAY_OWNER_REVIEWED_WEEK": SAT,
            "IPR_SUNDAY_OWNER_REVIEWED_SHA256": original_digest,
        }
        with patch.dict(os.environ, env, clear=True), \
             patch("scripts.sunday_editorial_handoff.send_packet") as smtp:
            with self.assertRaises(OwnerReviewRequired):
                replay(self.path, send=True)
            smtp.assert_not_called()

    def test_source_receipt_or_appendix_truncation_refused(self):
        original = self.original.decode("utf-8")
        mutations = [
            original.replace("=== MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY ===",
                             "MISSING RECEIPT"),
            original.replace("=== SOURCE APPENDIX — DO NOT EDIT ===",
                             "MISSING APPENDIX"),
            original.replace("END OF UNAPPROVED WORKSHEET",
                             "TRUNCATED", 1),
            original.replace("Packet: IPR-" + SAT,
                             "Packet: IPR-2026-10-03", 1),
            original.replace("SOURCE RECORD IDS:", "UNCITED:", 100)
                    .replace("EXTERNAL SOURCE IDS:", "UNCITED:", 100),
            "Not a manuscript",
        ]
        for item in mutations:
            self.path.write_text(item, encoding="utf-8")
            with self.subTest(item=item[:80]), self.assertRaises(ReplayRefused):
                inspect_file(self.path)

    def test_wrong_week_or_symlink_refused(self):
        with self.assertRaises(ReplayRefused):
            inspect_file(self.path, "2026-10-17")
        link = Path(self.tmp.name) / "link.txt"
        link.symlink_to(self.path)
        with self.assertRaises(ReplayRefused):
            inspect_file(link)
        self.path.write_bytes(self.original + b"\x00")
        with self.assertRaises(ReplayRefused):
            inspect_file(self.path)


if __name__ == "__main__":
    unittest.main()
