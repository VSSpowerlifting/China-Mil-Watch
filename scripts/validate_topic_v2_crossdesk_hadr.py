"""Read-only provenance validator for the v2 HADR cross-desk review packet.

Replays source IDs, stored excerpts, source-date and Git-blob *references*
against the merged v1 pilot ledger. Does NOT reread archived original blobs,
independently verify official claims, or classify/attach topics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKET = ROOT / "research" / "topic_v2_crossdesk_hadr" / "packet.json"
LEDGER = ROOT / "research" / "topic_pilot_v1" / "ledger.json"
ROLES = frozenset(("positive_candidate", "negative_control", "unassessable_body"))

# Explicit research selection. Roles identify *questions*, not gold labels.
EXPECTED = {
    "P16": ("china", "positive_candidate", "peace_train_china_laos"),
    "P21": ("china", "negative_control", "holiday_public_order_patrol"),
    "P35": ("singapore", "positive_candidate", "trident_resolve_admm_plus"),
    "P36": ("singapore", "unassessable_body", "trident_resolve_admm_plus"),
    "P38": ("japan", "positive_candidate", "kumamoto_earthquake_support"),
    "P49": ("philippines", "negative_control", "philippines_maritime_readiness"),
    "P51": ("philippines", "positive_candidate", "sanlakas_philippines"),
    "P52": ("philippines", "positive_candidate", "sanlakas_philippines"),
    "P57": ("indonesia", "positive_candidate", "wildfire_jmsdf_indonesia"),
    "P44": ("vietnam", "negative_control", "vietnam_myanmar_crime_cooperation"),
    "P58": ("korea", "negative_control", "korea_ballistic_missile_statement"),
}

ENTRY_FIELDS = frozenset((
    "pilot_id", "desk_id", "source_slug", "source_url",
    "source_stated_date", "title_original", "origin_key",
    "origin_commit", "origin_blob", "origin_path", "origin_ref",
    "storage_table", "body_sha256", "body_chars", "record_identity",
    "role", "event_key", "review_question", "evidence",
    "review_state", "owner_approval",
))


class CrossDeskEvidenceError(ValueError):
    """Packet cannot support a provenance-safe editorial review."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CrossDeskEvidenceError(message)


def _git_blob_sha(raw: bytes) -> str:
    """Git SHA1 blob format, not a generic SHA-1 of bytes."""
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") +
                        b"\0" + raw).hexdigest()


def validate(packet: dict, pilot: dict, ledger_blob_sha: str) -> dict:
    """Compare a proposed packet to the *exact* saved pilot ledger bytes."""
    _require(type(packet) is dict and type(pilot) is dict,
             "packet and pilot must be JSON objects")
    _require(packet.get("packet_id") ==
             "ipr_regional_v2_hadr_crossdesk_20261007", "packet ID drift")
    _require(type(packet.get("version")) is int and
             packet["version"] == 1, "unsupported packet version")
    _require(packet.get("scope_topic") == "military_hadr",
             "wrong evidence subject")
    _require(packet.get("source_pilot_taxonomy_version") == 1 and
             packet.get("target_taxonomy_version") == 2 and
             pilot.get("taxonomy_version") == 1,
             "taxonomy versions are inconsistent")
    _require(packet.get("classification_status") ==
             "provisional_source_first_editorial_controls_only",
             "packet wrongly asserts classification authority")
    _require(type(packet.get("record_count")) is int and
             type(packet.get("distinct_desk_count")) is int and
             type(packet.get("distinct_event_key_count")) is int,
             "counts must be integers")
    _require(packet.get("pilot_ledger_path") ==
             "research/topic_pilot_v1/ledger.json",
             "unexpected pilot source path")
    _require(packet.get("pilot_ledger_blob_sha") == ledger_blob_sha,
             "frozen pilot Git blob SHA mismatch")
    _require(packet.get("pilot_sample_size") == pilot.get("sample_size") ==
             len(pilot.get("records", [])) == 60,
             "frozen pilot sample size mismatch")
    _require("human" in str(packet.get("selection_note", "")).lower() and
             "model" in str(packet.get("selection_note", "")).lower(),
             "packet must disclose non-human model-selected origin")
    _require("blind" in str(packet.get("reviewer_gate", "")).lower(),
             "packet must explain why it is not a blind reviewer artifact")

    records = pilot["records"]
    by_id = {r["pilot_id"]: r for r in records}
    _require(len(by_id) == len(records), "duplicate original pilot IDs")
    rows = packet.get("cases")
    _require(type(rows) is list and len(rows) == len(EXPECTED) == 11,
             "cross-desk packet must contain 11 frozen cases")
    _require(type(pilot.get("origins")) is dict,
             "pilot has no pinned source origins")
    seen = set()
    desks = set()
    event_keys = set()
    counts = Counter()
    for row in rows:
        _require(type(row) is dict and set(row) == ENTRY_FIELDS,
                 "case contains missing or extraneous fields")
        id_ = row["pilot_id"]
        _require(type(id_) is str and id_ in EXPECTED and id_ not in seen,
                 "missing, unexpected, or duplicate case ID")
        seen.add(id_)
        original = by_id.get(id_)
        _require(type(original) is dict, "case missing from original pilot")
        desk, role, event = EXPECTED[id_]
        _require(row["desk_id"] == original["desk_id"] == desk,
                 "desk identity drift: " + id_)
        _require(row["role"] == role and row["role"] in ROLES and
                 row["event_key"] == event,
                 "case role or event family changed: " + id_)
        _require(row["source_slug"] == original["source_slug"] and
                 row["source_url"] == original["canonical_url"] and
                 row["source_stated_date"] == original["published_date"] and
                 row["title_original"] == original["title_original"] and
                 row["record_identity"] == original["record_id"] and
                 row["body_sha256"] == original["body_sha256"] and
                 row["body_chars"] == original["body_chars"],
                 "source content or identity drift: " + id_)

        key = original["origin"]
        origin = pilot["origins"].get(key)
        _require(type(origin) is dict and row["origin_key"] == key and
                 row["origin_commit"] == origin["commit"] and
                 row["origin_blob"] == origin["blob"] and
                 row["origin_path"] == origin["path"] and
                 row["origin_ref"] == origin["ref"] and
                 row["storage_table"] == original["row_locator"]["table"],
                 "archived origin pin drift: " + id_)
        _require(original["status"] == "provisional" and
                 original["review_state"] == "pending" and
                 row["review_state"] == "pending_human" and
                 row["owner_approval"] is None,
                 "case attempts to assert human approval: " + id_)
        _require(type(row["review_question"]) is str and
                 bool(row["review_question"].strip()),
                 "missing editorial research question: " + id_)
        # Original excerpts were model-selected, and are not independent labels.
        excerpts = original["evidence"]
        _require(type(row["evidence"]) is list and
                 len(row["evidence"]) == len(excerpts),
                 "source excerpt count drift: " + id_)
        for source_excerpt, actual in zip(excerpts, row["evidence"]):
            _require(type(actual) is dict and
                     set(actual) == {"id", "field", "start", "end", "quote"},
                     "invalid excerpt fields: " + id_)
            _require(actual == {key: source_excerpt[key] for key in
                                ("id", "field", "start", "end", "quote")},
                     "source excerpt provenance mismatch: " + id_)
        if role == "unassessable_body":
            _require(row["body_chars"] == 0 and row["evidence"] == [],
                     "unassessable body must not contain borrowed evidence")
        else:
            _require(row["body_chars"] > 0 and row["evidence"],
                     "assessable case must retain original excerpts")
        counts[role] += 1
        desks.add(desk)
        event_keys.add(event)

    _require(seen == set(EXPECTED), "case coverage drift")
    _require(dict(counts) == packet.get("provisional_role_counts") and
             counts == Counter({"positive_candidate": 6,
                               "negative_control": 4,
                               "unassessable_body": 1}),
             "role counts changed without review")
    _require(len(desks) == packet["distinct_desk_count"] == 7,
             "seven-desk coverage claim is incorrect")
    _require(len(event_keys) == packet["distinct_event_key_count"] == 9,
             "distinct event/context count mismatch")
    return {
        "cases": len(rows),
        "desk_count": len(desks),
        "event_contexts": len(event_keys),
        "roles": dict(sorted(counts.items())),
        "provenance": "matches frozen pilot Git blob metadata and ledger excerpts",
        "human_approval": False,
    }


def validate_files(packet_path: Path = PACKET, ledger_path: Path = LEDGER) -> dict:
    raw = ledger_path.read_bytes()
    pilot = json.loads(raw.decode("utf-8"))
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    return validate(packet, pilot, _git_blob_sha(raw))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    args = parser.parse_args()
    try:
        print(json.dumps(validate_files(args.packet, args.ledger),
                         indent=2, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, "HADR provenance check failed: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
