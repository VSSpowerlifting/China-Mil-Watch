#!/usr/bin/env python3
"""Create an UNSIGNED private worksheet for held Japan/Vietnam originals.

This does NOT review a source, authorize reuse, activate a desk, call a model,
or send an editor email. It makes human verification work explicit.
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
from core.regional_typed_human_review_prep import create_unsigned_worksheet  # noqa: E402
from core.regional_weekly_inventory import inspect  # noqa: E402


def save_private(path, doc):
    # Preserve the requested pathname for the exclusive open. Resolving the
    # leaf here would permit a dangling symlink introduced during preflight.
    target = Path(path).expanduser().absolute()
    resolved = target.resolve()
    root = ROOT.resolve()
    if (target.exists() or target.is_symlink() or
            resolved == root or root in resolved.parents or
            not target.parent.is_dir() or target.parent.is_symlink()):
        raise ValueError("private review worksheet must be a new file outside repo")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(target), flags, 0o600)
    owned = None
    try:
        owned = os.fstat(fd)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = None  # The stream now owns this descriptor.
            json.dump(doc, stream, ensure_ascii=False, sort_keys=True,
                      indent=2, allow_nan=False)
            stream.write("\n")
    except BaseException:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        # Best-effort rollback: never unlink an observed replacement.
        if owned is not None:
            try:
                current = target.lstat()
                if (not target.is_symlink() and
                        (current.st_dev, current.st_ino) ==
                        (owned.st_dev, owned.st_ino)):
                    target.unlink()
            except OSError:
                pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--review-local-day", required=True)
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    parser.add_argument("--marker", type=Path,
                        default=ROOT / ".github/state/last_daily_run_date.txt")
    parser.add_argument("--research-directory", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        records = load_editorial_evidence(
            args.week_ending, args.as_of, directory=args.research_directory)
        inventory = inspect(
            week_ending=args.week_ending, as_of=args.as_of,
            review_day=args.review_local_day,
            database=args.db, marker_path=args.marker,
            research_directory=args.research_directory)
        unsigned = create_unsigned_worksheet(inventory, records)
        save_private(args.out, unsigned)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.error(str(exc))
    print("Private UNSIGNED human source worksheet: %d held records." %
          unsigned["source_count"])
    print("All reviewer checks UNSET; model/email/publication authorization FALSE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
