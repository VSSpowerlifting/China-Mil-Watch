"""
0002 — desks and institutions.

Purely additive: two new tables, nothing existing touched. Rows are populated
from `desks/*/manifest.json` by the config sync that runs after migrations, not
here, so that a manifest correction reaches the database on the next run instead
of requiring a new migration.
"""

from __future__ import annotations

import sqlite3

VERSION = "0002"
NAME = "desks_and_institutions"

_DESKS = """
CREATE TABLE IF NOT EXISTS desks (
    desk_id                 TEXT PRIMARY KEY,
    display_name            TEXT NOT NULL,
    jurisdiction_code       TEXT NOT NULL,
    default_timezone        TEXT NOT NULL,
    default_calendar        TEXT NOT NULL DEFAULT 'gregorian',
    -- JSON array of BCP 47 tags. A JSON column rather than a child table:
    -- it is read whole, never joined against, and never filtered on.
    supported_language_tags TEXT NOT NULL,
    active                  INTEGER NOT NULL DEFAULT 1,
    -- legacy = already published under its own brand (the China desk today)
    -- shadow = private collection, no public surface (the Russia pilot's state)
    -- public = published as part of the parent platform
    -- paused = configuration retained, collection stopped
    public_status           TEXT NOT NULL DEFAULT 'shadow'
                            CHECK (public_status IN
                                   ('legacy', 'shadow', 'public', 'paused')),
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_INSTITUTIONS = """
CREATE TABLE IF NOT EXISTS institutions (
    institution_id        TEXT PRIMARY KEY,
    desk_id               TEXT NOT NULL REFERENCES desks(desk_id),
    display_name          TEXT NOT NULL,
    name_original         TEXT,
    institution_type      TEXT NOT NULL,
    parent_institution_id TEXT REFERENCES institutions(institution_id),
    active_from           TEXT,
    active_to             TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_institutions_desk ON institutions(desk_id)",
)


def is_already_applied(conn: sqlite3.Connection) -> bool:
    names = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('desks', 'institutions')"
        )
    }
    return names == {"desks", "institutions"}


def up(conn: sqlite3.Connection) -> None:
    conn.execute(_DESKS)
    conn.execute(_INSTITUTIONS)
    for stmt in _INDEXES:
        conn.execute(stmt)
