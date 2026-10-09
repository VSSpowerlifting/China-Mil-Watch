#!/usr/bin/env python3
"""Manual owner-only private source-review seal and offline synopsis preview.

No model request, sending, public artifacts, production writes or publication.
Always re-inspects the tracked database via a scratch copy.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.regional_reviewed_evidence import (  # noqa: E402
    ReviewGateError, private_model_packet, sign_private_review,
)
from core.regional_weekly_inventory import inspect  # noqa: E402

CONFIRM = "I REVIEWED SOURCES FOR PRIVATE MODEL SYNOPSES"


def _json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 50000:
        raise ReviewGateError("review file must be a bounded, regular private JSON file")
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReviewGateError("duplicate JSON key refused: " + key)
            result[key] = value
        return result
    with path.open(encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=no_duplicates,
                         parse_constant=lambda val: (_ for _ in ()).throw(
                             ReviewGateError("nonfinite JSON value refused")))


def _out(path, data):
    target = Path(path).expanduser().resolve()
    if target == ROOT.resolve() or ROOT.resolve() in target.parents:
        raise ReviewGateError("private review output may not be in the repository")
    if target.exists() or target.is_symlink() or not target.parent.is_dir():
        raise ReviewGateError("private review output must be new in an existing directory")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    handle = os.open(str(target), flags, 0o600)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True,
                      indent=2, allow_nan=False)
            stream.write("\n")
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal", "preview"))
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--review-local-day", required=True)
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    parser.add_argument("--marker", type=Path,
                        default=ROOT / ".github/state/last_daily_run_date.txt")
    parser.add_argument("--review", type=Path, required=True,
                        help="For seal: manually composed unsigned docket; "
                             "for preview: signed reviewed docket")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        parser.error("owner-only reviewed source material requires an interactive TTY")
    try:
        inventory = inspect(week_ending=args.week_ending, as_of=args.as_of,
                            review_day=args.review_local_day,
                            database=args.db, marker_path=args.marker)
        material = _json(args.review)
        if args.action == "seal":
            print("Sign only after independently checking the publisher's original")
            print("and confirming each synopsis is appropriately source-attributed.")
            print("This authorizes private synopsis review only, not publication.")
            if input("Type the exact approval phrase: ").strip() != CONFIRM:
                raise ReviewGateError("human source review confirmation missing")
        secret = getpass.getpass(
            "Owner-held review key (minimum 32 bytes, not stored): ").encode("utf-8")
        if args.action == "seal":
            result = sign_private_review(material, inventory, secret)
        else:
            result = private_model_packet(inventory, material, secret)
        _out(args.out, result)
    except (ReviewGateError, OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.action == "seal":
        print("PRIVATE review sealed; no AI model called or email sent.")
    else:
        print("PRIVATE synopsis packet verified; no AI model called or email sent.")
        print("Reviewed source count: %d" % len(result["production_sources"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
