#!/usr/bin/env python3
"""No-network, read-only audit of the *tracked* run-level LLM usage history.

This is a capacity EVIDENCE REPORT, not a budget increase, invoice, model
throughput proof, or inference about days absent from the history.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.usage import SCHEMA_VERSION, TASKS, USAGE_LOG_PATH

SCHEMA = "ipr-stored-llm-capacity-evidence/1"
COUNTERS = ("calls", "succeeded_calls", "failed_calls",
            "input_tokens", "output_tokens",
            "cache_creation_input_tokens", "cache_read_input_tokens")
MAX_RUNS = 365
COST_TOLERANCE = Decimal("0.000010")


class CapacityEvidenceError(ValueError):
    """Reject unsupported input instead of reporting plausible false numbers."""


def require(ok, description):
    if not ok:
        raise CapacityEvidenceError(description)


def day(value):
    require(type(value) is str and len(value) == 10,
            "usage run_date must be YYYY-MM-DD")
    try:
        when = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise CapacityEvidenceError("invalid usage run_date") from exc
    require(when.isoformat() == value, "noncanonical usage run date")
    return when


def nonnegative_number(value, name):
    require(type(value) is int and value >= 0, "invalid nonnegative count: " + name)
    return value


def money(value, name):
    require(type(value) in (int, float) and value >= 0,
            "invalid nonnegative estimated cost: " + name)
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise CapacityEvidenceError("invalid estimated cost: " + name) from exc
    require(amount.is_finite(), "nonfinite estimated cost: " + name)
    return amount


def validate_record(obj):
    require(type(obj) is dict and obj.get("schema_version") == SCHEMA_VERSION,
            "unsupported LLM usage record schema")
    dt = day(obj.get("run_date"))
    require(type(obj.get("run_status")) is str and obj["run_status"].strip(),
            "missing run status")
    require(type(obj.get("recorded_at")) is str,
            "missing usage record timestamp")
    try:
        recorded = datetime.fromisoformat(obj["recorded_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise CapacityEvidenceError("invalid usage record timestamp") from exc
    require(recorded.tzinfo is not None and recorded.utcoffset() is not None,
            "usage record timestamp must include time zone")
    for key in ("articles_queued", "articles_fully_analyzed", *COUNTERS):
        nonnegative_number(obj.get(key), key)
    require(obj["articles_fully_analyzed"] <= obj["articles_queued"],
            "fully analyzed exceeds recorded queue size")
    require(obj["calls"] == obj["succeeded_calls"] + obj["failed_calls"],
            "usage top-level successful/failed calls do not reconcile")
    tasks = obj.get("tasks")
    require(type(tasks) is list, "missing task-level usage receipts")
    unique = set()
    tally = Counter()
    task_cost = Decimal("0")
    has_unpriced = False
    require(type(obj.get("unpriced_models")) is list
            and all(type(m) is str and bool(m) for m in obj["unpriced_models"]),
            "invalid unpriced model declaration")
    unpriced = set(obj["unpriced_models"])
    require(len(unpriced) == len(obj["unpriced_models"]),
            "duplicated unpriced model declaration")
    for task in tasks:
        require(type(task) is dict, "invalid usage task receipt")
        name, model = task.get("task"), task.get("model")
        require(name in TASKS and type(model) is str and bool(model),
                "unsupported task label or missing model")
        require((name, model) not in unique, "duplicated task-model usage receipt")
        unique.add((name, model))
        for key in COUNTERS:
            tally[key] += nonnegative_number(task.get(key), key)
        require(task["calls"] == task["succeeded_calls"] + task["failed_calls"],
                "task call success/failure counts do not reconcile")
        c = task.get("estimated_cost_usd")
        if c is None:
            has_unpriced = True
            require(model in unpriced, "unpriced task/model missing from declaration")
        else:
            task_cost += money(c, "task estimated_cost_usd")
            require(model not in unpriced,
                    "priced model wrongly declared unpriced")
    require(all(tally[k] == obj[k] for k in COUNTERS),
            "task counters and run counters do not reconcile")
    require(has_unpriced == bool(unpriced),
            "unpriced model declarations and task receipts disagree")
    total_cost = money(obj.get("estimated_cost_usd"), "estimated_cost_usd")
    require(abs(task_cost - total_cost) <= COST_TOLERANCE,
            "estimated task costs and run cost do not reconcile")
    per = obj.get("estimated_cost_per_analyzed_article_usd")
    if obj["articles_fully_analyzed"]:
        require(per is not None and
                abs(money(per, "cost per analyzed article") -
                    total_cost / obj["articles_fully_analyzed"]) <= COST_TOLERANCE,
                "run estimated cost per fully analyzed article is inconsistent")
    else:
        require(per is None, "cost per article must be null for zero analyzed")
    return dt


def analyze_lines(raw):
    lines = raw.splitlines()
    require(0 < len(lines) <= MAX_RUNS, "LLM history empty or outside bounded range")
    dates = {}
    cost = Decimal("0")
    sums = Counter()
    tasks = {}
    calendar = []
    status = Counter()
    any_unpriced = False
    for line in lines:
        require(bool(line.strip()), "empty line in stored usage history")
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CapacityEvidenceError("malformed stored usage JSON") from exc
        dt = validate_record(obj)
        require(dt not in dates, "duplicate date in stored usage history")
        dates[dt] = obj
        cost += money(obj["estimated_cost_usd"], "estimated_cost_usd")
        any_unpriced |= bool(obj["unpriced_models"])
        status[obj["run_status"]] += 1
        for key in (*COUNTERS, "articles_queued", "articles_fully_analyzed"):
            sums[key] += obj[key]
        for item in obj["tasks"]:
            key = (item["task"], item["model"])
            result = tasks.setdefault(key, Counter())
            for field in COUNTERS:
                result[field] += item[field]
            if item["estimated_cost_usd"] is not None:
                result["estimated_cost_micro_usd"] += int(
                    (money(item["estimated_cost_usd"], "task cost") *
                     Decimal("1000000")).to_integral_value())
    sorted_days = sorted(dates)
    current = sorted_days[0]
    while current <= sorted_days[-1]:
        if current not in dates:
            calendar.append(current.isoformat())
        current += timedelta(days=1)
    daily = []
    for dt in sorted_days:
        record = dates[dt]
        daily.append({
            "run_date": dt.isoformat(),
            "run_status_reported": record["run_status"],
            "articles_queued": record["articles_queued"],
            "articles_fully_analyzed": record["articles_fully_analyzed"],
            "calls": record["calls"],
            "failed_calls": record["failed_calls"],
            "estimated_cost_usd": record["estimated_cost_usd"],
            "unpriced_models": record["unpriced_models"],
        })
    total_fully = sums["articles_fully_analyzed"]
    return {
        "schema": SCHEMA,
        "first_record_date": sorted_days[0].isoformat(),
        "last_record_date": sorted_days[-1].isoformat(),
        "recorded_run_dates": len(dates),
        "calendar_dates_with_no_usage_record": calendar,
        "no_record_does_not_prove_no_execution": True,
        "reported_run_statuses": dict(sorted(status.items())),
        "totals": {k: sums[k] for k in (
            "articles_queued", "articles_fully_analyzed", *COUNTERS)},
        "estimated_cost_usd": float(cost),
        "estimated_cost_per_fully_analyzed_usd": (
            float(cost / total_fully) if total_fully else None),
        "task_model_rollup": [
            {"task": task, "model": model,
             **{field: counts[field] for field in COUNTERS},
             "estimated_cost_usd": counts["estimated_cost_micro_usd"] / 1000000}
            for (task, model), counts in sorted(tasks.items())
        ],
        "daily": daily,
        "any_unpriced_models": any_unpriced,
        "cost_is_pinned_price_estimate_not_invoice": True,
        "fully_analyzed_is_not_all_queued_successes": True,
        "screening_rejections_not_counted_as_full_analysis": True,
        "run_authenticity_beyond_pinned_input_proven": False,
        "matching_actions_jobs_authenticated": False,
        "analysis_cap_change_authorized": False,
        "model_spend_authorized": False,
        "publication_authorized": False,
        "model_calls": 0,
        "writes": 0,
    }


def snapshot(path=USAGE_LOG_PATH):
    source = Path(path)
    require(source.is_file(), "tracked usage-history input missing")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    output = analyze_lines(source.read_text(encoding="utf-8"))
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    require(before == after, "usage history changed during read-only audit")
    output["input_file_sha256"] = before
    output["input_file_identity_not_signed"] = True
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usage-jsonl", type=Path, default=Path(USAGE_LOG_PATH))
    args = parser.parse_args(argv)
    try:
        print(json.dumps(snapshot(args.usage_jsonl), sort_keys=True, indent=2))
    except (CapacityEvidenceError, OSError, ValueError, TypeError) as exc:
        parser.exit(1, "Read-only model capacity audit refused: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
