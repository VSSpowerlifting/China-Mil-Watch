"""Compose pre-existing country desk checkpoint receipts; never issue approval.

Consumes only the *outputs* of existing immutable-source review tools. This is
not a collector, Actions fetcher, source-review validator, rights adjudicator,
deployment path or promotion gate. Every real acceptance remains external.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

SCHEMA = "ipr-country-desk-checkpoint-intake/1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_BYTES = 2_000_000
VIETNAM_BRANCHES = {
    "vn_mps_foreign_affairs_vi": "shadow/vietnam-mps-foreign-affairs",
    "vn_moit_energy_vi": "shadow/vietnam-moit-energy",
    "vn_moit_foundational_industry_vi": "shadow/vietnam-moit-foundational-industry",
}
MILESTONES = {
    "day-07": "2026-10-14",
    "day-14": "2026-10-21",
    "day-30": "2026-11-06",
}
EXTERNAL_HOLDS = [
    "independent_complete_Actions_attempt_and_failure_artifact_review",
    "named_human_original_publisher_and_content_version_review",
    "separate_source_action_rights_and_robots_review",
    "approved_private_evidence_custody_and_public_projection",
    "C1_C13_and_30_consecutive_days_with_Day7_14_30_checkpoints",
    "written_owner_source_admission_and_release_decisions",
]


class CheckpointRefused(ValueError):
    """Mixed, stale, fabricated, malformed or unbound evidence."""


def require(ok, why):
    if not ok:
        raise CheckpointRefused(why)


def day(value):
    require(type(value) is str, "date must be a canonical YYYY-MM-DD string")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise CheckpointRefused("invalid date") from None
    require(result.isoformat() == value, "noncanonical date")
    return result


def sha40(value):
    return type(value) is str and HEX40.fullmatch(value) is not None


def false_flags(obj, fields):
    require(type(obj) is dict, "report must be an object")
    for field in fields:
        require(obj.get(field) is False,
                "unsafe or unknown approval claim: " + field)


def read_report(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(),
            "report must be a regular local file")
    require(0 < path.stat().st_size <= MAX_BYTES, "report is empty or oversized")

    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "duplicate JSON field")
            out[key] = value
        return out

    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except CheckpointRefused:
        # Preserve a specific duplicate-key rejection rather than hiding it
        # behind the generic malformed-JSON error.
        raise
    except (ValueError, UnicodeError) as exc:
        raise CheckpointRefused("invalid report JSON") from exc
    require(type(raw) is dict, "report root must be an object")
    return raw


def result(desk, as_of, checkpoint, evidence, machine_candidate, holds):
    # Never turn machine evidence into source permission, desk status or
    # editorial/model eligibility. Only known fixed metadata is emitted.
    return {
        "schema": SCHEMA,
        "desk": desk,
        "as_of_utc": as_of,
        "checkpoint": checkpoint,
        "machine_status": ("candidate_for_human_checkpoint" if machine_candidate
                           else "machine_evidence_incomplete_or_held"),
        "machine_evidence": evidence,
        "machine_holds": sorted(set(holds)),
        "external_holds": list(EXTERNAL_HOLDS),
        "human_checkpoint_authenticated": False,
        "complete_Actions_history_authenticated": False,
        "source_reuse_rights_approved": False,
        "private_custody_approved": False,
        "C13_satisfied": False,
        "production_eligible": False,
        "public_records_admitted": False,
        "weekly_model_eligible": False,
        "desk_activated": False,
        "deployment_authorized": False,
        "source_or_output_writes": 0,
    }


def philippines(preflight, actions):
    require(preflight.get("protocol") == "ipr_ph_afp_admission_preflight_v1"
            and preflight.get("desk") == "philippines_afp_shadow_only",
            "not an AFP original-source preflight")
    require(actions.get("protocol") == "ipr_ph_afp_actions_positive_match_v1"
            and actions.get("desk") == "ph-afp",
            "not an AFP Actions-positive-match report")
    false_flags(preflight, (
        "production_eligible", "weekly_AI_model_eligible", "desk_activated",
        "thirty_day_continuity_assessed", "day_7_human_checkpoint_completed",
        "day_14_human_checkpoint_completed", "day_30_human_checkpoint_completed"))
    false_flags(actions, (
        "production_eligible", "weekly_ai_writer_eligible",
        "export_query_scope_independently_authenticated",
        "historical_failed_and_rerun_attempts_exhaustively_audited",
        "github_metadata_signed_or_authenticated_by_script",
        "human_reviews_or_reuse_rights_approved"))
    state = preflight.get("state_commit")
    require(sha40(state) and actions.get("state_commit") == state,
            "AFP source commit mismatch")
    as_of = preflight.get("as_of_utc_date")
    require(day(as_of) == day(actions.get("as_of_utc_date")), "AFP as-of mismatch")
    window = preflight.get("audit_window")
    require(type(window) is list and len(window) == 2,
            "AFP seven-day window missing")
    start, end = (day(v) for v in window)
    require(end - start == timedelta(days=6) and
            actions.get("window_start") == start.isoformat() and
            actions.get("window_end") == end.isoformat() and
            start >= date(2026, 10, 7),
            "AFP evidence windows do not match")
    slots, a_slots = preflight.get("slots"), actions.get("slots")
    require(type(slots) is list and len(slots) == 7 and
            type(a_slots) is list and len(a_slots) == 7,
            "AFP requires exactly seven matched slots")
    supported = matched = 0
    holds = []
    seen_run_ids = set()
    expected_pending, expected_held = [], []
    for i, (slot, att) in enumerate(zip(slots, a_slots)):
        require(type(slot) is dict and type(att) is dict and
                slot.get("date") == (start + timedelta(days=i)).isoformat()
                and att.get("date") == slot["date"]
                and att.get("run_id") == slot.get("run_id"),
                "AFP slot date or run identity mismatch")
        is_supported = slot.get("collection_status") == "ledger_success_unverified_actions"
        supported += is_supported
        run_id = slot.get("run_id")
        if is_supported:
            require(type(run_id) is str and run_id not in seen_run_ids,
                    "AFP scheduled run IDs must be unique")
            seen_run_ids.add(run_id)
        count = slot.get("inserted")
        review_status = slot.get("review_status")
        if count is None:
            require(not is_supported and review_status == "collection_evidence_unavailable",
                    "AFP unavailable ledger cannot have a source review")
        else:
            require(is_supported and type(count) is int and count >= 0,
                    "AFP inserted count disagrees with the ledger")
            if count == 0:
                require(review_status == "no_insertions",
                        "AFP zero-insertion slot has a fabricated review")
            else:
                require(review_status in (
                    "human_source_review_packet_missing",
                    "source_fidelity_held_not_admissible",
                    "packet_checks_passed_identity_not_authenticated"),
                    "AFP per-run review status is unrecognized")
                if review_status == "human_source_review_packet_missing":
                    expected_pending.append(run_id)
                if review_status == "source_fidelity_held_not_admissible":
                    expected_held.append(run_id)
        require((att.get("status") in ("actions_success_matches_ledger", "actions_unverified")
                 if is_supported else
                 att.get("status") == "not_eligible_for_actions_match"),
                "AFP Actions slot contradicts ledger")
        matched += att.get("status") == "actions_success_matches_ledger"
        if att.get("status") == "actions_unverified":
            holds.append("unverified_AFP_Actions_slot_" + slot["date"])
        if not is_supported:
            holds.append("missing_or_invalid_AFP_ledger_" + slot["date"])
    require(preflight.get("ledger_slots_supported") == supported and
            preflight.get("seven_slot_ledger_gate") is (supported == 7) and
            actions.get("matched_scheduled_successes") == matched and
            actions.get("all_seven_positive_runs_matched") is (matched == 7 and supported == 7),
            "AFP summary counts disagree with seven slots")
    pending, held = preflight.get("pending_review_runs"), preflight.get("held_review_runs")
    require(type(pending) is list and type(held) is list and
            all(type(x) is str for x in pending + held),
            "AFP review packet inventories malformed")
    packet_ok = preflight.get("source_review_packet_gate")
    require(type(packet_ok) is bool, "AFP review-packet gate must be explicit")
    require(pending == expected_pending and held == expected_held,
            "AFP per-run review inventories disagree with slot statuses")
    require(packet_ok is (supported == 7 and not pending and not held),
            "AFP source review gate contradicts its packet inventory")
    require(preflight.get("seven_day_machine_evidence_candidate_for_human_checkpoint")
            is (supported == 7 and packet_ok) and
            preflight.get("production_minimum_consecutive_collecting_days") == 30,
            "AFP milestone or 30-day threshold disagrees with preflight")
    if not packet_ok:
        holds.append("AFP_original_source_review_packets_incomplete_or_held")
    other = actions.get("other_scheduled_runs_in_export")
    require(type(other) is list, "AFP additional Actions inventory missing")
    if other:
        holds.append("AFP_unreconciled_scheduled_Actions_events")
    if day(as_of) < end:
        holds.append("AFP_checkpoint_window_not_elapsed")
    candidate = supported == 7 and matched == 7 and packet_ok and not other and day(as_of) >= end
    return result("philippines_afp", as_of, "day-07", {
        "state_commit": state,
        "window": [start.isoformat(), end.isoformat()],
        "verified_ledger_slots": supported,
        "positive_Actions_matches": matched,
        "original_source_packet_machine_gate": packet_ok,
        "extra_scheduled_Actions_events_need_review": bool(other),
    }, candidate, holds)


def vietnam(rollup, bridge):
    require(rollup.get("schema") == "ipr-vietnam-three-source-checkpoint-rollup/1"
            and rollup.get("desk_id") == "vietnam",
            "not a three-source Vietnam formal packet rollup")
    require(bridge.get("schema") == "ipr-vietnam-github-reconciler-bridge/1"
            and bridge.get("source") == "real_GitHub_REST_read_only_bounded_window",
            "not a bounded GitHub Vietnam attempt report")
    false_flags(rollup, ("human_signoff_complete",
                         "rights_to_publicly_republish_established",
                         "production_promotion_authorized", "desk_qualified"))
    false_flags(bridge, ("independent_git_history_fully_verified",
                         "complete_failed_attempt_artifact_review",
                         "owner_signed_checkpoint", "source_use_rights_approved",
                         "production_or_publication_authorized"))
    checkpoint, as_of = rollup.get("checkpoint"), rollup.get("as_of")
    require(checkpoint in MILESTONES, "unrecognized Vietnam checkpoint")
    review_day = day(as_of)
    review_window = bridge.get("review_window")
    require(type(review_window) is dict and
            review_window.get("from") == "2026-10-07"
            and review_window.get("through") == as_of,
            "Vietnam Actions audit must end on the packet's as-of date")
    state_heads = bridge.get("state_head_shas")
    counts = bridge.get("source_anomaly_counts")
    require(type(state_heads) is dict and set(state_heads) == set(VIETNAM_BRANCHES)
            and type(counts) is dict and set(counts) == set(VIETNAM_BRANCHES)
            and all(type(v) is int and 0 <= v <= 1000 for v in counts.values()),
            "Vietnam source heads or anomaly counts incomplete")
    rec = bridge.get("reconciler")
    require(type(rec) is dict and
            rec.get("schema") == "ipr-vn-ministry-attempt-reconciliation/1"
            and rec.get("review_window") == review_window
            and type(rec.get("warnings")) is list,
            "invalid Vietnam attempt reconciliation")
    false_flags(rec, ("github_attempt_inventory_independently_proven_exhaustive",
                      "failed_attempt_artifacts_independently_verified",
                      "all_scheduled_slots_proven_complete",
                      "day_7_human_signoff_complete", "desk_qualified",
                      "production_promotion_authorized", "source_rights_expanded"))
    latest = rec.get("latest_run_by_source")
    rows = rollup.get("sources")
    require(type(latest) is dict and set(latest) == set(VIETNAM_BRANCHES)
            and type(rows) is list and len(rows) == 3,
            "Vietnam triplet source identities missing")
    by_slug = {s.get("source_slug"): s for s in rows if type(s) is dict}
    require(len(by_slug) == 3 and set(by_slug) == set(VIETNAM_BRANCHES),
            "duplicate or foreign Vietnam source in packet")
    require(rollup.get("source_count") == 3
            and rollup.get("all_three_review_packets_integrity_checked") is True,
            "Vietnam formal packet integrity not proven")
    reached = []
    holds = []
    out = []
    for slug in sorted(VIETNAM_BRANCHES):
        row = by_slug[slug]
        require(row.get("state_branch") == VIETNAM_BRANCHES[slug]
                and sha40(row.get("state_commit"))
                and row["state_commit"] == state_heads[slug]
                and row.get("as_of") == as_of and row.get("checkpoint") == checkpoint
                and type(row.get("latest_run_id")) is str
                and row["latest_run_id"] == latest[slug],
                "Vietnam packet, branch or latest Actions ledger pin mismatch: " + slug)
        false_flags(row, ("human_signoff_complete", "production_promotion_authorized"))
        for name in ("anomaly_count", "missing_collecting_days_count",
                     "uncovered_date_count", "consecutive_collecting_days_count"):
            require(type(row.get(name)) is int and row[name] >= 0,
                    "missing or invalid Vietnam source counters")
        require(type(row.get("checkpoint_reached")) is bool,
                "Vietnam source missing checkpoint threshold")
        require(row["anomaly_count"] >= counts[slug],
                "Vietnam formal packet omitted a committed source anomaly: " + slug)
        reached.append(row["checkpoint_reached"])
        if counts[slug] or row["anomaly_count"]:
            holds.append(slug + "_source_anomalies_require_disposition")
        if row["missing_collecting_days_count"] or row["uncovered_date_count"]:
            holds.append(slug + "_collection_or_window_gaps")
        if not row["checkpoint_reached"]:
            holds.append(slug + "_checkpoint_not_reached")
        out.append({
            "slug": slug,
            "state_commit": row["state_commit"],
            "checkpoint_reached_elapsed_time_only": row["checkpoint_reached"],
            "source_surface_and_other_anomalies": row["anomaly_count"],
            "missing_collecting_days": row["missing_collecting_days_count"],
            "uncovered_windows": row["uncovered_date_count"],
        })
    require(rollup.get("all_three_machine_checkpoints_reached") is all(reached)
            and rollup.get("latest_published_run_attempts_aligned") is
            (len({latest[s] for s in VIETNAM_BRANCHES}) == 1),
            "Vietnam three-source rollup contradicts its source packets")
    require(type(rollup.get("machine_warnings")) is list, "Vietnam packet warnings missing")
    if rollup["machine_warnings"]:
        holds.append("Vietnam_formal_checkpoint_warnings_require_review")
    if rec["warnings"]:
        holds.append("Vietnam_Actions_attempt_warnings_require_review")
    if any(counts.values()) or rec["warnings"]:
        require(bridge.get("status") == "needs_review",
                "Vietnam bridge hid observed warnings")
    else:
        require(bridge.get("status") == "reconciled_bounded_metadata_not_human_approved",
                "Vietnam bridge has contradictory status")
    if review_day < day(MILESTONES[checkpoint]):
        holds.append("Vietnam_checkpoint_earliest_scheduled_day_not_due")
    candidate = (all(reached) and not holds
                 and review_day >= day(MILESTONES[checkpoint]))
    return result("vietnam_three_ministry_sources", as_of, checkpoint, {
        "sources": out,
        "all_machine_elapsed_thresholds_reached": all(reached),
        "bounded_Actions_attempt_warnings": len(rec["warnings"]),
        "formal_packet_warnings": len(rollup["machine_warnings"]),
        "no_rights_or_human_signoff_inferred": True,
    }, candidate, holds)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modes = parser.add_subparsers(dest="desk", required=True)
    ph = modes.add_parser("philippines", help="AFP only; NSC remains separately held")
    ph.add_argument("--preflight", required=True, type=Path)
    ph.add_argument("--actions", required=True, type=Path)
    vn = modes.add_parser("vietnam", help="three ministry families, source-specific holds")
    vn.add_argument("--rollup", required=True, type=Path)
    vn.add_argument("--actions", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = (philippines(read_report(args.preflight), read_report(args.actions))
                  if args.desk == "philippines" else
                  vietnam(read_report(args.rollup), read_report(args.actions)))
    except (CheckpointRefused, OSError, KeyError, TypeError, OverflowError) as exc:
        parser.exit(2, "country checkpoint intake refused: %s\n" % exc)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
