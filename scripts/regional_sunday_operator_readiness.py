#!/usr/bin/env python3
"""No-model, no-send Sunday regional operational-readiness digest.

This report is private diagnostic metadata. It never grants source-use,
manuscript, editor email or publication approval.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH  # noqa: E402
from core.regional_sunday_operator_readiness import summarize  # noqa: E402
from core.regional_weekly_inventory import inspect  # noqa: E402


def _private_write(destination, report):
    dest = Path(destination).expanduser()
    target = dest.resolve()
    root = ROOT.resolve()
    if (dest.is_symlink() or dest.exists() or
            target == root or root in target.parents or
            not target.parent.is_dir() or dest.parent.is_symlink()):
        raise ValueError("new operator report must be outside repo in an existing directory")
    flags = os.O_CREAT | os.O_WRONLY | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(target), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(report, output, sort_keys=True,
                      ensure_ascii=False, allow_nan=False, indent=2)
            output.write("\n")
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--week-ending", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--review-local-day", required=True)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--marker", type=Path,
                   default=ROOT / ".github/state/last_daily_run_date.txt")
    p.add_argument("--private-evidence-directory", type=Path,
                   help="Validated pending Japan/Vietnam research notes, HOLD only")
    p.add_argument("--out", type=Path, required=True,
                   help="New private JSON file outside repo, never overwritten")
    args = p.parse_args(argv)
    try:
        inventory = inspect(
            week_ending=args.week_ending,
            as_of=args.as_of,
            review_day=args.review_local_day,
            database=args.db,
            marker_path=args.marker,
            research_directory=args.private_evidence_directory)
        report = summarize(inventory)
        _private_write(args.out, report)
    except (ValueError, OSError, TypeError) as exc:
        p.error(str(exc))
    print("Regional Sunday production corpus: " + report["machine_corpus_gate"])
    print("Held reasons: " + str(sum(report["held_reason_counts"].values())))
    print("Pending unapproved research: " +
          str(sum(report["pending_private_research_by_desk"].values())))
    print("Model FALSE; Dylan delivery FALSE; publication FALSE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
