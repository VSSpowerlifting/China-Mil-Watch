"""Actual planner → pipeline.run → Analyzer → scratch SQLite → private journal."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import sqlite3
import anthropic
import httpx
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pipeline
from analysis.analyzer import Analyzer
from migrations.runner import apply_all, connect
from storage import db
from tests.test_analysis_admission import MockClient, response
from tests.test_migrations import build_legacy_db
from scripts.analysis_capacity import PrivateRunJournal, read_packet, validate_packet


class ScratchRuntime(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-capacity-offline-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "fictional.db"
        build_legacy_db(self.path, articles=0)
        conn = connect(self.path)
        apply_all(conn)
        conn.execute("INSERT INTO sources(slug,display_name,base_url,language,desk_id) VALUES ('fictional-test','FICTIONAL test source','https://fictional.invalid','en','china')")
        conn.commit()
        conn.close()
        self.rows = []
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        for module, name, value in ((db, "DB_PATH", self.path), (pipeline, "DB_PATH", self.path),
                                    (pipeline, "CACHE_DIR", self.root / "cache"),
                                    (pipeline, "OUTPUT_DIR", self.root / "unused-output"),
                                    (pipeline, "ANTHROPIC_API_KEY", "fictional-offline-key")):
            self.patches.enter_context(patch.object(module, name, value))
        self.patches.enter_context(patch.dict("os.environ", {"LLM_USAGE_RECORD_PATH": str(self.root / "telemetry.json")}))
        self.marker = self.patches.enter_context(patch.object(pipeline, "_write_billing_failure_marker"))
        self.client = MockClient()
        self.patches.enter_context(patch("analysis.analyzer.anthropic.Anthropic", return_value=self.client))
        self.patches.enter_context(patch("analysis.analyzer.ANTHROPIC_API_KEY", "fictional-offline-key"))
        self.journal = PrivateRunJournal(self.root / "run.jsonl")
        self.addCleanup(self.journal.close)

    def seed(self, body="FICTIONAL source body", **state):
        aid = db.insert_article({"url": "https://fictional.invalid/%d" % len(self.rows),
                                 "source_slug": "fictional-test", "title_original": "FICTIONAL title",
                                 "text_original": body, "published_date": "2026-10-11",
                                 "content_hash": "fictional-%d" % len(self.rows)}, None)
        self.rows.append(aid)
        if state:
            with db.get_conn() as conn:
                conn.execute("UPDATE articles SET " + ",".join(k + "=?" for k in state) + " WHERE id=?", [*state.values(), aid])
        return aid

    def run_pipeline(self, budget="24"):
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.run([], date(2026, 10, 11), budget_usd=budget,
                         receipt_sink=self.journal, generate_output=False)

    def test_complete_scratch_dao_and_usage_receipts_reconcile(self):
        aid = self.seed()
        self.run_pipeline()
        packet = read_packet(self.journal.path)
        self.assertEqual(packet["run"]["articles"][0]["outcome"], "fully-analyzed")
        self.assertTrue(packet["run"]["articles"][0]["attempted"])
        self.assertEqual(packet["run"]["status"], "completed")
        self.assertEqual(len(packet["run"]["calls"]), 4)
        with db.get_conn() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
            self.assertIsNotNone(row["analyzed_at"])
            self.assertEqual(row["summary_english"], "FICTIONAL summary")
            self.assertEqual(row["processing_attempts"], None)
        self.assertNotIn("FICTIONAL source body", self.journal.path.read_text())
        self.assertNotIn("FICTIONAL summary", self.journal.path.read_text())
        telemetry = json.loads((self.root / "telemetry.json").read_text())
        self.assertAlmostEqual(telemetry["estimated_cost_usd"], float(packet["run"]["known_cost_usd"]), places=6)
        self.assertEqual(telemetry["articles_fully_analyzed"], 1)
        self.assertEqual(self.journal.path.stat().st_mode & 0o777, 0o600)

    def test_budget_denial_and_holds_do_not_consume_retry_state(self):
        ready = self.seed(processing_attempts=2, processing_state="retriable")
        blank = self.seed("\u2003\n")
        paused = self.seed(processing_state="paused", processing_attempts=5)
        self.run_pipeline("0.01")
        packet = read_packet(self.journal.path)
        self.assertEqual(packet["plan"]["selected_ids"], [ready])
        self.assertEqual(packet["run"]["articles"][0]["outcome"], "budget-deferred")
        self.assertEqual(self.client.requests, [])
        self.assertEqual(packet["plan"]["counts"]["held"], 2)
        with db.get_conn() as conn:
            self.assertEqual(conn.execute("SELECT processing_attempts FROM articles WHERE id=?", (ready,)).fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT processing_state FROM articles WHERE id=?", (paused,)).fetchone()[0], "paused")
            self.assertIsNone(conn.execute("SELECT passed_relevance FROM articles WHERE id=?", (blank,)).fetchone()[0])
        self.marker.assert_not_called()

    def test_missing_usage_is_unknown_no_full_dao_result_no_retry_denial(self):
        aid = self.seed(processing_attempts=2)
        self.client.hook = lambda k: response(usage=False)
        self.run_pipeline()
        packet = read_packet(self.journal.path)
        self.assertEqual(packet["run"]["status"], "incomplete")
        self.assertEqual(packet["run"]["articles"][0]["outcome"], "unknown")
        self.assertGreater(Decimal(packet["run"]["unresolved_usd"]), 0)
        with db.get_conn() as conn:
            row = conn.execute("SELECT analyzed_at, processing_attempts FROM articles WHERE id=?", (aid,)).fetchone()
            self.assertIsNone(row[0])
            self.assertEqual(row[1], 2)
        self.marker.assert_not_called()

    def test_interrupted_execution_keeps_incomplete_write_ahead_record(self):
        self.seed()
        self.client.hook = lambda k: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt): self.run_pipeline()
        packet = read_packet(self.journal.path)
        self.assertEqual(packet["run"]["status"], "incomplete")
        self.assertGreater(Decimal(packet["run"]["unresolved_usd"]), 0)

    def test_invalid_guard_cannot_fall_back_to_legacy(self):
        self.seed()
        with self.assertRaises(ValueError): self.run_pipeline("NaN")
        self.assertEqual(self.client.requests, [])

    def test_fatal_account_error_keeps_remaining_records_unattempted(self):
        first = self.seed()
        second = self.seed()
        third = self.seed()
        def blocked(k):
            raise anthropic.APIStatusError("FICTIONAL account block", response=httpx.Response(402,
                  request=httpx.Request("POST", "https://fictional.invalid")), body={})
        self.client.hook = blocked
        with self.assertRaises(SystemExit): self.run_pipeline()
        r = read_packet(self.journal.path)["run"]
        self.assertEqual(len(self.client.requests), 1)
        self.assertEqual([a["outcome"] for a in r["articles"]], ["unknown", "unattempted", "unattempted"])
        self.assertEqual(r["status"], "incomplete")
        self.marker.assert_called_once()

    def test_disabled_guard_preserves_legacy_calls_and_dao_results(self):
        aid = self.seed()
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.run([], date(2026, 10, 11), generate_output=False)
        self.assertEqual(len(self.client.requests), 4)
        self.assertEqual(self.client.options, [])
        self.assertEqual(self.client.max_retries, 2)
        with db.get_conn() as conn:
            self.assertIsNotNone(conn.execute("SELECT analyzed_at FROM articles WHERE id=?", (aid,)).fetchone()[0])

    def test_stale_expected_plan_refused_before_provider_dispatch(self):
        self.seed()
        with self.assertRaisesRegex(ValueError, "stale"):
            pipeline.run([], date(2026, 10, 11), budget_usd="24", receipt_sink=self.journal,
                         expected_plan={"plan_id": "stale"}, generate_output=False)
        self.assertEqual(self.client.requests, [])
