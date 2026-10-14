"""Offline Korea Actions-attempt census for shared Indonesia/Korea shadow workflow.

The entire paginated workflow history and each run's artifact listing are
caller-supplied. This module verifies structural completeness and reconciles
Korea's run attempts against pinned ledger exports. It CANNOT authenticate
the caller's GitHub exports, sign Day 7 or grant source/corpus permission.
No network calls, Korean text, production DB, shadow writes or site output.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from core.shadow_schedule import scheduled_slot_date
from scripts import audit_indonesia_shadow_provenance as provenance
from scripts.audit_indonesia_actions_attempts import ARTIFACT

SCHEMA = "ipr-korea-shared-actions-attempt-inventory/1"
START = date(2026, 10, 6)
CRON = "17:47"
GRACE = timedelta(hours=6)
LOCAL = "local-native-20261006-korea"
RESULTS = frozenset(("ok", "ok_all_duplicates", "ok_no_publications", "ok_all_filtered"))


def require(ok, message):
    if not ok:
        raise provenance.ProvenanceError(message)


def scan(pages, artifacts, ledgers, *, as_of_utc):
    """Check all supplied attempts. Never infer a failed run from a green ledger."""
    now = provenance.utc(as_of_utc)
    require(START <= now.date() <= date(2026, 11, 7),
            "Korea audit date outside bounded first-month evaluation")
    actions = provenance.parse_actions_export(pages)
    require(type(artifacts) is dict and
            set(artifacts) == {str(key) for key in actions},
            "every workflow run must have an artifact-list response")
    require(type(ledgers) is list and len(ledgers) >= 1,
            "pinned Korea ledger export missing")
    by_id = {}
    for ledger in ledgers:
        require(type(ledger) is dict and
                type(ledger.get("run_id")) is str,
                "malformed Korea ledger")
        run_id = ledger["run_id"]
        require((run_id == LOCAL or provenance.RUN_ID.fullmatch(run_id)) and
                run_id not in by_id and ledger.get("desk") == "korea",
                "foreign, duplicate or malformed Korea ledger")
        by_id[run_id] = ledger

    holds, mapped, per_date, followups = [], set(), {}, []
    counts = {"workflow_runs_examined": 0, "korea_attempts": 0,
              "indonesia_attempts": 0, "unattributed_attempts": 0,
              "korea_failed_or_cancelled": 0, "korea_rerun_attempts": 0,
              "korea_missing_ledgers": 0}
    for run_id, action in sorted(actions.items()):
        require(action.get("workflow_id") == provenance.WORKFLOW_ID and
                action.get("name") == provenance.WORKFLOW_NAME,
                "wrong shared workflow in Actions export")
        created = provenance.utc(action.get("created_at"))
        if created.date() < START or created > now:
            continue
        counts["workflow_runs_examined"] += 1
        attempt = action.get("run_attempt")
        require(type(attempt) is int and attempt >= 1 and
                action.get("event") in ("schedule", "workflow_dispatch") and
                action.get("head_branch") == "main",
                "unrecognized Actions event, attempt or branch")
        result = artifacts[str(run_id)]
        require(type(result) is dict and type(result.get("total_count")) is int and
                type(result.get("artifacts")) is list and
                result["total_count"] == len(result["artifacts"]) and
                result["total_count"] <= 100,
                "incomplete or malformed artifact listing")
        scopes = set()
        for item in result["artifacts"]:
            require(type(item) is dict and type(item.get("name")) is str,
                    "malformed artifact identity")
            match = ARTIFACT.fullmatch(item["name"])
            require(match is not None and int(match[2]) == run_id and
                    int(match[3]) <= attempt,
                    "unexpected cross-run or future-attempt artifact")
            scopes.add(match[1])
        require(len(scopes) <= 1, "conflicting desks in one run's artifacts")
        scope = next(iter(scopes), "unselected")
        if scope == "indonesia":
            counts["indonesia_attempts"] += 1
            continue
        if scope == "unselected":
            counts["unattributed_attempts"] += 1
            holds.append("shared_workflow_unattributed_attempt")
            continue
        counts["korea_attempts"] += 1
        key = "%d-%d" % (run_id, attempt)
        reasons = []
        if attempt != 1:
            counts["korea_rerun_attempts"] += 1
            holds.append("korea_rerun_needs_attempt_history_review")
            reasons.append("rerun_requires_review")
        if action.get("status") != "completed" or action.get("conclusion") != "success":
            counts["korea_failed_or_cancelled"] += 1
            holds.append("korea_failed_cancelled_or_unfinished_workflow")
            reasons.append("github_action_not_successful")
        if key not in by_id:
            counts["korea_missing_ledgers"] += 1
            holds.append("korea_action_attempt_without_pinned_ledger")
            reasons.append("no_matched_state_ledger")
        else:
            mapped.add(key)
            ledger = by_id[key]
            if ledger.get("health") != "ok" or ledger.get("result") not in RESULTS:
                holds.append("korea_ledger_not_a_successful_original_capture")
                reasons.append("matched_state_ledger_not_healthy")
            if action.get("event") == "schedule":
                logical = scheduled_slot_date(created, CRON)
                if (ledger.get("target_date") != logical.isoformat() or
                        ledger.get("target_date_source") != "schedule-slot"):
                    holds.append("korea_schedule_slot_and_ledger_disagree")
                    reasons.append("scheduled_state_date_mismatch")
            elif ledger.get("target_date_source") == "schedule-slot":
                holds.append("manual_korea_run_masquerades_as_schedule")
                reasons.append("manual_event_with_scheduled_ledger")
        if reasons:
            followups.append({
                "run_attempt_id": key,
                "scheduled_target_date": (
                    scheduled_slot_date(created, CRON).isoformat()
                    if action["event"] == "schedule" else None),
                "event": action["event"],
                "reasons": reasons,
                "publisher_timeout_verified_by_this_census": False,
                "retrieval_retried": False,
                "human_review_or_desk_approval": False,
            })
        if action.get("event") == "schedule":
            logical = scheduled_slot_date(created, CRON)
            if START < logical <= now.date():
                per_date.setdefault(logical.isoformat(), []).append(key)

    bootstrap = by_id.get(LOCAL)
    if not bootstrap or bootstrap.get("health") != "ok" or \
            bootstrap.get("target_date") != START.isoformat():
        holds.append("original_local_day_zero_missing_or_unhealthy")
    missing_ledgers = sorted(set(by_id) - {LOCAL} - mapped)
    if missing_ledgers:
        holds.append("pinned_korea_ledger_absent_from_actions_inventory")

    pending, missing, duplicates = [], [], []
    current = START + timedelta(days=1)
    while current <= now.date():
        instant = datetime.combine(current, time(17, 47), timezone.utc)
        if now < instant + GRACE:
            pending.append(current.isoformat())
        else:
            ids = per_date.get(current.isoformat(), [])
            if not ids:
                missing.append(current.isoformat())
            elif len(ids) > 1:
                duplicates.append(current.isoformat())
        current += timedelta(days=1)
    if missing:
        holds.append("mature_korea_scheduled_day_without_attempt")
    if duplicates:
        holds.append("multiple_korea_scheduled_attempts_for_day")

    holds = sorted(set(holds))
    return {
        "schema": SCHEMA, "as_of_utc": now.isoformat().replace("+00:00", "Z"),
        "source_family": "kr_policy_mnd_releases",
        "state_branch": "shadow/korea-policy-briefing",
        "census_source": "caller_supplied_actions_and_artifact_exports",
        "github_export_independently_authenticated": False,
        "actions_pagination_structurally_complete": True,
        "artifact_pages_structurally_complete": True,
        "counts": counts, "mature_scheduled_dates": sorted(
            day for day in per_date if day not in pending),
        "pending_dates": pending, "missing_dates": missing,
        "duplicate_dates": duplicates,
        "pinned_ledger_unmapped_count": len(missing_ledgers),
        "attempts_needing_followup": followups,
        "holds": holds,
        "verdict": ("HOLD" if holds else "PENDING_SCHEDULED_GRACE"
                    if pending else "CONSISTENT_UNAUTHENTICATED_CENSUS_ONLY"),
        "human_day7_review_completed": False,
        "korean_original_language_review_completed": False,
        "source_rights_approved": False,
        "production_eligible": False,
        "sunday_brief_eligible": False,
        "public_new_sources_approved": False,
        "mutations": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-export", required=True, type=Path)
    parser.add_argument("--artifacts-export", required=True, type=Path)
    parser.add_argument("--korea-ledgers-export", required=True, type=Path)
    parser.add_argument("--as-of-utc", required=True)
    args = parser.parse_args(argv)
    try:
        pages = json.loads(args.runs_export.read_text(encoding="utf-8"))
        artifacts = json.loads(args.artifacts_export.read_text(encoding="utf-8"))
        ledgers = json.loads(args.korea_ledgers_export.read_text(encoding="utf-8"))
        report = scan(pages, artifacts, ledgers, as_of_utc=args.as_of_utc)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, "Korea Actions census: " + str(exc) + "\n")
    print(json.dumps(report, sort_keys=True, indent=2))
    return 1 if report["holds"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
