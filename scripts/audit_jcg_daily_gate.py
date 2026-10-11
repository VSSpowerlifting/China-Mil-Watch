"""Read-only JCG daily schedule gate + source-ledger observation.

This manual tool reads GitHub repository metadata ONLY. It does not enable a
GitHub variable, run a workflow, contact publisher sites, collect originals,
change a desk, perform human review or create a qualification receipt.

The current variable value cannot tell us its historical values. Therefore
skipped jobs cannot be retroactively classified as publisher failures, and
an absent scheduled run cannot be assumed to mean zero publications.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timezone

from core.shadow_schedule import scheduled_slot_date
from scripts.attest_vietnam_run_state import (
    AttestationHold, GithubRead, PREFIX, encoded_content,
    pinned_head, require, utc,
)

SCHEMA = "ipr-japan-jcg-schedule-gate-observation/1"
WORKFLOW = ".github/workflows/jcg_guarded_daily_shadow.yml"
VARIABLE = "JCG_SHADOW_DAILY_ENABLED"
BRANCH = "shadow/japan-jcg"
DESK = "japan_jcg"
LEDGER = re.compile(r"[0-9]{8}T[0-9]{6}(?:\.[0-9]{1,6})?\+0000-[1-9][0-9]*-[1-9][0-9]*\.json\Z")
RUN_ATTEMPT = re.compile(r"[1-9][0-9]*-[1-9][0-9]*\Z")
MAX_LEDGERS = 60
MAX_RUNS = 30
MAX_JOBS = 30
SCHEDULED_AT = "19:13"
TRUSTED_OBSERVER_REF = (
    "VSSpowerlifting/China-Mil-Watch/.github/workflows/"
    "jcg_gate_readonly_observation.yml@refs/heads/main"
)


def _valid_day(value, *, end):
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise AttestationHold("invalid source logical date") from None
    require(day <= end, "source ledger after operator as-of date")
    return day


def _gate(api):
    value = api.get(PREFIX + "/actions/variables/" + VARIABLE)
    require(isinstance(value, dict) and value.get("name") == VARIABLE
            and value.get("value") in ("true", "false"),
            "repository variable not independently confirmed")
    # Only the current observed value is known; no proof of prior settings.
    return value["value"] == "true"


def gate_from_trusted_actions_context(environ):
    """GitHub's evaluated vars context, not an editable caller-supplied gate.

    This alternative avoids granting token access to repository Variables.
    It can describe only the gate's value for this one manual Actions run.
    """
    require(environ.get("GITHUB_ACTIONS") == "true" and
            environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and
            environ.get("GITHUB_REPOSITORY") == "VSSpowerlifting/China-Mil-Watch" and
            environ.get("GITHUB_REF") == "refs/heads/main" and
            environ.get("GITHUB_WORKFLOW_REF") == TRUSTED_OBSERVER_REF and
            isinstance(environ.get("GITHUB_SHA"), str) and
            re.fullmatch(r"[0-9a-f]{40}", environ["GITHUB_SHA"]) is not None,
            "untrusted GitHub Actions workflow context")
    raw = environ.get("IPR_JCG_OBSERVED_GATE")
    require(raw in ("true", "false"),
            "repository gate unset or unavailable in Actions vars context")
    return raw == "true"


def _source_state(api, *, as_of):
    head = pinned_head(api, BRANCH)
    clock = encoded_content(api, "state/clock.json", head)
    require(clock.get("desk") == DESK and
            isinstance(clock.get("day_zero_run_id"), str) and
            RUN_ATTEMPT.fullmatch(clock["day_zero_run_id"]) and
            isinstance(clock.get("day_zero_utc"), str),
            "source-specific original Day 0 clock not proven")
    utc(clock["day_zero_utc"])
    entries = api.get(PREFIX + "/contents/state/ledger?ref=" + head)
    require(isinstance(entries, list) and 1 <= len(entries) <= MAX_LEDGERS,
            "source state ledger inventory unavailable or unbounded")
    names = [x.get("name") for x in entries if isinstance(x, dict)]
    require(len(names) == len(entries) and len(set(names)) == len(names) and
            all(isinstance(x, str) and LEDGER.fullmatch(x) for x in names),
            "source ledger directory has invalid or duplicate names")
    rows = []
    for filename in sorted(names):
        item = encoded_content(api, "state/ledger/" + filename, head)
        require(item.get("desk") == DESK and
                item.get("day_zero_utc") == clock["day_zero_utc"] and
                isinstance(item.get("run_id"), str) and
                RUN_ATTEMPT.fullmatch(item["run_id"]) and
                item.get("target_date_source") in ("explicit", "schedule-slot",
                                                   "manual-utc-date") and
                item.get("result") in ("ok", "ok_no_publications",
                                       "ok_all_filtered", "ok_all_duplicates") and
                item.get("health") == "ok",
                "source ledger has wrong identity, result or Day 0 clock")
        day = _valid_day(item.get("target_date"), end=as_of)
        anomalies = item.get("anomalies", []) or []
        source_anomalies = item.get("source_anomalies", []) or []
        require(isinstance(anomalies, list) and
                isinstance(source_anomalies, list),
                "malformed source anomaly fields")
        rows.append({
            "run_id": item["run_id"],
            "target_date": day.isoformat(),
            "target_date_source": item["target_date_source"],
            "anomaly_count": len(anomalies) + len(source_anomalies),
        })
    require(sum(x["run_id"] == clock["day_zero_run_id"] and
                x["target_date_source"] == "explicit" for x in rows) == 1,
            "Day 0 clock and unique explicit ledger not linked")
    return head, clock, rows


def _scheduled_runs(api, *, as_of):
    # If GitHub has more than one page, abort; absence or truncation must
    # never become a falsely exhaustive green report.
    path = (PREFIX + "/actions/workflows/jcg_guarded_daily_shadow.yml/runs?"
            "event=schedule&per_page=30&page=1")
    page = api.get(path)
    require(isinstance(page, dict) and
            type(page.get("total_count")) is int and
            isinstance(page.get("workflow_runs"), list),
            "scheduled workflow run index unreadable")
    records = page["workflow_runs"]
    require(0 <= page["total_count"] <= MAX_RUNS and
            len(records) == page["total_count"],
            "scheduled run inventory missing or exceeds bounded read")
    examined = []
    for row in records:
        require(isinstance(row, dict) and type(row.get("id")) is int and
                type(row.get("run_attempt")) is int and
                1 <= row["run_attempt"] <= 5 and
                row.get("event") == "schedule" and row.get("path") == WORKFLOW and
                row.get("status") in ("completed", "in_progress", "queued"),
                "unexpected JCG workflow run metadata")
        created = utc(row.get("run_started_at") or row.get("created_at"))
        logical = scheduled_slot_date(created, SCHEDULED_AT)
        if logical > as_of:
            continue
        require(logical >= date(2026, 10, 8),
                "JCG scheduled run predates its Day 0")
        for number in range(1, row["run_attempt"] + 1):
            runid = row["id"]
            jobs = api.get(PREFIX + "/actions/runs/{}/attempts/{}/jobs?per_page=30".format(
                runid, number))
            require(isinstance(jobs, dict) and
                    type(jobs.get("total_count")) is int and
                    isinstance(jobs.get("jobs"), list) and
                    jobs["total_count"] <= MAX_JOBS and
                    len(jobs["jobs"]) == jobs["total_count"],
                    "incomplete exact Actions job attempt inventory")
            shadows = [x for x in jobs["jobs"]
                       if isinstance(x, dict) and x.get("name") == "shadow"]
            require(len(shadows) == 1, "exact JCG shadow job is missing or ambiguous")
            j = shadows[0]
            require(j.get("conclusion") in ("skipped", "success", "failure",
                                            "cancelled", "timed_out", None) and
                    j.get("status") in ("completed", "in_progress", "queued"),
                    "unrecognized JCG shadow job result")
            outcome = j.get("conclusion") if j.get("status") == "completed" else "pending"
            require(outcome != None, "completed job lacks a conclusion")
            examined.append({"run_id": "{}-{}".format(runid, number),
                             "logical_date": logical.isoformat(),
                             "job_outcome": outcome})
    require(len({x["run_id"] for x in examined}) == len(examined),
            "duplicate scheduled attempt identity")
    return examined


def observe(api, *, as_of, actions_gate=None):
    """Run read-only trust checks; never derive past variable values."""
    try:
        cutoff = date.fromisoformat(as_of)
    except (TypeError, ValueError):
        raise AttestationHold("invalid as-of ISO date") from None
    require(date(2026, 10, 8) <= cutoff <= datetime.now(timezone.utc).date(),
            "as-of is before source Day 0 or in the future")
    require(actions_gate is None or type(actions_gate) is bool,
            "gate observation must be an exact boolean")
    enabled_now = _gate(api) if actions_gate is None else actions_gate
    head, clock, ledgers = _source_state(api, as_of=cutoff)
    attempts = _scheduled_runs(api, as_of=cutoff)
    rows = {x["run_id"]: x for x in ledgers
            if x["target_date_source"] == "schedule-slot"}
    duplicate = len(rows) != sum(x["target_date_source"] == "schedule-slot"
                                 for x in ledgers)
    require(not duplicate, "duplicate official collecting run in source ledgers")
    anomalies = sum(x["anomaly_count"] for x in ledgers)
    anomalies_by_attempt = []
    evidence_days = []
    for item in attempts:
        record = rows.get(item["run_id"])
        if item["job_outcome"] == "success":
            if record and record["target_date"] == item["logical_date"]:
                evidence_days.append(item["logical_date"])
                if record["anomaly_count"]:
                    anomalies_by_attempt.append(item["run_id"])
            else:
                anomalies_by_attempt.append(item["run_id"])
        elif record is not None:
            anomalies_by_attempt.append(item["run_id"])
    reported_attempts = {x["run_id"] for x in attempts}
    state_only = sorted(set(rows) - reported_attempts)
    if state_only:
        anomalies_by_attempt.extend(state_only)
    reasons = []
    if not enabled_now:
        reasons.append("current repository gate disabled; historic values unknown")
    if not attempts:
        reasons.append("no scheduled job attempts observed in bounded inventory")
    if anomalies_by_attempt:
        reasons.append("scheduled Actions job and pinned state ledger require reconciliation")
    if anomalies:
        reasons.append("source ledger anomalies remain subject to human review")
    if enabled_now and not evidence_days:
        reasons.append("enabled now, but no successful scheduled collection day is verified")
    require(pinned_head(api, BRANCH) == head,
            "JCG state branch moved during observation")
    return {
        "schema": SCHEMA,
        "state": "held_for_review" if reasons else "bounded_observations_only",
        "source": "Japan Coast Guard English official shadow only",
        "observation_as_of": cutoff.isoformat(),
        "current_gate_enabled": enabled_now,
        "current_gate_observed_via": (
            "github_rest_repository_variable" if actions_gate is None
            else "verified_actions_vars_context_at_manual_dispatch"
        ),
        "historic_gate_values_known": False,
        "state_branch": BRANCH,
        "pinned_state_head": head,
        "day_zero_run": clock["day_zero_run_id"],
        "day_zero_utc": clock["day_zero_utc"],
        "published_source_ledgers": len(ledgers),
        "scheduled_attempts_seen": len(attempts),
        "scheduled_attempts": attempts,
        "scheduled_success_days_correlated_with_ledger": sorted(set(evidence_days)),
        "source_anomalies_observed": anomalies,
        "mismatch_attempts_needing_review": sorted(set(anomalies_by_attempt)),
        "review_reasons": reasons,
        "complete_scheduled_attempt_history_proven": False,
        "daily_collection_authorized_by_this_tool": False,
        "human_day_7_review_approved": False,
        "source_licence_or_publication_authorized": False,
        "production_desk_promotion_authorized": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", required=True, help="UTC YYYY-MM-DD")
    p.add_argument("--approve-github-read", action="store_true",
                   help="manually authorize GitHub Actions variable, run/jobs and source ledger GETs")
    p.add_argument("--gate-from-actions-context", action="store_true",
                   help="only in the fixed, main-branch manual GitHub observer workflow")
    args = p.parse_args(argv)
    if not args.approve_github_read:
        p.error("no GitHub API reads without --approve-github-read")
    if not os.environ.get("GITHUB_TOKEN"):
        p.error("read-only GITHUB_TOKEN is required to inspect GitHub Actions and source state")
    try:
        context_gate = (
            gate_from_trusted_actions_context(os.environ)
            if args.gate_from_actions_context else None
        )
        report = observe(GithubRead(token=os.environ["GITHUB_TOKEN"]),
                         as_of=args.as_of, actions_gate=context_gate)
    except AttestationHold as exc:
        print(json.dumps({"schema": SCHEMA, "state": "blocked",
                          "reason": str(exc), "promotion_authorized": False}))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["state"] == "bounded_observations_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
