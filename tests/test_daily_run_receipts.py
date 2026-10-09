"""Synthetic Daily receipt interpretation, no GitHub/network/provider calls."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import audit_daily_run_receipts as audit

CAPTURE = {
    "new_articles_stored": 46,
    "queue_total": 324,
    "queue_new": 42,
    "queue_backlog": 282,
    "daily_analysis_cap": 55,
    "backlog_after_cap": 266,
    "deferred_new": 3,
}


def complete(run_id=37827949547, created="2026-10-08T18:54:55Z"):
    return {
        "run_id": run_id, "attempt": 1, "workflow": audit.WORKFLOW,
        "event": "schedule", "status": "completed", "conclusion": "success",
        "created_at": created, "updated_at": "2026-10-08T20:00:00Z",
        "guard": {"step_result": "success", "should_run": True},
        "steps": {key: "success" for key in audit.STEP_NAMES},
        "analysis": dict(CAPTURE),
    }


def guard_only():
    row = complete(run_id=37836092547, created="2026-10-08T19:59:46Z")
    row["updated_at"] = "2026-10-08T20:05:00Z"
    row["guard"]["should_run"] = False
    row["steps"] = {key: "skipped" for key in audit.STEP_NAMES}
    row["analysis"] = None
    return row


def cancelled():
    row = complete(run_id=37678868237,
                   created="2026-10-07T20:01:15Z")
    row["updated_at"] = "2026-10-07T20:11:15Z"
    row["conclusion"] = "cancelled"
    row["guard"] = {"step_result": "skipped", "should_run": None}
    row["steps"] = {key: "unknown" for key in audit.STEP_NAMES}
    row["analysis"] = None
    return row


def envelope(runs=None):
    return {
        "schema": audit.SCHEMA, "as_of_utc": "2026-10-09T03:00:00Z",
        "runs": [complete()] if runs is None else runs,
    }


class DailyReceipts(unittest.TestCase):
    def classify(self, rows=None):
        return audit.interpret(envelope(rows))

    def test_completed_pipeline_is_candidate_not_authenticated_production(self):
        result = self.classify()
        self.assertEqual(result["attempts"][0]["status"],
                         "collection_validation_deploy_candidate")
        self.assertFalse(result["archive_capture_verified"])
        self.assertFalse(result["production_health_certified"])
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["editor_delivery_authorized"])
        self.assertEqual(result["writes"], 0)

    def test_october_eight_backlog_metrics_not_conflated_with_stored(self):
        report = self.classify()
        b = report["supplied_pipeline_backlog_snapshots"][0]
        self.assertEqual(b["new_articles_stored"], 46)
        self.assertEqual(b["backlog_after_cap"], 266)
        self.assertEqual(b["daily_analysis_cap"], 55)
        self.assertEqual(report["attempts"][0]["analysis_log_metrics_supplied"]["queue_new"], 42)
        self.assertFalse(report["analysis_queue_current_state_verified"])

    def test_guard_only_green_is_not_second_collection(self):
        report = self.classify([complete(), guard_only()])
        classifications = {r["run_id"]: r["status"] for r in report["attempts"]}
        self.assertEqual(classifications[37836092547],
                         "green_scheduling_guard_skip_candidate")
        self.assertEqual(len(report["supplied_pipeline_backlog_snapshots"]), 1)

    def test_cancelled_run_is_not_automatically_missed_collection(self):
        report = self.classify([cancelled()])
        self.assertEqual(report["attempts"][0]["status"],
                         "cancelled_execution_extent_unknown")
        self.assertFalse(report["missing_run_dates_inferred"])
        self.assertFalse(report["complete_actions_history_established"])

    def test_cancelled_run_with_pipeline_evidence_stays_ambiguous(self):
        row = cancelled()
        row["steps"]["Run pipeline"] = "success"
        self.assertEqual(self.classify([row])["attempts"][0]["status"],
                         "cancelled_execution_extent_unknown")

    def test_cancelled_during_preflight_with_pipeline_skipped(self):
        row = cancelled()
        row["guard"] = {"step_result": "success", "should_run": True}
        row["steps"] = {key: "skipped" for key in audit.STEP_NAMES}
        result = self.classify([row])
        self.assertEqual(result["attempts"][0]["status"],
                         "cancelled_pipeline_step_skipped_candidate")
        self.assertFalse(result["attempts"][0]["collection_executed_authenticated"])
        self.assertFalse(result["missing_run_dates_inferred"])

    def test_cancelled_run_pipeline_unknown_stays_unresolved(self):
        row = cancelled()
        row["guard"] = {"step_result": "success", "should_run": True}
        row["steps"]["Run pipeline"] = "unknown"
        self.assertEqual(self.classify([row])["attempts"][0]["status"],
                         "cancelled_execution_extent_unknown")

    def test_workflow_failure_on_pipeline_is_not_source_silence(self):
        row = complete()
        row["conclusion"] = "failure"
        row["steps"]["Run pipeline"] = "failure"
        row["steps"]["Validate rendered output"] = "skipped"
        row["steps"]["Deploy to GitHub Pages"] = "skipped"
        result = self.classify([row])
        self.assertEqual(result["attempts"][0]["status"],
                         "pipeline_failed_attempt")
        self.assertFalse(result["no_publications_inferred"])

    def test_postdeploy_health_gate_failure_does_not_erase_deploy(self):
        row = complete()
        row["conclusion"] = "failure"
        row["steps"]["Health gate"] = "failure"
        self.assertEqual(self.classify([row])["attempts"][0]["status"],
                         "post_deploy_health_gate_failed")

    def test_unverified_successful_wrapper_not_called_collection(self):
        row = complete()
        row["guard"]["should_run"] = None
        self.assertEqual(self.classify([row])["attempts"][0]["status"],
                         "green_workflow_work_not_established")

    def test_missing_successful_pipeline_step_is_not_full_run(self):
        row = complete()
        row["steps"]["Run pipeline"] = "unknown"
        row["analysis"] = None
        self.assertEqual(self.classify([row])["attempts"][0]["status"],
                         "green_workflow_work_not_established")

    def test_green_guard_skip_with_unknown_steps_is_not_verified_skip(self):
        row = guard_only()
        row["steps"]["Deploy to GitHub Pages"] = "unknown"
        self.assertEqual(self.classify([row])["attempts"][0]["status"],
                         "green_workflow_work_not_established")

    def test_guard_skip_cannot_claim_successful_deploy(self):
        row = guard_only()
        row["steps"]["Deploy to GitHub Pages"] = "success"
        with self.assertRaisesRegex(audit.ReceiptError, "guard-only skip conflicts"):
            self.classify([row])

    def test_claimed_guard_decision_needs_successful_guard(self):
        row = complete()
        row["guard"]["step_result"] = "failure"
        with self.assertRaisesRegex(audit.ReceiptError, "without completed guard"):
            self.classify([row])

    def test_metrics_require_pipeline_step_evidence(self):
        row = complete()
        row["steps"]["Run pipeline"] = "unknown"
        with self.assertRaisesRegex(audit.ReceiptError, "non-executed"):
            self.classify([row])

    def test_queue_components_must_add_up(self):
        row = complete()
        row["analysis"]["queue_backlog"] = 281
        with self.assertRaisesRegex(audit.ReceiptError, "queue components"):
            self.classify([row])

    def test_backlog_after_must_fit_original_queue(self):
        row = complete()
        row["analysis"]["backlog_after_cap"] = 325
        with self.assertRaisesRegex(audit.ReceiptError, "impossible post-cap"):
            self.classify([row])

    def test_stored_articles_may_exceed_queue_new_candidates(self):
        row = complete()
        row["analysis"]["new_articles_stored"] = 60
        # Stored articles and LLM-eligible candidates are different metrics.
        self.assertEqual(self.classify([row])["attempts"][0]["status"],
                         "collection_validation_deploy_candidate")

    def test_negative_or_boolean_metrics_refused(self):
        for patch in ({"backlog_after_cap": -1}, {"daily_analysis_cap": 0},
                      {"deferred_new": True}):
            with self.subTest(patch=patch):
                row = complete()
                row["analysis"].update(patch)
                with self.assertRaises(audit.ReceiptError):
                    self.classify([row])

    def test_duplicate_run_attempt_rejected(self):
        with self.assertRaisesRegex(audit.ReceiptError, "duplicate Actions"):
            self.classify([complete(), copy.deepcopy(complete())])

    def test_distinct_attempts_not_conflated(self):
        one = complete()
        two = copy.deepcopy(one)
        two["attempt"] = 2
        self.assertEqual(self.classify([one, two])["provided_attempts"], 2)

    def test_wrong_workflow_cannot_be_counted_as_daily(self):
        row = complete()
        row["workflow"] = "Singapore Shadow Collection"
        with self.assertRaisesRegex(audit.ReceiptError, "unrecognized Daily"):
            self.classify([row])

    def test_impossible_local_and_future_timestamp_refused(self):
        for change in ({"created_at": "2026-10-08T19:00:00"},
                       {"updated_at": "2026-10-10T23:00:00Z"},
                       {"updated_at": "2026-10-07T00:00:00Z"}):
            with self.subTest(change=change):
                row = complete()
                row.update(change)
                with self.assertRaises(audit.ReceiptError):
                    self.classify([row])

    def test_new_york_day_not_assumed_utc_day(self):
        row = complete(created="2026-10-09T01:00:00Z")
        row["updated_at"] = "2026-10-09T01:30:00Z"
        result = self.classify([row])["attempts"][0]
        self.assertEqual(result["created_utc_date"], "2026-10-09")
        self.assertEqual(result["created_new_york_date"], "2026-10-08")

    def test_cancelled_october_seven_does_not_imply_daily_absence(self):
        rows = []
        for n in (37671050416, 37671821866, 37674022650,
                  37675691246, 37678868237):
            row = cancelled()
            row["run_id"] = n
            rows.append(row)
        report = self.classify(rows)
        self.assertEqual(
            report["created_ny_day_counts"]["2026-10-07"]
                  ["cancelled_execution_extent_unknown"], 5)
        self.assertFalse(report["missing_run_dates_inferred"])

    def test_empty_list_is_not_proof_nothing_ran(self):
        report = self.classify([])
        self.assertEqual(report["provided_attempts"], 0)
        self.assertEqual(report["created_ny_day_counts"], {})
        self.assertFalse(report["complete_actions_history_established"])

    def test_cli_json_output_and_no_input_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            payload = json.dumps(envelope([complete(), guard_only()]))
            path.write_text(payload, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(Path(audit.__file__).resolve()), str(path)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            loaded = json.loads(proc.stdout)
            self.assertEqual(loaded["provided_attempts"], 2)
            self.assertFalse(loaded["supplied_actions_export_authenticated"])
            self.assertEqual(path.read_text(encoding="utf-8"), payload)


if __name__ == "__main__":
    unittest.main()
