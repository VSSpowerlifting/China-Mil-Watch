"""Two stored SQLite snapshots: exact identity accounting, never model inference."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import audit_stored_queue_transitions as diff
from scripts import audit_analysis_queue_by_source as queue

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


class StoredTransitions(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-stored-transition-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.before = self.root / "older.db"
        self.after = self.root / "newer.db"
        with sqlite3.connect(self.before) as con:
            con.executescript("""
                CREATE TABLE sources (
                    id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT
                );
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL,
                    source_id INTEGER,
                    passed_relevance INTEGER,
                    analyzed_at TEXT,
                    processing_state TEXT,
                    scraped_at TEXT
                );
            """)
            con.executemany("INSERT INTO sources VALUES (?,?,?)", [
                (1, "mod_china", "china"), (2, "sg_mindef", "singapore")])
        shutil.copyfile(self.before, self.after)

    def insert(self, which, ident, *, source=1, passed=None,
               analyzed=None, state=None, scraped="2026-10-08 13:00:00",
               url=None):
        with sqlite3.connect(which) as con:
            con.execute(
                "INSERT INTO articles VALUES (?,?,?,?,?,?,?)",
                (ident, url or "https://example.org/official/%d" % ident,
                 source, passed, analyzed, state, scraped))

    def edit(self, ident, **changes):
        with sqlite3.connect(self.after) as con:
            for field, value in changes.items():
                if field not in ("source_id", "passed_relevance", "analyzed_at",
                                 "processing_state", "scraped_at", "url"):
                    raise ValueError(field)
                con.execute("UPDATE articles SET %s=? WHERE id=?" % field,
                            (value, ident))

    def compare(self):
        return diff.snapshot_pair(self.before, self.after, at=NOW)

    def test_distinct_ids_and_state_transitions_reconcile_exactly(self):
        for i, opts in (
            (1, {}), (2, {"passed": 1}), (3, {}),
            (4, {"source": 2}), (5, {})):
            self.insert(self.before, i, **opts)
        shutil.copyfile(self.before, self.after)
        self.edit(1, passed_relevance=1)
        self.edit(2, analyzed_at="2026-10-09T08:00:00Z")
        self.edit(3, passed_relevance=0)
        self.edit(4, source_id=1)
        with sqlite3.connect(self.after) as c:
            c.execute("DELETE FROM articles WHERE id=5")
        self.insert(self.after, 6)
        r = self.compare()
        self.assertEqual(r["before"]["daily_eligible"], 4)
        self.assertEqual(r["after"]["daily_eligible"], 3)
        self.assertEqual(r["identity_comparison"]["added_ids"], 1)
        self.assertEqual(r["identity_comparison"]["removed_ids"], 1)
        self.assertEqual(r["identity_comparison"]["shared_ids"], 4)
        self.assertEqual(r["identity_comparison"]["changed_queue_bucket"], 4)
        self.assertEqual(r["identity_comparison"]["records_with_source_reassignment"], 1)
        self.assertEqual(r["daily_queue_change"], {
            "net_stored_change": -1,
            "new_ids_in_daily": 1, "removed_ids_previously_daily": 1,
            "shared_ids_entered_daily": 1,
            "shared_ids_left_daily": 2,
        })
        self.assertEqual(r["shared_daily_exit_destinations"],
                         {"completed_analysis": 1, "relevance_rejected": 1})
        self.assertFalse(r["successful_analysis_jobs_inferred"])
        self.assertFalse(r["historical_model_execution_authenticated"])
        self.assertFalse(r["snapshot_ancestry_authenticated"])

    def test_shared_date_cutoff_does_not_invent_age_transition(self):
        self.insert(self.before, 1, scraped="2026-09-24")
        shutil.copyfile(self.before, self.after)
        self.insert(self.after, 2, scraped="2026-10-08")
        r = self.compare()
        self.assertEqual(r["same_cutoff_for_both"], "2026-09-25")
        self.assertEqual(r["identity_comparison"]["changed_queue_bucket"], 0)
        self.assertEqual(r["added_record_buckets"], {"daily_unscored_live": 1})
        self.assertEqual(r["before"]["daily_eligible"], 1)
        self.assertEqual(r["after"]["daily_eligible"], 2)

    def test_paused_to_retriable_is_metadata_not_model_certification(self):
        self.insert(self.before, 1, state="paused")
        shutil.copyfile(self.before, self.after)
        self.edit(1, processing_state="retriable")
        r = self.compare()
        self.assertEqual(r["daily_queue_change"]["shared_ids_entered_daily"], 1)
        self.assertFalse(r["model_spend_authorized"])
        self.assertFalse(r["collection_executed_authenticated"])

    def test_same_id_different_canonical_url_refuses_diff(self):
        self.insert(self.before, 1)
        shutil.copyfile(self.before, self.after)
        self.edit(1, url="https://example.org/an-unrelated-document")
        with self.assertRaisesRegex(queue.QueueAuditError, "conflicting canonical URL"):
            self.compare()

    def test_distinct_paths_with_identical_bytes_are_not_history(self):
        self.insert(self.before, 1)
        shutil.copyfile(self.before, self.after)
        with self.assertRaisesRegex(queue.QueueAuditError, "identical bytes"):
            self.compare()

    def test_same_path_refused_without_creating_files(self):
        with self.assertRaisesRegex(queue.QueueAuditError, "distinct"):
            diff.snapshot_pair(self.before, self.before, at=NOW)

    def test_missing_input_does_not_create_a_new_database(self):
        missing = self.root / "not-present.db"
        with self.assertRaisesRegex(queue.QueueAuditError, "must exist"):
            diff.snapshot_pair(missing, self.after, at=NOW)
        self.assertFalse(missing.exists())

    def test_malformed_legacy_schema_refused(self):
        with sqlite3.connect(self.after) as con:
            con.execute("DROP TABLE articles")
            con.execute("CREATE TABLE articles (id INTEGER, url TEXT)")
        with self.assertRaisesRegex(queue.QueueAuditError, "requires current articles"):
            self.compare()

    def test_original_db_bytes_and_sidecars_unchanged(self):
        self.insert(self.before, 1)
        shutil.copyfile(self.before, self.after)
        self.insert(self.after, 2)
        prior = [hashlib.sha256(x.read_bytes()).hexdigest()
                 for x in (self.before, self.after)]
        r = self.compare()
        after = [hashlib.sha256(x.read_bytes()).hexdigest()
                 for x in (self.before, self.after)]
        self.assertEqual(prior, after)
        self.assertEqual(r["before"]["input_sha256"]["db"], prior[0])
        self.assertEqual(r["after"]["input_sha256"]["db"], prior[1])
        for p in (self.before, self.after):
            self.assertFalse(Path(str(p) + "-wal").exists())
            self.assertFalse(Path(str(p) + "-shm").exists())

    def test_concurrent_change_to_older_input_fails_closed(self):
        self.insert(self.before, 1)
        shutil.copyfile(self.before, self.after)
        self.insert(self.after, 2)
        original = diff.queue._snapshot_file_hashes
        calls = [0]
        def changed(path):
            calls[0] += 1
            if calls[0] == 3:
                self.insert(self.before, 3)
            return original(path)
        with patch.object(diff.queue, "_snapshot_file_hashes", side_effect=changed):
            with self.assertRaisesRegex(queue.QueueAuditError, "changed"):
                self.compare()

    def test_cli_requires_two_dbs_and_does_not_show_article_urls(self):
        self.insert(self.before, 1, url="https://example.org/private/test?id=SECRET")
        shutil.copyfile(self.before, self.after)
        self.insert(self.after, 2)
        proc = subprocess.run([
            sys.executable, str(Path(diff.__file__).resolve()),
            "--before-db", str(self.before), "--after-db", str(self.after),
            "--at-utc", "2026-10-09T12:00:00Z"
        ], text=True, capture_output=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        r = json.loads(proc.stdout)
        self.assertEqual(r["schema"], diff.SCHEMA)
        self.assertEqual(r["daily_queue_change"]["net_stored_change"], 1)
        self.assertNotIn("SECRET", proc.stdout)
        self.assertNotIn("https://example.org", proc.stdout)
        self.assertFalse(r["cost_or_budget_established"])
        self.assertEqual(r["model_calls"], 0)
        self.assertEqual(r["writes"], 0)

    def test_naive_timestamp_refused_before_mutation(self):
        self.insert(self.before, 1)
        shutil.copyfile(self.before, self.after)
        self.insert(self.after, 2)
        with self.assertRaisesRegex(queue.QueueAuditError, "timezone-aware"):
            diff.snapshot_pair(self.before, self.after, at=datetime(2026, 10, 9))


if __name__ == "__main__":
    unittest.main()
