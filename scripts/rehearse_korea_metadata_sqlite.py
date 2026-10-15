"""Korea signed-review -> isolated METADATA-ONLY SQLite rehearsal.

A fresh, outside-repo owner-only SQLite file is the ONLY mutable output.
Rebuild and match all source evidence via the #656 intake bridge before
checking #658's distinct-signer, exact-version metadata-only review seals.
No production DB, source body, HWPX, translations, editor email or website.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

from core import korea_versioned_review_admission as review
from scripts import stage_korea_production_candidates as stage

SCHEMA = "ipr-korea-metadata-disposable-sqlite-rehearsal/1"
TABLE = """
CREATE TABLE korea_metadata_rehearsal (
    source_identity TEXT NOT NULL PRIMARY KEY,
    source_git_commit TEXT NOT NULL,
    candidate_version_sha256 TEXT NOT NULL UNIQUE,
    official_url TEXT NOT NULL UNIQUE,
    publisher_date TEXT NOT NULL,
    source_slug TEXT NOT NULL,
    issuer_institution TEXT NOT NULL,
    republisher_institution TEXT NOT NULL,
    originality TEXT NOT NULL,
    authority_tier TEXT NOT NULL,
    original_text_sha256 TEXT NOT NULL,
    publisher_html_sha256 TEXT NOT NULL,
    original_hwpx_sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status='metadata_only_rehearsal_not_production')
)
"""


class RehearsalHold(ValueError):
    """Refusal deliberately contains no content, addresses or identities."""


def need(test, reason):
    if not test:
        raise RehearsalHold(reason)


def rehearse(source_checkout, packet, seals, *, reviewer_key,
             owner_key, as_of_utc, destination):
    """Metadata-only disposable db; never modifies or publishes source state."""
    path = stage._path(destination)
    checkout = Path(source_checkout).expanduser().resolve(strict=True)
    need(checkout != path and checkout not in path.parents,
         "rehearsal_output_inside_source_checkout")
    need(type(packet) is dict and type(seals) is list
         and 1 <= len(seals) <= stage.ROWS,
         "invalid_metadata_rehearsal_inputs")
    try:
        verified = stage.build(str(checkout))
    except (ValueError, OSError):
        raise RehearsalHold("original_korea_source_reverification_failed") from None
    need(stage.canonical(verified) == stage.canonical(packet),
         "staged_packet_changed_since_original_evidence_verification")
    indexed = review._packet(verified)
    signatures = []
    seen = set()
    for seal in seals:
        try:
            receipt = review.verify(
                verified, seal, reviewer_key=reviewer_key,
                owner_key=owner_key, as_of_utc=as_of_utc)
        except (review.AdmissionHold, ValueError, KeyError, TypeError):
            raise RehearsalHold("review_or_owner_signature_not_eligible") from None
        ident = receipt["source_identity"]
        need(ident in indexed and ident not in seen,
             "duplicate_or_unrecognized_review")
        seen.add(ident)
        signatures.append(receipt)

    rows = []
    for receipt in signatures:
        if not receipt["metadata_only_disposable_db_rehearsal_candidate"]:
            continue
        src = indexed[receipt["source_identity"]]
        need(receipt["candidate_version_sha256"] ==
             src["candidate_version_sha256"]
             and receipt["source_git_commit"] ==
                 verified["source_git_commit"],
             "signed_review_source_version_drift")
        rows.append((
            src["source_identity"], verified["source_git_commit"],
            src["candidate_version_sha256"], src["canonical_source_url"],
            src["publisher_posted_date"], src["source_slug"],
            src["institution_id"], src["publisher_institution_id"],
            src["originality"], src["authority_tier"],
            src["original_text_sha256"], src["publisher_html_sha256"],
            src["original_hwpx_sha256"],
            "metadata_only_rehearsal_not_production",
        ))
    rows.sort(key=lambda row: row[0])
    # Construct in-memory, including every write and idempotency check,
    # BEFORE creating a durable scratch file.
    tmp = sqlite3.connect(":memory:")
    try:
        tmp.execute("PRAGMA foreign_keys=ON")
        tmp.execute(TABLE)
        tmp.executemany(
            "INSERT INTO korea_metadata_rehearsal VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        tmp.commit()
        existing = tmp.execute(
            "SELECT source_identity,candidate_version_sha256 FROM "
            "korea_metadata_rehearsal ORDER BY source_identity").fetchall()
        need(existing == [(r[0], r[2]) for r in rows],
             "metadata_rehearsal_integrity_failed")
        tmp.executemany(
            "INSERT OR IGNORE INTO korea_metadata_rehearsal VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        need(tmp.execute("SELECT COUNT(*) FROM korea_metadata_rehearsal")
             .fetchone()[0] == len(rows),
             "metadata_rehearsal_not_idempotent")
        tmp.commit()  # SQLite backup must not copy a source with an open write transaction.
        need(tmp.execute("PRAGMA quick_check").fetchone()[0] == "ok",
             "metadata_rehearsal_database_corrupt")
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        created = False
        try:
            fd = os.open(str(path), flags, 0o600)
            created = True
            os.close(fd)
            disk = sqlite3.connect(str(path))
            try:
                tmp.backup(disk)
                disk.commit()
            finally:
                disk.close()
        except Exception:
            if created:
                path.unlink()
            raise
    except sqlite3.Error:
        raise RehearsalHold("metadata_rehearsal_sqlite_write_refused") from None
    finally:
        tmp.close()
    return {
        "schema": SCHEMA,
        "source_git_commit": verified["source_git_commit"],
        "source_packet_sha256": hashlib.sha256(
            stage.canonical(verified)).hexdigest(),
        "original_record_count": verified["source_original_count"],
        "reviewed_source_count": len(signatures),
        "held_source_count": len(signatures) - len(rows),
        "signed_metadata_rehearsal_rows": len(rows),
        "unreviewed_source_count": len(indexed) - len(signatures),
        "original_body_title_or_media_exported": False,
        "real_production_rows_written": 0,
        "actual_public_records_created": 0,
        "external_model_or_email_sent": False,
        "source_rights_independently_authenticated_by_tool": False,
        "publisher_completeness_proved": False,
    }
