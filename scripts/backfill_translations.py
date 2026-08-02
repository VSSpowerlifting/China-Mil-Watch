#!/usr/bin/env python3
"""
One-off backfill for articles stranded by the translation token cap.

Context (DECISION_LOG 2026-07-30): `Analyzer.translate()` was capped at
max_tokens=4000, so every long article was truncated mid-JSON and never
written. 163 of 697 relevant articles were affected — 100% of those over
5000 Chinese characters. The cap is fixed; this script clears the backlog
those failures left behind.

What it does NOT do: re-run relevance scoring. Those scores and reasonings
are the existing audit record for each article and are preserved verbatim.
This script only fills in what the truncation destroyed — translation,
summary, categories, significance.

Usage:
    .venv/bin/python scripts/backfill_translations.py --dry-run
    .venv/bin/python scripts/backfill_translations.py --limit 3
    .venv/bin/python scripts/backfill_translations.py
"""

import argparse
import logging
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.analyzer import AnalysisError, Analyzer, FatalAPIError  # noqa: E402
from analysis.prompts import PROMPT_VERSION  # noqa: E402
from config import ANALYSIS_MODEL, DB_PATH  # noqa: E402
from scripts.spend_guard import preflight  # noqa: E402
from storage import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill")

STUCK_QUERY = """
    SELECT id, title_original, text_original, length(text_original) AS n
      FROM articles
     WHERE passed_relevance = 1
       AND (title_english IS NULL OR title_english = '')
     ORDER BY n DESC
"""


def fetch_stuck(limit=None):
    """Longest first — those are the ones the cap actually broke."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(STUCK_QUERY).fetchall()
    finally:
        conn.close()
    return rows[:limit] if limit else rows


def process(analyzer, row):
    """Translate + summarize + categorize one article. Returns (id, ok, detail)."""
    aid = row["id"]
    # FatalAPIError propagates: it means the account is blocked, so the caller
    # must stop the whole batch rather than record this as one failed article.
    try:
        title_en, body_en = analyzer.translate(
            row["title_original"] or "", row["text_original"] or ""
        )
    except FatalAPIError:
        raise
    except AnalysisError as exc:
        return aid, False, f"translation: {exc}"

    # A summary is MANDATORY before writing: validate_output.py rule 6 fails the
    # deploy gate on any analyzed article with a blank summary. Writing the
    # translation without one produces a record that reads as complete but
    # breaks the gate — which is exactly what happened on the first run of this
    # script when the API spend limit hit mid-batch (DECISION_LOG 2026-07-30).
    # Bail instead: analyzed_at stays NULL, so the article is retried later and
    # the translation is re-derived rather than half-written.
    try:
        summary = analyzer.summarize(title_en, body_en)
    except FatalAPIError:
        raise
    except AnalysisError as exc:
        return aid, False, f"summary: {exc}"
    if not summary:
        return aid, False, "summary: model returned an empty summary"

    # Categories are not gated by the validator, so a failure here is logged and
    # the record is still written — an uncategorized article is degraded, not broken.
    categories, is_significant, reason = [], False, None
    try:
        categories, is_significant, reason = analyzer.categorize(title_en, body_en)
    except AnalysisError as exc:
        logger.warning("  [%d] categorization failed: %s", aid, exc)

    db.update_analysis(
        article_id=aid,
        title_english=title_en,
        text_english=body_en,
        summary_english=summary,
        is_significant=is_significant,
        significance_reasoning=reason,
        categories=categories,
        model_id=ANALYSIS_MODEL,
        prompt_version=PROMPT_VERSION,
    )
    flag = " ★ SIGNIFICANT" if is_significant else ""
    return aid, True, f"{len(body_en)} chars{flag}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, help="Process only the N longest stuck articles")
    ap.add_argument("--workers", type=int, default=3, help="Parallel articles (default 3)")
    ap.add_argument("--dry-run", action="store_true", help="List what would run; no API calls")
    ap.add_argument("--confirm-spend", action="store_true",
                    help="Acknowledge the estimated cost (required above the threshold)")
    args = ap.parse_args()

    rows = fetch_stuck(args.limit)
    if not rows:
        logger.info("No stuck articles. Backlog is clear.")
        return 0

    logger.info("%d stuck article(s) to process (longest first)", len(rows))
    if args.dry_run:
        for r in rows:
            logger.info("  DRY RUN id=%-5d %6d chars  %.50s", r["id"], r["n"], r["title_original"])
        return 0

    # Gate the spend BEFORE spawning workers (DECISION_LOG 2026-07-31).
    total_chars = sum(r["n"] or 0 for r in rows)
    if not preflight(
        # Translate + summarize + categorize all run on the analysis model, and
        # every article here has already passed relevance — so unlike screening
        # this is a single-stage cost. The 1.6 ratio covers the summary and
        # category calls on top of the translation itself.
        stages=[("translate+summarize", total_chars, ANALYSIS_MODEL, 1.6)],
        article_count=len(rows),
        confirmed=args.confirm_spend,
    ):
        return 2

    analyzer = Analyzer()
    ok, failed = 0, []
    aborted = None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, analyzer, r): r for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            row = futures[fut]
            try:
                aid, success, detail = fut.result()
            except FatalAPIError as exc:
                # Account-level block: every remaining article would fail the
                # same way. Cancel the rest instead of burning the queue.
                aborted = str(exc)
                logger.error("[%d/%d] ACCOUNT BLOCKED — %s", i, len(rows), exc)
                for pending in futures:
                    pending.cancel()
                break
            except Exception as exc:  # noqa: BLE001 — one bad article must not kill the run
                failed.append((row["id"], f"unexpected: {exc}"))
                logger.error("[%d/%d] id=%d UNEXPECTED: %s", i, len(rows), row["id"], exc)
                continue
            if success:
                ok += 1
                logger.info("[%d/%d] id=%-5d ok — %s", i, len(rows), aid, detail)
            else:
                failed.append((aid, detail))
                logger.error("[%d/%d] id=%-5d FAILED — %s", i, len(rows), aid, detail)

    logger.info("─" * 52)
    if aborted:
        logger.error("Backfill ABORTED on an account-level API block: %s", aborted)
        logger.error(
            "%d article(s) completed and are committed; the rest were not "
            "attempted and remain in the backlog. Re-run once access is "
            "restored — completed articles are skipped automatically.", ok,
        )
        return 2

    logger.info("Backfill complete: %d succeeded, %d failed", ok, len(failed))
    for aid, detail in failed:
        logger.info("  still stuck: id=%d — %s", aid, detail)
    logger.info("Re-run to retry failures; run validate_output.py before publishing.")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
