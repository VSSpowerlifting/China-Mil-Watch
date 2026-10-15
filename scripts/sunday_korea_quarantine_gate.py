"""Independent pre-model and pre-delivery quarantine for Korea held evidence.

This is NOT a way to admit Korea. A future source-loader allowlist expansion
cannot, by itself, turn held Korean source notes into Sunday model/SMTP input.
Separate owner/source/reuse/signature approvals and a reviewed release change
will be necessary before this denial can ever be lifted.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from core.brief_editorial_evidence import EditorialEvidenceError, load_editorial_evidence

SCHEMA = "ipr-korea-sunday-packet-quarantine/1"
ALLOWED_OTHER_DESKS = frozenset({"japan", "vietnam", "indonesia", "philippines"})
KR_ID = re.compile(r"(?:KR[-_]|korea[-_:])", re.IGNORECASE)
KR_PUBLISHER = re.compile(r"(?:^|\.)korea\.kr$", re.IGNORECASE)
ROOT = Path(__file__).resolve().parents[1]


class KoreaSundayHold(ValueError):
    """Fixed error codes without packet content, source names or personal data."""


def demand(condition, reason):
    if not condition:
        raise KoreaSundayHold(reason)


def _pairs(values):
    result = {}
    for key, value in values:
        demand(key not in result, "duplicate_packet_json_key")
        result[key] = value
    return result


def _has_korean_source(row):
    # Even if the general source parser is later expanded, Korea remains held
    # at this distinct model/SMTP boundary. Fail on malformed identity types.
    demand(type(row) is dict, "non_object_research_item")
    for key in ("desk", "id", "source_url"):
        demand(type(row.get(key)) is str, "missing_or_nontext_source_identity")
    from urllib.parse import urlsplit
    try:
        domain = urlsplit(row["source_url"]).hostname or ""
    except ValueError:
        raise KoreaSundayHold("malformed_source_url") from None
    return (row["desk"].lower() == "korea"
            or KR_ID.match(row["id"]) is not None
            or KR_PUBLISHER.search(domain) is not None)


def inspect(*, packet, week_ending, as_of, permit_missing=False):
    demand(type(permit_missing) is bool, "invalid_missing_policy")
    path = Path(packet)
    demand(path.is_absolute() and path.name == week_ending + ".json"
           and path.parent.is_dir() and not path.parent.is_symlink()
           and not path.is_symlink(), "unsafe_or_wrong_week_packet")
    if not path.exists():
        demand(permit_missing, "expected_sunday_packet_missing")
        return _receipt(week_ending, 0, "missing_packet_no_korea_admission")
    demand(path.is_file() and 0 < path.stat().st_size <= 40000,
           "unsafe_packet_file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              KoreaSundayHold("nonfinite_packet_value")))
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, KoreaSundayHold):
            raise
        raise KoreaSundayHold("malformed_packet_json") from None
    demand(type(data) is dict and type(data.get("items")) is list,
           "missing_research_items")
    for row in data["items"]:
        demand(not _has_korean_source(row), "korea_not_admitted_to_sunday")
        demand(row["desk"] in ALLOWED_OTHER_DESKS,
               "unexpected_unapproved_sunday_desk")
    # Preserve strict source/version/date/schema/permission gate of the
    # canonical loader; this is an additional DENY, not its replacement.
    try:
        validated = load_editorial_evidence(
            week_ending, as_of, directory=path.parent)
    except (EditorialEvidenceError, OSError, TypeError) as exc:
        raise KoreaSundayHold("existing_sunday_source_contract_rejected") from exc
    demand(len(validated) == len(data["items"]),
           "sunday_packet_source_roster_changed")
    demand(not any(_has_korean_source(row) for row in validated),
           "validated_korea_evidence_prohibited")
    return _receipt(week_ending, len(validated), "korea_held_outside_sunday")


def _receipt(week_ending, other_count, status):
    return {
        "schema": SCHEMA,
        "week_ending": week_ending,
        "status": status,
        "other_desk_source_count": other_count,
        "korea_research_offered_to_model_or_email": 0,
        "korea_source_admission_authorized": False,
        "korean_original_body_loaded": False,
        "model_called": False,
        "email_sent": False,
        "publication_or_production_authorized": False,
        "mutated_research_packet": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--permit-missing", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = inspect(packet=args.packet, week_ending=args.week_ending,
                         as_of=args.as_of, permit_missing=args.permit_missing)
    except (KoreaSundayHold, ValueError, OSError) as exc:
        reason = str(exc) if isinstance(exc, KoreaSundayHold) else "packet_refused"
        print(json.dumps({"schema": SCHEMA, "status": "HOLD",
                          "reason": reason,
                          "korea_research_offered_to_model_or_email": 0,
                          "korea_source_admission_authorized": False,
                          "model_called": False,
                          "email_sent": False}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
