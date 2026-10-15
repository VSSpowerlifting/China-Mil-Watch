"""Prospective Korean 7-slot ledger AND GitHub Actions candidate, read-only.

Unlike the original October 7–13 Day-7 review, a clean later window may be
assessed independently without backdating the October 12 failed slot.
Inputs must be supplied by the existing authenticated full Actions census.
This pure evaluator alone does NOT authenticate exports or approve production.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from core.shadow_schedule import scheduled_slot_date
from scripts import audit_korea_actions_attempts as census
from scripts import audit_indonesia_shadow_provenance as provenance
from scripts.watch_korea_shadow_slots import matured_slot

SCHEMA = "ipr-korea-authenticated-prospective-seven-slot-candidate/1"
DAY_ZERO = date(2026, 10, 6)
HISTORICAL_GAP = "2026-10-12"
RUN = re.compile(r"[1-9][0-9]*-1\Z")
ALLOWED = frozenset(census.RESULTS)
SCHEDULE = "17:47"


def _require(condition, reason):
    if not condition:
        raise provenance.ProvenanceError(reason)


def evaluate(pages, artifacts, ledgers, *, as_of_utc):
    """Exact seven latest mature logical dates, no model, publication or writes.

    Invalid/failed attempts remain observations but cannot count as a success.
    Never treat an unclassified shared-workflow run as a Korea success.
    """
    now = provenance.utc(as_of_utc)
    end = matured_slot(now)
    starts = [end - timedelta(days=i) for i in range(6, -1, -1)]
    actions = provenance.parse_actions_export(pages)
    _require(type(artifacts) is dict
             and set(artifacts) == {str(ident) for ident in actions},
             "incomplete authenticated artifact roster")
    _require(type(ledgers) is list and len(ledgers) <= 70,
             "missing or excessive Korea original ledgers")
    source_ledger = {}
    for l in ledgers:
        _require(type(l) is dict and l.get("desk") == "korea"
                 and type(l.get("run_id")) is str
                 and l["run_id"] not in source_ledger,
                 "malformed, foreign or duplicate original ledger")
        source_ledger[l["run_id"]] = l
    _require(source_ledger.get(census.LOCAL, {}).get("health") == "ok"
             and source_ledger[census.LOCAL].get("target_date") == DAY_ZERO.isoformat(),
             "original Korea Day 0 missing or unhealthy")

    observed = {}
    ambiguous_scheduled_dates = set()
    for run_id, action in actions.items():
        _require(type(run_id) is int and run_id > 0
                 and type(action) is dict
                 and action.get("workflow_id") == provenance.WORKFLOW_ID
                 and action.get("name") == provenance.WORKFLOW_NAME,
                 "foreign or malformed shared workflow run")
        created = provenance.utc(action.get("created_at"))
        if created > now or created.date() < DAY_ZERO:
            continue
        page = artifacts[str(run_id)]
        _require(type(page) is dict and type(page.get("artifacts")) is list
                 and type(page.get("total_count")) is int
                 and len(page["artifacts"]) == page["total_count"]
                 and len(page["artifacts"]) <= 100,
                 "incomplete per-run artifact evidence")
        names = [row.get("name") for row in page["artifacts"]
                 if type(row) is dict]
        _require(len(names) == len(page["artifacts"])
                 and all(type(name) is str for name in names),
                 "malformed artifact name")
        matching = [n for n in names
                    if n.startswith("candidate-shadow-korea-")]
        other = [n for n in names
                 if n.startswith("candidate-shadow-indonesia-")]
        if not matching:
            if not other and action.get("event") == "schedule":
                # An artifactless/unselected shared scheduled attempt may
                # have been Korea; assigning only one desk would invent data.
                # Conservatively hold BOTH possible nominal desk dates.
                for cron in ("17:17", SCHEDULE):
                    ambiguous_scheduled_dates.add(
                        scheduled_slot_date(created, cron).isoformat())
            continue
        if action.get("event") != "schedule":
            # A manual Korea execution never substitutes for a real schedule.
            continue
        logical = scheduled_slot_date(created, SCHEDULE)
        attempt = action.get("run_attempt")
        key = "{}-{}".format(run_id, attempt)
        accepted_name = "candidate-shadow-korea-{}-1".format(run_id)
        valid = (
            type(attempt) is int and attempt == 1
            and len(names) == 1 and names == [accepted_name]
            and action.get("status") == "completed"
            and action.get("conclusion") == "success"
            and action.get("head_branch") == "main"
            and RUN.fullmatch(key) is not None
        )
        record = source_ledger.get(key)
        valid = (valid and type(record) is dict
                 and record.get("target_date_source") == "schedule-slot"
                 and record.get("target_date") == logical.isoformat()
                 and record.get("health") == "ok"
                 and record.get("result") in ALLOWED)
        observed.setdefault(logical.isoformat(), []).append(bool(valid))

    # A whole historical failure can be retained while a new 7-day window
    # becomes a ledger-plus-Actions candidate. Neither grants rights/use.
    days = [d.isoformat() for d in starts]
    failures = [d for d in days
                if observed.get(d) != [True]
                or d in ambiguous_scheduled_dates]
    # Do not assign a 7-slot verdict before the 7th genuine post-Day-0 slot.
    enough_history = starts[0] > DAY_ZERO
    streak = 0
    for d in reversed(days):
        if observed.get(d) != [True] or d in ambiguous_scheduled_dates:
            break
        streak += 1
    passed = enough_history and not failures
    return {
        "schema": SCHEMA,
        "evaluated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "latest_mature_date": end.isoformat(),
        "prospective_dates": days,
        "verified_first_attempt_schedule_and_ledger_dates":
            [d for d in days if observed.get(d) == [True]],
        "unqualified_dates": failures,
        "ambiguous_shared_scheduled_dates": sorted(
            set(days) & ambiguous_scheduled_dates),
        "prospective_consecutive_successful_days": streak,
        "seven_day_actions_and_ledger_candidate": passed,
        "historical_october_12_gap_automatically_repaired": False,
        "historical_october_12_success_claimed": False,
        "historical_october_12_remains_separate_review": True,
        "source": "caller_supplied_full_actions_runs_and_original_ledgers",
        "caller_evidence_authenticated_by_this_function": False,
        "all_historical_attempts_approved": False,
        "capture_bytes_reverified_by_this_function": False,
        "publisher_completeness_proved": False,
        "independent_korean_review_completed": False,
        "source_rights_approved": False,
        "model_or_email_authorized": False,
        "production_or_publication_authorized": False,
        "changes_source_state": False,
    }
