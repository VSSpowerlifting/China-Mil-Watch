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
that date.

No collection loss is observable in the reviewed Singapore corpus — the only
corpus either checkpoint review has read. The state-hash chain stayed coherent
across both boundaries, no fetch, extraction or access failure
was recorded, insertions continued in the runs that followed, and the 30-day
lookbacks overlap so heavily that the nominal day was inside the window either
way. Those facts are about what this desk observed and stored. They do not, and
cannot, establish that the ministry published nothing that this desk never
observed: no evidence reachable from inside the corpus can prove that negative.
The defect is date attribution; loss is unobserved, which is not the same claim
as ruled out.

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
A scheduled **first attempt** belongs to its **nominal slot**: the most recent
occurrence of the cron's time-of-day at or before the moment the job started.
That slot's UTC date is the logical collection date.

  started 21:42, cron 21:10  ->  same day      (on time)
  started 00:45, cron 21:10  ->  previous day  (delayed across midnight)
  started 05:20, cron 21:10  ->  previous day  (delayed eight hours)
  started 21:10, cron 21:10  ->  same day      (boundary is inclusive)

A delayed run and the next on-time run therefore resolve to different logical
dates, which is the property that stops two ledgers sharing one date.

This is a **repository-defined convention, not a reconstruction of GitHub's own
nominal occurrence.** A runner does not receive the scheduled time; only the
event name and the moment the job actually started are available. The rule
therefore assumes the delay is under twenty-four hours, which every observed
delay on this repository has been. A hypothetical delay beyond a full cron
period would resolve to the wrong slot, and nothing available inside the job
could detect it. That residual is accepted deliberately: it is far narrower
than the execution-date behaviour it replaces, and it is stated here rather
than hidden behind a claim of exactness.

Manual dispatch gets no slot. A hand-started run is not a scheduled one and may
not claim a scheduled one's date, so it records the honest UTC date it ran on
unless the operator names a date explicitly.

Re-runs are refused, not re-derived
-----------------------------------
`GITHUB_RUN_ATTEMPT` begins at 1 and increments with each re-run; a re-run keeps
the original run id, ref, commit and **triggering event**, but it does not keep
the original moment. Re-running a scheduled job from the UI a day later would
therefore arrive here looking exactly like a first attempt — `event_name` still
`schedule` — while `started` names an entirely different slot. The same hazard
applies to re-running a manual dispatch: the recomputed UTC date is simply the
date of the re-run.

Neither category is unambiguous, so both are refused: any attempt above 1 with
no explicit `--target-date` is fatal. An explicit `--target-date` stays
authoritative on a re-run, and it is the recovery path — a failed scheduled run
is recovered by a deliberate manual dispatch naming the day it was meant to
cover, never by an ambiguous UI re-run.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

#: How the logical date was arrived at. Recorded in the ledger so a reader
#: never has to infer it from the timestamps.
SOURCE_SCHEDULE = "schedule-slot"
SOURCE_MANUAL = "manual-utc-date"
SOURCE_EXPLICIT = "explicit"

#: Every value a collector may record, and therefore every value a reader may
#: accept. A ledger written before this module existed carries no
#: `target_date_source` at all and stays readable — the field is optional, its
#: *value* is not. `scripts/review_shadow_state.py` validates against the same
#: three, re-declared there rather than imported because its runtime imports
#: are pinned to an allowlist; `tests/test_shadow_logical_target_date.py` holds
#: the two copies equal.
SOURCES = (SOURCE_EXPLICIT, SOURCE_SCHEDULE, SOURCE_MANUAL)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CRON_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
# ASCII-pinned: `\d` is Unicode-aware and `int()` accepts other digit
# systems, so an unpinned pattern would read "\u0662" as 2. Actions writes
# ASCII; anything else here did not come from Actions.
_RUN_ATTEMPT = re.compile(r"^[0-9]+$")

#: What an operator is told to do when a re-run is refused. One sentence, kept
#: in one place so the two collectors cannot describe the recovery differently.
RERUN_RECOVERY = (
    "Recover by dispatching the workflow by hand with the target_date input "
    "set to the day the original attempt was meant to cover "
    "(Actions -> the desk's workflow -> Run workflow -> target_date), or "
    "locally with --target-date YYYY-MM-DD. Do not re-run the failed run from "
    "the UI: a re-run cannot say which day it means.")


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


def parse_run_attempt(value) -> int:
    """
    `GITHUB_RUN_ATTEMPT` as a positive integer.

    Actions sets this to 1 on a first attempt and increments it on every
    re-run. A value this module cannot read is not treated as 1: an unreadable
    attempt number means the caller does not know whether this is a re-run, and
    that is exactly the state in which a date must not be inferred.
    """
    text = "" if value is None else str(value).strip()
    if not _RUN_ATTEMPT.match(text):
        raise ScheduleError(
            "--run-attempt must be a positive integer (GITHUB_RUN_ATTEMPT "
            "begins at 1 and increments on each re-run), got %r" % (value,))
    attempt = int(text)
    if attempt < 1:
        raise ScheduleError(
            "--run-attempt must be at least 1, got %r. Attempt numbering "
            "starts at 1; %s cannot name an attempt." % (value, text))
    return attempt


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
                        cron_utc: str = None, explicit: str = None,
                        run_attempt=1) -> tuple:
    """
    Returns `(logical_date, source)`.

    Precedence, and each step is deliberate:

      0. `run_attempt` is validated first, whatever else was passed. An
         unreadable attempt number means the caller cannot tell a first run
         from a re-run, and a date inferred in that state would be a guess;
      1. an explicit `--target-date` always wins and is recorded as explicit —
         including on a re-run, where it is the only accepted input;
      2. any attempt above 1 without an explicit date is refused;
      3. a *scheduled* first attempt with a cron time resolves to its nominal
         slot;
      4. anything else — manual dispatch, a local run, a workflow that did not
         say — records the UTC date it actually ran on.

    Two refusals, for the same reason. A scheduled event whose cron time is
    missing is refused rather than falling through to (4): that fallthrough is
    the original bug, and a workflow that forgets to pass its cron should fail
    loudly on its first run, not quietly two months later inside a checkpoint
    review. A re-run without an explicit date is refused rather than resolved
    at (3) or (4): a re-run keeps the original event but not the original
    moment, so both rules would silently answer for a different day than the
    attempt being repeated.
    """
    attempt = parse_run_attempt(run_attempt)

    if explicit is not None and str(explicit).strip() != "":
        return parse_iso_date(explicit), SOURCE_EXPLICIT

    if started.tzinfo is None:
        raise ScheduleError("start time has no timezone: %r" % started)
    started = started.astimezone(timezone.utc)

    if attempt > 1:
        raise ScheduleError(
            "this is attempt %d of the run and no --target-date was given. A "
            "re-run keeps the original event but not the original moment, so "
            "resolving the date now would attribute this collection to "
            "whichever day the re-run happens to fall in rather than to the "
            "day the first attempt covered. Refusing to guess. %s"
            % (attempt, RERUN_RECOVERY))

    if (event_name or "").strip() == "schedule":
        if cron_utc is None or str(cron_utc).strip() == "":
            raise ScheduleError(
                "a scheduled run must name its cron time with --cron-utc; "
                "without it the logical date would fall back to the execution "
                "date, which is the defect this resolver exists to remove")
        return scheduled_slot_date(started, cron_utc), SOURCE_SCHEDULE

    return started.date(), SOURCE_MANUAL
