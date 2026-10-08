"""Manually verify IPR editorial Gmail SMTP credentials without sending email.

Run from repository root:
    python -m scripts.editor_smtp_preflight

This does not compose a draft, send a message, publish content, or change
repository configuration. Never log credentials or sender/recipient addresses.
"""
from __future__ import annotations

import os
import smtplib
import ssl

from scripts.weekly_editorial_handoff import single_address


def check_smtp(*, connect=smtplib.SMTP_SSL):
    """Authenticate against Gmail SMTP; no message can be sent on this path."""
    # Check both addresses so delivery problems are detected before writing.
    single_address(os.environ.get("IPR_EDITOR_TO", ""), "IPR_EDITOR_TO")
    sender = single_address(os.environ.get("IPR_SMTP_USER", ""), "IPR_SMTP_USER")
    app_password = "".join(os.environ.get("IPR_SMTP_APP_PASSWORD", "").split())
    if (len(app_password) != 16 or not app_password.isascii()
            or not app_password.isalnum()):
        raise ValueError(
            "IPR_SMTP_APP_PASSWORD must be a Google-generated 16-character app password"
        )

    with connect("smtp.gmail.com", 465,
                 context=ssl.create_default_context(), timeout=20) as client:
        client.login(sender, app_password)
    return True


def main():
    check_smtp()
    print("IPR Gmail SMTP authentication successful. Recipient address syntax valid.")
    print("No email sent; no Claude API call made; delivery variable unchanged.")


if __name__ == "__main__":
    main()
