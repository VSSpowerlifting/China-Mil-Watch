"""
PLA Watch — daily pipeline runner.

Execution stages:
  1.  Initialize DB (create tables and seed data if absent)
  2.  Open a scrape_run record
  3.  Scrape source(s) for the target date
  4.  Normalize metadata and compute content hashes
  5.  Deduplicate against the DB
  6.  Keyword relevance pre-filter (free, fast)
  7.  Store all keyword-passing articles to DB
  8.  Store keyword-rejected articles with passed_relevance=0 (audit trail)
  9.  LLM relevance scoring on stored candidates (Analyzer.score_relevance)
  10. Update DB with relevance scores; skip fully analyzed articles
  11. Full analysis on passing articles: translate → (summary ∥ categorize)
  12. Update DB with analysis results
  13. Complete the scrape_run record with summary stats

The pipeline is resumable: re-running with the same --date will skip
articles already in the DB (dedup) and articles with analyzed_at already
set (pending-analysis query), so a crashed mid-analysis run picks up where
it left off.

Usage:
    python pipeline.py                        # All sources, today
    python pipeline.py --source pla_daily     # Single source
    python pipeline.py --date 2026-05-06      # Specific date
    python pipeline.py --dry-run              # No DB writes, no API calls
"""

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from config import (
    ANTHROPIC_API_KEY, BACKLOG_RESERVE_FRACTION, CACHE_DIR, DAILY_ANALYSIS_CAP,
    DB_PATH, LIVE_BACKLOG_DAYS, OUTPUT_DIR, ANALYSIS_MODEL, RELEVANCE_MODEL,
)
from processing.dedup import dedup_articles
from processing.deduplicator import deduplicate
from processing.metadata import normalize_article
from processing.relevance import (
    apply_relevance_threshold,
    keyword_filter,
    llm_relevance_check,
)
from core.collection import status as collection_status
from core.collection.contract import CollectionWindow
from core.collection.health import aggregate_status, human_report
from core.registry import get_registry
from storage import db

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("pipeline")

# ── Source registry ───────────────────────────────────────────────────────────

# Sources come from desk manifests (`desks/*/manifest.json`), not from a list of
# imported classes. This module no longer names a single China scraper: adding,
# disabling or re-pointing a source is a configuration edit, and a second desk
# needs no change here at all.
#
# `SCRAPERS` survives only as a name lookup, for the CLI's `--source` choices.
#
# It used to also expose `SCRAPERS[slug](target_date=…)`, mimicking the old
# slug -> scraper-class mapping. Review found that interface was a lie: it
# returned an *adapter* (which has no `.scrape()`) and silently discarded
# `target_date`. Nothing in the repository called it — so rather than
# implementing a legacy contract with no consumers, the shim was narrowed to
# the operations it can honour truthfully. Anything needing to collect goes
# through `get_registry().get_adapter(slug).collect(window)`.

def available_slugs() -> list:
    """Every source slug any desk manifest declares."""
    return get_registry().slugs


class _SourceSlugView:
    """
    Read-only view of the configured source slugs.

    Supports exactly `slug in SCRAPERS`, `.keys()`, iteration and `len()`.
    Subscripting deliberately raises with an explanatory message rather than
    returning something that looks like a scraper and is not.
    """

    def __contains__(self, slug: str) -> bool:
        return slug in get_registry()

    def keys(self):
        return available_slugs()

    def __iter__(self):
        return iter(available_slugs())

    def __len__(self) -> int:
        return len(available_slugs())

    def __getitem__(self, slug):
        raise TypeError(
            "SCRAPERS is a slug view, not a scraper-class mapping. "
            "Use get_registry().get_adapter(%r).collect(window) instead." % (slug,)
        )


SCRAPERS = _SourceSlugView()


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run(
    sources:         list[str],
    target_date:     date,
    dry_run:         bool = False,
    no_analysis:     bool = False,
) -> None:
    start_time = datetime.now()
    logger.info("=== PLA Watch pipeline — %s ===", target_date.isoformat())
    logger.info("Sources: %s | dry-run: %s", sources, dry_run)
    if no_analysis:
        logger.warning(
            "--no-analysis: scraping and storing only. Articles keep "
            "passed_relevance NULL and drain as backlog on a later run."
        )
    logger.info(
        "Models: relevance=%s  analysis=%s  | cap=%d",
        RELEVANCE_MODEL, ANALYSIS_MODEL, DAILY_ANALYSIS_CAP,
    )
    if dry_run:
        logger.info("DRY RUN — no DB writes, no API calls")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    db.init_db()
    run_id = None if dry_run else db.start_scrape_run()

    all_scraped: list[dict] = []
    errors:      list[str]  = []

    # ── Stage 3: Scrape ───────────────────────────────────────────────────────
    #
    # Every source now produces an explicit structured result instead of a bare
    # list. "Published nothing" and "could not be reached" both used to yield
    # [] — which is how MOD China went silent for four weeks without a single
    # failed run (DECISION_LOG 2026-08-09 §5). Those are now different statuses,
    # recorded per source in `source_run_results` and reported before the run
    # closes.
    registry = get_registry()
    window = CollectionWindow(target_date=target_date)
    source_results = []

    for slug in sources:
        if slug not in registry:
            msg = f"{slug}: no desk manifest declares this source — skipping"
            logger.warning(msg)
            errors.append(msg)
            from core.collection.contract import SourceRunResult
            source_results.append(
                SourceRunResult(source_slug=slug,
                                status=collection_status.UNKNOWN_SOURCE,
                                error_detail="not declared in any desk manifest")
            )
            continue

        try:
            adapter = registry.get_adapter(slug)
            result, documents = adapter.collect(window)
        except Exception as exc:
            # An adapter that crashes must not take the run down with it: the
            # other sources' collection is still worth keeping.
            from core.collection.contract import SourceRunResult
            msg = f"{slug}: scrape failed — {exc}"
            logger.error(msg)
            errors.append(msg)
            source_results.append(
                SourceRunResult(source_slug=slug,
                                status=collection_status.ADAPTER_ERROR,
                                desk_id=registry.get_source(slug).desk_id,
                                error_detail=str(exc)[:200])
            )
            continue

        all_scraped.extend(doc.as_article_dict() for doc in documents)
        source_results.append(result)

        if result.is_failure:
            msg = f"{slug}: collection {result.status} — {result.error_detail or 'no detail'}"
            logger.error(msg)
            errors.append(msg)
        elif result.status == collection_status.OK_NO_PUBLICATIONS:
            logger.info("%s: listing reached, nothing new published", slug)
        elif result.status == collection_status.NOT_IMPLEMENTED:
            logger.warning(
                "%s: configured but the adapter is a documented stub — "
                "contributes nothing by design", slug,
            )

    logger.info("Scraped (raw): %d", len(all_scraped))

    # The collection-health table is printed AFTER per-source attribution below,
    # not here. Printed at this point it reported `dup=0 new=0` for every source
    # and an unrefined status — the fold that computes those numbers, and that
    # turns OK into OK_ALL_DUPLICATES / OK_ALL_FILTERED, has not run yet. The
    # persisted `source_run_results` rows were always correct, so the log and the
    # database disagreed, which is the opposite of what a health table is for.

    # ── Stages 4–6: Normalize, dedup, keyword filter ──────────────────────────
    normalized  = [normalize_article(a) for a in all_scraped]
    # Collapse PLA Daily syndicated reposts (same Chinese title across
    # multiple service-branch sub-paths) before the URL/hash dedup.
    title_deduped = dedup_articles(normalized)
    logger.info(
        "Title-dedup: %d in → %d out (%d syndicated reposts removed)",
        len(normalized), len(title_deduped), len(normalized) - len(title_deduped),
    )
    new_articles = deduplicate(title_deduped)
    kw_passed, kw_rejected = keyword_filter(new_articles)

    if dry_run:
        # Nothing is stored, so the attribution fold below never runs and the
        # dup/new columns cannot be filled in. Report what a dry run can honestly
        # know rather than printing nothing at all.
        logger.info("\n%s", human_report(source_results, run_id))
        _print_summary(all_scraped, new_articles, kw_passed, [], [], dry_run)
        return



    # ── Stage 7–8: Store articles ─────────────────────────────────────────────
    inserted: list[tuple[int, dict]] = []   # (article_id, article)

    for article in kw_passed:
        aid = db.insert_article(article, run_id)
        if aid is not None:
            inserted.append((aid, article))

    for article in kw_rejected:
        aid = db.insert_article(article, run_id)
        if aid is not None:
            db.update_relevance(aid, 0.0, "failed keyword pre-filter", False)

    logger.info("Stored %d new articles (%d keyword-rejected, stored with passed=0)",
                len(inserted), len(kw_rejected))

    # ── Per-source attribution ────────────────────────────────────────────────
    # Fold the dedup and filter outcomes back onto each source's result, then
    # persist. Without this the run knows 34 articles arrived but not which
    # source stopped delivering — the exact blind spot that let MOD China go
    # silent for four weeks behind PLA Daily's volume.
    from collections import Counter

    scraped_by_source  = Counter(a.get("source_slug") for a in all_scraped)
    new_by_source      = Counter(a.get("source_slug") for a in new_articles)
    inserted_by_source = Counter(a.get("source_slug") for _, a in inserted)
    rejected_by_source = Counter(a.get("source_slug") for a in kw_rejected)

    for result in source_results:
        slug = result.source_slug
        result.duplicates = max(
            0, scraped_by_source.get(slug, 0) - new_by_source.get(slug, 0)
        )
        result.new_documents      = inserted_by_source.get(slug, 0)
        result.relevance_rejected = rejected_by_source.get(slug, 0)

        # Refine a successful-but-empty outcome now that dedup and filtering
        # have run. Both are healthy states, and both are distinct from silence:
        # the source published, we simply kept none of it.
        if result.status == collection_status.OK and result.new_documents == 0:
            if result.duplicates > 0:
                result.status = collection_status.OK_ALL_DUPLICATES
            elif result.relevance_rejected > 0:
                result.status = collection_status.OK_ALL_FILTERED

        db.record_source_run_result(run_id, result)

    collection_agg = aggregate_status(source_results)

    # Now the table matches what was just written to source_run_results.
    logger.info("\n%s", human_report(source_results, run_id))
    logger.info("Collection aggregate status: %s", collection_agg)

    # ── Stages 9–12: LLM analysis ────────────────────────────────────────────
    articles_analyzed      = 0
    passed_relevance_count = 0   # articles that passed relevance this run
    # Set when the run aborts on an account-level API failure (spend limit,
    # exhausted credit, bad credentials) rather than a per-article one.
    account_blocked: Optional[str] = None

    # Build the analysis queue, newest-first so fresh scrapes are never starved:
    #   1. inserted — scraped this run (passed_relevance NULL)
    #   2. pending  — passed relevance in a prior run but analysis never finished
    #   3. unscored — stored by a prior run that never reached relevance scoring,
    #                 INCLUDING articles truncated by the cap on an earlier day
    # Backlog (2 + 3) gets a reserved share of DAILY_ANALYSIS_CAP so a full day
    # of fresh scrapes cannot crowd it out. This comment previously claimed the
    # backlog "drains every run to fill capacity"; before the 2026-07-30 fix
    # that was false — the queue was concatenated and truncated to the cap, and
    # since every run scrapes more than the cap, the backlog got zero slots and
    # never drained at all (DECISION_LOG 2026-07-30).
    # Format: (article_id, title_zh, body_zh, url)
    new_queue: list[tuple[int, str, str, str]] = [
        (aid,
         a.get("title_original", ""),
         a.get("text_original",  ""),
         a.get("url", "?"))
        for aid, a in inserted
    ]

    inserted_ids = {aid for aid, _ in inserted}

    pending_rows = db.get_articles_pending_analysis()
    pending: list[tuple[int, str, str, str]] = [
        (r["id"],
         r["title_original"] or "",
         r["text_original"]  or "",
         r["url"]            or "?")
        for r in pending_rows
        if r["id"] not in inserted_ids
    ]

    queued_ids = inserted_ids | {aid for aid, *_ in pending}
    unscored_rows = [
        r for r in db.get_articles_unscored() if r["id"] not in queued_ids
    ]

    # Unscored articles are NOT drained in plain FIFO order. Oldest-first buries
    # whatever is recency-critical: on 2026-08-02 the recovered 07-30/07-31
    # articles sat behind 1,106 older unscored rows — ~2 months of draining — so
    # they could not be screened in time for edition No. 12, which covers their
    # own week. Pure FIFO spends the whole backlog reserve on material too old to
    # reach any unwritten edition (DECISION_LOG 2026-08-02).
    #
    # Live articles (scraped within LIVE_BACKLOG_DAYS) go first, oldest-first
    # among themselves so a week fills chronologically. Everything older keeps
    # FIFO behind them, so the archive is deferred but never starved.
    # scraped_at is written by SQLite's datetime('now'), which is UTC.
    live_cutoff = (
        datetime.now(timezone.utc) - timedelta(days=LIVE_BACKLOG_DAYS)
    ).strftime("%Y-%m-%d")
    live_rows    = [r for r in unscored_rows if (r["scraped_at"] or "")[:10] >= live_cutoff]
    archive_rows = [r for r in unscored_rows if (r["scraped_at"] or "")[:10] <  live_cutoff]

    unscored: list[tuple[int, str, str, str]] = [
        (r["id"],
         r["title_original"] or "",
         r["text_original"]  or "",
         r["url"]            or "?")
        for r in live_rows + archive_rows
    ]

    backlog       = pending + unscored
    backlog_total = len(backlog)

    logger.info(
        "Unscored backlog: %d live (scraped since %s), %d archive — live first",
        len(live_rows), live_cutoff, len(archive_rows),
    )

    # Reserve a share of the cap for the backlog. A plain
    # `(new + backlog)[:cap]` starves it completely whenever a single run
    # scrapes more than the cap — which is every run — so the reservation is
    # what makes the "can't stay invisible forever" claim above actually true.
    backlog_slots = 0
    if backlog:
        backlog_slots = min(
            len(backlog),
            max(1, round(DAILY_ANALYSIS_CAP * BACKLOG_RESERVE_FRACTION)),
        )
    new_take = new_queue[: DAILY_ANALYSIS_CAP - backlog_slots]
    # Slots the fresh scrapes didn't need spill back to the backlog.
    backlog_take = backlog[: DAILY_ANALYSIS_CAP - len(new_take)]
    queue = new_take + backlog_take

    pre_cap = len(new_queue) + backlog_total
    if pre_cap > DAILY_ANALYSIS_CAP:
        logger.warning(
            "Queue has %d articles (%d new + %d backlog); capping to %d "
            "(DAILY_ANALYSIS_CAP). Set env var DAILY_ANALYSIS_CAP=N to raise it.",
            pre_cap, len(new_queue), backlog_total, DAILY_ANALYSIS_CAP,
        )

    deferred_new      = len(new_queue) - len(new_take)
    backlog_remaining = backlog_total - len(backlog_take)
    logger.info(
        "Analysis queue: %d/%d new + %d/%d backlog this run (cap=%d, reserve=%.0f%%)",
        len(new_take), len(new_queue), len(backlog_take), backlog_total,
        DAILY_ANALYSIS_CAP, BACKLOG_RESERVE_FRACTION * 100,
    )
    if deferred_new > 0:
        # Deferred new articles keep passed_relevance NULL and re-enter as
        # `unscored` on a later run. If this is nonzero every day, the cap is
        # below the scrape rate and the backlog grows without bound.
        logger.warning(
            "%d newly scraped article(s) deferred by the cap — they become "
            "backlog. Sustained deferral means DAILY_ANALYSIS_CAP (%d) is below "
            "the daily scrape rate.",
            deferred_new, DAILY_ANALYSIS_CAP,
        )
    if backlog_remaining > 0:
        logger.warning(
            "%d backlog article(s) still unprocessed after today's cap — they will "
            "drain on later runs (raise DAILY_ANALYSIS_CAP to clear them faster).",
            backlog_remaining,
        )

    if no_analysis:
        logger.info(
            "Skipping LLM analysis (--no-analysis). %d article(s) stored and "
            "left for a later run.", len(queue),
        )
    elif not ANTHROPIC_API_KEY:
        logger.warning(
            "ANTHROPIC_API_KEY is not set — skipping LLM analysis.\n"
            "Set the key in .env and re-run to complete analysis."
        )
    elif not queue:
        logger.info("No articles to analyze — all up to date.")
    else:
        from analysis.analyzer import Analyzer, FatalAPIError
        analyzer = Analyzer()

        for i, (aid, title_zh, body_zh, url) in enumerate(queue, 1):
            logger.info(
                "[%d/%d] Analyzing: %s",
                i, len(queue), title_zh[:70],
            )

            try:
                result = analyzer.analyze(title_zh, body_zh)
            except FatalAPIError as exc:
                # Account-level failure: every remaining call would fail the
                # same way. On 2026-07-31 the spend limit was reached mid-run
                # and the loop made 40 further doomed calls before finishing.
                account_blocked = str(exc)
                logger.error(
                    "ABORTING analysis at %d/%d — account-level API failure, not "
                    "an article-level one: %s\n"
                    "The %d remaining queued article(s) were NOT attempted; they "
                    "stay unscored and re-enter the backlog on a later run. "
                    "Articles scraped this run are already stored.",
                    i, len(queue), account_blocked, len(queue) - i,
                )
                errors.append(f"Analysis aborted: {account_blocked}")
                break

            if result is None:
                msg = f"Analysis failed entirely for article {aid} ({url})"
                logger.error(msg)
                errors.append(msg)
                continue

            # Always write relevance result
            db.update_relevance(
                aid,
                score     = result["relevance_score"],
                reasoning = result["relevance_reasoning"],
                passed    = result["passed_relevance"],
            )

            if result["passed_relevance"]:
                passed_relevance_count += 1

            # Write full analysis only for articles that passed relevance AND
            # produced a summary. Writing on title_english alone sets
            # analyzed_at on a record with a blank summary, which reads as
            # complete here but fails validate_output.py and blocks the deploy
            # (DECISION_LOG 2026-07-31). Without the summary the article stays
            # pending and a later run retries it.
            if (
                result["passed_relevance"]
                and result.get("title_english")
                and (result.get("summary_english") or "").strip()
            ):
                db.update_analysis(
                    article_id             = aid,
                    title_english          = result.get("title_english",          ""),
                    text_english           = result.get("text_english",           ""),
                    summary_english        = result.get("summary_english",        ""),
                    is_significant         = result.get("is_significant",         False),
                    significance_reasoning = result.get("significance_reasoning"),
                    categories             = result.get("categories",             []),
                    model_id               = result["model_id"],
                    prompt_version         = result["prompt_version"],
                )
                articles_analyzed += 1

                if result.get("is_significant"):
                    logger.info(
                        "  ★ SIGNIFICANT: %s",
                        result.get("significance_reasoning", ""),
                    )
            elif result["passed_relevance"]:
                # Passed relevance but translation/summary failed → no publishable
                # output. analyzed_at stays NULL so this becomes pending backlog
                # and a later run retries it.
                missing = (
                    "no English translation"
                    if not result.get("title_english")
                    else "a translation but no summary"
                )
                msg = (
                    f"Post-relevance analysis incomplete for article {aid} ({url}): "
                    f"passed relevance but produced {missing}"
                )
                logger.error(msg)
                errors.append(msg)

    # ── Stage 13: Close run record ────────────────────────────────────────────
    # --no-analysis is a deliberate skip, not a failure: it must not trip the
    # billing-failure guard or exit non-zero, or the site-generation stage and
    # the CI commit are skipped and the day's collection is discarded anyway.
    analysis_attempted = bool(len(queue) > 0 and ANTHROPIC_API_KEY and not no_analysis)

    # Relevance scoring itself failed for every queued article (analyze() returned
    # None) → likely API/billing outage. Preserved exactly as the original check
    # so the billing-failure guard behaves the same.
    relevance_total_failure = (
        analysis_attempted
        and articles_analyzed == 0
        and any("Analysis failed entirely" in e for e in errors)
    )
    # Relevance scoring worked (≥1 article passed) but translation/summary failed
    # for ALL of them, so the run produced nothing publishable. Previously this
    # slipped through as a "success". Not a billing failure, but the run must
    # still fail visibly so a later cron window or manual run retries.
    post_relevance_total_failure = (
        analysis_attempted
        and articles_analyzed == 0
        and passed_relevance_count > 0
        and not relevance_total_failure
    )
    # An account-level block is only a *run* failure if it stopped everything.
    # If some articles were analyzed before the block, that work is publishable
    # and the run should still generate the site and exit 0 — the marker below
    # is what prevents later cron windows from retrying against a dead account.
    account_block_total_failure = account_blocked is not None and articles_analyzed == 0

    total_analysis_failed = (
        relevance_total_failure
        or post_relevance_total_failure
        or account_block_total_failure
    )

    # Write the billing marker whenever the account is confirmed blocked, even
    # on a partial success: every later window today would hit the same wall.
    # This is a definitive signal from the API, unlike relevance_total_failure,
    # which infers billing trouble from "everything failed".
    if account_blocked is not None and not dry_run:
        logger.error(
            "Account-level API block detected (%s). Writing billing-failure "
            "marker so later cron windows today skip their paid retries.",
            account_blocked,
        )
        _write_billing_failure_marker(target_date)

    # Close the run with an honest status. Until 2026-08-09 this call omitted
    # `status`, so it always defaulted to 'completed' — including 2026-08-07,
    # which hit the credit wall after 24 of 36 articles. That run looked
    # identical to a clean day in the audit log and the outage went unnoticed
    # for two days.
    #
    # Only an account-level block downgrades a partial run. Per-article
    # "post-relevance analysis incomplete" errors are routine and self-healing
    # (the article stays pending and a later run retries it); downgrading on
    # those would mark most runs 'degraded' and make the field meaningless.
    #
    # Collection failures degrade the run too, independently of analysis. A run
    # where one required source could not be reached is not a clean day, even
    # if the other sources delivered and every article analyzed successfully —
    # that combination is precisely what reported success for four weeks while
    # MOD China was dead.
    if total_analysis_failed:
        run_status = "failed"
    elif account_blocked is not None:
        run_status = "degraded"
    elif collection_agg in ("failed", "degraded"):
        run_status = "degraded"
        failed_slugs = [r.source_slug for r in source_results if r.is_failure]
        logger.error(
            "Run marked degraded by collection: %d source(s) failed (%s)",
            len(failed_slugs), ", ".join(sorted(failed_slugs)),
        )
    else:
        run_status = "completed"

    if run_id is not None:
        db.complete_scrape_run(
            run_id,
            articles_scraped  = len(all_scraped),
            articles_new      = len(inserted),
            articles_analyzed = articles_analyzed,
            errors            = errors,
            status            = run_status,
        )

    elapsed = (datetime.now() - start_time).total_seconds()
    db_total = db.get_total_analyzed_count() if not dry_run else 0
    _print_summary(all_scraped, new_articles, kw_passed, inserted, errors, dry_run,
                   articles_analyzed=articles_analyzed, db_total=db_total, elapsed=elapsed,
                   pre_cap=pre_cap, backlog_remaining=backlog_remaining)

    if total_analysis_failed:
        if account_block_total_failure:
            logger.error(
                "FATAL: analysis aborted on an account-level API block before any "
                "article completed (%s). The billing-failure marker is already "
                "written. Scraped articles are stored and the workflow's persist "
                "step commits them; nothing new is publishable, so the site is "
                "not regenerated.",
                account_blocked,
            )
        elif relevance_total_failure:
            logger.error(
                "FATAL: %d article(s) queued for analysis but zero succeeded — "
                "API or billing failure. Writing billing-failure marker to prevent "
                "repeated paid retries from later cron windows today.",
                len(queue),
            )
            if not dry_run and account_blocked is None:
                _write_billing_failure_marker(target_date)
        else:
            logger.error(
                "FATAL: %d article(s) passed relevance but none produced a usable "
                "translation/summary — post-relevance analysis failed for the whole "
                "queue. Not writing the success marker; a later cron window or manual "
                "run will retry the now-pending articles. (No billing marker: relevance "
                "scoring succeeded, so this is not credit exhaustion.)",
                passed_relevance_count,
            )
        sys.exit(2)

    # ── Stage 14: Generate site ───────────────────────────────────────────────
    # --no-analysis is an outage-capture mode: store the day's articles and stop.
    # It must not regenerate output/, for two reasons found on 2026-07-31.
    # First, the generator renders from the working tree, so an uncommitted
    # template edit gets baked into output/ — and CI commits output/. A capture
    # run published a methodology draft that was deliberately left uncommitted
    # for review. An unreviewed template is not protected by being uncommitted.
    # Second, regenerating from a DB whose analysis is knowingly incomplete
    # rewrites the published site from a partial record.
    if not dry_run and not no_analysis:
        try:
            import importlib.util
            from pathlib import Path as _Path
            _spec = importlib.util.spec_from_file_location(
                "site_generator",
                _Path(__file__).parent / "site" / "generator.py",
            )
            _gen = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_gen)
            _gen.generate_site()
            logger.info("Site generated → %s", OUTPUT_DIR)
        except Exception as exc:
            logger.error("Site generation failed: %s", exc)
            sys.exit(1)


# ── Billing-failure marker ────────────────────────────────────────────────────

BILLING_FAILURE_STATE_FILE = ".github/state/last_billing_failure_date.txt"


def _write_billing_failure_marker(target_date: date) -> None:
    """
    Write today's NY date to a state file so the scheduling guard in the
    workflow can skip later cron windows after a total API/billing failure.
    This file is separate from last_daily_run_date.txt so a successful manual
    workflow_dispatch still writes the success marker and clears the failure.
    Note: the workflow must commit+push this file for it to persist to origin/main.
    """
    from pathlib import Path
    p = Path(BILLING_FAILURE_STATE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(target_date.isoformat())
    logger.info("Billing-failure marker written: %s → %s", p, target_date.isoformat())


# ── Terminal summary ──────────────────────────────────────────────────────────

def _print_summary(
    scraped:           list,
    after_dedup:       list,
    after_kw:          list,
    inserted:          list,
    errors:            list,
    dry_run:           bool,
    articles_analyzed: int   = 0,
    db_total:          int   = 0,
    elapsed:           float = 0.0,
    pre_cap:           int   = 0,
    backlog_remaining: int   = 0,
) -> None:
    sep = "─" * 52
    tag = "(DRY RUN)" if dry_run else ""
    print(f"\n{sep}")
    print(f"  PLA Watch pipeline complete {tag}")
    print(sep)
    print(f"  Scraped (raw):          {len(scraped):>4}")
    print(f"  After dedup:            {len(after_dedup):>4}")
    print(f"  After keyword filter:   {len(after_kw):>4}")
    if not dry_run:
        print(f"  Stored to DB:           {len(inserted):>4}")
        if pre_cap > DAILY_ANALYSIS_CAP:
            print(f"  Queue before cap:       {pre_cap:>4}")
            print(f"  Cap (DAILY_ANALYSIS_CAP):{DAILY_ANALYSIS_CAP:>4}")
        if backlog_remaining:
            print(f"  Backlog remaining:      {backlog_remaining:>4}  (drains on later runs)")
        print(f"  Analyzed this run:      {articles_analyzed:>4}")
        print(f"  Total analyzed in DB:   {db_total:>4}")
        print(f"  Relevance model:        {RELEVANCE_MODEL}")
        print(f"  Analysis model:         {ANALYSIS_MODEL}")
    if elapsed:
        print(f"  Elapsed:                {elapsed:>6.1f}s")
    if errors:
        print(f"  Errors ({len(errors)}):")
        for e in errors:
            print(f"    • {e}")
    print(sep)
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PLA Watch — scrape, analyze, and store daily PLA media coverage."
    )
    parser.add_argument(
        "--source",
        choices=list(SCRAPERS.keys()),
        default=None,
        help="Scrape a single source (default: all sources)",
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help="Target date to scrape (default: today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline without writing to DB or calling LLM APIs",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help=(
            "Scrape and store articles, but skip all LLM analysis. Stored "
            "articles keep passed_relevance NULL and drain as backlog on a "
            "later run. Use when the API is unavailable (spend limit, outage) "
            "so a day's collection is still captured rather than lost. Note "
            "that ANTHROPIC_API_KEY='' does NOT do this — config.py treats an "
            "empty value as unset and falls back to .env."
        ),
    )
    args = parser.parse_args()

    target   = args.date or date.today()
    sources  = [args.source] if args.source else list(SCRAPERS.keys())

    run(
        sources=sources,
        target_date=target,
        dry_run=args.dry_run,
        no_analysis=args.no_analysis,
    )
