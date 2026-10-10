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


# Freeze extracted directly from the tracked October 9 archive as attested in
# Actions #38011850371. These are stored UTF-8 field digests, NOT current live
# publisher bytes and NOT permissions or an editorial approval.
# record_id: (original-title SHA-256, stored-original-body SHA-256)
FROZEN_SHA256 = {
    4428: ("32735782d12cd31a7613d6acd21aa83e1c270a24cfa996e04a139ed771979761",
           "414935d1bcf719d117e6c3342cc0fdb955a2580bd5d16aac523e610e06f1ae29"),
    4452: ("93755fdca78aba593bf4d5881915f6e7f3f08bcdb22369b05206d6a61c206467",
           "3f84c0d0c26a900f34b068c4c5f29967fd2864ea41821051323b180e24a15b02"),
    4454: ("10350cb9b2f0d12b9d9dd40f521114c7fb67a87cf16ec0fe7874bef5f1da69d9",
           "e7ba778857ecf0fea62e95a7920864650a138227f07f1ae4c52b4edb0d7a8bab"),
    4466: ("d9e2a8fa63ffbb5254098f438600901be05f15698543dead06222d21bd44be5a",
           "ef18634fd29ff57894eb35d35339cd60bf6b1d2339fe6038875bc7b5bea49878"),
    4472: ("be2bcd573a98bf0f6ce8724673769b409b01fc0d1283f913c615675bd7516c22",
           "0e4d1a580c8267e9f2b486f742c17e95551761943cac53013fa4f292dc87d078"),
    4849: ("86c69325e667ffb5a38fba14544c42c598b601a83f0793808e8c2d7c5be432cb",
           "ced43fd969de5301f2297ec64867b7a2a88e2870b071d743a540ac1e1cb2ef77"),
    4983: ("6f79d6441401a6516bb1511cd13c32df5e5a26efcc95d12bf55cfbf24966a41a",
           "7eabfff1c6cd89df11309b2ec956dcafd7a4e0b46620c1e368466de7a7b2ccce"),
}


class EvidenceAuditError(ValueError):
    pass


def normalized(text):
    return " ".join((text or "").casefold().split())


def verify_record(row, spec, *, valid_manifest=True, expected_record_id=None,
                  frozen_sha256=None):
    """Pure check, easily tested with synthetic rows; no original body emitted."""
    pub_date, slug, anchors, event_group = spec
    expected = BASE + slug + "/"
    errors = []
    review_holds = []
    if not valid_manifest:
        errors.append("source-not-enabled-in-declared-manifest")
    if row is None:
        return {"record_id": None, "event_group": event_group,
                "errors": ["missing-record"], "review_holds": []}
    rid = row.get("id")
    if expected_record_id is not None and (type(rid) is not int or rid != expected_record_id):
        errors.append("record-id-mismatch")
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
    title_sha = hashlib.sha256(title.encode("utf-8")).hexdigest()
    original_sha = hashlib.sha256(original.encode("utf-8")).hexdigest()
    if frozen_sha256 is not None:
        if title_sha != frozen_sha256[0]:
            errors.append("frozen-original-title-drift")
        if original_sha != frozen_sha256[1]:
            errors.append("frozen-original-body-drift")
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
        review_holds.append("screened-not-selected-human-review-required")
    return {
        "record_id": rid,
        "event_group": event_group,
        "publisher_date": row.get("published_date"),
        "source_slug": row.get("source_slug"),
        "stored_title_sha256": title_sha,
        "stored_original_sha256": original_sha,
        "stored_original_characters": len(original),
        "title_present": bool(title.strip()),
        "all_anchors_present": not missing,
        "checks": len(anchors),
        "errors": sorted(set(errors)),
        "review_holds": sorted(set(review_holds)),
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
    # Context helps distinguish an isolated deliberate screening rejection
    # from a widespread migration/default-value artifact. No model text output.
    with read_only(db_path) as conn:
        cohort = {
            ("pending" if flag is None else "selected" if flag == 1 else "not_selected"): count
            for flag, count in conn.execute("""
                SELECT a.passed_relevance, COUNT(*)
                FROM articles AS a JOIN sources AS s ON s.id = a.source_id
                WHERE s.slug = ?
                GROUP BY a.passed_relevance
            """, (SOURCE,)).fetchall()
        }
        finding = conn.execute("""
            SELECT relevance_score IS NOT NULL, relevance_reasoning IS NOT NULL,
                   model_id IS NOT NULL, analyzed_at IS NOT NULL
            FROM articles WHERE id = 4428
        """).fetchone()
    if finding is None:
        raise EvidenceAuditError("screening review record missing")
    screening_context = {
        "singapore_source_dispositions": cohort,
        "record_4428_score_present": bool(finding[0]),
        "record_4428_reasoning_present": bool(finding[1]),
        "record_4428_model_id_present": bool(finding[2]),
        "record_4428_analysis_timestamp_present": bool(finding[3]),
    }
    by_id = {row["id"]: dict(row) for row in rows}
    if set(FROZEN_SHA256) != set(RECORDS):
        raise EvidenceAuditError("frozen source digests do not exactly cover candidate record IDs")
    reports = []
    for rid, spec in sorted(RECORDS.items()):
        result = verify_record(by_id.get(rid), spec, valid_manifest=manifest_ok,
                               expected_record_id=rid, frozen_sha256=FROZEN_SHA256[rid])
        result["record_id"] = rid
        reports.append(result)
    # The same exercise can appear in multiple source releases. Count declared
    # activity groups, not source IDs; these are research labels, not proven events.
    grouping = {}
    for entry in reports:
        grouping.setdefault(entry["event_group"], []).append(entry["record_id"])
        if entry["record_id"] == 4849:
            # This *one source* discusses two separately identified multilateral
            # activities; do not mistake two themes for two independent sources.
            grouping.setdefault("admm-plus-maritime-security-jca-2026", []).append(4849)
    return {
        "schema": SCHEMA,
        "snapshot_db_sha256": sha,
        "verified_as": "frozen_stored_source_parity_only",
        "not_verified": [
            "live-publisher-body-byte-parity", "rights-and-full-text-reuse",
            "human-claim-interpretation", "publisher-independent-corroboration",
            "public-publication-approval",
        ],
        "manifest_source_enabled": manifest_ok,
        "screening_context": screening_context,
        "selected_source_records": len(reports),
        "research_activity_groups": grouping,
        "research_activity_count": len(grouping),
        "all_stored_checks_passed": all(not x["errors"] for x in reports),
        "editorial_screening_holds": sum(bool(x["review_holds"]) for x in reports),
        "screening_clear_for_editorial_use": all(not x["review_holds"] for x in reports),
        "evidence": reports,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    parser.add_argument("--manifest", type=Path, default=ROOT / "desks/singapore/manifest.json")
    parser.add_argument("--strict", action="store_true", help="exit nonzero if any stored identity/body parity check fails")
    parser.add_argument("--require-no-editorial-holds", action="store_true",
                        help="fail if any record has outstanding editorial-screening holds")
    args = parser.parse_args(argv)
    result = scan(args.db, args.manifest)
    # Safe metadata only: never print publisher original text or private bodies.
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    if args.strict and not result["all_stored_checks_passed"]:
        return 1
    if args.require_no_editorial_holds and not result["screening_clear_for_editorial_use"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
