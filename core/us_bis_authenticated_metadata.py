"""BIS genuine-schedule-attested metadata -> DISTINCT typed live-candidate SQLite.

Only neutral official links, posted dates and Commerce/BIS attribution. This
module is not wired into the public renderer or any production workflow.
The source attestor MUST be run by the authenticated GitHub API release caller;
a serialized report alone is not trusted evidence of a genuine GitHub run.
"""
from __future__ import annotations

import re
from pathlib import Path
from scripts.collect_us_bis_homepage_metadata import canonical, ISSUER, HOST, INDEX, BISHold
from scripts.verify_us_bis_homepage_receipt import verify, iso_day
from scripts.reconcile_db import read_only

NAME = "bis_authenticated_official_source_records"
OBS = "bis_authenticated_official_observations"
SHA = re.compile("[0-9a-f]{40}\\Z")
DIGEST = re.compile("[0-9a-f]{64}\\Z")
FIELDS = ("canonical_official_url","publisher_posted_date",
          "official_issuer","official_publisher","publisher_listing_url")

class BISLiveAdmissionHold(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise BISLiveAdmissionHold(reason)


def validate(packet, attestation):
    need(type(attestation) is dict, "attestation_missing")
    need(attestation.get("status") ==
         "PASS_GENUINE_SCHEDULED_SOURCE_METADATA_RECEIPT",
         "genuine_source_attestation_not_passed")
    day = attestation.get("receipt_day")
    need(type(day) is str, "attested_source_day_absent")
    try:
        rows = packet["rows"]
        verify(packet, expected_day=day)
    except (BISHold, KeyError, ValueError, TypeError):
        raise BISLiveAdmissionHold("official_source_packet_untrusted") from None
    need(type(attestation.get("source_commit")) is str and
         SHA.fullmatch(attestation["source_commit"]) is not None,
         "source_commit_sha_invalid")
    need(type(attestation.get("source_branch_head")) is str and
         SHA.fullmatch(attestation["source_branch_head"]) is not None,
         "source_branch_sha_invalid")
    need(type(attestation.get("source_run_id")) is int and
         attestation["source_run_id"] > 0 and
         type(attestation.get("source_run_attempt")) is int and
         attestation["source_run_attempt"] > 0, "scheduled_run_id_invalid")
    need(type(attestation.get("official_listing_sha256")) is str and
         DIGEST.fullmatch(attestation["official_listing_sha256"]) is not None
         and attestation["official_listing_sha256"] ==
         packet["official_listing_sha256"], "source_listing_digest_disagrees")
    need(type(attestation.get("verified_official_link_rows")) is int and
         attestation["verified_official_link_rows"] == len(rows),
         "attested_row_count_disagrees")
    need(attestation.get("source_html_independently_rehashed") is False and
         attestation.get("qualified_clean_day_streak") is False and
         attestation.get("live_sqlite_admission_authorized") is False and
         attestation.get("public_site_publishing_authorized") is False,
         "attestation_made_unauthorized_promotion_claim")
    need(len({r["canonical_official_url"] for r in rows}) == len(rows),
         "duplicate_official_source_url")
    return day,rows


def create_schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS
        bis_authenticated_official_source_records (
          source_identity TEXT PRIMARY KEY,
          canonical_official_url TEXT NOT NULL UNIQUE,
          publisher_posted_date TEXT NOT NULL,
          official_issuer TEXT NOT NULL
            CHECK (official_issuer='us_bureau_of_industry_and_security'),
          official_publisher TEXT NOT NULL
            CHECK (official_publisher='www.bis.gov'),
          publisher_listing_url TEXT NOT NULL
            CHECK (publisher_listing_url='https://www.bis.gov/'),
          first_observed_utc TEXT NOT NULL,
          first_attested_source_commit TEXT NOT NULL,
          source_run_id INTEGER NOT NULL,
          public_scope TEXT NOT NULL CHECK(public_scope='official_link_only')
        )""")
    con.execute("""CREATE TABLE IF NOT EXISTS
        bis_authenticated_official_observations (
          observed_on_utc TEXT PRIMARY KEY,
          official_listing_sha256 TEXT NOT NULL,
          exact_attested_source_commit TEXT NOT NULL,
          source_run_id INTEGER NOT NULL,
          source_run_attempt INTEGER NOT NULL,
          verified_link_count INTEGER NOT NULL CHECK(verified_link_count > 0),
          scope TEXT NOT NULL CHECK(scope='official_link_metadata_only')
        )""")


def admit_attested(con, packet, attestation):
    """Savepoint-atomic, idempotent candidate admission, not a public release."""
    day, rows = validate(packet, attestation)
    con.execute("SAVEPOINT bis_attested_admission")
    try:
        create_schema(con)
        old = con.execute(
            "SELECT official_listing_sha256, exact_attested_source_commit, "
            "source_run_id, source_run_attempt, verified_link_count "
            "FROM bis_authenticated_official_observations "
            "WHERE observed_on_utc=?", (day,)).fetchone()
        expected = (packet["official_listing_sha256"],
                    attestation["source_commit"], attestation["source_run_id"],
                    attestation["source_run_attempt"], len(rows))
        if old is not None:
            need(old == expected, "previous_genuine_source_observation_changed")
        else:
            con.execute(
                "INSERT INTO bis_authenticated_official_observations "
                "(observed_on_utc,official_listing_sha256,"
                "exact_attested_source_commit,source_run_id,source_run_attempt,"
                "verified_link_count,scope) VALUES (?,?,?,?,?,?,?)",
                (*((day,) + expected), "official_link_metadata_only"))
        added = 0
        for row in rows:
            expected_row = tuple(row[k] for k in FIELDS)
            ident = row["source_identity"]
            old_row = con.execute(
                "SELECT canonical_official_url,publisher_posted_date,"
                "official_issuer,official_publisher,publisher_listing_url "
                "FROM bis_authenticated_official_source_records "
                "WHERE source_identity=?", (ident,)).fetchone()
            if old_row is not None:
                need(old_row == expected_row,
                     "previously_attested_source_identity_changed")
                continue
            con.execute(
                "INSERT INTO bis_authenticated_official_source_records "
                "(source_identity,canonical_official_url,publisher_posted_date,"
                "official_issuer,official_publisher,publisher_listing_url,"
                "first_observed_utc,first_attested_source_commit,"
                "source_run_id,public_scope) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ident, *expected_row, day,
                 attestation["source_commit"],
                 attestation["source_run_id"], "official_link_only"))
            added += 1
        con.execute("RELEASE SAVEPOINT bis_attested_admission")
        return added
    except Exception:
        con.execute("ROLLBACK TO SAVEPOINT bis_attested_admission")
        con.execute("RELEASE SAVEPOINT bis_attested_admission")
        raise


def load_public_links(db_path):
    """Only the separate attested table; missing means no BIS coverage."""
    need(Path(db_path).is_file(), "production_database_missing")
    with read_only(str(db_path)) as con:
        if not con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND "
            "name='bis_authenticated_official_source_records'").fetchone():
            return []
        rows = con.execute(
            "SELECT source_identity,canonical_official_url,"
            "publisher_posted_date,official_issuer,official_publisher,"
            "publisher_listing_url,first_attested_source_commit,public_scope "
            "FROM bis_authenticated_official_source_records "
            "ORDER BY publisher_posted_date DESC,source_identity DESC").fetchall()
    results, seen = [], set()
    for ident, url, day, issuer, publisher, listing, sha, scope in rows:
        resolved = canonical(url)
        need(resolved is not None and url == resolved[0] and
             ident == "us-bis-homepage-press:" + resolved[1],
             "stored_official_url_identity_corrupted")
        try:
            iso_day(day)
        except (BISHold, ValueError, TypeError):
            raise BISLiveAdmissionHold("stored_publisher_date_corrupted") from None
        need("2025-01-01" <= day and issuer == ISSUER and publisher == HOST
             and listing == INDEX and scope == "official_link_only"
             and type(sha) is str and SHA.fullmatch(sha) is not None,
             "stored_bis_provenance_corrupted")
        need(url not in seen, "stored_bis_url_duplicate")
        seen.add(url)
        results.append({
            "source_identity": ident, "source_url": url,
            "published_date": day,
            "neutral_label": "BIS official press reference · " + day
        })
    return results
