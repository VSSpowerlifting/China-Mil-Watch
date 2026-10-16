"""Source-scoped, read-only production admission *schema* rehearsal.

This is not an importer, readiness attestation, source-rights decision or
release path. It never reads shadow article content, production article bodies
or original URLs. It cannot create/write a database or touch output/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

SCHEMA = "ipr-country-source-admission-schema-preflight/1"
CHECKPOINT_SCHEMA = "ipr-country-desk-checkpoint-intake/1"
MAX_REPORT_BYTES = 2_000_000
MAX_DB_BYTES = 8_000_000_000
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SOURCE_CONTRACTS = {
    "ph_afp_articles": ("philippines_afp", "philippines", "shadow/ph-afp", "candidate_architecture_only"),
    "vn_mps_foreign_affairs_vi": ("vietnam_three_ministry_sources", "vietnam",
                                   "shadow/vietnam-mps-foreign-affairs", "candidate_architecture_only"),
    "vn_moit_energy_vi": ("vietnam_three_ministry_sources", "vietnam",
                           "shadow/vietnam-moit-energy", "source_rights_hold"),
    "vn_moit_foundational_industry_vi": ("vietnam_three_ministry_sources", "vietnam",
                                         "shadow/vietnam-moit-foundational-industry", "source_rights_hold"),
}
VIETNAM_FAMILIES = frozenset(k for k in SOURCE_CONTRACTS if k.startswith("vn_"))
REQUIRED_SOURCE_FIELDS = frozenset({
    "id", "slug", "display_name", "base_url", "language", "desk_id",
    "institution_id", "language_tag", "authority_tier", "enabled",
})
REQUIRED_ARTICLE_FIELDS = frozenset({
    "id", "url", "content_hash", "source_id", "title_original",
    "text_original", "published_date", "scraped_at", "processing_state",
})
AUTHORITY_FALSE = (
    "human_checkpoint_authenticated", "complete_Actions_history_authenticated",
    "source_reuse_rights_approved", "private_custody_approved",
    "C13_satisfied", "production_eligible", "public_records_admitted",
    "weekly_model_eligible", "desk_activated", "deployment_authorized",
)
NEXT_STAGES = (
    "complete_human_Day7_Day14_Day30_and_30_consecutive_collecting_days",
    "publisher_original_and_rights_action_review_per_source",
    "independent_failed_and_rerun_Actions_attempts_evidence",
    "approved_private_evidence_custody_and_generation_binding",
    "separate_collision_review_for_canonical_URL_and_existing_source_row",
    "separate_reversible_copy_only_ingest_on_private_disposable_database",
    "separate_public_projection_and_private_content_leak_validation",
    "explicit_owner_release_PR_and_live_deployment_review",
)


class AdmissionSchemaRefused(ValueError):
    """Safe fixed diagnostic; never emit publisher bodies, titles or URLs."""


def ensure(ok, code):
    if not ok:
        raise AdmissionSchemaRefused(code)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical_day(value):
    ensure(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
           "invalid_checkpoint_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise AdmissionSchemaRefused("invalid_checkpoint_date") from None
    ensure(parsed.isoformat() == value, "invalid_checkpoint_date")
    return parsed


def unique_object(pairs):
    obj = {}
    for k, v in pairs:
        ensure(k not in obj, "duplicate_json_key")
        obj[k] = v
    return obj


def load_checkpoint(path):
    path = Path(path)
    ensure(path.is_file() and not path.is_symlink(), "invalid_checkpoint_file")
    ensure(0 < path.stat().st_size <= MAX_REPORT_BYTES, "checkpoint_file_size_invalid")
    try:
        receipt = json.loads(path.read_text("utf-8"), object_pairs_hook=unique_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(
                                 AdmissionSchemaRefused("nonfinite_json_number")))
    except AdmissionSchemaRefused:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise AdmissionSchemaRefused("checkpoint_json_invalid") from None
    ensure(type(receipt) is dict, "checkpoint_not_an_object")
    return receipt


def bind_checkpoint(checkpoint, source):
    ensure(type(checkpoint) is dict and
           checkpoint.get("schema") == CHECKPOINT_SCHEMA,
           "not_a_country_desk_checkpoint_receipt")
    ensure(source in SOURCE_CONTRACTS, "undeclared_source_family")
    expected_desk, desk, branch, policy = SOURCE_CONTRACTS[source]
    ensure(checkpoint.get("desk") == expected_desk,
           "wrong_desk_checkpoint_receipt")
    for key in AUTHORITY_FALSE:
        ensure(checkpoint.get(key) is False, "checkpoint_authority_claim")
    ensure(checkpoint.get("source_or_output_writes") == 0 and
           type(checkpoint.get("source_or_output_writes")) is int,
           "checkpoint_reported_writes")
    ensure(checkpoint.get("machine_status") in (
        "candidate_for_human_checkpoint", "machine_evidence_incomplete_or_held"),
        "unknown_machine_checkpoint_state")
    holds = checkpoint.get("machine_holds")
    external = checkpoint.get("external_holds")
    ensure(type(holds) is list and len(holds) <= 128 and
           all(type(x) is str and 0 < len(x) <= 200 for x in holds)
           and len(holds) == len(set(holds)),
           "malformed_machine_holds")
    ensure(type(external) is list and len(external) <= 128 and
           "written_owner_source_admission_and_release_decisions" in external
           and "separate_source_action_rights_and_robots_review" in external,
           "missing_external_release_holds")
    as_of = checkpoint.get("as_of_utc")
    observed_day = canonical_day(as_of)
    # Do not turn a forged pre-checkpoint status into a mechanically clean
    # source-registration rehearsal. The full source review remains external.
    earliest = ("2026-10-13" if source == "ph_afp_articles" else
                {"day-07": "2026-10-14", "day-14": "2026-10-21",
                 "day-30": "2026-11-06"}.get(checkpoint.get("checkpoint")))
    ensure(earliest is not None and observed_day >= canonical_day(earliest),
           "source_checkpoint_not_yet_due")
    evidence = checkpoint.get("machine_evidence")
    ensure(type(evidence) is dict, "missing_checkpoint_machine_evidence")
    if source == "ph_afp_articles":
        ensure(checkpoint.get("checkpoint") == "day-07", "wrong_AFP_checkpoint")
        frozen = evidence.get("state_commit")
        ensure(type(frozen) is str and SHA40.fullmatch(frozen),
               "invalid_AFP_state_commit")
        ensure(evidence.get("window") == ["2026-10-07", "2026-10-13"],
               "wrong_AFP_seven_slot_window")
        ensure(type(evidence.get("verified_ledger_slots")) is int and
               0 <= evidence["verified_ledger_slots"] <= 7 and
               type(evidence.get("positive_Actions_matches")) is int and
               0 <= evidence["positive_Actions_matches"] <= evidence["verified_ledger_slots"],
               "invalid_AFP_machine_counts")
    else:
        ensure(checkpoint.get("checkpoint") in ("day-07", "day-14", "day-30"),
               "wrong_Vietnam_checkpoint")
        rows = evidence.get("sources")
        ensure(type(rows) is list and len(rows) == 3 and
               all(type(row) is dict for row in rows), "invalid_Vietnam_source_cohort")
        by = {row.get("slug"): row for row in rows}
        ensure(len(by) == 3 and set(by) == VIETNAM_FAMILIES,
               "missing_or_duplicate_Vietnam_source")
        for slug, row in by.items():
            ensure(type(row.get("state_commit")) is str and
                   SHA40.fullmatch(row["state_commit"]) and
                   type(row.get("checkpoint_reached_elapsed_time_only")) is bool,
                   "invalid_Vietnam_source_state")
        frozen = by[source]["state_commit"]
    # Only a source and its pinned SHA are allowed through, not copied note,
    # URL, article text, human identity, or operator-supplied rights claim.
    return {
        "source": source, "desk": desk, "state_branch": branch,
        "state_commit": frozen, "source_policy": policy,
        "machine_state": checkpoint["machine_status"],
        "machine_hold_count": len(holds),
        "checkpoint_date": as_of,
        "checkpoint_label": checkpoint["checkpoint"],
        "receipt_sha256": sha(canonical_json(checkpoint)),
    }


def frozen_database_digest(path):
    """Hash whole frozen SQLite bytes without selecting or decoding a record."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def table_columns(conn, table):
    return {row[1] for row in conn.execute("PRAGMA table_info('%s')" % table)}


def has_unique_column(conn, table, column):
    for row in conn.execute("PRAGMA index_list('%s')" % table):
        # Partial indexes cannot guarantee complete canonical identities.
        if not row[2] or (len(row) >= 5 and row[4]):
            continue
        index_name = row[1]
        columns = [x[2] for x in conn.execute(
            "PRAGMA index_info('%s')" % index_name.replace("'", "''"))]
        if columns == [column]:
            return True
    return False


def inspect_database(path, source):
    path = Path(path)
    ensure(path.is_file() and not path.is_symlink(),
           "invalid_production_database_file")
    size = path.stat().st_size
    ensure(100 <= size <= MAX_DB_BYTES, "production_database_size_invalid")
    ensure(not any(Path(str(path) + suffix).exists()
                   for suffix in ("-wal", "-shm", "-journal")),
           "production_database_has_live_sidecars")
    db = path.resolve()
    try:
        with closing(sqlite3.connect(
                db.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
            conn.execute("PRAGMA query_only=ON")
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            ensure("sources" in tables and "articles" in tables,
                   "production_schema_missing_base_tables")
            source_fields = table_columns(conn, "sources")
            article_fields = table_columns(conn, "articles")
            src_unique = has_unique_column(conn, "sources", "slug")
            url_unique = has_unique_column(conn, "articles", "url")
            if "slug" in source_fields:
                existing = conn.execute(
                    "SELECT COUNT(*) FROM sources WHERE slug=?", (source,)).fetchone()[0]
            else:
                existing = None
            signature = {
                "source_required_columns_present":
                    REQUIRED_SOURCE_FIELDS.issubset(source_fields),
                "article_required_columns_present":
                    REQUIRED_ARTICLE_FIELDS.issubset(article_fields),
                "unique_source_slug_index": src_unique,
                "unique_article_canonical_url_index": url_unique,
            }
            signature["schema_compatible"] = all(signature.values())
            return signature, existing
    except sqlite3.DatabaseError:
        raise AdmissionSchemaRefused("production_database_read_failed") from None


def plan(source, checkpoint, database):
    binding = bind_checkpoint(checkpoint, source)
    # A later collision audit must be able to prove it used this identical
    # production snapshot. Never confuse the checkpoint source Git SHA
    # with the unrelated production database identity.
    before = frozen_database_digest(database)
    schema, existing = inspect_database(database, source)
    after = frozen_database_digest(database)
    ensure(before == after, "production_database_changed_during_preflight")
    holds = []
    if not schema["schema_compatible"]:
        holds.append("production_schema_contract_not_satisfied")
    if existing is None:
        holds.append("production_source_lookup_unavailable")
    elif existing:
        holds.append("production_source_slug_already_registered_review_collision")
    if binding["machine_state"] != "candidate_for_human_checkpoint":
        holds.append("source_machine_checkpoint_unreconciled_or_held")
    if binding["machine_hold_count"]:
        holds.append("source_machine_checkpoint_has_unresolved_holds")
    if binding["source_policy"] == "source_rights_hold":
        holds.append("MOIT_source_rights_and_robots_remain_held")
    return {
        "schema": SCHEMA,
        "candidate_source_slug": source,
        "desk_slug": binding["desk"],
        "source_state_branch": binding["state_branch"],
        "pinned_source_commit": binding["state_commit"],
        "checkpoint_date": binding["checkpoint_date"],
        "checkpoint_label": binding["checkpoint_label"],
        "checkpoint_receipt_sha256": binding["receipt_sha256"],
        "production_database_sha256": after,
        "production_schema_checks": schema,
        "production_source_slug_collisions": existing,
        "machine_checkpoint_state": binding["machine_state"],
        "machine_hold_count": binding["machine_hold_count"],
        "schema_preflight": ("structure_compatible_no_admission" if not holds
                             else "blocked_before_any_ingest"),
        "holds": holds,
        "next_separate_engineering_stages": list(NEXT_STAGES),
        "source_rights_authorized": False,
        "human_review_authenticated": False,
        "record_collisions_audited": False,
        "private_evidence_migration_authorized": False,
        "candidate_records_imported": 0,
        "production_write_authorized": False,
        "public_record_projection_authorized": False,
        "website_or_model_release_authorized": False,
        "registry_or_manifest_changes_authorized": False,
        "database_or_output_writes": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, choices=sorted(SOURCE_CONTRACTS))
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path,
                        help="consistent read-only SQLite snapshot; no WAL/SHM")
    args = parser.parse_args(argv)
    try:
        report = plan(args.source, load_checkpoint(args.checkpoint), args.database)
    except (AdmissionSchemaRefused, OSError, TypeError, OverflowError) as exc:
        parser.exit(2, "country admission schema preflight refused: %s\n" % (
            str(exc) if isinstance(exc, AdmissionSchemaRefused) else
            "unreadable_or_invalid_input"))
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
