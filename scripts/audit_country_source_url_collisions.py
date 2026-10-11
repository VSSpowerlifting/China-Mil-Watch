"""Offline candidate URL collision rehearsal; no importer or release authority.

Inputs: S3 read-only schema preflight report, one locally reviewed candidate
URL inventory, and precisely the same immutable, consistent production DB
snapshot. No GitHub/publisher calls, private original bodies, DB writes, or
public record exports. All candidate inputs are unauthenticated assertions.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import re
import sqlite3
import sys
from pathlib import Path

from scripts.inspect_country_admission_boundary import (
    SCHEMA as S3_SCHEMA, SOURCE_CONTRACTS, SHA40, MAX_DB_BYTES,
    AdmissionSchemaRefused, canonical_day, canonical_json, ensure,
    frozen_database_digest, inspect_database, load_checkpoint, sha,
)

SCHEMA = "ipr-country-canonical-url-collision-rehearsal/1"
CANDIDATES_SCHEMA = "ipr-country-source-url-candidates/1"
MAX_CANDIDATES = 4000
MAX_INPUT_BYTES = 1_500_000
AUDIT_FAMILIES = frozenset(("ph_afp_articles", "vn_mps_foreign_affairs_vi"))
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
AFP_URL = re.compile(r"https://www\.afp\.mil\.ph/news/[a-z0-9]+(?:-[a-z0-9]+)*\Z")
AFP_ID = re.compile(r"afp:[1-9][0-9]{0,11}\Z")
MPS_URL = re.compile(r"https://bocongan\.gov\.vn/bai-viet/[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]{10}\Z")
MPS_ID = re.compile(r"mps-vi:[0-9]{10}\Z")
REQUIRED_SCHEMA_CHECKS = frozenset((
    "source_required_columns_present", "article_required_columns_present",
    "unique_source_slug_index", "unique_article_canonical_url_index",
    "schema_compatible",
))
S3_FALSE_FLAGS = (
    "source_rights_authorized", "human_review_authenticated",
    "record_collisions_audited", "private_evidence_migration_authorized",
    "production_write_authorized", "public_record_projection_authorized",
    "website_or_model_release_authorized", "registry_or_manifest_changes_authorized",
)
S3_REPORT_KEYS = frozenset((
    "schema", "candidate_source_slug", "desk_slug", "source_state_branch",
    "pinned_source_commit", "checkpoint_date", "checkpoint_label",
    "checkpoint_receipt_sha256", "production_database_sha256",
    "production_schema_checks", "production_source_slug_collisions",
    "machine_checkpoint_state", "machine_hold_count", "schema_preflight",
    "holds", "next_separate_engineering_stages",
    "candidate_records_imported", "database_or_output_writes",
)) | frozenset(S3_FALSE_FLAGS)
CANDIDATE_KEYS = frozenset(("source_identity", "canonical_url", "publisher_date"))


class CollisionRefused(AdmissionSchemaRefused):
    """Only fixed error codes. Never interpolate candidate content in diagnostics."""


def require(ok, why):
    if not ok:
        raise CollisionRefused(why)


def load_private_file(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(),
            "input_must_be_regular_file")
    require(0 < path.stat().st_size <= MAX_INPUT_BYTES, "input_size_out_of_bounds")
    # Reuse S3's duplicate-key/nonfinite-number rejecting input reader. The
    # bound here is tighter than S3's 2 MB limit.
    return load_checkpoint(path)


def bind_s3(report, source):
    require(source in AUDIT_FAMILIES, "source_not_in_collision_rehearsal_scope")
    require(type(report) is dict and report.get("schema") == S3_SCHEMA,
            "not_a_source_schema_preflight")
    require(set(report) == S3_REPORT_KEYS,
            "unexpected_or_missing_S3_report_fields")
    require(report.get("candidate_source_slug") == source and
            report.get("desk_slug") == SOURCE_CONTRACTS[source][1] and
            report.get("source_state_branch") == SOURCE_CONTRACTS[source][2],
            "source_identity_not_bound_to_preflight")
    require(type(report.get("pinned_source_commit")) is str and
            SHA40.fullmatch(report["pinned_source_commit"]),
            "invalid_source_state_pin")
    for name in ("production_database_sha256", "checkpoint_receipt_sha256"):
        require(type(report.get(name)) is str and SHA64.fullmatch(report[name]),
                "invalid_preflight_digest")
    require(type(report.get("machine_hold_count")) is int and
            report["machine_hold_count"] >= 0 and
            report.get("machine_checkpoint_state") in (
                "candidate_for_human_checkpoint", "machine_evidence_incomplete_or_held"),
            "invalid_machine_checkpoint_state")
    canonical_day(report.get("checkpoint_date"))
    require(report.get("checkpoint_label") in ("day-07", "day-14", "day-30"),
            "invalid_checkpoint_label")
    if source == "ph_afp_articles":
        require(report["checkpoint_label"] == "day-07",
                "AFP_checkpoint_must_be_day_07")
    checks = report.get("production_schema_checks")
    require(type(checks) is dict and set(checks) == REQUIRED_SCHEMA_CHECKS and
            all(checks[k] is True for k in REQUIRED_SCHEMA_CHECKS),
            "preflight_requires_structurally_compatible_schema")
    require(type(report.get("production_source_slug_collisions")) is int and
            report["production_source_slug_collisions"] >= 0,
            "invalid_existing_source_collision_count")
    require(type(report.get("holds")) is list and
            len(report["holds"]) < 150 and
            all(type(x) is str for x in report["holds"]),
            "malformed_preflight_holds")
    expected_status = ("blocked_before_any_ingest" if report["holds"]
                       else "structure_compatible_no_admission")
    require(report.get("schema_preflight") == expected_status,
            "preflight_status_contradicts_holds")
    require(report.get("candidate_records_imported") == 0 and
            type(report.get("candidate_records_imported")) is int and
            report.get("database_or_output_writes") == 0 and
            type(report.get("database_or_output_writes")) is int,
            "preflight_has_reported_mutations")
    for name in S3_FALSE_FLAGS:
        require(report.get(name) is False, "preflight_claims_unauthorized_approval")
    return report


def validate_candidates(doc, s3):
    require(type(doc) is dict and set(doc) == {
        "schema", "source_slug", "state_commit",
        "checkpoint_receipt_sha256", "production_database_sha256", "records",
    } and doc["schema"] == CANDIDATES_SCHEMA,
            "invalid_candidate_inventory_schema")
    require(doc["source_slug"] == s3["candidate_source_slug"] and
            doc["state_commit"] == s3["pinned_source_commit"] and
            doc["checkpoint_receipt_sha256"] == s3["checkpoint_receipt_sha256"] and
            doc["production_database_sha256"] == s3["production_database_sha256"],
            "candidate_metadata_does_not_match_preflight_pins")
    records = doc["records"]
    require(type(records) is list and 1 <= len(records) <= MAX_CANDIDATES,
            "candidate_count_out_of_bounds")
    identities, urls = set(), set()
    normalized = []
    source = doc["source_slug"]
    for row in records:
        require(type(row) is dict and set(row) == CANDIDATE_KEYS,
                "candidate_row_contains_extra_or_missing_fields")
        ident, url, publisher_day = (row["source_identity"],
                                     row["canonical_url"], row["publisher_date"])
        require(type(ident) is str and type(url) is str and len(url) <= 600,
                "candidate_identity_or_url_invalid")
        try:
            canonical_day(publisher_day)
        except AdmissionSchemaRefused:
            raise CollisionRefused("candidate_publisher_date_invalid") from None
        if source == "ph_afp_articles":
            require(AFP_ID.fullmatch(ident) and AFP_URL.fullmatch(url),
                    "candidate_not_in_AFP_identity_or_URL_scope")
            # The AFP numeric API article ID is NOT derivable from the public
            # /news/<slug> route. This pairing remains an assertion from the
            # human-review inventory, not a proven original-source identity.
        else:
            require(MPS_ID.fullmatch(ident) and MPS_URL.fullmatch(url),
                    "candidate_not_in_MPS_identity_or_URL_scope")
            # The real source adapter provides the authoritative URL-derived
            # MPS identity. Do not silently accept a parallel URL grammar.
            from core.collection.vietnam_sources import SOURCES
            require(SOURCES[source].identity(url) == ident,
                    "MPS_url_derived_identity_mismatch")
        require(ident not in identities and url not in urls,
                "duplicate_candidate_identity_or_canonical_URL")
        identities.add(ident)
        urls.add(url)
        normalized.append((ident, url))
    return sorted(normalized)


def compare(s3, inventory, database):
    """A collision report for only the presented URLs, not entire source corpus."""
    source = inventory.get("source_slug") if type(inventory) is dict else None
    s3 = bind_s3(s3, source)
    records = validate_candidates(inventory, s3)
    # Verify schema and source registration anew against the same stable
    # file bytes. The staged S3 receipt is not an authority for DB contents.
    db = Path(database)
    # The S3 inspector rejects symlinks, live sidecars and missing indexes.
    before = frozen_database_digest_if_safe(db)
    require(before == s3["production_database_sha256"],
            "production_snapshot_differs_from_schema_preflight")
    checks, source_rows = inspect_database(db, source)
    require(checks == s3["production_schema_checks"] and
            source_rows == s3["production_source_slug_collisions"],
            "production_source_registration_or_schema_changed")
    counts = {"new_URLs": 0, "already_present_same_source": 0,
              "foreign_source_URL_collisions": 0, "orphan_source_URL_collisions": 0}
    try:
        with closing(sqlite3.connect(
                db.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as con:
            con.execute("PRAGMA query_only=ON")
            # Exactly the two columns needed for classification. Never select
            # original content, URL, document title, ID, or arbitrary notes.
            for _, url in records:
                row = con.execute(
                    "SELECT s.slug FROM articles AS a "
                    "LEFT JOIN sources AS s ON s.id=a.source_id "
                    "WHERE a.url=?", (url,)).fetchone()
                if row is None:
                    counts["new_URLs"] += 1
                elif row[0] is None:
                    counts["orphan_source_URL_collisions"] += 1
                elif row[0] == source:
                    counts["already_present_same_source"] += 1
                else:
                    counts["foreign_source_URL_collisions"] += 1
    except sqlite3.DatabaseError:
        raise CollisionRefused("production_collision_query_failed") from None
    after = frozen_database_digest_if_safe(db)
    require(after == before, "production_snapshot_changed_during_rehearsal")
    holds = []
    if source_rows:
        holds.append("source_slug_already_exists_requires_source_registration_review")
    if counts["already_present_same_source"]:
        holds.append("same_source_existing_URLs_require_idempotence_review")
    if counts["foreign_source_URL_collisions"]:
        holds.append("foreign_source_URL_collisions_require_human_resolution")
    if counts["orphan_source_URL_collisions"]:
        holds.append("orphan_source_URL_collisions_require_schema_repair")
    if s3["machine_hold_count"] or s3["machine_checkpoint_state"] != "candidate_for_human_checkpoint":
        holds.append("machine_checkpoint_and_original_review_incomplete")
    if s3["holds"]:
        holds.append("upstream_schema_or_source_holds_not_resolved")
    # The absence of URL collisions is NOT proof the inventory is complete,
    # the originals matched, the publisher authorized use, or a release passed.
    return {
        "schema": SCHEMA,
        "source_slug": source,
        "state_commit": s3["pinned_source_commit"],
        "production_database_sha256": after,
        "checkpoint_receipt_sha256": s3["checkpoint_receipt_sha256"],
        "s3_preflight_sha256": sha(canonical_json(s3)),
        "candidate_inventory_sha256": sha(canonical_json(inventory)),
        "candidate_records_supplied": len(records),
        "candidate_URL_outcomes": counts,
        "holds": sorted(set(holds)),
        "collision_rehearsal": ("needs_resolution" if holds else
                                "supplied_URLs_no_detected_collisions_not_an_admission"),
        "entire_source_corpus_inventory_verified": False,
        "AFP_numeric_id_to_public_slug_authenticated": False,
        "complete_actions_attempts_authenticated": False,
        "human_original_review_authenticated": False,
        "publisher_source_rights_approved": False,
        "private_custody_established": False,
        "schema_migration_authorized": False,
        "records_imported": 0,
        "public_projection_authorized": False,
        "record_promotion_authorized": False,
        "weekly_AI_authorized": False,
        "deployment_authorized": False,
        "database_or_output_writes": 0,
        "note": "Counts apply to supplied URLs only; no full source inventory or permission is implied.",
    }


def frozen_database_digest_if_safe(db):
    db = Path(db)
    require(db.is_file() and not db.is_symlink(), "unsafe_database_snapshot_path")
    require(100 <= db.stat().st_size <= MAX_DB_BYTES,
            "database_snapshot_size_out_of_bounds")
    require(not any(Path(str(db) + s).exists()
                    for s in ("-wal", "-shm", "-journal")),
            "database_snapshot_has_transaction_sidecars")
    try:
        return frozen_database_digest(db)
    except OSError:
        raise CollisionRefused("database_snapshot_unreadable") from None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--s3-preflight", type=Path, required=True)
    p.add_argument("--candidates", type=Path, required=True)
    p.add_argument("--database", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = compare(load_private_file(args.s3_preflight),
                         load_private_file(args.candidates),
                         args.database)
    except (AdmissionSchemaRefused, OSError, TypeError, RecursionError) as exc:
        p.exit(2, "source URL collision rehearsal refused: %s\n" %
               (str(exc) if isinstance(exc, AdmissionSchemaRefused)
                else "invalid_or_unreadable_input"))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
