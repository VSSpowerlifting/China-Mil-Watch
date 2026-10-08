"""Independent reviewer gate for the frozen Regional Topic Taxonomy pilot.

This CLI has no write operations, network access, database access, model calls,
or production attachment API. Output is stdout only. The initial blind packet
never reads model topic proposals or the second-pass assessment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "research" / "topic_pilot_v1" / "ledger.json"
ASSESSMENT = ROOT / "research" / "topic_pilot_v1" / "review" / "assessment.json"
PROTOCOL_VERSION = 1
DECISIONS = frozenset(("pending", "classified", "abstain", "unassessable"))


class ReviewGateError(ValueError):
    """A human-review file violates the review contract."""


def _load_json(path: Path) -> tuple[dict, str]:
    blob = path.read_bytes()
    value = json.loads(blob.decode("utf-8"))
    if not isinstance(value, dict):
        raise ReviewGateError("expected JSON object: %s" % path)
    return value, hashlib.sha256(blob).hexdigest()


def _sources(version: int) -> tuple[dict, dict, dict]:
    if type(version) is not int or version not in (1, 2):
        raise ReviewGateError("unsupported taxonomy version")
    ledger, ledger_hash = _load_json(LEDGER)
    vocabulary, taxonomy_hash = _load_json(
        ROOT / "taxonomy" / ("regional_topics.v%d.json" % version)
    )
    if vocabulary.get("taxonomy_version") != version:
        raise ReviewGateError("taxonomy file/version mismatch")
    if ledger.get("taxonomy_id") != vocabulary.get("taxonomy_id"):
        raise ReviewGateError("pilot and taxonomy identities diverge")
    records = ledger.get("records")
    if not isinstance(records, list) or len(records) != ledger.get("sample_size"):
        raise ReviewGateError("pilot sample count mismatch")
    if len({r.get("pilot_id") for r in records}) != len(records):
        raise ReviewGateError("duplicate pilot IDs")
    return ledger, {
        "ledger_sha256": ledger_hash,
        "sample_size": len(records),
    }, {
        "taxonomy_id": vocabulary["taxonomy_id"],
        "taxonomy_version": version,
        "taxonomy_sha256": taxonomy_hash,
        "topic_slugs": [t["slug"] for t in vocabulary["topics"]],
    }


def _identity(record: dict) -> dict:
    return {
        "pilot_id": record["pilot_id"],
        "record_id": record["record_id"],
        "desk_id": record["desk_id"],
        "source_url": record["canonical_url"],
        "body_sha256": record["body_sha256"],
    }


def make_template(version: int = 1) -> dict:
    """Produce unsigned, pending-only form; never populate model judgments."""
    ledger, pin, vocab = _sources(version)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "pilot": pin,
        "taxonomy": vocab,
        "reviewer": {
            "name": "",
            "independent_reading_attested": False,
        },
        "records": [
            {
                **_identity(record),
                "decision": "pending",
                "topics": [],
                "rationale": "",
                "read_full_source": False,
                "reviewed_at_utc": None,
            }
            for record in ledger["records"]
        ],
    }


def blind_packet(version: int = 1) -> str:
    """Present original-language evidence with no model labels or decisions."""
    ledger, _, vocabulary = _sources(version)
    parts = [
        "# Indo-Pacific Record — independent source-first topic review",
        "",
        "Vocabulary version: %d. The frozen sample has %d records."
        % (version, len(ledger["records"])),
        "",
        "**Blindness limit:** Excerpts were selected in the earlier model pilot, "
        "so excerpt selection is not independent. No proposed or second-pass "
        "topic labels appear here. Reviewers must inspect the entire pinned "
        "source body and original language, not just these excerpts.",
        "",
        "**Subject vocabulary:**",
        "",
    ]
    for topic in vocabulary["topic_slugs"]:
        parts.append("- " + topic)
    for record in ledger["records"]:
        parts.extend([
            "",
            "## %s — %s" % (record["pilot_id"], record["desk_id"]),
            "",
            "**Original title:** " + record["title_original"],
            "",
            "**Source-stated publication date:** " + str(record["published_date"]),
            "",
            "**Source URL:** " + record["canonical_url"],
            "",
            "**Stable identity:** %s / %s / %s"
            % (record["desk_id"], record["source_slug"], record["canonical_url"]),
            "",
            "**Preserved body SHA-256:** " + record["body_sha256"],
            "",
            "**Original source excerpts (context only):**",
            "",
        ])
        excerpts = record["evidence"]
        if not excerpts:
            parts.append("_No preserved excerpt; check source availability._")
        for excerpt in excerpts:
            # The quote is original preserved text; never synthesize a translation.
            parts.append("> " + excerpt["quote"].replace("\n", "\n> "))
            parts.append("")
        parts.append("Review independently: select relevant topic slugs, "
                     "or record abstain/unassessable and explain why.")
    return "\n".join(parts) + "\n"


def _check_timestamp(value: Any, record_id: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReviewGateError("%s: reviewed_at_utc must end with Z" % record_id)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ReviewGateError("%s: invalid UTC timestamp" % record_id)
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ReviewGateError("%s: timestamp must be UTC" % record_id)


def validate_decisions(
    decisions: dict, version: int = 1, *, require_complete: bool = False
) -> dict:
    """Validate self-attestation and provenance, without claiming it is true."""
    template = make_template(version)
    if type(decisions) is not dict:
        raise ReviewGateError("review payload must be an object")
    for key in ("protocol_version", "pilot", "taxonomy"):
        if decisions.get(key) != template[key]:
            raise ReviewGateError("%s does not match frozen review contract" % key)

    incoming = decisions.get("records")
    if not isinstance(incoming, list) or len(incoming) != len(template["records"]):
        raise ReviewGateError("review record count mismatch")
    originals = {r["pilot_id"]: r for r in template["records"]}
    reviewed = 0
    counts = {choice: 0 for choice in sorted(DECISIONS)}
    for entry in incoming:
        if not isinstance(entry, dict):
            raise ReviewGateError("review entry must be an object")
        pilot_id = entry.get("pilot_id")
        if pilot_id not in originals or not isinstance(pilot_id, str):
            raise ReviewGateError("unknown pilot ID")
        if originals[pilot_id] is None:
            raise ReviewGateError("%s appears twice" % pilot_id)
        expected = originals[pilot_id]
        if set(entry) != set(expected):
            raise ReviewGateError("%s: unexpected or missing entry fields" % pilot_id)
        for field in _identity(expected):
            if entry.get(field) != expected[field]:
                raise ReviewGateError("%s: %s identity changed" % (pilot_id, field))
        originals[pilot_id] = None  # every identity occurs exactly once
        decision = entry.get("decision")
        if decision not in DECISIONS:
            raise ReviewGateError("%s: invalid decision" % pilot_id)
        counts[decision] += 1
        topics = entry.get("topics")
        if not isinstance(topics, list) or len(topics) != len(set(map(str, topics))):
            raise ReviewGateError("%s: invalid or duplicate topics" % pilot_id)
        if any(type(x) is not str or x not in template["taxonomy"]["topic_slugs"] for x in topics):
            raise ReviewGateError("%s: unknown topic for selected version" % pilot_id)
        if not isinstance(entry.get("rationale"), str):
            raise ReviewGateError("%s: rationale must be text" % pilot_id)
        if type(entry.get("read_full_source")) is not bool:
            raise ReviewGateError("%s: read_full_source must be boolean" % pilot_id)
        if decision == "pending":
            if (topics or entry["rationale"] or entry["read_full_source"] or
                    entry.get("reviewed_at_utc") is not None):
                raise ReviewGateError("%s: pending record contains judgment" % pilot_id)
            continue
        reviewed += 1
        if decision == "classified" and not topics:
            raise ReviewGateError("%s: classified requires at least one topic" % pilot_id)
        if decision != "classified" and topics:
            raise ReviewGateError("%s: nonclassified decision has topics" % pilot_id)
        if not entry["rationale"].strip():
            raise ReviewGateError("%s: rationale required" % pilot_id)
        if decision != "unassessable" and not entry["read_full_source"]:
            raise ReviewGateError("%s: full source reading required" % pilot_id)
        _check_timestamp(entry["reviewed_at_utc"], pilot_id)
    if require_complete and reviewed != len(incoming):
        raise ReviewGateError("comparison requires all records independently reviewed")
    reviewer = decisions.get("reviewer")
    if not isinstance(reviewer, dict) or set(reviewer) != set(template["reviewer"]):
        raise ReviewGateError("reviewer metadata malformed")
    if type(reviewer["independent_reading_attested"]) is not bool:
        raise ReviewGateError("review attestation must be boolean")
    if reviewed and (
        not isinstance(reviewer["name"], str) or
        not reviewer["name"].strip() or
        not reviewer["independent_reading_attested"]
    ):
        raise ReviewGateError("reviewed records require named reviewer self-attestation")
    # A boolean attestation cannot technically prove human identity or blindness.
    return {"total": len(incoming), "reviewed": reviewed, "counts": counts}


def compare_model_passes(decisions: dict, version: int = 1) -> str:
    """Expose model suggestions only after a fully completed signed review."""
    result = validate_decisions(decisions, version, require_complete=True)
    if version != 1:
        raise ReviewGateError(
            "cross-version comparison needs an explicit mapping; do not "
            "compare v2 labels directly with v1 model suggestions"
        )
    ledger, _ = _load_json(LEDGER)
    second, _ = _load_json(ASSESSMENT)
    initial = {r["pilot_id"]: [p["topic"] for p in r["proposals"]]
               for r in ledger["records"]}
    suggestions = {r["pilot_id"]: r["recommended_topics"]
                   for r in second["records"]}
    reviewed = {r["pilot_id"]: r["topics"] for r in decisions["records"]}
    if set(initial) != set(suggestions) or set(initial) != set(reviewed):
        raise ReviewGateError("model/review identities differ")
    lines = [
        "# Independent-review comparison — descriptive, not a gold-set certification",
        "",
        "The reviewer self-attested to an independent original-source reading. "
        "This script cannot verify human identity, blindness, or factual truth.",
        "",
        "Reviewed: %d records. Comparison shown only after full completion."
        % result["reviewed"],
        "",
        "| Record | Human-listed topics | Initial model proposal | Second model pass |",
        "|---|---|---|---|",
    ]
    for pilot_id in sorted(initial):
        def fmt(labels: list[str]) -> str:
            return ", ".join(sorted(labels)) or "—"
        lines.append("| %s | %s | %s | %s |" %
                     (pilot_id, fmt(reviewed[pilot_id]),
                      fmt(initial[pilot_id]), fmt(suggestions[pilot_id])))
    lines.extend(["", "Differences are descriptive, not accuracy or "
                  "inter-rater reliability estimates. Human adjudication "
                  "must be recorded and authorized separately.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-version", type=int, default=1, choices=(1, 2))
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("packet", help="print source-first, proposal-blind markdown")
    modes.add_parser("template", help="print unsigned blank review JSON")
    check = modes.add_parser("validate", help="validate user-edited review JSON")
    check.add_argument("--decisions", type=Path, required=True)
    check.add_argument("--require-complete", action="store_true")
    comparison = modes.add_parser("compare", help="reveal proposals after complete review")
    comparison.add_argument("--decisions", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "packet":
            print(blind_packet(args.taxonomy_version), end="")
        elif args.mode == "template":
            print(json.dumps(make_template(args.taxonomy_version),
                             ensure_ascii=False, indent=2))
        else:
            decisions, _ = _load_json(args.decisions)
            if args.mode == "validate":
                result = validate_decisions(
                    decisions, args.taxonomy_version,
                    require_complete=args.require_complete,
                )
                print(json.dumps(result, sort_keys=True))
            else:
                print(compare_model_passes(decisions, args.taxonomy_version))
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, "review gate: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
