"""
Database access layer for PLA Watch.

All SQL lives here. No ORM — keeping it transparent and dependency-light.
Connection uses WAL mode for safe concurrent reads during site generation.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from config import DB_PATH

logger = logging.getLogger(__name__)

# ── Connection ────────────────────────────────────────────────────────────────

@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    """Yield a connection that auto-commits on clean exit, rolls back on error."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Initialization ────────────────────────────────────────────────────────────

def init_db(apply_migrations: bool = True) -> None:
    """
    Create tables and seed data if they don't exist, then bring the schema up to
    date. Safe to call repeatedly.

    Why migrations run here: `scripts/reconcile_db.py` resolves a diverged
    database by copying the published side's *file*, so a rebase against an
    origin that predates a schema change silently restores the older shape — no
    conflict, no warning. That has already happened twice to the `'degraded'`
    constraint (DECISION_LOG 2026-08-09 §7, and again by the Phase 0 audit).

    `init_db()` is the pipeline's single write-path entry point and runs before
    any collection, so applying migrations here makes the schema self-healing
    instead of dependent on someone remembering the standing re-apply rule.
    Migrations are idempotent; on an already-current database this is a
    no-op costing one table scan of `schema_migrations`.

    Pass `apply_migrations=False` for the rare case of wanting the legacy schema
    exactly as `schema.sql` defines it (the migration tests use this to build
    pre-migration fixtures).
    """
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    with get_conn() as conn:
        conn.executescript(sql)
    logger.info("Database initialized at %s", DB_PATH)

    if not apply_migrations:
        return

    # Imported lazily: storage/ must stay importable in contexts that have no
    # desk configuration on disk (and to keep the import graph acyclic).
    from migrations.runner import apply_all, connect

    conn = connect(DB_PATH)
    try:
        report = apply_all(conn)
    finally:
        conn.close()

    if report["applied"] or report["already_present"]:
        logger.info(
            "migrations: applied=%s detected-already-present=%s",
            report["applied"] or "none", report["already_present"] or "none",
        )


# ── Source lookup ─────────────────────────────────────────────────────────────

def get_source_id(slug: str) -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM sources WHERE slug = ?", (slug,)
        ).fetchone()
    return row["id"] if row else None


# ── Deduplication checks ──────────────────────────────────────────────────────

def url_exists(url: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM articles WHERE url = ?", (url,)
        ).fetchone()
    return row is not None


def hash_exists(content_hash: str) -> bool:
    """True if an article with this content hash is already stored."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM articles WHERE content_hash = ?", (content_hash,)
        ).fetchone()
    return row is not None


# ── Scrape run log ────────────────────────────────────────────────────────────

def start_scrape_run() -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO scrape_runs (status) VALUES ('running')"
        )
        return cur.lastrowid


def complete_scrape_run(
    run_id: int,
    articles_scraped: int,
    articles_new: int,
    articles_analyzed: int,
    errors: list[str],
    status: str = "completed",
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE scrape_runs
               SET completed_at      = datetime('now'),
                   articles_scraped  = ?,
                   articles_new      = ?,
                   articles_analyzed = ?,
                   errors            = ?,
                   status            = ?
             WHERE id = ?
            """,
            (articles_scraped, articles_new, articles_analyzed,
             json.dumps(errors), status, run_id),
        )


# ── Article writes ────────────────────────────────────────────────────────────

def insert_article(article: dict, scrape_run_id: int) -> Optional[int]:
    """
    Insert a new article. Returns the new row id, or None if the URL
    already exists.
    """
    source_id = get_source_id(article["source_slug"])
    if source_id is None:
        logger.error("Unknown source slug: %s", article["source_slug"])
        return None

    try:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO articles
                    (url, content_hash, source_id, scrape_run_id,
                     title_original, text_original, published_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article["url"],
                    article["content_hash"],
                    source_id,
                    scrape_run_id,
                    article.get("title_original"),
                    article.get("text_original"),
                    article.get("published_date"),
                ),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        logger.debug("Duplicate URL skipped: %s", article["url"])
        return None


def insert_articles_atomic(
    passed: list, rejected: list, run_id: int,
) -> list:
    """
    Insert one source's whole batch (both keyword-passed and keyword-rejected
    articles) as a single all-or-nothing transaction.

    `insert_article()` above deliberately commits each article on its own
    connection -- correct for sources that should tolerate losing only the
    one bad record in a batch (pipeline.py's Stage 3 comment explains why).
    This function exists for the opposite guarantee, for sources configured
    into `pipeline.py`'s `ATOMIC_BATCH_SLUGS`: if ANY insert in the batch
    hits a genuine, unexpected error, EVERY insert from this call is rolled
    back -- including ones that had already succeeded earlier in the same
    call -- so a mid-batch failure can never leave part of a batch committed
    and the rest lost. A duplicate URL is not such a failure: it is the same
    ordinary, expected outcome `insert_article()` already treats as "already
    present, nothing to do", and does not roll back the batch.

    Returns the `(article_id, article)` pairs actually inserted from `passed`
    (mirroring what the caller's own per-article loop would have collected).
    Raises on genuine failure -- the caller decides how to record that; this
    function's only job is the transaction boundary.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    inserted: list = []
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")

        def _insert_one(article: dict) -> Optional[int]:
            source_id = _get_source_id_on(conn, article["source_slug"])
            if source_id is None:
                raise ValueError(
                    "unknown source slug: %s" % article["source_slug"])
            try:
                cur = conn.execute(
                    """
                    INSERT INTO articles
                        (url, content_hash, source_id, scrape_run_id,
                         title_original, text_original, published_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article["url"], article["content_hash"], source_id,
                        run_id, article.get("title_original"),
                        article.get("text_original"),
                        article.get("published_date"),
                    ),
                )
                return cur.lastrowid
            except sqlite3.IntegrityError:
                # Duplicate URL: the ordinary outcome insert_article() also
                # treats as "nothing to do", not a batch-breaking failure.
                return None

        for article in passed:
            aid = _insert_one(article)
            if aid is not None:
                inserted.append((aid, article))

        for article in rejected:
            aid = _insert_one(article)
            if aid is not None:
                conn.execute(
                    """
                    UPDATE articles
                       SET relevance_score     = ?,
                           relevance_reasoning = ?,
                           passed_relevance    = ?
                     WHERE id = ?
                    """,
                    (0.0, "failed keyword pre-filter", 0, aid),
                )

        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _get_source_id_on(conn: sqlite3.Connection, slug: str) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM sources WHERE slug = ?", (slug,)
    ).fetchone()
    return row["id"] if row else None


def update_relevance(
    article_id: int,
    score: float,
    reasoning: str,
    passed: bool,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE articles
               SET relevance_score     = ?,
                   relevance_reasoning = ?,
                   passed_relevance    = ?
             WHERE id = ?
            """,
            (score, reasoning, int(passed), article_id),
        )


def update_analysis(
    article_id: int,
    title_english: str,
    text_english: str,
    summary_english: str,
    is_significant: bool,
    significance_reasoning: Optional[str],
    categories: list[str],
    model_id: str,
    prompt_version: str,
) -> None:
    """Persist full analysis results and category tags for a single article."""
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE articles
               SET title_english          = ?,
                   text_english           = ?,
                   summary_english        = ?,
                   is_significant         = ?,
                   significance_reasoning = ?,
                   analyzed_at            = datetime('now'),
                   model_id               = ?,
                   prompt_version         = ?
             WHERE id = ?
            """,
            (
                title_english, text_english, summary_english,
                int(is_significant), significance_reasoning,
                model_id, prompt_version, article_id,
            ),
        )
        # Upsert categories via join table
        for slug in categories:
            row = conn.execute(
                "SELECT id FROM categories WHERE slug = ?", (slug,)
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT OR IGNORE INTO article_categories VALUES (?, ?)",
                    (article_id, row["id"]),
                )
            else:
                logger.warning(
                    "Category slug '%s' not in DB — skipping (check schema.sql seed data)",
                    slug,
                )


# ── Queries for pipeline resume ───────────────────────────────────────────────

def get_articles_pending_analysis() -> list[sqlite3.Row]:
    """
    Return articles that passed relevance but haven't been fully analyzed yet.
    Used to resume a pipeline that was interrupted after relevance scoring.

    Records dispositioned `paused` or `terminal` by `core.processing_state`
    are excluded. The two are not the same thing and must not be read as such:
    `terminal` is a statement about the document (its adapter found media and
    no prose), while `paused` only means the retry budget is spent and a human
    should look — `resume_paused_article()` puts it straight back. Neither is
    deleted; the row keeps its reason, attempt count and both timestamps, so
    "why did this stop" always has an answer.
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, url, title_original, text_original,
                   processing_attempts
              FROM articles
             WHERE passed_relevance = 1
               AND analyzed_at IS NULL
               AND COALESCE(processing_state, '') NOT IN ('paused', 'terminal')
             ORDER BY id
            """
        ).fetchall()


def get_articles_unscored() -> list[sqlite3.Row]:
    """
    Return articles inserted by a prior run that never reached LLM relevance
    scoring (passed_relevance IS NULL).  This happens when the API was
    unavailable during the run that scraped them.

    `scraped_at` is selected so the caller can order this queue by editorial
    liveness rather than plain FIFO — see the live-window split in pipeline.py
    (DECISION_LOG 2026-08-02).
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, url, title_original, text_original, scraped_at,
                   processing_attempts
              FROM articles
             WHERE passed_relevance IS NULL
               AND COALESCE(processing_state, '') NOT IN ('paused', 'terminal')
             ORDER BY id
            """
        ).fetchall()


def record_processing_failure(article_id: int, disposition) -> None:
    """
    Record one observed analysis failure against a record.

    Writes the state, the reason, the running attempt count and both
    timestamps. `processing_first_failed_at` is set once and never overwritten,
    so the history survives however many failures follow.

    `disposition` is a `core.processing_state.Disposition`.
    """
    from core.processing_state import now_utc

    stamp = now_utc()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE articles
               SET processing_state           = ?,
                   processing_reason          = ?,
                   processing_attempts        = ?,
                   processing_first_failed_at =
                       COALESCE(processing_first_failed_at, ?),
                   processing_last_failed_at  = ?
             WHERE id = ?
            """,
            (disposition.state, disposition.reason, disposition.attempts,
             stamp, stamp, article_id),
        )


def clear_processing_failure(article_id: int) -> None:
    """
    Forget a record's failure history once it has been analyzed successfully.

    A record that succeeds is not carrying a failure any more, and leaving a
    stale `retriable` state on it would misreport the corpus's health. Called
    only on success, so a terminal record — which by construction never reaches
    analysis again — keeps its history.
    """
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE articles
               SET processing_state           = NULL,
                   processing_reason          = NULL,
                   processing_attempts        = NULL,
                   processing_first_failed_at = NULL,
                   processing_last_failed_at  = NULL
             WHERE id = ?
            """,
            (article_id,),
        )


def get_articles_in_state(state: str) -> list:
    """
    Every record currently held in `state`, with its reason and history.

    This is the review queue: a human decides what to do, and until somebody
    does these sit here visibly rather than vanishing.
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, url, processing_state, processing_reason,
                   processing_attempts, processing_first_failed_at,
                   processing_last_failed_at
              FROM articles
             WHERE processing_state = ?
             ORDER BY id
            """,
            (state,),
        ).fetchall()


def get_terminal_articles() -> list:
    """Records whose content cannot be analyzed. Not reversible here."""
    return get_articles_in_state("terminal")


def get_paused_articles() -> list:
    """Records held for manual review because the retry budget ran out."""
    return get_articles_in_state("paused")


def resume_paused_article(article_id: int) -> bool:
    """
    Return one paused record to the automatic analysis queue.

    The recovery path for a spend control. The attempt count is reset — the
    budget is what paused it, so resuming without clearing it would pause the
    record again on its next failure — while `processing_reason` and both
    timestamps are **kept**, so the record still says it was paused once and
    when.

    Refuses a record that is not paused, and returns False rather than raising:
    a terminal record is a statement about its content and is not un-made by
    calling this, and a never-failed record has nothing to resume.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT processing_state FROM articles WHERE id = ?",
            (article_id,),
        ).fetchone()
        if row is None or row["processing_state"] != "paused":
            return False
        conn.execute(
            """
            UPDATE articles
               SET processing_state    = 'retriable',
                   processing_attempts = 0
             WHERE id = ?
            """,
            (article_id,),
        )
        return True


# ── Site-generation bulk fetch ────────────────────────────────────────────────

def get_all_analyzed_articles() -> list[sqlite3.Row]:
    """
    Return every fully analyzed article, newest first, with source info and
    a comma-separated category_slugs column pre-joined.  Used by the site
    generator to avoid N+1 category queries.
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT a.*,
                   s.slug          AS source_slug,
                   s.display_name  AS source_name,
                   s.language      AS source_language,
                   GROUP_CONCAT(c.slug) AS category_slugs
              FROM articles a
              JOIN sources s ON s.id = a.source_id
              LEFT JOIN article_categories ac ON ac.article_id = a.id
              LEFT JOIN categories c ON c.id = ac.category_id
             WHERE a.passed_relevance = 1
               AND a.analyzed_at IS NOT NULL
             GROUP BY a.id
             ORDER BY a.published_date DESC, a.is_significant DESC,
                      a.relevance_score DESC
            """
        ).fetchall()


# ── Aggregate counts ─────────────────────────────────────────────────────────

def get_total_analyzed_count() -> int:
    """Total articles with full analysis in DB (across all runs)."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM articles WHERE analyzed_at IS NOT NULL"
        ).fetchone()[0]


# ── Site-generation queries ───────────────────────────────────────────────────

def get_articles_for_date(date_str: str) -> list[sqlite3.Row]:
    """Return all analyzed articles for a given date, significance-first."""
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT a.*, s.display_name AS source_name, s.language AS source_language
              FROM articles a
              JOIN sources  s ON s.id = a.source_id
             WHERE a.published_date = ?
               AND a.passed_relevance = 1
               AND a.analyzed_at IS NOT NULL
             ORDER BY a.is_significant DESC, a.relevance_score DESC
            """,
            (date_str,),
        ).fetchall()


def get_article_categories(article_id: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.slug
              FROM article_categories ac
              JOIN categories c ON c.id = ac.category_id
             WHERE ac.article_id = ?
            """,
            (article_id,),
        ).fetchall()
    return [r["slug"] for r in rows]


def get_recent_dates(limit: int = 30) -> list[str]:
    """Return the most recent N distinct publication dates with analyzed articles."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT published_date
              FROM articles
             WHERE passed_relevance = 1
               AND analyzed_at IS NOT NULL
               AND published_date IS NOT NULL
             ORDER BY published_date DESC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [r["published_date"] for r in rows]


def get_articles_for_date_range(start_date: str, end_date: str) -> list[sqlite3.Row]:
    """
    Return all analyzed articles published between start_date and end_date (inclusive).
    Used by the weekly PLA Watch generator. Read-only.

    Not desk-aware: it takes every source at once. Briefs select by desk with
    `get_articles_for_desks()`.
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT a.*,
                   s.slug          AS source_slug,
                   s.display_name  AS source_name,
                   GROUP_CONCAT(c.slug) AS category_slugs
              FROM articles a
              JOIN sources s ON s.id = a.source_id
              LEFT JOIN article_categories ac ON ac.article_id = a.id
              LEFT JOIN categories c ON c.id = ac.category_id
             WHERE a.passed_relevance = 1
               AND a.analyzed_at IS NOT NULL
               AND a.published_date >= ?
               AND a.published_date <= ?
             GROUP BY a.id
             ORDER BY a.published_date DESC, a.is_significant DESC,
                      a.relevance_score DESC
            """,
            (start_date, end_date),
        ).fetchall()


# ── Desk-aware compatibility accessors ────────────────────────────────────────
#
# Migration 0003 added desk metadata to `sources` alongside the original
# columns. Nothing was dropped: `language` ('zh'/'en') and `is_active` are still
# there and still written. These accessors read the NEW column and fall back to
# the legacy one, so callers can be migrated one at a time and a database that
# has not been migrated yet keeps answering correctly.
#
# Removing the legacy columns is a later, separately approved cleanup. Until
# then the fallback is the contract, not a temporary hack.

def _has_column(conn, table: str, column: str) -> bool:
    return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})"))


def get_source_language_tag(slug: str) -> Optional[str]:
    """
    BCP 47 tag for a source, e.g. 'zh-Hans'.

    Falls back to widening the legacy bare code: 'zh' -> 'zh-Hans' is correct
    for every current source (all PRC simplified-script publications) and is
    recorded explicitly in the China manifest rather than inferred at runtime.
    """
    with get_conn() as conn:
        if _has_column(conn, "sources", "language_tag"):
            row = conn.execute(
                "SELECT language_tag, language FROM sources WHERE slug = ?", (slug,)
            ).fetchone()
            if row is None:
                return None
            if row["language_tag"]:
                return row["language_tag"]
            legacy = row["language"]
        else:
            row = conn.execute(
                "SELECT language FROM sources WHERE slug = ?", (slug,)
            ).fetchone()
            if row is None:
                return None
            legacy = row["language"]
    return {"zh": "zh-Hans", "en": "en"}.get(legacy, legacy)


def get_source_desk_id(slug: str) -> Optional[str]:
    """Desk owning a source, or None on an unmigrated database."""
    with get_conn() as conn:
        if not _has_column(conn, "sources", "desk_id"):
            return None
        row = conn.execute(
            "SELECT desk_id FROM sources WHERE slug = ?", (slug,)
        ).fetchone()
    return row["desk_id"] if row else None


def source_is_enabled(slug: str) -> bool:
    """`enabled` if migrated, else the legacy `is_active`."""
    with get_conn() as conn:
        has_enabled = _has_column(conn, "sources", "enabled")
        row = conn.execute(
            "SELECT %s AS enabled, is_active FROM sources WHERE slug = ?"
            % ("enabled" if has_enabled else "NULL"),
            (slug,),
        ).fetchone()
    if row is None:
        return False
    if row["enabled"] is not None:
        return bool(row["enabled"])
    return bool(row["is_active"])


def get_sources_with_desk_metadata() -> list:
    """All sources with whatever desk metadata exists. Read-only."""
    with get_conn() as conn:
        if not _has_column(conn, "sources", "desk_id"):
            return conn.execute(
                "SELECT slug, display_name, base_url, language, is_active "
                "FROM sources ORDER BY slug"
            ).fetchall()
        return conn.execute(
            """
            SELECT s.*, d.display_name AS desk_display_name,
                   i.display_name AS institution_display_name
              FROM sources s
              LEFT JOIN desks d ON d.desk_id = s.desk_id
              LEFT JOIN institutions i ON i.institution_id = s.institution_id
             ORDER BY s.slug
            """
        ).fetchall()


def get_articles_for_desks(start_date: str, end_date: str, desks,
                           conn: Optional[sqlite3.Connection] = None) -> list:
    """
    Every stored record from the named desks' sources published between
    start_date and end_date (inclusive), whatever its screening state.
    Read-only.

    The brief-authoring counterpart of `get_articles_for_date_range()`, which
    serves the predecessor weekly and takes analyzed records from every source
    at once. Here a desk contributes only if it is named. Each row carries the
    desk that owns its source (`desk_id`) and that source's language
    (`source_language_tag`, widening the legacy bare code exactly as
    `get_source_language_tag()` does). The two are independent: the China Desk
    collects two English-language sources.

    Screening state is carried, not filtered on. Desks do not share one
    pipeline — the Singapore records promoted on 2026-09-21 have never been
    relevance-screened — so the weekly generator's `passed_relevance = 1 AND
    analyzed_at IS NOT NULL` would silently drop a whole desk.

    `conn` lets a caller read through `scripts.reconcile_db.read_only()`, so an
    authoring run cannot leave `-wal`/`-shm` beside the tracked database.
    """
    desk_ids = sorted({str(d).strip() for d in (desks or ()) if str(d).strip()})
    if not desk_ids:
        raise ValueError("name at least one desk; selection is never unscoped")

    def run(c):
        if not _has_column(c, "sources", "desk_id"):
            raise RuntimeError(
                "sources has no desk_id (migration 0003 not applied): records "
                "cannot be selected by desk, and their desk is not guessed")
        legacy = "CASE s.language WHEN 'zh' THEN 'zh-Hans' ELSE s.language END"
        tag = ("COALESCE(NULLIF(s.language_tag, ''), %s)" % legacy
               if _has_column(c, "sources", "language_tag") else legacy)
        cur = c.cursor()
        cur.row_factory = sqlite3.Row
        return cur.execute(
            """
            SELECT a.*,
                   s.slug          AS source_slug,
                   s.display_name  AS source_name,
                   s.desk_id       AS desk_id,
                   %s AS source_language_tag
              FROM articles a
              JOIN sources s ON s.id = a.source_id
             WHERE s.desk_id IN (%s)
               AND a.published_date >= ?
               AND a.published_date <= ?
             ORDER BY s.desk_id, a.published_date DESC, a.id DESC
            """ % (tag, ",".join("?" * len(desk_ids))),
            (*desk_ids, start_date, end_date),
        ).fetchall()

    if conn is not None:
        return run(conn)
    with get_conn() as c:
        return run(c)


# ── Per-source collection results ─────────────────────────────────────────────

def record_source_run_result(run_id: int, result) -> None:
    """
    Persist one source's outcome for one run (upsert on (run, source)).

    `result` is a core.collection.contract.SourceRunResult. `is_failure` is
    stored rather than derived so that changing the status vocabulary later
    cannot retroactively rewrite what an old run reported.
    """
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='source_run_results'"
        ).fetchone():
            logger.warning(
                "source_run_results table missing — run migrations; "
                "skipping per-source result for %s", result.source_slug,
            )
            return
        conn.execute(
            """
            INSERT INTO source_run_results
                (scrape_run_id, source_slug, desk_id, status, is_failure,
                 started_at, completed_at, references_discovered, fetched,
                 extracted, duplicates, new_documents, relevance_rejected,
                 failed_fetches, text_unavailable, error_detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scrape_run_id, source_slug) DO UPDATE SET
                status                = excluded.status,
                is_failure            = excluded.is_failure,
                completed_at          = excluded.completed_at,
                references_discovered = excluded.references_discovered,
                fetched               = excluded.fetched,
                extracted             = excluded.extracted,
                text_unavailable      = excluded.text_unavailable,
                duplicates            = excluded.duplicates,
                new_documents         = excluded.new_documents,
                relevance_rejected    = excluded.relevance_rejected,
                failed_fetches        = excluded.failed_fetches,
                error_detail          = excluded.error_detail
            """,
            (run_id, result.source_slug, result.desk_id, result.status,
             1 if result.is_failure else 0, result.started_at,
             result.completed_at, result.references_discovered, result.fetched,
             result.extracted, result.duplicates, result.new_documents,
             result.relevance_rejected, result.failed_fetches,
             result.text_unavailable, result.error_detail),
        )


def get_source_run_results(run_id: int) -> list:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='source_run_results'"
        ).fetchone():
            return []
        return conn.execute(
            "SELECT * FROM source_run_results WHERE scrape_run_id = ? "
            "ORDER BY source_slug",
            (run_id,),
        ).fetchall()


def get_last_success_by_source() -> dict:
    """
    Most recent run in which each source produced a new document.

    Answers "when did this source last actually deliver?" — which a green run
    does not, and which is the question MOD China's four silent weeks needed
    someone to be asking.
    """
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='source_run_results'"
        ).fetchone():
            return {}
        rows = conn.execute(
            """
            SELECT source_slug,
                   MAX(CASE WHEN new_documents > 0 THEN completed_at END)
                       AS last_new_document,
                   MAX(CASE WHEN is_failure = 0 THEN completed_at END)
                       AS last_successful_collection
              FROM source_run_results
             GROUP BY source_slug
            """
        ).fetchall()
    return {r["source_slug"]: dict(r) for r in rows}
