"""Safe, pleasant Sunday editor copy; the immutable audited TXT is unchanged.

These are no-network, no-model, no-email tests. SMTP is mocked.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_editor_readable import (
    ReadableEditorError, editable_sections, prose_only_html, prose_only_text,
)
from scripts.sunday_editorial_handoff import render_packet, send_packet
from tests.test_briefs_editorial_evidence import SAT, manuscript, scaffold
from core.brief_editorial_evidence import load_editorial_evidence


def reviewed_packet():
    return render_packet(
        scaffold(), manuscript=manuscript(), as_of=SAT,
        research_evidence=load_editorial_evidence(SAT, SAT),
    )


class ReadableSundayEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = reviewed_packet()

    def test_clean_copy_keeps_content_but_hides_technical_envelope(self):
        sections = editable_sections(self.packet)
        self.assertEqual(sections[0][0], "WORKING TITLE")
        self.assertEqual(sections[-1][0], "CROSS-DESK COMPARISON")
        plain = prose_only_text(self.packet)
        html = prose_only_html(self.packet)
        self.assertIn(sections[0][1], plain)
        self.assertIn(sections[0][1], html)
        self.assertIn("Hi Dylan", plain)
        self.assertIn("language, flow, clarity", plain)
        self.assertIn("language, flow, clarity", html)
        for marker in (
            "=== EDITABLE MANUSCRIPT ===",
            "=== SOURCE APPENDIX",
            "SOURCE RECORD IDS:",
            "EXTERNAL SOURCE IDS:",
            "MODEL-AVAILABLE OFFICIAL SOURCE RESEARCH",
            "SOURCE RECORD",
            "Pinned shadow commit:",
            "Version/content SHA-256:",
            "COVERAGE SNAPSHOT",
            "EDITORIAL QUESTIONS / SATURDAY FOLLOW-UP",
            "EDITORIAL FOCUS",
        ):
            self.assertNotIn(marker, plain)
            self.assertNotIn(marker, html)
        self.assertIn("=== SOURCE APPENDIX", self.packet)
        self.assertIn("EXTERNAL SOURCE IDS:", self.packet)

    def test_html_escapes_source_like_markup_and_renders_bold(self):
        original = self.packet
        changed = original.replace(
            "## WHAT STOOD OUT\n",
            "## WHAT STOOD OUT\n<script>danger</script> and **significant**.\n\n", 1
        )
        html = prose_only_html(changed)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<strong>significant</strong>", html)
        self.assertIn("</html>", html)

    def test_source_appendix_never_enters_dylans_reading_view(self):
        altered = self.packet.replace(
            "=== SOURCE APPENDIX — DO NOT EDIT ===",
            "=== SOURCE APPENDIX — DO NOT EDIT ===\n"
            "SECRET APPENDIX TEXT THAT MUST STAY OUT OF EDITOR EMAIL",
            1,
        )
        self.assertNotIn("SECRET APPENDIX TEXT", prose_only_text(altered))
        self.assertNotIn("SECRET APPENDIX TEXT", prose_only_html(altered))

    def test_malformed_headers_duplicates_and_missing_status_fail_closed(self):
        original = self.packet
        mutations = (
            original.replace("=== SOURCE APPENDIX — DO NOT EDIT ===", "wrong", 1),
            original.replace("=== EDITABLE MANUSCRIPT ===",
                             "=== EDITABLE MANUSCRIPT ===\n=== EDITABLE MANUSCRIPT ===", 1),
            original.replace("Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED",
                             "Status: PUBLISHED", 1),
            original.replace("## WHAT STOOD OUT", "## UNTRUSTED SECTION", 1),
            original.replace("## WHAT STOOD OUT",
                             "## WHAT STOOD OUT\nOriginal\n\n## WHAT STOOD OUT", 1),
        )
        for variant in mutations:
            with self.subTest(variant=variant[:60]):
                with self.assertRaises(ReadableEditorError):
                    editable_sections(variant)

    def test_sunday_email_is_article_first_and_retains_exact_reviewed_bytes(self):
        from unittest.mock import MagicMock
        packet_bytes = self.packet.encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "one-provisional.txt"
            p.write_bytes(packet_bytes)
            fake_mail = MagicMock()
            fake_mail.__enter__.return_value = fake_mail
            env = {
                "IPR_EDITOR_TO": "dylan@example.org",
                "IPR_SMTP_USER": "ben@example.org",
                "IPR_SMTP_APP_PASSWORD": "abcdefghijklmnop",
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": SAT,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": hashlib.sha256(packet_bytes).hexdigest(),
            }
            with patch.dict("os.environ", env), \
                 patch("scripts.sunday_editorial_handoff.require_owner_review"), \
                 patch("scripts.sunday_editorial_handoff.require_exact_reviewed_manuscript") as verified, \
                 patch("scripts.sunday_editorial_handoff.smtplib.SMTP_SSL") as smtp:
                smtp.return_value.__enter__.return_value = fake_mail
                send_packet(p, SAT, full_week=True)
                msg = fake_mail.send_message.call_args.args[0]
        verified.assert_called_once()
        self.assertEqual(verified.call_args.kwargs["manuscript_bytes"], packet_bytes)
        self.assertEqual(msg["To"], "dylan@example.org")
        self.assertIn("Sunday draft for language edits", str(msg["Subject"]))
        text_body = msg.get_body(preferencelist=("plain",)).get_content()
        html_body = msg.get_body(preferencelist=("html",)).get_content()
        self.assertIn("Hi Dylan", text_body)
        self.assertIn("language, flow, clarity", text_body)
        self.assertIn("<h1", html_body)
        self.assertNotIn("=== SOURCE APPENDIX", text_body)
        self.assertNotIn("Pinned shadow commit", html_body)
        files = list(msg.iter_attachments())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].get_filename(), "one-provisional.txt")
        self.assertEqual(files[0].get_payload(decode=True), packet_bytes)


if __name__ == "__main__":
    unittest.main()
