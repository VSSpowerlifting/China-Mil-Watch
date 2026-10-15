"""Explicit, scratch-only BIS receipt-to-SQLite admission rehearsal.

NO production DB option; NO Git or network access; NO Pages output. Receipts
supplied to this command are *untrusted rehearsal inputs*, never qualified
scheduled observations. Live admission needs an independently built gate.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from core.us_bis_official_metadata import BISAdmissionHold, admit_scratch, load_staged_links, validate

REPO_ROOT = Path(__file__).resolve().parent.parent


def stage(packet_path, scratch_db, *, input_reference_sha):
    packet_path = Path(packet_path)
    output = Path(scratch_db)
    if not output.is_absolute():
        raise BISAdmissionHold("scratch_db_must_be_absolute")
    destination = output.resolve(strict=False)
    if (destination == REPO_ROOT or REPO_ROOT in destination.parents
            or destination == (REPO_ROOT / "pla_watch.db")
            or output.is_symlink() or output.exists()
            or not destination.parent.is_dir()):
        raise BISAdmissionHold("scratch_destination_not_isolated_or_not_new")
    if (not packet_path.is_file() or packet_path.is_symlink()
            or packet_path.stat().st_size > 120_000
            or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\.json",
                                packet_path.name)):
        raise BISAdmissionHold("unsafe_or_unnamed_receipt")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    day = packet_path.stem
    # Check before even opening a SQLite connection on the scratch destination.
    validate(packet, receipt_day=day)
    try:
        with sqlite3.connect(str(destination)) as con:
            added = admit_scratch(
                con, packet, receipt_day=day,
                input_reference_sha=input_reference_sha)
            if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise BISAdmissionHold("scratch_integrity_failed")
        rows = load_staged_links(destination)
        if len(rows) != len(packet["rows"]):
            raise BISAdmissionHold("scratch_readback_disagrees")
    except Exception:
        # Scratch DB only; never touch production paths or source evidence.
        destination.unlink(missing_ok=True)
        raise
    return {"status": "SCRATCH_ONLY_NOT_AUTHENTICATED",
            "typed_links_staged": added,
            "input_rows": len(packet["rows"]),
            "scheduled_source_proved": False,
            "approved_for_live_admission": False,
            "live_records_written": 0, "site_modified": False}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--scratch-db", required=True)
    ap.add_argument("--input-reference-sha", required=True)
    ap.add_argument("--acknowledge-unauthenticated-rehearsal",
                    action="store_true")
    args = ap.parse_args(argv)
    if not args.acknowledge_unauthenticated_rehearsal:
        raise SystemExit("HOLD: this is only an unauthenticated scratch rehearsal")
    try:
        result = stage(args.receipt, args.scratch_db,
                       input_reference_sha=args.input_reference_sha)
    except (BISAdmissionHold, ValueError, OSError, sqlite3.Error,
            UnicodeError, TypeError) as exc:
        raise SystemExit("HOLD: BIS scratch metadata admission: " + str(exc))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
