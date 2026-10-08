"""No-network guardrail tests for weekly Briefs editorial handoff."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.weekly_editorial_handoff import render_packet, send_packet


def draft():
    return {
        "editorial_status": "draft",
        "issue_number": None,
        "week_start": "2026-09-27",
        "week_ending": "2026-10-03",
        "desks": ["china", "singapore"],
        "coverage_by_desk": {
            "china": {"records": 1, "by_screening": {"analyzed": 1}},
            "singapore": {"records": 1, "by_screening": {"awaiting_screening": 1}},
        },
        "source_trail": [
            {"record_id": 1, "desk": "china", "date": "2026-10-01",
             "source": "Agency A", "title": "A test development",
             "title_original": "Test", "lang": "zh", "url": "https://example.com/1",
             "screening": "analyzed"},
            {"record_id": 2, "desk": "singapore", "date": "2026-10-02",
             "source": "Agency B", "title": "A second development",
             "title_original": "A second development", "lang": "en",
             "url": "https://example.com/2", "screening": "awaiting_screening"},
        ],
    }


class EditorialWorksheetTests(unittest.TestCase):
    def test_packet_is_unapproved_and_source_linked(self):
        text = render_packet(draft())
        self.assertIn("NOT APPROVED OR PUBLISHED", text)
        self.assertIn("## OPENING NOTE", text)
        self.assertIn("Record 1 | china | 2026-10-01 | Agency A", text)
        self.assertIn("Record 2 | singapore | 2026-10-02 | Agency B", text)
        self.assertIn("https://example.com/2", text)
        self.assertNotIn("No. 17", text)

    def test_numbered_or_approved_packet_refused(self):
        for change in ({"issue_number": 17}, {"editorial_status": "approved"}):
            item = draft()
            item.update(change)
            with self.assertRaises(ValueError):
                render_packet(item)

    def test_missing_second_desk_warns_without_inventing_exception(self):
        item = draft()
        item["source_trail"] = item["source_trail"][:1]
        text = render_packet(item)
        self.assertIn("COVERAGE WARNING", text)
        self.assertIn("single-desk Brief would require", text)
        self.assertIn("NOT APPROVED OR PUBLISHED", text)

    def test_no_candidates_refused(self):
        item = draft()
        item["source_trail"] = []
        with self.assertRaises(ValueError):
            render_packet(item)

    def test_wrong_weekday_refused(self):
        item = draft()
        item["week_ending"] = "2026-10-02"
        with self.assertRaises(ValueError):
            render_packet(item)

    def test_source_newlines_cannot_inject_headings(self):
        item = draft()
        item["source_trail"][0]["title"] = "real\n## FAKE HEADER"
        text = render_packet(item)
        self.assertIn("Title: real ## FAKE HEADER", text)
        self.assertNotIn("\n## FAKE HEADER", text)

    def test_sender_needs_secrets_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "IPR-week.txt"
            path.write_text("test", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                with patch("scripts.weekly_editorial_handoff.smtplib.SMTP_SSL") as smtp:
                    with self.assertRaises(ValueError):
                        send_packet(path, "2026-10-03")
                    smtp.assert_not_called()

    def test_rejects_non_app_password_before_smtp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "IPR-week.txt"
            path.write_text("test", encoding="utf-8")
            env = {
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_SMTP_USER": "author@gmail.com",
                "IPR_SMTP_APP_PASSWORD": "not-a-generated-app-password",
            }
            with patch.dict(os.environ, env, clear=True):
                with patch("scripts.weekly_editorial_handoff.smtplib.SMTP_SSL") as smtp:
                    with self.assertRaisesRegex(ValueError, "16-character"):
                        send_packet(path, "2026-10-03")
                    smtp.assert_not_called()

    def test_runner_launches_handoff_as_a_module(self):
        # The workflow must keep the repository root on sys.path. Launching
        # 'python scripts/weekly_editorial_handoff.py' breaks absolute
        # 'from scripts.*' imports at runtime even though unit tests pass.
        project = Path(__file__).resolve().parents[1]
        workflow = (project / ".github" / "workflows" /
                    "weekly_briefs_editorial_handoff.yml").read_text(encoding="utf-8")
        self.assertIn('python -m scripts.weekly_editorial_handoff "${args[@]}"', workflow)
        self.assertNotIn('python scripts/weekly_editorial_handoff.py', workflow)

    def test_delivery_uses_single_recipient_and_attachment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "IPR-week.txt"
            path.write_text("test content", encoding="utf-8")
            env = {
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_SMTP_USER": "author@gmail.com",
                "IPR_SMTP_APP_PASSWORD": "abcdefghijklmnop",
            }
            with patch.dict(os.environ, env, clear=True):
                with patch("scripts.weekly_editorial_handoff.smtplib.SMTP_SSL") as smtp:
                    send_packet(path, "2026-10-03")
                    client = smtp.return_value.__enter__.return_value
                    client.login.assert_called_once_with("author@gmail.com", "abcdefghijklmnop")
                    mail = client.send_message.call_args.args[0]
                    self.assertEqual(mail["To"], "editor@example.com")
                    self.assertEqual(mail["Reply-To"], "author@gmail.com")
                    attachment = list(mail.iter_attachments())[0]
                    self.assertEqual(attachment.get_filename(), "IPR-week.txt")
                    self.assertEqual(attachment.get_content(), "test content")


if __name__ == "__main__":
    unittest.main()
