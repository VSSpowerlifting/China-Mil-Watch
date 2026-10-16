"""C3 no-send MIME tests. All mailbox fixtures are reserved example.invalid."""
import hashlib
import unittest
from email import policy
from email.parser import BytesParser

from core.sunday_reviewed_mime import (
    FictionalMimeHold, compose_fictional_reviewed_editor_mime,
)
from tests.test_sunday_editor_readable import reviewed_packet


def sha(data):
    return hashlib.sha256(data).hexdigest()


_UNSET = object()


class FictionalEditorMimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = reviewed_packet()
        cls.original = cls.text.encode("utf-8")

    def build(self, raw=_UNSET, **changes):
        if raw is _UNSET:
            raw = self.original
        args = dict(
            week="2026-10-10",
            reviewed_sha256=sha(raw if isinstance(raw, bytes) else self.original),
            recipient="editor@example.invalid", sender="owner@example.invalid",
        )
        args.update(changes)
        return compose_fictional_reviewed_editor_mime(raw, **args)

    def test_exact_reviewed_binary_attachment_survives_mime_serialization(self):
        message = self.build()
        attachments = list(message.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_payload(decode=True), self.original)
        self.assertEqual(attachments[0].get_filename(),
                         "IPR-2026-10-10-reviewed-reference.txt")
        parsed = BytesParser(policy=policy.default).parsebytes(message.as_bytes())
        files = list(parsed.iter_attachments())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].get_payload(decode=True), self.original)

    def test_article_first_plain_and_html_do_not_leak_source_appendix(self):
        message = self.build()
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn("Hi Dylan", plain)
        self.assertIn("language, flow, clarity", plain)
        self.assertIn("<h1", html)
        for marker in ("=== SOURCE APPENDIX", "MANUSCRIPT SOURCE USE",
                       "SOURCE RECORD IDS:", "EXTERNAL SOURCE IDS:",
                       "END OF SOURCE APPENDIX"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, plain)
                self.assertNotIn(marker, html)
        self.assertIn("END OF SOURCE APPENDIX", self.original.decode("utf-8"))

    def test_header_identity_and_provisional_purpose(self):
        m = self.build()
        self.assertEqual(str(m["From"]), "owner@example.invalid")
        self.assertEqual(str(m["To"]), "editor@example.invalid")
        self.assertEqual(str(m["Reply-To"]), "owner@example.invalid")
        self.assertIn("UNAPPROVED", str(m["Subject"]))
        self.assertEqual(m.get_all("Cc", []), [])
        self.assertEqual(m.get_all("Bcc", []), [])

    def test_composer_requires_exact_approved_byte_digest(self):
        for candidate in (sha(b"different"), "a"*63, "A"*64, "", None):
            with self.subTest(candidate=candidate), self.assertRaises(FictionalMimeHold):
                self.build(reviewed_sha256=candidate)

    def test_changed_editorial_prose_requires_new_digest(self):
        altered = self.original.replace(b"## WHAT STOOD OUT",
                                        b"## WHAT STOOD OUT\nModified prose", 1)
        with self.assertRaisesRegex(FictionalMimeHold, "differ"):
            self.build(altered, reviewed_sha256=sha(self.original))

    def test_different_week_is_not_implicitly_authorized(self):
        with self.assertRaises(FictionalMimeHold):
            self.build(week="2026-10-17")

    def test_only_single_reserved_fictional_recipient(self):
        recipients = ("editor@example.com", "editor@example.org",
                      "editor@example.invalid,other@example.invalid",
                      "editor@example.invalid\nBcc:someone@example.invalid",
                      "Editor@example.invalid", "editor@example.invalid ",
                      "editor..x@example.invalid", "", "editor@sub.example.invalid")
        for candidate in recipients:
            with self.subTest(candidate=candidate), self.assertRaises(FictionalMimeHold):
                self.build(recipient=candidate)

    def test_invalid_sender_or_sender_equal_editor_fails(self):
        with self.assertRaises(FictionalMimeHold):
            self.build(sender="sender@example.org")
        with self.assertRaises(FictionalMimeHold):
            self.build(sender="editor@example.invalid")

    def test_corrupt_utf8_and_nul_are_rejected(self):
        for changed in (b"\xff" + self.original, self.original + b"\x00"):
            with self.subTest(prefix=changed[:5]), self.assertRaises(FictionalMimeHold):
                self.build(changed)

    def test_newline_normalization_fails_closed(self):
        changed = self.original.replace(b"\n", b"\r\n")
        with self.assertRaises(FictionalMimeHold):
            self.build(changed)

    def test_truncated_or_repeated_source_receipt_refused(self):
        originals = (
            self.original.replace(
                "=== MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY ===".encode("utf-8"),
                b"missing-source-use", 1),
            self.original + b"\nEND OF SOURCE APPENDIX",
            self.original.replace(b"END OF UNAPPROVED WORKSHEET",
                                  b"END OF UNREVIEWED WORKSHEET", 1),
        )
        for changed in originals:
            with self.subTest(length=len(changed)), self.assertRaises(FictionalMimeHold):
                self.build(changed)

    def test_oversized_or_non_bytes_input_refused(self):
        for bad in ("text", b"", b"a"*2_000_001, None):
            with self.subTest(size=len(bad) if bad is not None else None), \
                 self.assertRaises(FictionalMimeHold):
                self.build(bad)

    def test_html_escapes_injected_editorial_markup(self):
        edited = self.original.replace(b"## WHAT STOOD OUT\n",
                 b'## WHAT STOOD OUT\n<script src="https://invalid.test/evil"></script>\n', 1)
        msg = self.build(edited)
        body = msg.get_body(preferencelist=("html",)).get_content()
        self.assertNotIn('<script src=', body)
        self.assertIn('&lt;script', body)
        self.assertEqual(list(msg.iter_attachments())[0].get_payload(decode=True), edited)

    def test_no_filesystem_smtp_or_generation_import_in_composer_module(self):
        import inspect
        import core.sunday_reviewed_mime as module
        source = inspect.getsource(module)
        for forbidden in ("smtplib", "SMTP_SSL", "open(", "read_bytes(",
                          "send_packet(", "compose(", "anthropic", "requests."):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
