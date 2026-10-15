"""Admit source-reverified Korea MND URL/date/issuer metadata into live SQLite.

Requires an already collected, clean Git checkout of the Korea shadow branch.
NEVER downloads Korean publisher originals, copies titles/bodies/media, uses an
LLM, signs editorial reviews, sends email or publishes a broad site tree.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from core import korea_official_metadata_admission as admission
from migrations.runner import apply_all
from scripts import stage_korea_production_candidates as stage


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-checkout", required=True)
    p.add_argument("--production-db", required=True)
    p.add_argument("--standing-official-links-approval", action="store_true")
    args = p.parse_args(argv)
    try:
        if not args.standing_official_links_approval:
            raise admission.MetadataHold("explicit_standing_policy_flag_missing")
        db = Path(args.production_db).expanduser().resolve(strict=True)
        if db != admission.ROOT / "pla_watch.db" or db.is_symlink():
            raise admission.MetadataHold("only_canonical_production_database_allowed")
        policy = admission.read_policy()
        # Expensive original HWPX/HTML/text + clean Git ancestry verification
        # happens BEFORE any live SQLite connection or schema mutation.
        verified = stage.build(args.source_checkout)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with sqlite3.connect(str(db)) as conn:
            apply_all(conn, sync_config=False)
            receipt = admission.admit(conn, verified, policy, as_of_utc=now)
            conn.commit()
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise admission.MetadataHold("production_sqlite_integrity_failed")
            # Git-tracked DB cannot retain untracked WAL sidecars.
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("PRAGMA journal_mode=DELETE")
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except (admission.MetadataHold, stage.IntakeHold, sqlite3.Error,
            OSError, ValueError) as exc:
        reason = (str(exc) if isinstance(
            exc, (admission.MetadataHold, stage.IntakeHold))
            else "korea_source_or_database_unavailable")
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "original_title_or_body_published": False,
                          "website_updated": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
