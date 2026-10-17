"""Offline PRIVATE reconciliation of Kemhan reviewer worksheet against pinned originals.

Never certifies reviewer identity, rights, collection reliability or production
eligibility. Unsigned rows (including positive assertions) remain NON-AUTHORITY.
The public renderer and regional SQLite writer do not import this module.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from scripts.bind_indonesia_review_versions import (
    PIN, HELD_ID, REVIEW_FIELDS, SCHEMA as SOURCE_SCHEMA, digest,
)

SCHEMA = "ipr-indonesia-unsigned-review-reconciliation/1"
# The actual verified 31-original pinned-Git workflow run #38952228512.
# If originals change, generate and verify a NEW trusted handoff; do not
# quietly accept a newly supplied manifest digest.
EXPECTED_MANIFEST_SHA256 = (
    "6dd3b25ad4c69983e6faf555605bd8fce967c0af5cdba35dd3638c0591b514ad"
)
HEX = re.compile(r"[0-9a-f]{64}\Z")
UTC = re.compile(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z\Z")
READABLE_LIMIT = 350000
REVIEW_CELLS = tuple(REVIEW_FIELDS[6:])
CHECK_FIELDS = ("original_language_checked", "publisher_date_and_title_checked",
                "factual_claims_checked")
RIGHTS_FIELDS = ("publisher_link_use_review", "source_body_reuse_review",
                 "translation_reuse_review", "media_reuse_review")
IMMUTABLE_FIELDS = REVIEW_FIELDS[:6]
SOURCE_FIELDS = frozenset((
    "source_identity", "official_url", "publication_date", "disposition",
    "known_geography_hold", "original_title_sha256", "original_text_sha256",
    "archived_capture_sha256", "source_version_sha256",
    "human_review_authenticated", "rights_or_publication_authorized",
))


class ReviewReconciliationHold(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise ReviewReconciliationHold(reason)


def _expected_row(record):
    return {
        "source_identity": record["source_identity"],
        "source_version_sha256": record["source_version_sha256"],
        "official_url": record["official_url"],
        "publication_date": record["publication_date"],
        "disposition": record["disposition"],
        "source_geography_hold": (
            "YES — MUST REMAIN HELD" if record["known_geography_hold"] else "NO"
        ),
    }


def reconcile(manifest, worksheet_rows, *, expected_sha=EXPECTED_MANIFEST_SHA256,
              as_of_utc=None):
    """Return only aggregate HOLD-safe counts, never source or person details.

    `expected_sha` is an independent, reviewer-trusted digest; the CLI uses
    the constant from the genuine pinned-source workflow. Tests may inject a
    *synthetic* digest without modifying production or claiming authentication.
    """
    need(type(expected_sha) is str and HEX.fullmatch(expected_sha) is not None,
         "trusted_manifest_digest_not_supplied")
    need(type(manifest) is dict and manifest.get("schema") == SOURCE_SCHEMA and
         manifest.get("source_family") == "id_kemhan_news" and
         manifest.get("immutable_source_commit") == PIN and
         manifest.get("originals_version_bound") == 31 and
         manifest.get("known_geography_holds") == 1 and
         manifest.get("human_review_authenticated") is False and
         manifest.get("archive_original_bytes_exported") is False and
         manifest.get("archived_capture_bytes_independently_authenticated") is False and
         manifest.get("publisher_reuse_rights_approved") is False and
         manifest.get("production_admission_authorized") is False and
         manifest.get("public_site_changed") is False,
         "unknown_or_prepublished_source_manifest")
    records = manifest.get("records")
    need(type(records) is list and len(records) == 31 and
         type(manifest.get("manifest_sha256")) is str and
         manifest["manifest_sha256"] == expected_sha and
         digest(records) == expected_sha,
         "untrusted_or_modified_original_manifest")
    by_id = {}
    for item in records:
        need(type(item) is dict and set(item) == SOURCE_FIELDS,
             "unexpected_original_manifest_fields")
        sid = item["source_identity"]
        need(type(sid) is str and sid not in by_id and
             item["official_url"].startswith("https://www.kemhan.go.id/") and
             type(item["source_version_sha256"]) is str and
             all(type(item[k]) is str and HEX.fullmatch(item[k])
                 for k in ("source_version_sha256", "original_title_sha256",
                           "original_text_sha256", "archived_capture_sha256")) and
             item["human_review_authenticated"] is False and
             item["rights_or_publication_authorized"] is False and
             item["known_geography_hold"] is (sid == HELD_ID) and
             item["disposition"] in (
                 "official_link_already_public_not_reviewed",
                 "new_source_review_candidate",
                 "hold_publisher_geography_inconsistent"),
             "corrupt_or_premature_original_reference")
        need((item["disposition"] == "hold_publisher_geography_inconsistent") ==
             item["known_geography_hold"], "held_disposition_not_preserved")
        by_id[sid] = item
    need(HELD_ID in by_id and len(by_id) == 31, "held_original_missing")
    need(type(worksheet_rows) is list and len(worksheet_rows) == 31,
         "incomplete_or_extra_reviewer_rows")
    if as_of_utc is None:
        as_of_utc = datetime.now(timezone.utc)
    need(isinstance(as_of_utc, datetime) and as_of_utc.tzinfo is not None,
         "review_cutoff_requires_timezone")
    summary = {"not_started": 0, "unsigned_review_complete": 0,
               "held_exception": 0}
    seen = set()
    for row in worksheet_rows:
        need(type(row) is dict and set(row) == set(REVIEW_FIELDS) and
             all(type(v) is str and len(v) <= 4000 for v in row.values()),
             "unexpected_or_oversized_reviewer_cells")
        sid = row["source_identity"]
        need(sid in by_id and sid not in seen and
             all(row[k] == v for k, v in
                 _expected_row(by_id[sid]).items()),
             "reviewer_worksheet_original_version_mismatch")
        seen.add(sid)
        # Spaces do not silently turn a partially-filled review into a
        # genuine reviewer receipt. All blank only = not started.
        edited = any(row[k] != "" for k in REVIEW_CELLS)
        if edited:
            need(bool(row["reviewer_name"].strip()) and
                 row["reviewer_name"] == row["reviewer_name"].strip() and
                 bool(row["review_notes"].strip()) and
                 type(row["reviewed_at_utc"]) is str and
                 UTC.fullmatch(row["reviewed_at_utc"]) is not None,
                 "review_claim_missing_person_date_or_notes")
            try:
                when = datetime.strptime(row["reviewed_at_utc"],
                                         "%Y-%m-%dT%H:%M:%SZ").replace(
                                             tzinfo=timezone.utc)
            except ValueError:
                raise ReviewReconciliationHold("invalid_reviewer_timestamp") from None
            need(datetime(2026, 10, 14, tzinfo=timezone.utc) <= when <=
                 as_of_utc.astimezone(timezone.utc),
                 "reviewer_timestamp_outside_real_source_window")
            need(all(row[k] in ("yes", "no", "unclear") for k in CHECK_FIELDS)
                 and all(row[k] in ("allow", "deny", "unclear")
                         for k in RIGHTS_FIELDS),
                 "review_claim_has_unrecognized_scope_or_incomplete_checks")
            if by_id[sid]["known_geography_hold"]:
                need(row["publisher_link_use_review"] != "allow" and
                     all(row[k] != "allow" for k in RIGHTS_FIELDS),
                     "geography_discrepancy_cannot_be_overridden")
        if by_id[sid]["known_geography_hold"]:
            summary["held_exception"] += 1
        elif edited:
            summary["unsigned_review_complete"] += 1
        else:
            summary["not_started"] += 1
    need(seen == set(by_id) and sum(summary.values()) == 31 and
         summary["held_exception"] == 1,
         "reviewer_roster_coverage_or_exception_drift")
    return {
        "schema": SCHEMA,
        "immutable_source_commit": PIN,
        "exact_manifest_sha256": expected_sha,
        "review_rows_reconciled": 31,
        "counts": summary,
        "row_original_versions_matched": True,
        "source_originals_reloaded_by_this_reconciler": False,
        "reviewer_identity_authenticated": False,
        "review_evidence_independently_authenticated": False,
        "publisher_link_use_authority_authenticated": False,
        "publisher_body_translation_media_rights_authenticated": False,
        "all_actions_attempts_authenticated": False,
        "production_admission_authorized": False,
        "public_site_publication_authorized": False,
        "approved_official_links": 0,
        "production_writes": 0,
    }


def read_bounded(path):
    file = Path(path)
    need(file.is_file() and not file.is_symlink() and
         file.stat().st_size <= READABLE_LIMIT, "private_review_file_missing_or_too_large")
    return file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--worksheet", required=True)
    args = parser.parse_args(argv)
    try:
        manifest_path = read_bounded(args.manifest)
        worksheet_path = read_bounded(args.worksheet)
        need(manifest_path.resolve() != worksheet_path.resolve(),
             "manifest_and_worksheet_must_be_distinct")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with worksheet_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, strict=True)
            need(reader.fieldnames == list(REVIEW_FIELDS),
                 "unexpected_unsigned_review_spreadsheet_headers")
            rows = list(reader)
        result = reconcile(manifest, rows)
    except (OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
        # Never echo potentially identifying reviewer names, private notes,
        # publisher titles or URLs to a shared CI log.
        reason = str(exc) if isinstance(exc, ReviewReconciliationHold) else (
            "private_reviewer_inputs_untrusted")
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_writes": 0}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
