"""Read-only archived Japanese MOD source *row* drift — never PDF rights proof.

A new shadow SQLite Git blob does not mean an earlier publisher document
changed. This audit compares the precisely pinned historical extracted text
to the same URL in a newer independently lineage-checked shadow Git state.
It does not fetch live PDF bytes or admit research to the regional model.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import tempfile
from pathlib import Path

from scripts import audit_japan_oct05_brief_source as pinned

SCHEMA = "ipr-japan-oct05-shadow-row-version-comparison/1"
FIELDS = (
    "url", "source_slug", "title_original", "text_original",
    "published_date", "language_tag", "publication_kind",
    "content_sha256", "capture_sha256", "first_seen_run",
)


class JapanRowDriftError(ValueError):
    """Current archive is not a valid independent version comparison."""


def need(ok, reason):
    if not ok:
        raise JapanRowDriftError(reason)


def _digest(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def inspect_current_snapshot(db_bytes):
    """Inspect current SQLite row by canonical historical URL, no write."""
    need(type(db_bytes) is bytes and 0 < len(db_bytes) <= 5_000_000
         and db_bytes.startswith(b"SQLite format 3\x00"),
         "new shadow blob is not a bounded SQLite snapshot")
    with tempfile.TemporaryDirectory(prefix="ipr-jp-shadow-compare-") as folder:
        path = Path(folder) / "shadow.db"
        path.write_bytes(db_bytes)
        con = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA query_only=ON")
            need(con.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                 "new shadow SQLite integrity failed")
            rows = con.execute(
                "SELECT " + ",".join(FIELDS) +
                " FROM shadow_records WHERE url=?", (pinned.PDF_URL,)
            ).fetchall()
            need(len(rows) <= 1, "duplicate official publisher URL in new archive")
            return dict(rows[0]) if rows else None
        except sqlite3.DatabaseError as exc:
            raise JapanRowDriftError("new shadow snapshot schema or query invalid") from exc
        finally:
            con.close()


def compare_pinned_row(current_row, *, current_commit, current_blob):
    """Compare row bytes/identity to already independently attested old pin.

    The trusted baseline is pinned.py's fixed historical SHA and published
    original identity. A current row can be UNCHANGED, CHANGED or MISSING;
    none of these states is human approval or current publisher attestation.
    """
    need(isinstance(current_commit, str)
         and re.fullmatch(r"[0-9a-f]{40}", current_commit)
         and isinstance(current_blob, str)
         and re.fullmatch(r"[0-9a-f]{40}", current_blob),
         "current exact Git object identifiers are required")
    if current_row is None:
        verdict = "held_original_row_missing_in_new_shadow_archive"
        differences = ["canonical_publisher_record_missing"]
        current_text_sha = None
    else:
        need(type(current_row) is dict and
             all(field in current_row for field in FIELDS),
             "new row lacks versioned publisher-source fields")
        current_text = current_row["text_original"]
        need(isinstance(current_text, str) and len(current_text) <= 100000,
             "new row has malformed or oversized Japanese original text")
        current_text_sha = _digest(current_text)
        differences = []
        values = {
            "url": pinned.PDF_URL,
            "source_slug": pinned.SOURCE,
            "title_original": pinned.TITLE,
            "published_date": "2026-10-05",
            "language_tag": "ja",
            "publication_kind": "press release",
            "first_seen_run": pinned.EXPECTED_RUN,
            "content_sha256": pinned.TEXT_SHA256,
            "capture_sha256": pinned.CAPTURE_SHA256,
        }
        for field, expected in values.items():
            if current_row[field] != expected:
                differences.append(field)
        if current_text_sha != pinned.TEXT_SHA256:
            differences.append("extracted_japanese_text_bytes")
        if current_row["content_sha256"] != current_text_sha:
            differences.append("current_text_integrity_hash_inconsistent")
        verdict = ("same_archived_extracted_text_and_row_identity"
                   if not differences else
                   "changed_or_inconsistent_current_shadow_source")
    return {
        "schema": SCHEMA,
        "historical_git_commit": pinned.STATE_COMMIT,
        "historical_sqlite_git_blob_sha1": pinned.DB_BLOB_SHA1,
        "historical_extracted_text_sha256": pinned.TEXT_SHA256,
        "current_git_commit": current_commit,
        "current_sqlite_git_blob_sha1": current_blob,
        "current_extracted_text_sha256": current_text_sha,
        "row_comparison": verdict,
        "changed_fields": sorted(differences),
        "historical_and_current_text_equal":
            bool(current_row is not None and
                 current_text_sha == pinned.TEXT_SHA256),
        "archived_original_pdf_bytes_verified": False,
        "live_official_publisher_version_verified": False,
        "complete_original_pdf_human_checked": False,
        "source_reuse_rights_reviewed": False,
        "private_regional_model_input_authorized": False,
        "dylan_editor_email_authorized": False,
        "publication_authorized": False,
        "shadow_desk_promoted_to_production": False,
        "no_publisher_url_or_article_body_in_receipt": True,
    }
