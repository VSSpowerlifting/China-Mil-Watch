"""Source-attributed analysis queue: no model, no database writes, no false queue."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from scripts import audit_analysis_queue_by_source as audit


NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


class StoredQueueAudit(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ipr-queue-audit-")
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.file = self.temp / "snapshot.db"
        self.con = sqlite3.connect(self.file)
        self.con.execute("""
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT
            )""")
        self.con.execute("""
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                source_id INTEGER,
                passed_relevance INTEGER,
                analyzed_at TEXT,
                processing_state TEXT,
                scraped_at TEXT
            )""")
        self.con.executemany("INSERT INTO sources VALUES (?,?,?)", [
            (1, "cn_mod", "china"),
            (2, "sg_mindef", "singapore"),
            (3, "unknown_desk", None),
        ])
        self.con.commit()
        self.addCleanup(self.con.close)

    def insert(self, ident, source_id=1, passed=None,
               analyzed=None, state=None, scraped="2026-10-08 13:00:00"):
        self.con.execute(
            "INSERT INTO articles VALUES (?,?,?,?,?,?)",
            (ident, source_id, passed, analyzed, state, scraped))
        self.con.commit()

    def get(self):
        return audit.summarize(self.con, at=NOW, live_days=14)

    def row(self, report, slug):
        return next(r for r in report["sources"] if r["source_slug"] == slug)

    def test_empty_source_queue_is_not_an_authenticated_clearance(self):
        r = self.get()
        self.assertEqual(r["stored_daily_queue_eligible"], 0)
        self.assertFalse(r["live_production_state_authenticated"])
        self.assertFalse(r["historical_run_completeness_established"])
        self.assertFalse(r["next_run_new_articles_known"])
        self.assertFalse(r["publication_authorized"])
        self.assertEqual(r["writes"], 0)

    def test_china_unscored_live_and_archive_are_distinct(self):
        self.insert(1, scraped="2026-10-08 12:00:00")
        self.insert(2, scraped="2026-08-02 12:00:00")
        r = self.get()
        x = self.row(r, "cn_mod")
        self.assertEqual(x["daily_unscored_live"], 1)
        self.assertEqual(x["daily_unscored_archive"], 1)
        self.assertEqual(r["stored_daily_queue_eligible"], 2)

    def test_china_pending_analysis_is_not_new_unscored(self):
        self.insert(1, passed=1, scraped="2026-09-01 12:00:00")
        r = self.get()
        self.assertEqual(r["stored_daily_pending_analysis"], 1)
        self.assertEqual(r["stored_daily_unscored"], 0)

    def test_singapore_unscored_held_out_of_china_model_queue(self):
        self.insert(1, source_id=2)
        r = self.get()
        x = self.row(r, "sg_mindef")
        self.assertFalse(x["daily_model_queue_eligible_by_desk"])
        self.assertEqual(x["held_unscored"], 1)
        self.assertEqual(r["stored_daily_queue_eligible"], 0)
        self.assertEqual(r["stored_held_out_of_daily"], 1)

    def test_singapore_pending_also_held_out(self):
        self.insert(1, source_id=2, passed=1)
        r = self.get()
        self.assertEqual(self.row(r, "sg_mindef")["held_pending_analysis"], 1)
        self.assertEqual(r["stored_held_out_of_daily"], 1)

    def test_paused_terminal_records_not_eligible(self):
        self.insert(1, state="paused")
        self.insert(2, state="terminal")
        r = self.get()
        self.assertEqual(r["totals"]["paused"], 1)
        self.assertEqual(r["totals"]["terminal"], 1)
        self.assertEqual(r["stored_daily_queue_eligible"], 0)

    def test_processed_and_rejected_are_not_backlog(self):
        self.insert(1, passed=1, analyzed="2026-10-08T13:00:00Z")
        self.insert(2, passed=0)
        r = self.get()
        self.assertEqual(r["totals"]["completed_analysis"], 1)
        self.assertEqual(r["totals"]["relevance_rejected"], 1)
        self.assertEqual(r["stored_daily_queue_eligible"], 0)

    def test_null_scrape_date_does_not_claim_recent_or_historical_age(self):
        self.insert(1, scraped=None)
        r = self.get()
        self.assertEqual(r["totals"]["daily_unscored_undated"], 1)
        self.assertEqual(r["totals"]["daily_unscored_live"], 0)

    def test_exact_cutoff_inclusive_and_one_day_before_archive(self):
        self.insert(1, scraped="2026-09-25 00:00:00")
        self.insert(2, scraped="2026-09-24 23:59:59")
        r = self.get()
        self.assertEqual(r["live_unscored_cutoff_utc_day"], "2026-09-25")
        self.assertEqual(r["totals"]["daily_unscored_live"], 1)
        self.assertEqual(r["totals"]["daily_unscored_archive"], 1)

    def test_unattributed_source_kept_visible_without_desk_guess(self):
        self.insert(1, source_id=999)
        r = self.get()
        x = self.row(r, "__missing_source__")
        self.assertEqual(x["desk_id"], "__undeclared_desk__")
        self.assertEqual(x["daily_unscored_live"], 1)
        self.assertTrue(x["daily_model_queue_eligible_by_desk"])
        self.assertEqual(x["rows_total"], 1)

    def test_null_desk_uses_pipeline_fallback_not_promoted_desk(self):
        self.insert(1, source_id=3)
        r = self.get()
        x = self.row(r, "unknown_desk")
        self.assertEqual(x["desk_id"], "__undeclared_desk__")
        self.assertEqual(x["daily_unscored_live"], 1)

    def test_unknown_processing_state_not_called_retriable(self):
        self.insert(1, state="mysterious")
        r = self.get()
        self.assertEqual(r["totals"]["unknown_state"], 1)
        self.assertEqual(r["stored_daily_queue_eligible"], 0)

    def test_bad_relevance_flag_fail_closed(self):
        self.insert(1, passed=2)
        with self.assertRaisesRegex(audit.QueueAuditError, "unexpected relevance"):
            self.get()

    def test_bad_scrape_timestamp_refused(self):
        self.insert(1, scraped="not a date")
        with self.assertRaisesRegex(audit.QueueAuditError, "scrape date is invalid"):
            self.get()

    def test_bad_snapshot_timezone_and_live_window_refused(self):
        self.insert(1)
        with self.assertRaisesRegex(audit.QueueAuditError, "timezone-aware"):
            audit.summarize(self.con, at=datetime(2026, 10, 9))
        with self.assertRaisesRegex(audit.QueueAuditError, "range"):
            audit.summarize(self.con, at=NOW, live_days=0)

    def test_incomplete_database_schema_refused(self):
        self.con.execute("DROP TABLE articles")
        self.con.commit()
        with self.assertRaisesRegex(audit.QueueAuditError, "requires current articles"):
            self.get()

    def test_by_source_and_total_accounting_exact(self):
        self.insert(1)
        self.insert(2, passed=1)
        self.insert(3, source_id=2)
        self.insert(4, passed=0)
        self.insert(5, state="paused")
        r = self.get()
        self.assertEqual(r["article_rows"], 5)
        self.assertEqual(sum(r["totals"].values()), 5)
        self.assertEqual(sum(x["rows_total"] for x in r["sources"]), 5)
        self.assertEqual(r["stored_daily_queue_eligible"], 2)
        self.assertEqual(r["stored_held_out_of_daily"], 1)

    def test_snapshot_reads_copy_without_modifying_tracked_db(self):
        self.insert(1)
        self.con.commit()
        before = hashlib.sha256(self.file.read_bytes()).hexdigest()
        r = audit.snapshot(self.file, at=NOW)
        after = hashlib.sha256(self.file.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual(r["input_file_sha256"]["db"], before)
        self.assertEqual(r["stored_daily_queue_eligible"], 1)
        self.assertTrue(r["input_file_identity_not_signed"])
        self.assertFalse(r["live_production_state_authenticated"])
        self.assertEqual(r["model_calls"], 0)
        self.assertEqual(r["writes"], 0)

    def test_concurrent_input_change_refused_without_misattributing_hash(self):
        self.insert(1)
        self.con.commit()
        original = audit.read_only

        @contextmanager
        def changed_during_copy(path):
            with original(path) as copy:
                # Simulate another actor modifying the *source* after we
                # hashed it. The audit must not label the scratch snapshot
                # with the old source hash if the source subsequently changes.
                self.insert(2, passed=1)
                yield copy

        with patch.object(audit, "read_only", side_effect=changed_during_copy):
            with self.assertRaisesRegex(audit.QueueAuditError,
                                        "changed during analysis audit"):
                audit.snapshot(self.file, at=NOW)

    def test_missing_db_refused_before_creating_it(self):
        p = self.temp / "missing.db"
        with self.assertRaisesRegex(audit.QueueAuditError, "absent"):
            audit.snapshot(p, at=NOW)
        self.assertFalse(p.exists())

    def test_cli_json_only_no_article_body_or_auth_tokens(self):
        self.insert(1)
        self.con.commit()
        result = subprocess.run(
            [sys.executable, str(Path(audit.__file__).resolve()),
             "--db", str(self.file)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertIn("input_file_sha256", parsed)
        self.assertNotIn("text_original", result.stdout)
        self.assertNotIn("ANTHROPIC_API_KEY", result.stdout)
        self.assertEqual(parsed["model_calls"], 0)
        self.assertEqual(parsed["writes"], 0)


if __name__ == "__main__":
    unittest.main()
