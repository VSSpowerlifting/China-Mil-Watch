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


class TestTransientFailuresAreNeverPermanent(unittest.TestCase):
    """
    BLOCKER 1, proof 1. An attempt counter measures this project's luck, not
    the document's nature, and only the document's nature is grounds for a
    permanent disposition.
    """

    def test_five_transient_failures_create_no_permanent_disposition(self):
        attempts = None
        for _ in range(ps.RETRY_BUDGET):
            d = ps.classify(attempts_before=attempts, has_body=True,
                            failure=ps.TRANSIENT)
            attempts = d.attempts
            self.assertFalse(d.is_terminal)
            self.assertFalse(d.is_permanent_content_disposition)
        self.assertEqual(attempts, ps.RETRY_BUDGET)

    def test_a_transient_failure_does_not_even_leave_the_queue(self):
        """
        An account-level outage would otherwise pause the whole backlog at
        once. Our billing lapsing is not the document's fault.
        """
        for extra in (0, ps.RETRY_BUDGET, ps.RETRY_BUDGET * 10):
            with self.subTest(attempts_before=extra):
                d = ps.classify(attempts_before=extra, has_body=True,
                                failure=ps.TRANSIENT)
                self.assertEqual(d.state, ps.RETRIABLE)
                self.assertFalse(d.leaves_queue)

    def test_an_empty_body_never_goes_terminal_on_the_counter_alone(self):
        """
        Records 3432, 3946 and 3948 held empty bodies because an extractor had
        been left behind by a template change, not because the documents were
        empty. A counter cannot tell those apart, so it is not allowed to try.
        """
        d = ps.classify(attempts_before=ps.RETRY_BUDGET * 4, has_body=False,
                        failure=ps.ANALYSIS_INCOMPLETE)
        self.assertEqual(d.state, ps.PAUSED)
        self.assertFalse(d.is_terminal)
        self.assertNotIn(d.reason, ps.TERMINAL_REASONS)

    def test_no_failure_kind_can_reach_terminal_without_a_verdict(self):
        for failure in ps.FAILURES:
            for body in (True, False):
                for attempts in (None, 1, ps.RETRY_BUDGET, 500):
                    with self.subTest(failure=failure, body=body,
                                      attempts=attempts):
                        d = ps.classify(attempts_before=attempts,
                                        has_body=body, failure=failure)
                        self.assertNotEqual(d.state, ps.TERMINAL)


class TestPauseIsReversible(unittest.TestCase):
    """BLOCKER 1, proof 2 (classification half; the DB half is below)."""

    def test_the_budget_pauses_rather_than_disposing(self):
        d = ps.classify(attempts_before=ps.RETRY_BUDGET - 1, has_body=True,
                        failure=ps.ANALYSIS_INCOMPLETE)
        self.assertEqual(d.state, ps.PAUSED)
        self.assertEqual(d.reason, "retry_budget_exhausted")
        self.assertTrue(d.leaves_queue)
        self.assertFalse(d.is_permanent_content_disposition)

    def test_paused_and_terminal_are_distinguishable(self):
        paused = ps.classify(attempts_before=ps.RETRY_BUDGET - 1,
                             has_body=True, failure=ps.ANALYSIS_FAILED)
        terminal = ps.classify(attempts_before=None, has_body=False,
                               failure=ps.ANALYSIS_FAILED,
                               content_verdict=ps.MEDIA_ONLY)
        self.assertNotEqual(paused.state, terminal.state)
        self.assertTrue(terminal.is_permanent_content_disposition)
        self.assertFalse(paused.is_permanent_content_disposition)
        self.assertTrue(paused.leaves_queue and terminal.leaves_queue)

    def test_resume_returns_a_record_to_the_queue_with_a_fresh_budget(self):
        d = ps.resume()
        self.assertEqual(d.state, ps.RETRIABLE)
        self.assertEqual(d.attempts, 0)
        self.assertFalse(d.leaves_queue)


class TestOnlyContentReachesTerminal(unittest.TestCase):
    """BLOCKER 1, proof 3 (classification half)."""

    def test_a_media_only_verdict_is_terminal_at_once(self):
        d = ps.classify(attempts_before=None, has_body=False,
                        failure=ps.ANALYSIS_FAILED,
                        content_verdict=ps.MEDIA_ONLY)
        self.assertTrue(d.is_terminal)
        self.assertEqual(d.reason, "unsupported_media_only")
        self.assertTrue(d.is_permanent_content_disposition)

    def test_an_explicit_no_prose_verdict_is_terminal(self):
        d = ps.classify(attempts_before=None, has_body=False,
                        failure=ps.ANALYSIS_FAILED,
                        content_verdict=ps.NO_USABLE_PROSE)
        self.assertTrue(d.is_terminal)
        self.assertEqual(d.reason, "no_usable_prose")

    def test_an_unknown_verdict_is_refused(self):
        with self.assertRaises(ValueError):
            ps.classify(attempts_before=None, has_body=False,
                        failure=ps.ANALYSIS_FAILED,
                        content_verdict="probably_nothing")

    def test_an_unknown_failure_kind_is_refused(self):
        with self.assertRaises(ValueError):
            ps.classify(attempts_before=None, has_body=True, failure="vibes")

    def test_the_reason_vocabulary_is_closed(self):
        seen = set()
        for attempts in (None, 1, ps.RETRY_BUDGET - 1, ps.RETRY_BUDGET):
            for body in (True, False):
                for failure in ps.FAILURES:
                    for verdict in (None,) + ps.CONTENT_VERDICTS:
                        seen.add(ps.classify(
                            attempts_before=attempts, has_body=body,
                            failure=failure, content_verdict=verdict).reason)
        self.assertTrue(seen <= set(ps.REASONS),
                        "undeclared reason(s): %s" % (seen - set(ps.REASONS)))

    def test_each_reason_belongs_to_exactly_one_state(self):
        groups = (set(ps.TERMINAL_REASONS), set(ps.PAUSED_REASONS),
                  set(ps.RETRIABLE_REASONS))
        for i, a in enumerate(groups):
            for b in groups[i + 1:]:
                self.assertFalse(a & b, "reason belongs to two states: %s"
                                 % (a & b))

    def test_attempts_only_ever_advance(self):
        attempts = None
        for expected in range(1, ps.RETRY_BUDGET + 1):
            d = ps.classify(attempts_before=attempts, has_body=True,
                            failure=ps.ANALYSIS_FAILED)
            self.assertEqual(d.attempts, expected)
            attempts = d.attempts

    def test_the_budget_is_not_one(self):
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
               "   AND COALESCE(processing_state, '') NOT IN ('paused','terminal') "
               " ORDER BY id")
    UNSCORED = ("SELECT id FROM articles "
                " WHERE passed_relevance IS NULL "
                "   AND COALESCE(processing_state, '') NOT IN ('paused','terminal') "
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
            source.count(
                "COALESCE(processing_state, '') NOT IN ('paused', 'terminal')"),
            2, "both analysis-queue queries must exclude paused and terminal")


if __name__ == "__main__":
    unittest.main()


class TestStateLifecycleAgainstTheDatabase(unittest.TestCase):
    """
    BLOCKER 1, proofs 2, 4 and 5, driven through the real storage functions
    rather than hand-written SQL, so the queries under test are the ones the
    pipeline actually runs.
    """

    def setUp(self):
        import storage.db as sdb
        self.sdb = sdb
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "lifecycle.db"
        con = sqlite3.connect(str(self.db))
        con.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT, "
                    "passed_relevance INTEGER, analyzed_at TEXT, "
                    "title_original TEXT, text_original TEXT, scraped_at TEXT)")
        m0007.up(con)
        for rid in (1, 2, 3):
            con.execute("INSERT INTO articles (id, url, passed_relevance, "
                        "title_original, text_original) VALUES (?,?,1,?,?)",
                        (rid, "u%d" % rid, "t%d" % rid, "body text"))
        con.commit()
        con.close()
        self._saved = sdb.DB_PATH
        sdb.DB_PATH = self.db

    def tearDown(self):
        self.sdb.DB_PATH = self._saved
        self.tmp.cleanup()

    def queue_ids(self):
        return [r["id"] for r in self.sdb.get_articles_pending_analysis()]

    def state_of(self, rid):
        con = sqlite3.connect(str(self.db))
        try:
            return con.execute(
                "SELECT processing_state, processing_reason, "
                "processing_attempts, processing_first_failed_at "
                "  FROM articles WHERE id = ?", (rid,)).fetchone()
        finally:
            con.close()

    def fail_until_paused(self, rid):
        attempts = None
        for _ in range(ps.RETRY_BUDGET):
            d = ps.classify(attempts_before=attempts, has_body=True,
                            failure=ps.ANALYSIS_INCOMPLETE)
            self.sdb.record_processing_failure(rid, d)
            attempts = d.attempts
        return attempts

    # ── proof 2 ──────────────────────────────────────────────────────────────

    def test_a_paused_record_can_be_resumed_and_then_analyzed(self):
        self.fail_until_paused(1)
        self.assertEqual(self.state_of(1)[0], "paused")
        self.assertNotIn(1, self.queue_ids())

        self.assertTrue(self.sdb.resume_paused_article(1))
        self.assertIn(1, self.queue_ids(), "resume did not re-queue the record")
        state, reason, attempts, first = self.state_of(1)
        self.assertEqual(state, "retriable")
        self.assertEqual(attempts, 0, "the budget was not reset")
        self.assertEqual(reason, "retry_budget_exhausted",
                         "the record must still say it was paused once")
        self.assertIsNotNone(first, "the failure history was discarded")

        # …and a successful analysis afterwards clears it completely.
        self.sdb.clear_processing_failure(1)
        self.assertEqual(self.state_of(1), (None, None, None, None))
        self.assertIn(1, self.queue_ids())

    def test_resume_refuses_a_record_that_is_not_paused(self):
        d = ps.classify(attempts_before=None, has_body=False,
                        failure=ps.ANALYSIS_FAILED,
                        content_verdict=ps.MEDIA_ONLY)
        self.sdb.record_processing_failure(2, d)
        self.assertFalse(self.sdb.resume_paused_article(2),
                         "a terminal record is not un-made by resume()")
        self.assertEqual(self.state_of(2)[0], "terminal")
        self.assertFalse(self.sdb.resume_paused_article(3))
        self.assertFalse(self.sdb.resume_paused_article(999))

    def test_paused_and_terminal_are_listed_separately(self):
        self.fail_until_paused(1)
        self.sdb.record_processing_failure(2, ps.classify(
            attempts_before=None, has_body=False, failure=ps.ANALYSIS_FAILED,
            content_verdict=ps.MEDIA_ONLY))
        self.assertEqual([r["id"] for r in self.sdb.get_paused_articles()], [1])
        self.assertEqual([r["id"] for r in self.sdb.get_terminal_articles()],
                         [2])

    # ── proof 4 ──────────────────────────────────────────────────────────────

    def test_a_terminal_record_stays_out_across_repeated_queue_builds(self):
        self.sdb.record_processing_failure(2, ps.classify(
            attempts_before=None, has_body=False, failure=ps.ANALYSIS_FAILED,
            content_verdict=ps.MEDIA_ONLY))
        for run in range(5):
            with self.subTest(run=run):
                self.assertNotIn(2, self.queue_ids())
        self.assertEqual(self.state_of(2)[2], 1,
                         "a queue build advanced a terminal record's counter")

    def test_a_terminal_record_is_excluded_not_deleted(self):
        self.sdb.record_processing_failure(2, ps.classify(
            attempts_before=None, has_body=False, failure=ps.ANALYSIS_FAILED,
            content_verdict=ps.MEDIA_ONLY))
        con = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(
                con.execute("SELECT COUNT(*) FROM articles").fetchone()[0], 3)
        finally:
            con.close()

    # ── proof 5 ──────────────────────────────────────────────────────────────

    def test_untouched_records_are_unaffected_by_another_s_disposition(self):
        before = self.queue_ids()
        self.fail_until_paused(1)
        self.sdb.record_processing_failure(2, ps.classify(
            attempts_before=None, has_body=False, failure=ps.ANALYSIS_FAILED,
            content_verdict=ps.MEDIA_ONLY))
        self.assertEqual(self.queue_ids(), [3])
        self.assertEqual(self.state_of(3), (None, None, None, None))
        self.assertEqual(sorted(before), [1, 2, 3])

    def test_a_transient_failure_leaves_the_record_queued(self):
        attempts = None
        for _ in range(ps.RETRY_BUDGET * 2):
            d = ps.classify(attempts_before=attempts, has_body=True,
                            failure=ps.TRANSIENT)
            self.sdb.record_processing_failure(3, d)
            attempts = d.attempts
        self.assertIn(3, self.queue_ids(),
                      "an API outage removed a good document from the queue")
        self.assertEqual(self.state_of(3)[0], "retriable")


class TestAdapterVerdictReachesTerminal(unittest.TestCase):
    """
    BLOCKER 1, proof 3. End to end: a recorded fixture, through the adapter's
    own verdict, into a terminal state — and the drift control that must not.
    """

    FIXTURES = REPO_ROOT / "tests" / "fixtures" / "xinhua_mil"
    URL = "https://www.news.cn/milpro/20260915/" + "a" * 32 + "/c.html"

    def parsed(self, name):
        from scraper.sources.xinhua_mil import XinhuaMilScraper
        return XinhuaMilScraper().parse_article(
            self.URL, (self.FIXTURES / name).read_text(encoding="utf-8"))

    def test_a_photo_set_fixture_is_classified_terminal(self):
        article = self.parsed("derived_media_only.html")
        self.assertEqual(article["text_original"], "")
        self.assertEqual(article["content_verdict"], ps.MEDIA_ONLY)

        d = ps.classify(attempts_before=None, has_body=False,
                        failure=ps.ANALYSIS_FAILED,
                        content_verdict=article["content_verdict"])
        self.assertTrue(d.is_terminal)
        self.assertTrue(d.is_permanent_content_disposition)
        self.assertEqual(d.reason, "unsupported_media_only")
        self.assertEqual(d.attempts, 1, "a photo set should not need five runs")

    def test_a_real_article_yields_no_verdict(self):
        article = self.parsed("article_hormuz_transits.html")
        self.assertTrue(article["text_original"].strip())
        self.assertIsNone(article["content_verdict"])

    def test_template_drift_yields_no_verdict(self):
        """
        The Global Times defect in miniature: when the body container is gone
        the adapter cannot tell an empty document from an unreadable one, so it
        says nothing and the record stays retriable.
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(
            (self.FIXTURES / "derived_media_only.html").read_text(
                encoding="utf-8"), "lxml")
        soup.find(id="detail").decompose()
        from scraper.sources.xinhua_mil import XinhuaMilScraper
        article = XinhuaMilScraper().parse_article(self.URL, str(soup))
        self.assertEqual(article["text_original"], "")
        self.assertIsNone(article["content_verdict"],
                          "template drift was reported as a content verdict")

        d = ps.classify(attempts_before=None, has_body=False,
                        failure=ps.ANALYSIS_FAILED,
                        content_verdict=article["content_verdict"])
        self.assertFalse(d.is_terminal)

    def test_the_pipeline_only_offers_verdicts_it_actually_has(self):
        """
        Backlog records carry no verdict — nothing stores one — so they can
        only ever be retriable or paused. That is deliberate, and this asserts
        the pipeline builds the map from records scraped this run.
        """
        source = (REPO_ROOT / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn('aid: a.get("content_verdict")', source)
        self.assertIn("for aid, a in inserted", source)
