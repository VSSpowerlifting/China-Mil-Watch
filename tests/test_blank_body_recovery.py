"""Historical body-recovery preflight never fetches or rewrites publisher text."""
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

from scripts import audit_blank_body_recovery as a
from scripts import audit_analysis_queue_by_source as q

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


class BlankBodyRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ipr-empty-body-preflight-")
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "fixture.db"
        self.con = sqlite3.connect(self.db)
        self.addCleanup(self.con.close)
        self.con.executescript("""
          CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
          CREATE TABLE articles (
              id INTEGER PRIMARY KEY, source_id INTEGER,
              passed_relevance INTEGER, analyzed_at TEXT,
              processing_state TEXT, scraped_at TEXT, published_date TEXT,
              processing_attempts INTEGER, processing_reason TEXT, url TEXT,
              text_original TEXT
          );
        """)
        self.con.executemany("INSERT INTO sources VALUES (?,?,?)", [
            (1, "global_times_mil", "china"), (2, "pla_daily", "china"),
            (3, "sg_mindef", "singapore")])
        self.con.commit()

    def insert(self, ident, *, source=1, body=None, scraped="2026-09-15",
               passed=None, state=None, attempts=None, analyzed=None, reason=None,
               url="https://www.globaltimes.cn/page/202609/123.shtml"):
        self.con.execute(
            "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ident, source, passed, analyzed, state, scraped, "2026-09-14",
             attempts, reason, url, body))
        self.con.commit()

    def report(self, **kwargs):
        return a.review(self.con, at=NOW, live_days=14, **kwargs)

    def test_empty_review_is_not_no_publications_claim(self):
        r = self.report()
        self.assertEqual(0, r["blank_body_daily_candidates"])
        self.assertFalse(r["publisher_page_rechecked"])
        self.assertFalse(r["extraction_recovery_validated"])
        self.assertFalse(r["retry_authorized"])
        self.assertEqual(r["network_requests"], 0)

    def test_september_fix_boundary_is_recorded_not_inferred_causation(self):
        self.insert(1, scraped="2026-09-15")
        self.insert(2, scraped="2026-09-16")
        self.insert(3, scraped="2026-10-08")
        self.insert(4, scraped=None)
        self.insert(5, source=2, scraped="2026-08-01")
        r = self.report()
        self.assertEqual(5, r["blank_body_daily_candidates"])
        self.assertEqual(
            {"before_documented_fix_date": 1,
             "on_or_after_documented_fix_date": 2,
             "missing_scrape_date": 1, "not_applicable": 1},
            r["date_relations"])
        self.assertEqual("on_or_after_documented_fix_date",
                         r["candidate_review_receipts"][1][
                             "documented_fix_date_relation"])
        self.assertFalse(r["publisher_page_rechecked"])

    def test_nonblank_rejected_held_and_paused_are_excluded(self):
        self.insert(1, body="Real prose")
        self.insert(2, passed=0)
        self.insert(3, source=3)
        self.insert(4, state="paused")
        self.insert(5, passed=1, analyzed="2026-09-15")
        self.insert(6, passed=1, body="")
        r = self.report()
        self.assertEqual(1, r["blank_body_daily_candidates"])
        self.assertEqual(6, r["candidate_review_receipts"][0]["article_id"])

    def test_prior_failures_retained_as_review_not_retries(self):
        self.insert(1, attempts=3, reason="empty_body_unconfirmed",
                    state="retriable")
        r = self.report()
        self.assertTrue(r["candidate_review_receipts"][0]["had_processing_attempts"])
        self.assertEqual("empty_body_unconfirmed",
                         r["candidate_review_receipts"][0]["processing_reason"])
        self.assertFalse(r["retry_authorized"])
        self.assertEqual(0, r["model_calls"])

    def test_no_url_by_default_explicit_preview_drops_query_and_fragment(self):
        self.insert(1, url="https://www.globaltimes.cn/page/202609/123.shtml"
                           "?session=NO_PUBLIC_LEAK#secret")
        default = json.dumps(self.report())
        self.assertNotIn("session", default)
        self.assertNotIn("globaltimes.cn/page", default)
        with_urls = self.report(include_review_urls=True)
        url = with_urls["candidate_review_receipts"][0]["review_url_display_only"]
        self.assertEqual("https://www.globaltimes.cn/page/202609/123.shtml", url)
        self.assertNotIn("secret", json.dumps(with_urls))
        self.assertTrue(with_urls["source_urls_included_by_operator"])

    def test_unsafe_review_urls_rejected_only_on_explicit_opt_in(self):
        self.insert(1, url="https://user:password@www.globaltimes.cn/page/1")
        self.assertEqual(self.report()["blank_body_daily_candidates"], 1)
        with self.assertRaisesRegex(q.QueueAuditError, "unsafe article review"):
            self.report(include_review_urls=True)

    def test_source_counts_and_original_queue_reconcile(self):
        self.insert(1)
        self.insert(2, scraped="2026-10-08")
        self.insert(3, source=2)
        self.insert(4, source=3)
        self.insert(5, passed=0)
        r = self.report()
        self.assertEqual(r["blank_body_daily_candidates"], 3)
        self.assertEqual(sum(s["count"] for s in r["source_date_relations"]), 3)
        self.assertEqual(r["stored_daily_queue_eligible"], 3)

    def test_reject_more_than_one_hundred_candidates(self):
        for ident in range(1, 102):
            self.insert(ident)
        with self.assertRaisesRegex(q.QueueAuditError, "candidate cap"):
            self.report()

    def test_missing_source_schema_rejected_by_canonical_audit(self):
        self.con.execute("DROP TABLE sources")
        self.con.commit()
        with self.assertRaisesRegex(q.QueueAuditError, "requires current sources"):
            self.report()

    def test_snapshot_preserves_original_hash_and_sidecars(self):
        self.insert(1)
        prior = hashlib.sha256(self.db.read_bytes()).hexdigest()
        report = a.snapshot(self.db, at=NOW)
        self.assertEqual(prior, report["input_file_sha256"]["db"])
        self.assertEqual(prior, hashlib.sha256(self.db.read_bytes()).hexdigest())
        self.assertFalse(Path(str(self.db) + "-wal").exists())
        self.assertFalse(Path(str(self.db) + "-shm").exists())

    def test_change_during_audit_fails_closed(self):
        self.insert(1)
        original = a.queue._snapshot_file_hashes
        called = [0]
        def changed(path):
            called[0] += 1
            if called[0] == 2:
                self.insert(2)
            return original(path)
        with patch.object(a.queue, "_snapshot_file_hashes", side_effect=changed):
            with self.assertRaisesRegex(q.QueueAuditError, "changed"):
                a.snapshot(self.db, at=NOW)

    def test_cli_json_without_urls_and_without_writes(self):
        self.insert(1, url="https://www.globaltimes.cn/page/1?secret=1")
        result = subprocess.run(
            [sys.executable, str(Path(a.__file__).resolve()),
             "--db", str(self.db)], text=True,
            capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        r = json.loads(result.stdout)
        self.assertEqual(1, r["blank_body_daily_candidates"])
        self.assertNotIn("review_url_display_only", result.stdout)
        self.assertNotIn("secret=1", result.stdout)
        self.assertFalse(r["publication_authorized"])
        self.assertEqual(0, r["network_requests"])
        self.assertEqual(0, r["writes"])


if __name__ == "__main__":
    unittest.main()
