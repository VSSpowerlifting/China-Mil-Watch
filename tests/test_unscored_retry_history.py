"""Unscored Daily backlog must honor the existing reversible retry budget.

No provider calls, no network, no tracked database writes. Synthetic SQLite
fixtures exercise the same storage row selectors and failure persistence used
by pipeline.py. No record may become terminal on attempt count alone.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core import processing_state as ps
from migrations.versions import m0007_article_processing_state as m0007
from pipeline import prior_processing_attempts
from storage import db as sdb


class UnscoredRetryHistoryContracts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-unscored-retry-")
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "isolated.db"
        self.previous_db = sdb.DB_PATH
        self.addCleanup(setattr, sdb, "DB_PATH", self.previous_db)
        con = sqlite3.connect(str(self.db))
        try:
            con.execute("""
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY, url TEXT,
                    passed_relevance INTEGER, analyzed_at TEXT,
                    title_original TEXT, text_original TEXT,
                    scraped_at TEXT
                )
            """)
            m0007.up(con)
            con.executemany(
                """INSERT INTO articles
                   (id, url, passed_relevance, analyzed_at, title_original,
                    text_original, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (1, "https://example.invalid/never-scored", None, None,
                     "Relevant but malformed relevance JSON",
                     "Verified source body", "2026-10-01"),
                    (2, "https://example.invalid/pending", 1, None,
                     "Already relevance-passed",
                     "Second source body", "2026-10-01"),
                    (3, "https://example.invalid/unattempted", None, None,
                     "Never attempted", "Third source body", "2026-10-01"),
                    (4, "https://example.invalid/complete", 1,
                     "2026-10-02", "Completed", "Completed text", "2026-10-01"),
                ],
            )
            con.commit()
        finally:
            con.close()
        sdb.DB_PATH = self.db

    def history(self):
        pending = sdb.get_articles_pending_analysis()
        unscored = sdb.get_articles_unscored()
        return prior_processing_attempts(pending, unscored)

    def snapshot(self, rid):
        with sqlite3.connect(str(self.db)) as conn:
            return conn.execute(
                "SELECT processing_state, processing_reason, processing_attempts,"
                "       processing_first_failed_at, processing_last_failed_at,"
                "       url, text_original"
                "  FROM articles WHERE id=?", (rid,),
            ).fetchone()

    def fail(self, rid, kind=ps.ANALYSIS_FAILED):
        n = self.history().get(rid)
        d = ps.classify(
            attempts_before=n, has_body=True, failure=kind)
        sdb.record_processing_failure(rid, d)
        return d

    def test_pipeline_reads_both_actual_storage_lanes(self):
        # Protect the site of integration, not just the pure helper.
        source = (Path(__file__).resolve().parents[1] / "pipeline.py").read_text()
        self.assertIn(
            "attempts_before = prior_processing_attempts(pending_rows, unscored_rows)",
            source,
        )
        self.assertEqual(self.history(), {})
        self.fail(1)
        self.fail(2, ps.ANALYSIS_INCOMPLETE)
        self.assertEqual(self.history(), {1: 1, 2: 1})
        self.assertNotIn(3, self.history())
        self.assertNotIn(4, self.history())

    def test_repeated_relevance_failure_pauses_unscored_at_budget(self):
        for i in range(1, ps.RETRY_BUDGET + 1):
            queued = [r["id"] for r in sdb.get_articles_unscored()]
            self.assertIn(1, queued)
            d = self.fail(1)
            self.assertEqual(d.attempts, i)
            self.assertNotEqual(d.state, ps.TERMINAL)
            self.assertEqual(self.snapshot(1)[2], i)
            if i < ps.RETRY_BUDGET:
                self.assertEqual(d.state, ps.RETRIABLE)
                self.assertEqual(self.history()[1], i)
            else:
                self.assertEqual(d.state, ps.PAUSED)
                self.assertEqual(d.reason, "retry_budget_exhausted")
        self.assertNotIn(1, [r["id"] for r in sdb.get_articles_unscored()])
        self.assertEqual(self.snapshot(1)[5:],
                         ("https://example.invalid/never-scored",
                          "Verified source body"))
        self.assertIsNotNone(self.snapshot(1)[3])
        self.assertIsNotNone(self.snapshot(1)[4])

    def test_paused_article_requires_explicit_resume(self):
        for _ in range(ps.RETRY_BUDGET):
            self.fail(1)
        original_body = self.snapshot(1)[-1]
        self.assertNotIn(1, self.history())
        self.assertTrue(sdb.resume_paused_article(1))
        self.assertEqual(self.history()[1], 0)
        self.assertEqual(self.fail(1).attempts, 1)
        self.assertEqual(self.snapshot(1)[-1], original_body)
        self.assertEqual(self.snapshot(1)[0], ps.RETRIABLE)

    def test_pending_lane_retains_existing_retry_semantics(self):
        for i in range(1, ps.RETRY_BUDGET + 1):
            d = self.fail(2, ps.ANALYSIS_INCOMPLETE)
            self.assertEqual(d.attempts, i)
        self.assertNotIn(2, [r["id"] for r in sdb.get_articles_pending_analysis()])
        self.assertEqual(self.snapshot(2)[0], ps.PAUSED)

    def test_transient_failure_is_not_paused_even_beyond_budget(self):
        for i in range(1, ps.RETRY_BUDGET + 4):
            d = self.fail(1, ps.TRANSIENT)
            self.assertEqual(d.attempts, i)
            self.assertEqual(d.state, ps.RETRIABLE)
        self.assertIn(1, [r["id"] for r in sdb.get_articles_unscored()])
        self.assertEqual(self.snapshot(1)[1], "transient_failure")


if __name__ == "__main__":
    unittest.main()
