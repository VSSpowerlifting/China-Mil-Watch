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
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.analyzer import Analyzer, FatalAPIError  # noqa: E402
from config import ANALYSIS_MODEL, DB_PATH, RELEVANCE_MODEL  # noqa: E402
from scripts.spend_guard import preflight  # noqa: E402
from storage import db  # noqa: E402

# Share of articles that historically pass relevance and therefore incur the
# expensive analysis-model calls. Measured across the corpus (DECISION_LOG
# 2026-07-30); only this fraction costs more than a cheap relevance call.
HISTORICAL_PASS_RATE = 0.44

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill-unscored")

UNSCORED_QUERY = """
    SELECT id, url, title_original, text_original,
           length(text_original) AS n
      FROM articles
     WHERE {where}
     ORDER BY id
"""

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fetch_unscored(limit=None, since=None, until=None):
    """
    Never-scored articles, oldest id first.

    `since`/`until` bound `published_date` (YYYY-MM-DD, inclusive) so one
    edition window can be screened without paying for the whole backlog.
    `--limit` alone cannot do that: it slices from the oldest id, and a current
    edition's articles sit at the *end* of that queue.
    """
    where = ["passed_relevance IS NULL"]
    params = []
    if since:
        where.append("published_date >= ?")
        params.append(since)
    if until:
        where.append("published_date <= ?")
        params.append(until)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            UNSCORED_QUERY.format(where=" AND ".join(where)), params
        ).fetchall()
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
    ap.add_argument("--since", help="Only articles published on/after this date (YYYY-MM-DD)")
    ap.add_argument("--until", help="Only articles published on/before this date (YYYY-MM-DD)")
    ap.add_argument("--workers", type=int, default=4, help="Parallel articles (default 4)")
    ap.add_argument("--dry-run", action="store_true", help="Count only; no API calls")
    ap.add_argument("--confirm-spend", action="store_true",
                    help="Acknowledge the estimated cost (required above the threshold)")
    args = ap.parse_args()

    # A malformed date would silently select nothing and read as "backlog clear",
    # which is the one wrong answer this script must never give.
    for label, value in (("--since", args.since), ("--until", args.until)):
        if value and not DATE_RE.match(value):
            logger.error("%s must be YYYY-MM-DD, got %r", label, value)
            return 2

    window = ""
    if args.since or args.until:
        window = f" in window {args.since or '…'}→{args.until or '…'}"

    rows = fetch_unscored(args.limit, args.since, args.until)
    if not rows:
        logger.info("No unscored articles%s. Nothing to do.", window)
        return 0

    logger.info("%d never-scored article(s)%s to process (oldest id first)",
                len(rows), window)
    if args.dry_run:
        logger.info("  DRY RUN — id range %d..%d", rows[0]["id"], rows[-1]["id"])
        return 0

    # Gate the spend BEFORE spawning workers (DECISION_LOG 2026-07-31). Two
    # stages: every article pays a cheap relevance call; only the ~44% that
    # pass go on to the expensive analysis model.
    total_chars = sum(r["n"] or 0 for r in rows)
    if not preflight(
        stages=[
            # Relevance returns a score and a sentence of reasoning — output is
            # negligible next to the article it reads.
            ("relevance (all)", total_chars, RELEVANCE_MODEL, 0.02),
            ("analysis (passers)", int(total_chars * HISTORICAL_PASS_RATE),
             ANALYSIS_MODEL, 1.6),
        ],
        article_count=len(rows),
        confirmed=args.confirm_spend,
    ):
        return 2

    analyzer = Analyzer()
    tally = {
        "analyzed": 0, "rejected": 0,
        "translate_failed": 0, "summary_failed": 0, "error": 0,
    }
    aborted = None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, analyzer, r): r for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            row = futures[fut]
            try:
                aid, status, detail = fut.result()
            except FatalAPIError as exc:
                # Account-level block: cancel the batch rather than issue one
                # doomed call per remaining article.
                aborted = str(exc)
                logger.error("[%d/%d] ACCOUNT BLOCKED — %s", i, len(rows), exc)
                for pending in futures:
                    pending.cancel()
                break
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
    if aborted:
        logger.error("Screening ABORTED on an account-level API block: %s", aborted)
        logger.error(
            "%d article(s) were scored and committed; the rest were not "
            "attempted and stay unscored. Re-run once access is restored — "
            "scored articles drop out of the queue automatically.",
            tally["analyzed"] + tally["rejected"],
        )
        return 2

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
