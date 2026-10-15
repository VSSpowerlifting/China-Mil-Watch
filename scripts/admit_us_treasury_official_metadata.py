"""Admit preserved Treasury first-party metadata into isolated live SQLite tables.

Requires an explicit standing-approval flag; publishing is a separate workflow.
Do not ingest publisher headlines, source bodies, attachments or models.
"""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
import subprocess
from pathlib import Path
from core.us_treasury_official_metadata import admit, TreasuryAdmissionHold

def run(source_checkout, production_db):
    source_checkout = Path(source_checkout).resolve(strict=True)
    production_db = Path(production_db).resolve(strict=True)
    sha = subprocess.check_output(
        ["git", "-C", str(source_checkout), "rev-parse", "HEAD"], text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise TreasuryAdmissionHold("unverifiable_source_commit")
    observation_dir = source_checkout / "observations"
    paths = sorted(observation_dir.glob("*.json"))
    if not paths or len(paths) > 5000:
        raise TreasuryAdmissionHold("missing_or_excessive_source_history")
    with sqlite3.connect(str(production_db)) as con:
        con.execute("PRAGMA journal_mode=DELETE")
        con.execute("BEGIN IMMEDIATE")
        newly = 0
        for path in paths:
            if path.is_symlink() or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\.json", path.name) or path.stat().st_size > 120000:
                raise TreasuryAdmissionHold("invalid_observation_file")
            packet = json.loads(path.read_text(encoding="utf-8"))
            newly += admit(con, packet, receipt_day=path.stem, source_sha=sha)
        if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise TreasuryAdmissionHold("database_integrity_hold")
    return {"source_commit_sha":sha, "observations":len(paths),
            "new_official_metadata_records":newly,
            "source_bodies_copied":False, "publisher_titles_copied":False}

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-checkout",required=True)
    parser.add_argument("--production-db",required=True)
    parser.add_argument("--standing-official-links-approval",action="store_true")
    args = parser.parse_args(argv)
    if not args.standing_official_links_approval:
        raise SystemExit("HOLD: missing standing metadata-only owner approval")
    try:
        print(json.dumps(run(args.source_checkout,args.production_db),sort_keys=True))
    except (TreasuryAdmissionHold, ValueError, OSError, sqlite3.Error,
            subprocess.CalledProcessError) as exc:
        raise SystemExit("HOLD: Treasury source admission failed: " + str(exc))

if __name__ == "__main__":
    main()
