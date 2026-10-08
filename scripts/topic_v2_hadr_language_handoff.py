"""Split frozen v2 HADR blind packets by source language; assemble signed reviews.

This never supplies model roles, assigns reviewers, fabricates human judgments,
compares labels, approves classification, reads live sources, or changes a DB.
A completed review still needs human identity and original-source verification.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.topic_v2_hadr_review import (  # noqa: E402
    TargetedReviewError,
    blind_packet,
    make_template,
    validate_decisions,
)

PROTOCOL = 1
LANGUAGES = {
    "en": ("P35", "P36", "P49", "P51", "P52"),
    "zh": ("P16", "P21"),
    "ja": ("P38",),
    "id": ("P57",),
    "vi": ("P44",),
    "ko": ("P58",),
}
LANGUAGE_NAMES = {
    "en": "English", "zh": "Chinese", "ja": "Japanese",
    "id": "Indonesian", "vi": "Vietnamese", "ko": "Korean",
}
FORBIDDEN_EDITOR_TERMS = (
    "positive_candidate", "negative_control", "unassessable_body",
    "review_question", "event_key", "editor provisional role",
)


class AssignmentError(ValueError):
    """A source-language packet or independent decision handoff is invalid."""


def _configuration() -> dict:
    canonical = make_template()
    actual = [row["pilot_id"] for row in canonical["records"]]
    selected = [pid for values in LANGUAGES.values() for pid in values]
    if (len(actual) != 11 or len(set(actual)) != 11 or
            len(selected) != 11 or len(set(selected)) != 11 or
            set(actual) != set(selected)):
        raise AssignmentError("language coverage no longer matches the frozen 11 records")
    if (next(r for r in canonical["records"] if r["pilot_id"] == "P36")["body_chars"]
            != 0):
        raise AssignmentError("P36 missing-body contract changed")
    return canonical


def make_assignment(language: str) -> dict:
    canonical = _configuration()
    if language not in LANGUAGES:
        raise AssignmentError("unsupported source language")
    allowed = set(LANGUAGES[language])
    return {
        "assignment_protocol": PROTOCOL,
        "source_language": language,
        "source_language_name": LANGUAGE_NAMES[language],
        "contract": {k: copy.deepcopy(v) for k, v in canonical.items()
                     if k != "records"},
        "records": [copy.deepcopy(row) for row in canonical["records"]
                    if row["pilot_id"] in allowed],
    }


def packet_for_language(language: str) -> str:
    """Cut only the already-blinded #164 Markdown, never editor case metadata."""
    if language not in LANGUAGES:
        raise AssignmentError("unsupported source language")
    _configuration()
    source = blind_packet()
    sections = re.split(r"(?=^## P\d\d\b)", source, flags=re.MULTILINE)
    preface = sections[0]
    by_id = {}
    for section in sections[1:]:
        matched = re.match(r"## (P\d\d)\b", section)
        if matched is None or matched.group(1) in by_id:
            raise AssignmentError("corrupted/duplicate blind packet section")
        by_id[matched.group(1)] = section
    if set(by_id) != set(pid for ids in LANGUAGES.values() for pid in ids):
        raise AssignmentError("source-first blind packet coverage drift")
    packet = (
        preface +
        "\n## Language-specific reviewer assignment\n\n" +
        "Source language: " + LANGUAGE_NAMES[language] + " (" + language + ").\n\n" +
        "Only assigned records are included. Read the ENTIRE pinned " +
        "original-language source from the historical archive, not only these " +
        "model-selected excerpts. Do not use model suggestions, this " +
        "subject-targeted sample, or another record's text as a judgment. " +
        "No assigned reviewer or approval is implied.\n\n" +
        "".join(by_id[pid] for pid in LANGUAGES[language])
    )
    lowered = packet.lower()
    if any(term in lowered for term in FORBIDDEN_EDITOR_TERMS):
        raise AssignmentError("model/editor-side content leaked into blind handoff")
    return packet


def validate_assignment(data: dict, language: str, *,
                        require_complete: bool = False) -> dict:
    """Check an individual language packet through the merged #164 review gate."""
    expected = make_assignment(language)
    if not isinstance(data, dict) or set(data) != set(expected):
        raise AssignmentError("unknown language assignment top-level fields")
    if (data["assignment_protocol"] != expected["assignment_protocol"] or
            data["source_language"] != language or
            data["source_language_name"] != expected["source_language_name"] or
            data["contract"] != expected["contract"]):
        raise AssignmentError("frozen reviewer assignment/provenance contract changed")
    rows = data["records"]
    if (not isinstance(rows, list) or
            len(rows) != len(expected["records"]) or
            [r.get("pilot_id") if isinstance(r, dict) else None for r in rows] !=
            [r["pilot_id"] for r in expected["records"]]):
        raise AssignmentError("assigned record membership/order changed")
    full = _configuration()
    overlay = {row["pilot_id"]: copy.deepcopy(row) for row in rows}
    full["records"] = [overlay.get(row["pilot_id"], row)
                       for row in full["records"]]
    try:
        checked = validate_decisions(full)
    except TargetedReviewError as exc:
        raise AssignmentError(str(exc)) from exc
    pending = sum(row["decision"] == "pending" for row in rows)
    if require_complete and pending:
        raise AssignmentError("language assignment has pending human reviews")
    return {
        "source_language": language,
        "assigned": len(rows),
        "reviewed": len(rows) - pending,
        "pending": pending,
        "all_eleven_human_reviewed": checked["reviewed"] == 11,
        "identity_independently_authenticated": False,
        "owner_approval": False,
        "production_assignments": 0,
    }


def assemble_assignments(assignments: list[dict], *,
                         require_complete: bool = False) -> dict:
    """Combines all six independent language packets; does NOT compare to model."""
    if len(assignments) != len(LANGUAGES):
        raise AssignmentError("assembly requires exactly six source-language packets")
    observed = set()
    entries = {}
    for data in assignments:
        if not isinstance(data, dict):
            raise AssignmentError("reviewer packet must be an object")
        lang = data.get("source_language")
        if not isinstance(lang, str) or lang not in LANGUAGES or lang in observed:
            raise AssignmentError("unknown or duplicate source-language packet")
        validate_assignment(data, lang)
        observed.add(lang)
        for row in data["records"]:
            pid = row["pilot_id"]
            if pid in entries:
                raise AssignmentError("duplicate reviewer record across languages")
            entries[pid] = copy.deepcopy(row)
    if observed != set(LANGUAGES):
        raise AssignmentError("missing source-language packet")
    merged = _configuration()
    merged["records"] = [entries[row["pilot_id"]] for row in merged["records"]]
    try:
        validate_decisions(merged, require_complete=require_complete)
    except TargetedReviewError as exc:
        raise AssignmentError(str(exc)) from exc
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    for mode in ("packet", "template"):
        p = sub.add_parser(mode)
        p.add_argument("--language", choices=sorted(LANGUAGES), required=True)
    p = sub.add_parser("validate")
    p.add_argument("--language", choices=sorted(LANGUAGES), required=True)
    p.add_argument("--decisions", type=Path, required=True)
    p.add_argument("--require-complete", action="store_true")
    p = sub.add_parser("assemble")
    p.add_argument("--decisions", type=Path, nargs="+", required=True)
    p.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        if args.mode == "packet":
            print(packet_for_language(args.language), end="")
        elif args.mode == "template":
            print(json.dumps(make_assignment(args.language),
                             ensure_ascii=False, indent=2))
        elif args.mode == "validate":
            data = json.loads(args.decisions.read_text(encoding="utf-8"))
            print(json.dumps(validate_assignment(
                data, args.language, require_complete=args.require_complete
            ), indent=2))
        else:
            packets = [json.loads(path.read_text(encoding="utf-8"))
                       for path in args.decisions]
            print(json.dumps(assemble_assignments(
                packets, require_complete=args.require_complete
            ), ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, "HADR language review handoff: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
