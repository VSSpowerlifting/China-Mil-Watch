#!/usr/bin/env python3
"""Read-only GitHub Actions REST exporter for a bounded UTC day of Daily runs.

Exports *metadata* in the Phase-2 offline receipt format. It never downloads
logs, guesses the guard decision, verifies article coverage, or authenticates
the resulting file after export. No GitHub writes, model calls or collection.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import audit_daily_run_receipts as audit

REPO = "VSSpowerlifting/China-Mil-Watch"
BASE = "https://api.github.com/repos/" + REPO
WORKFLOW_PATH = ".github/workflows/daily_update.yml"
WORKFLOW_RUNS = "/actions/workflows/daily_update.yml/runs"
MAX_RUNS = 200
PAGE_SIZE = 100
MAX_PAGES = 2
TIMEOUT_SECONDS = 20
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "ipr-daily-operations-readonly/1",
}


class CaptureError(ValueError):
    """A partial or unrecognized Actions export is not a complete day receipt."""


def require(condition, reason):
    if not condition:
        raise CaptureError(reason)


def exact_utc_date(value):
    require(type(value) is str and
            bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)),
            "UTC day must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CaptureError("invalid UTC date") from exc


class RefuseRedirect(HTTPRedirectHandler):
    """Do not forward optional bearer credentials to a redirect target."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise CaptureError("GitHub Actions API redirected; refusing")


def transport(endpoint, query):
    """GET fixed-host GitHub API only; return JSON object, never follow API URLs."""
    require(type(endpoint) is str and endpoint.startswith("/actions/") and
            ".." not in endpoint and
            bool(re.fullmatch(r"/[a-zA-Z0-9_./-]+", endpoint)),
            "unsafe Actions API path")
    require(type(query) is dict and
            set(query).issubset({"per_page", "page", "created"}) and
            type(query.get("per_page")) is int and query["per_page"] == PAGE_SIZE,
            "unexpected Actions API query")
    headers = dict(HEADERS)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(BASE + endpoint + "?" + urlencode(query),
                      headers=headers, method="GET")
    try:
        opener = build_opener(RefuseRedirect())
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            require(response.geturl().startswith("https://api.github.com/"),
                    "unexpected Actions API redirect")
            require(response.status == 200, "unexpected Actions API status")
            raw = response.read(10_000_001)
            require(len(raw) <= 10_000_000, "Actions API response too large")
            return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        raise CaptureError("GitHub Actions API HTTP %d" % exc.code) from None
    except (URLError, TimeoutError, OSError, UnicodeError, ValueError) as exc:
        raise CaptureError("GitHub Actions API fetch failed or invalid JSON") from exc


def collect_paginated(fetch, endpoint, *, array_name, day_filter=None,
                      max_rows=MAX_RUNS, max_pages=MAX_PAGES):
    """Require exactly the advertised count; never accept truncated pagination."""
    require(type(max_rows) is int and 1 <= max_rows <= MAX_RUNS,
            "unbounded Actions import")
    out = []
    expected_total = None
    for page in range(1, max_pages + 1):
        query = {"per_page": PAGE_SIZE, "page": page}
        if day_filter is not None:
            query["created"] = day_filter
        doc = fetch(endpoint, query)
        require(type(doc) is dict and
                type(doc.get("total_count")) is int and
                type(doc.get(array_name)) is list,
                "Actions API list missing total_count or rows")
        total = doc["total_count"]
        require(0 <= total <= max_rows, "Actions API result limit exceeded")
        if expected_total is None:
            expected_total = total
        require(total == expected_total,
                "Actions API list changed during pagination; retry later")
        rows = doc[array_name]
        require(len(rows) <= PAGE_SIZE and
                (len(rows) == PAGE_SIZE or len(out) + len(rows) == total),
                "Actions API page incomplete or inconsistent")
        out.extend(rows)
        require(len(out) <= total, "Actions API contains more rows than total_count")
        if len(out) == total:
            return out
        require(len(rows) == PAGE_SIZE, "missing next page of Actions results")
    raise CaptureError("Actions API pagination exceeded safety bound")


def conclusion(value):
    if value in audit.STEP_RESULTS:
        return value
    return "unknown"


def convert_run(run, fetch, day):
    require(type(run) is dict and
            type(run.get("id")) is int and run["id"] > 0 and
            type(run.get("run_attempt")) is int and run["run_attempt"] > 0 and
            run.get("name") == audit.WORKFLOW and
            run.get("event") in audit.EVENTS and
            run.get("status") == "completed" and
            run.get("conclusion") in audit.CONCLUSIONS,
            "unexpected, unfinished or mismatched Daily workflow run")
    # The run-list API reports the current attempt, but a general jobs-list
    # response must not be silently attributed to that latest attempt. Until
    # this exporter uses the attempt-specific jobs endpoint and validates
    # its metadata, refuse reruns rather than invent attempt provenance.
    require(run["run_attempt"] == 1,
            "re-run attempt requires attempt-specific job provenance")
    identity = run["id"]
    created = audit.parse_utc(run.get("created_at"))
    require(created.date() == day, "Actions API run outside exact UTC day")
    updated = audit.parse_utc(run.get("updated_at"))
    require(created <= updated,
            "Actions API run timestamps out of order")
    jobs = collect_paginated(
        fetch, "/actions/runs/%d/jobs" % identity,
        array_name="jobs", max_rows=1, max_pages=1,
    )
    require(len(jobs) <= 1, "Daily workflow job cardinality changed; review manually")
    steps = {name: "unknown" for name in audit.STEP_NAMES}
    guard_result = "unknown"
    if jobs:
        job = jobs[0]
        require(type(job) is dict and
                job.get("run_id") == identity and
                type(job.get("id")) is int and
                job["id"] > 0 and
                job.get("name") == "update" and
                job.get("status") == "completed" and
                type(job.get("steps")) is list,
                "invalid or unexpected Daily job data")
        observed = set()
        for item in job["steps"]:
            require(type(item) is dict and type(item.get("name")) is str,
                    "malformed Actions step")
            name = item["name"]
            if name == "Scheduling guard" or name in steps:
                require(name not in observed, "duplicate guarded Daily step")
                observed.add(name)
                value = conclusion(item.get("conclusion"))
                if name == "Scheduling guard":
                    guard_result = value
                else:
                    steps[name] = value
    return {
        "run_id": identity,
        "attempt": run["run_attempt"],
        "workflow": audit.WORKFLOW,
        "event": run["event"],
        "status": "completed",
        "conclusion": run["conclusion"],
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "updated_at": updated.isoformat().replace("+00:00", "Z"),
        # Step metadata does NOT expose the guard's stdout decision.
        "guard": {"step_result": guard_result, "should_run": None},
        "steps": steps,
        # API job metadata does NOT contain stored/queued/backlog log totals.
        "analysis": None,
    }


def capture(day_utc, fetch=transport, *, as_of_utc=None):
    day = exact_utc_date(day_utc)
    require(day <= datetime.now(timezone.utc).date(),
            "future UTC day cannot be a Daily history window")
    rows = collect_paginated(
        fetch, WORKFLOW_RUNS,
        array_name="workflow_runs", day_filter=day.isoformat(),
    )
    seen = set()
    converted = []
    for run in rows:
        converted_run = convert_run(run, fetch, day)
        require(converted_run["run_id"] not in seen,
                "duplicated Daily run across Actions pages")
        seen.add(converted_run["run_id"])
        converted.append(converted_run)
    converted.sort(key=lambda r: (r["created_at"], r["run_id"]))
    as_of = as_of_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    doc = {"schema": audit.SCHEMA, "as_of_utc": as_of, "runs": converted}
    # Demand that the exact output obeys the downstream classifier contract.
    audit.interpret(doc)
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--created-utc-day", required=True,
                        help="UTC date, not nominal NY workflow/collection slot date")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(capture(args.created_utc_day), sort_keys=True, indent=2))
    except (CaptureError, audit.ReceiptError, TypeError, KeyError, ValueError) as exc:
        parser.exit(1, "Daily Actions API capture refused: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
