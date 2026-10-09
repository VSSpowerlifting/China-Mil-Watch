#!/usr/bin/env python3
"""Private no-send Japan/Vietnam source hold receipt (no approval).

This tool does not collect articles, check current publisher body fidelity,
grant copy rights, call a model, write production, or email any editor.
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

from core.brief_editorial_evidence import load_editorial_evidence  # noqa: E402
from core.regional_typed_research_holds import audit_typed_holds  # noqa: E402
from core.regional_weekly_inventory import inspect  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--review-local-day", required=True)
    parser.add_argument("--research-directory", required=True, type=Path)
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    parser.add_argument("--marker", type=Path,
                        default=ROOT / ".github/state/last_daily_run_date.txt")
    parser.add_argument("--out", required=True, type=Path,
                        help="New private JSON file outside the source repository")
    args = parser.parse_args(argv)
    target = args.out.expanduser()
    if target.is_symlink() or target.exists():
        parser.error("source hold report cannot overwrite or follow a symlink")
    resolved = target.resolve()
    if resolved == ROOT.resolve() or ROOT.resolve() in resolved.parents:
        parser.error("private research hold report must be outside repo")
    if not resolved.parent.is_dir():
        parser.error("output directory must exist and be private")
    try:
        rows = load_editorial_evidence(
            args.week_ending, args.as_of, directory=args.research_directory)
        inventory = inspect(
            week_ending=args.week_ending, as_of=args.as_of,
            review_day=args.review_local_day, database=args.db,
            marker_path=args.marker, research_directory=args.research_directory)
        report = audit_typed_holds(inventory, rows)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(resolved), flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(report, output, sort_keys=True,
                          ensure_ascii=False, indent=2, allow_nan=False)
                output.write("\n")
        except BaseException:
            resolved.unlink(missing_ok=True)
            raise
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    # A typed research ID is not evidence of rights or accepted manuscript use.
    print("PRIVATE research metadata holds: Japan %d; Vietnam %d." % (
        report["counts"]["japan"], report["counts"]["vietnam"]))
    print("First-pilot roster gap categories: %d." %
          len(report["first_pilot_roster_gaps"]))
    print("Model authorization FALSE; editor email FALSE; publication FALSE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
