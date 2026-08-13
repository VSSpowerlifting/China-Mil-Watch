"""
0003 — additive source metadata.

Adds desk, institution, authority, genre-adjacent and cadence columns to
`sources` with ALTER TABLE ADD COLUMN, which SQLite performs without rewriting
the table and without touching existing values.

Deliberately NOT done here:

  * **No column is dropped or renamed.** `sources.language` ('zh'/'en') and
    `sources.is_active` stay exactly as they are and keep being written by the
    existing code. `language_tag` and `enabled` are added alongside them, and
    `storage/db.py` gains accessors that read the new column and fall back to
    the legacy one. Removing the legacy columns is a later, separately approved
    cleanup — deprecating in documentation first is the whole point.

  * **No CHECK constraint on the new columns.** Adding one would require a table
    rebuild, which would rewrite `sources.id` handling and put the article
    foreign key at risk for no benefit: these values are validated at the
    manifest boundary by core/manifests.py, which produces a far better error
    message than a CHECK violation ever could.
"""

from __future__ import annotations

import sqlite3

VERSION = "0003"
NAME = "sources_desk_metadata"

# (column, type) — appended in this order.
NEW_COLUMNS = (
    ("desk_id",               "TEXT"),
    ("institution_id",        "TEXT"),
    ("language_tag",          "TEXT"),
    ("timezone",              "TEXT"),
    ("calendar",              "TEXT"),
    ("authority_tier",        "TEXT"),
    ("source_type",           "TEXT"),
    ("originality",           "TEXT"),
    ("expected_cadence_days", "REAL"),
    ("silence_threshold_days", "INTEGER"),
    ("access_method",         "TEXT"),
    ("enabled",               "INTEGER"),
    ("active_from",           "TEXT"),
    ("active_to",             "TEXT"),
    ("listing_endpoints",     "TEXT"),   # JSON array
    ("article_url_patterns",  "TEXT"),   # JSON array
    ("notes",                 "TEXT"),
)


def _existing_columns(conn: sqlite3.Connection):
    return {r[1] for r in conn.execute("PRAGMA table_info(sources)")}


def is_already_applied(conn: sqlite3.Connection) -> bool:
    have = _existing_columns(conn)
    return all(name in have for name, _ in NEW_COLUMNS)


def up(conn: sqlite3.Connection) -> None:
    have = _existing_columns(conn)
    for name, coltype in NEW_COLUMNS:
        if name in have:
            continue          # partial prior application; keep going
        conn.execute("ALTER TABLE sources ADD COLUMN %s %s" % (name, coltype))

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sources_desk ON sources(desk_id)"
    )
