#!/usr/bin/env python3
"""Read-only preserved-body parity gate for the seven B0 Singapore naval leads.

This verifies *stored archive identity and content*, NOT equality to today's
publisher-hosted page, source-use rights, factual truth, or editorial approval.
Does not print, network-fetch, distribute, or model-process official texts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reconcile_db import read_only  # noqa: E402

SCHEMA = "ipr-dossier-b0-preserved-evidence/1"
SOURCE = "sg_mindef_releases"
DESK = "singapore"
INSTITUTION = "sg_mindef"
BASE = "https://www.mindef.gov.sg/news-and-events/latest-releases/"
# IDs, dates, URLs refer to the pinned October 9 production archive.
# Phrases are *presence checks* of the stored original, not source quotations
# for publication and not evidence that a statement occurred as reported.
RECORDS = {
    4454: ("2026-07-30", "30jul26-nr2", ("rimpac", "steadfast"), "rimpac-2026"),
    4452: ("2026-08-29", "29aug26-nr", ("singapan", "japan"), "singapan-2026"),
    4466: ("2026-09-05", "5sep26-nr2", ("maritime cooperation", "navy"), "maritime-cooperation-2026"),
    4472: ("2026-09-09", "9sep26-nr", ("maritime cooperation", "navy"), "maritime-cooperation-2026"),
    4428: ("2026-09-18", "18sep26-nr2", ("singaroo", "australia"), "singaroo-2026"),
    4849: ("2026-10-02", "2oct26-nr3", ("asean", "maritime"), "asean-multilateral-2026"),
    4983: ("2026-10-08", "8oct26-nr2", ("pelican", "brunei"), "pelican-2026"),
}


class EvidenceAuditError(ValueError):
    pass


def normalized(text):
    return " ".join((text or "").casefold().split())


def verify_record(row, spec, *, valid_manifest=True):
    """Pure check, easily tested with synthetic rows; no original body emitted."""
    pub_date, slug, anchors, event_group = spec
    expected = BASE + slug + "/"
    errors = []
    if not valid_manifest:
        errors.append("source-not-enabled-in-declared-manifest")
    if row is None:
        return {"record_id": None, "event_group": event_group, "errors": ["missing-record"]}
    rid = row.get("id")
    for key, value in (
        ("source_slug", SOURCE), ("desk_id", DESK),
        ("institution_id", INSTITUTION), ("published_date", pub_date),
        ("url", expected),
    ):
        if row.get(key) != value:
            errors.append(key + "-mismatch")
    url = urlsplit(row.get("url") or "")
    if url.scheme != "https" or url.hostname != "www.mindef.gov.sg":
        errors.append("untrusted-publisher-url")
    title = row.get("title_original") or ""
    original = row.get("text_original") or ""
    lang = row.get("source_language_tag")
    if lang not in ("en", "en-SG"):
        errors.append("unexpected-language-tag")
    if not title.strip():
        errors.append("missing-original-title")
    if len(original.strip()) < 200:
        errors.append("missing-or-incomplete-original-body")
    if len(original) > 2_000_000:
        errors.append("body-size-requires-manual-review")
    text = normalized(original)
    missing = [a for a in anchors if a not in text]
    if missing:
        errors.append("stored-body-anchor-mismatch")
    if row.get("passed_relevance") == 0:
        # A negative model relevance filter is an editorial lead to inspect,
        # not a reason to rewrite or exclude a preserved original silently.
        errors.append("screened-not-selected-review-required")
    return {
        "record_id": rid,
        "event_group": event_group,
        "publisher_date": row.get("published_date"),
        "source_slug": row.get("source_slug"),
        "stored_title_sha256": hashlib.sha256(title.encode("utf-8")).hexdigest(),
        "stored_original_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "stored_original_characters": len(original),
        "title_present": bool(title.strip()),
        "all_anchors_present": not missing,
        "checks": len(anchors),
        "errors": sorted(set(errors)),
    }


def check_manifest(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("desk", {}).get("desk_id") != DESK:
        return False
    inst = {i.get("institution_id") for i in data.get("institutions", [])}
    matching = [s for s in data.get("sources", [])
                if s.get("slug") == SOURCE and s.get("enabled") is True
                and s.get("institution_id") == INSTITUTION
                and s.get("language_tag") == "en"]
    return INSTITUTION in inst and len(matching) == 1


def scan(db_path, manifest_path):
    if not db_path.is_file():
        raise EvidenceAuditError("tracked database does not exist")
    sha = hashlib.sha256(db_path.read_bytes()).hexdigest()
    manifest_ok = check_manifest(manifest_path)
    with read_only(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise EvidenceAuditError("invalid archive integrity")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise EvidenceAuditError("archive has foreign-key errors")
        try:
            rows = conn.execute("""
                SELECT a.id, a.published_date, a.url, a.title_original,
                    a.text_original, a.passed_relevance,
                    s.slug AS source_slug, s.desk_id, s.institution_id,
                    COALESCE(s.language_tag, s.language) AS source_language_tag
                FROM articles AS a
                JOIN sources AS s ON a.source_id = s.id
                WHERE a.id IN (?, ?, ?, ?, ?, ?, ?)
                ORDER BY a.id
            """, sorted(RECORDS)).fetchall()
        except sqlite3.OperationalError as e:
            raise EvidenceAuditError("archive schema missing expected provenance fields") from e
    by_id = {row["id"]: dict(row) for row in rows}
    reports = []
    for rid, spec in sorted(RECORDS.items()):
        result = verify_record(by_id.get(rid), spec, valid_manifest=manifest_ok)
        result["record_id"] = rid
        reports.append(result)
    # The same exercise can appear in multiple source releases. Count declared
    # activity groups, not source IDs; these are research labels, not proven events.
    grouping = {}
    for entry in reports:
        grouping.setdefault(entry["event_group"], []).append(entry["record_id"])
    return {
        "schema": SCHEMA,
        "snapshot_db_sha256": sha,
        "verified_as": "stored_source_reconciliation_only",
        "not_verified": [
            "live-publisher-body-byte-parity", "rights-and-full-text-reuse",
            "human-claim-interpretation", "publisher-independent-corroboration",
            "public-publication-approval",
        ],
        "manifest_source_enabled": manifest_ok,
        "selected_source_records": len(reports),
        "research_activity_groups": grouping,
        "all_stored_checks_passed": all(not x["errors"] for x in reports),
        "evidence": reports,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    parser.add_argument("--manifest", type=Path, default=ROOT / "desks/singapore/manifest.json")
    parser.add_argument("--strict", action="store_true", help="exit nonzero if any stored parity check fails")
    args = parser.parse_args(argv)
    result = scan(args.db, args.manifest)
    # Safe metadata only: never print publisher original text or private bodies.
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["all_stored_checks_passed"] or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
