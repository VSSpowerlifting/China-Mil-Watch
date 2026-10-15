"""Read-only authentication of visible AFP Actions run attempts and job receipts.

Only currently visible GitHub workflow runs within the requested bounded window
can be verified. Deleted runs, missing artifacts, source copyrights, and human
editorial signoff remain separate gates. No publisher fetch or production writes.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = "VSSpowerlifting/China-Mil-Watch"
WORKFLOW_ID = 376813005
WORKFLOW_NAME = "Philippines AFP Shadow Collection"
WINDOW_START = date(2026, 10, 7)
WINDOW_END = date(2026, 10, 13)


class AttemptAuditError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise AttemptAuditError(message)


def utc_date(value):
    require(type(value) is str, "missing UTC API timestamp")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AttemptAuditError("invalid UTC API timestamp") from exc
    require(stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0),
            "API timestamp does not have UTC offset")
    return stamp.date()


def flatten(pages, key, maximum):
    if type(pages) is dict:
        pages = [pages]
    require(type(pages) is list and 1 <= len(pages) <= 100,
            "missing or excessive API pages")
    rows, count = [], None
    for page in pages:
        require(type(page) is dict and type(page.get("total_count")) is int and
                type(page.get(key)) is list, "invalid paginated API response")
        current = page["total_count"]
        require(0 <= current <= maximum and
                (count is None or current == count), "unstable API total count")
        count = current
        rows.extend(page[key])
    require(len(rows) == count, "partial GitHub API pagination")
    return rows


def read_runs(pages, cutoff):
    try:
        day = date.fromisoformat(cutoff)
    except ValueError as exc:
        raise AttemptAuditError("invalid review cutoff") from exc
    require(day.isoformat() == cutoff and day >= WINDOW_END,
            "review cutoff not canonical or before Day 7")
    runs = {}
    for run in flatten(pages, "workflow_runs", 150):
        require(type(run) is dict and type(run.get("id")) is int and
                run["id"] > 0 and run["id"] not in runs,
                "invalid or duplicate workflow run")
        require(run.get("workflow_id") == WORKFLOW_ID and
                run.get("name") == WORKFLOW_NAME,
                "wrong workflow in bounded export")
        require(WINDOW_START <= utc_date(run.get("created_at")) <= day,
                "workflow run outside query bounds")
        require(type(run.get("run_attempt")) is int and
                1 <= run["run_attempt"] <= 20, "unbounded attempt count")
        runs[run["id"]] = run
    return runs


def gh_json(path):
    # No shell invocation and no token in arguments or receipts.
    try:
        process = subprocess.run(["gh", "api", "-X", "GET", path],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 check=True, timeout=35)
        value = json.loads(process.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise AttemptAuditError("GitHub historical attempt API unavailable") from exc
    require(type(value) is dict, "GitHub attempt API returned no object")
    return value


def fetch_attempts(runs):
    """Retrieve every attempt and every job page for each visible run ID."""
    result = {}
    for run_id in sorted(runs):
        history = {}
        for n in range(1, runs[run_id]["run_attempt"] + 1):
            attempt = gh_json(
                "repos/%s/actions/runs/%d/attempts/%d" % (REPO, run_id, n))
            pages = []
            for page_num in range(1, 12):
                page = gh_json(
                    "repos/%s/actions/runs/%d/attempts/%d/jobs?per_page=100&page=%d"
                    % (REPO, run_id, n, page_num))
                pages.append(page)
                count = page.get("total_count")
                require(type(count) is int and 0 <= count <= 1000,
                        "invalid attempt job count")
                if page_num * 100 >= count:
                    break
            else:
                raise AttemptAuditError("incomplete job pagination")
            history[n] = {"run": attempt, "job_pages": pages}
        result[run_id] = history
    return result


def validate(runs, histories, assessment):
    require(type(assessment) is dict and
            assessment.get("protocol") == "ipr_ph_afp_actions_positive_match_v1" and
            assessment.get("github_workflow_id") == WORKFLOW_ID and
            assessment.get("all_seven_positive_runs_matched") is True and
            assessment.get("no_unmatched_scheduled_runs_visible_in_review_window") is True,
            "existing independent positive-run assessment not passed")
    slots = assessment.get("slots")
    require(type(slots) is list and len(slots) == 7, "expected seven pinned slots")
    expected, dates = {}, set()
    for slot in slots:
        require(type(slot) is dict and
                slot.get("status") == "actions_success_matches_ledger" and
                type(slot.get("run_id")) is str and
                re.fullmatch(r"[1-9][0-9]*-1", slot["run_id"]) and
                type(slot.get("date")) is str,
                "unmatched or rerun positive source slot")
        run_id = int(slot["run_id"].split("-")[0])
        require(run_id not in expected and slot["date"] not in dates,
                "duplicate run or date in positive slots")
        expected[run_id] = slot["date"]
        dates.add(slot["date"])
    require(dates == {(WINDOW_START + timedelta(days=i)).isoformat()
                      for i in range(7)}, "source slots not seven consecutive days")
    require(set(runs) == set(histories) and set(expected).issubset(runs),
            "visible runs have incomplete attempt coverage")

    checked_attempts = checked_jobs = 0
    for run_id, run in sorted(runs.items()):
        attempts = histories[run_id]
        require(type(attempts) is dict and
                set(attempts) == set(range(1, run["run_attempt"] + 1)),
                "missing or extra historical attempt")
        for n, item in sorted(attempts.items()):
            require(type(item) is dict and type(item.get("run")) is dict,
                    "missing historical attempt")
            original = item["run"]
            require(original.get("id") == run_id and
                    original.get("run_attempt") == n and
                    original.get("workflow_id") == WORKFLOW_ID and
                    original.get("head_sha") == run.get("head_sha") and
                    original.get("event") == run.get("event") and
                    original.get("head_branch") == run.get("head_branch") and
                    original.get("created_at") == run.get("created_at"),
                    "historical attempt contradicts GitHub parent run")
            jobs = flatten(item.get("job_pages"), "jobs", 1000)
            require(bool(jobs), "attempt has no attributable jobs")
            unique_jobs = set()
            for job in jobs:
                require(type(job) is dict and type(job.get("id")) is int and
                        job["id"] > 0 and job["id"] not in unique_jobs and
                        job.get("run_id") == run_id and
                        job.get("run_attempt") == n,
                        "duplicate or wrong-attempt job receipt")
                unique_jobs.add(job["id"])
            checked_attempts += 1
            checked_jobs += len(jobs)
            if run_id in expected:
                require(n == 1 and run["run_attempt"] == 1 and
                        run.get("event") == "schedule" and
                        run.get("head_branch") == "main" and
                        original.get("status") == "completed" and
                        original.get("conclusion") == "success" and
                        run.get("status") == "completed" and
                        run.get("conclusion") == "success" and
                        utc_date(original.get("created_at")).isoformat() ==
                        expected[run_id],
                        "positive day has rerun or failed/incorrect scheduled attempt")
                require(all(job.get("status") == "completed" and
                            job.get("conclusion") in ("success", "skipped")
                            for job in jobs) and
                        any(job.get("conclusion") == "success" for job in jobs),
                        "positive attempt contains unsuccessful/unverified jobs")
            elif run.get("event") == "schedule" and \
                    WINDOW_START <= utc_date(run.get("created_at")) <= WINDOW_END:
                raise AttemptAuditError(
                    "additional scheduled run attempt within the fixed window")
    return {
        "protocol": "ipr_ph_afp_bounded_attempt_jobs_v1",
        "scope": "visible_GitHub_run_export_only",
        "verified_visible_runs": len(runs),
        "verified_visible_run_attempts": checked_attempts,
        "verified_visible_attempt_jobs": checked_jobs,
        "seven_positive_first_attempt_jobs_verified": True,
        "visible_attempts_completely_reconciled": True,
        "deleted_or_missing_historical_runs_exhaustively_verified": False,
        "human_source_reviews_approved": False,
        "source_rights_approved": False,
        "production_admission_authorized": False,
        "weekly_model_email_or_publication_authorized": False,
        "writes": 0,
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--runs-export", required=True, type=Path)
    cli.add_argument("--actions-assessment", required=True, type=Path)
    cli.add_argument("--cutoff", required=True)
    args = cli.parse_args()
    try:
        runs = read_runs(json.loads(args.runs_export.read_text()), args.cutoff)
        assessment = json.loads(args.actions_assessment.read_text())
        print(json.dumps(validate(runs, fetch_attempts(runs), assessment),
                         indent=2, sort_keys=True))
    except (OSError, ValueError, TypeError) as exc:
        cli.exit(1, "AFP historical attempt audit: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
