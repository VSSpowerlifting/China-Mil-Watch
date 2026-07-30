#!/usr/bin/env python3
"""
One-off backfill for articles that were never relevance-scored.

Context (DECISION_LOG 2026-07-30): DAILY_ANALYSIS_CAP was 15 while runs scraped
~30 articles/day, and the queue was `new + pending + unscored` truncated to the
cap — so the slice never reached the backlog. ~18 articles/day were deferred and
never revisited: 1,119 accumulated over 66 days with `passed_relevance IS NULL`,
i.e. never even screened for relevance. At the historical 44% pass rate that is
roughly 487 relevant articles no edition could ever have seen.

Unlike `backfill_translations.py`, this script DOES run relevance scoring — these
articles have no prior score, so there is no audit record to preserve. It runs
the full four-task `Analyzer.analyze()` path and writes exactly what pipeline.py
writes, so a backfilled article is indistinguishable from a normally-processed one.

Relevance runs on RELEVANCE_MODEL (Haiku, cheap); only articles that pass the
threshold incur the expensive Sonnet translation.

Usage:
    .venv/bin/python scripts/backfill_unscored.py --dry-run
    .venv/bin/python scripts/backfill_unscored.py --limit 10
    .venv/bin/python scripts/backfill_unscored.py
"""

import argparse
import logging
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.analyzer import Analyzer  # noqa: E402
from config import DB_PATH  # noqa: E402
from storage import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill-unscored")

UNSCORED_QUERY = """
    SELECT id, url, title_original, text_original
      FROM articles
     WHERE passed_relevance IS NULL
     ORDER BY id
"""


def fetch_unscored(limit=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(UNSCORED_QUERY).fetchall()
    finally:
        conn.close()
    return rows[:limit] if limit else rows


def process(analyzer, row):
    """
    Score + analyze one article. Returns (id, status, detail).

    Write order mirrors pipeline.py stages 9-12: relevance is always recorded
    (even on a fail) so the article leaves the unscored pool and the decision is
    auditable; full analysis is written only when translation succeeded.
    """
    aid = row["id"]
    result = analyzer.analyze(row["title_original"] or "", row["text_original"] or "")
    if result is None:
        return aid, "error", "analyze() returned None (relevance call failed)"

    db.update_relevance(
        aid,
        score=result["relevance_score"],
        reasoning=result["relevance_reasoning"],
        passed=result["passed_relevance"],
    )

    if not result["passed_relevance"]:
        return aid, "rejected", f"score={result['relevance_score']:.2f}"

    if not result.get("title_english"):
        # Passed relevance but translation failed. Leaves analyzed_at NULL, so it
        # re-enters the queue as `pending` and is retried on a later run.
        return aid, "translate_failed", f"score={result['relevance_score']:.2f}"

    if not result.get("summary_english"):
        # A blank summary fails validate_output.py rule 6 and blocks the deploy
        # gate, so an incomplete record must not be written at all. Leaving
        # analyzed_at NULL re-queues the article instead (DECISION_LOG 2026-07-30).
        return aid, "summary_failed", f"score={result['relevance_score']:.2f}"

    db.update_analysis(
        article_id=aid,
        title_english=result.get("title_english", ""),
        text_english=result.get("text_english", ""),
        summary_english=result.get("summary_english", ""),
        is_significant=result.get("is_significant", False),
        significance_reasoning=result.get("significance_reasoning"),
        categories=result.get("categories", []),
        model_id=result["model_id"],
        prompt_version=result["prompt_version"],
    )
    flag = " ★ SIGNIFICANT" if result.get("is_significant") else ""
    return aid, "analyzed", f"score={result['relevance_score']:.2f}{flag}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, help="Process only the first N (by id)")
    ap.add_argument("--workers", type=int, default=4, help="Parallel articles (default 4)")
    ap.add_argument("--dry-run", action="store_true", help="Count only; no API calls")
    args = ap.parse_args()

    rows = fetch_unscored(args.limit)
    if not rows:
        logger.info("No unscored articles. Backlog is clear.")
        return 0

    logger.info("%d never-scored article(s) to process (oldest id first)", len(rows))
    if args.dry_run:
        logger.info("  DRY RUN — id range %d..%d", rows[0]["id"], rows[-1]["id"])
        return 0

    analyzer = Analyzer()
    tally = {
        "analyzed": 0, "rejected": 0,
        "translate_failed": 0, "summary_failed": 0, "error": 0,
    }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, analyzer, r): r for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            row = futures[fut]
            try:
                aid, status, detail = fut.result()
            except Exception as exc:  # noqa: BLE001 — one bad article must not kill the run
                tally["error"] += 1
                logger.error("[%d/%d] id=%d UNEXPECTED: %s", i, len(rows), row["id"], exc)
                continue
            tally[status] += 1
            level = logger.error if status == "error" else logger.info
            level("[%d/%d] id=%-5d %-16s %s", i, len(rows), aid, status, detail)
            if i % 50 == 0:
                logger.info("  ... progress: %s", tally)

    logger.info("─" * 56)
    logger.info(
        "Screening complete: %d analyzed, %d rejected, %d translation-failed, "
        "%d summary-failed, %d errors",
        tally["analyzed"], tally["rejected"], tally["translate_failed"],
        tally["summary_failed"], tally["error"],
    )
    if tally["translate_failed"] or tally["summary_failed"] or tally["error"]:
        logger.info("Re-run to retry; translation failures also retry on the next daily run.")
    logger.info("Run validate_output.py before publishing anything from this data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
