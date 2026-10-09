"""Offline proof: manual Sunday delivery resends EXACT verified owner-reviewed bytes."""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_editorial_handoff import render_packet
from scripts.sunday_send_reviewed_packet import (
    ReviewedHandoffRefused, handoff, inspect_reviewed_attachment,
    main, validate_file,
)
from tests.test_briefs_editorial_evidence import scaffold
from tests.test_weekly_briefs_auto_writer import valid_manuscript

WEEK = "2026-10-10"
SUNDAY = datetime(2026, 10, 11, 19, 17, tzinfo=timezone.utc)
THURSDAY = datetime(2026, 10, 15, 19, 17, tzinfo=timezone.utc)


def create_reviewed_packet(folder):
    path = Path(folder) / "IPR-Briefs-Editorial-2026-10-10.txt"
    text = render_packet(
        scaffold(), manuscript=valid_manuscript(), as_of=WEEK,
    )
    path.write_bytes(text.encode("utf-8"))
    return path


class ReviewedPacketManualHandoff(unittest.TestCase):
    def test_default_dry_run_has_receipt_and_no_model_or_smtp(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            with patch.dict(os.environ, {}, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as email:
                receipt = handoff(file, WEEK, now=SUNDAY)
            self.assertEqual(receipt["attachment_sha256"],
                             hashlib.sha256(file.read_bytes()).hexdigest())
            self.assertEqual(receipt["week_ending"], WEEK)
            self.assertFalse(receipt["email_sent"])
            self.assertFalse(receipt["automated_model_called"])
            self.assertFalse(receipt["exact_owner_approval_matches"])
            self.assertFalse(receipt["publication_authorized"])
            email.assert_not_called()

    def test_exact_reviewed_file_digest_and_week_both_required_to_send(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            true_digest = hashlib.sha256(file.read_bytes()).hexdigest()
            for wrong_week, wrong_digest in (
                ("", true_digest), ("2026-10-03", true_digest),
                (WEEK, ""), (WEEK, "A" * 64), (WEEK, "0" * 64),
                (WEEK, true_digest + " "),
            ):
                with self.subTest(wrong_week=wrong_week, digest=wrong_digest):
                    with patch.dict(os.environ, {
                        "IPR_SUNDAY_OWNER_REVIEWED_WEEK": wrong_week,
                        "IPR_SUNDAY_OWNER_REVIEWED_SHA256": wrong_digest,
                    }, clear=True), patch(
                        "scripts.sunday_send_reviewed_packet.send_packet"
                    ) as smtp:
                        with self.assertRaisesRegex(
                            ReviewedHandoffRefused, "exact approved"
                        ):
                            handoff(file, WEEK, send=True,
                                    owner_confirmed=True, now=SUNDAY)
                        smtp.assert_not_called()

    def test_mutation_after_owner_review_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            expected = hashlib.sha256(file.read_bytes()).hexdigest()
            text = file.read_text(encoding="utf-8")
            file.write_text(text.replace("Two institutions described",
                                         "Three institutions described"),
                            encoding="utf-8")
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": expected,
            }, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                with self.assertRaises(ReviewedHandoffRefused):
                    handoff(file, WEEK, send=True, owner_confirmed=True, now=SUNDAY)
                send.assert_not_called()

    def test_valid_approved_send_uses_exact_snapshot_and_never_generates(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            approved_bytes = file.read_bytes()
            digest = hashlib.sha256(approved_bytes).hexdigest()
            captured = []
            def fake_send(path, week_ending, *, provisional=False, full_week=False):
                captured.append((week_ending, path.read_bytes(), full_week, provisional))
                self.assertNotEqual(path, file)
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": digest,
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
            }, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet",
                side_effect=fake_send,
            ) as send:
                output = handoff(file, WEEK, send=True,
                                 owner_confirmed=True, now=SUNDAY)
            self.assertEqual(captured, [(WEEK, approved_bytes, True, True)])
            self.assertEqual(send.call_count, 1)
            self.assertTrue(output["email_sent"])
            self.assertFalse(output["automated_model_called"])
            self.assertFalse(output["publication_authorized"])

    def test_historical_manual_send_requires_additional_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": digest,
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
            }, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                with self.assertRaisesRegex(
                    ReviewedHandoffRefused, "allow-historical-send"
                ):
                    handoff(file, WEEK, send=True,
                            owner_confirmed=True, now=THURSDAY)
                self.assertFalse(
                    handoff(file, WEEK, now=THURSDAY)["email_sent"]
                )
                self.assertTrue(handoff(
                    file, WEEK, send=True, owner_confirmed=True,
                    historical_override=True, now=THURSDAY,
                )["email_sent"])
                self.assertEqual(send.call_count, 1)

    def test_manual_send_refuses_parallel_friday_or_same_owner_recipient(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            approved = hashlib.sha256(file.read_bytes()).hexdigest()
            baseline = {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": approved,
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
            }
            for override, expected in (
                ({"IPR_EDITOR_DELIVERY_ENABLED": "true"}, "parallel editor service"),
                ({"IPR_PREVIEW_TO": "EDITOR@example.com"}, "differ"),
                ({"IPR_PREVIEW_TO": ""}, "distinct configured"),
                ({"IPR_EDITOR_TO": ""}, "distinct configured"),
            ):
                with self.subTest(override=override), patch.dict(
                    os.environ, dict(baseline, **override), clear=True
                ), patch("scripts.sunday_send_reviewed_packet.send_packet") as smtp:
                    with self.assertRaisesRegex(ReviewedHandoffRefused, expected):
                        handoff(file, WEEK, send=True,
                                owner_confirmed=True, now=SUNDAY)
                    smtp.assert_not_called()

    def test_no_confirmation_means_no_smtp_even_when_digest_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": digest,
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
            }, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                with self.assertRaises(ReviewedHandoffRefused):
                    handoff(file, WEEK, send=True,
                            owner_confirmed=False, now=SUNDAY)
                send.assert_not_called()

    def test_malformed_packet_or_week_refuses_before_smtp(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            content = file.read_text(encoding="utf-8")
            for changed in (
                content.replace("Packet: IPR-2026-10-10",
                                "Packet: IPR-2026-10-03"),
                content.replace("Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED",
                                "Status: APPROVED"),
                content.replace("END OF SOURCE APPENDIX", "MISSING END"),
                content + "FORGED EXTRA AFTER END",
                content.replace("=== SOURCE APPENDIX — DO NOT EDIT ===", ""),
                content.replace("=== SOURCE APPENDIX — DO NOT EDIT ===",
                                "=== SOURCE APPENDIX — DO NOT EDIT ===\n"
                                "=== SOURCE APPENDIX — DO NOT EDIT ==="),
                "not an editorial packet",
            ):
                with self.subTest(changed=changed[:65]):
                    file.write_text(changed, encoding="utf-8")
                    with self.assertRaises(ReviewedHandoffRefused):
                        validate_file(file, WEEK, now=SUNDAY)
            file.write_text(content, encoding="utf-8")
            for bad in ("2026-10-09", "2026-10-17", "2026-10-10 ", "no"):
                with self.subTest(week=bad), self.assertRaises(ReviewedHandoffRefused):
                    validate_file(file, bad, now=SUNDAY)
            with self.assertRaisesRegex(ReviewedHandoffRefused,
                                        "has not ended"):
                validate_file(file, WEEK, now=datetime(
                    2026, 10, 10, 19, tzinfo=timezone.utc
                ))

    def test_symlink_and_binary_and_oversize_files_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            link = Path(folder) / "alias.txt"
            link.symlink_to(file)
            with self.assertRaisesRegex(ReviewedHandoffRefused, "symlink"):
                validate_file(link, WEEK, now=SUNDAY)
            invalid = Path(folder) / "invalid.txt"
            invalid.write_bytes(b"\xff" * 20)
            with self.assertRaises(ReviewedHandoffRefused):
                validate_file(invalid, WEEK, now=SUNDAY)
            oversize = Path(folder) / "huge.txt"
            oversize.write_bytes(b"Z" * 3_000_001)
            with self.assertRaisesRegex(ReviewedHandoffRefused, "large"):
                validate_file(oversize, WEEK, now=SUNDAY)

    def test_cli_defaults_to_offline_and_has_no_send_control_in_dry_run(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            with patch("scripts.sunday_send_reviewed_packet.send_packet") as send:
                with patch("scripts.sunday_send_reviewed_packet.datetime") as clock:
                    clock.now.return_value = SUNDAY
                    self.assertEqual(main([
                        "--packet", str(file), "--week-ending", WEEK,
                    ]), 0)
                send.assert_not_called()
            with self.assertRaises(SystemExit):
                main(["--packet", str(file), "--week-ending", WEEK,
                      "--confirm-owner-reviewed"])


if __name__ == "__main__":
    unittest.main()
