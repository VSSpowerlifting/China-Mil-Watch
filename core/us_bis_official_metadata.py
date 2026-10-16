"""BIS official homepage metadata -> typed SQLite staging (never production).

This module is a rehearsal of *structure*, not proof that an observation was
collected by a genuine scheduled GitHub Actions run. Public promotion requires
a separate authenticated receipt census and explicit release implementation.
No site renderer imports this module.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from scripts.collect_us_bis_homepage_metadata import BISHold, HOST, INDEX, ISSUER, canonical
from scripts.verify_us_bis_homepage_receipt import verify, iso_day
from scripts.reconcile_db import read_only

RECORDS = "bis_official_source_records"
OBSERVATIONS = "bis_official_observations"
LINK_FIELDS = ("canonical_official_url", "publisher_posted_date",
               "official_issuer", "official_publisher", "publisher_listing_url")


class BISAdmissionHold(ValueError):
    """Refuse uncertain, inconsistent or unsafe BIS source metadata."""


def need(ok, reason):
    if not ok:
        raise BISAdmissionHold(reason)


def validate(packet, *, receipt_day):
    try:
        verify(packet, expected_day=receipt_day)
    except (BISHold, ValueError, TypeError, KeyError) as exc:
        raise BISAdmissionHold("source_receipt_untrusted: " + str(exc)) from None
    rows = packet["rows"]
    # The original collector only emits canonical, unique release identities.
    need(len({r["canonical_official_url"] for r in rows}) == len(rows),
         "duplicate_canonical_url")
    return rows


def create_schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS bis_official_source_records (
        source_identity TEXT PRIMARY KEY,
        canonical_official_url TEXT NOT NULL UNIQUE,
        publisher_posted_date TEXT NOT NULL,
        official_issuer TEXT NOT NULL
          CHECK(official_issuer='us_bureau_of_industry_and_security'),
        official_publisher TEXT NOT NULL CHECK(official_publisher='www.bis.gov'),
        publisher_listing_url TEXT NOT NULL
          CHECK(publisher_listing_url='https://www.bis.gov/'),
        first_observed_utc TEXT NOT NULL,
        input_reference_sha TEXT NOT NULL,
        record_scope TEXT NOT NULL CHECK(record_scope='official_link_only')
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS bis_official_observations (
        observed_on_utc TEXT PRIMARY KEY,
        official_listing_sha256 TEXT NOT NULL,
        input_reference_sha TEXT NOT NULL,
        verified_link_count INTEGER NOT NULL CHECK(verified_link_count>0),
        provenance_status TEXT NOT NULL
          CHECK(provenance_status='unverified_scratch_rehearsal')
    )""")


def admit_scratch(con, packet, *, receipt_day, input_reference_sha):
    """Idempotent, savepoint-atomic metadata-only staging into a SCRATCH SQLite DB.

    input_reference_sha identifies an input for comparison; it is NOT an
    authenticated source-branch commit or proof of schedule authenticity.
    """
    import re
    need(type(input_reference_sha) is str and
         re.fullmatch("[0-9a-f]{40}", input_reference_sha) is not None,
         "invalid_input_reference")
    rows = validate(packet, receipt_day=receipt_day)
    con.execute("SAVEPOINT bis_staged_admission")
    try:
        create_schema(con)
        previous = con.execute(
            "SELECT official_listing_sha256, verified_link_count "
            "FROM bis_official_observations WHERE observed_on_utc=?",
            (receipt_day,)).fetchone()
        if previous is not None:
            need(previous == (packet["official_listing_sha256"], len(rows)),
                 "immutable_observation_changed")
        else:
            con.execute(
                "INSERT INTO bis_official_observations VALUES (?,?,?,?,?)",
                (receipt_day, packet["official_listing_sha256"],
                 input_reference_sha, len(rows), "unverified_scratch_rehearsal"))
        added = 0
        for row in rows:
            ident = row["source_identity"]
            expected = tuple(row[key] for key in LINK_FIELDS)
            prior = con.execute(
                "SELECT canonical_official_url, publisher_posted_date, "
                "official_issuer, official_publisher, publisher_listing_url "
                "FROM bis_official_source_records WHERE source_identity=?",
                (ident,)).fetchone()
            if prior is not None:
                need(prior == expected, "admitted_source_identity_changed")
                continue
            con.execute(
                "INSERT INTO bis_official_source_records "
                "(source_identity,canonical_official_url,publisher_posted_date,"
                "official_issuer,official_publisher,publisher_listing_url,"
                "first_observed_utc,input_reference_sha,record_scope)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (ident, *expected, receipt_day,
                 input_reference_sha, "official_link_only"))
            added += 1
        con.execute("RELEASE SAVEPOINT bis_staged_admission")
        return added
    except Exception:
        con.execute("ROLLBACK TO SAVEPOINT bis_staged_admission")
        con.execute("RELEASE SAVEPOINT bis_staged_admission")
        raise


def load_staged_links(db_path):
    """Read metadata from a SQLite *scratch* file; does not render any page."""
    path = Path(db_path)
    need(path.is_file() and not path.is_symlink(), "staging_database_missing")
    with read_only(str(path)) as con:
        if not con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='bis_official_source_records'").fetchone():
            return []
        rows = con.execute(
            "SELECT source_identity, canonical_official_url, "
            "publisher_posted_date, official_issuer, official_publisher, "
            "publisher_listing_url,record_scope "
            "FROM bis_official_source_records "
            "ORDER BY publisher_posted_date DESC, source_identity DESC").fetchall()
    result = []
    seen = set()
    for identity, url, posted, issuer, publisher, listing, scope in rows:
        source = canonical(url)
        need(source is not None and url == source[0] and
             identity == "us-bis-homepage-press:" + source[1],
             "stored_identity_disagrees")
        need(issuer == ISSUER and publisher == HOST and listing == INDEX
             and scope == "official_link_only", "stored_source_disagrees")
        iso_day(posted)
        need("2025-01-01" <= posted, "stored_date_untrusted")
        need(url not in seen, "stored_url_duplicate")
        seen.add(url)
        result.append({"source_identity": identity, "source_url": url,
                       "published_date": posted,
                       "neutral_label": "BIS official press reference · " + posted})
    return result
