"""Authenticated GitHub metadata bridge to EXISTING Vietnam attempt reconciler.

Explicit manual GitHub REST GETs only, never a publisher request, state write,
collector restart, human checkpoint signoff or rights approval.

Reuses scripts.vietnam_ministry_attempt_reconciliation.reconcile unchanged.
Preserves initial failed bootstrap attempt and separate per-source Day-0 dates.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

from core.shadow_schedule import scheduled_slot_date
from scripts.attest_vietnam_run_state import (
    AttestationHold, GithubRead, PREFIX, pinned_head, encoded_content,
    require, utc,
)
from scripts.audit_shadow_workflow_bindings import validate as audit_bindings
from scripts.vietnam_ministry_attempt_reconciliation import (
    SCHEMA, SOURCES, WORKFLOW, MINISTRY_SHADOW_START,
    DAY_ZERO_RUN_ID, reconcile, AttemptEvidenceRefused,
)

OUTPUT_SCHEMA = "ipr-vietnam-github-reconciler-bridge/1"
PAGE_SIZE = 30
MAX_RUNS = 120
MAX_LEDGER_FILES = 60
LEDGER_NAME = re.compile(r"[0-9]{8}T[0-9]{6}\+0000-[1-9][0-9]*-[1-9][0-9]*\.json\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
TERMINAL = frozenset(("success", "failure", "cancelled", "timed_out",
                       "skipped", "action_required", "neutral"))


def window(through):
    try:
        day = date.fromisoformat(through)
    except (TypeError, ValueError):
        raise AttestationHold("invalid review through-date") from None
    require(MINISTRY_SHADOW_START <= day <= datetime.now(timezone.utc).date(),
            "review range outside approved dates")
    require((day - MINISTRY_SHADOW_START).days <= 45,
            "review window exceeds bounded historical audit")
    return day


def cron_time(cron):
    parts = cron.split(" ") if isinstance(cron, str) else []
    require(len(parts) == 5 and parts[2:] == ["*", "*", "*"] and
            all(x.isdigit() for x in parts[:2]),
            "unsupported scheduled source cron")
    minute, hour = map(int, parts[:2])
    require(0 <= minute < 60 and 0 <= hour < 24, "invalid UTC source cron")
    return "{:02d}:{:02d}".format(hour, minute)


def get_attempts(api, *, through, cron):
    """Bounded GitHub list+precise attempts, including every reported rerun."""
    base = PREFIX + "/actions/workflows/vietnam_ministry_shadow.yml/runs"
    selector = "?created={0}%2E%2E{1}&per_page={2}&page=".format(
        MINISTRY_SHADOW_START.isoformat(), through.isoformat(), PAGE_SIZE)
    listed = []
    total = None
    for page in range(1, 1 + (MAX_RUNS // PAGE_SIZE)):
        result = api.get(base + selector + str(page))
        require(isinstance(result, dict) and
                type(result.get("total_count")) is int and
                isinstance(result.get("workflow_runs"), list),
                "GitHub workflow run index malformed")
        if total is None:
            total = result["total_count"]
            require(0 < total <= MAX_RUNS, "empty or excessive bounded Actions window")
        require(result["total_count"] == total, "workflow index changed while paging")
        row = result["workflow_runs"]
        require(len(row) <= PAGE_SIZE, "unexpected Actions page size")
        listed.extend(row)
        if len(listed) >= total:
            break
        require(len(row) == PAGE_SIZE, "missing Actions page")
    require(total is not None and len(listed) == total,
            "incomplete bounded Actions window")
    runs = {}
    for item in listed:
        require(isinstance(item, dict), "invalid Actions run index member")
        ident, attempts = item.get("id"), item.get("run_attempt")
        require(type(ident) is int and ident > 1000000 and
                type(attempts) is int and 1 <= attempts <= 8 and
                ident not in runs and item.get("path") == WORKFLOW,
                "mismatched, duplicated or unbounded workflow run identity")
        runs[ident] = attempts
    attempts = []
    for run_id, max_attempt in sorted(runs.items()):
        for attempt in range(1, max_attempt + 1):
            item = api.get(PREFIX + "/actions/runs/{}/attempts/{}".format(
                run_id, attempt))
            require(isinstance(item, dict) and
                    item.get("id") == run_id and item.get("run_attempt") == attempt and
                    item.get("path") == WORKFLOW and
                    item.get("status") == "completed" and
                    item.get("conclusion") in TERMINAL and
                    item.get("event") in ("schedule", "workflow_dispatch") and
                    isinstance(item.get("head_sha"), str) and
                    SHA.fullmatch(item["head_sha"]), "unsound Actions attempt")
            started = utc(item.get("run_started_at"))
            # The one Day-0 bootstrap had THREE different source-specific
            # historical target days. Never invent one shared Actions date.
            target = None
            basis = None
            if item["event"] == "schedule":
                target = scheduled_slot_date(started, cron).isoformat()
                basis = "verified_schedule_slot"
            require(run_id != int(DAY_ZERO_RUN_ID.split("-")[0]) or
                    (attempt != 2 or (target is None and basis is None)),
                    "Day-0 bootstrap cannot be represented as a scheduled date")
            attempts.append({
                "run_id": run_id, "run_attempt": attempt,
                "event": item["event"], "conclusion": item["conclusion"],
                "run_url": "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/{}".format(run_id),
                "target_date": target, "target_date_basis": basis,
            })
    return attempts, {"listed_workflow_runs": len(runs),
                      "observed_actions_attempts": len(attempts),
                      "all_matching_index_pages_read": True}


def get_source_ledgers(api, *, source_slug, branch):
    """Read every pinned ledger; never fetch a state DB, capture or article."""
    head = pinned_head(api, branch)
    contents = api.get(PREFIX + "/contents/state/ledger?ref=" + head)
    require(isinstance(contents, list) and 1 <= len(contents) <= MAX_LEDGER_FILES,
            "empty or excessive source ledger list")
    names = [x.get("name") for x in contents if isinstance(x, dict)]
    require(len(names) == len(contents) and len(names) == len(set(names)) and
            all(isinstance(x, str) and LEDGER_NAME.fullmatch(x) for x in names),
            "malformed state ledger filename inventory")
    clock = encoded_content(api, "state/clock.json", head)
    require(clock.get("day_zero_run_id") == DAY_ZERO_RUN_ID and
            isinstance(clock.get("day_zero_utc"), str),
            "source clock cannot be tied to historic Day 0")
    rows, anomaly_total = [], 0
    for name in sorted(names):
        ledger = encoded_content(api, "state/ledger/" + name, head)
        require(ledger.get("source_slug") == source_slug and
                ledger.get("desk_id") == "vietnam" and
                ledger.get("day_zero_utc") == clock["day_zero_utc"],
                "source ledger not tied to its isolated state clock")
        fields = ("run_id", "result", "health", "target_date",
                  "target_date_source", "collector_commit", "finished_utc")
        require(all(key in ledger for key in fields),
                "source run ledger lacks required reconciliation metadata")
        row = {k: ledger[k] for k in fields}
        require(all(isinstance(v, str) for v in row.values()),
                "non-string published state evidence field")
        rows.append(row)
        anomalies = ledger.get("anomalies", [])
        source_anomalies = ledger.get("source_anomalies", [])
        require(isinstance(anomalies, list) and isinstance(source_anomalies, list),
                "unreadable source anomaly list")
        anomaly_total += len(anomalies) + len(source_anomalies)
    require(pinned_head(api, branch) == head,
            "source state branch changed while reading historical ledgers")
    return {"state_branch": branch, "state_commit": head, "runs": rows}, anomaly_total


def bridge(api, *, through, binding_report=None):
    """Produce metadata-only reconciler output with origin-truthful limitations."""
    cutoff = window(through)
    binding = binding_report if binding_report is not None else audit_bindings()
    require(binding.get("schema") == "ipr-shadow-source-workflow-bindings/1"
            and binding.get("declaration_only") is True and
            binding.get("all_runs_attested") is False,
            "invalid authoritative source workflow-binding audit")
    declared = binding.get("sources")
    require(isinstance(declared, list), "missing source bindings")
    actual_sources = {}
    for src, branch in SOURCES.items():
        matches = [x for x in declared if x.get("source_slug") == src]
        require(len(matches) == 1 and matches[0]["state_branch"] == branch and
                matches[0]["trigger"] == "scheduled" and
                matches[0]["workflow"] == WORKFLOW,
                "actual source binding differs from reconciler contract")
        actual_sources[src] = matches[0]
    cron = {x["cron"] for x in actual_sources.values()}
    require(len(cron) == 1, "three-source serial schedule no longer shares a cron")
    attempts, api_count = get_attempts(api, through=cutoff,
                                       cron=cron_time(next(iter(cron))))
    inventories, anomalies = {}, {}
    for slug, branch in sorted(SOURCES.items()):
        inventories[slug], anomalies[slug] = get_source_ledgers(
            api, source_slug=slug, branch=branch)
    expected_days = [(MINISTRY_SHADOW_START + timedelta(days=i)).isoformat()
                     for i in range((cutoff - MINISTRY_SHADOW_START).days + 1)]
    packet = {
        "schema": SCHEMA,
        "workflow": WORKFLOW,
        "review_window": {"from": MINISTRY_SHADOW_START.isoformat(),
                          "through": cutoff.isoformat()},
        "expected_target_dates": expected_days,
        "github_attempts": attempts,
        "source_ledgers": inventories,
    }
    try:
        report = reconcile(packet)
    except AttemptEvidenceRefused as exc:
        raise AttestationHold("existing Vietnam attempt reconciler refused: " + str(exc)) from None
    warnings = report["warnings"]
    review = bool(warnings or any(anomalies.values()))
    return {
        "schema": OUTPUT_SCHEMA,
        "source": "real_GitHub_REST_read_only_bounded_window",
        "review_window": packet["review_window"],
        "github": api_count,
        "state_head_shas": {slug: batch["state_commit"]
                            for slug, batch in sorted(inventories.items())},
        "source_anomaly_counts": anomalies,
        "reconciler": report,
        "status": "needs_review" if review else "reconciled_bounded_metadata_not_human_approved",
        "independent_git_history_fully_verified": False,
        "complete_failed_attempt_artifact_review": False,
        "owner_signed_checkpoint": False,
        "source_use_rights_approved": False,
        "production_or_publication_authorized": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--through", required=True, help="YYYY-MM-DD; start fixed at Oct 7")
    p.add_argument("--approve-github-read", action="store_true",
                   help="explicit bounded Actions/immutable state GitHub API observation")
    args = p.parse_args(argv)
    if not args.approve_github_read:
        p.error("no GitHub API calls without --approve-github-read")
    if not os.environ.get("GITHUB_TOKEN"):
        p.error("GITHUB_TOKEN required for bounded Actions history inventory")
    try:
        report = bridge(GithubRead(token=os.environ["GITHUB_TOKEN"]),
                        through=args.through)
    except AttestationHold as exc:
        print(json.dumps({"schema": OUTPUT_SCHEMA, "status": "blocked",
                          "reason": str(exc), "permission_for_production": False}))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["status"] == "reconciled_bounded_metadata_not_human_approved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
