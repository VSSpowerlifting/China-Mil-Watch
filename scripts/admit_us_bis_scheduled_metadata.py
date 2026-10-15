"""BIS metadata-only candidate importer: SOURCE AUTHENTICATION MUST PRECEDE SQL.

This CLI is inert unless explicitly passed owner-approved metadata-only scope,
authenticated Actions JSON and the exact verified Git shadow head. Its caller
must fetch those inputs independently via GitHub REST; never from shadow Git.
Not wired into any production or scheduled release workflow by this PR.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import subprocess
from pathlib import Path
from core.us_bis_authenticated_metadata import (
    BISLiveAdmissionHold, admit_attested, load_public_links)
from scripts.attest_us_bis_scheduled_receipt import attest, BISAttestationHold

def run(source_checkout, run_json, production_db, *, expected_remote_head):
    state = Path(source_checkout).resolve(strict=True)
    meta = Path(run_json)
    db_input = Path(production_db)
    if not meta.is_file() or meta.is_symlink() or meta.stat().st_size > 160000:
        raise BISLiveAdmissionHold("source_run_json_untrusted")
    if db_input.is_symlink():
        raise BISLiveAdmissionHold("database_symlink_not_allowed")
    db = db_input.resolve(strict=True)
    run_data = json.loads(meta.read_text(encoding="utf-8"))
    proof = attest(state, run_data, expected_remote_head=expected_remote_head)
    day, commit = proof["receipt_day"], proof["source_commit"]
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(state), "show",
             commit + ":observations/" + day + ".json"],
            stderr=subprocess.DEVNULL, timeout=15)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        raise BISLiveAdmissionHold("attested_receipt_unreadable") from None
    if not raw or len(raw) > 120000:
        raise BISLiveAdmissionHold("attested_receipt_unbounded")
    packet = json.loads(raw)
    # Authenticity and packet integrity were verified *before* DB connection.
    with sqlite3.connect(str(db)) as con:
        con.execute("PRAGMA journal_mode=DELETE")
        con.execute("BEGIN IMMEDIATE")
        added = admit_attested(con, packet, proof)
        if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise BISLiveAdmissionHold("sqlite_integrity_hold")
    rows = load_public_links(db)
    saved_ids = {row["source_identity"] for row in rows}
    if not all(row["source_identity"] in saved_ids for row in packet["rows"]):
        raise BISLiveAdmissionHold("attested_source_readback_missing")
    return {
        "status":"ATTESTED_BIS_METADATA_SQLITE_ADMITTED",
        "source_run_id":proof["source_run_id"],
        "source_commit":commit,"source_day":day,
        "new_metadata_rows":added,
        "total_bis_official_links":len(rows),
        "original_source_articles_written":0,
        "public_site_published":False,
    }

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-checkout",required=True)
    parser.add_argument("--authenticated-run-json",required=True)
    parser.add_argument("--expected-remote-head",required=True)
    parser.add_argument("--database",required=True)
    parser.add_argument("--standing-official-url-date-issuer-approval",
                        action="store_true")
    args=parser.parse_args(argv)
    if not args.standing_official_url_date_issuer_approval:
        raise SystemExit("HOLD: no standing metadata-only owner approval")
    try:
        print(json.dumps(run(args.source_checkout,args.authenticated_run_json,
                             args.database,
                             expected_remote_head=args.expected_remote_head),
                         sort_keys=True))
    except (BISLiveAdmissionHold,BISAttestationHold,ValueError,OSError,
            sqlite3.Error,TypeError,UnicodeError) as exc:
        raise SystemExit("HOLD: BIS metadata-only admission: " + str(exc))

if __name__=="__main__":
    main()
