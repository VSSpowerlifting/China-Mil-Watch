"""Exact-URL SHA-256 retirement guard for active corpus ingest.

The canonical source URL that was stored originally is hashed byte-for-byte.
There is no case folding, URL rebuilding, source-status inference or political
content classification. This guard only acts on explicitly retired URL hashes
already committed to the database's retirement ledger.

Old test/scratch DBs without migration 0008 have no retirements and remain
usable. Production daily collection applies/verifies migrations before ingest;
the release must separately prove the ledger survives any DB reconciliation.
"""
from hashlib import sha256
import sqlite3


def url_sha256(url: str) -> str:
    if not isinstance(url, str) or not url:
        raise ValueError("retirement lookup needs the exact nonempty stored URL")
    return sha256(url.encode("utf-8")).hexdigest()


def has_retired_table(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type='table' AND name='retired_article_urls'"
    ).fetchone() is not None


def is_retired(conn: sqlite3.Connection, url: str) -> bool:
    digest = url_sha256(url)
    # Legacy tests and pre-migration scratch copies have no rows to check.
    # All production callers migrate before collecting; an existing malformed
    # ledger must raise rather than be treated as no retirements.
    if not has_retired_table(conn):
        return False
    return conn.execute(
        "SELECT 1 FROM retired_article_urls WHERE url_sha256=?",
        (digest,)
    ).fetchone() is not None


def next_available_article_id(conn: sqlite3.Connection) -> int:
    """Never give a new source the identity of an already retired public page.

    SQLite INTEGER PRIMARY KEY without AUTOINCREMENT otherwise chooses
    MAX(active id)+1 and can reuse a deleted former maximum row.
    """
    live_max = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM articles"
    ).fetchone()[0]
    retired_max = (conn.execute(
        "SELECT COALESCE(MAX(original_article_id), 0) FROM retired_article_urls"
    ).fetchone()[0] if has_retired_table(conn) else 0)
    return max(live_max, retired_max) + 1


def verify_no_active_retired_urls(conn: sqlite3.Connection) -> int:
    """Return ledger size or fail on any accidentally resurrected active URL."""
    if not has_retired_table(conn):
        raise ValueError("retired URL ledger missing; migration 0008 required")
    if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='trigger' "
            "AND name='guard_retired_article_id_reuse'"
    ).fetchone() is None:
        raise ValueError("retired article ID protection trigger missing")
    hashes = {row[0] for row in conn.execute(
        "SELECT url_sha256 FROM retired_article_urls"
    )}
    if len(hashes) != conn.execute(
            "SELECT COUNT(*) FROM retired_article_urls").fetchone()[0]:
        raise ValueError("duplicate retirement ledger identities")
    former_ids = {row[0] for row in conn.execute(
        "SELECT original_article_id FROM retired_article_urls"
    )}
    for ident, url in conn.execute("SELECT id, url FROM articles"):
        if ident in former_ids:
            raise ValueError("retired article ID reused by an active record")
        if url_sha256(url) in hashes:
            raise ValueError("retired URL found inside active articles")
    return len(hashes)
