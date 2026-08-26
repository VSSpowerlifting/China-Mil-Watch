"""
0006 — record how many parsed documents carried no usable text.

The defect this closes: `source_run_results.extracted` counts documents the
parser returned a structure for, not documents that yielded text. A page that
is reachable and parseable but empty was indistinguishable from one that was
read in full, and the Coverage page rendered that count under the heading
"Read". The corpus holds 44 records with a complete title, canonical URL,
publication date and content hash beside a zero-character body — real items
whose text was never captured, reported as read.

`extracted` keeps its meaning. Redefining it would rewrite what every stored
row claims, and a historical row cannot be re-measured. Instead this adds the
missing half of the fact.

WHY THE COLUMN IS NULLABLE WITH NO DEFAULT
------------------------------------------
`NOT NULL DEFAULT 0` would be the conventional shape and it would be a lie.
Every row written before this migration observed nothing about usable text;
stamping 0 on them asserts that every one of those runs read every document it
parsed, which is measurably false — those 44 records came from those runs. NULL
says "not measured", the readers below render it as such, and no historical run
is assigned a completeness it never demonstrated.

The cause of each historical empty body is likewise NOT backfilled. Nothing
stored distinguishes source markup drift from a paywall, a JavaScript shell or
a transient truncation, and the raw HTML was never retained. An inferred cause
would be a guess wearing the costume of a record.
"""

from __future__ import annotations

import sqlite3

VERSION = "0006"
NAME = "source_run_text_unavailable"

_COLUMN = "text_unavailable"
_TABLE = "source_run_results"


def _columns(conn: sqlite3.Connection) -> set:
    return {row[1] for row in conn.execute("PRAGMA table_info(%s)" % _TABLE)}


def _table_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_TABLE,)
    ).fetchone() is not None


def is_already_applied(conn: sqlite3.Connection) -> bool:
    """
    True when the column is present — or when the table does not exist at all.

    Migration 0004 creates `source_run_results`, so on any database that has
    run the full chain the table is there. Treating an absent table as "already
    applied" keeps this migration a no-op on a database that legitimately
    predates 0004, rather than failing the whole run on a table it does not own.
    """
    if not _table_exists(conn):
        return True
    return _COLUMN in _columns(conn)


def up(conn: sqlite3.Connection) -> None:
    """
    Add the column, once, and write nothing else.

    Deliberately performs no UPDATE. `ALTER TABLE ... ADD COLUMN` with no
    default leaves every existing row NULL, which is the honest value, and it
    means this migration touches no row data at all — so a database that has
    already been migrated stays byte-identical when the runner re-checks it.
    """
    if not _table_exists(conn):
        return
    if _COLUMN in _columns(conn):
        return
    conn.execute(
        "ALTER TABLE %s ADD COLUMN %s INTEGER" % (_TABLE, _COLUMN)
    )
