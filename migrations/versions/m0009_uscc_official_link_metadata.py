"""0009 — first-party USCC URL/date/issuer records; NO article/body storage.

Separate from m0008 Korean MND official metadata and legacy articles. No
observed rows or publisher-content rights are introduced by this migration.
"""
import sqlite3

VERSION="0009"
NAME="uscc_official_link_metadata"
TABLE="uscc_official_source_records"
COLUMNS=frozenset((
 "source_identity","canonical_official_url","publisher_posted_date",
 "official_issuer","official_publisher","source_observed_on_utc",
 "source_git_commit","source_observation_sha256","source_listing_sha256",
 "public_scope","admitted_at_utc","released_at_utc",
))
DDL="""
CREATE TABLE IF NOT EXISTS uscc_official_source_records (
    source_identity TEXT PRIMARY KEY NOT NULL,
    canonical_official_url TEXT NOT NULL UNIQUE,
    publisher_posted_date TEXT NOT NULL,
    official_issuer TEXT NOT NULL
      CHECK (official_issuer='us_china_economic_security_review_commission'),
    official_publisher TEXT NOT NULL
      CHECK (official_publisher='www.uscc.gov'),
    source_observed_on_utc TEXT NOT NULL,
    source_git_commit TEXT NOT NULL,
    source_observation_sha256 TEXT NOT NULL,
    source_listing_sha256 TEXT NOT NULL,
    public_scope TEXT NOT NULL DEFAULT 'held'
      CHECK (public_scope IN ('held','official_link_only')),
    admitted_at_utc TEXT NOT NULL,
    released_at_utc TEXT,
    CHECK (length(source_identity) BETWEEN 22 AND 215
      AND substr(source_identity,1,11)='uscc-press:'
      AND length(substr(source_identity,12)) BETWEEN 11 AND 204
      AND substr(source_identity,12) NOT GLOB '*[^a-z0-9-]*'),
    CHECK (canonical_official_url =
       'https://www.uscc.gov/press-releases/' || substr(source_identity,12)),
    CHECK (length(publisher_posted_date)=10 AND
      publisher_posted_date GLOB '20[0-9][0-9]-[01][0-9]-[0-3][0-9]'),
    CHECK (length(source_observed_on_utc)=10 AND
      source_observed_on_utc GLOB '20[0-9][0-9]-[01][0-9]-[0-3][0-9]'),
    CHECK (length(source_git_commit)=40 AND
      source_git_commit NOT GLOB '*[^0-9a-f]*'),
    CHECK (length(source_observation_sha256)=64 AND
      source_observation_sha256 NOT GLOB '*[^0-9a-f]*'),
    CHECK (length(source_listing_sha256)=64 AND
      source_listing_sha256 NOT GLOB '*[^0-9a-f]*'),
    CHECK (public_scope='held' OR released_at_utc IS NOT NULL)
)
"""
IDX="""CREATE INDEX IF NOT EXISTS idx_uscc_official_link_posted_date
ON uscc_official_source_records(publisher_posted_date DESC,source_identity)"""

def columns(conn):
    if conn.execute(
      "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
      (TABLE,)).fetchone() is None:
        return None
    return {row[1] for row in conn.execute("PRAGMA table_info(%s)"%TABLE)}

def is_already_applied(conn):
    existing=columns(conn)
    if existing is None:
        return False
    if existing != COLUMNS:
        raise ValueError("USCC metadata schema mismatch; explicit migration required")
    return True

def up(conn):
    existing=columns(conn)
    if existing is not None and existing != COLUMNS:
        raise ValueError("USCC metadata schema drift")
    conn.execute(DDL)
    conn.execute(IDX)
