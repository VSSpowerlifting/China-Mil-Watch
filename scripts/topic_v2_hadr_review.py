"""Blinded, scoped human handoff for the eleven frozen v2 HADR control records.

Reads only version-pinned repository JSON; prints Markdown/JSON to stdout.
Never writes labels, reviewer decisions, archives, databases or production state.
Human review cannot be authenticated by a JSON validator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from scripts import validate_topic_v2_crossdesk_hadr as evidence

ROOT = Path(__file__).resolve().parent.parent
VOCAB = ROOT / "taxonomy" / "regional_topics.v2.json"
PROTOCOL = 1
SCOPE = "frozen_11_record_hadr_v2_editorial_review_only"
DECISIONS = frozenset(("pending", "classified", "abstain", "unassessable"))
IDENTITY = (
    "pilot_id", "desk_id", "source_slug", "source_url",
    "source_stated_date", "title_original", "origin_commit",
    "origin_blob", "origin_path", "storage_table", "record_identity",
    "body_sha256", "body_chars",
)
REVIEW = (
    "decision", "topics", "rationale", "read_full_source",
    "reviewer", "reviewed_at_utc",
)


class TargetedReviewError(ValueError):
    """Refuse an unsafe or unsupported scoped review."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs() -> tuple[dict, dict, dict]:
    # Replay frozen ledger/excerpt, event-family, and approval-state contracts.
    evidence.validate_files()
    packet = json.loads(evidence.PACKET.read_text(encoding="utf-8"))
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    if vocab.get("taxonomy_id") != "ipr_regional_topics" or vocab.get("taxonomy_version") != 2:
        raise TargetedReviewError("v2 vocabulary identity mismatch")
    topics = vocab.get("topics")
    if not isinstance(topics, list) or len(topics) != 20:
        raise TargetedReviewError("unexpected v2 topic vocabulary")
    slugs = [topic["slug"] for topic in topics]
    if len(set(slugs)) != 20 or "military_hadr" not in slugs:
        raise TargetedReviewError("incorrect v2 topic slugs")
    return packet, vocab, {"slugs": slugs, "sha256": _sha256(VOCAB)}


def _identity(case: dict) -> dict:
    return {key: case[key] for key in IDENTITY}


def make_template() -> dict:
    """Unsigned, per-record decisions. No suggested roles/event keys leak."""
    packet, _, vocab = _inputs()
    return {
        "protocol_version": PROTOCOL,
        "scope": SCOPE,
        "packet_id": packet["packet_id"],
        "packet_sha256": _sha256(evidence.PACKET),
        "pilot_ledger_sha256": _sha256(evidence.LEDGER),
        "taxonomy": {"id": "ipr_regional_topics", "version": 2,
                     "sha256": vocab["sha256"], "topic_slugs": vocab["slugs"]},
        "records": [
            {
                **_identity(case),
                "decision": "pending",
                "topics": [],
                "rationale": "",
                "read_full_source": False,
                "reviewer": {
                    "name": "",
                    "language_read": "",
                    "independent_reading_attested": False,
                    "original_language_reading_attested": False,
                },
                "reviewed_at_utc": None,
            }
            for case in packet["cases"]
        ],
    }


def blind_packet() -> str:
    """The reviewer never receives editor-assigned roles or event groups."""
    packet, vocab_data, _ = _inputs()
    lines = [
        "# Indo-Pacific Record — v2 source-first HADR review",
        "",
        "This is a purposive, model-selected eleven-record sample, not an independent",
        "or representative sample. Original excerpts were also model-selected.",
        "No proposed topics, editor candidate roles, event grouping or answers",
        "are supplied. Read each FULL pinned original-language body before deciding.",
        "A live URL is not a substitute for the pinned archived version.",
        "",
        "Vocabulary: v2. This is NOT the 60-record review or production approval.",
        "",
        "## Allowed topic definitions",
        "",
    ]
    for topic in vocab_data["topics"]:
        lines.append("- %s: %s — %s" %
                     (topic["slug"], topic["description"], topic["scope_note"]))
    for case in packet["cases"]:
        lines.extend([
            "", "## %s — %s" % (case["pilot_id"], case["desk_id"]), "",
            "Original title: " + case["title_original"], "",
            "Issuer/source: " + case["source_slug"], "",
            "Source-stated date: " + str(case["source_stated_date"]), "",
            "Source URL: " + case["source_url"], "",
            "Pinned archive: %s:%s (blob %s)" %
            (case["origin_commit"], case["origin_path"], case["origin_blob"]), "",
            "Stored table: " + case["storage_table"], "",
            "Preserved body SHA-256: " + case["body_sha256"], "",
            "Body characters: " + str(case["body_chars"]), "",
            "Original-language excerpt(s), selected by a previous model; context only:", "",
        ])
        if not case["evidence"]:
            lines.append("_No archived body/excerpt in this record. Do not borrow another record's text._")
        for item in case["evidence"]:
            lines.append("> " + item["quote"].replace("\n", "\n> "))
            lines.append("")
        lines.append("Independently decide v2 topics, abstain, or unassessable. "
                     "Do not infer a topic merely from the title or another record.")
    return "\n".join(lines) + "\n"


def _valid_utc(value: object, identity: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise TargetedReviewError(identity + ": reviewed_at_utc must be UTC and end in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise TargetedReviewError(identity + ": invalid reviewed_at_utc") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise TargetedReviewError(identity + ": reviewed_at_utc must be UTC")


def validate_decisions(data: dict, *, require_complete: bool = False) -> dict:
    """Strict targeted validation; NEVER approves a classification."""
    expected = make_template()
    if not isinstance(data, dict) or set(data) != set(expected):
        raise TargetedReviewError("unexpected review document or top-level field")
    for key in expected:
        if key != "records" and data[key] != expected[key]:
            raise TargetedReviewError("frozen review scope/provenance/taxonomy changed: " + key)
    rows = data["records"]
    if not isinstance(rows, list) or len(rows) != 11:
        raise TargetedReviewError("targeted review requires exactly eleven records")
    original = {item["pilot_id"]: item for item in expected["records"]}
    seen = set()
    counts = {key: 0 for key in sorted(DECISIONS)}
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(IDENTITY + REVIEW):
            raise TargetedReviewError("missing/extra fields in reviewer record")
        ident = row.get("pilot_id")
        if not isinstance(ident, str) or ident not in original or ident in seen:
            raise TargetedReviewError("unknown or duplicate pilot ID")
        seen.add(ident)
        exemplar = original[ident]
        if any(row[key] != exemplar[key] for key in IDENTITY):
            raise TargetedReviewError(ident + ": source identity or body digest changed")
        decision = row["decision"]
        if type(decision) is not str or decision not in DECISIONS:
            raise TargetedReviewError(ident + ": invalid decision")
        counts[decision] += 1
        topics = row["topics"]
        if (not isinstance(topics, list) or
                any(type(t) is not str for t in topics) or
                len(set(topics)) != len(topics)):
            raise TargetedReviewError(ident + ": invalid/duplicate topics")
        if any(t not in expected["taxonomy"]["topic_slugs"] for t in topics):
            raise TargetedReviewError(ident + ": unsupported v2 topic")
        if type(row["read_full_source"]) is not bool or type(row["rationale"]) is not str:
            raise TargetedReviewError(ident + ": malformed reading/rationale")
        reviewer = row["reviewer"]
        if not isinstance(reviewer, dict) or set(reviewer) != set(exemplar["reviewer"]):
            raise TargetedReviewError(ident + ": malformed reviewer")
        if (type(reviewer["name"]) is not str or
                type(reviewer["language_read"]) is not str or
                any(type(reviewer[k]) is not bool for k in (
                    "independent_reading_attested", "original_language_reading_attested"))):
            raise TargetedReviewError(ident + ": malformed reviewer attribution")
        if decision == "pending":
            if (topics or row["rationale"] or row["read_full_source"] or
                    row["reviewed_at_utc"] is not None or
                    reviewer != exemplar["reviewer"]):
                raise TargetedReviewError(ident + ": pending record contains judgments")
            continue
        if (not reviewer["name"].strip() or
                not reviewer["independent_reading_attested"]):
            raise TargetedReviewError(ident + ": actual named independent reviewer required")
        if not row["rationale"].strip():
            raise TargetedReviewError(ident + ": source-specific rationale required")
        _valid_utc(row["reviewed_at_utc"], ident)
        if decision == "classified":
            if not topics:
                raise TargetedReviewError(ident + ": classified requires topics")
        elif topics:
            raise TargetedReviewError(ident + ": unclassified decision cannot carry topics")
        if row["body_chars"] == 0 and decision != "unassessable":
            raise TargetedReviewError(ident + ": missing-body source must be unassessable")
        if decision in ("classified", "abstain"):
            if (not row["read_full_source"] or
                    not reviewer["original_language_reading_attested"] or
                    not reviewer["language_read"].strip()):
                raise TargetedReviewError(ident + ": full original-language source review required")
        if decision == "unassessable" and row["read_full_source"]:
            if (not reviewer["original_language_reading_attested"] or
                    not reviewer["language_read"].strip()):
                raise TargetedReviewError(ident + ": reading attestation inconsistent")
    if seen != set(original):
        raise TargetedReviewError("incomplete/duplicate record identity")
    if require_complete and counts["pending"]:
        raise TargetedReviewError("comparison blocked until all eleven reviews completed")
    return {
        "scope": SCOPE,
        "total": 11,
        "reviewed": 11 - counts["pending"],
        "counts": counts,
        "human_identity_independently_verified": False,
        "human_approval": False,
        "production_assignments": 0,
    }


def compare(data: dict) -> str:
    """Reveal the EDITOR packet, not earlier model v1 labels, only after closure."""
    validate_decisions(data, require_complete=True)
    packet, _, _ = _inputs()
    by_id = {r["pilot_id"]: r for r in data["records"]}
    events: dict[str, list[dict]] = defaultdict(list)
    for case in packet["cases"]:
        events[case["event_key"]].append(case)
    lines = [
        "# Scoped HADR editorial comparison — NOT gold labels",
        "",
        "All eleven decisions were format/provenance-validated, not independently authenticated.",
        "These are eleven **record** judgments across %d **event/context** groups." % len(events),
        "Editor roles are model-proposed control hypotheses; the v1 pilot is not a v2 gold set.",
        "No accuracy rates, topic approval, new corpus assignment, or corroboration are asserted.",
        "Historical immutable source replay must be recorded separately.",
        "",
        "| Event/context group | Record | Human decision | Human topics | Editor provisional role |",
        "|---|---|---|---|---|",
    ]
    for event, cases in events.items():
        for case in cases:
            choice = by_id[case["pilot_id"]]
            topics = ", ".join(choice["topics"]) or "—"
            lines.append("| %s | %s | %s | %s | %s |" % (
                event, case["pilot_id"], choice["decision"], topics, case["role"]))
    lines.extend(["", "No human approval is conferred. Resolve disagreements in a separate editorial decision.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("packet", help="print model-role-blinded source-first Markdown")
    modes.add_parser("template", help="print unsigned eleven-record v2 JSON")
    provenance = modes.add_parser("provenance", help="verify frozen source controls read-only")
    provenance.add_argument("--verify-sources", action="store_true",
                            help="opt-in immutable historical database Git blob replay")
    for mode in ("validate", "compare"):
        p = modes.add_parser(mode)
        p.add_argument("--decisions", type=Path, required=True)
        if mode == "validate":
            p.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        if args.mode == "packet":
            print(blind_packet(), end="")
        elif args.mode == "template":
            print(json.dumps(make_template(), ensure_ascii=False, indent=2))
        elif args.mode == "provenance":
            print(json.dumps(evidence.validate_files(verify_sources=args.verify_sources),
                             indent=2))
        else:
            data = json.loads(args.decisions.read_text(encoding="utf-8"))
            if args.mode == "validate":
                print(json.dumps(validate_decisions(
                    data, require_complete=args.require_complete), indent=2))
            else:
                print(compare(data))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, "targeted review: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
