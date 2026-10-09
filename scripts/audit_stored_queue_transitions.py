#!/usr/bin/env python3
"""Compare two pinned *stored* SQLite analysis queues without altering either.

This does not authenticate production, infer model execution, or estimate cost.
Same UTC cutoff is used for both sides to avoid invented age-based transitions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import LIVE_BACKLOG_DAYS
from scripts import audit_analysis_queue_by_source as queue
from scripts.reconcile_db import read_only

SCHEMA = "ipr-stored-queue-transition/1"
DAILY = frozenset((
    "daily_unscored_live", "daily_unscored_archive",
    "daily_unscored_undated", "daily_pending_analysis",
))
SAMPLE_LIMIT = 12


def require(condition, message):
    if not condition:
        raise queue.QueueAuditError(message)


def record_index(conn, report):
    cutoff = datetime.strptime(
        report["live_unscored_cutoff_utc_day"], "%Y-%m-%d").date()
    required = {
        "articles": {"id", "url", "source_id", "passed_relevance",
                     "analyzed_at", "processing_state", "scraped_at"},
        "sources": {"id", "slug", "desk_id"},
    }
    for table, cols in required.items():
        have = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        require(cols <= have, "transition audit requires current %s schema" % table)
    conn.row_factory = sqlite3.Row
    rows = {}
    categories = Counter()
    sources = {}
    for row in conn.execute("""
        SELECT a.id, a.url, a.passed_relevance, a.analyzed_at,
               a.processing_state, a.scraped_at,
               s.slug AS source_slug, s.desk_id
        FROM articles a LEFT JOIN sources s ON s.id = a.source_id
        ORDER BY a.id
    """):
        require(type(row["id"]) is int and row["id"] not in rows,
                "duplicate or invalid article identity")
        require(type(row["url"]) is str and bool(row["url"]),
                "article has missing or non-text canonical URL")
        bucket = queue.categorize(row, cutoff=cutoff)
        desk = row["desk_id"] or "__undeclared_desk__"
        slug = row["source_slug"] or "__missing_source__"
        key = (desk, slug)
        categories[bucket] += 1
        sources.setdefault(key, Counter())[bucket] += 1
        rows[row["id"]] = {
            "id": row["id"],
            "url_fingerprint": hashlib.sha256(row["url"].encode("utf-8")).hexdigest(),
            "desk_id": desk, "source_slug": slug, "bucket": bucket,
            "daily": bucket in DAILY,
        }
    require(len(rows) == report["article_rows"]
            and all(categories[k] == report["totals"][k] for k in queue.BUCKETS),
            "indexed rows disagree with canonical queue")
    return rows, sources


def load(path, instant, days):
    with read_only(path) as conn:
        summary = queue.summarize(conn, at=instant, live_days=days)
        rows, sources = record_index(conn, summary)
    return summary, rows, sources


def snapshot_pair(before, after, *, at=None, live_days=LIVE_BACKLOG_DAYS):
    instant = datetime.now(timezone.utc) if at is None else at
    require(type(instant) is datetime and instant.tzinfo is not None
            and instant.utcoffset() is not None,
            "comparison UTC time must be timezone-aware")
    instant = instant.astimezone(timezone.utc)
    left, right = Path(before), Path(after)
    require(left.is_file() and right.is_file(), "both stored SQLite inputs must exist")
    require(left.resolve() != right.resolve(),
            "comparison requires two distinct stored snapshot paths")
    h0 = queue._snapshot_file_hashes(left)
    h1 = queue._snapshot_file_hashes(right)
    a, ai, asrc = load(left, instant, live_days)
    b, bi, bsrc = load(right, instant, live_days)
    require(h0 == queue._snapshot_file_hashes(left)
            and h1 == queue._snapshot_file_hashes(right)
            and "db" in h0 and "db" in h1,
            "one or both SQLite inputs changed during two-snapshot comparison")
    require(h0 != h1, "two inputs have identical bytes; no time-separated evidence")
    old, new = set(ai), set(bi)
    common = old & new
    added, removed = new-old, old-new
    for ident in common:
        require(ai[ident]["url_fingerprint"] == bi[ident]["url_fingerprint"],
                "same article id has conflicting canonical URL; cannot infer identity")
    from_counts = Counter()
    to_counts = Counter()
    transitions = Counter()
    exiting = Counter()
    changed_source = 0
    for ident in common:
        arow, brow = ai[ident], bi[ident]
        if arow["bucket"] != brow["bucket"]:
            transitions[(arow["bucket"], brow["bucket"])] += 1
        if arow["daily"] and not brow["daily"]:
            exiting[brow["bucket"]] += 1
        if (arow["desk_id"], arow["source_slug"]) != (
                brow["desk_id"], brow["source_slug"]):
            changed_source += 1
    for ident in added:
        to_counts[bi[ident]["bucket"]] += 1
    for ident in removed:
        from_counts[ai[ident]["bucket"]] += 1
    old_daily = a["stored_daily_queue_eligible"]
    new_daily = b["stored_daily_queue_eligible"]
    added_daily = sum(bi[i]["daily"] for i in added)
    removed_daily = sum(ai[i]["daily"] for i in removed)
    entered_daily = sum(not ai[i]["daily"] and bi[i]["daily"] for i in common)
    left_daily = sum(ai[i]["daily"] and not bi[i]["daily"] for i in common)
    require(new_daily - old_daily ==
            added_daily - removed_daily + entered_daily - left_daily,
            "Daily queue change does not reconcile to article identities")
    require(sum(to_counts.values()) == len(added)
            and sum(from_counts.values()) == len(removed)
            and sum(transitions.values()) <= len(common),
            "stored article transitions do not reconcile")
    source_keys = set(asrc) | set(bsrc)
    sources = []
    for desk, slug in sorted(source_keys):
        old_source = asrc.get((desk, slug), Counter())
        new_source = bsrc.get((desk, slug), Counter())
        sources.append({
            "desk_id": desk, "source_slug": slug,
            "before_daily_eligible": sum(old_source[k] for k in DAILY),
            "after_daily_eligible": sum(new_source[k] for k in DAILY),
            "before_rows": sum(old_source.values()),
            "after_rows": sum(new_source.values()),
        })
    require(sum(s["before_daily_eligible"] for s in sources) == old_daily
            and sum(s["after_daily_eligible"] for s in sources) == new_daily,
            "source-level Daily accounting does not reconcile")
    return {
        "schema": SCHEMA,
        "comparison_at_utc": instant.isoformat().replace("+00:00", "Z"),
        "same_cutoff_for_both": a["live_unscored_cutoff_utc_day"],
        "before": {"input_sha256": h0, "article_rows": a["article_rows"],
                   "daily_eligible": old_daily, "desk_held": a["stored_held_out_of_daily"]},
        "after": {"input_sha256": h1, "article_rows": b["article_rows"],
                  "daily_eligible": new_daily, "desk_held": b["stored_held_out_of_daily"]},
        "identity_comparison": {
            "shared_ids": len(common), "added_ids": len(added),
            "removed_ids": len(removed),
            "records_with_source_reassignment": changed_source,
            "changed_queue_bucket": sum(transitions.values()),
        },
        "daily_queue_change": {
            "net_stored_change": new_daily - old_daily,
            "new_ids_in_daily": added_daily,
            "removed_ids_previously_daily": removed_daily,
            "shared_ids_entered_daily": entered_daily,
            "shared_ids_left_daily": left_daily,
        },
        "added_record_buckets": dict(sorted(to_counts.items())),
        "removed_record_buckets": dict(sorted(from_counts.items())),
        "shared_record_bucket_transitions": [
            {"from": old, "to": new, "count": count}
            for (old, new), count in sorted(transitions.items())
        ],
        "shared_daily_exit_destinations": dict(sorted(exiting.items())),
        "per_source": sources,
        "review_id_samples": {
            "added": sorted(added)[:SAMPLE_LIMIT],
            "removed": sorted(removed)[:SAMPLE_LIMIT],
            "source_reassigned": sorted(
                i for i in common if
                (ai[i]["desk_id"], ai[i]["source_slug"]) !=
                (bi[i]["desk_id"], bi[i]["source_slug"]))[:SAMPLE_LIMIT],
        },
        "sample_limit_per_category": SAMPLE_LIMIT,
        "input_hashes_not_signed": True,
        "snapshot_ancestry_authenticated": False,
        "historical_model_execution_authenticated": False,
        "successful_analysis_jobs_inferred": False,
        "cost_or_budget_established": False,
        "collection_executed_authenticated": False,
        "live_production_state_authenticated": False,
        "model_spend_authorized": False,
        "publication_authorized": False,
        "editor_delivery_authorized": False,
        "network_requests": 0, "model_calls": 0, "writes": 0,
    }


def utc_instant(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise queue.QueueAuditError("invalid comparison UTC instant") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
            "comparison instant requires UTC offset")
    return parsed.astimezone(timezone.utc)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before-db", required=True, type=Path)
    p.add_argument("--after-db", required=True, type=Path)
    p.add_argument("--at-utc", help="same explicit clock for both queue snapshots")
    args = p.parse_args(argv)
    try:
        result = snapshot_pair(args.before_db, args.after_db,
                               at=utc_instant(args.at_utc) if args.at_utc else None)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (queue.QueueAuditError, sqlite3.Error, OSError,
            ValueError, TypeError) as exc:
        p.exit(1, "Read-only queue transition audit refused: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
