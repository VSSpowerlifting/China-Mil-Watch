"""Private regional Sunday operator status, without manuscript/model authority.

Summarizes the already independently inspected full-week regional inventory.
This does NOT attest source rights, current publisher bodies, article selection,
editor approval, the Sunday attachment hash, or delivery readiness.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import timedelta

from scripts.sunday_corpus_readiness import iso_day

SCHEMA = "ipr-regional-sunday-operator-readiness/1"
INVENTORY = "ipr-regional-weekly-evidence/1"
READY_CORPUS = "candidate_for_no_send_model_preview_not_approved"
HELD_CORPUS = "hold_before_model_or_email"
ALLOWED_GATES = frozenset((
    "reporting_week_not_complete",
    "sunday_production_update_not_due",
    "same_sunday_success_marker_missing_or_stale",
    "fewer_than_two_desks_with_usable_source_text",
    "no_unscreened_or_selected_production_records",
))
ACTION_FOR = {
    "reporting_week_not_complete":
        "Complete the Saturday reporting window before claiming weekly coverage",
    "sunday_production_update_not_due":
        "Wait for the Sunday daily update and its success marker",
    "same_sunday_success_marker_missing_or_stale":
        "Independently verify the successful Sunday daily collection marker",
    "fewer_than_two_desks_with_usable_source_text":
        "Review eligible stored full-text records in at least two production desks",
    "no_unscreened_or_selected_production_records":
        "Inspect source screening and reporting-week publication coverage",
}


class OperatorReadinessError(ValueError):
    """Reject contradictory or altered evidence metadata instead of guessing."""


def require(condition, reason):
    if not condition:
        raise OperatorReadinessError(reason)


def _sha256(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")).hexdigest()


def summarize(inventory):
    """Emit metadata-only handoff blockers, never source data or authority."""
    require(isinstance(inventory, dict) and
            inventory.get("schema") == INVENTORY,
            "expected independent regional weekly inventory")
    for field in ("model_input_authorized", "editor_email_authorized",
                  "publication_authorized"):
        require(inventory.get(field) is False,
                "inventory cannot confer source-use or release authorization")
    require(inventory.get("source_trust_status") ==
            "inventory_only_not_attested_for_model_or_publication",
            "inventory does not declare unreviewed source trust")
    start, end, cutoff, observed = (
        iso_day(inventory.get(k)) for k in
        ("week_start", "week_ending", "source_as_of", "review_local_day")
    )
    require(end.weekday() == 5 and start == end - timedelta(days=6)
            and start <= cutoff <= end and cutoff <= observed,
            "invalid reporting-week calendar contract")
    coverage = inventory.get("coverage")
    evidence = inventory.get("production_evidence")
    held = inventory.get("held_production_records")
    pending = inventory.get("pending_private_research")
    require(all(isinstance(x, list) for x in (coverage, evidence, held, pending))
            and 2 <= len(coverage) <= 32 and len(evidence) <= 50000
            and len(held) <= 50000 and len(pending) <= 100,
            "missing or unbounded regional coverage arrays")
    supplied_hash = inventory.get("source_metadata_digest_sha256")
    require(isinstance(supplied_hash, str)
            and re.fullmatch(r"[0-9a-f]{64}", supplied_hash),
            "invalid regional inventory digest")
    calculated = _sha256({"evidence": evidence, "held": held,
                          "pending": pending, "coverage": coverage})
    require(calculated == supplied_hash,
            "regional inventory metadata was changed after inspection")

    cover = {}
    for line in coverage:
        require(isinstance(line, dict)
                and set(line) ==
                {"desk", "registry_status", "state", "reason", "stored",
                 "reviewable", "held", "pending_research"}
                and isinstance(line["desk"], str)
                and re.fullmatch(r"[a-z][a-z0-9_-]{1,40}", line["desk"])
                and line["desk"] not in cover
                and isinstance(line["registry_status"], str)
                and line["state"] in (
                    "reviewable", "no_qualifying_evidence",
                    "awaiting_validation", "collector_unavailable")
                and isinstance(line["reason"], str)
                and 5 <= len(line["reason"]) <= 500
                and all(type(line[k]) is int and 0 <= line[k] <= 50000
                        for k in ("stored", "reviewable", "held", "pending_research")),
                "invalid registered desk coverage")
        require(line["stored"] == line["reviewable"] + line["held"],
                "production corpus hold accounting is inconsistent")
        cover[line["desk"]] = line
    counters = {"reviewable": Counter(), "held": Counter(), "pending_research": Counter()}
    ids = set()
    for item in evidence:
        require(isinstance(item, dict) and
                type(item.get("id")) is int and item["id"] > 0
                and item["id"] not in ids and
                item.get("desk") in cover and
                item.get("lane") == "production_record" and
                item.get("scope") == "production_evidence",
                "invalid, duplicate, or nonproduction reviewable item")
        ids.add(item["id"])
        counters["reviewable"][item["desk"]] += 1
    for item in held:
        require(isinstance(item, dict) and
                type(item.get("record_id")) is int and item["record_id"] > 0
                and item["record_id"] not in ids
                and item.get("desk") in cover and
                isinstance(item.get("reason"), str),
                "invalid held record or duplicate evidence")
        ids.add(item["record_id"])
        counters["held"][item["desk"]] += 1
    pending_ids = set()
    for item in pending:
        require(isinstance(item, dict) and
                isinstance(item.get("id"), str) and
                item["id"] not in pending_ids
                and item.get("desk") in cover and
                item.get("reason") ==
                "independent_shadow_attestation_and_source_use_pending",
                "unapproved typed research cannot become production evidence")
        pending_ids.add(item["id"])
        counters["pending_research"][item["desk"]] += 1
    for desk, entry in cover.items():
        require(all(entry[k] == counters[k][desk] for k in counters),
                "desk source and hold totals do not match archived roster")
        if entry["state"] == "reviewable":
            require(entry["reviewable"] > 0, "reviewable desk has no verified pointer")

    issues = inventory.get("unmet_production_gates")
    verdict = inventory.get("production_preflight")
    require(isinstance(issues, list) and len(issues) <= 8
            and len(issues) == len(set(issues))
            and all(isinstance(x, str) and x in ALLOWED_GATES for x in issues)
            and verdict in (HELD_CORPUS, READY_CORPUS)
            and (verdict == READY_CORPUS) == (len(issues) == 0),
            "regional machine readiness contradicts full-week audit")
    calendar_full = cutoff == end and observed >= end + timedelta(days=1)
    if verdict == READY_CORPUS:
        require(calendar_full and
                len({x["desk"] for x in evidence}) >= 2,
                "machine-ready claim before Sunday or without two evidence desks")
    if not calendar_full:
        require(verdict == HELD_CORPUS,
                "partial reporting window cannot pass")
    held_reasons = dict(sorted(Counter(x["reason"] for x in held).items()))
    research_desks = dict(sorted(counters["pending_research"].items()))
    desk_view = [{
        "desk": x["desk"],
        "registry_status": x["registry_status"],
        "evidence_state": x["state"],
        "stored_count": x["stored"],
        "reviewable_count": x["reviewable"],
        "held_count": x["held"],
        "pending_unapproved_research_count": x["pending_research"],
    } for x in coverage]
    actions = list(dict.fromkeys(ACTION_FOR[issue] for issue in issues))
    if not actions:
        actions.append("Human-review current publisher originals, translation fidelity and source-use scope before drafting")
    if pending:
        actions.append("Keep Japan/Vietnam typed research on HOLD until independent source and rights review")
    if verdict == READY_CORPUS:
        actions.append("Create and verify owner-signed review docket before any separately authorized private model use")
    actions.append("Review the exact manuscript attachment separately before authorizing any Dylan delivery")
    return {
        "schema": SCHEMA,
        "week_start": start.isoformat(),
        "week_ending": end.isoformat(),
        "source_as_of": cutoff.isoformat(),
        "review_local_day": observed.isoformat(),
        "metadata_snapshot_sha256": supplied_hash,
        "machine_corpus_gate": (
            "passed_machine_only_not_model_or_email_approval" if not issues
            else "hold_before_model_and_editor_delivery"),
        "full_reporting_week_cutoff_reached": cutoff == end,
        "sunday_or_later_review_day_reached": observed > end,
        "historical_sunday_marker_cannot_be_inferred_from_this_receipt":
            observed > end + timedelta(days=1),
        "production_record_pointers": len(evidence),
        "held_production_records": len(held),
        "held_reason_counts": held_reasons,
        "pending_private_research_by_desk": research_desks,
        "desk_coverage": desk_view,
        "blocking_corpus_gates": issues,
        "operator_next_actions": actions,
        "editorial_review_stages": {
            "publisher_original_and_source_rights": "requires_independent_human_review",
            "owner_signed_source_docket": "not_proven_by_inventory",
            "AI_theme_proposal": "not_invoked_by_this_audit",
            "one_private_model_manuscript": "not_invoked_by_this_audit",
            "exact_attachment_editor_release": "separate_owner_SHA256_review_required",
            "public_brief": "separate_publication_approval_required",
        },
        "publisher_article_text_in_report": False,
        "official_publisher_silence_inferred": False,
        "model_called": False,
        "model_input_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "changes_production_archive": False,
    }
