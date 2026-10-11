"""C3 standalone, OFFLINE-ONLY, fictional-recipient reviewed Sunday MIME composer.

This is a pure message-construction seam, not delivery authorization.
No filesystem read, SMTP/client import, scheduling, model call or real address.
Only the Oct 10 pilot and reserved @example.invalid test recipients qualify.
A caller-supplied SHA proves byte equality, NOT authenticated owner sign-off,
source accuracy, permission to retain publisher text, or consent to email.
"""
from __future__ import annotations

import hashlib
import re
from email.message import EmailMessage

from scripts.sunday_editor_readable import prose_only_html, prose_only_text
from scripts.sunday_pilot_owner_review import PILOT_SATURDAY


class FictionalMimeHold(ValueError):
    """Byte identity, manuscript structure or synthetic-recipient guard failed."""


_SHA = re.compile(r"[a-f0-9]{64}\Z")
_FIXTURE_ADDRESS = re.compile(
    r"[a-z][a-z0-9._+-]{0,60}@example[.]invalid\Z", re.ASCII
)
_MAX_BYTES = 2_000_000
_SOURCE_USE = "=== MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY ==="
_APPENDIX = "=== SOURCE APPENDIX — DO NOT EDIT ==="
_FOOTER = "END OF UNAPPROVED WORKSHEET"


def _fixture_mailbox(address):
    """Disallow actual addresses, injected header fields and mailbox aliases."""
    if (not isinstance(address, str) or
            not _FIXTURE_ADDRESS.fullmatch(address) or
            ".." in address or ".@" in address):
        raise FictionalMimeHold("only single synthetic @example.invalid mailbox allowed")
    return address


def compose_fictional_reviewed_editor_mime(
        original_bytes, *, week, reviewed_sha256, recipient, sender):
    """Build one unsent MIME from the exact checked byte buffer; never re-open a path.

    A pure presentation step: caller holds a fictional digest, not an owner
    signature. The original TXT reference stays byte-exact in one attachment.
    SMTP, address resolution, journal reservation and all real approvals are
    expressly outside this module.
    """
    if week != PILOT_SATURDAY:
        raise FictionalMimeHold("only the explicitly scoped first Sunday pilot")
    if not isinstance(original_bytes, bytes) or not (0 < len(original_bytes) <= _MAX_BYTES):
        raise FictionalMimeHold("one bounded original TXT bytes object required")
    if not isinstance(reviewed_sha256, str) or not _SHA.fullmatch(reviewed_sha256):
        raise FictionalMimeHold("lowercase SHA-256 reviewed-byte pin required")
    if hashlib.sha256(original_bytes).hexdigest() != reviewed_sha256:
        raise FictionalMimeHold("original bytes differ from the supplied reviewed SHA")
    recipient = _fixture_mailbox(recipient)
    sender = _fixture_mailbox(sender)
    if recipient == sender:
        raise FictionalMimeHold("owner preview and fictional editor addresses must differ")
    if b"\x00" in original_bytes:
        raise FictionalMimeHold("binary source packet is not valid TXT")
    try:
        original = original_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FictionalMimeHold("reviewed TXT requires strict UTF-8") from exc
    if "\r" in original:
        raise FictionalMimeHold("no newline-normalization of the reviewed TXT")
    # This lightweight in-memory envelope check is NOT a substitute for
    # separate original-file inspection and independent source-use review.
    if (original.count("Packet: IPR-" + week + "\n") != 1 or
            any(original.count(marker) != 1 for marker in
                (_SOURCE_USE, _APPENDIX, "END OF MANUSCRIPT SOURCE USE",
                 "END OF SOURCE APPENDIX")) or
            not original.rstrip().endswith(_FOOTER)):
        raise FictionalMimeHold("missing or repeated pilot envelope/receipt")
    plain = prose_only_text(original)
    html = prose_only_html(original)
    # The renderer owns article selection. The original appendix is retained
    # in the reference attachment, but may not leak into either email body.
    if any(marker in plain or marker in html for marker in
           (_APPENDIX, _SOURCE_USE, "END OF SOURCE APPENDIX")):
        raise FictionalMimeHold("source appendix leaked into the readable body")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Reply-To"] = sender
    msg["Subject"] = (
        "IPR Briefs | week ending {} | Sunday draft for language edits "
        "(UNAPPROVED)".format(week)
    )
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(
        original_bytes, maintype="text", subtype="plain",
        filename="IPR-{}-reviewed-reference.txt".format(week),
    )
    # Verify the exact payload that would be handed to an eventual transport.
    parts = list(msg.iter_attachments())
    if (len(parts) != 1 or parts[0].get_payload(decode=True) != original_bytes):
        raise FictionalMimeHold("MIME attachment no longer matches reviewed bytes")
    return msg
