"""First Sunday editorial recipient requires exact-week human-owner clearance."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_pilot_owner_review import (
    OwnerReviewRequired, PILOT_SATURDAY, require_owner_review,
    require_approved_digest_format, require_exact_reviewed_manuscript,
)
from scripts.sunday_editorial_handoff import main, send_packet
from scripts.weekly_briefs_sunday_window import SundayHandoffRefused, resolve_sunday_handoff
from tests.test_briefs_editorial_evidence import scaffold

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml"


class FirstSundayOwnerReleaseTests(unittest.TestCase):
    def test_no_send_owner_preview_does_not_require_release(self):
        self.assertFalse(require_owner_review(
            week_ending=PILOT_SATURDAY, sending=False, approved_week=""))
        result = resolve_sunday_handoff(
            event="workflow_dispatch",
            now=datetime(2026, 10, 11, 19, 17, tzinfo=timezone.utc),
            reporting_saturday=PILOT_SATURDAY,
            send_email=False,
            sunday_daily_marker="2026-10-11",
            pilot_owner_reviewed_week="",
        )
        self.assertEqual(result["IPR_SUNDAY_SHOULD_SEND"], "false")

    def test_pilot_editor_send_requires_exact_reviewed_week(self):
        for value in ("", "true", "false", "2026-10-03", "2026-10-17",
                      " 2026-10-10", "2026-10-10 ", "2026-10-10\n"):
            with self.subTest(value=value), self.assertRaisesRegex(
                OwnerReviewRequired, "IPR_SUNDAY_OWNER_REVIEWED_WEEK"
            ):
                require_owner_review(
                    week_ending=PILOT_SATURDAY, sending=True,
                    approved_week=value,
                )
        self.assertTrue(require_owner_review(
            week_ending=PILOT_SATURDAY, sending=True,
            approved_week=PILOT_SATURDAY,
        ))

    def test_scheduled_pilot_checks_owner_before_email(self):
        now = datetime(2026, 10, 11, 19, 17, tzinfo=timezone.utc)
        with self.assertRaises(SundayHandoffRefused):
            resolve_sunday_handoff(
                event="schedule", now=now, send_email=True,
                sunday_daily_marker="2026-10-11",
                pilot_owner_reviewed_week="",
            )
        enabled = resolve_sunday_handoff(
            event="schedule", now=now, send_email=True,
            sunday_daily_marker="2026-10-11",
            pilot_owner_reviewed_week=PILOT_SATURDAY,
            pilot_owner_reviewed_sha256="a" * 64,
        )
        self.assertEqual(enabled["IPR_SUNDAY_SHOULD_SEND"], "true")

    def test_digest_is_required_before_model_even_if_week_reviewed(self):
        now = datetime(2026, 10, 11, 19, 17, tzinfo=timezone.utc)
        for digest in ("", "TRUE", "b" * 63, "B" * 64):
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(
                    SundayHandoffRefused, "IPR_SUNDAY_OWNER_REVIEWED_SHA256"
                ):
                    resolve_sunday_handoff(
                        event="schedule", now=now, send_email=True,
                        sunday_daily_marker="2026-10-11",
                        pilot_owner_reviewed_week=PILOT_SATURDAY,
                        pilot_owner_reviewed_sha256=digest,
                    )
        self.assertTrue(require_approved_digest_format(
            week_ending=PILOT_SATURDAY, sending=True,
            approved_sha256="a" * 64,
        ))
        self.assertFalse(require_approved_digest_format(
            week_ending=PILOT_SATURDAY, sending=False,
            approved_sha256="",
        ))

    def test_later_week_sends_keep_normal_scheduling_rules(self):
        self.assertFalse(require_owner_review(
            week_ending="2026-10-17", sending=True, approved_week=""))
        result = resolve_sunday_handoff(
            event="schedule",
            now=datetime(2026, 10, 18, 19, 17, tzinfo=timezone.utc),
            send_email=True,
            sunday_daily_marker="2026-10-18",
            pilot_owner_reviewed_week="",
        )
        self.assertEqual(result["IPR_SUNDAY_WEEK_END"], "2026-10-17")

    def test_direct_send_packet_cannot_bypass_owner_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "first-edition.txt"
            path.write_text("Private source review still outstanding.")
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": "",
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
                "IPR_SMTP_USER": "author@gmail.com",
                "IPR_SMTP_APP_PASSWORD": "abcdefghijklmnop",
            }, clear=True), patch(
                "scripts.sunday_editorial_handoff.smtplib.SMTP_SSL"
            ) as smtp:
                with self.assertRaises(OwnerReviewRequired):
                    send_packet(path, PILOT_SATURDAY, full_week=True)
                smtp.assert_not_called()
                # A private owner preview is allowed, and has no Dylan address.
                send_packet(path, PILOT_SATURDAY, full_week=True,
                            preview_to_owner=True)
                mail = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
                self.assertEqual(mail["To"], "owner@example.com")
                self.assertNotIn("editor@example.com", str(mail))

    def test_pilot_release_needs_exact_reviewed_attachment_hash(self):
        attachment = b"IPR pilot manuscript and appendices\\n"
        exact = hashlib.sha256(attachment).hexdigest()
        self.assertTrue(require_exact_reviewed_manuscript(
            week_ending=PILOT_SATURDAY, sending=True,
            manuscript_bytes=attachment, approved_sha256=exact,
        ))
        for wrong in ("", "true", "0" * 64, exact.upper(), " " + exact,
                      hashlib.sha256(b"another model draft").hexdigest()):
            with self.subTest(approved=wrong), self.assertRaises(
                OwnerReviewRequired
            ):
                require_exact_reviewed_manuscript(
                    week_ending=PILOT_SATURDAY, sending=True,
                    manuscript_bytes=attachment, approved_sha256=wrong,
                )
        self.assertFalse(require_exact_reviewed_manuscript(
            week_ending=PILOT_SATURDAY, sending=False,
            manuscript_bytes=attachment, approved_sha256="",
        ))
        self.assertFalse(require_exact_reviewed_manuscript(
            week_ending="2026-10-17", sending=True,
            manuscript_bytes=attachment, approved_sha256="",
        ))

    def test_direct_smtp_requires_review_of_exact_bytes_not_just_week(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "first-edition.txt"
            # Dylan-facing sends now require a structured article.
            # Keep checking that only the owner's exact reviewed bytes go out.
            from tests.test_sunday_editor_readable import reviewed_packet
            original = reviewed_packet().encode("utf-8")
            path.write_bytes(original)
            approved = hashlib.sha256(original).hexdigest()
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": PILOT_SATURDAY,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": hashlib.sha256(
                    b"a different draft"
                ).hexdigest(),
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
                "IPR_SMTP_USER": "author@gmail.com",
                "IPR_SMTP_APP_PASSWORD": "abcdefghijklmnop",
            }, clear=True), patch(
                "scripts.sunday_editorial_handoff.smtplib.SMTP_SSL"
            ) as smtp:
                with self.assertRaisesRegex(OwnerReviewRequired,
                                             "differs from owner's reviewed"):
                    send_packet(path, PILOT_SATURDAY, full_week=True)
                smtp.assert_not_called()
                os.environ["IPR_SUNDAY_OWNER_REVIEWED_SHA256"] = approved
                send_packet(path, PILOT_SATURDAY, full_week=True)
                email = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
                self.assertEqual(email["To"], "editor@example.com")
                self.assertEqual(next(email.iter_attachments()).get_content().encode(),
                                 original)

    def test_owner_preview_contains_exact_attachment_digest_for_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private-preview.txt"
            data = b"Private edition in exact bytes\\n"
            path.write_bytes(data)
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": "",
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": "",
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
                "IPR_SMTP_USER": "author@gmail.com",
                "IPR_SMTP_APP_PASSWORD": "abcdefghijklmnop",
            }, clear=True), patch(
                "scripts.sunday_editorial_handoff.smtplib.SMTP_SSL"
            ) as smtp:
                send_packet(path, PILOT_SATURDAY, full_week=True,
                            preview_to_owner=True)
                mail = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
                self.assertIn(hashlib.sha256(data).hexdigest(),
                              mail.get_body(preferencelist=("plain",)).get_content())
                self.assertEqual(mail["To"], "owner@example.com")

    def test_cli_blocks_model_and_attachment_without_owner_review(self):
        with tempfile.TemporaryDirectory() as folder:
            sidecar = Path(folder) / "scaffold.json"
            dest = Path(folder) / "draft.txt"
            sidecar.write_text(json.dumps(scaffold()), encoding="utf-8")
            with patch.dict(os.environ,
                            {"IPR_SUNDAY_OWNER_REVIEWED_WEEK": ""}), patch(
                "scripts.sunday_editorial_handoff.send_packet"
            ) as smtp, patch(
                "scripts.sunday_briefs_auto_writer.compose"
            ) as composer:
                with self.assertRaises(OwnerReviewRequired):
                    main(["--sidecar", str(sidecar), "--out", str(dest),
                          "--as-of", PILOT_SATURDAY,
                          "--full-week", "--write-automatic", "--send"])
                composer.assert_not_called()
                smtp.assert_not_called()
                self.assertFalse(dest.exists())

    def test_workflow_injects_approval_into_both_guards_before_model(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        review = "vars.IPR_SUNDAY_OWNER_REVIEWED_WEEK"
        self.assertEqual(text.count(review), 2)
        self.assertEqual(text.count("vars.IPR_SUNDAY_OWNER_REVIEWED_SHA256"), 2)
        self.assertIn("pilot_owner_reviewed_sha256=os.environ.get(", text)
        self.assertIn('pilot_owner_reviewed_week=os.environ.get(', text)
        self.assertIn("python -m scripts.sunday_editorial_handoff", text)
        step = text.index("- name: Verify reporting Saturday and Sunday's successful database update")
        draft = text.index("- name: Generate source-cited Sunday manuscript")
        self.assertLess(step, draft)
        self.assertNotIn("git push", text)
        self.assertNotIn("actions/upload-artifact", text)


if __name__ == "__main__":
    unittest.main()
