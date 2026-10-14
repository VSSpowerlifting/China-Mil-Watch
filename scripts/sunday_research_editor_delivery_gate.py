"""Fail closed if model-only Vietnam evidence would be distributed by email.

Sunday private-model evidence can be suitable for an unapproved manuscript
without the owner separately authorizing editor-email distribution. This gate
runs after exact-source refresh and BEFORE any model/API call or SMTP action.
It never inspects or copies the publisher's original article bodies.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.brief_editorial_evidence import load_editorial_evidence


class EditorDeliveryNotAuthorized(ValueError):
    """A draft-only source would be sent beyond its explicit approved scope."""


def check(*, week_ending, as_of, packet, send_email=False,
          vietnam_email_approved_week=""):
    if type(send_email) is not bool:
        raise EditorDeliveryNotAuthorized("send-email request must be a boolean")
    packet = Path(packet)
    if packet.is_symlink() or packet.name != week_ending + ".json":
        raise EditorDeliveryNotAuthorized("missing or wrong-week private evidence file")
    # The validated reader rejects malformed dates, stale as-of, forged source
    # status, bad URLs, invented shadow hashes, duplicate IDs and copied bodies.
    evidence = load_editorial_evidence(week_ending, as_of, directory=packet.parent)
    vietnam_count = sum(item["desk"] == "vietnam" for item in evidence)
    if send_email and vietnam_count and vietnam_email_approved_week != week_ending:
        raise EditorDeliveryNotAuthorized(
            "Vietnam source synopses are authorized for private AI drafting only; "
            "editor-email distribution requires separate exact-week owner approval"
        )
    return {
        "week_ending": week_ending,
        "source_count": len(evidence),
        "vietnam_count": vietnam_count,
        "editor_send_requested": send_email,
        "vietnam_editor_send_authorized": (
            not send_email or not vietnam_count or
            vietnam_email_approved_week == week_ending
        ),
        "publication_or_source_approval": False,
        "model_was_called": False,
        "email_sent": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--send-email", action="store_true")
    parser.add_argument("--approved-week", default="")
    args = parser.parse_args(argv)
    try:
        receipt = check(
            week_ending=args.week_ending, as_of=args.as_of,
            packet=args.packet, send_email=args.send_email,
            vietnam_email_approved_week=args.approved_week,
        )
    except (EditorDeliveryNotAuthorized, ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
