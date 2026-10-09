"""Read-only stored backlog triage never becomes automated model selection."""
from __future__ import annotations

import copy
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

from scripts import audit_analysis_backlog_triage as triage
from scripts import audit_analysis_queue_by_source as queue_audit

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


class TriageContracts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-triage-contract-")
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.path = self.folder / "test.db"
        self.conn = sqlite3.connect(self.path)
        self.addCleanup(self.conn.close)
        self.conn.executescript("""
          CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
          CREATE TABLE articles (
            id INTEGER PRIMARY KEY, source_id INTEGER, passed_relevance INTEGER,
            analyzed_at TEXT, processing_state TEXT, scraped_at TEXT,
            published_date TEXT, text_original TEXT, processing_attempts INTEGER
          );
        """)
        self.conn.executemany("INSERT INTO sources VALUES (?,?,?)", [
            (1, "cn_mod", "china"), (2, "sg_mindef", "singapore"),
            (3, "undeclared", None)])
        self.conn.commit()

    def insert(self, id, *, source=1, passed=None, analyzed=None,
               state=None, scraped="2026-10-08 04:00:00",
               published="2026-10-07", body="Official release prose",
               attempts=None):
        self.conn.execute("INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?)", (
            id, source, passed, analyzed, state, scraped, published, body, attempts))
        self.conn.commit()

    def audit(self):
        return triage.audit(self.conn, at=NOW, live_days=14)

    def test_empty_database_has_no_permission_or_phantom_work(self):
        v = self.audit()
        self.assertEqual(v["article_rows"], 0)
        self.assertEqual(v["stored_daily_queue_eligible"], 0)
        self.assertEqual(v["metadata_flags"]["daily_missing_body"], 0)
        self.assertFalse(v["model_spend_authorized"])
        self.assertFalse(v["editorial_significance_assessed"])
        self.assertFalse(v["publication_authorized"])
        self.assertEqual(v["model_calls"], 0)
        self.assertEqual(v["writes"], 0)

    def test_review_lanes_reconcile_with_canonical_queue(self):
        self.insert(1)
        self.insert(2, scraped="2026-07-01 10:00:00")
        self.insert(3, scraped=None)
        self.insert(4, passed=1, attempts=2)
        self.insert(5, body=" ")
        self.insert(6, source=2)
        self.insert(7, state="paused")
        self.insert(8, state="mystery")
        self.insert(9, passed=0)
        self.insert(10, passed=1, analyzed="2026-10-08")
        report = self.audit()
        labels = report["review_lanes"]
        for key in triage.REVIEW_LANES:
            self.assertEqual(labels[key], 1 if key != "ready_undated_unscored"
                             else 1)
        # Eight reviewable rows: 5 Daily, 1 held, 1 paused, 1 unknown.
        self.assertEqual(report["article_rows"], 10)
        self.assertEqual(report["stored_daily_queue_eligible"], 5)
        self.assertEqual(report["stored_held_out_of_daily"], 1)
        self.assertEqual(report["stored_paused"], 1)
        self.assertEqual(report["metadata_flags"]["daily_missing_body"], 1)
        self.assertEqual(report["metadata_flags"]["daily_has_previous_failures"], 1)
        self.assertEqual(report["sources"][0]["desk_id"], "china")
        self.assertEqual(report["sources"][1]["desk_id"], "singapore")

    def test_missing_body_is_only_a_review_flag_not_terminal(self):
        self.insert(1, body=None)
        self.insert(2, passed=1, body=" \n")
        report = self.audit()
        self.assertEqual(report["stored_daily_queue_eligible"], 2)
        self.assertEqual(report["review_lanes"]["missing_body_daily"], 2)
        self.assertFalse(report["text_extraction_verified"])
        self.assertFalse(report["model_spend_authorized"])

    def test_unknown_desk_fallback_is_labeled_not_claimed_china(self):
        self.insert(1, source=3)
        report = self.audit()
        self.assertEqual(report["stored_daily_queue_eligible"], 1)
        self.assertEqual(report["metadata_flags"]["daily_without_declared_desk"], 1)
        self.assertEqual(report["sources"][0]["desk_id"], "__undeclared_desk__")

    def test_historical_and_held_records_never_mix(self):
        self.insert(1, source=1, scraped="2026-06-10 10:00:00")
        self.insert(2, source=2)
        report = self.audit()
        self.assertEqual(report["review_lanes"]["ready_archive_unscored"], 1)
        self.assertEqual(report["review_lanes"]["held_desk_separate_review"], 1)
        self.assertEqual(report["stored_daily_queue_eligible"], 1)
        self.assertEqual(report["stored_held_out_of_daily"], 1)

    def test_unscored_missing_publication_date_and_attempts_are_not_verdicts(self):
        self.insert(1, published=None, attempts=3)
        report = self.audit()
        self.assertEqual(report["metadata_flags"]["daily_missing_publication_date"], 1)
        self.assertEqual(report["metadata_flags"]["daily_has_previous_failures"], 1)
        self.assertFalse(report["publisher_dates_authenticated"])

    def test_no_urls_bodies_or_titles_leave_audit(self):
        self.insert(1, body="SENSITIVE_SENTINEL_BODY_NOT_FOR_REPORT")
        report = self.audit()
        dumped = json.dumps(report)
        self.assertNotIn("SENSITIVE_SENTINEL_BODY_NOT_FOR_REPORT", dumped)
        self.assertNotIn("text_original", dumped)
        self.assertNotIn("url", dumped)
        self.assertEqual(report["review_samples"]["ready_recent_unscored"][0][
            "article_id"], 1)

    def test_sample_limit_is_explicit_and_totals_stay_complete(self):
        for ident in range(1, 27):
            self.insert(ident)
        report = self.audit()
        self.assertEqual(report["stored_daily_queue_eligible"], 26)
        self.assertEqual(len(report["review_samples"]["ready_recent_unscored"]), 20)
        self.assertEqual(report["review_sample_limit_per_lane"], 20)

    def test_invalid_retry_counter_refuses_daily_queue(self):
        self.insert(1, attempts=-1)
        with self.assertRaisesRegex(queue_audit.QueueAuditError, "attempt"):
            self.audit()

    def test_malformed_schema_refuses_instead_of_guessing_text(self):
        self.conn.execute("DROP TABLE articles")
        self.conn.execute("""
          CREATE TABLE articles (
            id INTEGER, source_id INTEGER, passed_relevance INTEGER,
            analyzed_at TEXT, processing_state TEXT, scraped_at TEXT)
        """)
        self.conn.commit()
        with self.assertRaisesRegex(queue_audit.QueueAuditError, "full article"):
            self.audit()

    def test_snapshot_pins_hash_and_no_sqlite_sidecars_or_writes(self):
        self.insert(1)
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        report = triage.snapshot(self.path, at=NOW)
        self.assertEqual(report["input_file_sha256"]["db"], before)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)
        self.assertFalse(Path(str(self.path)+"-wal").exists())
        self.assertFalse(Path(str(self.path)+"-shm").exists())

    def test_change_during_snapshot_fails_closed(self):
        self.insert(1)
        real = triage.existing._snapshot_file_hashes
        calls = [0]
        def modified(path):
            calls[0] += 1
            if calls[0] == 2:
                self.insert(2)
            return real(path)
        with patch.object(triage.existing, "_snapshot_file_hashes", side_effect=modified):
            with self.assertRaisesRegex(queue_audit.QueueAuditError, "changed"):
                triage.snapshot(self.path, at=NOW)

    def test_cli_json_only_without_model_calls(self):
        self.insert(1)
        result = subprocess.run([
            sys.executable, str(Path(triage.__file__).resolve()),
            "--db", str(self.path)], text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["stored_daily_queue_eligible"], 1)
        self.assertEqual(parsed["model_calls"], 0)
        self.assertEqual(parsed["writes"], 0)
        self.assertFalse(parsed["model_spend_authorized"])
        self.assertFalse(parsed["publication_authorized"])


    def test_body_ready_dispatch_is_separate_from_stored_queue_count(self):
        self.insert(1, body="Published statement")
        self.insert(2, body="")
        self.insert(3, body=" \n\t ")
        self.insert(4, source=2, body="Held-desk statement")
        self.insert(5, state="paused", body="Paused statement")
        report = self.audit()
        self.assertEqual(report["stored_daily_queue_eligible"], 3)
        self.assertEqual(report["stored_daily_model_dispatch_body_ready"], 1)
        self.assertEqual(report["stored_daily_model_dispatch_body_withheld"], 2)
        self.assertEqual(report["metadata_flags"]["daily_missing_body"], 2)
        self.assertEqual(report["stored_held_out_of_daily"], 1)
        self.assertEqual(report["sources"][0]["daily_model_dispatch_body_ready"], 1)
        self.assertEqual(report["sources"][0]["daily_model_dispatch_body_withheld"], 2)
        self.assertFalse(report["model_spend_authorized"])
        self.assertTrue(report["model_dispatch_preview_not_future_run_workload"])

    def test_unicode_only_whitespace_has_no_dispatch_body(self):
        self.insert(1, body="\u00a0\u2003\n")
        report = self.audit()
        # SQLite TRIM is ASCII-only, so prior review-lane counts are kept
        # unchanged; the stricter new model dispatch contract is separate.
        self.assertEqual(report["review_lanes"]["ready_recent_unscored"], 1)
        self.assertEqual(report["metadata_flags"]["daily_missing_body"], 0)
        self.assertEqual(report["stored_daily_model_dispatch_body_ready"], 0)
        self.assertEqual(report["stored_daily_model_dispatch_body_withheld"], 1)

    def test_sqlite_blob_cannot_masquerade_as_dispatchable_prose(self):
        self.insert(1, body=b"Not verified decoded text")
        report = self.audit()
        self.assertEqual(report["stored_daily_queue_eligible"], 1)
        self.assertEqual(report["stored_daily_model_dispatch_body_ready"], 0)
        self.assertEqual(report["stored_daily_model_dispatch_body_withheld"], 1)

    def test_no_queue_records_produce_no_dispatch_permission(self):
        self.insert(1, source=2)
        self.insert(2, state="paused")
        self.insert(3, passed=0)
        report = self.audit()
        self.assertEqual(report["stored_daily_queue_eligible"], 0)
        self.assertEqual(report["stored_daily_model_dispatch_body_ready"], 0)
        self.assertEqual(report["stored_daily_model_dispatch_body_withheld"], 0)
        self.assertFalse(report["model_spend_authorized"])
        self.assertTrue(report["model_dispatch_preview_not_spending_approval"])

    def test_only_counts_not_body_content_leave_the_audit(self):
        sentinel = "PRIVATE_SOURCE_BODY_SENTINEL_NOT_IN_OPERATOR_REPORT"
        self.insert(1, body=sentinel)
        self.insert(2, body="\u2003")
        report = self.audit()
        dumped = json.dumps(report)
        self.assertNotIn(sentinel, dumped)
        self.assertNotIn("stored_original_body", dumped)
        self.assertEqual(report["stored_daily_model_dispatch_body_ready"], 1)
        self.assertEqual(report["stored_daily_model_dispatch_body_withheld"], 1)


if __name__ == "__main__":
    unittest.main()
