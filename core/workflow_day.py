"""
The workflow day — one definition, used by everything that records one.

The daily workflow's whole contract is "at most one successful run per New York
calendar day". Its scheduling guard reads `America/New_York` to decide that.
`pipeline._write_billing_failure_marker()` wrote `date.today()` instead — the
runner's UTC date — while its own docstring claimed it wrote the New York date.

Every configured cron window sits at 08:23-10:23 EDT, where the two agree, so
the mismatch has never fired. It is four hours of latitude wide: a run failing
after 20:00 New York would stamp *tomorrow's* marker on *today's* failure,
suppressing a day that never failed while leaving the day that did fail open.
Moving a cron window is a one-line change that would silently arm it.

Why a module rather than a fixed offset
---------------------------------------
`-04:00` is right for eight months of the year. `zoneinfo` is right for all
twelve, and the transitions are exactly where a hand-rolled offset breaks:
2026-03-08 and 2026-11-01, both of which the tests exercise.

Why not share code with the workflow
------------------------------------
The guard is inline Python inside `daily_update.yml` and already reads New York
correctly. Making it import this module would mean the workflow could not run
before dependencies are installed, for no gain. Instead the two are held
together by a test that *executes* the guard body out of the YAML and compares
its answer to this function's at frozen instants, including both DST
transitions. Duplication that is proved equal is safer here than a shared
import that changes when the workflow can run.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

#: The timezone the daily workflow's "one run per day" contract is written in.
#: Not configurable: two components disagreeing about which day it is *is* the
#: defect this module exists to remove.
WORKFLOW_TIMEZONE = ZoneInfo("America/New_York")

WORKFLOW_TIMEZONE_NAME = "America/New_York"


def workflow_day(now: datetime = None) -> date:
    """
    The calendar date the daily workflow considers "today".

    `now` is for tests. It may be timezone-aware, in which case it is converted;
    a naive datetime is rejected rather than guessed at, because assuming a
    zone for it is how this bug started.
    """
    if now is None:
        return datetime.now(WORKFLOW_TIMEZONE).date()
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError(
            "workflow_day() needs an aware datetime; a naive one has no "
            "answer and guessing its zone is the defect this replaces")
    return now.astimezone(WORKFLOW_TIMEZONE).date()


def workflow_day_string(now: datetime = None) -> str:
    """The same value in the `YYYY-MM-DD` form the state files hold."""
    return workflow_day(now).isoformat()
