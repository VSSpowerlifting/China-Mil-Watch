"""Preserve scheduled editor delivery without distributing model-only research.

Before any model/API call or SMTP, validate the source-refreshed Sunday packet.
A Vietnam synopsis authorized only for private model drafting must be withheld
from an emailed worksheet unless separately approved for that exact week.
Non-Vietnam sources remain eligible: this does not silence the Sunday handoff.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.brief_editorial_evidence import load_editorial_evidence

ROOT = Path(__file__).resolve().parents[1]


class EditorDeliveryNotAuthorized(ValueError):
    """Unsafe draft-only research would be distributed beyond its consent."""


def check(*, week_ending, as_of, packet, send_email=False,
          vietnam_email_approved_week="", safe_out=None):
    if type(send_email) is not bool:
        raise EditorDeliveryNotAuthorized("send-email request must be a boolean")
    packet = Path(packet)
    if packet.is_symlink() or packet.name != week_ending + ".json":
        raise EditorDeliveryNotAuthorized("missing or wrong-week private evidence file")
    # The existing strict loader refuses duplicate IDs, wrong source families,
    # noncanonical URLs, copied bodies, forged approvals and invalid dates.
    evidence = load_editorial_evidence(week_ending, as_of, directory=packet.parent)
    vietnam_count = sum(item["desk"] == "vietnam" for item in evidence)
    consent = vietnam_email_approved_week == week_ending
    withheld = vietnam_count if send_email and not consent else 0
    effective = packet.resolve()

    if withheld:
        if safe_out is None:
            raise EditorDeliveryNotAuthorized(
                "Vietnam research is model-only; supply a private scratch "
                "output to withhold it before editor email"
            )
        dest = Path(safe_out)
        if (dest.name != week_ending + ".json" or dest.is_symlink()
                or dest.parent.is_symlink() or not dest.parent.is_dir()
                or dest.exists()):
            raise EditorDeliveryNotAuthorized(
                "editor-safe research output must be new and week-specific"
            )
        resolved = dest.resolve()
        if ROOT == resolved or ROOT in resolved.parents:
            raise EditorDeliveryNotAuthorized(
                "editor-safe research packet must be outside repository"
            )
        # Preserve original non-Vietnam entries and metadata exactly, never
        # copy publisher bodies or quietly change their research identities.
        original = json.loads(packet.read_text(encoding="utf-8"))
        retained = [x for x in original["items"] if x["desk"] != "vietnam"]
        if len(original["items"]) != len(evidence) or (
                len(original["items"]) - len(retained) != vietnam_count):
            raise EditorDeliveryNotAuthorized("refreshed research roster differs")
        if not retained:
            raise EditorDeliveryNotAuthorized(
                "no non-Vietnam research remains for scheduled editor worksheet"
            )
        filtered = dict(original, items=retained)
        # Recheck the derived scratch roster with the same trusted loader.
        with dest.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(
                filtered, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")) + "\n")
        try:
            checked = load_editorial_evidence(
                week_ending, as_of, directory=dest.parent)
            if (len(checked) != len(retained)
                    or any(x["desk"] == "vietnam" for x in checked)):
                raise EditorDeliveryNotAuthorized(
                    "filtered editor packet failed source checks")
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        effective = resolved

    return {
        "week_ending": week_ending,
        "source_count_before_delivery_scope": len(evidence),
        "vietnam_private_model_sources": vietnam_count,
        "vietnam_withheld_from_editor_count": withheld,
        "editor_packet_source_count": len(evidence) - withheld,
        "effective_packet": str(effective),
        "editor_send_requested": send_email,
        "vietnam_editor_send_authorized": consent,
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
    parser.add_argument("--safe-out", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = check(
            week_ending=args.week_ending, as_of=args.as_of,
            packet=args.packet, send_email=args.send_email,
            vietnam_email_approved_week=args.approved_week,
            safe_out=args.safe_out,
        )
    except (EditorDeliveryNotAuthorized, ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
