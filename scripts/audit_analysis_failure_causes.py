#!/usr/bin/env python3
"""Read-only failure/extraction diagnostic for stored analysis-queue records.

Observes article metadata; neither retries nor judges a government publication.
Only aggregate counts and bounded article ID receipts are emitted. All SQLite
reads happen on a temporary copy; DB, journal and output trees stay unchanged.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH, LIVE_BACKLOG_DAYS
from core import processing_state as state_rules
from scripts import audit_analysis_queue_by_source as queue
from scripts.reconcile_db import read_only

SCHEMA = "ipr-analysis-failure-review/1"
SAMPLE_LIMIT = 12
DAILY = frozenset(("daily_unscored_live", "daily_unscored_archive",
                   "daily_unscored_undated", "daily_pending_analysis"))
COUNTERS = ("daily_eligible", "daily_blank_body", "daily_prior_attempts",
            "daily_blank_and_prior_attempts", "daily_unknown_failure_reason",
            "daily_blank_recent_scrapes", "daily_blank_archive_scrapes",
            "daily_blank_undated_scrapes",
            "daily_missing_publication_date", "paused", "terminal",
            "state_inconsistency")
SAMPLES = ("daily_blank_body", "daily_prior_attempts", "state_inconsistency",
           "paused")


def require(condition, explanation):
    if not condition:
        raise queue.QueueAuditError(explanation)


def inconsistent(row, state):
    """Flag contradictions without changing eligibility or dispositions."""
    passed = row["passed_relevance"]
    analyzed = row["analyzed_at"] is not None
    reason = row["processing_reason"]
    if analyzed and passed != 1:
        return True
    if state == "paused" and reason not in state_rules.PAUSED_REASONS:
        return True
    if state == "terminal" and reason not in state_rules.TERMINAL_REASONS:
        return True
    if state == "retriable" and reason not in state_rules.RETRIABLE_REASONS:
        return True
    if state == "" and reason:
        return True
    return False


def examine(conn, *, at=None, live_days=LIVE_BACKLOG_DAYS):
    """Share the *same scratch connection* with #280's canonical queue audit."""
    base = queue.summarize(conn, at=at, live_days=live_days)
    needed = {"text_original", "processing_reason", "processing_attempts",
              "published_date"}
    fields = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    require(needed.issubset(fields),
            "failure review requires current article processing metadata")
    cutoff = date.fromisoformat(base["live_unscored_cutoff_utc_day"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
       SELECT a.id, a.passed_relevance, a.analyzed_at, a.processing_state,
              a.processing_reason, a.processing_attempts, a.scraped_at,
              a.published_date,
              length(trim(COALESCE(a.text_original, ''),
                ' ' || char(9) || char(10) || char(11) ||
                char(12) || char(13))) AS body_chars,
              s.slug AS source_slug, s.desk_id
         FROM articles a
         LEFT JOIN sources s ON s.id = a.source_id
        ORDER BY a.id
    """)
    source_stats = {}
    totals = Counter()
    causes = Counter()
    samples = {kind: [] for kind in SAMPLES}
    observed = Counter()
    for row in rows:
        bucket = queue.categorize(row, cutoff=cutoff)
        observed[bucket] += 1
        desk = row["desk_id"] if row["desk_id"] is not None else "__undeclared_desk__"
        slug = row["source_slug"] if row["source_slug"] is not None else "__missing_source__"
        counter = source_stats.setdefault((desk, slug), Counter())
        reason = row["processing_reason"]
        require(reason is None or type(reason) is str,
                "unsupported processing reason metadata")
        attempts = row["processing_attempts"]
        require(attempts is None or (type(attempts) is int and attempts >= 0),
                "invalid stored attempt count")
        record_state = row["processing_state"] or ""
        flags = set()
        if inconsistent(row, record_state):
            flags.add("state_inconsistency")
        if bucket in DAILY:
            flags.add("daily_eligible")
            if not row["body_chars"]:
                flags.add("daily_blank_body")
                scraped = queue.recorded_date(row["scraped_at"])
                if scraped is None:
                    flags.add("daily_blank_undated_scrapes")
                elif scraped >= cutoff:
                    flags.add("daily_blank_recent_scrapes")
                else:
                    flags.add("daily_blank_archive_scrapes")
            if attempts and attempts > 0:
                flags.add("daily_prior_attempts")
                if reason not in state_rules.REASONS:
                    flags.add("daily_unknown_failure_reason")
                causes[reason or "__missing_reason__"] += 1
            if not row["published_date"]:
                flags.add("daily_missing_publication_date")
            if "daily_blank_body" in flags and "daily_prior_attempts" in flags:
                flags.add("daily_blank_and_prior_attempts")
        if bucket in ("paused", "terminal"):
            flags.add(bucket)
        for flag in flags:
            counter[flag] += 1
            totals[flag] += 1
            if flag in samples and len(samples[flag]) < SAMPLE_LIMIT:
                samples[flag].append({
                    "article_id": row["id"],
                    "desk_id": desk,
                    "source_slug": slug,
                    "queue_bucket": bucket,
                    "processing_state": record_state or None,
                    "processing_reason": reason,
                    "processing_attempts": attempts,
                    "scraped_at": row["scraped_at"],
                })
    require(all(observed[b] == base["totals"][b] for b in queue.BUCKETS),
            "failure review disagrees with canonical queue classification")
    require(totals["daily_eligible"] == base["stored_daily_queue_eligible"]
            and totals["paused"] == base["totals"]["paused"]
            and totals["terminal"] == base["totals"]["terminal"],
            "failure review queue/paused/terminal totals do not reconcile")
    require(totals["daily_blank_and_prior_attempts"] <=
            min(totals["daily_blank_body"], totals["daily_prior_attempts"]),
            "invalid overlap accounting")
    require(sum(totals[k] for k in (
                "daily_blank_recent_scrapes", "daily_blank_archive_scrapes",
                "daily_blank_undated_scrapes")) == totals["daily_blank_body"],
            "blank body scrape-age accounting does not reconcile")
    sources = []
    for (desk, slug), counts in sorted(source_stats.items()):
        if not any(counts.values()):
            continue
        sources.append({
            "desk_id": desk, "source_slug": slug,
            **{key: counts[key] for key in COUNTERS},
        })
    for key in COUNTERS:
        require(sum(r[key] for r in sources) == totals[key],
                "source-level failure count disagrees: " + key)
    return {
        "schema": SCHEMA,
        "audit_generated_utc": base["snapshot_audit_generated_utc"],
        "queue_audit_schema": queue.SCHEMA,
        "article_rows": base["article_rows"],
        "stored_daily_queue_eligible": base["stored_daily_queue_eligible"],
        "stored_held_out_of_daily": base["stored_held_out_of_daily"],
        "totals": {key: totals[key] for key in COUNTERS},
        "recorded_failure_reasons_on_daily_queue": dict(sorted(causes.items())),
        "sources": sources,
        "samples_by_flag": samples,
        "sample_limit_per_flag": SAMPLE_LIMIT,
        "input_file_sha256": None,
        "input_file_identity_not_signed": True,
        "content_verdicts_authenticated": False,
        "root_causes_established": False,
        "live_production_state_authenticated": False,
        "retry_authorized": False,
        "model_spend_authorized": False,
        "publication_authorized": False,
        "editor_delivery_authorized": False,
        "model_calls": 0,
        "writes": 0,
    }


def snapshot(path=DB_PATH, *, at=None, live_days=LIVE_BACKLOG_DAYS):
    source = Path(path)
    require(source.is_file(), "tracked SQLite input missing")
    before = queue._snapshot_file_hashes(source)
    with read_only(source) as conn:
        report = examine(conn, at=at, live_days=live_days)
    after = queue._snapshot_file_hashes(source)
    require(before == after and "db" in after,
            "database or sidecars changed during failure review")
    report["input_file_sha256"] = before
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(DB_PATH))
    args = parser.parse_args(argv)
    try:
        print(json.dumps(snapshot(args.db), ensure_ascii=False, sort_keys=True,
                         indent=2))
    except (queue.QueueAuditError, OSError, sqlite3.Error,
            TypeError, ValueError) as exc:
        parser.exit(1, "Read-only analysis failure review refused: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
