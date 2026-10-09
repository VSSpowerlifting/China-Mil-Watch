"""Stored LLM usage evidence is consistent, read-only and not spending authority."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import audit_stored_llm_capacity as audit


def receipt(date="2026-10-06", cost=0.006):
    tasks = [
        {"task": "relevance", "model": "haiku", "calls": 3,
         "succeeded_calls": 3, "failed_calls": 0, "input_tokens": 120,
         "output_tokens": 12, "cache_creation_input_tokens": 0,
         "cache_read_input_tokens": 0, "estimated_cost_usd": 0.001},
        {"task": "translation", "model": "sonnet", "calls": 1,
         "succeeded_calls": 1, "failed_calls": 0, "input_tokens": 100,
         "output_tokens": 40, "cache_creation_input_tokens": 0,
         "cache_read_input_tokens": 0, "estimated_cost_usd": 0.002},
        {"task": "summary", "model": "sonnet", "calls": 1,
         "succeeded_calls": 1, "failed_calls": 0, "input_tokens": 90,
         "output_tokens": 30, "cache_creation_input_tokens": 0,
         "cache_read_input_tokens": 0, "estimated_cost_usd": 0.002},
        {"task": "categorization", "model": "sonnet", "calls": 1,
         "succeeded_calls": 1, "failed_calls": 0, "input_tokens": 90,
         "output_tokens": 10, "cache_creation_input_tokens": 0,
         "cache_read_input_tokens": 0, "estimated_cost_usd": 0.001},
    ]
    return {
        "schema_version": 1, "run_date": date,
        "recorded_at": date + "T19:30:00+00:00",
        "run_status": "completed",
        "analysis_model": "sonnet", "relevance_model": "haiku",
        "articles_queued": 3, "articles_fully_analyzed": 1,
        "calls": 6, "succeeded_calls": 6, "failed_calls": 0,
        "input_tokens": 400, "output_tokens": 102,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
        "estimated_cost_usd": cost,
        "estimated_cost_per_analyzed_article_usd": cost,
        "unpriced_models": [], "pricing_checked": "2026-10-01",
        "tasks": tasks,
    }


class StoredUsageEvidenceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="ipr-capacity-ledger-")
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "usage.jsonl"

    def put(self, *rows):
        self.path.write_text("".join(json.dumps(x) + "\n" for x in rows),
                             encoding="utf-8")

    def test_two_receipts_and_missing_day_not_missing_execution(self):
        self.put(receipt("2026-10-06"), receipt("2026-10-08"))
        result = audit.snapshot(self.path)
        self.assertEqual(result["recorded_run_dates"], 2)
        self.assertEqual(result["calendar_dates_with_no_usage_record"],
                         ["2026-10-07"])
        self.assertTrue(result["no_record_does_not_prove_no_execution"])
        self.assertEqual(result["totals"]["articles_queued"], 6)
        self.assertEqual(result["totals"]["articles_fully_analyzed"], 2)
        self.assertEqual(result["totals"]["calls"], 12)
        self.assertAlmostEqual(result["estimated_cost_usd"], 0.012)
        self.assertFalse(result["model_spend_authorized"])
        self.assertFalse(result["analysis_cap_change_authorized"])
        self.assertFalse(result["matching_actions_jobs_authenticated"])
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["writes"], 0)

    def test_cost_is_not_invoice_and_relevance_rejects_not_failure(self):
        self.put(receipt())
        result = audit.snapshot(self.path)
        self.assertTrue(result["cost_is_pinned_price_estimate_not_invoice"])
        self.assertTrue(result["screening_rejections_not_counted_as_full_analysis"])
        self.assertEqual(result["totals"]["articles_queued"], 3)
        self.assertEqual(result["totals"]["articles_fully_analyzed"], 1)

    def test_exact_task_totals_and_task_cost_reconcile(self):
        self.put(receipt())
        result = audit.snapshot(self.path)
        tasks = result["task_model_rollup"]
        self.assertEqual(sum(r["calls"] for r in tasks), 6)
        self.assertEqual(sum(r["succeeded_calls"] for r in tasks), 6)
        self.assertAlmostEqual(sum(r["estimated_cost_usd"] for r in tasks), 0.006)

    def test_duplicate_day_refused_even_when_otherwise_valid(self):
        x = receipt()
        self.put(x, x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError, "duplicate date"):
            audit.snapshot(self.path)

    def test_unsupported_schema_refused(self):
        x = receipt()
        x["schema_version"] = 9
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError, "schema"):
            audit.snapshot(self.path)

    def test_failed_call_not_reconciled_refused(self):
        x = receipt()
        x["failed_calls"] = 1
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError, "calls do not reconcile"):
            audit.snapshot(self.path)

    def test_task_to_run_counter_mismatch_refused(self):
        x = receipt()
        x["input_tokens"] += 1
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError,
                                    "task counters and run"):
            audit.snapshot(self.path)

    def test_duplicate_model_task_receipt_refused(self):
        x = receipt()
        x["tasks"].append(copy.deepcopy(x["tasks"][0]))
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError, "duplicated task"):
            audit.snapshot(self.path)

    def test_task_cost_mismatch_refused(self):
        x = receipt()
        x["estimated_cost_usd"] = 0.5
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError,
                                    "task costs and run cost"):
            audit.snapshot(self.path)

    def test_bad_per_analyzed_cost_refused(self):
        x = receipt()
        x["estimated_cost_per_analyzed_article_usd"] = 0.5
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError,
                                    "cost per fully analyzed"):
            audit.snapshot(self.path)

    def test_zero_fully_analyzed_requires_null_per_article_cost(self):
        x = receipt()
        x["articles_fully_analyzed"] = 0
        x["estimated_cost_per_analyzed_article_usd"] = None
        self.put(x)
        result = audit.snapshot(self.path)
        self.assertIsNone(result["estimated_cost_per_fully_analyzed_usd"])
        x["estimated_cost_per_analyzed_article_usd"] = 0.1
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError,
                                    "must be null"):
            audit.snapshot(self.path)

    def test_unpriced_task_marks_report_incomplete(self):
        x = receipt()
        x["tasks"][1]["estimated_cost_usd"] = None
        x["unpriced_models"] = ["sonnet"]
        # A single model cannot be both priced and unpriced in one record.
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError,
                                    "wrongly declared unpriced"):
            audit.snapshot(self.path)
        for t in x["tasks"]:
            if t["model"] == "sonnet":
                t["estimated_cost_usd"] = None
        x["estimated_cost_usd"] = 0.001
        x["estimated_cost_per_analyzed_article_usd"] = 0.001
        self.put(x)
        result = audit.snapshot(self.path)
        self.assertTrue(result["any_unpriced_models"])

    def test_bad_run_date_and_timezone_refused(self):
        x = receipt()
        x["run_date"] = "2026-13-06"
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError, "run_date"):
            audit.snapshot(self.path)
        x["run_date"] = "2026-10-06"
        x["recorded_at"] = "2026-10-06T12:30:00"
        self.put(x)
        with self.assertRaisesRegex(audit.CapacityEvidenceError, "time zone"):
            audit.snapshot(self.path)

    def test_empty_line_or_broken_json_refused(self):
        self.path.write_text("\n", encoding="utf-8")
        with self.assertRaisesRegex(audit.CapacityEvidenceError, "empty line"):
            audit.snapshot(self.path)
        self.path.write_text("{bad json}", encoding="utf-8")
        with self.assertRaisesRegex(audit.CapacityEvidenceError, "malformed"):
            audit.snapshot(self.path)

    def test_snapshot_input_mutation_refuses_stale_hash(self):
        self.put(receipt())
        real = audit.hashlib.sha256
        with patch.object(audit.hashlib, "sha256", wraps=real) as hasher:
            # The test confirms a successful report anchors the exact contents.
            before = hashlib.sha256(self.path.read_bytes()).hexdigest()
            report = audit.snapshot(self.path)
            self.assertGreaterEqual(hasher.call_count, 2)
            self.assertEqual(report["input_file_sha256"], before)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)

    def test_cli_no_body_or_url_no_network_or_write(self):
        self.put(receipt())
        out = subprocess.run([sys.executable, str(Path(audit.__file__).resolve()),
                              "--usage-jsonl", str(self.path)],
                             text=True, capture_output=True, timeout=20)
        self.assertEqual(out.returncode, 0, out.stderr)
        v = json.loads(out.stdout)
        self.assertEqual(v["recorded_run_dates"], 1)
        self.assertNotIn("text_original", out.stdout)
        self.assertNotIn("article_url", out.stdout)
        self.assertFalse(v["publication_authorized"])
        self.assertEqual(v["model_calls"], 0)
        self.assertEqual(v["writes"], 0)


if __name__ == "__main__":
    unittest.main()
