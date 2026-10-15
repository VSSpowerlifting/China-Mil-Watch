"""Validate source-bound USCC factual metadata for a held or link-only SQL lane.

The production caller must independently authenticate that the JSON bytes
were fetched from shadow/uscc-press at the named commit; this pure module
NEVER asserts source Git custody based on an unauthenticated caller claim.
No bodies, original titles, media or analysis are allowed in input or output.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date
from urllib.parse import urlsplit

TABLE="uscc_official_source_records"
SCHEMA="ipr-uscc-firstparty-official-link-metadata/1"
PREFIX="https://www.uscc.gov/press-releases/"
ISSUER="us_china_economic_security_review_commission"
SLUG=re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
HASH=re.compile(r"[0-9a-f]{64}\Z")
GIT=re.compile(r"[0-9a-f]{40}\Z")
ROW_KEYS=frozenset(("source_identity","canonical_official_url",
                   "publisher_posted_date","official_issuer",
                   "official_publisher","publisher_listing_url"))
PACKET_KEYS=frozenset((
    "schema","source_host","source_family","publisher","issuer",
    "collection_mode","observed_on_utc","official_listing_url",
    "official_listing_sha256","rows","visible_dated_rows",
    "original_titles_copied","bodies_copied","document_media_copied",
    "analysis_performed","publication_authorized_by_collector",
    "production_records_written","complete_publisher_history_claimed",
))
class USCCAdmissionHold(ValueError):
    pass

def need(ok,reason):
    if not ok:
        raise USCCAdmissionHold(reason)

def _day(value):
    need(type(value) is str and len(value)==10,"invalid_posted_date")
    try: d=date.fromisoformat(value)
    except ValueError: raise USCCAdmissionHold("invalid_posted_date") from None
    need(d.isoformat()==value,"invalid_posted_date")
    return d

def validate(packet, *, source_git_commit, source_observation_sha256):
    need(type(source_git_commit) is str and GIT.fullmatch(source_git_commit),
         "source_git_commit_unverified")
    need(type(source_observation_sha256) is str and
         HASH.fullmatch(source_observation_sha256),
         "source_observation_hash_unverified")
    need(type(packet) is dict and set(packet)==PACKET_KEYS,
         "untrusted_source_packet_fields")
    need(packet["schema"]==SCHEMA and packet["source_host"]=="www.uscc.gov"
         and packet["source_family"]=="uscc_press_releases"
         and packet["issuer"]==ISSUER
         and packet["publisher"]=="U.S.-China Economic and Security Review Commission"
         and packet["collection_mode"]=="bounded_official_listing_metadata_only"
         and packet["official_listing_url"]=="https://www.uscc.gov/press-releases"
         and type(packet["official_listing_sha256"]) is str
         and HASH.fullmatch(packet["official_listing_sha256"])
         and type(packet["visible_dated_rows"]) is int
         and type(packet["rows"]) is list
         and packet["visible_dated_rows"]==len(packet["rows"])
         and 1<=len(packet["rows"])<=75
         and packet["original_titles_copied"] is False
         and packet["bodies_copied"] is False
         and packet["document_media_copied"] is False
         and packet["analysis_performed"] is False
         and packet["publication_authorized_by_collector"] is False
         and packet["production_records_written"]==0
         and type(packet["production_records_written"]) is int
         and packet["complete_publisher_history_claimed"] is False,
         "source_scope_or_rights_changed")
    observed=_day(packet["observed_on_utc"])
    results=[];seen=set();urls=set()
    for row in packet["rows"]:
        need(type(row) is dict and set(row)==ROW_KEYS,
             "source_original_or_unreviewed_field_present")
        ident=row["source_identity"]
        need(type(ident) is str and ident.startswith("uscc-press:"),
             "invalid_source_identity")
        slug=ident[len("uscc-press:"):]
        need(11<=len(slug)<=204 and SLUG.fullmatch(slug),
             "invalid_official_slug")
        url=row["canonical_official_url"]
        need(type(url) is str and url==PREFIX+slug
             and urlsplit(url).scheme=="https"
             and urlsplit(url).netloc=="www.uscc.gov"
             and not urlsplit(url).query
             and not urlsplit(url).fragment
             and row["official_issuer"]==ISSUER
             and row["official_publisher"]=="www.uscc.gov"
             and row["publisher_listing_url"]=="https://www.uscc.gov/press-releases",
             "official_url_or_issuer_scope_changed")
        posted=_day(row["publisher_posted_date"])
        need(date(2025,1,1)<=posted<=observed, "untrusted_date_order")
        need(ident not in seen and url not in urls,
             "duplicate_source_identity_or_url")
        seen.add(ident);urls.add(url)
        results.append((ident,url,posted.isoformat(),ISSUER,"www.uscc.gov",
                        observed.isoformat(),source_git_commit,
                        source_observation_sha256,
                        packet["official_listing_sha256"]))
    return sorted(results)

def admit(conn:sqlite3.Connection,packet,*,source_git_commit,
          source_observation_sha256,as_of_utc,permit_official_metadata):
    need(permit_official_metadata is True,
         "standing_official_metadata_approval_not_supplied")
    need(type(as_of_utc) is str and re.fullmatch(
         r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
         as_of_utc),"invalid_import_time")
    rows=validate(packet,source_git_commit=source_git_commit,
                  source_observation_sha256=source_observation_sha256)
    columns={r[1] for r in conn.execute("PRAGMA table_info(%s)"%TABLE)}
    need("public_scope" in columns and "source_observation_sha256" in columns,
         "uscc_production_metadata_migration_missing")
    added=unchanged=0
    conn.execute("SAVEPOINT uscc_verified_metadata_link_admission")
    try:
        for row in rows:
            old=conn.execute(
              "SELECT canonical_official_url,publisher_posted_date,"
              "official_issuer,official_publisher,public_scope "
              "FROM uscc_official_source_records WHERE source_identity=?",
              (row[0],)).fetchone()
            if old is not None:
                need(tuple(old)==(row[1],row[2],row[3],row[4],
                                  "official_link_only"),
                     "published_source_version_or_issuer_changed")
                unchanged+=1
                continue
            conn.execute(
              "INSERT INTO uscc_official_source_records "
              "(source_identity,canonical_official_url,publisher_posted_date,"
              "official_issuer,official_publisher,source_observed_on_utc,"
              "source_git_commit,source_observation_sha256,"
              "source_listing_sha256,public_scope,admitted_at_utc,released_at_utc)"
              " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (*row,"official_link_only",as_of_utc,as_of_utc))
            added+=1
        need(conn.execute("PRAGMA foreign_key_check").fetchall()==[],
             "metadata_foreign_key_violation")
        conn.execute("RELEASE SAVEPOINT uscc_verified_metadata_link_admission")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT uscc_verified_metadata_link_admission")
        conn.execute("RELEASE SAVEPOINT uscc_verified_metadata_link_admission")
        raise
    return {"schema":"ipr-uscc-verified-official-link-admission/1",
            "source_git_commit":source_git_commit,
            "new_official_links":added,
            "unchanged_official_links":unchanged,
            "original_titles_or_bodies_copied":False,
            "media_or_analysis_published":False}
