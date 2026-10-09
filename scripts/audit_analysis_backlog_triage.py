#!/usr/bin/env python3
"""Read-only mechanical triage of an already-stored analysis backlog.

This is an editorial REVIEW INVENTORY, not an automated ranking, model queue,
source authority, publication approval or estimate of what deserves analysis.
Only record IDs and aggregate metadata leave the scratch SQLite connection.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH, LIVE_BACKLOG_DAYS
from scripts import audit_analysis_queue_by_source as existing
from scripts.reconcile_db import read_only

SCHEMA = "ipr-stored-backlog-triage/1"
SAMPLE_LIMIT = 20
ELIGIBLE = frozenset((
    "daily_unscored_live", "daily_unscored_archive",
    "daily_unscored_undated", "daily_pending_analysis",
))
HELD = frozenset(("held_unscored", "held_pending_analysis"))
REVIEW_LANES = (
    "ready_recent_unscored", "ready_pending_analysis",
    "ready_archive_unscored", "ready_undated_unscored",
    "missing_body_daily", "held_desk_separate_review",
    "paused_manual_review", "unknown_state_review",
)


def require(test, detail):
    if not test:
        raise existing.QueueAuditError(detail)


def review_lane(bucket, body_nonblank):
    """Mechanical readiness label, not an editorial or expenditure decision."""
    if bucket in ELIGIBLE and not body_nonblank:
        return "missing_body_daily"
    if bucket == "daily_unscored_live":
        return "ready_recent_unscored"
    if bucket == "daily_pending_analysis":
        return "ready_pending_analysis"
    if bucket == "daily_unscored_archive":
        return "ready_archive_unscored"
    if bucket == "daily_unscored_undated":
        return "ready_undated_unscored"
    if bucket in HELD:
        return "held_desk_separate_review"
    if bucket == "paused":
        return "paused_manual_review"
    if bucket == "unknown_state":
        return "unknown_state_review"
    return None


def audit(conn, *, at=None, live_days=LIVE_BACKLOG_DAYS):
    """Cross-reconcile metadata against the #280 audit in the SAME scratch DB."""
    base = existing.summarize(conn, at=at, live_days=live_days)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    require({"text_original", "processing_attempts", "published_date"}.issubset(columns),
            "backlog triage requires full article metadata schema")
    when = datetime.fromisoformat(base["snapshot_audit_generated_utc"].replace("Z", "+00:00"))
    from datetime import date
    cutoff = date.fromisoformat(base["live_unscored_cutoff_utc_day"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT a.id, a.passed_relevance, a.analyzed_at, a.processing_state,
               a.scraped_at, a.published_date, a.processing_attempts,
               a.text_original AS stored_original_body,
               length(trim(COALESCE(a.text_original, ''),
                           ' ' || char(9) || char(10) || char(11) ||
                           char(12) || char(13))) AS body_characters,
               s.slug AS source_slug, s.desk_id
          FROM articles AS a
          LEFT JOIN sources AS s ON s.id = a.source_id
         ORDER BY a.id
    """)
    queue_totals = Counter()
    lane_totals = Counter()
    stats = Counter()
    dispatch_counts = Counter()
    source_counts = {}
    samples = {lane: [] for lane in REVIEW_LANES}
    for row in rows:
        bucket = existing.categorize(row, cutoff=cutoff)
        queue_totals[bucket] += 1
        if bucket not in ELIGIBLE | HELD | {"paused", "unknown_state"}:
            continue
        body_chars = row["body_characters"]
        require(type(body_chars) is int and body_chars >= 0,
                "invalid body-character metadata")
        body_nonblank = body_chars > 0
        lane = review_lane(bucket, body_nonblank)
        require(lane is not None, "unclassified review inventory row")
        lane_totals[lane] += 1
        desk = row["desk_id"] if row["desk_id"] is not None else "__undeclared_desk__"
        slug = row["source_slug"] if row["source_slug"] is not None else "__missing_source__"
        key = (desk, slug)
        counters = source_counts.setdefault(key, Counter())
        counters[lane] += 1
        if bucket in ELIGIBLE:
            counters["daily_eligible"] += 1
            # The in-run paid queue checks Python str.strip() on the actual
            # stored original body (see the separate model-dispatch guard).
            # SQLite's ASCII-only TRIM can label a Unicode-only whitespace
            # record as 'ready' for *review*, though it is unfit for a model
            # request. Keep both measurements distinct; do not mutate the
            # historical triage lanes or hide mismatches.
            original = row["stored_original_body"]
            dispatch_ready = isinstance(original, str) and bool(original.strip())
            status = ("body_ready" if dispatch_ready else "body_withheld")
            dispatch_counts[status] += 1
            counters["daily_model_dispatch_" + status] += 1
            if not body_nonblank:
                counters["daily_missing_body"] += 1
                stats["daily_missing_body"] += 1
            retries = row["processing_attempts"]
            require(retries is None or (type(retries) is int and retries >= 0),
                    "invalid stored processing attempt count")
            if retries:
                counters["daily_has_previous_failures"] += 1
                stats["daily_has_previous_failures"] += 1
            if not row["published_date"]:
                counters["daily_missing_publication_date"] += 1
                stats["daily_missing_publication_date"] += 1
            if desk == "__undeclared_desk__":
                stats["daily_without_declared_desk"] += 1
        if len(samples[lane]) < SAMPLE_LIMIT:
            # Published date is a string from the DB, not evidence of verified
            # publisher chronology; do not include titles, bodies or URLs.
            samples[lane].append({
                "article_id": row["id"],
                "source_slug": slug,
                "desk_id": desk,
                "queue_bucket": bucket,
                "scraped_at": row["scraped_at"],
                "published_date": row["published_date"],
                "body_nonblank": body_nonblank,
                "processing_attempts": row["processing_attempts"],
            })
    require(all(queue_totals[k] == base["totals"][k] for k in existing.BUCKETS),
            "triage and canonical stored queue disagree")
    daily_lanes = (
        "ready_recent_unscored", "ready_pending_analysis",
        "ready_archive_unscored", "ready_undated_unscored", "missing_body_daily",
    )
    require(sum(lane_totals[x] for x in daily_lanes) ==
            base["stored_daily_queue_eligible"], "Daily review lanes do not reconcile")
    require(dispatch_counts["body_ready"] + dispatch_counts["body_withheld"] ==
            base["stored_daily_queue_eligible"],
            "model dispatch/body readiness does not reconcile to stored Daily queue")
    require(dispatch_counts["body_withheld"] >= lane_totals["missing_body_daily"],
            "model dispatch withheld count misses canonical blank-body records")
    require(lane_totals["held_desk_separate_review"] ==
            base["stored_held_out_of_daily"], "held desk totals do not reconcile")
    require(lane_totals["paused_manual_review"] == base["totals"]["paused"] and
            lane_totals["unknown_state_review"] == base["totals"]["unknown_state"],
            "manual review totals do not reconcile")
    sources = []
    for (desk, slug), counts in sorted(source_counts.items()):
        sources.append({
            "desk_id": desk,
            "source_slug": slug,
            "daily_eligible": counts["daily_eligible"],
            "daily_missing_body": counts["daily_missing_body"],
            "daily_model_dispatch_body_ready": counts["daily_model_dispatch_body_ready"],
            "daily_model_dispatch_body_withheld": counts["daily_model_dispatch_body_withheld"],
            "daily_has_previous_failures": counts["daily_has_previous_failures"],
            "daily_missing_publication_date": counts["daily_missing_publication_date"],
            **{lane: counts[lane] for lane in REVIEW_LANES},
        })
    require(sum(s["daily_eligible"] for s in sources) ==
            base["stored_daily_queue_eligible"], "source totals do not reconcile")
    require(sum(s["daily_model_dispatch_body_ready"] for s in sources) ==
            dispatch_counts["body_ready"] and
            sum(s["daily_model_dispatch_body_withheld"] for s in sources) ==
            dispatch_counts["body_withheld"],
            "source-level dispatch readiness does not reconcile")
    return {
        "schema": SCHEMA,
        "snapshot_audit_generated_utc": when.isoformat().replace("+00:00", "Z"),
        "input_file_sha256": None,  # Filled by snapshot() after checking the original.
        "source_queue_audit_schema": existing.SCHEMA,
        "article_rows": base["article_rows"],
        "stored_daily_queue_eligible": base["stored_daily_queue_eligible"],
        "stored_daily_model_dispatch_body_ready": dispatch_counts["body_ready"],
        "stored_daily_model_dispatch_body_withheld": dispatch_counts["body_withheld"],
        "model_dispatch_body_test_matches_python_strip": True,
        "model_dispatch_preview_not_future_run_workload": True,
        "model_dispatch_preview_not_spending_approval": True,
        "stored_held_out_of_daily": base["stored_held_out_of_daily"],
        "stored_paused": base["totals"]["paused"],
        "live_unscored_cutoff_utc_day": base["live_unscored_cutoff_utc_day"],
        "review_lanes": {lane: lane_totals[lane] for lane in REVIEW_LANES},
        "metadata_flags": {
            "daily_missing_body": stats["daily_missing_body"],
            "daily_has_previous_failures": stats["daily_has_previous_failures"],
            "daily_missing_publication_date": stats["daily_missing_publication_date"],
            "daily_without_declared_desk": stats["daily_without_declared_desk"],
        },
        "sources": sources,
        "review_samples": samples,
        "review_sample_limit_per_lane": SAMPLE_LIMIT,
        "editorial_significance_assessed": False,
        "text_extraction_verified": False,
        "publisher_dates_authenticated": False,
        "live_production_state_authenticated": False,
        "next_run_workload_known": False,
        "model_spend_authorized": False,
        "publication_authorized": False,
        "editor_delivery_authorized": False,
        "model_calls": 0,
        "writes": 0,
    }


def snapshot(path=DB_PATH, *, at=None, live_days=LIVE_BACKLOG_DAYS):
    source = Path(path)
    require(source.is_file(), "tracked SQLite input is absent")
    before = existing._snapshot_file_hashes(source)
    with read_only(source) as conn:
        result = audit(conn, at=at, live_days=live_days)
    after = existing._snapshot_file_hashes(source)
    require(before == after and "db" in after,
            "database or sidecars changed during backlog triage")
    result["input_file_sha256"] = before
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(DB_PATH))
    args = parser.parse_args(argv)
    try:
        print(json.dumps(snapshot(args.db), indent=2, sort_keys=True,
                         ensure_ascii=False))
    except (existing.QueueAuditError, OSError, sqlite3.Error, ValueError,
            TypeError) as exc:
        parser.exit(1, "Read-only backlog triage refused: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
