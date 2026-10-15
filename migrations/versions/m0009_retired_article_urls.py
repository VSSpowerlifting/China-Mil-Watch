"""0009 — retain article URL identity after active-corpus retirement.

Creates an empty ledger, without writing or retiring any existing article.
Populating it is a separate, reviewed, atomic database release. The original
article row is intentionally NOT referenced: the row may be permanently
retired from the active publication while its URL SHA-256 remains.
"""
import sqlite3

VERSION = "0009"
NAME = "retired_article_urls"

DDL = """
CREATE TABLE IF NOT EXISTS retired_article_urls (
    url_sha256         TEXT PRIMARY KEY NOT NULL
                       CHECK(length(url_sha256) = 64
                         AND url_sha256 NOT GLOB '*[^0-9a-f]*'),
    original_article_id INTEGER NOT NULL UNIQUE CHECK(original_article_id > 0),
    source_slug       TEXT NOT NULL,
    retired_at        TEXT NOT NULL,
    selection_sha256  TEXT NOT NULL CHECK(length(selection_sha256) = 64)
)
"""


TRIGGER_DDL = """
CREATE TRIGGER IF NOT EXISTS guard_retired_article_id_reuse
BEFORE INSERT ON articles
WHEN EXISTS (
  SELECT 1 FROM retired_article_urls WHERE original_article_id = NEW.id
)
BEGIN
  SELECT RAISE(ABORT, 'retired article ID must not be reused');
END
"""


def is_already_applied(conn: sqlite3.Connection) -> bool:
    return (conn.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type='table' AND name='retired_article_urls'"
    ).fetchone() is not None and conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='trigger' "
        "AND name='guard_retired_article_id_reuse'"
    ).fetchone() is not None)


def up(conn: sqlite3.Connection) -> None:
    # Empty on purpose: creating this table never makes a retention decision.
    conn.execute(DDL)
    conn.execute(TRIGGER_DDL)
