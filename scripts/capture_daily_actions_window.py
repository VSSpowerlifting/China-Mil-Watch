#!/usr/bin/env python3
"""Bounded, explicit read-only Daily Actions history across 1–7 UTC days.

Joins the existing exact-day GitHub Actions metadata importer; it does not
interpret job logs or authenticate collection/publishing/queue evidence.
This is an operator-invoked CLI, never an automatic monitoring loop.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import audit_daily_run_receipts as audit
from scripts import capture_daily_actions_receipts as capture

MAX_DAYS = 7
MAX_ATTEMPTS = 200


class WindowError(ValueError):
    """Unbounded, duplicate, incomplete or contradictory metadata window."""


def require(ok, reason):
    if not ok:
        raise WindowError(reason)


def merge_window(start_utc_day, end_utc_day, *, fetch_day=None, as_of_utc=None):
    """Return one canonical raw receipt, not authenticated or a completeness proof.

    Each daily fetch must succeed completely; one failing/malformed UTC date
    fails the entire bounded window rather than silently dropping that date.
    """
    start = capture.exact_utc_date(start_utc_day)
    end = capture.exact_utc_date(end_utc_day)
    require(start <= end, "window end precedes start")
    span = (end - start).days + 1
    require(1 <= span <= MAX_DAYS,
            "Daily Actions window exceeds seven UTC creation dates")
    require(end <= datetime.now(timezone.utc).date(),
            "future UTC creation-day window is not permitted")
    as_of = (as_of_utc or datetime.now(timezone.utc)
             .isoformat().replace("+00:00", "Z"))
    # Verify a single UTC as-of *before* any HTTP request.
    stamp = audit.parse_utc(as_of)
    require(stamp.date() >= end, "as-of precedes requested last UTC day")
    capture_one = capture.capture if fetch_day is None else fetch_day
    runs = []
    seen = set()
    for offset in range(span):
        day = (start + timedelta(days=offset)).isoformat()
        receipt = capture_one(day, as_of_utc=as_of)
        require(type(receipt) is dict and
                set(receipt) == {"schema", "as_of_utc", "runs"} and
                receipt["schema"] == audit.SCHEMA and
                receipt["as_of_utc"] == as_of and
                type(receipt["runs"]) is list,
                "one UTC day's Actions receipt has unexpected schema or as-of")
        audit.interpret(receipt)
        for row in receipt["runs"]:
            created = audit.parse_utc(row["created_at"])
            require(created.date().isoformat() == day,
                    "run attributed to wrong UTC capture date")
            identity = (row["run_id"], row["attempt"])
            require(identity not in seen,
                    "duplicate run attempt in combined UTC window")
            seen.add(identity)
            runs.append(row)
            require(len(runs) <= MAX_ATTEMPTS,
                    "combined seven-day Actions receipt exceeds 200 attempts")
    combined = {"schema": audit.SCHEMA, "as_of_utc": as_of,
                "runs": sorted(runs, key=lambda r: (
                    r["created_at"], r["run_id"], r["attempt"]))}
    # Keep all the downstream conservative/unauthenticated flags unchanged.
    interpreted = audit.interpret(combined)
    require(interpreted["provided_attempts"] == len(runs),
            "combined report unexpectedly lost run attempts")
    require(interpreted["complete_actions_history_established"] is False
            and interpreted["archive_capture_verified"] is False
            and interpreted["publication_authorized"] is False,
            "combined report gained unsupported authority")
    return combined


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-utc-day", required=True,
                   help="inclusive YYYY-MM-DD UTC Actions creation date")
    p.add_argument("--through-utc-day", required=True,
                   help="inclusive YYYY-MM-DD, at most seven UTC days from start")
    args = p.parse_args(argv)
    try:
        print(json.dumps(merge_window(args.from_utc_day,
                                      args.through_utc_day),
                         indent=2, sort_keys=True))
    except (WindowError, capture.CaptureError, audit.ReceiptError,
            ValueError, TypeError, KeyError) as exc:
        p.exit(1, "Daily Actions window refused: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
