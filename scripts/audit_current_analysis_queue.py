#!/usr/bin/env python3
"""Read-only, source-attributed analysis queue snapshot for IPR.

This describes ONE copied SQLite state, not historical Daily throughput, live
GitHub Actions status, available Anthropic credits, or publisher activity.
No mutations, model calls, web requests, collection or automatic retries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "pla_watch.db"  # Tracked audit input; no dotenv/model dependency.
from scripts.reconcile_db import read_only  # noqa: E402

SCHEMA = "ipr-current-analysis-queue/1"
KINDS = (
    "pending_relevance", "pending_analysis", "paused_manual_review",
    "terminal_content", "screened_out", "analyzed", "inconsistent_state",
)
REQUIRED = {
    "articles": {"id", "source_id", "passed_relevance", "analyzed_at",
                 "processing_state"},
    "sources": {"id", "slug", "desk_id"},
}


class QueueAuditError(ValueError):
    """A missing or inconsistent input must not produce misleading counts."""


def _require_schema(conn):
    for table, columns in REQUIRED.items():
        available = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        if not columns.issubset(available):
            raise QueueAuditError("schema missing %s columns: %s" %
                                  (table, sorted(columns - available)))


def _classify(passed, analyzed, state):
    if passed not in (None, 0, 1) or state not in (
            None, "", "retriable", "paused", "terminal"):
        return "inconsistent_state"
    if analyzed is not None:
        return ("analyzed" if passed == 1 and state not in ("paused", "terminal")
                else "inconsistent_state")
    if state == "paused":
        return "paused_manual_review"
    if state == "terminal":
        return "terminal_content"
    if passed is None:
        return "pending_relevance"
    if passed == 1:
        return "pending_analysis"
    return "screened_out"


def audit(conn):
    """Count actual stored records by immutable source identity in one read."""
    conn.row_factory = sqlite3.Row
    _require_schema(conn)
    rows = conn.execute("""
        SELECT a.id AS article_id, a.passed_relevance, a.analyzed_at,
               a.processing_state, s.slug AS source_slug, s.desk_id
          FROM articles AS a
          LEFT JOIN sources AS s ON s.id = a.source_id
         ORDER BY a.id
    """).fetchall()
    counters = Counter()
    sources = {}
    fingerprint = hashlib.sha256()
    last_id = 0
    for row in rows:
        ident = row["article_id"]
        slug = row["source_slug"]
        desk = row["desk_id"]
        if not isinstance(ident, int) or ident <= last_id:
            raise QueueAuditError("invalid/duplicate article identity")
        if not isinstance(slug, str) or not slug:
            raise QueueAuditError("article has an unattributed source")
        if desk is not None and not isinstance(desk, str):
            raise QueueAuditError("invalid source desk identity")
        last_id = ident
        kind = _classify(row["passed_relevance"], row["analyzed_at"],
                         row["processing_state"])
        counters[kind] += 1
        key = (desk, slug)
        bucket = sources.setdefault(key, Counter())
        bucket[kind] += 1
        # Digest input dispositions, not confidential bodies or source URLs.
        identity = [ident, desk, slug, row["passed_relevance"],
                    row["analyzed_at"], row["processing_state"]]
        fingerprint.update(json.dumps(identity, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8") + b"\n")

    def counts(counter):
        return {kind: int(counter[kind]) for kind in KINDS}

    details = [
        {
            "desk_id": desk,
            "source_slug": slug,
            "counts": counts(counter),
            "stored_records": sum(counter.values()),
        }
        for (desk, slug), counter in sorted(
            sources.items(), key=lambda p: (p[0][0] or "", p[0][1]))
    ]
    total = sum(counters.values())
    if total != len(rows) or sum(x["stored_records"] for x in details) != total:
        raise QueueAuditError("per-source analysis counts do not reconcile")

    return {
        "schema": SCHEMA,
        "scope": "single_copied_production_database_not_live_actions",
        "queue_state_digest_sha256": fingerprint.hexdigest(),
        "max_article_id": last_id if rows else None,
        "stored_records": total,
        "counts": counts(counters),
        "automatic_queue_candidates": (
            counters["pending_relevance"] + counters["pending_analysis"]),
        "held_out_of_automatic_queue": (
            counters["paused_manual_review"] + counters["terminal_content"]),
        "sources_without_desk_assignment": sorted(
            {slug for (desk, slug) in sources if desk is None}),
        "sources": details,
        "limits": [
            "A single read-only copied SQLite view, not today's live pipeline queue or run log.",
            "Queue candidates use the same relevance/state predicates as the resume queries; actual pipeline selection, per-desk routing and daily cap can differ.",
            "Paused retry-budget records require human review; terminal content records are not retryable.",
            "Historical Daily backlog figures are different snapshots and must not be subtracted from these counts.",
            "No model spend, successful collection, publisher silence, desk activation, or editorial publication is authorized.",
        ],
        "collection_performed": False,
        "analysis_performed": False,
        "model_spend_authorized": False,
        "publication_authorized": False,
    }


def _destination(value):
    target = Path(value).expanduser()
    if target.is_symlink() or target.exists():
        raise QueueAuditError("output must be a new file")
    target = target.resolve()
    if target == ROOT.resolve() or ROOT.resolve() in target.parents:
        raise QueueAuditError("output must be outside the repository")
    if not target.parent.is_dir():
        raise QueueAuditError("output parent must already exist")
    return target


def _write_new(path, payload):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(DB_PATH))
    parser.add_argument("--out", type=Path, required=True,
                        help="new private JSON file outside repository")
    args = parser.parse_args(argv)
    try:
        target = _destination(args.out)
        if not args.db.is_file():
            raise QueueAuditError("read-only production SQLite input missing")
        with read_only(args.db) as conn:
            result = audit(conn)
        _write_new(target, result)
    except (QueueAuditError, sqlite3.Error, OSError, ValueError) as exc:
        parser.error(str(exc))
    print("Read-only source-attributed queue audit written (no model or collection).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
