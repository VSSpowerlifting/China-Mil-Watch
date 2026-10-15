"""0008 — typed metadata-only Korea reference records in the live SQLite DB.

This table is NOT a second articles table and carries no Korean body, original
title, image, translation, AI output or claim. Source collection, exact-version
review, and website release are separate authorities. The migration writes ZERO
rows and never turns shadow collection into publication by itself.

An auto-updating Korea Desk can use this source-bound table after an explicitly
approved ingestion and publishing workflow exists. Until then it is empty.
"""
from __future__ import annotations

import sqlite3

VERSION = "0008"
NAME = "korea_official_source_metadata"

TABLE = "korea_official_source_records"

SCHEMA = """
CREATE TABLE IF NOT EXISTS korea_official_source_records (
    source_identity TEXT PRIMARY KEY NOT NULL,
    canonical_official_url TEXT NOT NULL UNIQUE,
    publisher_posted_date TEXT NOT NULL,
    source_git_commit TEXT NOT NULL,
    source_db_sha256 TEXT NOT NULL,
    candidate_version_sha256 TEXT NOT NULL,
    original_title_sha256 TEXT NOT NULL,
    original_text_sha256 TEXT NOT NULL,
    publisher_html_sha256 TEXT NOT NULL,
    original_hwpx_sha256 TEXT NOT NULL,
    official_issuer TEXT NOT NULL
        CHECK (official_issuer = 'kr_mnd'),
    official_republisher TEXT NOT NULL
        CHECK (official_republisher = 'kr_policy_briefing'),
    source_language TEXT NOT NULL
        CHECK (source_language = 'ko'),
    authority_tier TEXT NOT NULL
        CHECK (authority_tier = 'B'),
    originality TEXT NOT NULL
        CHECK (originality = 'syndicated'),
    public_scope TEXT NOT NULL DEFAULT 'held'
        CHECK (public_scope IN ('held', 'official_link_only')),
    admitted_at_utc TEXT,
    released_at_utc TEXT,
    CHECK (length(source_identity) = 22
           AND substr(source_identity, 1, 13) = 'korea-policy:'
           AND substr(source_identity, 14) NOT GLOB '*[^0-9]*'),
    CHECK (canonical_official_url =
           'https://www.korea.kr/briefing/pressReleaseView.do?newsId=' ||
           substr(source_identity, 14)),
    CHECK (length(source_git_commit) = 40),
    CHECK (length(source_db_sha256) = 64),
    CHECK (length(candidate_version_sha256) = 64),
    CHECK (length(original_title_sha256) = 64),
    CHECK (length(original_text_sha256) = 64),
    CHECK (length(publisher_html_sha256) = 64),
    CHECK (length(original_hwpx_sha256) = 64),
    CHECK (length(publisher_posted_date) = 10
           AND publisher_posted_date GLOB
               '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]'),
    CHECK (public_scope = 'held' OR
           (admitted_at_utc IS NOT NULL AND released_at_utc IS NOT NULL))
)
"""

INDEX = """
CREATE INDEX IF NOT EXISTS idx_korea_official_source_date
ON korea_official_source_records (publisher_posted_date DESC, source_identity)
"""

EXPECTED_COLUMNS = frozenset((
    "source_identity", "canonical_official_url", "publisher_posted_date",
    "source_git_commit", "source_db_sha256", "candidate_version_sha256",
    "original_title_sha256", "original_text_sha256", "publisher_html_sha256",
    "original_hwpx_sha256", "official_issuer", "official_republisher",
    "source_language", "authority_tier", "originality", "public_scope",
    "admitted_at_utc", "released_at_utc",
))


def _existing_columns(conn: sqlite3.Connection):
    found = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)
    ).fetchone()
    if found is None:
        return None
    return {row[1] for row in conn.execute("PRAGMA table_info(%s)" % TABLE)}


def is_already_applied(conn: sqlite3.Connection) -> bool:
    cols = _existing_columns(conn)
    if cols is None:
        return False
    if cols != EXPECTED_COLUMNS:
        raise ValueError("Korea metadata schema drift requires explicit migration")
    return True


def up(conn: sqlite3.Connection) -> None:
    cols = _existing_columns(conn)
    if cols is not None and cols != EXPECTED_COLUMNS:
        raise ValueError("Korea metadata schema drift requires explicit migration")
    conn.execute(SCHEMA)
    conn.execute(INDEX)
