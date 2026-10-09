"""Fail-visible, read-only metadata review of stored analysis failure causes."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import audit_analysis_failure_causes as audit
from scripts import audit_analysis_queue_by_source as base

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


class FailureReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ipr-failure-review-")
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / "fixture.db"
        self.conn = sqlite3.connect(self.db)
        self.addCleanup(self.conn.close)
        self.conn.executescript("""
          CREATE TABLE sources (
            id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT
          );
          CREATE TABLE articles (
            id INTEGER PRIMARY KEY, source_id INTEGER,
            passed_relevance INTEGER, analyzed_at TEXT,
            processing_state TEXT, processing_reason TEXT,
            processing_attempts INTEGER, scraped_at TEXT,
            published_date TEXT, text_original TEXT
          );
        """)
        self.conn.executemany("INSERT INTO sources VALUES (?,?,?)", [
            (1, "cn_mod", "china"), (2, "sg_mindef", "singapore")
        ])
        self.conn.commit()

    def insert(self, ident, *, source=1, passed=None, analyzed=None,
               state=None, reason=None, attempts=None,
               body="Sample government publication",
               published="2026-10-07", scraped="2026-10-08"):
        self.conn.execute("INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?)", (
            ident, source, passed, analyzed, state, reason, attempts,
            scraped, published, body))
        self.conn.commit()

    def report(self):
        return audit.examine(self.conn, at=NOW, live_days=14)

    def test_empty_snapshot_is_not_a_health_certification(self):
        report = self.report()
        self.assertEqual(report["stored_daily_queue_eligible"], 0)
        self.assertEqual(report["totals"]["daily_blank_body"], 0)
        self.assertFalse(report["root_causes_established"])
        self.assertFalse(report["model_spend_authorized"])
        self.assertFalse(report["retry_authorized"])
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(report["writes"], 0)

    def test_daily_blank_retries_and_overlap_are_not_added_together(self):
        self.insert(1, body=" \t\n", attempts=2,
                    state="retriable", reason="empty_body_unconfirmed")
        self.insert(2, body="", attempts=None)
        self.insert(3, passed=1, attempts=1,
                    state="retriable", reason="analysis_incomplete")
        self.insert(4, source=2, body=None, attempts=3,
                    state="retriable", reason="transient_failure")
        report = self.report()
        self.assertEqual(report["stored_daily_queue_eligible"], 3)
        self.assertEqual(report["stored_held_out_of_daily"], 1)
        self.assertEqual(report["totals"]["daily_blank_body"], 2)
        self.assertEqual(report["totals"]["daily_prior_attempts"], 2)
        self.assertEqual(report["totals"]["daily_blank_and_prior_attempts"], 1)
        self.assertEqual(report["recorded_failure_reasons_on_daily_queue"],
                         {"analysis_incomplete": 1, "empty_body_unconfirmed": 1})

    def test_paused_and_terminal_are_not_daily_backlog(self):
        self.insert(1, state="paused", reason="retry_budget_exhausted", attempts=5)
        self.insert(2, state="terminal", reason="unsupported_media_only", attempts=1)
        report = self.report()
        self.assertEqual(report["stored_daily_queue_eligible"], 0)
        self.assertEqual(report["totals"]["paused"], 1)
        self.assertEqual(report["totals"]["terminal"], 1)
        self.assertEqual(report["totals"]["state_inconsistency"], 0)

    def test_mismatched_processing_states_are_review_flags_not_auto_repairs(self):
        self.insert(1, passed=0, analyzed="2026-10-07")
        self.insert(2, state="paused", reason="transient_failure", attempts=4)
        self.insert(3, state="retriable", reason="unsupported_media_only", attempts=1)
        self.insert(4, state="terminal", reason="analysis_failed", attempts=1)
        report = self.report()
        self.assertEqual(report["totals"]["state_inconsistency"], 4)
        self.assertEqual(report["totals"]["paused"], 1)
        self.assertEqual(report["totals"]["terminal"], 1)
        self.assertFalse(report["retry_authorized"])

    def test_unknown_failure_reason_is_a_flag_not_an_invented_cause(self):
        self.insert(1, attempts=1, reason=None, state="retriable")
        self.insert(2, attempts=1, reason="future_reason", state="retriable")
        report = self.report()
        self.assertEqual(report["totals"]["daily_unknown_failure_reason"], 2)
        self.assertEqual(report["recorded_failure_reasons_on_daily_queue"],
                         {"__missing_reason__": 1, "future_reason": 1})

    def test_source_totals_and_real_categories_reconcile(self):
        self.insert(1, body="", attempts=2,
                    state="retriable", reason="empty_body_unconfirmed")
        self.insert(2, source=2)
        self.insert(3, passed=0)
        report = self.report()
        self.assertEqual(report["article_rows"], 3)
        self.assertEqual(report["stored_daily_queue_eligible"], 1)
        self.assertEqual(sum(s["daily_eligible"] for s in report["sources"]), 1)
        self.assertEqual(sum(s["daily_blank_body"] for s in report["sources"]), 1)
        self.assertEqual(report["sources"][0]["source_slug"], "cn_mod")
        self.assertEqual(report["stored_held_out_of_daily"], 1)

    def test_body_and_url_are_never_in_output(self):
        self.insert(1, body="DO_NOT_PUBLISH_CONTENT")
        raw = json.dumps(self.report())
        self.assertNotIn("DO_NOT_PUBLISH_CONTENT", raw)
        self.assertNotIn("text_original", raw)
        self.assertNotIn("url", raw)
        self.assertEqual(self.report()["samples_by_flag"]["daily_blank_body"], [])

    def test_review_sample_limit_enforced(self):
        for ident in range(1, 19):
            self.insert(ident, body="")
        r = self.report()
        self.assertEqual(r["totals"]["daily_blank_body"], 18)
        self.assertEqual(len(r["samples_by_flag"]["daily_blank_body"]), 12)

    def test_unknown_state_not_a_daily_model_dispatch(self):
        self.insert(1, state="future_processing_state", body="")
        report = self.report()
        self.assertEqual(report["stored_daily_queue_eligible"], 0)
        self.assertEqual(report["totals"]["daily_blank_body"], 0)

    def test_invalid_attempts_fail_closed(self):
        self.insert(1, attempts=-3)
        with self.assertRaisesRegex(base.QueueAuditError, "attempt"):
            self.report()

    def test_no_writes_and_database_hash_pinned(self):
        self.insert(1, body=None)
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        report = audit.snapshot(self.db, at=NOW)
        self.assertEqual(report["input_file_sha256"]["db"], before)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)
        self.assertFalse(Path(str(self.db)+"-wal").exists())
        self.assertFalse(Path(str(self.db)+"-shm").exists())

    def test_changed_database_refused(self):
        self.insert(1)
        genuine = audit.queue._snapshot_file_hashes
        calls = [0]
        def change(path):
            calls[0] += 1
            if calls[0] == 2:
                self.insert(2)
            return genuine(path)
        with patch.object(audit.queue, "_snapshot_file_hashes", side_effect=change):
            with self.assertRaisesRegex(base.QueueAuditError, "changed"):
                audit.snapshot(self.db, at=NOW)

    def test_cli_clean_json_without_calls_or_mutation(self):
        self.insert(1, body="", attempts=1, reason="analysis_failed",
                    state="retriable")
        result = subprocess.run(
            [sys.executable, str(Path(audit.__file__).resolve()), "--db",
             str(self.db)],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["totals"]["daily_prior_attempts"], 1)
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(report["writes"], 0)
        self.assertFalse(report["publication_authorized"])


if __name__ == "__main__":
    unittest.main()
