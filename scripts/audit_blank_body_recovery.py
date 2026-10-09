#!/usr/bin/env python3
"""Private, read-only review inventory for blank stored analysis bodies.

No URL is emitted unless an operator opts in. No URLs are fetched, records
changed, retries dispatched, models invoked or content rights adjudicated.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH, LIVE_BACKLOG_DAYS
from scripts import audit_analysis_queue_by_source as queue
from scripts.reconcile_db import read_only

SCHEMA = "ipr-blank-body-recovery-preflight/1"
GT_FIX_DATE = date(2026, 9, 16)
DAILY = frozenset(("daily_unscored_live", "daily_unscored_archive",
                   "daily_unscored_undated", "daily_pending_analysis"))
REVIEW_CAP = 100


def require(ok, why):
    if not ok:
        raise queue.QueueAuditError(why)


def review_url(raw):
    """Display-only publisher locator; drop query, fragment and credentials."""
    require(isinstance(raw, str) and len(raw) < 4096,
            "invalid stored review URL")
    value = urlsplit(raw)
    require(value.scheme in ("http", "https") and value.hostname
            and not value.username and not value.password
            and value.port in (None, 80, 443),
            "unsafe article review URL")
    return urlunsplit((value.scheme, value.hostname.lower(),
                       value.path, "", ""))


def fix_window(slug, scrape_date):
    if slug != "global_times_mil":
        return "not_applicable"
    if scrape_date is None:
        return "missing_scrape_date"
    if scrape_date < GT_FIX_DATE:
        return "before_documented_fix_date"
    return "on_or_after_documented_fix_date"


def review(conn, *, at=None, live_days=LIVE_BACKLOG_DAYS,
           include_review_urls=False):
    """Reconcile candidate membership with #280 on the same SQLite copy."""
    base = queue.summarize(conn, at=at, live_days=live_days)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    require({"text_original", "url", "published_date",
             "processing_attempts", "processing_reason"}.issubset(columns),
            "blank-body preflight requires full stored article metadata")
    cutoff = date.fromisoformat(base["live_unscored_cutoff_utc_day"])
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT a.id, a.source_id, a.passed_relevance, a.analyzed_at,
               a.processing_state, a.scraped_at, a.published_date,
               a.processing_attempts, a.processing_reason, a.url,
               length(trim(COALESCE(a.text_original, ''),
                ' ' || char(9) || char(10) || char(11) ||
                char(12) || char(13))) AS body_characters,
               s.slug AS source_slug, s.desk_id
          FROM articles a
          LEFT JOIN sources s ON s.id = a.source_id
         ORDER BY a.id
    """
    counts = Counter()
    by_source = {}
    entries = []
    all_buckets = Counter()
    for row in conn.execute(sql):
        bucket = queue.categorize(row, cutoff=cutoff)
        all_buckets[bucket] += 1
        if bucket not in DAILY or row["body_characters"] != 0:
            continue
        scraped = queue.recorded_date(row["scraped_at"])
        source = row["source_slug"] or "__missing_source__"
        desk = row["desk_id"] or "__undeclared_desk__"
        age = fix_window(source, scraped)
        label = (desk, source, age)
        counts[age] += 1
        by_source[label] = by_source.get(label, 0) + 1
        require(len(entries) < REVIEW_CAP,
                "blank-body review inventory exceeds approved candidate cap")
        attempts = row["processing_attempts"]
        require(attempts is None or (type(attempts) is int and attempts >= 0),
                "invalid recorded attempt count")
        item = {
            "article_id": row["id"],
            "desk_id": desk,
            "source_slug": source,
            "queue_bucket": bucket,
            "scraped_at": row["scraped_at"],
            "published_date_unverified": row["published_date"],
            "documented_fix_date_relation": age,
            "had_processing_attempts": bool(attempts),
            "processing_reason": row["processing_reason"],
        }
        if include_review_urls:
            item["review_url_display_only"] = review_url(row["url"])
        entries.append(item)
    require(all(all_buckets[key] == base["totals"][key]
                for key in queue.BUCKETS),
            "recovery inventory and canonical queue disagree")
    require(sum(by_source.values()) == len(entries),
            "recovery candidates/source count inconsistent")
    return {
        "schema": SCHEMA,
        "audit_generated_utc": base["snapshot_audit_generated_utc"],
        "input_file_sha256": None,
        "article_rows": base["article_rows"],
        "stored_daily_queue_eligible": base["stored_daily_queue_eligible"],
        "live_unscored_cutoff_utc_day": base["live_unscored_cutoff_utc_day"],
        "documented_global_times_fix_date": GT_FIX_DATE.isoformat(),
        "blank_body_daily_candidates": len(entries),
        "date_relations": dict(sorted(counts.items())),
        "source_date_relations": [
            {"desk_id": d, "source_slug": s, "fix_date_relation": w, "count": n}
            for (d, s, w), n in sorted(by_source.items())
        ],
        "candidate_review_receipts": entries,
        "source_urls_included_by_operator": bool(include_review_urls),
        "publisher_page_rechecked": False,
        "extraction_recovery_validated": False,
        "model_spend_authorized": False,
        "retry_authorized": False,
        "archive_rewrite_authorized": False,
        "publication_authorized": False,
        "editor_delivery_authorized": False,
        "model_calls": 0,
        "network_requests": 0,
        "writes": 0,
    }


def snapshot(path=DB_PATH, *, at=None, live_days=LIVE_BACKLOG_DAYS,
             include_review_urls=False):
    source = Path(path)
    require(source.is_file(), "original tracked SQLite file missing")
    before = queue._snapshot_file_hashes(source)
    with read_only(source) as conn:
        result = review(conn, at=at, live_days=live_days,
                        include_review_urls=include_review_urls)
    after = queue._snapshot_file_hashes(source)
    require(before == after and "db" in after,
            "original SQLite/sidecars changed during recovery preflight")
    result["input_file_sha256"] = before
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=Path(DB_PATH))
    p.add_argument("--include-review-urls", action="store_true",
                   help="explicit local opt-in to display original publisher locators "
                        "without query strings; NEVER use in public CI logs")
    args = p.parse_args(argv)
    try:
        print(json.dumps(snapshot(args.db,
                                  include_review_urls=args.include_review_urls),
                         ensure_ascii=False, sort_keys=True, indent=2))
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        p.exit(1, "Read-only blank-body recovery preflight refused: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
