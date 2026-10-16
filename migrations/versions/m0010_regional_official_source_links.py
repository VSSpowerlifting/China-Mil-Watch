"""0010 — empty, metadata-only source-link index for AFP and Kemhan.

Creates no record and grants no right to publish. Explicit independent source
review, real scheduled Actions lineage and controlled Pages release remain
required by the separate application writer. NEVER migrate shadow article
bodies, title text, captures, images or editorial output here.

This module intentionally does not import the held/release branch: migrations
must remain independently replayable if the application code is not yet merged.
"""
from __future__ import annotations

import sqlite3

VERSION = "0010"
NAME = "regional_official_source_links"
TABLE = "regional_official_source_links"
INDEX = "idx_regional_official_source_family_day"
COLUMNS = frozenset((
    "source_family", "source_identity", "desk", "canonical_official_url",
    "publisher_posted_date", "official_issuer", "official_publisher",
    "official_republisher", "source_git_commit", "metadata_version_sha256",
    "first_seen_run", "release_scope", "release_proof_sha256",
    "released_at_utc",
))

DDL = """
CREATE TABLE IF NOT EXISTS regional_official_source_links (
    source_family TEXT NOT NULL
        CHECK (source_family IN ('ph_afp_articles', 'id_kemhan_news')),
    source_identity TEXT NOT NULL CHECK (length(source_identity) > 0),
    desk TEXT NOT NULL CHECK (
        (source_family='ph_afp_articles' AND desk='philippines') OR
        (source_family='id_kemhan_news' AND desk='indonesia')
    ),
    canonical_official_url TEXT NOT NULL UNIQUE CHECK (
        (source_family='ph_afp_articles'
         AND canonical_official_url GLOB 'https://www.afp.mil.ph/news/*') OR
        (source_family='id_kemhan_news'
         AND canonical_official_url GLOB 'https://www.kemhan.go.id/*')
    ),
    publisher_posted_date TEXT NOT NULL CHECK (
        publisher_posted_date GLOB
        '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]'
    ),
    official_issuer TEXT,
    official_publisher TEXT NOT NULL CHECK (
        (source_family='ph_afp_articles'
         AND official_issuer='ph_afp' AND official_publisher='ph_afp') OR
        (source_family='id_kemhan_news'
         AND official_issuer IS NULL AND official_publisher='id_kemhan')
    ),
    official_republisher TEXT CHECK (official_republisher IS NULL),
    source_git_commit TEXT NOT NULL
        CHECK(length(source_git_commit)=40
              AND source_git_commit NOT GLOB '*[^0-9a-f]*'),
    metadata_version_sha256 TEXT NOT NULL
        CHECK(length(metadata_version_sha256)=64
              AND metadata_version_sha256 NOT GLOB '*[^0-9a-f]*'),
    first_seen_run TEXT NOT NULL CHECK(length(first_seen_run)>0),
    release_scope TEXT NOT NULL CHECK(release_scope='official_link_only'),
    release_proof_sha256 TEXT NOT NULL
        CHECK(length(release_proof_sha256)=64
              AND release_proof_sha256 NOT GLOB '*[^0-9a-f]*'),
    released_at_utc TEXT NOT NULL,
    PRIMARY KEY(source_family, source_identity)
)
"""
INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_regional_official_source_family_day
ON regional_official_source_links (
    source_family, publisher_posted_date DESC, source_identity
)
"""


def _columns(conn: sqlite3.Connection):
    found = conn.execute(
        "SELECT type FROM sqlite_master WHERE name=?", (TABLE,)
    ).fetchone()
    if found is None:
        return None
    if found[0] != "table":
        raise ValueError("regional source index name occupied by non-table")
    return {row[1] for row in conn.execute("PRAGMA table_info(%s)" % TABLE)}


def _has_index(conn: sqlite3.Connection):
    row = conn.execute(
        "SELECT type, tbl_name FROM sqlite_master WHERE name=?",
        (INDEX,)
    ).fetchone()
    return row is not None and tuple(row) == ("index", TABLE)


def is_already_applied(conn: sqlite3.Connection) -> bool:
    cols = _columns(conn)
    if cols is None:
        return False
    if cols != COLUMNS:
        raise ValueError("regional source index schema drift requires review")
    return _has_index(conn)


def up(conn: sqlite3.Connection) -> None:
    cols = _columns(conn)
    if cols is not None and cols != COLUMNS:
        raise ValueError("regional source index schema drift requires review")
    conn.execute(DDL)
    conn.execute(INDEX_DDL)
    if _columns(conn) != COLUMNS or not _has_index(conn):
        raise ValueError("regional source index migration incomplete")
