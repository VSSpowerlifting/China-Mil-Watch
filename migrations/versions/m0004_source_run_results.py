"""
0004 — per-source collection results.

The defect this closes: `scrape_runs` records one aggregate row per run, so
"PLA Daily published 34 articles and MOD China could not be reached" and
"PLA Daily published 34 articles and MOD China published nothing" are the same
row. MOD China went silent for four weeks without a single failed run because
PLA Daily supplies ~87% of the corpus and the totals never moved
(DECISION_LOG 2026-08-09 §5).

One row per (run, source), so every run can answer per source: how many
references were discovered, fetched, extracted, deduplicated, kept, rejected —
and if none, whether that was silence or failure.
"""

from __future__ import annotations

import sqlite3

VERSION = "0004"
NAME = "source_run_results"

_TABLE = """
CREATE TABLE IF NOT EXISTS source_run_results (
    id                    INTEGER PRIMARY KEY,
    scrape_run_id         INTEGER NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
    source_slug           TEXT    NOT NULL,
    desk_id               TEXT,

    -- The structured outcome. Mirrors core.collection.status.CollectionStatus;
    -- see docs/COLLECTION_HEALTH.md for what each value means and, crucially,
    -- which ones are success and which are failure.
    status                TEXT    NOT NULL,
    -- True when this source's outcome should degrade the aggregate run.
    -- Stored rather than derived so a later change to the status vocabulary
    -- cannot retroactively rewrite what an old run reported.
    is_failure            INTEGER NOT NULL DEFAULT 0,

    started_at            TEXT,
    completed_at          TEXT,

    references_discovered INTEGER NOT NULL DEFAULT 0,
    fetched               INTEGER NOT NULL DEFAULT 0,
    extracted             INTEGER NOT NULL DEFAULT 0,
    duplicates            INTEGER NOT NULL DEFAULT 0,
    new_documents         INTEGER NOT NULL DEFAULT 0,
    relevance_rejected    INTEGER NOT NULL DEFAULT 0,

    failed_fetches        INTEGER NOT NULL DEFAULT 0,
    error_detail          TEXT,

    -- One (run, source) result. A second write for the same pair is an upsert,
    -- not a duplicate row: a source is collected once per run.
    UNIQUE (scrape_run_id, source_slug)
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_srr_run ON source_run_results(scrape_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_srr_source ON source_run_results(source_slug)",
)


def is_already_applied(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_run_results'"
    ).fetchone() is not None


def up(conn: sqlite3.Connection) -> None:
    conn.execute(_TABLE)
    for stmt in _INDEXES:
        conn.execute(stmt)
