"""Read-only diagnosis of Sunday's IPR editorial *workflow*, never proof of email.

All outputs contain only dates, workflow metadata and categorical verdicts.
Offline JSON is the default. --live explicitly calls the GitHub Actions GET
API; it never dispatches, emails, drafts, runs a model or changes repository data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
WORKFLOW = ".github/workflows/sunday_briefs_editorial_handoff.yml"
WORKFLOW_FILE = "sunday_briefs_editorial_handoff.yml"
SCHEDULE_UTC_HOUR = 19
SCHEDULE_UTC_MINUTE = 17
DISPATCH_GRACE = timedelta(minutes=90)
MAX_JSON = 2_000_000
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SCHEMA = "ipr-sunday-editorial-delivery-observer/1"


class DeliveryAuditError(ValueError):
    """Unusable, insufficient or malformed GitHub run metadata."""


def parse_utc(value):
    if not isinstance(value, str):
        raise DeliveryAuditError("GitHub event timestamp must be a string")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DeliveryAuditError("invalid GitHub event timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise DeliveryAuditError("workflow timestamps must include UTC offset")
    return stamp.astimezone(timezone.utc)


def sunday_for(now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise DeliveryAuditError("audit clock must include a timezone")
    today = now.astimezone(NY).date()
    return today - timedelta(days=(today.weekday() + 1) % 7)


def diagnose(payload, *, now, daily_marker=None):
    """Classify an explicit metadata snapshot without external side effects.

    Never report mail as delivered; GitHub's workflow success is not an
    independently confirmed Gmail Sent receipt.
    """
    if not isinstance(payload, dict):
        raise DeliveryAuditError("expected workflow metadata object")
    state = payload.get("workflow_state", "unknown")
    if state not in ("active", "disabled_manually", "disabled_inactivity", "disabled_fork", "deleted", "unknown"):
        raise DeliveryAuditError("unrecognized workflow state")
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list) or len(runs) > 100:
        raise DeliveryAuditError("expected at most 100 workflow runs")
    anchor = sunday_for(now)
    expected = datetime.combine(
        anchor, time(SCHEDULE_UTC_HOUR, SCHEDULE_UTC_MINUTE, tzinfo=timezone.utc)
    )
    week_end = anchor - timedelta(days=1)
    now_utc = now.astimezone(timezone.utc)
    observed = []
    manual = []
    for item in runs:
        if not isinstance(item, dict):
            raise DeliveryAuditError("invalid workflow run")
        if item.get("path") != WORKFLOW:
            continue
        event = item.get("event")
        if event not in ("schedule", "workflow_dispatch"):
            continue
        created = parse_utc(item.get("created_at"))
        if created.astimezone(NY).date() != anchor:
            continue
        status = item.get("status")
        conclusion = item.get("conclusion")
        if status not in ("queued", "in_progress", "waiting", "requested", "pending", "completed"):
            raise DeliveryAuditError("unexpected GitHub workflow run status")
        if conclusion not in (
            None, "success", "failure", "cancelled", "skipped", "timed_out",
            "action_required", "neutral", "stale",
        ):
            raise DeliveryAuditError("unexpected workflow conclusion")
        ident = item.get("id")
        if not isinstance(ident, int) or isinstance(ident, bool) or ident <= 0:
            raise DeliveryAuditError("workflow run requires a numeric ID")
        candidate = {
            "run_id": ident,
            "created_at_utc": created.isoformat().replace("+00:00", "Z"),
            "status": status,
            "conclusion": conclusion,
        }
        if event == "schedule":
            observed.append(candidate)
        else:
            manual.append(candidate)

    observed.sort(key=lambda x: (x["created_at_utc"], x["run_id"]))
    manual.sort(key=lambda x: (x["created_at_utc"], x["run_id"]))
    # Duplicate workflow entries in the fetched API page are malformed input,
    # not multiple independent delivery attempts.
    ids = [x["run_id"] for x in observed + manual]
    if len(ids) != len(set(ids)):
        raise DeliveryAuditError("duplicate workflow run IDs in snapshot")

    if state != "active" and state != "unknown":
        verdict = "WORKFLOW_DISABLED"
    elif len(observed) > 1:
        verdict = "MULTIPLE_SCHEDULED_RUNS_NEED_REVIEW"
    elif observed:
        current = observed[-1]
        if current["status"] != "completed":
            verdict = "WORKFLOW_IN_PROGRESS"
        elif current["conclusion"] == "success":
            verdict = "RUN_SUCCEEDED_EMAIL_UNCONFIRMED"
        elif current["conclusion"] == "skipped":
            verdict = "RUN_SKIPPED"
        else:
            verdict = "RUN_FAILED_OR_CANCELLED"
    elif now_utc < expected:
        verdict = "NOT_DUE"
    elif now_utc < expected + DISPATCH_GRACE:
        verdict = "WITHIN_SCHEDULER_GRACE"
    else:
        verdict = "MISSING_SCHEDULED_RUN"

    # A tracked marker is useful only for the presently local Sunday; it
    # cannot attest last week's collection from a later main commit.
    marker = (daily_marker or "").strip()
    if now.astimezone(NY).date() != anchor:
        marker_verdict = "HISTORICAL_MARKER_NOT_ATTESTED"
    elif not marker:
        marker_verdict = "MARKER_UNCHECKED"
    elif marker == anchor.isoformat():
        marker_verdict = "SAME_SUNDAY_MARKER_PRESENT"
    else:
        marker_verdict = "SUNDAY_MARKER_MISMATCH"

    return {
        "schema": SCHEMA,
        "week_ending": week_end.isoformat(),
        "expected_scheduled_utc": expected.isoformat().replace("+00:00", "Z"),
        "checked_at_utc": now_utc.isoformat().replace("+00:00", "Z"),
        "workflow_state": state,
        "scheduled_runs": observed,
        "manual_runs_same_sunday": [x["run_id"] for x in manual],
        "verdict": verdict,
        "collection_marker_verdict": marker_verdict,
        "editor_email": "NOT_VERIFIED_FROM_ACTIONS",
        "publication_approval": "NOT_ATTESTED",
        "automatic_retry_authorized": False,
    }


def _github_get(url, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ipr-sunday-readonly-observer",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read(MAX_JSON + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise DeliveryAuditError("GitHub Actions read-only metadata unavailable") from exc
    if len(raw) > MAX_JSON:
        raise DeliveryAuditError("GitHub Actions metadata unexpectedly large")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeliveryAuditError("unparseable GitHub Actions metadata") from exc


def fetch_live(repo, *, token=""):
    if not REPOSITORY_RE.fullmatch(repo):
        raise DeliveryAuditError("invalid repository owner/name")
    base = "https://api.github.com/repos/" + repo + "/actions/workflows/" + WORKFLOW_FILE
    state = _github_get(base, token)
    # Include dispatches so they cannot be mistaken for missing scheduled runs.\n    runs = _github_get(base + "/runs?per_page=100", token)
    if not isinstance(state, dict) or not isinstance(runs, dict):
        raise DeliveryAuditError("invalid GitHub Actions API result")
    if not isinstance(runs.get("workflow_runs"), list):
        raise DeliveryAuditError("GitHub workflow run list unavailable")
    return {
        "workflow_state": state.get("state", "unknown"),
        "workflow_runs": runs["workflow_runs"],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--runs-json", type=Path, help="offline GitHub metadata fixture")
    group.add_argument("--live", action="store_true", help="read official GitHub GET endpoints")
    p.add_argument("--repo", default="VSSpowerlifting/China-Mil-Watch",
                   help="exact repository owner/name, used for live GET")
    p.add_argument("--now-utc", help="offset-aware audit timestamp (default: current UTC)")
    p.add_argument("--marker-file", type=Path,
                   help="optional read-only current-main daily success marker")
    args = p.parse_args(argv)
    try:
        now = parse_utc(args.now_utc) if args.now_utc else datetime.now(timezone.utc)
        if args.live:
            snapshot = fetch_live(args.repo, token=os.environ.get("GITHUB_TOKEN", ""))
        else:
            path = args.runs_json
            if not path.is_file() or path.stat().st_size > MAX_JSON:
                raise DeliveryAuditError("missing or oversized offline metadata snapshot")
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        marker = None
        if args.marker_file:
            if not args.marker_file.is_file() or args.marker_file.stat().st_size > 50:
                raise DeliveryAuditError("invalid or absent daily collection marker")
            marker = args.marker_file.read_text(encoding="utf-8").strip()
        result = diagnose(snapshot, now=now, daily_marker=marker)
    except (DeliveryAuditError, OSError, json.JSONDecodeError) as exc:
        p.exit(2, "AUDIT UNKNOWN: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))
    # Nonzero only for actionable scheduler problems: never trigger a send.
    return 1 if result["verdict"] in (
        "WORKFLOW_DISABLED", "MULTIPLE_SCHEDULED_RUNS_NEED_REVIEW",
        "RUN_SKIPPED", "RUN_FAILED_OR_CANCELLED", "MISSING_SCHEDULED_RUN"
    ) else 0


if __name__ == "__main__":
    sys.exit(main())
