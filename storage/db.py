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
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, url, title_original, text_original
              FROM articles
             WHERE passed_relevance = 1
               AND analyzed_at IS NULL
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
            SELECT id, url, title_original, text_original, scraped_at
              FROM articles
             WHERE passed_relevance IS NULL
             ORDER BY id
            """
        ).fetchall()


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
