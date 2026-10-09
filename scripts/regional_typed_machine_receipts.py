#!/usr/bin/env python3
"""Read-only, no-model alignment of historical Japan/Vietnam machine receipts.

Important: validates supplied metadata contracts, but it does NOT rerun Git
objects, inspect live publisher text, authorize copying, or approve a Brief.
Generate the input attestations separately via their existing state auditors.
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

from core.regional_typed_machine_receipts import reconcile_machine_receipts  # noqa: E402


def load(path, limit=500000):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("receipt must be bounded regular JSON, not a symlink")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("receipt must be a JSON object")
    return data


def write_private(path, result):
    path = Path(path).expanduser()
    root = ROOT.resolve()
    dest = path.resolve()
    if (path.is_symlink() or path.exists() or
            dest == root or root in dest.parents or
            not dest.parent.is_dir() or
            dest.parent.is_symlink()):
        raise ValueError("new private report must be outside repo and not a symlink")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(dest), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as writer:
            json.dump(result, writer, indent=2, sort_keys=True, ensure_ascii=False)
            writer.write("\n")
    except BaseException:
        dest.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holds", type=Path, required=True,
                        help="Existing regional typed-source HOLD report")
    parser.add_argument("--japan-attestation", type=Path,
                        help="Separate exact historical MOD source receipt")
    parser.add_argument("--vietnam-queue", type=Path, action="append", default=[],
                        help="Repeat for EACH historical MPS state-commit queue")
    parser.add_argument("--out", type=Path, required=True,
                        help="New private metadata-only receipt outside repo")
    args = parser.parse_args(argv)
    if len(args.vietnam_queue) > 4:
        parser.error("at most four distinct historical MPS queues are accepted")
    try:
        holds = load(args.holds)
        japan = load(args.japan_attestation) if args.japan_attestation else None
        queues = [load(x) for x in args.vietnam_queue]
        receipt = reconcile_machine_receipts(
            holds, japan=japan, vietnam_queues=queues)
        write_private(args.out, receipt)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.error(str(exc))
    counts = {desk: sum(x["desk"] == desk for x in receipt["items"])
              for desk in ("japan", "vietnam")}
    print("Private HOLD reconciliation: Japan %d, Vietnam %d." %
          (counts["japan"], counts["vietnam"]))
    print("Human source rights PENDING. Model FALSE, editor email FALSE, publication FALSE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
