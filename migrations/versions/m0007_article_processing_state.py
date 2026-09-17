"""
0007 — give a record that cannot be analyzed somewhere to say so.

The defect this closes: there is no terminal processing state. The analysis
queue is built from two queries in `storage/db.py` —

    passed_relevance = 1 AND analyzed_at IS NULL     (pending)
    passed_relevance IS NULL                         (unscored)

— and neither has any way to exclude a record that will never succeed. A record
that passed relevance on a title and holds no body can never produce a
translation, so it re-enters the queue on every run, for ever. Measured
2026-09-16 on the tracked corpus: article 2678 had been retried on **28
separate runs**, and five records were in that state together.

Retrying costs a model call each time and crowds the reserved backlog slots
that real material needs, so the cost is not only untidiness.

WHAT IS AND IS NOT DECIDED HERE
-------------------------------
This migration adds columns and writes no row. It does **not** disposition any
existing record: classifying the current backlog is a judgement about specific
documents and belongs to a run that is allowed to touch production data, not to
a schema change. Every existing row is left NULL, which is the honest value —
those records have failed many times, but nothing observed and stored their
attempt count, so inventing one would be a guess wearing the costume of a
record (the same reasoning as 0006).

WHY NULLABLE WITH NO DEFAULT
----------------------------
`NOT NULL DEFAULT 0` on `processing_attempts` would assert that every record in
the corpus has been attempted zero times, which is measurably false for the
seven that fail on every run. NULL says "not measured". A record only acquires
a state and an attempt count once this code actually observes a failure.

THE COLUMNS
-----------
    processing_state           NULL | 'retriable' | 'terminal'
    processing_attempts        how many times analysis has been observed to fail
    processing_reason          why, from core.processing_state.REASONS
    processing_first_failed_at ISO-8601 UTC of the first observed failure
    processing_last_failed_at  ISO-8601 UTC of the most recent one

`processing_reason` and both timestamps exist so a terminal record keeps its
history. A record that stops being retried without recording why it stopped has
been silently dropped, which is the outcome this project refuses everywhere
else.
"""

from __future__ import annotations

import sqlite3

VERSION = "0007"
NAME = "article_processing_state"

_TABLE = "articles"
_COLUMNS = (
    ("processing_state",           "TEXT"),
    ("processing_attempts",        "INTEGER"),
    ("processing_reason",          "TEXT"),
    ("processing_first_failed_at", "TEXT"),
    ("processing_last_failed_at",  "TEXT"),
)


def _columns(conn: sqlite3.Connection) -> set:
    return {row[1] for row in conn.execute("PRAGMA table_info(%s)" % _TABLE)}


def _table_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_TABLE,)
    ).fetchone() is not None


def is_already_applied(conn: sqlite3.Connection) -> bool:
    """
    True when every column is present — or when the table does not exist.

    An absent `articles` table means a database this migration does not own, so
    it reports itself applied rather than failing the whole chain.
    """
    if not _table_exists(conn):
        return True
    present = _columns(conn)
    return all(name in present for name, _ in _COLUMNS)


def up(conn: sqlite3.Connection) -> None:
    """
    Add the columns, once, and write no row data.

    Each `ALTER TABLE ... ADD COLUMN` carries no default, so every existing row
    is left NULL and the migration touches no row at all. A database that has
    already been migrated stays byte-identical when the runner re-checks it.
    """
    if not _table_exists(conn):
        return
    present = _columns(conn)
    for name, sql_type in _COLUMNS:
        if name in present:
            continue
        conn.execute(
            "ALTER TABLE %s ADD COLUMN %s %s" % (_TABLE, name, sql_type)
        )
