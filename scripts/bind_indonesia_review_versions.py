"""Bind Indonesia's private 31-item review roster to preserved source versions.

Read-only evidence preparation, not review completion or a publication grant.
The existing private reader verifies exact Git/SQLite original-source content
in memory first. Only SHA-256 digests and existing metadata leave this process.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import tempfile
from pathlib import Path

from scripts import private_country_desk_reader as reader
from scripts.prepare_indonesia_reference_review_queue import HELD_PATH

ROOT = Path(__file__).resolve().parents[1]
PIN = "0595c6677be24f8f0f33aecb28eec0050e36e8f9"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SCHEMA = "ipr-id-kemhan-source-version-review-manifest/1"
HELD_ID = "kemhan:" + HELD_PATH
ROW_FIELDS = frozenset((
    "publication_date", "title_original", "official_url",
    "source_identity", "first_seen_run", "disposition",
    "independent_human_review_complete", "publisher_body_reuse_authorized",
    "eligible_for_public_corpus",
))
SOURCE_COLUMNS = (
    "source_identity", "source_slug", "url", "title_original",
    "published_date", "first_seen_run", "language_tag",
    "text_original", "content_sha256", "capture_sha256",
)
REVIEW_FIELDS = (
    "source_identity", "source_version_sha256", "official_url",
    "publication_date", "disposition", "source_geography_hold",
    "reviewer_name", "reviewed_at_utc", "original_language_checked",
    "publisher_date_and_title_checked", "factual_claims_checked",
    "publisher_link_use_review", "source_body_reuse_review",
    "translation_reuse_review", "media_reuse_review", "review_notes",
)


class IndonesiaReviewHold(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise IndonesiaReviewHold(reason)


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def build_manifest(queue, originals):
    """Reject partial, altered, or already-approved queues without exporting text."""
    need(type(queue) is dict and queue.get("schema") ==
         "ipr-indonesia-private-review-queue/1" and
         queue.get("state_commit") == PIN and
         queue.get("source_family") == "id_kemhan_news" and
         queue.get("stored_originals") == 31 and
         queue.get("public_renderer_consumes_queue") is False and
         queue.get("independent_human_review_completed") is False and
         queue.get("source_reuse_approved") is False and
         queue.get("public_corpus_admitted") is False and
         queue.get("counts") == {
             "official_link_already_public_not_reviewed": 15,
             "hold_publisher_geography_inconsistent": 1,
             "new_source_review_candidate": 15,
         } and type(queue.get("rows")) is list and
         len(queue["rows"]) == 31 and type(originals) is list and
         len(originals) == 31, "frozen_review_cohort_or_scope_changed")
    by_id = {}
    for raw in originals:
        need(type(raw) is dict and set(SOURCE_COLUMNS) <= set(raw),
             "pinned_original_schema_changed")
        sid = raw["source_identity"]
        need(type(sid) is str and sid not in by_id and
             sid.startswith("kemhan:/") and
             raw["source_slug"] == "id_kemhan_news" and
             raw["language_tag"] == "id" and
             type(raw["text_original"]) is str and bool(raw["text_original"].strip())
             and type(raw["content_sha256"]) is str and
             HEX64.fullmatch(raw["content_sha256"]) is not None and
             hashlib.sha256(raw["text_original"].encode("utf-8")).hexdigest() ==
             raw["content_sha256"] and
             type(raw["capture_sha256"]) is str and
             HEX64.fullmatch(raw["capture_sha256"]) is not None,
             "missing_or_mutated_archived_original_version")
        by_id[sid] = raw
    records, seen = [], set()
    for row in queue["rows"]:
        need(type(row) is dict and set(row) == ROW_FIELDS,
             "review_queue_fields_or_private_scope_changed")
        sid = row["source_identity"]
        need(type(sid) is str and sid not in seen and sid in by_id and
             row["independent_human_review_complete"] is False and
             row["publisher_body_reuse_authorized"] is False and
             row["eligible_for_public_corpus"] is False,
             "duplicate_unrecognized_or_prepublished_review_item")
        original = by_id[sid]
        need(row["official_url"] == original["url"] and
             row["publication_date"] == original["published_date"] and
             row["first_seen_run"] == original["first_seen_run"] and
             row["title_original"] ==
             " ".join(original["title_original"].split()),
             "review_queue_does_not_match_archived_original")
        held = sid == HELD_ID
        if held:
            need(row["disposition"] == "hold_publisher_geography_inconsistent",
                 "known_publisher_geography_hold_removed")
        else:
            need(row["disposition"] in (
                "official_link_already_public_not_reviewed",
                "new_source_review_candidate"),
                "unknown_indonesia_release_disposition")
        title_sha = hashlib.sha256(
            original["title_original"].encode("utf-8")).hexdigest()
        source = {
            "source_identity": sid,
            "official_url": original["url"],
            "publication_date": original["published_date"],
            "first_seen_run": original["first_seen_run"],
            "source_commit": PIN,
            "original_title_sha256": title_sha,
            "original_text_sha256": original["content_sha256"],
            "archived_capture_sha256": original["capture_sha256"],
        }
        records.append({
            "source_identity": sid,
            "official_url": row["official_url"],
            "publication_date": row["publication_date"],
            "disposition": row["disposition"],
            "known_geography_hold": held,
            "original_title_sha256": title_sha,
            "original_text_sha256": original["content_sha256"],
            "archived_capture_sha256": original["capture_sha256"],
            "source_version_sha256": digest(source),
            "human_review_authenticated": False,
            "rights_or_publication_authorized": False,
        })
        seen.add(sid)
    need(seen == set(by_id) and
         sum(r["known_geography_hold"] for r in records) == 1 and
         next(r for r in records if r["known_geography_hold"])["source_identity"] ==
         HELD_ID, "incomplete_or_unheld_original_manifest")
    records.sort(key=lambda r: r["source_identity"])
    return {
        "schema": SCHEMA,
        "source_family": "id_kemhan_news",
        "immutable_source_commit": PIN,
        "originals_version_bound": 31,
        "known_geography_holds": 1,
        "human_review_authenticated": False,
        "archive_original_bytes_exported": False,
        "archived_capture_bytes_independently_authenticated": False,
        "publisher_reuse_rights_approved": False,
        "production_admission_authorized": False,
        "public_site_changed": False,
        "records": records,
        "manifest_sha256": digest(records),
    }


def pinned_originals(source_repo, commit):
    need(commit == PIN, "not_the_approved_31_original_git_commit")
    # Existing source reader checks commit, clock, publisher URL, language,
    # source body digest and typed official issuer for every archived original.
    items, count = reader._read_snapshot(
        "id_kemhan_news", source_repo, commit, "")
    need(count == len(items) == 31,
         "pinned_reader_not_exactly_31_verified_originals")
    data = reader.git(source_repo, "show", PIN + ":state/shadow.db",
                      cap=reader.MAX_DB_BYTES)
    need(data.startswith(b"SQLite format 3\x00"),
         "verified_git_object_is_not_sqlite")
    with tempfile.TemporaryDirectory(prefix="ipr-id-version-review-") as td:
        filename = Path(td) / "source.db"
        filename.write_bytes(data)
        with sqlite3.connect(filename.as_uri()+"?mode=ro&immutable=1",
                             uri=True) as con:
            con.row_factory = sqlite3.Row
            need(con.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                 "original_database_integrity_failed")
            fields = ",".join(SOURCE_COLUMNS)
            originals = [
                dict(x) for x in con.execute(
                    "SELECT " + fields + " FROM shadow_records")
            ]
        need(len(originals) == 31, "unexpected_shadow_record_count")
        return originals


def write_private(manifest, directory):
    directory = Path(directory)
    need(directory.is_absolute() and directory.is_dir() and
         not directory.is_symlink() and
         ROOT != directory.resolve() and
         ROOT not in directory.resolve().parents and
         not (directory / "original_version_manifest.json").exists() and
         not (directory / "review_decisions_UNSIGNED.csv").exists(),
         "private_artifact_destination_invalid")
    (directory / "original_version_manifest.json").open(
        "x", encoding="utf-8").write(
            json.dumps(manifest, ensure_ascii=False, indent=2,
                       sort_keys=True) + "\n")
    with (directory / "review_decisions_UNSIGNED.csv").open(
        "x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(REVIEW_FIELDS)
        for row in manifest["records"]:
            fields = {
                "source_identity": row["source_identity"],
                "source_version_sha256": row["source_version_sha256"],
                "official_url": row["official_url"],
                "publication_date": row["publication_date"],
                "disposition": row["disposition"],
                "source_geography_hold":
                    "YES — MUST REMAIN HELD" if row["known_geography_hold"]
                    else "NO",
            }
            # Never pre-populate an approval or human review identity. Harden
            # metadata written to spreadsheets against formula injection.
            writer.writerow([
                ("'" + str(fields.get(k, "")) if
                 str(fields.get(k, "")).startswith(("=", "+", "-", "@"))
                 else fields.get(k, "")) for k in REVIEW_FIELDS
            ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-repo", type=Path, required=True)
    parser.add_argument("--state-commit", required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    spec = "id_kemhan_news,%s,%s" % (args.state_repo, args.state_commit)
    slug, repo, commit = reader.parse_input(spec)
    need(slug == "id_kemhan_news" and commit == PIN,
         "invalid_indonesia_source")
    need(args.queue.is_file() and args.queue.parent.resolve() ==
         args.out.resolve(), "queue_must_be_in_same_private_directory")
    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    manifest = build_manifest(queue, pinned_originals(repo, commit))
    write_private(manifest, args.out)
    # Public CI logs reveal only counts/status, not original URLs/titles.
    print(json.dumps({
        "schema": manifest["schema"],
        "originals_version_bound": 31,
        "known_geography_holds": 1,
        "human_review_authenticated": False,
        "production_admission_authorized": False,
        "manifest_sha256": manifest["manifest_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
