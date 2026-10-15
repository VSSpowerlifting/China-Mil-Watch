"""Verified USCC metadata observation -> isolated, idempotent SQLite admission.

This is a congressional commission record family, not PACOM, DVIDS, or an
IPR-authored article. Only publisher URLs, dates, identity and issuer are stored.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from scripts.collect_uscc_press_metadata import (
    SCHEMA as SOURCE_SCHEMA, INDEX, HOST, canonical,
)
from scripts.reconcile_db import read_only

ISSUER = "us_china_economic_security_review_commission"
FIELDS = frozenset(("source_identity", "canonical_official_url",
                    "publisher_posted_date", "official_issuer",
                    "official_publisher", "publisher_listing_url"))
ENVELOPE = frozenset(("schema", "source_host", "source_family", "publisher",
    "issuer", "collection_mode", "observed_on_utc", "official_listing_url",
    "official_listing_sha256", "rows", "visible_dated_rows",
    "original_titles_copied", "bodies_copied", "document_media_copied",
    "analysis_performed", "publication_authorized_by_collector",
    "production_records_written", "complete_publisher_history_claimed"))
SHA = re.compile(r"[a-f0-9]{40}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
DAY = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\Z")

class USCCAdmissionHold(ValueError):
    pass

def require(ok, reason):
    if not ok:
        raise USCCAdmissionHold(reason)

def checked_day(value):
    require(type(value) is str and DAY.fullmatch(value), "invalid_date")
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise USCCAdmissionHold("invalid_date") from None
    require(day.isoformat() == value, "noncanonical_date")
    return day

def validate_observation(packet, *, receipt_day):
    require(type(packet) is dict and set(packet) == ENVELOPE,
            "observation_unknown_fields")
    require(packet["schema"] == SOURCE_SCHEMA and packet["source_host"] == HOST
            and packet["source_family"] == "uscc_press_releases"
            and packet["publisher"] ==
                "U.S.-China Economic and Security Review Commission"
            and packet["issuer"] == ISSUER
            and packet["collection_mode"] ==
                "bounded_official_listing_metadata_only"
            and packet["official_listing_url"] == INDEX,
            "observation_source_identity_invalid")
    require(checked_day(packet["observed_on_utc"]) == checked_day(receipt_day),
            "observation_file_day_disagrees")
    require(type(packet["official_listing_sha256"]) is str and
            DIGEST.fullmatch(packet["official_listing_sha256"]),
            "listing_digest_invalid")
    for key in ("original_titles_copied", "bodies_copied",
                "document_media_copied", "analysis_performed",
                "publication_authorized_by_collector",
                "complete_publisher_history_claimed"):
        require(packet[key] is False, "publisher_content_or_authority_claim")
    require(packet["production_records_written"] == 0 and
            type(packet["production_records_written"]) is int,
            "collector_claims_production_write")
    rows = packet["rows"]
    require(type(rows) is list and type(packet["visible_dated_rows"]) is int
            and 1 <= len(rows) <= 75
            and len(rows) == packet["visible_dated_rows"],
            "listing_count_mismatch")
    ids, urls = set(), set()
    for r in rows:
        require(type(r) is dict and set(r) == FIELDS and
                all(type(x) is str for x in r.values()),
                "unapproved_publisher_fields")
        require(r["official_issuer"] == ISSUER
                and r["official_publisher"] == HOST
                and r["publisher_listing_url"] == INDEX,
                "publisher_attribution_invalid")
        source = canonical(r["canonical_official_url"])
        require(source is not None and
                r["canonical_official_url"] == source[0] and
                r["source_identity"] == "uscc-press:" + source[1],
                "official_url_and_identity_disagree")
        require(date(2025, 1, 1) <= checked_day(r["publisher_posted_date"])
                <= checked_day(receipt_day), "official_date_untrusted")
        require(r["source_identity"] not in ids and
                r["canonical_official_url"] not in urls,
                "duplicate_observation_entry")
        ids.add(r["source_identity"])
        urls.add(r["canonical_official_url"])
    return rows

def create_schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS uscc_official_source_records (
        source_identity TEXT PRIMARY KEY,
        canonical_official_url TEXT NOT NULL UNIQUE,
        publisher_posted_date TEXT NOT NULL,
        official_issuer TEXT NOT NULL,
        official_publisher TEXT NOT NULL,
        publisher_listing_url TEXT NOT NULL,
        first_observed_utc TEXT NOT NULL,
        first_source_commit_sha TEXT NOT NULL,
        public_scope TEXT NOT NULL CHECK (public_scope='official_link_only')
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS uscc_official_observations (
        observed_on_utc TEXT PRIMARY KEY,
        official_listing_sha256 TEXT NOT NULL,
        source_commit_sha TEXT NOT NULL,
        verified_link_count INTEGER NOT NULL
    )""")

def admit(con, packet, *, receipt_day, source_sha):
    rows = validate_observation(packet, receipt_day=receipt_day)
    require(type(source_sha) is str and SHA.fullmatch(source_sha),
            "source_commit_sha_invalid")
    create_schema(con)
    old = con.execute("""SELECT official_listing_sha256, verified_link_count
        FROM uscc_official_observations WHERE observed_on_utc=?""",
        (receipt_day,)).fetchone()
    if old is not None:
        require(old == (packet["official_listing_sha256"], len(rows)),
                "previous_daily_observation_changed")
    else:
        con.execute("""INSERT INTO uscc_official_observations VALUES (?,?,?,?)""",
            (receipt_day, packet["official_listing_sha256"], source_sha, len(rows)))
    inserted = 0
    for row in rows:
        ident = row["source_identity"]
        old = con.execute("""SELECT canonical_official_url,
            publisher_posted_date, official_issuer, official_publisher,
            publisher_listing_url FROM uscc_official_source_records
            WHERE source_identity=?""", (ident,)).fetchone()
        expected = tuple(row[k] for k in
            ("canonical_official_url", "publisher_posted_date",
             "official_issuer", "official_publisher", "publisher_listing_url"))
        if old is not None:
            require(old == expected, "admitted_source_identity_changed")
            continue
        con.execute("""INSERT INTO uscc_official_source_records
            (source_identity,canonical_official_url,publisher_posted_date,
             official_issuer,official_publisher,publisher_listing_url,
             first_observed_utc,first_source_commit_sha,public_scope)
             VALUES (?,?,?,?,?,?,?,?,?)""",
            (ident, *expected, receipt_day, source_sha, "official_link_only"))
        inserted += 1
    return inserted

def load_public_links(db_path):
    if not Path(db_path).is_file():
        raise USCCAdmissionHold("production_database_unavailable")
    with read_only(str(db_path)) as con:
        if not con.execute("""SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='uscc_official_source_records'""").fetchone():
            return []
        rows = con.execute("""SELECT source_identity,canonical_official_url,
            publisher_posted_date,official_issuer,official_publisher,
            publisher_listing_url FROM uscc_official_source_records
            WHERE public_scope='official_link_only'
            ORDER BY publisher_posted_date DESC, source_identity DESC""").fetchall()
    public = []
    for ident, url, day, issuer, host, listing in rows:
        validate_observation({
            "schema": SOURCE_SCHEMA, "source_host": HOST,
            "source_family":"uscc_press_releases",
            "publisher":"U.S.-China Economic and Security Review Commission",
            "issuer":ISSUER, "collection_mode":"bounded_official_listing_metadata_only",
            "observed_on_utc":day, "official_listing_url":INDEX,
            "official_listing_sha256":"0"*64,
            "rows":[{"source_identity":ident,"canonical_official_url":url,
                     "publisher_posted_date":day,"official_issuer":issuer,
                     "official_publisher":host,"publisher_listing_url":listing}],
            "visible_dated_rows":1,
            "original_titles_copied":False,"bodies_copied":False,
            "document_media_copied":False,"analysis_performed":False,
            "publication_authorized_by_collector":False,
            "production_records_written":0,
            "complete_publisher_history_claimed":False,
        }, receipt_day=day)
        public.append({"source_identity":ident,"source_url":url,
                       "published_date":day,
                       "neutral_label":"USCC official press reference · " + day})
    return public
