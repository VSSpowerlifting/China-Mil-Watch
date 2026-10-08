"""Fail-closed, read-only AFP production-admission preflight.

Combines an immutable seven-slot shadow audit with separately pinned per-run
source-review decisions. It never authenticates human identity, authorizes
source reuse, upgrades a desk, feeds the AI writer, or writes an archive.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

from scripts import audit_ph_afp_seven_day as audit
from scripts import prepare_ph_afp_run_review as review

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json\Z")


class AdmissionPreflightError(ValueError):
    """Untrusted, contradictory, or misbound source review evidence."""


def validate_manifest(raw, audit_report):
    """Allow exactly one locally pinned review document per eligible run."""
    if type(raw) is not dict or set(raw) != {"protocol", "reviews"} or \
            raw["protocol"] != "ipr_ph_afp_activation_review_manifest_v1" or \
            type(raw["reviews"]) is not list:
        raise AdmissionPreflightError("invalid review manifest protocol or shape")
    eligible = {s["run_id"]: s for s in audit_report["slots"]
                if s["status"] == "ledger_success_unverified_actions"
                and s["inserted"] > 0}
    found = {}
    for row in raw["reviews"]:
        if type(row) is not dict or set(row) != {"run_id", "state_commit", "file"}:
            raise AdmissionPreflightError("invalid per-run review manifest entry")
        rid, commit, file = row["run_id"], row["state_commit"], row["file"]
        if rid not in eligible or rid in found:
            raise AdmissionPreflightError("duplicate or ineligible run review")
        if type(commit) is not str or not SHA40.fullmatch(commit):
            raise AdmissionPreflightError("review requires a literal historical SHA")
        if type(file) is not str or not FILE.fullmatch(file) or file in \
                {r["file"] for r in found.values()}:
            raise AdmissionPreflightError("unsafe or reused local review filename")
        found[rid] = row
    return found


def summarize(audit_report, review_counts):
    """No data combination can itself authorize production or model input."""
    slots = []
    pending_review_runs = []
    held_review_runs = []
    for s in audit_report["slots"]:
        status = s["status"]
        n = s.get("inserted") if status == "ledger_success_unverified_actions" else None
        rid = s.get("run_id")
        if n is None:
            review_status = "collection_evidence_unavailable"
        elif n == 0:
            review_status = "no_insertions"
        elif rid in review_counts:
            if review_counts[rid].get("total") != n:
                raise AdmissionPreflightError("reviewed count conflicts with immutable run")
            decisions = review_counts[rid].get("decisions")
            if type(decisions) is not dict or set(decisions) != {"verified", "hold", "pending"} or \
                    any(type(decisions[k]) is not int or decisions[k] < 0 for k in decisions) or \
                    sum(decisions.values()) != n:
                raise AdmissionPreflightError("malformed or incomplete review decision counts")
            if decisions["hold"] or decisions["pending"]:
                review_status = "source_fidelity_held_not_admissible"
                held_review_runs.append(rid)
            else:
                review_status = "packet_checks_passed_identity_not_authenticated"
        else:
            review_status = "human_source_review_packet_missing"
            pending_review_runs.append(rid)
        slots.append({"date": s["date"], "collection_status": status,
                      "run_id": rid, "inserted": n, "review_status": review_status})
    supported = audit_report["all_seven_ledger_slots_supported"] is True
    all_packs = not pending_review_runs and not held_review_runs and all(
        s["collection_status"] == "ledger_success_unverified_actions"
        for s in slots)
    return {
        "protocol": "ipr_ph_afp_admission_preflight_v1",
        "desk": "philippines_afp_shadow_only",
        "state_commit": audit_report["immutable_state_commit"],
        "as_of_utc_date": audit_report["as_of_utc_date"],
        "audit_window": [audit_report["window_start"], audit_report["window_end"]],
        "slots": slots,
        "ledger_slots_supported": audit_report["successfully_supported_ledger_slots"],
        "seven_slot_ledger_gate": supported,
        "source_review_packet_gate": all_packs,
        "pending_review_runs": pending_review_runs,
        "held_review_runs": held_review_runs,
        # Seven days are a checkpoint, not production-promotion maturity.
        # docs/DESK_STRENGTH_CRITERIA.md C13 requires 30 consecutive collecting
        # days and independent Day-7, Day-14, and Day-30 human checkpoints.
        "seven_day_machine_evidence_candidate_for_human_checkpoint": supported and all_packs,
        "production_minimum_consecutive_collecting_days": 30,
        "thirty_day_continuity_assessed": False,
        "day_7_human_checkpoint_completed": False,
        "day_14_human_checkpoint_completed": False,
        "day_30_human_checkpoint_completed": False,
        "unresolved_external_gates": [
            "C13_thirty_consecutive_collecting_days_and_day_7_14_30_human_checkpoints",
            "independent_GitHub_Actions_event_and_failed_attempt_audit",
            "real_human_original_source_review_and_identity_authentication",
            "original_source_access_indexing_and_reuse_rights_ruling",
            "editorial_corroboration_and_cross_desk_attribution_review",
            "owner_written_production_and_AI_writer_authorization",
        ],
        "production_eligible": False,
        "weekly_AI_model_eligible": False,
        "desk_activated": False,
        "database_or_output_writes": 0,
    }


def evaluate(state_repo, state_commit, as_of, manifest=None, review_dir=None,
             start_date=None):
    frozen = audit.FrozenState(state_repo, state_commit)
    scorecard = audit.assess(frozen, as_of=as_of, start=start_date)
    counts = {}
    if manifest is not None:
        if review_dir is None:
            raise AdmissionPreflightError("review-dir required with manifest")
        rows = validate_manifest(manifest, scorecard)
        for rid, row in rows.items():
            original = review.make_packet(
                review.FrozenState(state_repo, row["state_commit"]), rid)
            source_path = Path(review_dir) / row["file"]
            decisions = json.loads(source_path.read_text(encoding="utf-8"))
            verified = review.validate_packet(decisions, original,
                                              require_complete=True)
            slot = next(s for s in scorecard["slots"]
                        if s.get("run_id") == rid)
            if original["target_date"] != slot["date"]:
                raise AdmissionPreflightError("review run date disagrees with audit")
            counts[rid] = verified
    return summarize(scorecard, counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-repo", required=True, type=Path)
    parser.add_argument("--state-commit", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--review-dir", type=Path)
    args = parser.parse_args()
    try:
        if (args.manifest is None) != (args.review_dir is None):
            raise AdmissionPreflightError("manifest and review-dir must be supplied together")
        manifest = (json.loads(args.manifest.read_text(encoding="utf-8"))
                    if args.manifest else None)
        report = evaluate(args.state_repo, args.state_commit, args.as_of,
                          manifest, args.review_dir, args.start_date)
        print(json.dumps(report, indent=2))
    except (AdmissionPreflightError, audit.AFPSevenDayError,
            review.AFPReviewError, OSError, ValueError, TypeError,
            sqlite3.DatabaseError, UnicodeDecodeError) as exc:
        parser.exit(1, "AFP activation preflight: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
