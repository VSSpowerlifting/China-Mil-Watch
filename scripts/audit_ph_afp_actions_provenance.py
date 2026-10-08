"""Offline AFP shadow Actions provenance cross-check (not source approval).

Match pinned AFP ledger identities and collector commit hashes to a complete
GitHub workflow-runs API export. The exported JSON is not cryptographically
authenticated here; rerun-attempt histories, human reviews, and rights remain
independent gates. Never fetch URLs, edit state, or activate any source.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

from scripts import audit_ph_afp_seven_day as audit

WORKFLOW_ID = 376813005
WORKFLOW_NAME = "Philippines AFP Shadow Collection"
REPO = "VSSpowerlifting/China-Mil-Watch"
RUN_ID = re.compile(r"([1-9][0-9]*)-([1-9][0-9]*)\Z")


class ActionsProvenanceError(ValueError):
    """Missing, contradictory or incomplete workflow-run export."""


def require(ok, why):
    if not ok:
        raise ActionsProvenanceError(why)


def parse_export(pages):
    """Accept the GitHub CLI --paginate --slurp array, or a single API page."""
    if type(pages) is dict:
        pages = [pages]
    require(type(pages) is list and bool(pages) and len(pages) <= 100,
            "expected bounded nonempty GitHub Actions pagination export")
    total = None
    rows = []
    ids = set()
    for page in pages:
        require(type(page) is dict and type(page.get("total_count")) is int and
                type(page.get("workflow_runs")) is list,
                "invalid GitHub Actions page")
        count = page["total_count"]
        require(0 <= count <= 10000 and (total is None or count == total),
                "inconsistent GitHub Actions total count")
        total = count
        for item in page["workflow_runs"]:
            require(type(item) is dict and type(item.get("id")) is int and
                    item["id"] > 0 and item["id"] not in ids,
                    "duplicate or malformed GitHub Actions run ID")
            ids.add(item["id"])
            rows.append(item)
    require(len(rows) == total,
            "incomplete workflow-run pagination (all pages required)")
    return {row["id"]: row for row in rows}


def check_action(ledger, action):
    """Validate a single preserved successful ledger's reported scheduled run."""
    issues = []
    def test(condition, label):
        if not condition:
            issues.append(label)
    m = RUN_ID.fullmatch(str(ledger["run_id"]))
    require(m is not None, "AFP ledger run ID cannot bind to Actions")
    action_id, attempt = map(int, m.groups())
    if action is None:
        return ["actions_run_missing_from_export"]
    test(action.get("id") == action_id, "run_identity_mismatch")
    test(action.get("run_attempt") == attempt, "run_attempt_mismatch")
    test(action.get("workflow_id") == WORKFLOW_ID and
         action.get("name") == WORKFLOW_NAME, "workflow_identity_mismatch")
    test(action.get("event") == "schedule", "not_a_scheduled_workflow_event")
    test(action.get("head_branch") == "main", "not_main_branch")
    test(action.get("status") == "completed" and
         action.get("conclusion") == "success", "actions_not_successful")
    test(action.get("head_sha") == ledger.get("collector_commit"),
         "collector_commit_mismatch")
    try:
        created = audit.utc(action.get("created_at"))
        target = audit.day(ledger["target_date"])
        # Never accept the wrong-day schedule as automatic evidence. A delayed
        # next-day run requires a separate event/cron investigation.
        test(created.date() == target, "created_outside_scheduled_utc_date")
    except (audit.AFPSevenDayError, TypeError, ValueError):
        issues.append("invalid_actions_created_at")
    return issues


def compare(scorecard, ledgers, actions):
    by_id = {ledger["run_id"]: ledger for ledger in ledgers}
    results = []
    matched = 0
    scheduled_ids = set()
    for slot in scorecard["slots"]:
        run_id = slot.get("run_id")
        if slot["status"] != "ledger_success_unverified_actions":
            result = "not_eligible_for_actions_match"
            issues = []
        else:
            m = RUN_ID.fullmatch(str(run_id))
            require(m is not None and run_id in by_id,
                    "scorecard run missing from pinned ledgers")
            action_id = int(m.group(1))
            scheduled_ids.add(action_id)
            issues = check_action(by_id[run_id], actions.get(action_id))
            result = "actions_success_matches_ledger" if not issues else \
                "actions_unverified"
            matched += not bool(issues)
        results.append({"date": slot["date"], "run_id": run_id,
                        "status": result, "issues": issues})
    visible_other = [
        {"id": x["id"], "event": x.get("event"),
         "created_at": x.get("created_at"), "conclusion": x.get("conclusion")}
        for x in actions.values()
        if x.get("workflow_id") == WORKFLOW_ID and
        x.get("event") == "schedule" and x["id"] not in scheduled_ids
    ]
    return {
        "protocol": "ipr_ph_afp_actions_positive_match_v1",
        "desk": "ph-afp",
        "state_commit": scorecard["immutable_state_commit"],
        "window_start": scorecard["window_start"],
        "window_end": scorecard["window_end"],
        "as_of_utc_date": scorecard["as_of_utc_date"],
        "github_workflow_id": WORKFLOW_ID,
        "github_workflow_name": WORKFLOW_NAME,
        "exported_workflow_runs": len(actions),
        "matched_scheduled_successes": matched,
        "all_seven_positive_runs_matched": matched == 7 and
            scorecard["all_seven_ledger_slots_supported"] is True,
        "slots": results,
        "other_scheduled_runs_in_export": visible_other,
        "export_query_scope_independently_authenticated": False,
        "historical_failed_and_rerun_attempts_exhaustively_audited": False,
        "github_metadata_signed_or_authenticated_by_script": False,
        "human_reviews_or_reuse_rights_approved": False,
        "production_eligible": False,
        "weekly_ai_writer_eligible": False,
        "writes": 0,
        "note": "Matching official run metadata adds independent positive evidence; " +
                "operator-supplied exports cannot prove missing failed attempts " +
                "or authenticate historical GitHub API responses.",
    }


def evaluate(state_repo, commit, as_of, pages, *, start_date=None):
    state = audit.FrozenState(state_repo, commit)
    scorecard = audit.assess(state, as_of=as_of, start=start_date)
    runs = audit.load_ledgers(state)
    return compare(scorecard, runs, parse_export(pages))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-repo", required=True, type=Path)
    parser.add_argument("--state-commit", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--actions-export", type=Path, required=True)
    args = parser.parse_args()
    try:
        pages = json.loads(args.actions_export.read_text(encoding="utf-8"))
        result = evaluate(args.state_repo, args.state_commit, args.as_of,
                          pages, start_date=args.start_date)
        print(json.dumps(result, indent=2))
    except (ActionsProvenanceError, audit.AFPSevenDayError, OSError,
            ValueError, TypeError, sqlite3.DatabaseError,
            UnicodeDecodeError) as exc:
        parser.exit(1, "AFP Actions provenance: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
