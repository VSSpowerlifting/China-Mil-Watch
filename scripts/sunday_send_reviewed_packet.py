"""Manually hand the EXACT owner-reviewed Sunday Briefs worksheet to Dylan.

Offline digest receipt by default. The explicit --send --confirm-owner-reviewed
path sends a temporary byte-for-byte snapshot, never starts an AI model, and
never regenerates a source appendix. Not publication or a rights approval.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.sunday_editorial_handoff import send_packet, single_address

NY = ZoneInfo("America/New_York")
SCHEMA = "ipr-reviewed-sunday-manual-handoff/1"
MAX_BYTES = 3_000_000
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
HEADER = "INDO-PACIFIC RECORD | BRIEFS EDITORIAL WORKSHEET"
STRUCTURE = (
    "=== EDITABLE MANUSCRIPT ===",
    "## WORKING TITLE",
    "## CONCRETE DEVELOPMENT",
    "=== SOURCE APPENDIX — DO NOT EDIT ===",
    "=== MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY ===",
    "END OF MANUSCRIPT SOURCE USE",
    "END OF SOURCE APPENDIX",
    "END OF UNAPPROVED WORKSHEET",
)


class ReviewedHandoffRefused(ValueError):
    """Unsafe or unapproved exact-file editorial handoff."""


def validate_file(path, week_ending, *, now=None):
    """Return a verified immutable-in-memory snapshot of the local worksheet."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".txt":
        raise ReviewedHandoffRefused("reviewed packet must be an existing regular .txt, not a symlink")
    if not DATE.fullmatch(week_ending):
        raise ReviewedHandoffRefused("reporting Saturday must be exact YYYY-MM-DD")
    try:
        saturday = date.fromisoformat(week_ending)
    except ValueError as exc:
        raise ReviewedHandoffRefused("invalid reporting Saturday") from exc
    if saturday.weekday() != 5:
        raise ReviewedHandoffRefused("reporting date must be a Saturday")
    if now is None:
        now = datetime.now(NY)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ReviewedHandoffRefused("local clock must have timezone")
    today = now.astimezone(NY).date()
    if saturday >= today:
        raise ReviewedHandoffRefused("reporting Saturday has not ended")
    if saturday < today - timedelta(days=98):
        raise ReviewedHandoffRefused("reviewed edition is outside 98-day historical review window")
    if path.stat().st_size > MAX_BYTES:
        raise ReviewedHandoffRefused("unexpectedly large editorial worksheet")
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_BYTES:
        raise ReviewedHandoffRefused("empty or unexpectedly large reviewed attachment")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewedHandoffRefused("owner-review attachment must be UTF-8 text") from exc
    if not text.startswith(HEADER + "\nPacket: IPR-" + week_ending + "\n"):
        raise ReviewedHandoffRefused("worksheet header or exact edition identity mismatch")
    if text.count("Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED") != 1:
        raise ReviewedHandoffRefused("worksheet must explicitly remain unnumbered and unapproved")
    for marker in STRUCTURE:
        if text.count(marker) != 1:
            raise ReviewedHandoffRefused("reviewed worksheet lacks unique protected structure: " + marker)
    if "SOURCE RECORD IDS:" not in text:
        raise ReviewedHandoffRefused("thematic manuscript lacks production citation bookkeeping")
    if not text.endswith("END OF UNAPPROVED WORKSHEET\n"):
        raise ReviewedHandoffRefused("reviewed file has trailing or missing worksheet boundary")
    return payload


def inspect_reviewed_attachment(path, week_ending, *, approval_week="", approval_digest="",
                                now=None):
    packet = validate_file(path, week_ending, now=now)
    actual = hashlib.sha256(packet).hexdigest()
    approved = bool(
        approval_week == week_ending and isinstance(approval_digest, str)
        and DIGEST.fullmatch(approval_digest)
        and hmac.compare_digest(actual, approval_digest)
    )
    return packet, {
        "schema": SCHEMA,
        "week_ending": week_ending,
        "attachment_sha256": actual,
        "attachment_bytes": len(packet),
        "exact_owner_approval_matches": approved,
        "automated_model_called": False,
        "publisher_rights_or_facts_reviewed_by_program": False,
        "email_sent": False,
        "publication_authorized": False,
    }


def handoff(path, week_ending, *, send=False, owner_confirmed=False,
            historical_override=False, now=None):
    """Return metadata only; never email unless BOTH explicit manual flags hold."""
    if now is None:
        now = datetime.now(NY)
    packet, receipt = inspect_reviewed_attachment(
        path, week_ending,
        approval_week=os.environ.get("IPR_SUNDAY_OWNER_REVIEWED_WEEK", ""),
        approval_digest=os.environ.get("IPR_SUNDAY_OWNER_REVIEWED_SHA256", ""),
        now=now,
    )
    if not send:
        if owner_confirmed or historical_override:
            raise ReviewedHandoffRefused("send confirmations are invalid on a dry run")
        return receipt
    if not owner_confirmed or not receipt["exact_owner_approval_matches"]:
        raise ReviewedHandoffRefused(
            "Dylan send refused: --confirm-owner-reviewed and exact approved "
            "IPR_SUNDAY_OWNER_REVIEWED_WEEK/SHA256 are required"
        )
    local_day = now.astimezone(NY).date()
    latest_saturday = local_day - timedelta(days=(local_day.weekday() - 5) % 7)
    if (week_ending != latest_saturday.isoformat()
            or local_day.weekday() != 6) and not historical_override:
        raise ReviewedHandoffRefused(
            "sending a past-week reviewed manuscript requires --allow-historical-send"
        )
    # A deliberate manual editor handoff must not run alongside the old
    # recurring Friday delivery service. The operator supplies the same
    # environment that IPR's weekly workflow uses; we do not update variables.
    for service in ("IPR_EDITOR_DELIVERY_ENABLED",
                    "IPR_SUNDAY_EDITOR_DELIVERY_ENABLED"):
        if os.environ.get(service, "").strip().lower() == "true":
            raise ReviewedHandoffRefused(
                "parallel editor service enabled: disable " + service
            )
    try:
        editor = single_address(os.environ.get("IPR_EDITOR_TO", ""), "IPR_EDITOR_TO")
        owner = single_address(os.environ.get("IPR_PREVIEW_TO", ""), "IPR_PREVIEW_TO")
    except ValueError as exc:
        raise ReviewedHandoffRefused(
            "manual handoff needs distinct configured owner and editor addresses"
        ) from exc
    if editor.casefold() == owner.casefold():
        raise ReviewedHandoffRefused(
            "manual editor recipient must differ from the owner-preview address"
        )
    # Snapshot bytes in a private temporary directory. Protect against a
    # changed original file between preflight hashing and SMTP attachment read.
    with tempfile.TemporaryDirectory(prefix="ipr-reviewed-sunday-") as folder:
        reviewed_copy = Path(folder) / Path(path).name
        reviewed_copy.write_bytes(packet)
        send_packet(reviewed_copy, week_ending, provisional=True, full_week=True)
    receipt["email_sent"] = True
    return receipt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--packet", type=Path, required=True,
                   help="local owner-reviewed .txt; never a fresh AI run")
    p.add_argument("--week-ending", required=True, help="reviewed reporting Saturday")
    p.add_argument("--send", action="store_true",
                   help="actually deliver the exact approved file; absent means offline receipt")
    p.add_argument("--confirm-owner-reviewed", action="store_true",
                   help="explicit owner acknowledgement for this exact attachment")
    p.add_argument("--allow-historical-send", action="store_true",
                   help="acknowledge deliberate older-edition delivery")
    args = p.parse_args(argv)
    try:
        receipt = handoff(
            args.packet, args.week_ending, send=args.send,
            owner_confirmed=args.confirm_owner_reviewed,
            historical_override=args.allow_historical_send,
        )
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
