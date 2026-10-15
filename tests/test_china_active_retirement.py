"""No production mutation; true scratch SQLite deletion and citation custody."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.plan_china_active_retirement import plan, scratch_retirement


def fixture():
    return {
        "snapshot": {"date": "2026-10-14", "records": 7},
        "fields": ["id", "date", "source", "state", "title_en", "title_orig"],
        "sources": [{"code": "pla_daily", "desk": {"code": "china"}},
                    {"code": "sg_mindef_releases", "desk": {"code": "singapore"}}],
        "records": [
            [1, "2026-10-14", 0, 0, "China 1", "中文 1"],
            [2, "2026-10-14", 0, 0, "China 2", "中文 2"],
            [3, "2026-10-14", 0, 0, "Cited China", "中文 3"],
            [4, "2026-10-14", 0, 0, "Low priority", "中文 4"],
            [5, "2026-10-14", 0, 0, "Secondary", "中文 5"],
            [6, "2026-10-14", 1, 0, "Singapore 1", "Singapore 1"],
            [7, "2026-10-14", 1, 0, "Singapore 2", "Singapore 2"],
        ],
        "focus_ids": [1, 2, 6, 7],
        "focus_policy": "automated_research_focus_not_human_curated",
        "trail_ids": [3, 6],
    }


def sample_plan(index):
    return plan(index, expected_china_focus=2, minimum_retire=1)


class ChinaRetirementPlanTest(unittest.TestCase):
    def test_exact_retirement_protects_citations_and_other_desks(self):
        before = fixture()
        frozen = copy.deepcopy(before)
        result = sample_plan(before)
        self.assertEqual(before, frozen)
        self.assertEqual(result["china_to_retire"], 2)
        self.assertEqual(result["china_after"], 3)
        self.assertEqual(result["total_after"], 5)
        self.assertEqual(result["retired_ids"], (4, 5))
        self.assertEqual(set(result["kept_ids"]), {1, 2, 3, 6, 7})
        self.assertEqual(result["citation_only_china_retained"], 1)

    def test_refuses_citation_identity_missing_from_corpus(self):
        obj = fixture()
        obj["trail_ids"] = [999]
        with self.assertRaisesRegex(ValueError, "lost source identity"):
            sample_plan(obj)

    def test_refuses_suppressing_other_desk_from_focus(self):
        obj = fixture()
        obj["focus_ids"].remove(7)
        with self.assertRaisesRegex(ValueError, "other desks"):
            sample_plan(obj)

    def test_refuses_undisclosed_algorithm_or_changed_quota(self):
        obj = fixture()
        obj["focus_policy"] = "human_editor_approved"
        with self.assertRaisesRegex(ValueError, "disclosed"):
            sample_plan(obj)
        obj = fixture()
        obj["focus_ids"].remove(2)
        with self.assertRaisesRegex(ValueError, "cohort changed"):
            sample_plan(obj)

    def test_refuses_historical_body_hold_promoted_in_focus(self):
        obj = fixture()
        obj["records"][0][0] = 2265
        obj["focus_ids"][0] = 2265
        with self.assertRaisesRegex(ValueError, "body hold"):
            sample_plan(obj)

    def test_refuses_misclassified_or_duplicate_source_record(self):
        obj = fixture()
        obj["records"][4][0] = 3
        with self.assertRaisesRegex(ValueError, "duplicate"):
            sample_plan(obj)


class ChinaRetirementScratchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="china-cull-tests-")
        self.root = Path(self.temp.name)
        self.original = self.root / "current.db"
        con = sqlite3.connect(str(self.original))
        con.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT UNIQUE);
            CREATE TABLE article_categories (
                article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
                category_id INTEGER NOT NULL);
        """)
        con.executemany("INSERT INTO articles(id,url) VALUES(?,?)",
                        [(i, "source-%s" % i) for i in range(1, 8)])
        con.executemany("INSERT INTO article_categories(article_id,category_id) VALUES(?,1)",
                        [(i,) for i in range(1, 8)])
        con.commit()
        con.close()
        self.data = sample_plan(fixture())

    def tearDown(self):
        self.temp.cleanup()

    def test_scratch_deletion_really_removes_rows_without_touching_input(self):
        original = self.original.read_bytes()
        scratch = self.root / "retired.db"
        result = scratch_retirement(self.original, scratch, self.data)
        self.assertFalse(result["production_db_modified"])
        self.assertEqual(result["retired"], 2)
        self.assertEqual(self.original.read_bytes(), original)
        self.assertFalse((self.root / "current.db-wal").exists())
        self.assertFalse((self.root / "current.db-shm").exists())
        with sqlite3.connect(str(scratch)) as con:
            remaining = {row[0] for row in con.execute("SELECT id FROM articles")}
            attached = {row[0] for row in
                        con.execute("SELECT article_id FROM article_categories")}
            self.assertEqual(remaining, {1, 2, 3, 6, 7})
            self.assertEqual(attached, remaining)
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0],
                             "ok")

    def test_refuses_overwriting_existing_database(self):
        with self.assertRaisesRegex(ValueError, "not exist"):
            scratch_retirement(self.original, self.original, self.data)

    def test_refuses_stale_index_without_creating_scratch(self):
        data = dict(self.data, retired_ids=(4, 5, 999))
        dest = self.root / "new.db"
        with self.assertRaisesRegex(ValueError, "does not match"):
            scratch_retirement(self.original, dest, data)
        self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
