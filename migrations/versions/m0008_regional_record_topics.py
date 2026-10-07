"""0008 — add an empty cross-desk regional topic assignment store.

This migration adds schema only. It creates no topic assignment and changes no
existing article, category, source, or analysis row. The same table definition
is exposed through core.topics.ensure_topic_store() so a shadow SQLite state
database can opt into the identical attachment contract without becoming part
of the production corpus.
"""

from __future__ import annotations

import sqlite3

from core.topics import ensure_topic_store


VERSION = "0008"
NAME = "regional_record_topics"

_TABLE = "record_topics"
_REQUIRED_COLUMNS = {
    "desk_id",
    "source_slug",
    "record_url",
    "topic_slug",
    "taxonomy_version",
    "assignment_method",
    "assigned_by",
    "assigned_at",
    "confidence",
    "evidence",
}


def _columns(conn: sqlite3.Connection) -> set:
    return {row[1] for row in conn.execute("PRAGMA table_info(%s)" % _TABLE)}


def _table_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (_TABLE,),
    ).fetchone() is not None


def is_already_applied(conn: sqlite3.Connection) -> bool:
    return _table_exists(conn) and _REQUIRED_COLUMNS.issubset(_columns(conn))


def up(conn: sqlite3.Connection) -> None:
    if _table_exists(conn):
        missing = _REQUIRED_COLUMNS - _columns(conn)
        if missing:
            raise sqlite3.IntegrityError(
                "partial record_topics table is missing columns: %s" %
                ", ".join(sorted(missing))
            )
    ensure_topic_store(conn)
