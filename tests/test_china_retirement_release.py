"""Synthetic complete-corpus boundary tests for the manual China cutover."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.retired_article_urls import url_sha256
from scripts.verify_china_retirement_render import validate


class ChinaRetirementReleaseVerifierTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.before, self.after = root / "before", root / "after"
        self.before.mkdir()
        self.after.mkdir()
        self.db = root / "retired.db"
        self.plan = root / "plan.json"
        self.active = set(range(1, 874))
        self.retired = set(range(874, 5274))
        self.trails = list(range(1, 183))
        self.focus = list(range(1, 687))
        self.analyzed = set(range(1, 634))
        rows = lambda ids: [
            [ident, "2026-10-15", 0, 1 if ident in self.analyzed else 0,
             "title", "original"] for ident in sorted(ids)]
        headers = {
            "states": [{"code": "collected"}, {"code": "analyzed"}],
            "trail_ids": self.trails,
            "focus_ids": self.focus,
        }
        (self.before / "corpus-index.json").write_text(
            json.dumps(dict(headers, records=rows(self.active | self.retired))))
        (self.after / "corpus-index.json").write_text(
            json.dumps(dict(headers, records=rows(self.active))))
        digest = sha256(",".join(map(str, sorted(self.retired))).encode()).hexdigest()
        self.plan.write_text(json.dumps({
            "retirement_id_sha256": digest,
            "china_to_retire": 4400,
            "total_after": 873,
        }))
        for folder, ids in (("record", self.active), ("article", self.analyzed)):
            d = self.after / folder
            d.mkdir()
            for ident in ids:
                (d / ("%d.html" % ident)).write_text("record")
        (self.after / "data").mkdir()
        (self.after / "data" / "articles.json").write_text(
            json.dumps([{"id": i} for i in sorted(self.analyzed)]))
        (self.after / "sitemap.xml").write_text(
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            '<url><loc>https://indopacificrecord.org/record/1.html</loc></url>'
            '</urlset>')
        with sqlite3.connect(self.db) as con:
            con.executescript("""
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
            con.executemany("INSERT INTO articles VALUES (?, ?)", [
                (ident, "https://example.org/active/%d" % ident)
                for ident in sorted(self.active)
            ])
            con.executemany("INSERT INTO retired_article_urls VALUES (?, ?)", [
                (url_sha256("https://example.org/retired/%d" % ident), ident)
                for ident in sorted(self.retired)
            ])

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return validate(self.before, self.after, self.db, self.plan)

    def test_complete_scratch_release_exact_identity_and_routes(self):
        r = self.check()
        self.assertEqual(r["before"], 5273)
        self.assertEqual(r["retired"], 4400)
        self.assertEqual(r["retained"], 873)
        self.assertEqual(r["protected_trails"], 182)
        self.assertEqual(r["legacy_export"], 633)
        self.assertEqual(r["url_id_tombstones"], 4400)

    def test_missing_cited_record_is_fatal(self):
        (self.after / "record" / "1.html").unlink()
        with self.assertRaisesRegex(ValueError, "record pages"):
            self.check()

    def test_retired_old_record_or_legacy_redirect_is_fatal(self):
        (self.after / "article" / "900.html").write_text("old redirect")
        with self.assertRaisesRegex(ValueError, "article pages"):
            self.check()

    def test_retired_record_in_legacy_export_is_fatal(self):
        export = self.after / "data" / "articles.json"
        rows = json.loads(export.read_text())
        rows.append({"id": 900})
        export.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError, "legacy analyzed export"):
            self.check()

    def test_retired_record_in_sitemap_is_fatal(self):
        (self.after / "sitemap.xml").write_text(
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            '<url><loc>https://indopacificrecord.org/record/900.html</loc></url>'
            '</urlset>')
        with self.assertRaisesRegex(ValueError, "sitemap"):
            self.check()

    def test_retired_identity_manifest_mismatch_is_fatal(self):
        plan = json.loads(self.plan.read_text())
        plan["retirement_id_sha256"] = "f" * 64
        self.plan.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "retirement identity SHA"):
            self.check()

    def test_missing_tombstone_is_fatal(self):
        with sqlite3.connect(self.db) as con:
            con.execute("DELETE FROM retired_article_urls WHERE original_article_id=900")
        with self.assertRaisesRegex(ValueError, "tombstones"):
            self.check()


if __name__ == "__main__":
    unittest.main()
