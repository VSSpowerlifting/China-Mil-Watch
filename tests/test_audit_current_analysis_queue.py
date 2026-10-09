"""Offline current-DB analysis queue count; no external calls or writes."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.audit_current_analysis_queue import (
    QueueAuditError, audit, main,
)
from scripts.reconcile_db import read_only


class CurrentAnalysisQueueTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="ipr-queue-audit-")
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        self.db = self.root / "sample.db"
        with sqlite3.connect(self.db) as c:
            c.executescript("""
                CREATE TABLE sources (
                    id INTEGER PRIMARY KEY, slug TEXT UNIQUE, desk_id TEXT);
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY, source_id INTEGER,
                    passed_relevance INTEGER, analyzed_at TEXT,
                    processing_state TEXT);
                INSERT INTO sources VALUES
                    (1, 'china-mod', 'china'),
                    (2, 'sg-mod', 'singapore'),
                    (3, 'legacy-undesignated', NULL);
                INSERT INTO articles VALUES
                    (1, 1, NULL, NULL, NULL),
                    (2, 1, 1, NULL, NULL),
                    (3, 1, 1, NULL, 'paused'),
                    (4, 1, NULL, NULL, 'terminal'),
                    (5, 1, 1, '2026-10-08 12:00:00', NULL),
                    (6, 1, 0, NULL, NULL),
                    (7, 1, 2, NULL, NULL),
                    (8, 1, 1, NULL, 'retriable'),
                    (9, 2, 1, NULL, NULL),
                    (10, 3, NULL, NULL, NULL);
            """)

    def report(self):
        with read_only(self.db) as conn:
            return audit(conn)

    def test_source_attributed_statuses_partition_snapshot_exactly(self):
        r = self.report()
        self.assertEqual(r["schema"], "ipr-current-analysis-queue/1")
        self.assertEqual(r["stored_records"], 10)
        self.assertEqual(r["max_article_id"], 10)
        self.assertEqual(r["automatic_queue_candidates"], 5)
        self.assertEqual(r["held_out_of_automatic_queue"], 2)
        self.assertEqual(r["counts"], {
            "pending_relevance": 2, "pending_analysis": 3,
            "paused_manual_review": 1, "terminal_content": 1,
            "screened_out": 1, "analyzed": 1,
            "inconsistent_state": 1,
        })
        self.assertEqual([s["source_slug"] for s in r["sources"]],
                         ["legacy-undesignated", "china-mod", "sg-mod"])
        self.assertEqual([s["stored_records"] for s in r["sources"]], [1, 8, 1])
        self.assertEqual(r["sources_without_desk_assignment"],
                         ["legacy-undesignated"])
        self.assertFalse(r["analysis_performed"])
        self.assertFalse(r["model_spend_authorized"])
        self.assertFalse(r["publication_authorized"])

    def test_no_url_or_article_body_in_report_and_stable_state_digest(self):
        a = self.report()
        b = self.report()
        self.assertEqual(a["queue_state_digest_sha256"], b["queue_state_digest_sha256"])
        self.assertEqual(len(a["queue_state_digest_sha256"]), 64)
        body = json.dumps(a, ensure_ascii=False)
        self.assertNotIn("article body", body)
        self.assertNotIn("https://", body)
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE articles SET passed_relevance = 1 WHERE id = 1")
        changed = self.report()
        self.assertNotEqual(a["queue_state_digest_sha256"],
                            changed["queue_state_digest_sha256"])

    def test_missing_source_is_refused_not_silently_attributed(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE articles SET source_id = 999 WHERE id = 9")
        with self.assertRaisesRegex(QueueAuditError, "unattributed source"):
            self.report()

    def test_legacy_schema_missing_processing_state_is_refused(self):
        old = self.root / "old.db"
        with sqlite3.connect(old) as c:
            c.executescript("""
                CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY, source_id INTEGER,
                    passed_relevance INTEGER, analyzed_at TEXT);
            """)
        with read_only(old) as c, self.assertRaisesRegex(
                QueueAuditError, "processing_state"):
            audit(c)

    def test_unusual_completed_states_flagged_not_misreported_as_backlog(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE articles SET processing_state = 'paused' WHERE id = 5")
        r = self.report()
        self.assertEqual(r["counts"]["inconsistent_state"], 2)
        self.assertEqual(r["counts"]["analyzed"], 0)
        self.assertEqual(r["automatic_queue_candidates"], 5)

    def test_cli_private_exclusive_output_preserves_original_database(self):
        out = self.root / "private.json"
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.assertEqual(main(["--db", str(self.db), "--out", str(out)]), 0)
        self.assertTrue(out.is_file())
        self.assertEqual(json.loads(out.read_text())["stored_records"], 10)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)
        self.assertFalse(Path(str(self.db) + "-wal").exists())
        self.assertFalse(Path(str(self.db) + "-shm").exists())
        if os.name != "nt":
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(SystemExit):
            main(["--db", str(self.db), "--out", str(out)])
        self.assertEqual(json.loads(out.read_text())["stored_records"], 10)

    def test_cli_rejects_corrupt_source_before_writing_any_output(self):
        with sqlite3.connect(self.db) as c:
            c.execute("DELETE FROM sources WHERE id = 1")
        out = self.root / "must-not-exist.json"
        with self.assertRaises(SystemExit):
            main(["--db", str(self.db), "--out", str(out)])
        self.assertFalse(out.exists())

    def test_empty_archive_is_not_claimed_healthy_or_a_successful_collection(self):
        empty = self.root / "empty.db"
        with sqlite3.connect(empty) as c:
            c.executescript("""
                CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY, source_id INTEGER,
                    passed_relevance INTEGER, analyzed_at TEXT,
                    processing_state TEXT);
            """)
        with read_only(empty) as conn:
            report = audit(conn)
        self.assertEqual(report["stored_records"], 0)
        self.assertIsNone(report["max_article_id"])
        self.assertEqual(report["automatic_queue_candidates"], 0)
        self.assertFalse(report["collection_performed"])


if __name__ == "__main__":
    unittest.main()
