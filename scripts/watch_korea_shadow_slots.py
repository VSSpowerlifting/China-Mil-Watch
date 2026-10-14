"""Read-only Korea collection-slot watchdog: ledger evidence, NOT source approval.

Inspect metadata from an exact Git-pinned sparse shadow checkout. A successful
Korea target-date ledger shows an observed collection attempt; it cannot prove
publisher completeness, the Actions attempt census, correct HWPX semantics or
attachment rights. Recovery of source coverage must never be mistaken for a
successful scheduled collection.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.shadow_schedule import SOURCE_EXPLICIT, SOURCE_SCHEDULE
from scripts.run_korea_authenticated_actions_census import pinned_ledger_checkout

SCHEMA = "ipr-korea-readonly-logical-slot-watch/1"
STATE_BRANCH = "shadow/korea-policy-briefing"
FIRST_SLOT = date(2026, 10, 7)
EXPECTED_CLOCK_DAY = date(2026, 10, 6)
CRON_HOUR, CRON_MINUTE = 17, 47
GRACE_HOURS = 6
MAX_DAYS = 30
SUCCESS = frozenset(("ok", "ok_all_duplicates", "ok_no_publications", "ok_all_filtered"))
RUN_ID = re.compile(r"[1-9][0-9]*-1\Z")
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


class KoreaWatchHold(ValueError):
    pass


def require(ok, why):
    if not ok:
        raise KoreaWatchHold(why)


def utc(value):
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise KoreaWatchHold("invalid UTC observation") from exc
    else:
        raise KoreaWatchHold("invalid UTC observation")
    require(moment.tzinfo is not None and moment.utcoffset() == timedelta(0),
            "UTC timezone is mandatory")
    return moment.astimezone(timezone.utc)


def day(value):
    require(isinstance(value, str) and DAY.fullmatch(value) is not None,
            "noncanonical target date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise KoreaWatchHold("invalid target date") from exc
    require(parsed.isoformat() == value, "invalid ISO target date")
    return parsed


def matured_slot(as_of):
    """Latest 17:47 UTC schedule whose 6-hour delayed-run grace has elapsed."""
    moment = utc(as_of) - timedelta(hours=GRACE_HOURS)
    candidate = moment.date()
    if (moment.hour, moment.minute, moment.second) < (CRON_HOUR, CRON_MINUTE, 0):
        candidate -= timedelta(days=1)
    return candidate


def summarize(ledgers, clock, *, commit, as_of):
    """Distinguish scheduled-run continuity from explicitly recovered coverage."""
    require(isinstance(commit, str) and SHA.fullmatch(commit) is not None,
            "exact Korea state SHA required")
    now = utc(as_of)
    require(type(clock) is dict and clock.get("desk") == "korea"
            and day(utc(clock["day_zero_utc"]).date().isoformat()) == EXPECTED_CLOCK_DAY,
            "unexpected Korea Day 0 clock")
    require(type(ledgers) is list and bool(ledgers) and len(ledgers) <= 70,
            "absent or excessive Korea ledger entries")
    scheduled, recovered = set(), set()
    seen = set()
    for receipt in ledgers:
        require(type(receipt) is dict and receipt.get("desk") == "korea"
                and type(receipt.get("run_id")) is str
                and receipt["run_id"] not in seen,
                "foreign, duplicate or malformed Korea ledger")
        ident = receipt["run_id"]
        seen.add(ident)
        target = day(receipt.get("target_date"))
        require(target >= EXPECTED_CLOCK_DAY and target <= now.date(),
                "outside supported target-date interval")
        started = utc(receipt.get("started_utc"))
        finished = utc(receipt.get("finished_utc"))
        require(started <= finished and finished <= now + timedelta(minutes=5),
                "untrustworthy ledger timestamps")
        origin = receipt.get("target_date_source")
        require(origin in (SOURCE_SCHEDULE, SOURCE_EXPLICIT, "manual-utc-date"),
                "unknown logical target-date provenance")
        if receipt.get("health") != "ok" or receipt.get("result") not in SUCCESS:
            continue
        if origin == SOURCE_SCHEDULE:
            require(RUN_ID.fullmatch(ident) is not None,
                    "scheduled success must be a distinct first-attempt Actions ID")
            scheduled.add(target)
        elif origin == SOURCE_EXPLICIT:
            recovered.add(target)

    latest = matured_slot(now)
    first = max(FIRST_SLOT, latest - timedelta(days=MAX_DAYS - 1))
    due = [first + timedelta(days=n)
           for n in range(max(0, (latest - first).days + 1))]
    missing = [d for d in due if d not in scheduled]
    recovered_only = [d for d in missing if d in recovered]
    uncovered = [d for d in missing if d not in recovered]
    current_missing = latest >= FIRST_SLOT and latest not in scheduled
    return {
        "schema": SCHEMA,
        "state_branch": STATE_BRANCH,
        "state_commit": commit,
        "checked_at_utc": now.isoformat().replace("+00:00", "Z"),
        "logical_cron_utc": "17:47",
        "grace_hours": GRACE_HOURS,
        "latest_mature_slot": latest.isoformat(),
        "evaluated_scheduled_slots": len(due),
        "successful_scheduled_slots": len(due) - len(missing),
        "missing_scheduled_dates": [d.isoformat() for d in missing],
        "source_dates_recovered_explicitly_but_not_scheduled": [
            d.isoformat() for d in recovered_only],
        "source_dates_without_successful_scheduled_or_explicit_recovery": [
            d.isoformat() for d in uncovered],
        "current_mature_slot_missing": current_missing,
        "status": ("CURRENT_SCHEDULED_SLOT_MISSING" if current_missing else
                   "HISTORICAL_SCHEDULED_GAPS_REMAIN" if missing else
                   "LEDGER_SCHEDULED_SLOTS_OBSERVED"),
        "authenticates_all_github_actions_attempts": False,
        "verifies_capture_bytes_or_publisher_completeness": False,
        "government_silence_established": False,
        "human_review_approved": False,
        "source_or_media_rights_approved": False,
        "production_eligible": False,
        "weekly_brief_eligible": False,
        "automatically_retries_source": False,
        "changes_state": False,
    }


def inspect_checkout(folder, *, as_of):
    """Sparse pinned checkout: only state ledger/clock metadata are read."""
    commit, ledgers = pinned_ledger_checkout(folder)
    clockfile = Path(folder) / "state" / "clock.json"
    require(clockfile.is_file() and not clockfile.is_symlink()
            and clockfile.stat().st_size <= 10000, "unsafe or absent Korea clock")
    clock = json.loads(clockfile.read_text(encoding="utf-8"))
    return summarize(ledgers, clock, commit=commit, as_of=as_of)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shadow-checkout", type=Path, required=True)
    parser.add_argument("--as-of-utc", help="UTC instant; default real UTC now")
    parser.add_argument("--fail-current-gap", action="store_true",
                        help="Fail only when the latest matured slot is missing")
    args = parser.parse_args(argv)
    now = utc(args.as_of_utc or datetime.now(timezone.utc))
    require(now <= datetime.now(timezone.utc) + timedelta(minutes=5),
            "refuse future-dated observations")
    report = inspect_checkout(args.shadow_checkout, as_of=now)
    # Only bounded metadata goes into Actions logs. Never print source bodies.
    print(json.dumps(report, sort_keys=True))
    if args.fail_current_gap and report["current_mature_slot_missing"]:
        print("::error::Korea has no successful scheduled-run ledger for the "
              "latest mature slot. Verify authenticated Actions attempt census; "
              "use explicit desk=korea,target_date only for source recovery, "
              "not as replacement for uninterrupted scheduled reliability.")
        return 2
    if report["missing_scheduled_dates"]:
        print("::warning::Korea has historical scheduled-run gaps; "
              "manual recovery never retroactively qualifies those slots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
