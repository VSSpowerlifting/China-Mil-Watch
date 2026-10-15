"""Production ingestion and reconciliation must never resurrect retired URLs."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core.retired_article_urls import (
    has_retired_table, is_retired, url_sha256, verify_no_active_retired_urls,
)
from migrations.versions import m0008_retired_article_urls as migration
from storage import db
from tests.test_reconcile import (
    ReconcileCase, migrate, add_run, add_article, query, rdb,
)


def retire(con, url, old_id=23):
    con.execute(
        "INSERT INTO retired_article_urls "
        "(url_sha256, original_article_id, source_slug, retired_at, selection_sha256) "
        "VALUES (?, ?, 'pla_daily', '2026-10-15', ?)",
        (url_sha256(url), old_id, "a" * 64),
    )


class TestRetiredUrlIngestion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "live-copy.db"
        self.retired = "https://www.81.cn/china/old.html"
        self.allowed = "https://www.81.cn/china/new.html"
        con = sqlite3.connect(str(self.path))
        con.executescript("""
            CREATE TABLE sources(id INTEGER PRIMARY KEY, slug TEXT UNIQUE);
            INSERT INTO sources(id, slug) VALUES(1, 'pla_daily');
            CREATE TABLE articles(
                id INTEGER PRIMARY KEY,
                url TEXT NOT NULL UNIQUE,
                content_hash TEXT, source_id INTEGER,
                scrape_run_id INTEGER, title_original TEXT, text_original TEXT,
                published_date TEXT, relevance_score REAL,
                relevance_reasoning TEXT, passed_relevance INTEGER);
        """)
        self.assertFalse(migration.is_already_applied(con))
        migration.up(con)
        self.assertTrue(migration.is_already_applied(con))
        retire(con, self.retired)
        con.commit()
        con.close()
        self.binding = patch.object(db, "DB_PATH", self.path)
        self.binding.start()

    def tearDown(self):
        self.binding.stop()
        self.tmp.cleanup()

    def article(self, url):
        return dict(url=url, source_slug="pla_daily",
                    content_hash="test-content-hash", title_original="原标题",
                    text_original="正文", published_date="2026-10-15")

    def counts(self):
        with sqlite3.connect(str(self.path)) as con:
            return con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    def test_exact_digest_and_migration_are_deterministic(self):
        self.assertNotEqual(url_sha256(self.retired), url_sha256(self.retired.upper()))
        with sqlite3.connect(str(self.path)) as con:
            self.assertTrue(has_retired_table(con))
            self.assertTrue(is_retired(con, self.retired))
            self.assertFalse(is_retired(con, self.allowed))
            self.assertEqual(verify_no_active_retired_urls(con), 1)

    def test_early_dedup_treats_retired_url_as_existing(self):
        self.assertTrue(db.url_exists(self.retired))
        self.assertFalse(db.url_exists(self.allowed))

    def test_single_insert_skips_retired_and_accepts_new(self):
        self.assertIsNone(db.insert_article(self.article(self.retired), 1))
        self.assertEqual(self.counts(), 0)
        # The first new article must NOT reuse ID 1, and must be above the
        # retired ID 23 even if no currently active article has a higher ID.
        self.assertEqual(db.insert_article(self.article(self.allowed), 1), 24)
        self.assertEqual(self.counts(), 1)

    def test_atomic_batch_skips_retired_both_accepted_and_rejected(self):
        new = self.article(self.allowed)
        inserted = db.insert_articles_atomic(
            [self.article(self.retired), new],
            [self.article(self.retired)], 5)
        self.assertEqual(len(inserted), 1)
        self.assertEqual(inserted[0][1]["url"], self.allowed)
        self.assertEqual(inserted[0][0], 24)
        self.assertEqual(self.counts(), 1)
        with sqlite3.connect(str(self.path)) as con:
            self.assertEqual(verify_no_active_retired_urls(con), 1)

    def test_sqlite_trigger_refuses_old_id_even_for_different_new_url(self):
        with sqlite3.connect(str(self.path)) as con:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "retired article ID"):
                con.execute(
                    "INSERT INTO articles(id, url, source_id) VALUES (23, ?, 1)",
                    (self.allowed,))
            self.assertEqual(verify_no_active_retired_urls(con), 1)

    def test_implicit_sqlite_rowid_cannot_reuse_retired_published_id(self):
        # Without an AFTER INSERT trigger SQLite allocates MAX(active ID)+1
        # only after BEFORE INSERT triggers have evaluated NEW.id. Keep 22
        # active and 23 retired: implicit allocation must abort at 23.
        with sqlite3.connect(str(self.path)) as con:
            con.execute(
                "INSERT INTO articles(id,url,source_id) VALUES (22, ?, 1)",
                ("https://www.81.cn/china/unrelated.html",))
            with self.assertRaisesRegex(sqlite3.IntegrityError, "retired article ID"):
                con.execute(
                    "INSERT INTO articles(url,source_id) VALUES (?, 1)",
                    ("https://www.81.cn/china/fresh-implicit.html",))
            self.assertEqual(verify_no_active_retired_urls(con), 1)

    def test_active_and_retired_id_overlap_is_a_verification_error(self):
        # Do not rely solely on the URL hash: a writer could otherwise
        # produce a different article at a once-published numeric route.
        with sqlite3.connect(str(self.path)) as con:
            con.execute("DROP TRIGGER guard_retired_article_id_reuse")
            con.execute(
                "INSERT INTO articles(id, url, source_id) VALUES (23, ?, 1)",
                (self.allowed,))
            # Simulate a malformed historical copy with an old row already
            # present: restoring the enforcement trigger is not enough to
            # retroactively repair an illegal reused numeric identity.
            con.execute(migration.TRIGGER_DDL)
            with self.assertRaisesRegex(ValueError, "article ID reused"):
                verify_no_active_retired_urls(con)

    def test_corrupted_active_row_is_fatal_not_silently_allowed(self):
        with sqlite3.connect(str(self.path)) as con:
            con.execute(
                "INSERT INTO articles(url, source_id) VALUES (?, 1)",
                (self.retired,))
            with self.assertRaisesRegex(ValueError, "retired URL found"):
                verify_no_active_retired_urls(con)

    def test_missing_sqlite_id_guard_fails_database_validation(self):
        with sqlite3.connect(str(self.path)) as con:
            con.execute("DROP TRIGGER guard_retired_article_id_reuse")
            with self.assertRaisesRegex(ValueError, "protection trigger missing"):
                verify_no_active_retired_urls(con)

    def test_pre_migration_legacy_fixture_does_not_claim_retirements(self):
        with sqlite3.connect(":memory:") as con:
            self.assertFalse(is_retired(con, self.retired))
            self.assertFalse(has_retired_table(con))


class TestRetiredUrlReconciliation(ReconcileCase):
    def test_local_stale_article_not_resurrected(self):
        migrate(self.origin)
        old = "http://www.81.cn/x/retired-original.html"
        con = sqlite3.connect(str(self.origin))
        try:
            retire(con, old, 4001)
            con.commit()
        finally:
            # sqlite3's context manager commits but DOES NOT close its WAL
            # connection. Reconcile reads a copy of the committed DB file;
            # keeping the writing connection open would leave this fixture's
            # tombstone in a journal sidecar outside that exact-file copy.
            con.close()
        add_run(self.local, 11)
        add_article(self.local, 4001, 11, "retired-original")
        out, report, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        self.assertEqual(report["articles_inserted"], 0)
        self.assertEqual(report["retired_url_reinsertions_skipped"], 1)
        self.assertEqual(query(out, "SELECT id FROM articles WHERE url=?", (old,)), [])
        self.assertEqual(query(out, "SELECT COUNT(*) FROM retired_article_urls"),
                         [(1,)])

    def test_reconciled_new_article_uses_id_above_retired_high_water(self):
        migrate(self.origin)
        con = sqlite3.connect(str(self.origin))
        try:
            retire(con, "http://www.81.cn/x/old-retired-high.html", 9200)
            con.commit()
        finally:
            con.close()
        add_run(self.local, 11)
        add_article(self.local, 4001, 11, "fresh-source")
        out, report, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        self.assertEqual(report["articles_inserted"], 1)
        self.assertEqual(query(out,
            "SELECT id FROM articles WHERE url=?",
            ("http://www.81.cn/x/fresh-source.html",)), [(9201,)])

    def test_independent_local_retirement_cannot_be_silently_dropped(self):
        migrate(self.origin)
        migrate(self.local)
        con = sqlite3.connect(str(self.local))
        try:
            retire(con, "http://www.81.cn/x/local-retired.html", 4311)
            con.commit()
        finally:
            con.close()
        with self.assertRaisesRegex(SystemExit, "retirement ledger"):
            self.run_reconcile()


if __name__ == "__main__":
    unittest.main()
