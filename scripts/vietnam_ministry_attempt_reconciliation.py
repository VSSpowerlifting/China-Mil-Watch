"""Cross-check supplied GitHub Actions attempt receipts and ministry shadow ledgers.

Pure offline metadata: does not query GitHub, fetch publisher content, touch
SQLite, write state or certify historical attempt completeness. Use the
independently verified Actions attempt history and per-source committed ledger
summaries as inputs; unsuccessful workflow attempts may never reach state.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

SCHEMA = "ipr-vn-ministry-attempt-reconciliation-input/1"
REPORT_SCHEMA = "ipr-vn-ministry-attempt-reconciliation/1"
WORKFLOW = ".github/workflows/vietnam_ministry_shadow.yml"
SOURCES = {
    "vn_mps_foreign_affairs_vi": "shadow/vietnam-mps-foreign-affairs",
    "vn_moit_energy_vi": "shadow/vietnam-moit-energy",
    "vn_moit_foundational_industry_vi": "shadow/vietnam-moit-foundational-industry",
}
TERMINAL_CONCLUSIONS = frozenset(("success", "failure", "cancelled", "timed_out", "skipped", "action_required", "neutral"))
SUCCESS_RESULTS = frozenset(("ok", "ok_no_publications", "ok_all_duplicates"))
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
RUN_IDENT = re.compile(r"([1-9][0-9]{6,14})-([1-9][0-9]*)\Z")
MAX_INPUT_BYTES = 2_000_000
# This specifically governed MPS/MOIT cadence was first activated Oct 7.
# Review ranges must not trim its Day 0, and planned dates cannot be omitted.
MINISTRY_SHADOW_START = date(2026, 10, 7)


class AttemptEvidenceRefused(ValueError):
    """The provided evidence itself is untrustworthy or structurally ambiguous."""


def require(condition, message):
    if not condition:
        raise AttemptEvidenceRefused(message)


def exact(value, fields, context):
    require(isinstance(value, dict) and set(value) == set(fields),
            context + " must have exact evidence fields")


def valid_day(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
            "expected canonical calendar date")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise AttemptEvidenceRefused("invalid calendar date") from exc
    require(d.isoformat() == value, "noncanonical calendar date")
    return d


def utc_instant(value):
    require(isinstance(value, str), "UTC instant is not a string")
    try:
        t = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AttemptEvidenceRefused("bad source ledger UTC instant") from exc
    require(t.tzinfo is not None and t.utcoffset() == timedelta(0),
            "source ledger timestamp must have explicit UTC timezone")
    return t


def strict_json(text):
    def unique(fields):
        obj = {}
        for key, value in fields:
            require(key not in obj, "duplicate evidence JSON key")
            obj[key] = value
        return obj
    return json.loads(text, object_pairs_hook=unique)


def reconcile(packet):
    exact(packet, ("schema", "workflow", "review_window", "expected_target_dates",
                   "github_attempts", "source_ledgers"), "packet")
    require(packet["schema"] == SCHEMA and packet["workflow"] == WORKFLOW,
            "wrong ministry workflow or evidence schema")
    exact(packet["review_window"], ("from", "through"), "review_window")
    start, end = valid_day(packet["review_window"]["from"]), valid_day(packet["review_window"]["through"])
    require(start == MINISTRY_SHADOW_START,
            "ministry review window must include the approved October 7 Day 0")
    require(start <= end and (end - start).days <= 45, "unbounded review date range")
    targets = packet["expected_target_dates"]
    require(isinstance(targets, list) and len(targets) <= 46, "invalid expected target dates")
    checked_targets = [valid_day(x) for x in targets]
    require(len(set(checked_targets)) == len(checked_targets)
            and all(start <= d <= end for d in checked_targets),
            "duplicate or out-of-scope planned target date")
    # Daily schedule is explicitly approved, so a shorter handwritten list
    # cannot make a missed slot disappear. A missing Actions receipt will
    # produce a warning; it cannot silently erase its expected calendar day.
    expected_calendar = [
        (start + timedelta(days=i)).isoformat()
        for i in range((end - start).days + 1)
    ]
    require(targets == expected_calendar,
            "expected target dates must enumerate every ministry shadow calendar day")

    attempts = packet["github_attempts"]
    require(isinstance(attempts, list) and len(attempts) <= 500,
            "unbounded GitHub attempt list")
    actions = {}
    for row in attempts:
        exact(row, ("run_id", "run_attempt", "event", "conclusion", "run_url",
                    "target_date", "target_date_basis"), "Actions attempt")
        run_id, attempt = row["run_id"], row["run_attempt"]
        require(type(run_id) is int and 1000000 <= run_id <= 999999999999999
                and type(attempt) is int and attempt >= 1,
                "invalid GitHub run or attempt number")
        key = "%d-%d" % (run_id, attempt)
        require(key not in actions, "duplicate GitHub run attempt")
        require(row["run_url"] == "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/%d" % run_id,
                "GitHub Actions receipt URL mismatches run identity")
        require(row["event"] in ("schedule", "workflow_dispatch")
                and row["conclusion"] in TERMINAL_CONCLUSIONS,
                "unrecognized completed workflow attempt")
        target, basis = row["target_date"], row["target_date_basis"]
        if target is None:
            require(basis is None, "unverified date cannot carry provenance")
        else:
            d = valid_day(target)
            require(start <= d <= end, "Actions target outside review window")
            expected_basis = ("verified_schedule_slot" if row["event"] == "schedule"
                              else "verified_dispatch_input")
            require(basis == expected_basis, "wrong logical target-date provenance")
        actions[key] = row

    ledgers = packet["source_ledgers"]
    require(isinstance(ledgers, dict) and set(ledgers) == set(SOURCES),
            "exactly three ministry source inventories required")
    by_source = {}
    warnings = []
    for slug in sorted(SOURCES):
        batch = ledgers[slug]
        exact(batch, ("state_branch", "state_commit", "runs"), "source state")
        require(batch["state_branch"] == SOURCES[slug]
                and isinstance(batch["state_commit"], str)
                and HEX40.fullmatch(batch["state_commit"]),
                "source state branch/commit not pinned")
        rows = batch["runs"]
        require(isinstance(rows, list) and len(rows) <= 500,
                "unbounded source ledger count")
        seen = set()
        outcomes = {}
        for row in rows:
            exact(row, ("run_id", "result", "health", "target_date",
                        "target_date_source", "collector_commit", "finished_utc"),
                  "source ledger")
            identifier = row["run_id"]
            require(isinstance(identifier, str), "non-string ledger run identity")
            matched = RUN_IDENT.fullmatch(identifier)
            require(matched is not None and identifier not in seen, "duplicate/bad source run identity")
            seen.add(identifier)
            require(row["result"] in SUCCESS_RESULTS and row["health"] == "ok",
                    "non-success ledger in a published success-only state branch")
            require(isinstance(row["collector_commit"], str)
                    and HEX40.fullmatch(row["collector_commit"]), "unbound collector identity")
            target = valid_day(row["target_date"])
            require(start <= target <= end, "source run target outside review window")
            require(row["target_date_source"] in ("schedule-slot", "explicit"),
                    "unverified source target-date origin")
            utc_instant(row["finished_utc"])
            outcomes[identifier] = row
            action = actions.get(identifier)
            if action is None:
                warnings.append({"kind": "source_ledger_missing_actions_receipt",
                                 "source_slug": slug, "run_id": identifier})
            elif action["conclusion"] != "success":
                warnings.append({"kind": "published_state_for_non_successful_workflow",
                                 "source_slug": slug, "run_id": identifier,
                                 "conclusion": action["conclusion"]})
            else:
                expected_source = "schedule-slot" if action["event"] == "schedule" else "explicit"
                require(row["target_date_source"] == expected_source,
                        "source logical-date basis disagrees with Actions event")
                if action["target_date"] is not None:
                    require(row["target_date"] == action["target_date"],
                            "source logical day disagrees with separately evidenced Actions target")
                else:
                    warnings.append({"kind": "actions_target_date_unverified",
                                     "source_slug": slug, "run_id": identifier})
        by_source[slug] = outcomes

    # Even if an Actions receipt has no independently established target,
    # the SAME serial ministry batch cannot claim conflicting dates,
    # date-origin rules, or collector code SHAs across source states.
    recorded_keys = set().union(*(set(records) for records in by_source.values()))
    for identifier in sorted(recorded_keys, key=lambda x: tuple(map(int, x.split("-")))):
        reported = {slug: by_source[slug][identifier] for slug in sorted(SOURCES)
                    if identifier in by_source[slug]}
        for field, kind in (("target_date", "source_batch_target_dates_disagree"),
                            ("target_date_source", "source_batch_date_origins_disagree"),
                            ("collector_commit", "source_batch_collector_commits_disagree")):
            values = {slug: row[field] for slug, row in reported.items()}
            if len(set(values.values())) > 1:
                warnings.append({"kind": kind, "run_id": identifier,
                                 "values_by_source": values})

    for key in sorted(actions, key=lambda x: tuple(map(int, x.split("-")))):
        action = actions[key]
        present = [slug for slug in sorted(SOURCES) if key in by_source[slug]]
        if action["event"] == "schedule" and action["run_attempt"] > 1:
            warnings.append({"kind": "scheduled_workflow_rerun_requires_review", "run_id": key})
        if action["conclusion"] == "success":
            missing = [slug for slug in sorted(SOURCES) if slug not in present]
            if missing:
                warnings.append({"kind": "successful_workflow_missing_source_ledger",
                                 "run_id": key, "missing_sources": missing})
        else:
            warnings.append({"kind": "non_successful_workflow_attempt",
                             "run_id": key, "conclusion": action["conclusion"],
                             "source_ledgers_found": present})
    for wanted in sorted(targets):
        covered = []
        for identifier, a in actions.items():
            if a["conclusion"] == "success" and a["target_date"] == wanted:
                if all(identifier in by_source[slug] for slug in SOURCES):
                    covered.append(identifier)
        if not covered:
            warnings.append({"kind": "expected_day_without_fully_evidenced_three_source_attempt",
                             "target_date": wanted})

    by_latest = {}
    for slug, index in by_source.items():
        by_latest[slug] = (max(index, key=lambda k: utc_instant(index[k]["finished_utc"]))
                           if index else None)
    if len(set(by_latest.values())) > 1:
        warnings.append({"kind": "source_latest_committed_attempts_diverge",
                         "latest_by_source": by_latest})
    return {
        "schema": REPORT_SCHEMA,
        "workflow": WORKFLOW,
        "review_window": packet["review_window"],
        "github_attempts_supplied": len(actions),
        "per_source_ledger_counts": {slug: len(by_source[slug]) for slug in sorted(SOURCES)},
        "latest_run_by_source": by_latest,
        "warnings": warnings,
        "requires_human_attempt_history_check": True,
        "github_attempt_inventory_independently_proven_exhaustive": False,
        "failed_attempt_artifacts_independently_verified": False,
        "source_state_git_ancestry_independently_verified": False,
        "all_scheduled_slots_proven_complete": False,
        "day_7_human_signoff_complete": False,
        "desk_qualified": False,
        "production_promotion_authorized": False,
        "source_rights_expanded": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", help="metadata-only JSON evidence manually assembled from GitHub and source ledgers")
    args = ap.parse_args(argv)
    p = Path(args.input)
    require(p.is_file() and not p.is_symlink() and p.stat().st_size <= MAX_INPUT_BYTES,
            "unsafe or oversized input file")
    obj = strict_json(p.read_text(encoding="utf-8"))
    print(json.dumps(reconcile(obj), sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
