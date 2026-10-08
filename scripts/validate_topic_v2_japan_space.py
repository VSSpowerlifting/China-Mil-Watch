"""Read-only structural gate for unarchived Japan space-security discovery leads.

This validates an EDITOR source-admission prospectus, NOT historical source text,
an approved classifier, a licensed collector, or an independently reviewed set.
No network/database operations, no topic attachments and no write paths.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PACKET = ROOT / "research/topic_v2_japan_space/source_candidates.json"
VOCAB = ROOT / "taxonomy/regional_topics.v2.json"
ID = "ipr_japan_space_v2_source_admission_20261008"
TOPIC = "space_security"
DOMAINS = frozenset(("www.mod.go.jp", "www.mofa.go.jp", "www.jaxa.jp"))

EXPECTED = {
    "JSP01": ("https://www.mod.go.jp/j/press/wp/wp2026/html/n310204000.html",
              "positive_candidate", "japan_mod_2026_space_capability_policy", "jp_mod"),
    "JSP02": ("https://www.mod.go.jp/j/press/kisha/2026/0306a.html",
              "positive_candidate", "japan_space_wing_reorganization_20260323", "jp_mod"),
    "JSP03": ("https://www.mod.go.jp/asdf/ssa/activities/report01/",
              "positive_candidate", "japan_space_wing_reorganization_20260323", "jp_jasdf_space_ops"),
    "JSP04": ("https://www.mofa.go.jp/mofaj/gaiko/bluebook/2026/html/chapter3_01_02.html",
              "positive_candidate", "japan_us_security_space_cooperation", "jp_mofa"),
    "JSP05": ("https://www.jaxa.jp/press/2026/06/20260612-1_j.html",
              "hard_negative_candidate", "h3_f6_test_launch_20260612", "jp_jaxa"),
    "JSP06": ("https://www.jaxa.jp/press/2026/08/20260820-1_j.html",
              "hard_negative_candidate", "jaxa_mmx_planned_launch_20261020", "jp_jaxa"),
}
FIELDS = frozenset((
    "id", "issuer", "issuer_key", "desk_candidate", "document_group",
    "title_original", "url", "source_date", "source_year", "date_precision",
    "language", "document_type", "candidate_role", "review_context_key",
    "review_question", "caution", "archive_identity", "body_sha256",
    "review_state", "owner_approval",
))
ROOT_FIELDS = frozenset((
    "packet_id", "schema_version", "subject_topic", "taxonomy_id",
    "taxonomy_version", "document_type", "research_date", "selection_origin",
    "archive_status", "archival_note", "record_count", "candidate_role_counts",
    "distinct_source_group_count", "collection_authorized",
    "topic_assignments_authorized", "human_review_complete",
    "human_approvals", "candidates",
))


class AdmissionError(ValueError):
    """An editor-facing, non-authoritative research contract was violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AdmissionError(message)


def validate(packet: dict, vocabulary: dict) -> dict:
    _require(type(packet) is dict and set(packet) == ROOT_FIELDS, "packet schema changed")
    _require(type(vocabulary) is dict, "taxonomy must be an object")
    _require(vocabulary.get("taxonomy_id") == "ipr_regional_topics" and
             vocabulary.get("taxonomy_version") == 2,
             "version 2 taxonomy required")
    _require(TOPIC in [t["slug"] for t in vocabulary.get("topics", [])],
             "space_security missing from v2 vocabulary")
    _require(packet["packet_id"] == ID and type(packet["schema_version"]) is int and
             packet["schema_version"] == 1, "packet identity/version drift")
    _require(packet["subject_topic"] == TOPIC and
             packet["taxonomy_id"] == "ipr_regional_topics" and
             packet["taxonomy_version"] == 2,
             "topic scope or taxonomy version changed")
    _require(packet["document_type"] == "editor_facing_source_discovery_only" and
             packet["archive_status"] == "not_pinned_not_verified_against_full_japan_shadow",
             "archival status overstated")
    _require(packet["research_date"] == "2026-10-08",
             "research date changed without new documented verification")
    _require("Assistant" in packet["selection_origin"] and
             "not" in packet["archival_note"].lower(),
             "must disclose assistant curation and archival uncertainty")
    _require(all(packet[k] is False for k in (
        "collection_authorized", "topic_assignments_authorized", "human_review_complete")),
        "authorization or human review cannot be asserted here")
    _require(packet["human_approvals"] == [], "no human approvals exist")
    _require(type(packet["record_count"]) is int and packet["record_count"] == 6 and
             type(packet["distinct_source_group_count"]) is int and
             packet["distinct_source_group_count"] == 5,
             "incorrect sample/event totals")
    rows = packet["candidates"]
    _require(type(rows) is list and len(rows) == 6, "six exact sources required")
    roles = Counter()
    seen = set()
    contexts = set()
    issuers = set()
    for row in rows:
        _require(type(row) is dict and set(row) == FIELDS, "candidate schema altered")
        ident = row["id"]
        _require(type(ident) is str and ident in EXPECTED and ident not in seen,
                 "duplicate or unknown candidate ID")
        seen.add(ident)
        url, role, group, issuer_key = EXPECTED[ident]
        _require((row["url"], row["candidate_role"], row["review_context_key"],
                  row["issuer_key"]) == (url, role, group, issuer_key),
                 ident + ": pinned source/role/context drift")
        parsed = urlparse(row["url"])
        _require(parsed.scheme == "https" and parsed.hostname in DOMAINS and
                 parsed.username is None and parsed.password is None and
                 not parsed.query and not parsed.fragment,
                 ident + ": unexpected official source URL")
        _require(row["desk_candidate"] == "japan" and row["language"] == "ja",
                 ident + ": wrong desk/language")
        _require(all(type(row[key]) is str and row[key].strip() for key in (
            "issuer", "document_group", "title_original", "document_type",
            "review_question", "caution")), ident + ": incomplete lead")
        _require(type(row["source_year"]) is int and
                 row["source_year"] == 2026,
                 ident + ": unexpected year")
        if row["date_precision"] == "year":
            _require(row["source_date"] is None and ident in ("JSP01", "JSP04"),
                     ident + ": year precision or fabricated date")
        elif row["date_precision"] == "day":
            _require(ident not in ("JSP01", "JSP04") and
                     type(row["source_date"]) is str, ident + ": missing day date")
            try:
                parsed_date = date.fromisoformat(row["source_date"])
            except ValueError as exc:
                raise AdmissionError(ident + ": invalid date") from exc
            _require(parsed_date.year == 2026 and
                     parsed_date <= date(2026, 10, 8),
                     ident + ": future or wrong-year source date")
        else:
            raise AdmissionError(ident + ": unsupported date precision")
        _require(row["archive_identity"] is None and row["body_sha256"] is None and
                 row["review_state"] == "awaiting_source_admission" and
                 row["owner_approval"] is None,
                 ident + ": no archival identity or approvals established")
        roles[role] += 1
        contexts.add(group)
        issuers.add(issuer_key)
    _require(seen == set(EXPECTED), "pinned source coverage incomplete")
    _require(dict(roles) == packet["candidate_role_counts"] ==
             {"positive_candidate": 4, "hard_negative_candidate": 2},
             "candidate role counts drift")
    _require(len(contexts) == packet["distinct_source_group_count"] == 5,
             "event/context double-counting")
    return {
        "topic": TOPIC,
        "candidate_source_documents": 6,
        "distinct_event_or_policy_contexts": 5,
        "issuing_units": len(issuers),
        "editor_only_roles": dict(sorted(roles.items())),
        "source_bodies_pinned": 0,
        "records_human_approved": 0,
        "topic_assignments_written": 0,
        "authoritative_archive_coverage_verified": False,
    }


def validate_files(packet_path: Path = PACKET, vocabulary_path: Path = VOCAB) -> dict:
    return validate(json.loads(packet_path.read_text(encoding="utf-8")),
                    json.loads(vocabulary_path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        print(json.dumps(validate_files(), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, "Japan space source-admission gate: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
