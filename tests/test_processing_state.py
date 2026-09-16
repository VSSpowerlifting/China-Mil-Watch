"""
The terminal processing state — classification, storage and the queue.

The defect this closes: a record that can never be analyzed re-entered the
analysis queue on every run for ever. Measured on the tracked corpus
2026-09-16, article 2678 had been retried on 28 separate runs and five records
were in that state together, each costing a model call per run and each
occupying one of the reserved backlog slots that real material needs.

Offline. The database cases build a throwaway SQLite file with the columns
migration 0007 adds; nothing here opens the tracked database.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core import processing_state as ps                          # noqa: E402
from migrations.versions import (                                # noqa: E402
    m0007_article_processing_state as m0007,
)


class TestClassification(unittest.TestCase):
    """Which failures are worth retrying, and which are a loop."""

    def test_a_first_failure_with_a_body_is_retriable(self):
        d = ps.classify(attempts_before=None, has_body=True,
                        failure="analysis_incomplete")
        self.assertFalse(d.is_terminal)
        self.assertEqual(d.attempts, 1)
        self.assertEqual(d.reason, "analysis_incomplete")

    def test_an_empty_body_is_retriable_before_the_budget(self):
        """
        The case that matters. Records 3432, 3946 and 3948 held empty bodies
        because the extractor had been left behind by a template change, not
        because the documents were empty. Terminal-on-sight would have made an
        extraction regression permanent and invisible.
        """
        d = ps.classify(attempts_before=None, has_body=False,
                        failure="analysis_incomplete")
        self.assertFalse(d.is_terminal)
        self.assertEqual(d.reason, "no_prose_body")

    def test_the_budget_ends_the_retries(self):
        d = ps.classify(attempts_before=ps.RETRY_BUDGET - 1, has_body=False,
                        failure="analysis_incomplete")
        self.assertTrue(d.is_terminal)
        self.assertEqual(d.reason, "no_prose_body_budget_exhausted")
        self.assertEqual(d.attempts, ps.RETRY_BUDGET)

    def test_the_budget_distinguishes_an_empty_body_from_a_failed_call(self):
        with_body = ps.classify(attempts_before=ps.RETRY_BUDGET - 1,
                                has_body=True, failure="analysis_failed")
        self.assertEqual(with_body.reason, "analysis_failed_budget_exhausted")

    def test_an_unsupported_document_is_terminal_at_once(self):
        d = ps.classify(attempts_before=None, has_body=False,
                        failure="analysis_failed", unsupported=True)
        self.assertTrue(d.is_terminal)
        self.assertEqual(d.reason, "unsupported_document")

    def test_attempts_only_ever_advance(self):
        attempts = None
        for expected in range(1, ps.RETRY_BUDGET + 1):
            d = ps.classify(attempts_before=attempts, has_body=True,
                            failure="analysis_failed")
            self.assertEqual(d.attempts, expected)
            attempts = d.attempts

    def test_the_reason_vocabulary_is_closed(self):
        """A free-text reason is how a taxonomy stops meaning anything."""
        seen = set()
        for attempts in (None, 1, ps.RETRY_BUDGET - 1, ps.RETRY_BUDGET):
            for body in (True, False):
                for failure in ("analysis_failed", "analysis_incomplete"):
                    for unsupported in (True, False):
                        seen.add(ps.classify(
                            attempts_before=attempts, has_body=body,
                            failure=failure, unsupported=unsupported).reason)
        self.assertTrue(seen <= set(ps.REASONS),
                        "undeclared reason(s): %s" % (seen - set(ps.REASONS)))

    def test_an_unknown_failure_kind_is_refused(self):
        with self.assertRaises(ValueError):
            ps.classify(attempts_before=None, has_body=True,
                        failure="vibes")

    def test_the_budget_is_not_one(self):
        """One strike would make every transient model failure permanent."""
        self.assertGreater(ps.RETRY_BUDGET, 1)


class TestMigration(unittest.TestCase):
    """0007 adds columns and writes no row."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        con = sqlite3.connect(str(self.db))
        con.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT, "
                    "passed_relevance INTEGER, analyzed_at TEXT)")
        con.execute("INSERT INTO articles (id, url, passed_relevance) "
                    "VALUES (1, 'u', 1)")
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def columns(self, con):
        return {r[1] for r in con.execute("PRAGMA table_info(articles)")}

    def test_it_reports_itself_unapplied_then_applied(self):
        con = sqlite3.connect(str(self.db))
        self.assertFalse(m0007.is_already_applied(con))
        m0007.up(con)
        con.commit()
        self.assertTrue(m0007.is_already_applied(con))
        con.close()

    def test_every_declared_column_arrives(self):
        con = sqlite3.connect(str(self.db))
        m0007.up(con)
        con.commit()
        for name, _type in m0007._COLUMNS:
            self.assertIn(name, self.columns(con))
        con.close()

    def test_existing_rows_are_left_null(self):
        """NULL says 'not measured'. A default 0 would be a claim."""
        con = sqlite3.connect(str(self.db))
        m0007.up(con)
        con.commit()
        row = con.execute("SELECT processing_state, processing_attempts, "
                          "processing_reason FROM articles WHERE id=1"
                          ).fetchone()
        self.assertEqual(row, (None, None, None))
        con.close()

    def test_it_is_idempotent(self):
        con = sqlite3.connect(str(self.db))
        m0007.up(con)
        con.commit()
        before = self.columns(con)
        m0007.up(con)
        con.commit()
        self.assertEqual(self.columns(con), before)
        con.close()

    def test_an_absent_table_is_a_no_op_not_a_failure(self):
        other = Path(self.tmp.name) / "empty.db"
        con = sqlite3.connect(str(other))
        self.assertTrue(m0007.is_already_applied(con))
        m0007.up(con)          # must not raise
        con.close()


class TestQueueExclusion(unittest.TestCase):
    """A terminal record leaves the queue; a retriable one does not."""

    PENDING = ("SELECT id FROM articles "
               " WHERE passed_relevance = 1 AND analyzed_at IS NULL "
               "   AND COALESCE(processing_state, '') <> 'terminal' "
               " ORDER BY id")
    UNSCORED = ("SELECT id FROM articles "
                " WHERE passed_relevance IS NULL "
                "   AND COALESCE(processing_state, '') <> 'terminal' "
                " ORDER BY id")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "q.db"
        con = sqlite3.connect(str(self.db))
        con.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT, "
                    "passed_relevance INTEGER, analyzed_at TEXT)")
        m0007.up(con)
        rows = [
            (1, 1,    None, None),          # pending, never failed
            (2, 1,    None, "retriable"),   # pending, failing but eligible
            (3, 1,    None, "terminal"),    # pending, done retrying
            (4, None, None, None),          # unscored, never failed
            (5, None, None, "terminal"),    # unscored, done retrying
            (6, 1,    "2026-09-16", None),  # already analyzed
        ]
        for rid, passed, analyzed, state in rows:
            con.execute("INSERT INTO articles (id, url, passed_relevance, "
                        "analyzed_at, processing_state) VALUES (?,?,?,?,?)",
                        (rid, "u%d" % rid, passed, analyzed, state))
        con.commit()
        self.con = con

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_the_pending_queue_drops_only_terminal_records(self):
        self.assertEqual([r[0] for r in self.con.execute(self.PENDING)],
                         [1, 2])

    def test_the_unscored_queue_drops_only_terminal_records(self):
        self.assertEqual([r[0] for r in self.con.execute(self.UNSCORED)], [4])

    def test_a_terminal_record_is_excluded_not_deleted(self):
        """'Stopped being retried' and 'dropped quietly' are different."""
        self.assertEqual(
            self.con.execute("SELECT COUNT(*) FROM articles").fetchone()[0], 6)

    def test_the_live_queries_carry_the_same_guard(self):
        """The assertions above are only worth anything if db.py agrees."""
        source = (REPO_ROOT / "storage" / "db.py").read_text(encoding="utf-8")
        self.assertEqual(
            source.count("COALESCE(processing_state, '') <> 'terminal'"), 2,
            "both analysis-queue queries must exclude terminal records")


if __name__ == "__main__":
    unittest.main()
