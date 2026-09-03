"""
The logical collection date of a shadow run — one definition, two collectors.

Why this module exists
----------------------
Both shadow collectors derived `target_date` from `datetime.now(timezone.utc)
.date()`: the date the job *executed*. GitHub Actions does not start a
scheduled job at its cron time; it starts it when a runner is free, and the
observed lateness on this repository runs to hours. When that lateness crosses
UTC midnight, the run is stamped with the following calendar date and its own
nominal date acquires no ledger at all.

Two real occurrences, both found by the Singapore Day 7 and Day 14 checkpoint
reviews and preserved in the published review evidence:

  cron 21:10 UTC
  run 33027905549  created 2026-08-27T00:45:40Z  stamped 2026-08-27  (nominal 08-26)
  run 33455386368  created 2026-09-01T00:35:45Z  stamped 2026-09-01  (nominal 08-31)

Each left a missing-day anomaly for a day on which collection had in fact
happened, and each made the *following* on-time run the second ledger to carry
that date. The corpus was never affected: the state-hash chain stayed coherent,
no fetch, extraction or access failure was recorded, and the 30-day lookback
covered the nominal day either way. The defect is date attribution, not loss.

What this fixes, and what it deliberately does not
--------------------------------------------------
It fixes attribution *at the source*, for future runs. It does not rewrite a
single historical ledger: those are append-only evidence, two completed human
reviews already reason about them, and a backfill would invalidate both. The
review tool is likewise left alone — a missing-day anomaly is a true statement
about the ledger set it reads, and teaching it to hide one would remove the
signal that found this bug.

The rule
--------
A scheduled run belongs to its **nominal slot**: the most recent occurrence of
the cron's time-of-day at or before the moment the job started. That slot's UTC
date is the logical collection date.

  started 21:42, cron 21:10  ->  same day      (on time)
  started 00:45, cron 21:10  ->  previous day  (delayed across midnight)
  started 05:20, cron 21:10  ->  previous day  (delayed eight hours)
  started 21:10, cron 21:10  ->  same day      (boundary is inclusive)

A delayed run and the next on-time run therefore resolve to different logical
dates, which is the property that stops two ledgers sharing one date.

Manual dispatch gets no slot. A hand-started run is not a scheduled one and may
not claim a scheduled one's date, so it records the honest UTC date it ran on
unless the operator names a date explicitly.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

#: How the logical date was arrived at. Recorded in the ledger so a reader
#: never has to infer it from the timestamps.
SOURCE_SCHEDULE = "schedule-slot"
SOURCE_MANUAL = "manual-utc-date"
SOURCE_EXPLICIT = "explicit"

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CRON_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ScheduleError(ValueError):
    """An input that cannot be trusted to name a day. Always fatal."""


def parse_iso_date(value: str, field: str = "--target-date") -> date:
    """
    Strict `YYYY-MM-DD`. `date.fromisoformat` alone is not strict enough here:
    it is the only guard between an operator's typo and a ledger that says a
    day it does not mean, so the shape is checked before the value.
    """
    text = "" if value is None else str(value).strip()
    if not _ISO_DATE.match(text):
        raise ScheduleError(
            "%s must be an ISO date of the form YYYY-MM-DD, got %r" % (field, value))
    try:
        return date.fromisoformat(text)
    except ValueError as exc:                      # 2026-02-30 and friends
        raise ScheduleError("%s is not a real date: %r (%s)" % (field, value, exc))


def parse_cron_utc(value: str) -> tuple:
    """`HH:MM` in UTC — the time-of-day half of the workflow's cron."""
    text = "" if value is None else str(value).strip()
    m = _CRON_TIME.match(text)
    if not m:
        raise ScheduleError(
            "--cron-utc must be a 24-hour UTC time of the form HH:MM, got %r" % value)
    return int(m.group(1)), int(m.group(2))


def scheduled_slot_date(started: datetime, cron_utc: str) -> date:
    """
    The UTC date of the nominal cron slot this run belongs to.

    `started` must be timezone-aware; a naive datetime is a caller that does
    not know which day it is in, which is the whole bug.
    """
    if started.tzinfo is None:
        raise ScheduleError(
            "start time has no timezone: %r. This module exists because a "
            "moment without an offset cannot be placed on a day." % started)
    hour, minute = parse_cron_utc(cron_utc)
    started = started.astimezone(timezone.utc)
    if (started.hour, started.minute) < (hour, minute):
        return (started - timedelta(days=1)).date()
    return started.date()


def resolve_target_date(started: datetime, event_name: str = None,
                        cron_utc: str = None, explicit: str = None) -> tuple:
    """
    Returns `(logical_date, source)`.

    Precedence, and each step is deliberate:

      1. an explicit `--target-date` always wins and is recorded as explicit;
      2. a *scheduled* event with a cron time resolves to its nominal slot;
      3. anything else — manual dispatch, a local run, a workflow that did not
         say — records the UTC date it actually ran on.

    A scheduled event whose cron time is missing is refused rather than
    silently falling through to (3): that fallthrough is the original bug, and
    a workflow that forgets to pass its cron should fail loudly on the first
    run, not quietly two months later inside a checkpoint review.
    """
    if explicit is not None and str(explicit).strip() != "":
        return parse_iso_date(explicit), SOURCE_EXPLICIT

    if started.tzinfo is None:
        raise ScheduleError("start time has no timezone: %r" % started)
    started = started.astimezone(timezone.utc)

    if (event_name or "").strip() == "schedule":
        if cron_utc is None or str(cron_utc).strip() == "":
            raise ScheduleError(
                "a scheduled run must name its cron time with --cron-utc; "
                "without it the logical date would fall back to the execution "
                "date, which is the defect this resolver exists to remove")
        return scheduled_slot_date(started, cron_utc), SOURCE_SCHEDULE

    return started.date(), SOURCE_MANUAL
