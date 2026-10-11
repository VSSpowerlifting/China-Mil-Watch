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
import os
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
from processing.screening import desk_for_source, profile_for_desk
from core.collection import status as collection_status
from core.collection.contract import CollectionWindow
from core.collection.health import aggregate_status, human_report
from core.registry import get_registry
from core import processing_state
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


def hold_blank_original_bodies(candidates: list) -> tuple[list, int]:
    """Remove unextractable *stored inputs* from this run's model candidate list.

    A blank body is an extraction/recovery question, NEVER proof that the
    publisher issued no prose. Preserve those article rows and processing
    metadata unchanged; exclude them only from paid API dispatch so they
    cannot occupy fresh/backlog cap slots or repeatedly buy empty responses.

    Items are (article_id, title, original_body, url). Return a new list;
    callers keep their initial source data and all stored records intact.
    """
    ready = []
    withheld = 0
    for item in candidates:
        body = item[2]
        if isinstance(body, str) and body.strip():
            ready.append(item)
        else:
            withheld += 1
    return ready, withheld


def prior_processing_attempts(*stored_queue_lanes) -> dict[int, int]:
    """Carry recorded failure counts into every stored Daily retry lane.

    Previously only passed-relevance pending articles retained their counter.
    Never-scored backlog entries started again from attempt 1 on every run,
    so repeated model-format failures could not exhaust the five-attempt
    human-review pause budget. Do not invent history for newly scraped rows.
    """
    return {
        row["id"]: row["processing_attempts"]
        for lane in stored_queue_lanes
        for row in lane
        if row["processing_attempts"] is not None
    }


# ── Atomic-batch sources ─────────────────────────────────────────────────────
#
# Every source defaults to insert_article()'s per-article-own-commit design:
# a bad record costs only itself, and the other 340 PLA Daily articles from
# the same run are not held hostage by one. That default is deliberate and
# stays in place for every source not named here.
#
# Singapore is named here instead, following a bounded review of PR #69
# (2026-09-22): the corpus already holds two records a silent extraction
# defect damaged badly enough to need a governed, human-reviewed exclusion
# (DECISION_LOG.md, 2026-09-21) that SGMindefAdapter.extract()'s checks did
# not catch when it happened. A live scheduled run gets no such review before
# publishing, so for this source specifically, a batch commits completely or
# not at all -- see storage.db.insert_articles_atomic() and
# SGMindefAdapter.collect()'s own matching all-or-nothing gate.
ATOMIC_BATCH_SLUGS = frozenset({"sg_mindef_releases"})


def production_window(adapter, target_date: date) -> CollectionWindow:
    """
    The window a scheduled run hands one adapter: its target date plus the
    adapter's own `production_lookback_days` (zero unless it declares more).

    One window for every source used to be built here with no lookback. For
    Singapore, whose adapter discovers strictly by the window it is given,
    that meant a release was collectable on its slug date and never again, so
    the first week of production lost three releases the shadow collector
    still holds (see `SGMindefAdapter.production_lookback_days`).
    """
    return CollectionWindow(
        target_date=target_date,
        lookback_days=getattr(adapter, "production_lookback_days", 0))


def _store_atomic_batches(kw_passed: list, kw_rejected: list, run_id,
                          atomic_slugs=ATOMIC_BATCH_SLUGS):
    """
    Insert every atomic-batch source's articles as one all-or-nothing
    transaction per source, grouped from the combined (cross-source)
    kw_passed/kw_rejected lists Stage 4-6 already produced.

    Returns `(inserted, failed_slugs)`: `inserted` is the same
    `[(article_id, article), ...]` shape the ordinary per-article loop
    produces, for the articles that DID commit; `failed_slugs` names any
    source whose whole batch was rolled back, so the caller can record that
    source's run honestly instead of leaving it read as OK.
    """
    by_slug: dict = {}
    for a in kw_passed:
        slug = a.get("source_slug")
        if slug in atomic_slugs:
            by_slug.setdefault(slug, {"passed": [], "rejected": []})["passed"].append(a)
    for a in kw_rejected:
        slug = a.get("source_slug")
        if slug in atomic_slugs:
            by_slug.setdefault(slug, {"passed": [], "rejected": []})["rejected"].append(a)

    inserted: list = []
    failed_slugs: set = set()
    for slug, groups in by_slug.items():
        try:
            inserted.extend(
                db.insert_articles_atomic(groups["passed"], groups["rejected"], run_id)
            )
        except Exception as exc:
            logger.error(
                "%s: atomic batch insert failed — nothing from this run's "
                "%d-record batch was committed: %s",
                slug, len(groups["passed"]) + len(groups["rejected"]), exc,
            )
            failed_slugs.add(slug)
    return inserted, failed_slugs


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run(
    sources:         list[str],
    target_date:     date,
    dry_run:         bool = False,
    no_analysis:     bool = False,
    *,
    analysis_policy=None,
    budget_usd=None,
    receipt_sink=None,
    expected_plan=None,
    generate_output=True,
) -> None:
    # C1 provides only a validated private-mode inspection seam. Collection,
    # analysis and checkpoint lifecycle wiring belongs to separately reviewed
    # C2. Refuse before directories, initialization, collector or model work.
    private_context = db.current_database_context()
    if private_context is not None:
        from core.evidence_snapshot import require
        private_context.validate()
        require(dry_run is True, "custody_pipeline_not_integrated")
        logger.info("Fictional custody dry run: verified database; no execution")
        return
    if budget_usd is not None:
        from analysis.admission import money
        money(budget_usd)
        if not callable(receipt_sink):
            raise ValueError("guarded execution requires a private receipt sink")
        if dry_run or no_analysis:
            raise ValueError("guarded execution cannot be a skipped analysis run")
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
            result, documents = adapter.collect(
                production_window(adapter, target_date))
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

        # Identify unreadable source pages before dedup/filtering can hide
        # whether they were previously stored, rejected or newly inserted.
        # Public official-source locator only; never the body or title.
        from core.collection.text_gap_receipts import log_unreadable_source_receipts
        no_text_count = log_unreadable_source_receipts(slug, documents, logger)
        if (result.text_unavailable is not None
                and no_text_count != result.text_unavailable):
            logger.warning(
                "%s: source text-gap receipt count (%d) disagrees with "
                "adapter result (%d); investigate collection accounting",
                slug, no_text_count, result.text_unavailable,
            )
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
        # know rather than printing nothing at all — but say so, because an
        # unlabelled `dup=0 new=0` reads as "this source delivered nothing"
        # rather than "this run did not compute that".
        logger.info(
            "DRY RUN — the table below reports discovery only. dup/new/rejected "
            "are UNAVAILABLE (no storage, so no attribution), and each status is "
            "pre-refinement: ok_all_duplicates / ok_all_filtered are not resolved."
        )
        logger.info("\n%s", human_report(source_results, run_id))
        _print_summary(all_scraped, new_articles, kw_passed, [], [], dry_run)
        return



    # ── Stage 7–8: Store articles ─────────────────────────────────────────────
    # Atomic-batch sources (ATOMIC_BATCH_SLUGS) are pulled out first and
    # inserted as their own all-or-nothing transaction; everything else goes
    # through the exact same per-article loop as always -- unfiltered, this
    # IS that original loop, just now only reached by the ~all~ articles when
    # no source opts into the atomic path, which is every run before this.
    inserted: list[tuple[int, dict]] = []   # (article_id, article)

    normal_kw_passed = [a for a in kw_passed
                       if a.get("source_slug") not in ATOMIC_BATCH_SLUGS]
    normal_kw_rejected = [a for a in kw_rejected
                         if a.get("source_slug") not in ATOMIC_BATCH_SLUGS]

    for article in normal_kw_passed:
        aid = db.insert_article(article, run_id)
        if aid is not None:
            inserted.append((aid, article))

    for article in normal_kw_rejected:
        aid = db.insert_article(article, run_id)
        if aid is not None:
            db.update_relevance(aid, 0.0, "failed keyword pre-filter", False)

    atomic_inserted, atomic_failed_slugs = _store_atomic_batches(
        kw_passed, kw_rejected, run_id)
    inserted.extend(atomic_inserted)

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

        if slug in atomic_failed_slugs:
            # The batch existed and was rejected as a whole -- record that
            # honestly rather than letting new_documents == 0 read as
            # OK_ALL_DUPLICATES/OK_ALL_FILTERED below, which would claim a
            # storage failure was a healthy empty outcome.
            result.status = collection_status.STORAGE_FAILURE
            result.error_detail = (
                (result.error_detail + "; " if result.error_detail else "")
                + "atomic batch insert failed; no new records committed "
                  "this run"
            )
        # Refine a successful-but-empty outcome now that dedup and filtering
        # have run. Both are healthy states, and both are distinct from silence:
        # the source published, we simply kept none of it.
        elif result.status == collection_status.OK and result.new_documents == 0:
            if result.duplicates > 0:
                result.status = collection_status.OK_ALL_DUPLICATES
            elif result.relevance_rejected > 0:
                result.status = collection_status.OK_ALL_FILTERED

        db.record_source_run_result(run_id, result)

    collection_agg = aggregate_status(source_results)

    # Now the table matches what was just written to source_run_results.
    logger.info("\n%s", human_report(source_results, run_id))
    logger.info("Collection aggregate status: %s", collection_agg)

    def _record_failure(article_id: int, body: str, failure: str,
                        history: dict, verdicts: dict) -> None:
        """
        Note one observed analysis failure and decide whether to keep trying.

        A record that can never succeed used to re-enter this queue on every
        run for ever — article 2678 was retried 28 times.

        Three outcomes, and the difference between the last two matters:
        `retriable` keeps its place; `paused` is a spend control a human can
        undo with `db.resume_paused_article()`; `terminal` is a statement about
        the document's content and is reached ONLY through an adapter's
        deterministic verdict, never by an attempt counter. Five bad days for
        the model API must not permanently dispose of a good document.

        `verdicts` carries those adapter verdicts for records scraped this run,
        where the parsed document is still in hand. A backlog record has none —
        nothing stored it — so it can only ever be retriable or paused, which
        is the conservative answer and is deliberate.
        """
        disposition = processing_state.classify(
            attempts_before=history.get(article_id),
            has_body=bool((body or "").strip()),
            failure=failure,
            content_verdict=verdicts.get(article_id),
        )
        history[article_id] = disposition.attempts
        db.record_processing_failure(article_id, disposition)
        if disposition.is_terminal:
            logger.warning(
                "  article %d will not be retried: %s (attempt %d)",
                article_id, disposition.reason, disposition.attempts,
            )
        elif disposition.is_paused:
            logger.warning(
                "  article %d paused for manual review after %d attempts: %s "
                "— resume with db.resume_paused_article(%d)",
                article_id, disposition.attempts, disposition.reason,
                article_id,
            )

    # ── Stages 9–12: LLM analysis ────────────────────────────────────────────
    articles_analyzed      = 0
    passed_relevance_count = 0   # articles that passed relevance this run
    # Set when the run aborts on an account-level API failure (spend limit,
    # exhausted credit, bad credentials) rather than a per-article one.
    account_blocked: Optional[str] = None
    # Stays None when no model call was attempted (no key, --no-analysis, empty
    # queue); the usage telemetry below is recorded only when it was created.
    analyzer = None

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
    #
    # A desk whose screening profile is not in the daily queue (Singapore: its
    # records would be screened, then translated, summarised and categorised by
    # China-only prompts) is held out of all three sources of the queue. Its
    # records keep passed_relevance NULL, "awaiting screening", until a
    # reviewed desk-scoped screening (scripts/rescreen_desk.py) — see
    # processing/screening.py.
    from core.analysis_plan import Policy, build_plan, inventory, revalidate, code_identity
    from analysis.admission import AdmissionController, AdmissionDeferred, pricing_identity, task_settings, capacity_estimate
    with db.get_conn() as conn:
        candidates = inventory(conn, [aid for aid, _ in inserted])
    policy = analysis_policy or Policy(
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        cap=DAILY_ANALYSIS_CAP, reserve=BACKLOG_RESERVE_FRACTION,
        live_days=LIVE_BACKLOG_DAYS, budget_usd=budget_usd,
    )
    if policy.budget_usd != budget_usd:
        raise ValueError("plan/runtime budget mismatch")
    identities = dict(code_identity=code_identity(), pricing_identity=pricing_identity(),
                      snapshot_kind="after collection", snapshot_identity={"native_run_id": run_id},
                      execution_settings=task_settings(), capacity=capacity_estimate(task_settings(), budget_usd))
    plan = build_plan(candidates, policy, **identities)
    if expected_plan is not None and expected_plan != plan:
        raise ValueError("stale preview is not execution authority")
    # Immediately reread content/state, configuration and prices before dispatch.
    with db.get_conn() as conn:
        fresh_candidates = inventory(conn, [aid for aid, _ in inserted])
    revalidate(plan, fresh_candidates, policy, **{**identities,
               "code_identity": code_identity(), "pricing_identity": pricing_identity(),
               "execution_settings": task_settings(), "capacity": capacity_estimate(task_settings(), budget_usd)})
    by_id = {c.record_id: c for c in fresh_candidates}
    queue = [(i, by_id[i].title, by_id[i].body, by_id[i].url) for i in plan["selected_ids"]]
    attempts_before = {c.record_id: c.attempts for c in candidates if c.attempts is not None}
    content_verdicts = {aid: a.get("content_verdict") for aid, a in inserted if a.get("content_verdict")}
    pre_cap = plan["counts"]["eligible"]
    backlog_remaining = sum(r["lane"] in ("pending", "unscored") and
                            r["reason"] in ("cap-deferral", "allocation-deferral") for r in plan["records"])
    held_desks = Counter(r["desk_id"] for r in plan["records"] if r["reason"] == "desk-policy-hold")
    for desk_id, held in sorted(held_desks.items(), key=lambda kv: str(kv[0])):
        logger.info(
            "Held out of the daily analysis queue: %d %s-desk record(s) — the "
            "desk's screening is not run by the daily pipeline "
            "(processing/screening.py); they stay awaiting screening.",
            held, desk_id,
        )
    blank_lanes = Counter(r["lane"] for r in plan["records"] if r["reason"] == "blank-body")
    if blank_lanes:
        logger.warning(
            "Withheld %d stored article(s) with blank original bodies from "
            "paid analysis dispatch: %d new, %d pending, %d unscored. "
            "Rows and processing states were not changed; original text "
            "requires source/extraction review before analysis.",
            sum(blank_lanes.values()), blank_lanes["new"], blank_lanes["pending"], blank_lanes["unscored"],
        )
    new_total = sum(r["lane"] == "new" and
                    (r["selected"] or r["reason"] in ("cap-deferral", "allocation-deferral"))
                    for r in plan["records"])
    logger.info(
        "Analysis queue: %d/%d new + %d/%d backlog this run (cap=%d, reserve=%.0f%%)",
        plan["counts"]["new_planned"], new_total, plan["counts"]["backlog_planned"],
        pre_cap - new_total, policy.cap, policy.reserve * 100,
    )
    logger.info("Analysis plan %s: %d planned / %d eligible; %d held; %d deferred",
                plan["plan_id"], len(queue), pre_cap, plan["counts"]["held"], plan["counts"]["deferred"])
    guard = None
    if budget_usd is not None:
        if no_analysis or dry_run:
            raise ValueError("guarded execution cannot be a skipped analysis run")
        guard = AdmissionController(budget_usd, plan_id=plan["plan_id"],
                                    execution_id="scrape-run:%s" % run_id,
                                    sink=lambda receipt: receipt_sink({"plan": plan, "run": receipt}))

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
        analyzer = Analyzer(admission=guard) if guard is not None else Analyzer()

        for i, (aid, title_zh, body_zh, url) in enumerate(queue, 1):
            logger.info(
                "[%d/%d] Analyzing: %s",
                i, len(queue), "record %d" % aid if guard is not None else title_zh[:70],
            )
            if guard is not None:
                url = "private locator withheld"

            try:
                if guard is not None:
                    analyzer.prepare_article(aid)
                result = analyzer.analyze(title_zh, body_zh)
            except AdmissionDeferred as exc:
                if guard is not None:
                    outcome = "incomplete" if any(c["record_id"] == aid for c in guard.snapshot()["calls"]) else "budget-deferred"
                    guard.finish_article(aid, outcome, reason=str(exc))
                logger.info("Article %d operationally deferred; processing attempts unchanged", aid)
                continue
            except FatalAPIError as exc:
                # Account-level failure: every remaining call would fail the
                # same way. On 2026-07-31 the spend limit was reached mid-run
                # and the loop made 40 further doomed calls before finishing.
                if guard is not None:
                    guard.finish_article(aid, "incomplete")
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

            if result is not None and guard is not None and guard.blocked:
                result = {k: v for k, v in result.items()
                          if k not in ("title_english", "text_english", "summary_english")}
            if result is None:
                if guard is not None:
                    guard.finish_article(aid, "incomplete")
                msg = f"Analysis failed entirely for article {aid} ({url})"
                logger.error(msg)
                errors.append(msg)
                _record_failure(aid, body_zh, "analysis_failed",
                                attempts_before, content_verdicts)
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
                if guard is not None:
                    guard.finish_article(aid, "fully-analyzed")
                db.clear_processing_failure(aid)

                if result.get("is_significant"):
                    logger.info(
                        "  ★ SIGNIFICANT: %s",
                        "private model reasoning withheld" if guard is not None else result.get("significance_reasoning", ""),
                    )
            elif result["passed_relevance"]:
                if guard is not None:
                    guard.finish_article(aid, "incomplete")
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
                _record_failure(aid, body_zh, "analysis_incomplete",
                                attempts_before, content_verdicts)

            elif guard is not None:
                guard.finish_article(aid, "relevance-rejected")

    if guard is not None:
        guard.finish_run(plan["selected_ids"])

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
        _write_billing_failure_marker()

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

    # Operational accounting only (analysis/usage.py): counts what the API
    # reported, changes nothing above or below, and cannot raise.
    if analyzer is not None and not dry_run:
        _record_llm_usage(analyzer, run_status=run_status,
                          articles_queued=len(queue),
                          articles_fully_analyzed=articles_analyzed)

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
                _write_billing_failure_marker()
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
    if not dry_run and not no_analysis and generate_output:
        try:
            import importlib.util
            from pathlib import Path as _Path
            # Routed through site/render.py, the one place that selects a
            # frontend. No mode is passed, so this resolves to
            # DEFAULT_SITE_MODE — legacy — exactly as before. The scheduled
            # workflow sets nothing, and a contract test asserts it never does.
            _spec = importlib.util.spec_from_file_location(
                "site_render",
                _Path(__file__).parent / "site" / "render.py",
            )
            _render = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_render)
            _report = _render.render_site()
            logger.info("Site generated (%s mode) → %s",
                        _report["mode"], _report["output_dir"])
        except Exception as exc:
            logger.error("Site generation failed: %s", exc)
            sys.exit(1)


# ── LLM usage telemetry ───────────────────────────────────────────────────────

def _record_llm_usage(analyzer, *, run_status: str, articles_queued: int,
                      articles_fully_analyzed: int) -> None:
    """
    Log one usage summary and, when LLM_USAGE_RECORD_PATH is set, write this
    run's record to that runtime file.

    Observability only. It runs after the analysis stage and the run record are
    closed, so it cannot change what was analyzed, stored, published or retried;
    and it never raises, so a telemetry fault cannot fail a run that succeeded.
    It never writes a tracked file: the workflow's dedicated step appends the
    runtime record to the tracked history (daily_update.yml). Unset, as in every
    local run, it is log-only.
    """
    try:
        from analysis.usage import RECORD_PATH_ENV, record_run_usage
        from core.workflow_day import workflow_day_string
        record_run_usage(
            analyzer.usage,
            path=os.environ.get(RECORD_PATH_ENV) or None,
            run_date=workflow_day_string(),
            recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            run_status=run_status,
            analysis_model=ANALYSIS_MODEL,
            relevance_model=RELEVANCE_MODEL,
            articles_queued=articles_queued,
            articles_fully_analyzed=articles_fully_analyzed,
        )
    except Exception as exc:  # noqa: BLE001 — see the docstring
        logger.warning("LLM usage telemetry NOT recorded: %s", exc)


# ── Billing-failure marker ────────────────────────────────────────────────────

BILLING_FAILURE_STATE_FILE = ".github/state/last_billing_failure_date.txt"


def _write_billing_failure_marker(now: "datetime" = None) -> None:
    """
    Record the WORKFLOW DAY on which the account was blocked.

    The scheduling guard suppresses later cron windows by comparing this file
    to the current New York date, so the value written here has to be the same
    New York date. It previously wrote the run's `target_date`, which is
    `date.today()` — the runner's UTC date — while this docstring claimed
    otherwise. The two agree for every configured cron window and diverge for
    the four hours after 20:00 New York.

    The collection target date is deliberately no longer used: it is a claim
    about which day's *articles* were sought, not about which day the workflow
    is having. Conflating a content date with a schedule date is how this
    drifted in the first place.

    `now` is for tests. The workflow must still commit and push this file for
    it to reach origin/main.
    """
    from pathlib import Path
    from core.workflow_day import workflow_day_string
    stamp = workflow_day_string(now)
    p = Path(BILLING_FAILURE_STATE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(stamp)
    logger.info("Billing-failure marker written: %s → %s (workflow day, "
                "America/New_York)", p, stamp)


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
    parser.add_argument("--analysis-policy", choices=("compatibility", "age-aware"), default="compatibility")
    parser.add_argument("--analysis-budget-usd", help="opt-in strict per-run estimated USD envelope; separate spend approval required")
    parser.add_argument("--analysis-run-receipt", help="new private journal outside repository; required with budget")
    args = parser.parse_args()
    if bool(args.analysis_budget_usd is not None) != bool(args.analysis_run_receipt):
        parser.error("strict budget and private run receipt must be supplied together")

    target   = args.date or date.today()
    sources  = [args.source] if args.source else list(SCRAPERS.keys())

    from core.analysis_plan import Policy
    journal = None
    try:
        if args.analysis_budget_usd is not None:
            from analysis.admission import money
            from scripts.analysis_capacity import PrivateRunJournal
            money(args.analysis_budget_usd)
            if args.dry_run or args.no_analysis:
                parser.error("strict admission requires actual analysis, not a skipped run")
            journal = PrivateRunJournal(args.analysis_run_receipt)
        policy = Policy(datetime.now(timezone.utc).isoformat(), DAILY_ANALYSIS_CAP,
                        BACKLOG_RESERVE_FRACTION, LIVE_BACKLOG_DAYS, args.analysis_policy,
                        budget_usd=args.analysis_budget_usd)
        run(sources=sources, target_date=target, dry_run=args.dry_run,
            no_analysis=args.no_analysis, analysis_policy=policy,
            budget_usd=args.analysis_budget_usd, receipt_sink=journal)
    finally:
        if journal is not None:
            journal.close()
