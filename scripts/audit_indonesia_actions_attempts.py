"""Read-only Indonesia-vs-Korea Actions attempt inventory for a pinned shadow state.

Consumes complete GitHub Actions workflow-run pages and artifact-list responses.
Separate from ledgers: successful ledgers cannot prove failed/cancelled attempts
never happened. On source ambiguity, refuse to assert complete coverage.
No publisher requests, public renderer, licensing, state mutation or promotion.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path

from scripts import audit_indonesia_shadow_provenance as provenance
from core.shadow_schedule import scheduled_slot_date

ARTIFACT = re.compile(
    r"candidate-shadow-(indonesia|korea|unselected)-([1-9][0-9]*)-([1-9][0-9]*)\Z"
)


def require(value, message):
    if not value:
        raise provenance.ProvenanceError(message)


def scan(pages, artifact_responses, ledgers, as_of="2026-10-11"):
    """Return a count-only receipt. Unselected/failed/missing are explicit holds."""
    ending = provenance.day(as_of)
    start = date(2026, 10, 6)
    require(start <= ending, "audit date before actual Indonesia Day 0")
    actions = provenance.parse_actions_export(pages)
    require(type(artifact_responses) is dict and
            set(artifact_responses) == {str(run) for run in actions},
            "artifact export must cover every paginated workflow run")
    require(type(ledgers) is list and bool(ledgers), "no pinned ledgers")
    ledger_ids = {l["run_id"] for l in ledgers if
                  type(l) is dict and type(l.get("run_id")) is str and
                  provenance.RUN_ID.fullmatch(l["run_id"])}
    require(len(ledger_ids) == len(ledgers) - 1,
            "invalid or repeated original state ledgers")
    mapped_ledger_ids = set()
    scheduled_dates = {}
    counters = {
        "runs_considered": 0, "indonesia_attempts": 0, "korea_attempts": 0,
        "shared_unselected_attempts": 0, "indonesia_failures_or_cancellations": 0,
        "indonesia_success_without_pinned_ledger": 0,
        "indonesia_rerun_attempts": 0, "ambiguous_shared_failures": 0,
    }
    holds = []
    next_slot = provenance.utc((ending + timedelta(days=1)).isoformat() + "T17:17:00Z")
    for run_id, action in sorted(actions.items()):
        require(action.get("workflow_id") == provenance.WORKFLOW_ID and
                action.get("name") == provenance.WORKFLOW_NAME,
                "export contains a different workflow")
        created = provenance.utc(action.get("created_at"))
        if created.date() < start or created >= next_slot:
            continue  # Query includes following day's pre-slot delay window.
        counters["runs_considered"] += 1
        attempt = action.get("run_attempt")
        require(type(attempt) is int and attempt >= 1, "invalid run attempt")
        require(action.get("event") in ("workflow_dispatch", "schedule") and
                action.get("head_branch") == "main",
                "unexpected event/collector branch in source candidate workflow")
        response = artifact_responses[str(run_id)]
        require(type(response) is dict and type(response.get("total_count")) is int and
                type(response.get("artifacts")) is list and
                response["total_count"] == len(response["artifacts"]) and
                response["total_count"] <= 100,
                "incomplete or malformed run-artifact page")
        scopes = set()
        for artifact in response["artifacts"]:
            require(type(artifact) is dict and type(artifact.get("name")) is str,
                    "malformed artifact descriptor")
            m = ARTIFACT.fullmatch(artifact["name"])
            require(m is not None and int(m[2]) == run_id, "unknown/mismatched artifact")
            # A rerun can retain artifacts from earlier attempts. For provenance
            # we still cannot ignore a different-desk artifact from any attempt.
            require(int(m[3]) <= attempt, "artifact claims future run attempt")
            scopes.add(m[1])
        require(len(scopes) <= 1, "ambiguous multi-desk artifact for one run")
        scope = next(iter(scopes), "unselected")
        if scope == "unselected":
            counters["shared_unselected_attempts"] += 1
            if action.get("conclusion") != "success":
                counters["ambiguous_shared_failures"] += 1
            holds.append("shared_workflow_unattributed_run")
            continue
        if scope == "korea":
            counters["korea_attempts"] += 1
            continue
        counters["indonesia_attempts"] += 1
        key = str(run_id) + "-" + str(attempt)
        if attempt != 1:
            counters["indonesia_rerun_attempts"] += 1
            holds.append("indonesia_rerun_needs_manual_disposition")
        if action.get("status") != "completed" or action.get("conclusion") != "success":
            counters["indonesia_failures_or_cancellations"] += 1
            holds.append("indonesia_non_successful_workflow_attempt")
        if key not in ledger_ids:
            if action.get("conclusion") == "success":
                counters["indonesia_success_without_pinned_ledger"] += 1
            holds.append("indonesia_workflow_attempt_without_pinned_ledger")
        else:
            mapped_ledger_ids.add(key)
        if action.get("event") == "schedule":
            logical = scheduled_slot_date(created, "17:17")
            if logical <= ending and logical >= start:
                scheduled_dates.setdefault(logical.isoformat(), []).append(key)
        else:
            # Manual actions never prove scheduled-slot continuity.
            pass
    missing_ledger = sorted(ledger_ids - mapped_ledger_ids)
    if missing_ledger:
        holds.append("pinned_ledger_absent_from_workflow_attempt_inventory")
    required = [(start + timedelta(days=n)).isoformat()
                for n in range(1, (ending - start).days + 1)]
    missing_days = [d for d in required if len(scheduled_dates.get(d, [])) == 0]
    duplicate_days = [d for d in required if len(scheduled_dates.get(d, [])) > 1]
    if missing_days:
        holds.append("missing_scheduled_indonesia_attempt")
    if duplicate_days:
        holds.append("multiple_scheduled_indonesia_attempts")
    # Any identified Indonesia scheduled success that was absent in ledger is a
    # hold even when all preceding days were otherwise successful.
    holds = sorted(set(holds))
    return {
        "schema": "ipr-indonesia-shared-actions-attempt-inventory/1",
        "as_of": as_of, "state_branch": provenance.STATE_BRANCH,
        "read_scope": "all_shared_workflow_runs_in_queried_window_with_artifact_attribution",
        "run_listing_pagination_count_verified": True,
        "all_attempt_artifact_pages_count_verified": True,
        "artifact_attribution_caveat": "missing/unselected artifacts mean unknown desk",
        "counts": counters,
        "scheduled_indonesia_days_observed": sorted(scheduled_dates),
        "missing_scheduled_indonesia_days": missing_days,
        "duplicate_scheduled_indonesia_days": duplicate_days,
        "pinned_ledger_unmapped_count": len(missing_ledger),
        "holds": holds,
        "verdict": "HOLD" if holds else "CONSISTENT_THROUGH_AS_OF_NOT_DAY7_SIGNOFF",
        "independent_human_source_review_completed": False,
        "source_rights_approved": False,
        "day7_human_checkpoint_completed": False,
        "production_eligible": False,
        "publication_authorized": False,
        "mutations": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-repo", type=Path, required=True)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--runs-export", type=Path, required=True)
    p.add_argument("--artifacts-export", type=Path, required=True)
    p.add_argument("--as-of", default="2026-10-11")
    args = p.parse_args(argv)
    try:
        clock, ledgers, digest = provenance.pinned_state(args.state_repo, args.state_commit)
        pages = json.loads(args.runs_export.read_text())
        artifacts = json.loads(args.artifacts_export.read_text())
        actions = provenance.parse_actions_export(pages)
        provenance.assess(clock, ledgers, digest, actions)
        result = scan(pages, artifacts, ledgers, args.as_of)
        result["pinned_state_commit"] = args.state_commit
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result["holds"] else 0
    except (provenance.ProvenanceError, OSError, ValueError, KeyError) as exc:
        p.exit(2, "Indonesia shared Actions audit: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
