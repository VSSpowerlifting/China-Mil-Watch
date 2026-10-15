"""Real SQLite transaction tests: physical retirement + identity ledger."""
from hashlib import sha256
import sqlite3
import tempfile
from pathlib import Path
import unittest

from migrations.versions import m0008_retired_article_urls
from scripts.stage_china_retirement_atomic import (stage_atomic_retirement,
                                                   rehearse_on_new_scratch_copy)
from core.retired_article_urls import url_sha256, verify_no_active_retired_urls


def reviewed_selection(retired=(1, 4), kept=(2, 3, 5, 6)):
    retired = tuple(retired)
    kept = tuple(kept)
    return {
        "retired_ids": retired,
        "kept_ids": kept,
        "total_before": len(retired) + len(kept),
        "total_after": len(kept),
        "retirement_id_sha256": sha256(
            ",".join(map(str, sorted(retired))).encode()).hexdigest(),
    }


class TestAtomicRetirement(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "scratch-only.db"
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
            CREATE TABLE sources(id INTEGER PRIMARY KEY, slug TEXT UNIQUE);
            INSERT INTO sources VALUES (1, 'pla_daily');
            INSERT INTO sources VALUES (2, 'sg_mindef_releases');
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE,
                source_id INTEGER NOT NULL REFERENCES sources(id));
            CREATE TABLE article_categories (
                article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
                category_id INTEGER);
        """)
        m0008_retired_article_urls.up(self.conn)
        for ident in range(1, 7):
            slug_id = 2 if ident == 3 else 1
            self.conn.execute(
                "INSERT INTO articles(id,url,source_id) VALUES (?,?,?)",
                (ident, "https://original.example/%s" % ident, slug_id))
            self.conn.execute(
                "INSERT INTO article_categories(article_id,category_id) VALUES (?,1)",
                (ident,))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def state(self):
        return {
            "articles": list(self.conn.execute(
                "SELECT id,url FROM articles ORDER BY id")),
            "categories": list(self.conn.execute(
                "SELECT article_id FROM article_categories ORDER BY article_id")),
            "ledger": list(self.conn.execute(
                "SELECT original_article_id,url_sha256 FROM retired_article_urls "
                "ORDER BY original_article_id")),
        }

    def stage(self, data=None):
        return stage_atomic_retirement(
            self.conn, data or reviewed_selection(), "2026-10-15",
            minimum_retire=2, maximum_retire=3)

    def test_delete_and_tombstone_are_same_committed_transaction(self):
        result = self.stage()
        self.assertEqual(result["retired"], 2)
        self.assertEqual(result["retained"], 4)
        self.assertEqual(result["ledger_added"], 2)
        self.assertEqual([r[0] for r in self.state()["articles"]], [2, 3, 5, 6])
        self.assertEqual([r[0] for r in self.state()["categories"]], [2, 3, 5, 6])
        self.assertEqual(self.state()["ledger"], [
            (1, url_sha256("https://original.example/1")),
            (4, url_sha256("https://original.example/4")),
        ])
        self.assertEqual(verify_no_active_retired_urls(self.conn), 2)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO articles(id,url,source_id) VALUES (1,'fresh',1)")
        self.conn.rollback()
        with sqlite3.connect(str(self.path)) as again:
            self.assertEqual(
                again.execute("SELECT COUNT(*) FROM retired_article_urls").fetchone()[0],
                2)

    def test_failure_rolls_back_both_deletion_and_tombstones(self):
        self.conn.execute("""
            CREATE TRIGGER fail_retirement BEFORE DELETE ON articles
            WHEN OLD.id=4
            BEGIN SELECT RAISE(ABORT, 'blocked deletion'); END
        """)
        before = self.state()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "blocked deletion"):
            self.stage()
        self.assertEqual(self.state(), before)
        self.assertFalse(self.conn.in_transaction)

    def test_stale_source_database_is_rejected_without_mutation(self):
        self.conn.execute(
            "INSERT INTO articles(id,url,source_id) VALUES (7,'other',1)")
        self.conn.commit()
        before = self.state()
        with self.assertRaisesRegex(ValueError, "database advanced"):
            self.stage()
        self.assertEqual(self.state(), before)

    def test_refuses_non_china_source_even_if_owner_range_fits(self):
        self.conn.execute("UPDATE articles SET source_id=2 WHERE id=4")
        self.conn.commit()
        before = self.state()
        with self.assertRaisesRegex(ValueError, "non-China"):
            self.stage()
        self.assertEqual(self.state(), before)

    def test_refuses_modified_retirement_hash(self):
        selected = dict(reviewed_selection(),
                        retirement_id_sha256="a" * 64)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.stage(selected)
        self.assertEqual(len(self.state()["ledger"]), 0)

    def test_refuses_overlap_with_citation_held_id(self):
        selected = dict(reviewed_selection(), kept_ids=(1, 2, 3, 5, 6))
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.stage(selected)

    def test_refuses_unapproved_retirement_volume(self):
        with self.assertRaisesRegex(ValueError, "outside approved"):
            stage_atomic_retirement(self.conn, reviewed_selection(), "2026-10-15")
        self.assertEqual(len(self.state()["ledger"]), 0)

    def test_requires_foreign_key_validation(self):
        self.conn.execute("PRAGMA foreign_keys=OFF")
        with self.assertRaisesRegex(ValueError, "foreign keys"):
            self.stage()
        self.conn.execute("PRAGMA foreign_keys=ON")

    def test_rejects_unreviewed_dependency_that_would_not_cascade(self):
        self.conn.execute("""
            CREATE TABLE article_pins (
                article_id INTEGER REFERENCES articles(id) ON DELETE RESTRICT
            )
        """)
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, "unsafe foreign-key"):
            self.stage()

    def test_new_scratch_copy_retires_without_changing_original_bytes(self):
        original_bytes = self.path.read_bytes()
        scratch = Path(self.temp.name) / "separate-reduced.db"
        result = rehearse_on_new_scratch_copy(
            self.path, scratch, reviewed_selection(), "2026-10-15",
            minimum_retire=2, maximum_retire=3)
        self.assertEqual(result["retired"], 2)
        self.assertTrue(result["original_db_unchanged"])
        self.assertEqual(self.path.read_bytes(), original_bytes)
        with sqlite3.connect(str(scratch)) as reduced:
            self.assertEqual(
                [row[0] for row in reduced.execute(
                    "SELECT id FROM articles ORDER BY id")],
                [2, 3, 5, 6])
            self.assertEqual(verify_no_active_retired_urls(reduced), 2)
        self.assertEqual([r[0] for r in self.state()["articles"]],
                         [1, 2, 3, 4, 5, 6])

    def test_new_scratch_copy_rolls_back_failed_delete_and_removes_file(self):
        self.conn.execute("""
            CREATE TRIGGER block_copy_retirement BEFORE DELETE ON articles
            WHEN OLD.id=4
            BEGIN SELECT RAISE(ABORT, 'never partial'); END
        """)
        self.conn.commit()
        original_bytes = self.path.read_bytes()
        scratch = Path(self.temp.name) / "failed-copy.db"
        with self.assertRaisesRegex(sqlite3.IntegrityError, "never partial"):
            rehearse_on_new_scratch_copy(
                self.path, scratch, reviewed_selection(), "2026-10-15",
                minimum_retire=2, maximum_retire=3)
        self.assertFalse(scratch.exists())
        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(len(self.state()["ledger"]), 0)

    def test_scratch_copy_refuses_occupied_destination(self):
        with self.assertRaisesRegex(ValueError, "new absolute"):
            rehearse_on_new_scratch_copy(
                self.path, self.path, reviewed_selection(), "2026-10-15",
                minimum_retire=2, maximum_retire=3)

    def test_second_run_does_not_duplicate_retirement(self):
        self.stage()
        with self.assertRaisesRegex(ValueError, "database advanced"):
            self.stage()
        self.assertEqual(verify_no_active_retired_urls(self.conn), 2)


if __name__ == "__main__":
    unittest.main()
