#!/usr/bin/env python3
"""Write a private metadata-only weekly regional evidence inventory.

This does NOT invoke a model, send email, attest Japan/Vietnam shadow state,
approve publisher source-use, or alter the tracked SQLite database.
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

from core.regional_weekly_inventory import inspect  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-ending", required=True,
                        help="Exact reporting Saturday YYYY-MM-DD")
    parser.add_argument("--as-of", required=True,
                        help="Last included publisher-date YYYY-MM-DD")
    parser.add_argument("--review-local-day", required=True,
                        help="New York-local review day YYYY-MM-DD")
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    parser.add_argument("--marker", type=Path,
                        default=ROOT / ".github/state/last_daily_run_date.txt")
    parser.add_argument("--private-evidence-directory", type=Path,
                        help="Optional strictly validated research packet dir; "
                             "all shadow sources remain unapproved metadata holds")
    parser.add_argument("--out", type=Path, required=True,
                        help="Private file OUTSIDE the source repository; "
                             "must not already exist")
    args = parser.parse_args(argv)
    target = args.out.expanduser().resolve()
    if ROOT.resolve() == target or ROOT.resolve() in target.parents:
        parser.error("private inventory must be written outside the repository")
    if not target.parent.is_dir() or args.out.is_symlink() or target.exists():
        parser.error("output parent must exist and new output cannot overwrite files")
    try:
        report = inspect(
            week_ending=args.week_ending, as_of=args.as_of,
            review_day=args.review_local_day, database=args.db,
            marker_path=args.marker, research_directory=args.private_evidence_directory)
        # Exclusive owner-only creation; never create a public CI artifact.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        handle = os.open(str(target), flags, 0o600)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False,
                          sort_keys=True, indent=2)
                stream.write("\n")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    # No sources, bodies, private journal research, or URLs in stdout.
    print("PRIVATE regional inventory created; sources not authorized for model use.")
    print("Production records: %d; held: %d; pending research: %d." % (
        len(report["production_evidence"]),
        len(report["held_production_records"]),
        len(report["pending_private_research"])))
    print("Production preflight: " + report["production_preflight"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
