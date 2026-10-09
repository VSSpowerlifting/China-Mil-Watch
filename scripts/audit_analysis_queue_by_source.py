#!/usr/bin/env python3
"""Source-attributed, strictly read-only snapshot of the *stored* analysis queue.

Reports the queue reproducible from the checked-out SQLite snapshot. Not a
model runner, collection audit, live production monitor or budget forecast.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH, LIVE_BACKLOG_DAYS
from processing.screening import profile_for_desk
from scripts.reconcile_db import read_only

SCHEMA = "ipr-analysis-queue-by-source/1"
BUCKETS = (
    "daily_unscored_live", "daily_unscored_archive",
    "daily_unscored_undated", "daily_pending_analysis",
    "held_unscored", "held_pending_analysis",
    "paused", "terminal", "completed_analysis",
    "relevance_rejected", "unknown_state",
)
PERMITTED_STATES = frozenset(("", "retriable", "paused", "terminal"))


class QueueAuditError(ValueError):
    """Unsupported database, state or queue input must never look healthy."""


def require(ok, message):
    if not ok:
        raise QueueAuditError(message)


def recorded_date(raw):
    if raw is None or raw == "":
        return None
    require(type(raw) is str,
            "article scrape date has unsupported type")
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise QueueAuditError("article scrape date is invalid") from exc


def categorize(row, *, cutoff):
    """Mirror storage.db's two resume queries and pipeline's daily desk gate.

    New records inserted *during* a future pipeline run are unavailable in this
    stored snapshot. Do not equate this number with a future run's pre-cap queue.
    """
    state = row["processing_state"] or ""
    require(type(state) is str, "processing state must be text or NULL")
    if state not in PERMITTED_STATES:
        return "unknown_state"
    if state == "paused":
        return "paused"
    if state == "terminal":
        return "terminal"
    if row["analyzed_at"] is not None:
        return "completed_analysis"
    passed = row["passed_relevance"]
    if passed == 0:
        return "relevance_rejected"
    if passed is None:
        pending = "unscored"
    elif passed == 1:
        pending = "pending_analysis"
    else:
        raise QueueAuditError("unexpected relevance verdict outside 0/1/NULL")
    if not profile_for_desk(row["desk_id"]).daily_queue:
        return "held_" + pending
    if pending == "pending_analysis":
        return "daily_pending_analysis"
    scraped = recorded_date(row["scraped_at"])
    if scraped is None:
        return "daily_unscored_undated"
    return "daily_unscored_live" if scraped >= cutoff else "daily_unscored_archive"


def summarize(conn, *, at=None, live_days=LIVE_BACKLOG_DAYS):
    """Audit one connection, including scratch-copy WAL recovery by caller."""
    instant = at or datetime.now(timezone.utc)
    require(isinstance(instant, datetime) and
            instant.tzinfo is not None and
            instant.utcoffset() is not None,
            "audit timestamp must be timezone-aware")
    instant = instant.astimezone(timezone.utc)
    require(type(live_days) is int and 1 <= live_days <= 365,
            "configured live backlog days outside reviewed range")
    cutoff = (instant - timedelta(days=live_days)).date()
    required = {
        "articles": {"id", "source_id", "passed_relevance", "analyzed_at",
                     "processing_state", "scraped_at"},
        "sources": {"id", "slug", "desk_id"},
    }
    for table, columns in required.items():
        observed = {item[1] for item in conn.execute(
            "PRAGMA table_info(%s)" % table)}
        require(columns.issubset(observed),
                "analysis audit requires current %s schema" % table)
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT a.id, a.passed_relevance, a.analyzed_at,
               a.processing_state, a.scraped_at,
               s.slug AS source_slug, s.desk_id
          FROM articles AS a
          LEFT JOIN sources AS s ON s.id = a.source_id
         ORDER BY a.id
    """
    totals = Counter({key: 0 for key in BUCKETS})
    by_source = {}
    count = 0
    for row in conn.execute(sql):
        count += 1
        slug = row["source_slug"] if row["source_slug"] is not None else "__missing_source__"
        desk = row["desk_id"] if row["desk_id"] is not None else "__undeclared_desk__"
        # A slug reused by two desks would destroy source attribution.
        key = (desk, slug)
        if key not in by_source:
            by_source[key] = Counter({b: 0 for b in BUCKETS})
        name = categorize(row, cutoff=cutoff)
        by_source[key][name] += 1
        totals[name] += 1

    require(sum(totals.values()) == count and
            sum(sum(v.values()) for v in by_source.values()) == count,
            "analysis queue accounting did not reconcile")
    daily_unscored = sum(totals[k] for k in BUCKETS if k.startswith("daily_unscored_"))
    daily_pending = totals["daily_pending_analysis"]
    held = totals["held_unscored"] + totals["held_pending_analysis"]
    sources = []
    for (desk, slug), counts in sorted(by_source.items()):
        sources.append({
            "desk_id": desk, "source_slug": slug,
            "daily_model_queue_eligible_by_desk": (
                profile_for_desk(None if desk == "__undeclared_desk__" else desk).daily_queue
            ),
            **{bucket: counts[bucket] for bucket in BUCKETS},
            "rows_total": sum(counts.values()),
        })
    return {
        "schema": SCHEMA,
        "snapshot_audit_generated_utc": instant.isoformat().replace("+00:00", "Z"),
        "live_unscored_cutoff_utc_day": cutoff.isoformat(),
        "live_backlog_days_configured_at_audit": live_days,
        "article_rows": count,
        "sources": sources,
        "totals": {bucket: totals[bucket] for bucket in BUCKETS},
        "stored_daily_queue_eligible": daily_unscored + daily_pending,
        "stored_daily_unscored": daily_unscored,
        "stored_daily_pending_analysis": daily_pending,
        "stored_held_out_of_daily": held,
        "historical_run_completeness_established": False,
        "next_run_new_articles_known": False,
        "future_queue_cap_outcome_known": False,
        "live_production_state_authenticated": False,
        "collection_executed_authenticated": False,
        "model_spend_authorized": False,
        "source_rights_cleared": False,
        "publication_authorized": False,
        "editor_delivery_authorized": False,
        "model_calls": 0, "writes": 0,
    }


def snapshot(path=DB_PATH, *, at=None, live_days=LIVE_BACKLOG_DAYS):
    source = Path(path)
    require(source.is_file(), "tracked SQLite input is absent")
    # SHA of the concrete input files; not an independent attestable git SHA.
    hashes = {}
    for label, filename in (("db", source), ("wal", Path(str(source) + "-wal")),
                            ("shm", Path(str(source) + "-shm"))):
        if filename.exists():
            with filename.open("rb") as stream:
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                hashes[label] = digest.hexdigest()
    with read_only(source) as conn:
        report = summarize(conn, at=at, live_days=live_days)
    report["input_file_sha256"] = hashes
    report["input_file_identity_not_signed"] = True
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=Path(DB_PATH),
                   help="local pinned SQLite file; never opened for writing")
    args = p.parse_args(argv)
    try:
        print(json.dumps(snapshot(args.db), indent=2, sort_keys=True))
    except (QueueAuditError, sqlite3.Error, OSError, TypeError,
            ValueError) as exc:
        p.exit(1, "Read-only analysis queue audit refused: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
