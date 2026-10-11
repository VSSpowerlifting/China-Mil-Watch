"""Read-only, fail-closed check for the provisional regional topic owner queue.

This validator checks a model-authored editorial triage artifact against the
unchanged, merged 60-record pilot and its skeptical second pass. It never
generates human approval, reads production/shadow databases, or writes labels.

Run:
    python3 scripts/validate_topic_owner_queue.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "research" / "topic_pilot_v1" / "OWNER_DECISION_QUEUE.json"
LEDGER = ROOT / "research" / "topic_pilot_v1" / "ledger.json"
ASSESSMENT = ROOT / "research" / "topic_pilot_v1" / "review" / "assessment.json"

# These fixed groups record the editorial triage decision; regrouping needs
# explicit new editorial review, never an accidental spreadsheet reshuffle.
EXPECTED_GROUPS = {
    "gray_zone_military_pressure": ("P01",),
    "history_and_out_of_region": ("P05", "P10"),
    "geography_and_access": ("P12", "P25", "P59"),
    "capability_and_civilian_security": (
        "P18", "P22", "P23", "P42", "P43", "P44",
    ),
    "composite_and_materiality": ("P19", "P31", "P33"),
    "economic_resilience_and_hadr": ("P38", "P46", "P47"),
    "partnership_materiality": ("P58",),
}
ITEM_FIELDS = {
    "pilot_id", "desk_id", "source_url", "source_date", "original_title",
    "body_sha256", "initial_model_topics", "second_model_topics",
    "owner_question", "owner_decision", "decision_rationale", "reviewer",
    "reviewed_at_utc",
}
ROOT_FIELDS = {
    "queue_id", "status", "purpose", "source_refs",
    "owner_review_complete", "workflow_boundaries", "clusters",
}


class OwnerQueueError(ValueError):
    """The source-pinned editorial queue is incomplete or misrepresented."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise OwnerQueueError(message)


def _blob_sha(value: bytes) -> str:
    """Git blob SHA-1, including Git's length-prefixed object header."""
    return hashlib.sha1(
        b"blob " + str(len(value)).encode("ascii") + b"\0" + value
    ).hexdigest()


def _unique_rows(rows: list, id_field: str, name: str) -> dict:
    _require(type(rows) is list, name + " must be a list")
    result = {}
    for row in rows:
        _require(type(row) is dict and
                 type(row.get(id_field)) is str and row[id_field],
                 name + " has malformed record ID")
        ident = row[id_field]
        _require(ident not in result, name + " has duplicate ID: " + ident)
        result[ident] = row
    return result


def validate(queue: dict, ledger: dict, assessment: dict,
             ledger_sha: str, assessment_sha: str) -> dict:
    """Validate source, coverage and nonapproval; never modify the arguments."""
    _require(type(queue) is dict and set(queue) == ROOT_FIELDS,
             "queue metadata fields differ")
    _require(queue["queue_id"] ==
             "ipr_regional_topics_owner_questions_2026-10-07",
             "queue identity changed")
    _require(queue["status"] == "pending_owner_source_judgment" and
             queue["owner_review_complete"] is False,
             "queue may not declare a completed/approved review")
    _require(type(queue["purpose"]) is str and
             "blinded" in queue["purpose"].lower(),
             "queue must disclose that it is NOT suitable for blind review")
    _require(queue["workflow_boundaries"] == {
        "production_assignment": False,
        "human_gold_labels": False,
        "vocabulary_activation": False,
    }, "queue improperly authorizes classification or activation")
    refs = queue["source_refs"]
    _require(type(refs) is dict and set(refs) == {
        "repository", "pilot_merged_pr", "ledger_path", "ledger_blob_sha",
        "assessment_path", "assessment_blob_sha", "reviewed_head",
        "v2_scope_proposal_pr", "v2_implementation_pr",
        "independent_review_gate_pr",
    }, "source-ref schema changed")
    _require(refs["repository"] == "VSSpowerlifting/China-Mil-Watch" and
             refs["pilot_merged_pr"] == 128 and
             refs["v2_scope_proposal_pr"] == 133 and
             refs["v2_implementation_pr"] == 137 and
             refs["independent_review_gate_pr"] == 142,
             "queue source or workflow reference drift")
    _require(refs["ledger_path"] == "research/topic_pilot_v1/ledger.json" and
             refs["assessment_path"] ==
             "research/topic_pilot_v1/review/assessment.json",
             "source paths changed")
    _require(refs["ledger_blob_sha"] == ledger_sha and
             refs["assessment_blob_sha"] == assessment_sha,
             "frozen Git blob pin mismatch")
    _require(type(ledger) is dict and type(assessment) is dict and
             ledger.get("sample_size") == 60 and
             ledger.get("taxonomy_version") == 1 and
             assessment.get("human_approved") is False and
             assessment.get("reviewed_head") == refs["reviewed_head"],
             "pilot/assessment provenance or approval state changed")
    by_pilot = _unique_rows(ledger.get("records"), "pilot_id", "pilot")
    by_review = _unique_rows(
        assessment.get("records"), "pilot_id", "second-pass"
    )
    _require(len(by_pilot) == len(by_review) == 60 and
             set(by_pilot) == set(by_review),
             "the two pilot passes do not cover the same 60 records")

    flagged = {
        ident for ident, item in by_review.items()
        if type(item.get("owner_question")) is str and
        item["owner_question"].strip()
    }
    _require(len(flagged) == 19, "source owner-question count changed")
    groups = queue["clusters"]
    _require(type(groups) is list and
             len(groups) == len(EXPECTED_GROUPS),
             "expected seven editorial policy groups")
    seen_groups, seen_ids = set(), set()
    for group in groups:
        _require(type(group) is dict and set(group) ==
                 {"key", "title", "ids", "guideline", "items"},
                 "editorial cluster schema changed")
        key = group["key"]
        _require(type(key) is str and key in EXPECTED_GROUPS and
                 key not in seen_groups,
                 "duplicate or unfamiliar policy cluster")
        seen_groups.add(key)
        _require(type(group["title"]) is str and
                 bool(group["title"].strip()) and
                 type(group["guideline"]) is str and
                 bool(group["guideline"].strip()),
                 "cluster lacks editorial context")
        _require(group["ids"] == list(EXPECTED_GROUPS[key]),
                 "frozen policy case grouping changed: " + key)
        items = group["items"]
        _require(type(items) is list and
                 len(items) == len(group["ids"]),
                 "group record count differs: " + key)
        for idx, row in enumerate(items):
            _require(type(row) is dict and set(row) == ITEM_FIELDS,
                     "owner decision row has extra/missing fields")
            ident = group["ids"][idx]
            _require(row["pilot_id"] == ident and ident not in seen_ids,
                     "owner case duplicated, missing or reordered: " + ident)
            seen_ids.add(ident)
            original = by_pilot[ident]
            second = by_review[ident]
            _require(row["desk_id"] == original["desk_id"] ==
                     second["desk_id"] and
                     row["source_url"] == original["canonical_url"] ==
                     second["source_url"] and
                     row["source_date"] == original["published_date"] ==
                     second["source_date"] and
                     row["original_title"] == original["title_original"] and
                     row["body_sha256"] == original["body_sha256"] ==
                     second["body_sha256"],
                     "original source provenance altered: " + ident)
            initial = [proposal["topic"] for proposal in
                       original["proposals"]]
            _require(row["initial_model_topics"] == initial ==
                     second["original_topics"] and
                     row["second_model_topics"] ==
                     second["recommended_topics"],
                     "model suggestions have changed: " + ident)
            _require(row["owner_question"] == second["owner_question"],
                     "editorial question changed: " + ident)
            _require(row["owner_decision"] is None and
                     row["decision_rationale"] is None and
                     row["reviewer"] is None and
                     row["reviewed_at_utc"] is None,
                     "no human may be manufactured by this queue: " + ident)
    _require(seen_groups == set(EXPECTED_GROUPS) and
             seen_ids == flagged,
             "queue is missing or inventing flagged review cases")
    return {
        "source_pilot": "60 frozen v1 cases, two model-authored passes",
        "case_count": len(seen_ids),
        "group_count": len(seen_groups),
        "human_decisions": 0,
        "all_source_pins_match": True,
        "production_writes": False,
    }


def validate_files(
    queue_path: Path = QUEUE,
    ledger_path: Path = LEDGER,
    assessment_path: Path = ASSESSMENT,
) -> dict:
    lbytes = ledger_path.read_bytes()
    abytes = assessment_path.read_bytes()
    return validate(
        json.loads(queue_path.read_text(encoding="utf-8")),
        json.loads(lbytes.decode("utf-8")),
        json.loads(abytes.decode("utf-8")),
        _blob_sha(lbytes), _blob_sha(abytes),
    )


if __name__ == "__main__":
    try:
        print(json.dumps(validate_files(), ensure_ascii=False, indent=2))
    except (OwnerQueueError, OSError, KeyError, TypeError,
            json.JSONDecodeError) as exc:
        raise SystemExit("Owner queue refused: %s" % exc)
