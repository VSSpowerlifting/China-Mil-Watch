#!/usr/bin/env python3
"""Relax the scrape_runs.status CHECK to allow 'degraded'.

Background (2026-08-09). `complete_scrape_run()` was always called without a
`status` argument, so every run closed as 'completed' — including 2026-08-07,
which exhausted the API credit balance mid-run, analyzed 24 of 36 articles and
then aborted. The audit log could not distinguish that from a clean day, so the
outage went unnoticed for two days.

pipeline.py now reports an honest status, which needs a fourth allowed value.
SQLite cannot ALTER a CHECK constraint, so the table is rebuilt in place
following the official "Making Other Kinds Of Table Schema Changes" procedure.

Idempotent: re-running after a successful migration is a no-op. Safe to run on
a database that is already correct, and safe to re-run after an interruption
(the rebuild is wrapped in a single transaction).

Usage:
    .venv/bin/python scripts/migrate_status_degraded.py [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "pla_watch.db"

# Must stay byte-identical to the scrape_runs definition in storage/schema.sql,
# minus the IF NOT EXISTS clause. If you change one, change the other.
NEW_TABLE_SQL = """
CREATE TABLE scrape_runs_migrated (
    id                INTEGER PRIMARY KEY,
    started_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at      TEXT,
    articles_scraped  INTEGER NOT NULL DEFAULT 0,
    articles_new      INTEGER NOT NULL DEFAULT 0,
    articles_analyzed INTEGER NOT NULL DEFAULT 0,
    errors            TEXT,
    status            TEXT    NOT NULL DEFAULT 'running'
                              CHECK (status IN ('running', 'completed',
                                                'degraded', 'failed'))
)
"""

COLUMNS = (
    "id, started_at, completed_at, articles_scraped, "
    "articles_new, articles_analyzed, errors, status"
)


def current_schema(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='scrape_runs'"
    ).fetchone()
    if row is None:
        sys.exit("ERROR: no scrape_runs table found — is this the right database?")
    return row[0]


def migrate(db_path: Path, dry_run: bool) -> int:
    if not db_path.exists():
        sys.exit(f"ERROR: database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        existing = current_schema(conn)

        if "'degraded'" in existing:
            print(f"Already migrated — scrape_runs.status accepts 'degraded'.\n  {db_path}")
            return 0

        before = conn.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0]
        print(f"Database : {db_path}")
        print(f"Rows     : {before} scrape_runs")
        print("Change   : status CHECK gains 'degraded'")

        if dry_run:
            print("\n--dry-run: no changes written.")
            return 0

        # The official rebuild procedure. legacy_alter_table keeps the final
        # RENAME from rewriting references in other tables' schemas; only
        # articles.scrape_run_id points here and it must keep pointing at the
        # name 'scrape_runs', which is exactly what we rename back to.
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA legacy_alter_table=ON")
        try:
            conn.execute("BEGIN")
            conn.execute(NEW_TABLE_SQL)
            conn.execute(
                f"INSERT INTO scrape_runs_migrated ({COLUMNS}) "
                f"SELECT {COLUMNS} FROM scrape_runs"
            )
            conn.execute("DROP TABLE scrape_runs")
            conn.execute("ALTER TABLE scrape_runs_migrated RENAME TO scrape_runs")

            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                conn.execute("ROLLBACK")
                sys.exit(f"ERROR: foreign key check failed, rolled back: {violations}")

            after = conn.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0]
            if after != before:
                conn.execute("ROLLBACK")
                sys.exit(
                    f"ERROR: row count changed ({before} → {after}), rolled back."
                )

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys=ON")

        # Prove the new constraint actually took, then roll the probe back.
        conn.execute("BEGIN")
        conn.execute("INSERT INTO scrape_runs (status) VALUES ('degraded')")
        conn.execute("ROLLBACK")

        print(f"\nMigrated. {after} rows preserved; 'degraded' accepted.")
        return 0
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return migrate(args.db, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
