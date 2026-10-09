"""Join independent *machine* source receipts to regional Japan/Vietnam HOLDS.

Never upgrade a HOLD, never claim publisher consent or human original review.
An attestation may establish an exact historical Git extraction without proving
the publisher's current body, captured PDF bytes, or reproduction rights.
"""
from __future__ import annotations

import hashlib
import re

from core.regional_typed_research_holds import canonical
from scripts.prepare_vietnam_briefs_evidence import verified_queue

SCHEMA = "ipr-regional-typed-source-machine-reconciliation/1"
HOLDS = "ipr-regional-typed-research-holds/1"
JAPAN = "ipr-japan-private-research-attestation/1"
VIETNAM = "vietnam-mps-pilot-review-queue/1"


class MachineReceiptError(ValueError):
    """Receipts are missing, stale, contradictory, or falsely authorized."""


def need(condition, reason):
    if not condition:
        raise MachineReceiptError(reason)


def url_sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hold_index(holds):
    need(isinstance(holds, dict) and holds.get("schema") == HOLDS
         and holds.get("all_items_held_for_human_review") is True
         and holds.get("model_input_authorized") is False
         and holds.get("publication_authorized") is False
         and holds.get("editor_email_authorized") is False
         and holds.get("japan_vietnam_production_activated") is False,
         "input is not a never-approved regional HOLD report")
    rows = holds.get("items")
    need(isinstance(rows, list) and len(rows) <= 8, "unsafe typed hold roster")
    # The metadata-only HOLD report itself is a snapshot, not an authority.
    # Detect altered or reordered source rows before comparing receipts.
    expected = holds.get("typed_research_roster_sha256")
    need(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected)
         and hashlib.sha256(canonical(rows)).hexdigest() == expected,
         "regional typed HOLD roster checksum mismatch")
    counts = holds.get("counts")
    need(isinstance(counts, dict)
         and counts.get("japan") ==
         sum(row.get("desk") == "japan" for row in rows if isinstance(row, dict))
         and counts.get("vietnam") ==
         sum(row.get("desk") == "vietnam" for row in rows if isinstance(row, dict)),
         "regional typed HOLD desk counts mismatch")
    by_id = {}
    for item in rows:
        need(isinstance(item, dict)
             and isinstance(item.get("id"), str)
             and item["id"] not in by_id
             and item.get("desk") in ("japan", "vietnam")
             and item.get("state") ==
             "hold_independent_original_version_and_source_use_review"
             and item.get("private_model_input_authorized") is False
             and item.get("publication_authorized") is False
             and item.get("production_record") is False,
             "invalid typed HOLD identity or authority")
        by_id[item["id"]] = item
    need(isinstance(holds.get("week_ending"), str)
         and isinstance(holds.get("source_as_of"), str)
         and isinstance(holds.get("source_metadata_digest_sha256"), str)
         and re.fullmatch(r"[0-9a-f]{64}",
                          holds["source_metadata_digest_sha256"]),
         "missing exact week and inventory digest")
    return by_id


def reconcile_machine_receipts(holds, japan=None, vietnam_queues=None):
    """Compare separately verified history to exact held ID/version fingerprints.

    A queue digest protects queue consistency, NOT source authenticity:
    operator must independently regenerate Vietnam's queue using the existing
    verified shadow-state exporter. This function never obtains Git/URL bytes.
    """
    indexed = _hold_index(holds)
    week = holds["week_ending"]
    result = []
    japan_held = {i: x for i, x in indexed.items() if x["desk"] == "japan"}
    vietnam_held = {i: x for i, x in indexed.items() if x["desk"] == "vietnam"}
    need((japan is None or isinstance(japan, dict))
         and (vietnam_queues is None or
              (isinstance(vietnam_queues, list) and
               len(vietnam_queues) <= 4 and
               all(isinstance(q, dict) for q in vietnam_queues))),
         "machine receipts must be bounded validated JSON objects")
    if japan is not None:
        need(japan.get("schema") == JAPAN
             and japan.get("status") ==
             "exact_versions_verified_not_editorial_approval"
             and japan.get("week_ending") == week
             and japan.get("as_of") == holds["source_as_of"]
             and japan.get("human_source_review_completed") is False
             and japan.get("editorial_inclusion_approved") is False
             and japan.get("japan_production_eligible") is False
             and japan.get("archived_original_pdf_bytes_verified") is False
             and japan.get("smtp_or_production_writes") == 0,
             "Japan attestation falsely claims review or mismatches reporting week")
        evidence = japan.get("evidence")
        need(isinstance(evidence, list) and len(evidence) == len(japan_held)
             and japan.get("japan_records") == len(evidence),
             "Japan machine-attested roster differs from held records")
        seen = set()
        for entry in evidence:
            need(isinstance(entry, dict)
                 and isinstance(entry.get("id"), str)
                 and entry["id"] in japan_held and entry["id"] not in seen,
                 "new, duplicate, or missing Japan typed identity")
            ident = entry["id"]
            seen.add(ident)
            hold = japan_held[ident]
            need(isinstance(entry.get("publisher_url"), str)
                 and url_sha(entry["publisher_url"]) ==
                 hold["publisher_url_sha256"]
                 and entry.get("publication_date") == hold["published_date"],
                 "Japan publisher identity/date changed")
            if hold["source_kind"] == "shadow-extracted-original":
                need(entry.get("verification_class") ==
                     "immutable_shadow_extracted_text_digest_only"
                     and entry.get("pinned_state_commit") == hold["state_commit"]
                     and entry.get("text_sha256") == hold["source_content_sha256"]
                     and entry.get("archived_extracted_text_verified") is True
                     and entry.get("archived_original_pdf_bytes_verified") is False
                     and entry.get("full_pdf_human_fidelity_review_complete") is False,
                     "Japan immutable extracted-text evidence not pinned")
                level = "historical_extracted_text_digest_machine_checked_only"
            else:
                need(hold["source_kind"] ==
                     "official-publisher-page-reviewed-for-research"
                     and hold["historical_version_pin_structurally_present"] is False
                     and entry.get("verification_class") ==
                     "publisher_url_and_date_metadata_only"
                     and entry.get("original_html_body_pinned") is False
                     and entry.get("source_body_human_verified") is False,
                     "Japan HTML page improperly claims archived source")
                level = "publisher_metadata_only_original_body_missing"
            result.append({"id": ident, "desk": "japan", "machine_reconciliation": level,
                           "human_original_or_reuse_review_pending": True,
                           "eligible_for_regional_model": False})
        need(seen == set(japan_held), "Japan roster incomplete")
    else:
        result.extend({"id": ident, "desk": "japan",
                       "machine_reconciliation": "independent_machine_receipt_missing",
                       "human_original_or_reuse_review_pending": True,
                       "eligible_for_regional_model": False} for ident in japan_held)
    # A single reporting week may contain multiple historical MPS commit
    # pins. The Oct10 packet has TWO distinct commits: the Oct5 notes
    # use 46f6..., while the Oct7 Australia note uses c7c13....
    # Never silently treat one aggregate queue as attesting both snapshots.
    queue_by_commit = {}
    for queue in vietnam_queues or []:
        need(queue.get("schema") == VIETNAM and len(vietnam_held) <= 5,
             "not the bounded foreign-affairs ministry research queue")
        try:
            records = verified_queue(queue)
        except (ValueError, TypeError, KeyError) as exc:
            raise MachineReceiptError("Vietnam queue checksum/source contract failed") from exc
        commit = queue["state_commit"]
        need(commit not in queue_by_commit
             and commit in {h["state_commit"] for h in vietnam_held.values()},
             "duplicated or unrelated Vietnam state-commit receipt")
        by_identity = {}
        for row in records:
            ident = row.get("source_identity")
            need(isinstance(ident, str) and ident not in by_identity,
                 "malformed or duplicate Vietnam queue identity")
            by_identity[ident] = row
        queue_by_commit[commit] = by_identity
    for ident, hold in vietnam_held.items():
        match = re.fullmatch(r"VN-MPS-([1-9][0-9]{9})", ident)
        need(match is not None, "unknown Vietnam typed ID family")
        snapshot = queue_by_commit.get(hold["state_commit"])
        if snapshot is None:
            level = "exact_historical_commit_review_queue_not_supplied"
        else:
            entry = snapshot.get("mps-vi:" + match.group(1))
            need(entry is not None
                 and entry.get("published_date") == hold["published_date"]
                 and entry.get("content_sha256") == hold["source_content_sha256"]
                 and isinstance(entry.get("canonical_url"), str)
                 and url_sha(entry["canonical_url"]) ==
                 hold["publisher_url_sha256"]
                 and entry.get("human_source_reviewed") is False
                 and entry.get("reuse_rights_reviewed") is False
                 and entry.get("production_publication_authorized") is False,
                 "Vietnam queue source is absent, stale or falsely approved")
            level = ("queue_version_machine_eligible_not_human_approved"
                     if entry.get("machine_review_candidate") is True
                     and entry.get("machine_blockers") == []
                     and entry.get("body_status") == "text"
                     else "queue_version_machine_held")
        result.append({"id": ident, "desk": "vietnam",
                       "machine_reconciliation": level,
                       "human_original_or_reuse_review_pending": True,
                       "eligible_for_regional_model": False})
    result.sort(key=lambda x: (x["desk"], x["id"]))
    need(len(result) == len(indexed), "machine receipt did not account for every hold")
    return {
        "schema": SCHEMA,
        "week_ending": week,
        "regional_inventory_digest_sha256": holds["source_metadata_digest_sha256"],
        "typed_hold_roster_sha256": holds["typed_research_roster_sha256"],
        "japan_attestation_supplied": japan is not None,
        "vietnam_queue_commits_supplied": sorted(queue_by_commit),
        "items": result,
        "original_publisher_current_version_not_proven": True,
        "historical_archive_is_not_source_reuse_permission": True,
        "human_original_language_review_pending": True,
        "source_reuse_approval_pending": True,
        "model_input_authorized": False,
        "editor_email_authorized": False,
        "production_desk_promoted": False,
        "publication_authorized": False,
    }
