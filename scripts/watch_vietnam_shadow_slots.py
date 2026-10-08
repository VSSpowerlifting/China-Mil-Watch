"""Read-only logical-slot watchdog for Vietnam's three-source ministry collector.

An independently Git-verified shadow corpus establishes which collection
slots were *observed*. It does not prove a ministry issued no publications.
A missed scheduled slot is only overdue after a 12-hour grace interval,
because GitHub Actions routinely starts jobs hours after their cron slot.

This tool NEVER dispatches a recovery job, changes historical ledgers,
resets Day 0, opens publisher sites, grants reuse rights, writes production
state, sends an editorial email, or qualifies the Vietnam Desk.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from core.shadow_schedule import SOURCE_EXPLICIT, SOURCE_SCHEDULE
from scripts import review_vietnam_ministry_state as ministry
from scripts import review_vietnam_shadow_state as formal
from scripts.shadow_collect_vietnam_ministry import load_source

SOURCE = "vn_mps_foreign_affairs_vi"
STATE_BRANCH = "shadow/vietnam-mps-foreign-affairs"
WATCH_SCHEMA = "vietnam-ministry-scheduled-slot-watch/1"
EXPECTED_SLOT_UTC = time(18, 17)
GRACE_HOURS = 12
MAX_REPORT_DAYS = 30
HEX40 = re.compile(r"[a-f0-9]{40}\Z")


class WatchdogRefused(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise WatchdogRefused(reason)


def utc_moment(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise WatchdogRefused("invalid UTC timestamp") from exc
    else:
        raise WatchdogRefused("timestamp must be a UTC ISO instant")
    require(dt.tzinfo is not None and dt.utcoffset() == timedelta(0),
            "explicit UTC timestamp required")
    return dt.astimezone(timezone.utc)


def strict_day(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
            "logical day must be canonical YYYY-MM-DD")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise WatchdogRefused("invalid logical day") from exc
    require(result.isoformat() == value, "invalid canonical day")
    return result


def matured_latest(as_of, grace_hours=GRACE_HOURS):
    """Return the latest scheduled UTC slot past its allowed late-start grace."""
    require(type(grace_hours) is int and 0 <= grace_hours <= 18,
            "invalid schedule grace")
    moment = utc_moment(as_of) - timedelta(hours=grace_hours)
    slot_date = moment.date()
    if moment.time().replace(tzinfo=None) < EXPECTED_SLOT_UTC:
        slot_date -= timedelta(days=1)
    return slot_date


def summarize(evidence, *, state_commit, as_of, source_slug=SOURCE):
    """Do not infer completeness from lookback overlap or government silence."""
    require(isinstance(evidence, dict) and evidence.get("source_slug") == source_slug
            and source_slug == SOURCE, "foreign shadow reviewer/source")
    require(isinstance(state_commit, str) and HEX40.fullmatch(state_commit),
            "exact immutable MPS Git state required")
    as_of = utc_moment(as_of)
    mature = matured_latest(as_of)
    runs = evidence.get("runs")
    require(isinstance(runs, list) and bool(runs),
            "no independently verified source run ledger")
    clock = evidence.get("clock")
    require(isinstance(clock, dict) and clock.get("day_zero_utc"),
            "MPS has no durable successful Day 0 clock")
    day_zero = utc_moment(clock["day_zero_utc"])
    require(day_zero <= as_of + timedelta(minutes=5),
            "source clock dates the future")
    observed = {}
    first_scheduled = None
    latest_ok = None
    seen_run_ids = set()
    for record in runs:
        require(isinstance(record, dict) and
                isinstance(record.get("run_id"), str)
                and bool(record["run_id"]), "invalid run ledger ID")
        require(record["run_id"] not in seen_run_ids,
                "duplicate run ledger ID")
        seen_run_ids.add(record["run_id"])
        day = strict_day(record.get("target_date"))
        started = utc_moment(record.get("started_utc"))
        finished = utc_moment(record.get("finished_utc"))
        require(started <= finished and finished <= as_of + timedelta(minutes=5),
                "run timing invalid or postdates observation")
        require(record.get("health") in ("ok", "fail"),
                "unknown ministry run health")
        source = record.get("target_date_source")
        require(source in (SOURCE_SCHEDULE, SOURCE_EXPLICIT, "manual-utc-date"),
                "unknown target-date provenance")
        # The upstream reviewer confirms hashes and all capture/observation
        # ledgers. We only count explicitly successful target-date slots.
        if record["health"] != "ok":
            continue
        observed.setdefault(day, []).append(record["run_id"])
        latest_ok = max(latest_ok, day) if latest_ok else day
        if source == SOURCE_SCHEDULE:
            first_scheduled = min(first_scheduled, day) if first_scheduled else day
    require(first_scheduled is not None, "no known successful scheduled collection")
    # An explicit recovery date can close a missing slot, but an original
    # manually designated bootstrap date cannot invent prior schedule history.
    start = max(first_scheduled, mature - timedelta(days=MAX_REPORT_DAYS - 1))
    due = []
    if mature >= start:
        due = [start + timedelta(days=i)
               for i in range((mature - start).days + 1)]
    missing = [d.isoformat() for d in due if d not in observed]
    latest_day = latest_ok.isoformat() if latest_ok else None
    if missing:
        status = "overdue-logical-slots"
    elif due:
        status = "verified-scheduled-slots-present"
    else:
        status = "awaiting-first-mature-slot"
    return {
        "schema": WATCH_SCHEMA,
        "source_slug": SOURCE,
        "state_branch": STATE_BRANCH,
        "state_commit": state_commit,
        "checked_at_utc": as_of.isoformat().replace("+00:00", "Z"),
        "cron_utc": "18:17",
        "grace_hours": GRACE_HOURS,
        "latest_mature_scheduled_slot": mature.isoformat(),
        "first_known_scheduled_slot": first_scheduled.isoformat(),
        "latest_successful_logical_date": latest_day,
        "evaluated_slots": len(due),
        "present_slots": len(due) - len(missing),
        "overdue_logical_dates": missing,
        "status": status,
        "manual_recovery_required_if_overdue": bool(missing),
        "manual_recovery_workflow": "vietnam_ministry_shadow.yml",
        "manual_recovery_input": "target_date",
        "do_not_use_actions_rerun": True,
        "full_publisher_coverage_verified": False,
        "collection_window_complete_for_editorial": False,
        "government_silence_established": False,
        "desk_qualified": False,
        "email_sent": False,
    }


def verify_actual_state(state_repo, commit, *, as_of):
    """Review a named isolated state tree before inspecting its run ledger."""
    require(isinstance(commit, str) and HEX40.fullmatch(commit),
            "full exact 40-hex shadow commit required")
    repo = formal.resolve_state_repo(state_repo)
    formal.verify_state_commit(repo, commit, STATE_BRANCH)
    with tempfile.TemporaryDirectory(prefix="ipr-vn-slot-watch-") as tmp:
        state = formal.export_state_tree(repo, commit, Path(tmp) / "state")
        evidence = ministry.review(state, SOURCE)
        return summarize(evidence, state_commit=commit, as_of=as_of)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--state-repo", type=Path, required=True)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--as-of-utc", default=None,
                   help="UTC observation instant; omitted means now")
    p.add_argument("--require-current-slot", action="store_true",
                   help="fail only after the logical scheduled slot exceeds 12h grace")
    p.add_argument("--out", type=Path,
                   help="optional new untracked private output outside the repository")
    args = p.parse_args(argv)
    observed = utc_moment(args.as_of_utc or datetime.now(timezone.utc))
    require(observed <= datetime.now(timezone.utc) + timedelta(minutes=5),
            "refuse future-dated operational observations")
    result = verify_actual_state(args.state_repo, args.state_commit,
                                 as_of=observed)
    if args.out is not None:
        root = Path(__file__).resolve().parents[1].resolve()
        resolved = args.out.resolve()
        require(not args.out.exists() and not args.out.is_symlink()
                and args.out.parent.is_dir()
                and not args.out.parent.is_symlink()
                and resolved != root and root not in resolved.parents,
                "private watchdog report must be new, outside repository")
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    # Never print article text, source URLs, unpublished synopses or captures.
    print(json.dumps({
        "status": result["status"],
        "latest_mature_scheduled_slot": result["latest_mature_scheduled_slot"],
        "latest_successful_logical_date": result["latest_successful_logical_date"],
        "overdue_logical_dates": result["overdue_logical_dates"],
        "government_silence_established": False,
    }, sort_keys=True))
    if args.require_current_slot and result["overdue_logical_dates"]:
        raise SystemExit("REFUSED: at least one mature Vietnam MPS collection "
                         "date lacks a successful target-date ledger; "
                         "dispatch workflow manually with exact target_date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
