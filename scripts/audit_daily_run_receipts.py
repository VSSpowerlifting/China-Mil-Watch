#!/usr/bin/env python3
"""Classify *supplied* Daily GitHub Actions receipts, strictly offline.

This is a workflow-result interpretation aid, NOT an Actions API client,
authenticity proof, publisher-silence verdict, collector, or release gate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEMA = "ipr-daily-actions-receipts/1"
OUT_SCHEMA = "ipr-daily-operations-candidates/1"
WORKFLOW = "Daily PLA Watch Update"
STEP_NAMES = (
    "Run pipeline", "Validate rendered output",
    "Commit updated database and site output", "Deploy to GitHub Pages",
    "Record successful run", "Health gate",
)
STEP_RESULTS = frozenset(("success", "failure", "skipped", "cancelled", "unknown"))
CONCLUSIONS = frozenset(("success", "failure", "cancelled", "timed_out"))
EVENTS = frozenset(("schedule", "workflow_dispatch"))
ROOT_FIELDS = frozenset(("schema", "as_of_utc", "runs"))
RUN_FIELDS = frozenset(("run_id", "attempt", "workflow", "event", "status",
                        "conclusion", "created_at", "updated_at", "guard",
                        "steps", "analysis"))
GUARD_FIELDS = frozenset(("step_result", "should_run"))
ANALYSIS_FIELDS = frozenset((
    "new_articles_stored", "queue_total", "queue_new", "queue_backlog",
    "daily_analysis_cap", "backlog_after_cap", "deferred_new",
))
NY = ZoneInfo("America/New_York")


class ReceiptError(ValueError):
    """Refuse inconsistent evidence rather than guessing an operational result."""


def require(condition, message):
    if not condition:
        raise ReceiptError(message)


def parse_utc(raw):
    require(type(raw) is str, "UTC timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReceiptError("invalid timestamp") from exc
    require(parsed.tzinfo is not None and
            parsed.utcoffset() == timedelta(0),
            "only explicit UTC timestamps are accepted")
    return parsed.astimezone(timezone.utc)


def parse_analysis(data):
    if data is None:
        return None
    require(type(data) is dict and set(data) == ANALYSIS_FIELDS,
            "analysis log metrics incomplete or malformed")
    for key in ANALYSIS_FIELDS:
        require(type(data[key]) is int and data[key] >= 0,
                "analysis log metric must be a nonnegative integer: " + key)
    require(data["daily_analysis_cap"] >= 1,
            "analysis cap must be positive")
    require(data["queue_new"] + data["queue_backlog"] ==
            data["queue_total"],
            "queue components do not match the reported total")
    require(data["backlog_after_cap"] <= data["queue_total"] and
            data["deferred_new"] <= data["queue_new"],
            "impossible post-cap or deferred queue metric")
    # A pipeline can archive a record that is not eligible for the LLM queue.
    # Accordingly, stored articles need not equal queue_new.
    return dict(data)


def interpret(receipt):
    """Offline operator-supplied attempt analysis; all evidence flags false."""
    require(type(receipt) is dict and set(receipt) == ROOT_FIELDS and
            receipt.get("schema") == SCHEMA,
            "invalid Daily receipt envelope")
    as_of = parse_utc(receipt["as_of_utc"])
    raw = receipt["runs"]
    require(type(raw) is list and len(raw) <= 200,
            "run list missing or exceeds bounded offline window")
    seen = set()
    attempts = []
    for item in raw:
        require(type(item) is dict and set(item) == RUN_FIELDS,
                "missing/extra run receipt fields")
        run_id = item["run_id"]
        require(type(run_id) is int and run_id > 0 and
                type(item["attempt"]) is int and item["attempt"] >= 1,
                "invalid Actions run/attempt identity")
        identity = (run_id, item["attempt"])
        require(identity not in seen, "duplicate Actions run attempt")
        seen.add(identity)
        require(item["workflow"] == WORKFLOW and
                item["event"] in EVENTS and
                item["status"] == "completed" and
                item["conclusion"] in CONCLUSIONS,
                "unrecognized Daily workflow, trigger or conclusion")
        created = parse_utc(item["created_at"])
        updated = parse_utc(item["updated_at"])
        require(created <= updated <= as_of,
                "Actions event timestamps are impossible or future")
        guard = item["guard"]
        require(type(guard) is dict and set(guard) == GUARD_FIELDS and
                guard["step_result"] in STEP_RESULTS and
                (guard["should_run"] is None or
                 type(guard["should_run"]) is bool),
                "invalid scheduling guard evidence")
        steps = item["steps"]
        require(type(steps) is dict and set(steps) == set(STEP_NAMES) and
                all(status in STEP_RESULTS for status in steps.values()),
                "missing/malformed per-step execution evidence")
        if guard["should_run"] is not None:
            require(guard["step_result"] == "success",
                    "guard decision supplied without completed guard step")
        if guard["should_run"] is False:
            require(all(x != "success" for x in steps.values()),
                    "guard-only skip conflicts with an executed pipeline or deploy")
        analysis = parse_analysis(item["analysis"])
        if analysis is not None:
            require(steps["Run pipeline"] in ("success", "failure"),
                    "queue log metrics attached to non-executed pipeline")
        conclusion = item["conclusion"]
        if conclusion == "cancelled":
            # Preserve the distinction between a cancelled run without job
            # evidence, and a reviewed job whose pipeline step was skipped.
            # An operator-supplied skipped step is not authenticated proof
            # that no other job, dispatch or official publication existed.
            if (guard["should_run"] is True and
                all(steps[name] == "skipped" for name in STEP_NAMES)):
                status = "cancelled_pipeline_step_skipped_candidate"
            else:
                status = "cancelled_execution_extent_unknown"
        elif conclusion == "timed_out":
            status = "timed_out_execution_extent_unknown"
        elif conclusion == "failure":
            if steps["Run pipeline"] == "failure":
                status = "pipeline_failed_attempt"
            elif (steps["Deploy to GitHub Pages"] == "success" and
                  steps["Health gate"] == "failure"):
                status = "post_deploy_health_gate_failed"
            else:
                status = "failed_workflow_execution_requires_review"
        elif guard["should_run"] is False and all(
                x == "skipped" for x in steps.values()):
            status = "green_scheduling_guard_skip_candidate"
        elif (guard["should_run"] is True and
              all(x == "success" for x in steps.values())):
            status = "collection_validation_deploy_candidate"
        else:
            status = "green_workflow_work_not_established"
        attempts.append({
            "run_id": run_id, "attempt": item["attempt"],
            "actions_url": ("https://github.com/VSSpowerlifting/"
                            "China-Mil-Watch/actions/runs/%d" % run_id),
            "event": item["event"],
            "github_conclusion": conclusion,
            "created_utc_date": created.date().isoformat(),
            "created_new_york_date": created.astimezone(NY).date().isoformat(),
            "status": status,
            "guard_decision_supplied": guard["should_run"],
            "analysis_log_metrics_supplied": analysis,
            "collection_executed_authenticated": False,
            "deployment_authenticated": False,
            "log_metrics_authenticated": False,
        })
    attempts.sort(key=lambda r: (r["created_utc_date"], r["run_id"], r["attempt"]))
    days = {}
    for row in attempts:
        day = row["created_new_york_date"]
        days.setdefault(day, Counter())[row["status"]] += 1
    sequence = [
        row for row in attempts if
        row["status"] == "collection_validation_deploy_candidate" and
        row["analysis_log_metrics_supplied"] is not None
    ]
    backlog = [
        {"run_id": row["run_id"],
         "created_new_york_date": row["created_new_york_date"],
         "backlog_after_cap": row["analysis_log_metrics_supplied"]["backlog_after_cap"],
         "daily_analysis_cap": row["analysis_log_metrics_supplied"]["daily_analysis_cap"],
         "new_articles_stored": row["analysis_log_metrics_supplied"]["new_articles_stored"]}
        for row in sequence
    ]
    return {
        "schema": OUT_SCHEMA,
        "as_of_utc": as_of.isoformat().replace("+00:00", "Z"),
        "attempts": attempts,
        "provided_attempts": len(attempts),
        "created_ny_day_counts": {
            d: dict(sorted(v.items())) for d, v in sorted(days.items())
        },
        "supplied_pipeline_backlog_snapshots": backlog,
        "supplied_actions_export_authenticated": False,
        "complete_actions_history_established": False,
        "no_publications_inferred": False,
        "missing_run_dates_inferred": False,
        "archive_capture_verified": False,
        "analysis_queue_current_state_verified": False,
        "production_health_certified": False,
        "publication_authorized": False,
        "editor_delivery_authorized": False,
        "source_rights_cleared": False,
        "writes": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("receipt", type=Path,
                   help="operator-supplied JSON with Actions metadata and step/log excerpts")
    args = p.parse_args(argv)
    try:
        raw = json.loads(args.receipt.read_text(encoding="utf-8"))
        print(json.dumps(interpret(raw), sort_keys=True, indent=2))
    except (OSError, ValueError, TypeError, KeyError, ReceiptError) as exc:
        p.exit(1, "Daily workflow receipt refused: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
