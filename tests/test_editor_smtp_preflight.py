"""No-network tests for IPR's manually dispatched, no-send SMTP preflight."""
from __future__ import annotations

import os
import smtplib
import unittest
from unittest.mock import MagicMock, patch

from scripts.editor_smtp_preflight import check_smtp, main


VALID_ENV = {
    "IPR_EDITOR_TO": "editor@example.org",
    "IPR_SMTP_USER": "sender@gmail.com",
    "IPR_SMTP_APP_PASSWORD": "abcdefghijklmnop",
}


class SmtpPreflightTests(unittest.TestCase):
    def test_login_only_never_sends_email(self):
        server = MagicMock()
        with patch.dict(os.environ, VALID_ENV, clear=True):
            with patch("scripts.editor_smtp_preflight.ssl.create_default_context",
                       return_value="fake-ssl") as tls:
                connect = MagicMock()
                connect.return_value.__enter__.return_value = server
                self.assertTrue(check_smtp(connect=connect))
                connect.assert_called_once_with("smtp.gmail.com", 465,
                                                context="fake-ssl", timeout=20)
                server.login.assert_called_once_with("sender@gmail.com",
                                                     "abcdefghijklmnop")
                server.send_message.assert_not_called()
                server.sendmail.assert_not_called()
                tls.assert_called_once_with()

    def test_whitespace_in_displayed_app_password_is_normalized(self):
        env = dict(VALID_ENV, IPR_SMTP_APP_PASSWORD="abcd efgh ijkl mnop")
        with patch.dict(os.environ, env, clear=True):
            server = MagicMock()
            connect = MagicMock()
            connect.return_value.__enter__.return_value = server
            check_smtp(connect=connect)
            server.login.assert_called_once_with("sender@gmail.com",
                                                 "abcdefghijklmnop")
            server.sendmail.assert_not_called()

    def test_bad_credentials_refused_before_connect(self):
        for password in ("ordinary-password", "short", "", "abcd-efgh-ijkl-mnop"):
            with self.subTest(password=password):
                env = dict(VALID_ENV, IPR_SMTP_APP_PASSWORD=password)
                with patch.dict(os.environ, env, clear=True):
                    connect = MagicMock()
                    with self.assertRaisesRegex(ValueError, "16-character"):
                        check_smtp(connect=connect)
                    connect.assert_not_called()

    def test_missing_or_multiple_recipient_refused_before_connect(self):
        for recipient in ("", "one@example.org, other@example.org",
                          "editor@example.org\\r\\nBcc: bad@example.org"):
            with self.subTest(recipient=recipient):
                env = dict(VALID_ENV, IPR_EDITOR_TO=recipient)
                with patch.dict(os.environ, env, clear=True):
                    connect = MagicMock()
                    with self.assertRaises(ValueError):
                        check_smtp(connect=connect)
                    connect.assert_not_called()

    def test_smtp_authentication_error_propagates_and_does_not_send(self):
        with patch.dict(os.environ, VALID_ENV, clear=True):
            server = MagicMock()
            server.login.side_effect = smtplib.SMTPAuthenticationError(
                535, b"bad credentials"
            )
            connect = MagicMock()
            connect.return_value.__enter__.return_value = server
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                check_smtp(connect=connect)
            server.send_message.assert_not_called()
            server.sendmail.assert_not_called()

    def test_main_reports_no_mail_without_leaking_credentials(self):
        with patch("scripts.editor_smtp_preflight.check_smtp", return_value=True):
            with patch("builtins.print") as printed:
                main()
        lines = "\\n".join(call.args[0] for call in printed.call_args_list)
        self.assertIn("No email sent", lines)
        self.assertNotIn(VALID_ENV["IPR_SMTP_APP_PASSWORD"], lines)
        self.assertNotIn(VALID_ENV["IPR_SMTP_USER"], lines)


if __name__ == "__main__":
    unittest.main()
