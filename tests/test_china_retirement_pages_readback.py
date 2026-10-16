"""Byte-for-byte Pages readback proof and fail-closed negative tests."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.retired_article_urls import url_sha256
from scripts.verify_china_retirement_pages_readback import verify


class PagesReadbackTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.expected, self.pages = base / "output", base / "published"
        self.expected.mkdir()
        self.pages.mkdir()
        self.db = base / "reduced.db"
        self.write("corpus-index.json", json.dumps({
            "records": [[1, "2026-10-15", 0, 0, "Title", "Original"]],
            "trail_ids": [1],
        }))
        self.write("record/1.html", "<h1>Official source</h1>")
        self.write("data/articles.json", "[]")
        (self.pages / "CNAME").write_text("indopacificrecord.org\n")
        (self.pages / ".nojekyll").write_text("")
        with sqlite3.connect(self.db) as conn:
            conn.executescript("""
              CREATE TABLE articles(id INTEGER PRIMARY KEY, url TEXT NOT NULL);
              CREATE TABLE retired_article_urls(
                url_sha256 TEXT PRIMARY KEY,
                original_article_id INTEGER NOT NULL UNIQUE
              );
              CREATE TRIGGER guard_retired_article_id_reuse
              AFTER INSERT ON articles WHEN EXISTS (
                SELECT 1 FROM retired_article_urls
                 WHERE original_article_id=NEW.id)
              BEGIN SELECT RAISE(ABORT, 'retired'); END;
            """)
            conn.execute("INSERT INTO articles VALUES (1,'https://official.example/1')")
            conn.executemany("INSERT INTO retired_article_urls VALUES (?,?)",
                             [(url_sha256("https://official.example/%d" % n), n)
                              for n in (2, 3)])

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, name, value):
        for root in (self.expected, self.pages):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")

    def check(self):
        return verify(self.expected, self.pages, self.db, expected_tombstones=2)

    def test_exact_readback_succeeds(self):
        result = self.check()
        self.assertEqual(result["active_record_count"], 1)
        self.assertEqual(result["retired_url_id_tombstones"], 2)
        self.assertEqual(result["published_files_verified"], 3)

    def test_deployed_record_content_drift_rejected(self):
        (self.pages / "record/1.html").write_text("stale text")
        with self.assertRaisesRegex(ValueError, "byte mismatch"):
            self.check()

    def test_missing_page_rejected(self):
        (self.pages / "record/1.html").unlink()
        with self.assertRaisesRegex(ValueError, "file-list drift"):
            self.check()

    def test_unexpected_retired_record_route_rejected(self):
        (self.pages / "record/900.html").write_text("stale record")
        with self.assertRaisesRegex(ValueError, "file-list drift"):
            self.check()

    def test_missing_hosting_domain_rejected(self):
        (self.pages / "CNAME").write_text("wrong.example")
        with self.assertRaisesRegex(ValueError, "custom domain"):
            self.check()

    def test_database_record_identity_drift_rejected(self):
        with sqlite3.connect(self.db) as con:
            con.execute("INSERT INTO articles VALUES (4,'https://official.example/4')")
        with self.assertRaisesRegex(ValueError, "production SQLite"):
            self.check()

    def test_missing_retirement_tombstone_rejected(self):
        with sqlite3.connect(self.db) as con:
            con.execute("DELETE FROM retired_article_urls WHERE original_article_id=3")
        with self.assertRaisesRegex(ValueError, "ledger count"):
            self.check()


if __name__ == "__main__":
    unittest.main()
