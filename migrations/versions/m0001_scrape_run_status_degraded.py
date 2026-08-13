"""
0001 — allow 'degraded' as a scrape_runs.status.

This change already exists in production: it was applied by hand on 2026-08-09,
silently reverted by a rebase (DECISION_LOG 2026-08-09 §7), found reverted again
during the Phase 0 audit, and re-applied via
`scripts/migrate_status_degraded.py` before this framework existed.

It is restated here as migration 0001 so that the reversion cannot recur
unnoticed: any database this framework touches now either has the constraint or
gets it, and `schema_migrations` records which. The standalone script remains
valid and produces an identical result; it is now the manual escape hatch rather
than the only mechanism.
"""

from __future__ import annotations

import sqlite3

VERSION = "0001"
NAME = "scrape_run_status_degraded"

_NEW_TABLE = """
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

_COLUMNS = (
    "id, started_at, completed_at, articles_scraped, "
    "articles_new, articles_analyzed, errors, status"
)


def is_already_applied(conn: sqlite3.Connection) -> bool:
    """
    Behavioural check, not a substring search.

    Previously this asked whether the literal `'degraded'` appeared anywhere in
    the table's stored SQL, which a comment mentioning the word would satisfy
    just as well as a constraint permitting it. Instead, probe the constraint the
    way the pipeline will: attempt the write and roll it back.
    """
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='scrape_runs'"
    ).fetchone()
    if row is None:
        return False

    savepoint = "probe_degraded_status"
    conn.execute("SAVEPOINT %s" % savepoint)
    try:
        conn.execute("INSERT INTO scrape_runs (status) VALUES ('degraded')")
        return True           # accepted → already supported
    except sqlite3.IntegrityError:
        return False          # rejected → migration still needed
    finally:
        conn.execute("ROLLBACK TO %s" % savepoint)
        conn.execute("RELEASE %s" % savepoint)


def up(conn: sqlite3.Connection) -> None:
    before = conn.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0]

    # legacy_alter_table keeps the final RENAME from rewriting the reference in
    # articles' schema: articles.scrape_run_id must keep pointing at the name
    # 'scrape_runs', which is exactly what we rename back to.
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute(_NEW_TABLE)
        conn.execute(
            "INSERT INTO scrape_runs_migrated (%s) SELECT %s FROM scrape_runs"
            % (_COLUMNS, _COLUMNS)
        )
        conn.execute("DROP TABLE scrape_runs")
        conn.execute("ALTER TABLE scrape_runs_migrated RENAME TO scrape_runs")
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")

    after = conn.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0]
    if after != before:
        raise RuntimeError(
            "scrape_runs row count changed during rebuild (%d -> %d)"
            % (before, after)
        )
