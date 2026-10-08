"""Sunday owner preview is separately authorized and never contacts Dylan."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_editorial_handoff import send_packet, main
from tests.test_briefs_editorial_evidence import scaffold, manuscript

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml"
SAT = "2026-10-10"


class SundayOwnerPreviewTests(unittest.TestCase):
    def test_preview_needs_distinct_configured_owner_email(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "sunday.txt"
            document.write_text("PRIVATE ONE-THEME DRAFT", encoding="utf-8")
            for recipient in ("", "dylan@example.com", "DYLAN@example.com"):
                with self.subTest(recipient=recipient), patch.dict(os.environ, {
                    "IPR_EDITOR_TO": "dylan@example.com",
                    "IPR_PREVIEW_TO": recipient,
                    "IPR_SMTP_USER": "author@gmail.com",
                    "IPR_SMTP_APP_PASSWORD": "abcdefghijklmnop",
                }, clear=True):
                    with patch("scripts.sunday_editorial_handoff.smtplib.SMTP_SSL") as smtp:
                        with self.assertRaises(ValueError):
                            send_packet(document, SAT, full_week=True,
                                        preview_to_owner=True)
                        smtp.assert_not_called()

    def test_private_preview_sends_only_to_owner_not_dylan(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "sunday.txt"
            document.write_text("PRIVATE ONE-THEME DRAFT", encoding="utf-8")
            with patch.dict(os.environ, {
                "IPR_EDITOR_TO": "dylan@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
                "IPR_SMTP_USER": "author@gmail.com",
                "IPR_SMTP_APP_PASSWORD": "abcdefghijklmnop",
            }, clear=True):
                with patch("scripts.sunday_editorial_handoff.smtplib.SMTP_SSL") as smtp:
                    send_packet(document, SAT, full_week=True,
                                preview_to_owner=True)
                    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            self.assertEqual(message["To"], "owner@example.com")
            self.assertNotIn("dylan@example.com", str(message))
            self.assertIn("OWNER-ONLY", message["Subject"])
            self.assertIn("NOT delivered to Dylan", message.get_body(preferencelist=("plain",)).get_content())
            self.assertEqual(next(message.iter_attachments()).get_content(),
                             "PRIVATE ONE-THEME DRAFT")

    def test_preview_and_editor_delivery_cannot_both_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_file = root / "sidecar.json"
            input_file.write_text(json.dumps(scaffold()), encoding="utf-8")
            output = root / "preview.txt"
            with patch("scripts.sunday_editorial_handoff.send_packet") as send:
                with self.assertRaises(SystemExit):
                    main(["--sidecar", str(input_file), "--out", str(output),
                          "--full-week", "--write-automatic", "--as-of", SAT,
                          "--send", "--preview-to-owner"])
                send.assert_not_called()
                self.assertFalse(output.exists())

    def test_legacy_no_send_does_not_email_either_party(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_file = root / "sidecar.json"
            input_file.write_text(json.dumps(scaffold()), encoding="utf-8")
            output = root / "preview.txt"
            with patch("scripts.sunday_briefs_auto_writer.compose",
                       return_value=manuscript()):
                with patch("scripts.sunday_editorial_handoff.send_packet") as mail:
                    main(["--sidecar", str(input_file), "--out", str(output),
                          "--full-week", "--include-research", "--write-automatic",
                          "--as-of", SAT])
                    mail.assert_not_called()
            self.assertTrue(output.exists())

    def test_preview_cli_only_after_full_week_and_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_file = root / "sidecar.json"
            input_file.write_text(json.dumps(scaffold()), encoding="utf-8")
            output = root / "preview.txt"
            for omitted in ("--full-week", "--write-automatic"):
                args = ["--sidecar", str(input_file), "--out", str(output),
                        "--full-week", "--write-automatic", "--as-of", SAT,
                        "--preview-to-owner"]
                args.remove(omitted)
                with self.subTest(omitted=omitted):
                    with self.assertRaises(SystemExit):
                        main(args)
                    self.assertFalse(output.exists())

    def test_workflow_owner_preview_is_opt_in_and_email_secret_is_separate(self):
        code = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("      preview_to_owner:", code)
        self.assertIn("        default: false", code)
        self.assertIn("secrets.IPR_PREVIEW_TO", code)
        self.assertIn("inputs.preview_to_owner == true", code)
        self.assertIn('[[ "$IPR_PREVIEW_REQUESTED" != "true" ]]', code)
        self.assertIn("args+=(--preview-to-owner)", code)
        self.assertIn("args+=(--send)", code)
        self.assertNotIn("actions/upload-artifact", code)
        self.assertNotIn("git push", code)
        self.assertIn("permissions:\n  contents: read", code)


if __name__ == "__main__":
    unittest.main()
