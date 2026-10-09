#!/usr/bin/env python3
"""Read-only historic/current MPS source comparison, NOT source-use approval.

Input queues must be generated from the separately verified exact Git state
commits, never handwritten. Does not fetch publishers, call models or email.
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
from core.vietnam_mps_source_version_drift import compare_mps_versions  # noqa: E402
from scripts.prepare_vietnam_briefs_evidence import load as load_verified_json  # noqa: E402


def new_private_report(path, receipt):
    # Preserve the requested leaf for exclusive no-follow creation.
    # Resolve separately only to enforce the repository boundary.
    target = Path(path).expanduser().absolute()
    resolved = target.resolve()
    root = ROOT.resolve()
    if (target.is_symlink() or target.exists() or
            resolved == root or root in resolved.parents or
            not target.parent.is_dir() or target.parent.is_symlink()):
        raise ValueError("new private MPS report must be outside repo and not overwrite")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(target), flags, 0o600)
    owned = None
    try:
        owned = os.fstat(fd)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = None  # stream owns descriptor once fdopen succeeds.
            json.dump(receipt, stream, indent=2, sort_keys=True,
                      ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    except BaseException:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        # Cleanup only if the created inode still occupies this path.
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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research-directory", type=Path,
                   default=ROOT / "research/briefs_editorial_evidence")
    p.add_argument("--historical-queue", action="append", type=Path, required=True,
                   help="Repeat for exact Oct5 and Oct7 historical state exports")
    p.add_argument("--current-queue", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    if len(args.historical_queue) != 2:
        p.error("exactly two historical state-commit queues required")
    try:
        records = load_editorial_evidence(
            "2026-10-10", "2026-10-10", directory=args.research_directory)
        history = [load_verified_json(q, 5000000) for q in args.historical_queue]
        latest = load_verified_json(args.current_queue, 5000000)
        result = compare_mps_versions(records, history, latest)
        new_private_report(args.out, result)
    except (ValueError, TypeError, OSError, UnicodeError) as exc:
        p.error(str(exc))
    print("MPS shadow source rows compared: " + str(result["compared_sources"]))
    for status, number in result["comparison_counts"].items():
        print(status + ": " + str(number))
    print("Publisher/human/rights reviews NOT DONE; model/email/publication FALSE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
