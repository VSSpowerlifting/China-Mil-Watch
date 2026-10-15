"""No production mutation; true scratch SQLite deletion and citation custody."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from migrations.versions import m0008_retired_article_urls
from scripts.plan_china_active_retirement import (plan, scratch_retirement,
                                                    publication_record_dependencies)


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
    return plan(index, expected_china_focus=2, minimum_retire=1,
                maximum_retire=2, preferred_retire=2)


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

    def test_safe_context_buffer_enforces_exact_retirement_range(self):
        obj = fixture()
        for ident in (8, 9, 10, 11):
            obj["records"].append(
                [ident, "2026-10-15", 0, 0, "Unreviewed context", "新消息"])
        obj["snapshot"]["records"] = len(obj["records"])
        result = sample_plan(obj)
        self.assertEqual(result["china_to_retire"], 2)
        self.assertEqual(result["supplemental_automated_context"], 4)
        self.assertTrue({3, 6, 7}.issubset(set(result["kept_ids"])))
        self.assertTrue(set(result["retired_ids"]).isdisjoint({3, 6, 7}))

    def test_insufficient_actual_retirements_fail_owner_range(self):
        obj = fixture()
        obj["focus_ids"] = [1, 2, 4, 5, 6, 7]
        with self.assertRaisesRegex(ValueError, "owner-approved"):
            plan(obj, expected_china_focus=4, minimum_retire=2,
                 maximum_retire=3, preferred_retire=2)

    def test_canonical_brief_and_timeline_references_are_additional_protection(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "briefs").mkdir()
            (root / "timelines").mkdir()
            (root / "briefs" / "approved.json").write_text(json.dumps({
                "source_trail": [{"record_id": 4}]
            }))
            (root / "timelines" / "private-draft.json").write_text(json.dumps({
                "entries": [{"evidence": [{"record_id": 5}]}]
            }))
            bound, totals = publication_record_dependencies(root)
            self.assertEqual(bound, {4, 5})
            self.assertEqual(totals, {"briefs": 1, "timelines": 1})
            result = plan(fixture(), expected_china_focus=2,
                          minimum_retire=0, maximum_retire=2,
                          preferred_retire=2, publication_ids=bound)
            self.assertTrue(bound <= set(result["kept_ids"]))
            self.assertEqual(result["bound_brief_and_timeline_ids"], 2)
            self.assertEqual(result["china_to_retire"], 0)

    def test_invalid_editorial_reference_refuses_retirement(self):
        with self.assertRaisesRegex(ValueError, "missing corpus ID"):
            plan(fixture(), expected_china_focus=2,
                 minimum_retire=1, maximum_retire=2,
                 preferred_retire=2, publication_ids={99999})

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
            CREATE TABLE sources(id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE);
            INSERT INTO sources VALUES (1, 'pla_daily');
            INSERT INTO sources VALUES (2, 'sg_mindef_releases');
            CREATE TABLE articles(
                id INTEGER PRIMARY KEY,
                url TEXT NOT NULL UNIQUE,
                source_id INTEGER NOT NULL REFERENCES sources(id));
            CREATE TABLE article_categories (
                article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
                category_id INTEGER NOT NULL);
        """)
        m0008_retired_article_urls.up(con)
        con.executemany("INSERT INTO articles(id,url,source_id) VALUES(?,?,?)",
                        [(i, "source-%s" % i, 1 if i <= 5 else 2)
                         for i in range(1, 8)])
        con.executemany("INSERT INTO article_categories(article_id,category_id) VALUES(?,1)",
                        [(i,) for i in range(1, 8)])
        con.commit()
        con.close()
        self.data = sample_plan(fixture())

    def tearDown(self):
        self.temp.cleanup()

    def stage(self, *args, **kwargs):
        # Unit fixture has 2 China retirements; production defaults remain
        # strictly 4300–4500 in both planner and atomic executor.
        kwargs.setdefault("minimum_retire", 1)
        kwargs.setdefault("maximum_retire", 2)
        return scratch_retirement(*args, **kwargs)

    def test_scratch_deletion_really_removes_rows_without_touching_input(self):
        original = self.original.read_bytes()
        scratch = self.root / "retired.db"
        result = self.stage(self.original, scratch, self.data)
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
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM retired_article_urls").fetchone()[0], 2)
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0],
                             "ok")

    def test_private_url_hash_receipt_records_every_retirement(self):
        from hashlib import sha256
        dest = self.root / "reduced.db"
        tombstones = self.root / "private-tombstones.json"
        result = self.stage(
            self.original, dest, self.data, tombstone_path=tombstones)
        self.assertEqual(result["url_tombstone_count"], 2)
        self.assertEqual(result["private_tombstone_receipt"], str(tombstones))
        payload = json.loads(tombstones.read_text())
        self.assertEqual(payload["retired_count"], 2)
        self.assertEqual(payload["retired_url_sha256"], sorted(
            sha256(("source-%s" % i).encode()).hexdigest() for i in (4, 5)))
        self.assertNotIn("source-4", tombstones.read_text())
        self.assertNotIn("source-5", tombstones.read_text())
        self.assertEqual(tombstones.stat().st_mode & 0o777, 0o600)

    def test_refuses_overwriting_retirement_manifest(self):
        receipt = self.root / "exists.json"
        receipt.write_text("protected")
        with self.assertRaisesRegex(ValueError, "tombstone path"):
            self.stage(self.original, self.root / "new.db", self.data,
                               tombstone_path=receipt)
        self.assertEqual(receipt.read_text(), "protected")
        self.assertFalse((self.root / "new.db").exists())

    def test_refuses_overwriting_existing_database(self):
        with self.assertRaisesRegex(ValueError, "new absolute"):
            self.stage(self.original, self.original, self.data)

    def test_refuses_stale_index_without_creating_scratch(self):
        from hashlib import sha256
        # Same number of IDs and internally consistent digest, but ID 999
        # was never present in the source; ID 5 would also go unaccounted.
        # This must fail the exact source-identity comparison, not just quota.
        data = dict(self.data, retired_ids=(4, 999),
                    retirement_id_sha256=sha256(b"4,999").hexdigest())
        dest = self.root / "new.db"
        with self.assertRaisesRegex(ValueError, "database identities differ"):
            self.stage(self.original, dest, data)
        self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
