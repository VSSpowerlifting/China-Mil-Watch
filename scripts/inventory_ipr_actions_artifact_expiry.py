#!/usr/bin/env python3
"""Cross-desk GitHub Actions artifact/attempt expiry inventory (metadata only).

Operator-only authenticated, read-only GitHub API queries, no artifact ZIP
download, publisher contact, source-original access, Git writes or side effects.
Never treat retained API history as proof deleted historical runs did not exist.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

SCHEMA = "ipr-actions-artifact-retention-inventory/1"
REPO = "VSSpowerlifting/China-Mil-Watch"
SCOPED_WORKFLOWS = frozenset((
    ".github/workflows/indonesia_korea_shadow.yml",
    ".github/workflows/ph_afp_shadow.yml",
    ".github/workflows/ph_nsc_shadow.yml",
    ".github/workflows/vietnam_ministry_shadow.yml",
    ".github/workflows/vietnam_shadow.yml",
    ".github/workflows/singapore_shadow.yml",
    ".github/workflows/japan_shadow.yml",
    ".github/workflows/jcg_guarded_daily_shadow.yml",
    ".github/workflows/japan_jcg_shadow_manual.yml",
))
MAX_DAYS = 35
MAX_RUNS_PER_DAY = 500
MAX_ARTIFACTS_PER_RUN = 200
MAX_RESPONSE_BYTES = 6_000_000
NUMBER = re.compile(r"[1-9][0-9]{5,15}\Z")
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z")
ART_ATTEMPT = re.compile(r"-(?P<run>[1-9][0-9]{5,15})-(?P<attempt>[1-9][0-9]*)\Z")


class CensusHold(ValueError):
    """Emit controlled failure codes, never gh stderr/credentials/API bodies."""


def require(ok, code):
    if not ok:
        raise CensusHold(code)


def utc(value):
    require(type(value) is str and STAMP.fullmatch(value), "malformed_utc_timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CensusHold("malformed_utc_timestamp") from None


def day(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
            "malformed_calendar_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise CensusHold("malformed_calendar_date") from None
    require(parsed.isoformat() == value, "malformed_calendar_date")
    return parsed


def gh_get(route):
    require(type(route) is str and route.startswith("repos/" + REPO + "/actions/")
            and not any(x in route for x in ("#", "://", "..", "\n", "\r")),
            "github_route_invalid")
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", "--hostname", "github.com", route],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise CensusHold("github_api_unavailable") from None
    require(result.returncode == 0 and len(result.stdout) <= MAX_RESPONSE_BYTES,
            "github_api_failed_or_oversize")
    try:
        value = json.loads(result.stdout)
    except (UnicodeError, ValueError):
        raise CensusHold("github_response_not_json") from None
    require(type(value) is dict, "github_response_not_object")
    return value


def pages(fetch, route, collection, cap):
    """Validate bounded exhaustive pagination with stable total and unique IDs."""
    expected, items = None, []
    for page in range(1, (cap + 99) // 100 + 1):
        response = fetch(route + ("&" if "?" in route else "?") +
                         "per_page=100&page=" + str(page))
        require(type(response) is dict and type(response.get("total_count")) is int
                and type(response.get(collection)) is list, "github_pagination_malformed")
        total = response["total_count"]
        chunk = response[collection]
        require(0 <= total <= cap and len(chunk) <= 100 and
                (expected is None or total == expected),
                "github_pagination_changed_or_excessive")
        expected = total
        items.extend(chunk)
        require(len(items) <= total and all(type(x) is dict and
                type(x.get("id")) is int and x["id"] > 0 for x in items),
                "github_pagination_invalid_items")
        if len(items) == total:
            require(len({x["id"] for x in items}) == total,
                    "github_pagination_duplicate_id")
            return items
        require(len(chunk) == 100, "github_pagination_truncated")
    raise CensusHold("github_pagination_bound_exceeded")


def collect(fetch, first, last, as_of):
    begin, finish = day(first), day(last)
    now = utc(as_of)
    require(begin <= finish and (finish - begin).days < MAX_DAYS and
            finish <= now.date() and begin >= date(2026, 10, 1),
            "requested_window_invalid")
    observed = []
    seen_runs = set()
    current = begin
    while current <= finish:
        iso = current.isoformat()
        run_path = "repos/" + REPO + "/actions/runs?created=" + iso + ".." + iso
        all_runs = pages(fetch, run_path, "workflow_runs", MAX_RUNS_PER_DAY)
        for run in all_runs:
            run_id = run["id"]
            require(run_id not in seen_runs, "duplicate_run_across_dates")
            seen_runs.add(run_id)
            created = utc(run.get("created_at"))
            require(created.date() == current, "github_created_date_filter_mismatch")
            workflow = run.get("path")
            if workflow not in SCOPED_WORKFLOWS:
                continue
            event = run.get("event")
            if event not in ("schedule", "workflow_dispatch"):
                continue
            attempt = run.get("run_attempt")
            require(type(attempt) is int and 1 <= attempt <= 50,
                    "run_attempt_invalid")
            require(run.get("status") in ("completed", "queued", "in_progress",
                                         "waiting", "requested", "pending"),
                    "run_status_unknown")
            artifact_path = ("repos/" + REPO + "/actions/runs/" +
                             str(run_id) + "/artifacts")
            listing = pages(fetch, artifact_path, "artifacts",
                            MAX_ARTIFACTS_PER_RUN)
            artifacts = []
            labeled_attempts = set()
            for art in listing:
                expires = utc(art.get("expires_at"))
                require(type(art.get("name")) is str and
                        1 <= len(art["name"]) <= 256 and
                        type(art.get("size_in_bytes")) is int and
                        art["size_in_bytes"] >= 0 and
                        type(art.get("expired")) is bool,
                        "artifact_metadata_invalid")
                if type(art.get("workflow_run")) is dict:
                    require(art["workflow_run"].get("id") == run_id,
                            "artifact_wrong_run_scope")
                match = ART_ATTEMPT.search(art["name"])
                parsed = None
                if match:
                    require(int(match["run"]) == run_id,
                            "artifact_attempt_wrong_run")
                    parsed = int(match["attempt"])
                    require(1 <= parsed <= attempt,
                            "artifact_attempt_outside_run")
                    labeled_attempts.add(parsed)
                artifacts.append({
                    "id": art["id"], "name": art["name"], "bytes": art["size_in_bytes"],
                    "expires_utc": expires.isoformat().replace("+00:00", "Z"),
                    "expired": art["expired"], "name_attempt": parsed,
                    "hours_until_expiry": int((expires - now).total_seconds() // 3600),
                })
            artifacts.sort(key=lambda x: (x["expires_utc"], x["id"]))
            reasons = []
            if not artifacts:
                reasons.append("no_retained_artifacts")
            if any(x["expired"] or x["hours_until_expiry"] < 0 for x in artifacts):
                reasons.append("artifact_already_expired")
            if attempt > 1 and set(range(1, attempt)) - labeled_attempts:
                reasons.append("earlier_attempt_receipt_not_established")
            if any(x["name_attempt"] is None for x in artifacts):
                reasons.append("artifact_attempt_name_not_decodable")
            if run["status"] != "completed" or run.get("conclusion") != "success":
                reasons.append("run_unsuccessful_or_unfinished")
            observed.append({
                "run_id": run_id, "workflow": workflow, "event": event,
                "created_utc": created.isoformat().replace("+00:00", "Z"),
                "latest_run_attempt": attempt, "conclusion": run.get("conclusion"),
                "artifacts": artifacts, "holds": sorted(set(reasons)),
            })
        current += timedelta(days=1)
    observed.sort(key=lambda x: (x["created_utc"], x["run_id"]))
    artifact_rows = [
        {"run_id": x["run_id"], "workflow": x["workflow"], **art}
        for x in observed for art in x["artifacts"]
    ]
    artifact_rows.sort(key=lambda x: (x["expires_utc"], x["id"]))
    return {
        "schema": SCHEMA, "repo": REPO, "window": {"from": first, "through": last},
        "as_of_utc": as_of, "scoped_run_count": len(observed),
        "retained_artifact_count": len(artifact_rows),
        "retained_compressed_bytes": sum(x["bytes"] for x in artifact_rows),
        "earliest_retained_expiry_utc": (artifact_rows[0]["expires_utc"]
                                         if artifact_rows else None),
        "earliest_artifacts": artifact_rows[:20],
        "runs": observed,
        "actual_artifact_bytes_downloaded_or_hashed": False,
        "deleted_or_preexisting_expired_run_history_exhaustive": False,
        "failed_attempt_originals_independently_preserved": False,
        "source_retention_rights_granted": False,
        "production_cutover_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--through-date", required=True)
    parser.add_argument("--as-of-utc", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        report = collect(gh_get, args.from_date, args.through_date,
                         args.as_of_utc)
        # Explicit refusal to overwrite an existing custody receipt.
        with open(args.out, "x", encoding="utf-8") as handle:
            json.dump(report, handle, sort_keys=True, indent=2)
            handle.write("\n")
    except (CensusHold, OSError) as exc:
        code = str(exc) if isinstance(exc, CensusHold) else "output_unavailable"
        print(json.dumps({"schema": SCHEMA, "status": "HOLD",
                          "reason": code, "production_cutover_authorized": False},
                         sort_keys=True))
        return 2
    print(json.dumps({
        "schema": SCHEMA, "metadata_output_written": True,
        "scoped_run_count": report["scoped_run_count"],
        "retained_artifact_count": report["retained_artifact_count"],
        "earliest_retained_expiry_utc": report["earliest_retained_expiry_utc"],
        "raw_originals_preserved": False,
        "migration_authorized": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
