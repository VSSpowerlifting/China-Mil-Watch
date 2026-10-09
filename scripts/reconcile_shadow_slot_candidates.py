"""Conservative, offline logical-slot accounting for isolated shadow collectors.

This is *not* a run, state, GitHub API, publisher or rights verifier. It
classifies only supplied evidence and never turns metadata into publication
authority. Existing source-specific, pinned audits must run independently.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.shadow_schedule import (
    SOURCE_EXPLICIT, SOURCE_MANUAL, SOURCE_SCHEDULE,
    parse_cron_utc, parse_iso_date, scheduled_slot_date,
)

SCHEMA = "ipr-shadow-slot-candidates/1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
SLUG = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")
RUN_ID = re.compile(r"([1-9][0-9]*)-([1-9][0-9]*)\Z")
SUCCESS = frozenset(("ok", "ok_no_publications", "ok_all_duplicates",
                    "ok_all_filtered"))
MAX_DAYS = 31
OBS_FIELDS = frozenset((
    "source_slug", "state_branch", "run_id", "target_date",
    "target_date_source", "github_event", "github_conclusion",
    "ledger_health", "ledger_result", "started_utc", "finished_utc",
    "new_records", "action_identity_checked", "pinned_state_checked",
))
CONTRACT_FIELDS = frozenset(("source_slug", "state_branch", "start_date",
                            "cron_utc", "grace_hours"))


class SlotEvidenceError(ValueError):
    """Malformed, contradictory or unbounded user-supplied evidence."""


def require(condition, reason):
    if not condition:
        raise SlotEvidenceError(reason)


def utc(value):
    require(type(value) is str, "UTC instant must be a string")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SlotEvidenceError("malformed UTC instant") from exc
    require(dt.tzinfo is not None and dt.utcoffset() == timedelta(0),
            "explicit zero-offset UTC instant required")
    return dt.astimezone(timezone.utc)


def exact_day(value):
    require(type(value) is str and bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)),
            "logical date must be YYYY-MM-DD")
    try:
        result = parse_iso_date(value, "logical date")
    except ValueError as exc:
        raise SlotEvidenceError("invalid logical UTC date") from exc
    return result


def validate_contract(contract, as_of):
    require(type(contract) is dict and set(contract) == CONTRACT_FIELDS,
            "unexpected or missing slot contract fields")
    source = contract["source_slug"]
    branch = contract["state_branch"]
    require(type(source) is str and bool(SLUG.fullmatch(source)),
            "invalid source identity")
    require(type(branch) is str and bool(re.fullmatch(r"shadow/[a-z0-9_/-]+", branch))
            and ".." not in branch and not branch.endswith("/"),
            "invalid explicit state branch")
    start = exact_day(contract["start_date"])
    require(type(contract["grace_hours"]) is int and
            0 <= contract["grace_hours"] <= 18,
            "invalid scheduled-run grace interval")
    try:
        hour, minute = parse_cron_utc(contract["cron_utc"])
    except ValueError as exc:
        raise SlotEvidenceError("invalid daily UTC schedule") from exc
    now = utc(as_of)
    require(start <= now.date() and 0 <= (now.date() - start).days < MAX_DAYS,
            "unbounded or future logical schedule window")
    return start, hour, minute, now


def verify_row(row, contract, now):
    require(type(row) is dict and set(row) == OBS_FIELDS,
            "malformed evidence row fields")
    require(row["source_slug"] == contract["source_slug"] and
            row["state_branch"] == contract["state_branch"],
            "source/branch identity mismatch")
    run = row["run_id"]
    require(type(run) is str and RUN_ID.fullmatch(run), "invalid Actions run identity")
    action_id, attempt = map(int, RUN_ID.fullmatch(run).groups())
    target = exact_day(row["target_date"])
    started, finished = utc(row["started_utc"]), utc(row["finished_utc"])
    require(started <= finished and finished <= now,
            "impossible or future source run interval")
    require(target <= now.date(), "future target date in evidence")
    require(row["target_date_source"] in
            (SOURCE_SCHEDULE, SOURCE_MANUAL, SOURCE_EXPLICIT),
            "unknown target date source")
    require(row["github_event"] in ("schedule", "workflow_dispatch"),
            "unsupported Actions trigger")
    require(row["github_conclusion"] in ("success", "failure", "cancelled", "timed_out"),
            "unknown Actions conclusion")
    require(row["ledger_health"] in ("ok", "fail"),
            "unknown collector health")
    require(row["ledger_result"] in SUCCESS | frozenset(("fail", "partial")),
            "unknown collector result")
    require(type(row["new_records"]) is int and row["new_records"] >= 0,
            "invalid new-record count")
    for field in ("action_identity_checked", "pinned_state_checked"):
        require(type(row[field]) is bool,
                "attestation indicator must be an explicit boolean")
    # An Actions scheduled re-run preserves event=schedule but is not an
    # original scheduled-slot attempt; only an explicit manual recovery could
    # qualify. Nor can a manual dispatch without an explicit target_date
    # impersonate a recovered scheduled day.
    mode = "nonqualifying"
    reason = "manual_without_explicit_recovery_target"
    if row["github_event"] == "schedule":
        if attempt != 1 or row["target_date_source"] != SOURCE_SCHEDULE:
            reason = "scheduled_rerun_or_noncanonical_target"
        elif scheduled_slot_date(started, contract["cron_utc"]) != target:
            reason = "scheduled_timestamp_disagrees_with_logical_slot"
        else:
            mode, reason = "scheduled", None
    elif row["target_date_source"] == SOURCE_EXPLICIT:
        # An explicitly named date is not *automatically* a recovery. A
        # dispatch before that date's nominal cron would predate the slot it
        # purports to repair. Keep the receipt visible but not qualifying.
        cron_hour, cron_minute = parse_cron_utc(contract["cron_utc"])
        nominal = datetime.combine(target, time(cron_hour, cron_minute),
                                   tzinfo=timezone.utc)
        if started < nominal:
            reason = "manual_dispatch_predates_target_slot"
        else:
            mode, reason = "recovery", None
    success = (row["github_conclusion"] == "success" and
               row["ledger_health"] == "ok" and row["ledger_result"] in SUCCESS)
    attested_by_inputs = (row["action_identity_checked"] and
                          row["pinned_state_checked"])
    return {
        "run_id": run, "actions_id": action_id, "attempt": attempt,
        "target_date": target.isoformat(),
        "mode": mode, "nonqualifying_reason": reason,
        "reported_success": success,
        "input_checks_present": attested_by_inputs,
        "new_records": row["new_records"],
    }


def reconcile(contract, observations, as_of):
    """Return due/pending candidate slots, never a production readiness verdict.

    The input attestation flags are *claims* passed by the caller. The report
    never authenticates them and always marks them non-authoritative.
    """
    start, hour, minute, now = validate_contract(contract, as_of)
    require(type(observations) is list and len(observations) <= 500,
            "unbounded or malformed run observations")
    checked = []
    seen = set()
    for row in observations:
        parsed = verify_row(row, contract, now)
        require(parsed["run_id"] not in seen, "duplicate Actions attempt identity")
        seen.add(parsed["run_id"])
        checked.append(parsed)
    by_date = {}
    for row in checked:
        by_date.setdefault(row["target_date"], []).append(row)
    slots = []
    counts = {"pending": 0, "candidate_supported": 0,
              "review_required": 0, "missing_from_supplied_evidence": 0}
    for index in range((now.date() - start).days + 1):
        day = start + timedelta(days=index)
        when = datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)
        mature = now >= when + timedelta(hours=contract["grace_hours"])
        runs = by_date.get(day.isoformat(), [])
        candidates = [r for r in runs if r["mode"] in ("scheduled", "recovery")]
        positives = [r for r in candidates if r["reported_success"] and
                     r["input_checks_present"]]
        disqualifying = [r for r in candidates if r not in positives]
        if not mature:
            status = "pending_grace"
        elif len(positives) > 1:
            status = "conflicting_multiple_success_candidates"
        elif len(positives) == 1 and disqualifying:
            status = "success_with_other_unresolved_attempt"
        elif len(positives) == 1:
            best = positives[0]
            if best["mode"] == "recovery":
                status = "explicit_manual_recovery_candidate"
            elif best["new_records"] == 0:
                status = "scheduled_success_no_new_records_candidate"
            else:
                status = "scheduled_success_new_records_candidate"
        elif candidates:
            status = "attempt_present_but_not_attested_success"
        elif runs:
            status = "only_nonqualifying_attempts_observed"
        else:
            status = "mature_slot_missing_from_supplied_evidence"
        if status == "pending_grace":
            counts["pending"] += 1
        elif status in ("explicit_manual_recovery_candidate",
                        "scheduled_success_no_new_records_candidate",
                        "scheduled_success_new_records_candidate"):
            counts["candidate_supported"] += 1
        elif status == "mature_slot_missing_from_supplied_evidence":
            counts["missing_from_supplied_evidence"] += 1
        else:
            counts["review_required"] += 1
        slots.append({
            "logical_date": day.isoformat(),
            "scheduled_at_utc": when.isoformat().replace("+00:00", "Z"),
            "matures_at_utc": (when + timedelta(hours=contract["grace_hours"]))
                .isoformat().replace("+00:00", "Z"),
            "status": status,
            "observed_run_ids": sorted(x["run_id"] for x in runs),
            "candidate_new_records": sum(x["new_records"] for x in positives),
            "new_record_count_is_not_publication_completeness": True,
        })
    return {
        "schema": SCHEMA, "source_slug": contract["source_slug"],
        "state_branch": contract["state_branch"],
        "as_of_utc": now.isoformat().replace("+00:00", "Z"),
        "start_date": start.isoformat(),
        "cron_utc": contract["cron_utc"],
        "grace_hours": contract["grace_hours"],
        "counts": counts, "slots": slots,
        "observation_count": len(checked),
        "unscoped_observations": [
            r["run_id"] for r in checked
            if r["target_date"] < start.isoformat()
        ],
        "supplied_actions_export_authenticated": False,
        "source_capture_chain_verified_by_this_audit": False,
        "all_historical_scheduled_attempts_exhaustively_observed": False,
        "government_silence_established": False,
        "desk_production_eligible": False,
        "weekly_ai_writer_eligible": False,
        "editor_delivery_authorized": False,
        "automatic_recovery_dispatched": False,
        "writes": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--observations", type=Path, required=True)
    p.add_argument("--as-of-utc", required=True)
    args = p.parse_args(argv)
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        observations = json.loads(args.observations.read_text(encoding="utf-8"))
        print(json.dumps(reconcile(contract, observations, args.as_of_utc),
                         sort_keys=True, indent=2))
    except (SlotEvidenceError, OSError, ValueError, TypeError) as exc:
        p.exit(1, "shadow logical slots: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
