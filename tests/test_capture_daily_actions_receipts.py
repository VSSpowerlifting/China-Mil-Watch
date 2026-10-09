"""No-network Actions REST capture and offline-classifier trust boundaries."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import capture_daily_actions_receipts as grab
from scripts import audit_daily_run_receipts as audit

DAY = "2026-10-07"


def run(run_id=37671050416, *, time="2026-10-07T18:59:27Z",
        conclusion="cancelled"):
    return {
        "id": run_id,
        "name": audit.WORKFLOW,
        "event": "schedule",
        "run_attempt": 1,
        "status": "completed",
        "conclusion": conclusion,
        "created_at": time,
        "updated_at": "2026-10-07T23:37:25Z",
    }


def job(run_id=37671050416, *, browser="cancelled", pipeline="skipped"):
    core = [
        {"name": "Scheduling guard", "conclusion": "success"},
        {"name": "Install Playwright browser", "conclusion": browser},
        {"name": "Run pipeline", "conclusion": pipeline},
        {"name": "Validate rendered output", "conclusion": "skipped"},
        {"name": "Commit updated database and site output",
         "conclusion": "skipped"},
        {"name": "Deploy to GitHub Pages", "conclusion": "skipped"},
        {"name": "Record successful run", "conclusion": "skipped"},
        {"name": "Health gate", "conclusion": "skipped"},
    ]
    return {
        "id": 112962601539, "run_id": run_id,
        "name": "update", "status": "completed", "steps": core,
    }


def fixture(runs=None, jobs=None, *, total=None):
    run_rows = [run()] if runs is None else runs
    mapping = {} if jobs is None else jobs
    seen = []

    def fake(path, params):
        seen.append((path, dict(params)))
        if path == grab.WORKFLOW_RUNS:
            rows = run_rows[(params["page"] - 1) * 100:params["page"] * 100]
            return {"total_count": len(run_rows) if total is None else total,
                    "workflow_runs": copy.deepcopy(rows)}
        if path.startswith("/actions/runs/") and path.endswith("/jobs"):
            run_id = int(path.split("/")[3])
            rows = mapping.get(run_id, [])
            return {"total_count": len(rows), "jobs": copy.deepcopy(rows)}
        raise AssertionError("Unexpected Actions URL " + path)

    fake.seen = seen
    return fake


class CaptureDailyActions(unittest.TestCase):
    def test_export_cancellation_with_observed_skipped_pipeline(self):
        fake = fixture(jobs={37671050416: [job()]})
        source = grab.capture(DAY, fake, as_of_utc="2026-10-09T04:00:00Z")
        self.assertEqual(source["schema"], audit.SCHEMA)
        self.assertEqual(source["runs"][0]["guard"],
                         {"step_result": "success", "should_run": None})
        self.assertEqual(source["runs"][0]["steps"]["Run pipeline"], "skipped")
        self.assertIsNone(source["runs"][0]["analysis"])
        verdict = audit.interpret(source)
        self.assertEqual(verdict["attempts"][0]["status"],
                         "cancelled_execution_extent_unknown")
        self.assertFalse(verdict["supplied_actions_export_authenticated"])
        self.assertFalse(verdict["production_health_certified"])
        self.assertFalse(verdict["publication_authorized"])
        self.assertEqual(fake.seen[0][0], grab.WORKFLOW_RUNS)

    def test_jobless_cancelled_run_is_not_invented_pipeline_skip(self):
        fake = fixture()
        result = grab.capture(DAY, fake, as_of_utc="2026-10-09T04:00:00Z")
        self.assertEqual(result["runs"][0]["guard"]["step_result"], "unknown")
        self.assertTrue(all(step == "unknown" for step in
                            result["runs"][0]["steps"].values()))
        self.assertEqual(audit.interpret(result)["attempts"][0]["status"],
                         "cancelled_execution_extent_unknown")

    def test_actual_executed_steps_do_not_forge_guard_decision(self):
        row = run(conclusion="success")
        step = job()
        step["steps"][1]["conclusion"] = "success"
        for item in step["steps"]:
            if item["name"] in audit.STEP_NAMES:
                item["conclusion"] = "success"
        result = grab.capture(DAY, fixture(jobs={row["id"]: [step]}),
                              as_of_utc="2026-10-09T04:00:00Z")
        self.assertIsNone(result["runs"][0]["guard"]["should_run"])
        self.assertIsNone(result["runs"][0]["analysis"])
        self.assertEqual(audit.interpret(result)["attempts"][0]["status"],
                         "green_workflow_work_not_established")

    def test_no_run_is_not_an_authenticated_empty_day(self):
        result = grab.capture(DAY, fixture([]), as_of_utc="2026-10-09T04:00:00Z")
        self.assertEqual(result["runs"], [])
        verdict = audit.interpret(result)
        self.assertFalse(verdict["complete_actions_history_established"])
        self.assertFalse(verdict["missing_run_dates_inferred"])

    def test_one_query_per_run_and_utc_day_filter(self):
        rows = [run(100, time="2026-10-07T19:00:00Z"),
                run(101, time="2026-10-07T20:00:00Z")]
        fake = fixture(rows)
        r = grab.capture(DAY, fake, as_of_utc="2026-10-09T04:00:00Z")
        self.assertEqual(len(r["runs"]), 2)
        self.assertEqual(fake.seen[0][1],
                         {"per_page": 100, "page": 1, "created": DAY})
        self.assertEqual(len(fake.seen), 3)
        self.assertEqual(fake.seen[1][0], "/actions/runs/100/jobs")
        self.assertEqual(fake.seen[2][0], "/actions/runs/101/jobs")

    def test_second_page_of_runs_checked(self):
        rows = [run(1000 + i, time="2026-10-07T18:59:27Z")
                for i in range(101)]
        fake = fixture(rows)
        result = grab.capture(DAY, fake, as_of_utc="2026-10-09T04:00:00Z")
        self.assertEqual(len(result["runs"]), 101)
        self.assertEqual(
            [p["page"] for path, p in fake.seen if path == grab.WORKFLOW_RUNS],
            [1, 2])

    def test_partial_page_refused(self):
        fake = fixture([run()], total=2)
        with self.assertRaisesRegex(grab.CaptureError, "incomplete"):
            grab.capture(DAY, fake)

    def test_changing_total_count_between_pages_refused(self):
        rows = [run(1000 + i) for i in range(101)]
        original = fixture(rows)
        def different(path, params):
            result = original(path, params)
            if path == grab.WORKFLOW_RUNS and params["page"] == 2:
                result["total_count"] = 102
            return result
        with self.assertRaisesRegex(grab.CaptureError, "changed during pagination"):
            grab.capture(DAY, different)

    def test_excessive_run_count_refused(self):
        rows = [run(1000 + i) for i in range(201)]
        with self.assertRaisesRegex(grab.CaptureError, "limit exceeded"):
            grab.capture(DAY, fixture(rows))

    def test_duplicate_run_in_pages_refused(self):
        rows = [run(1000 + i) for i in range(100)] + [run(1000)]
        with self.assertRaisesRegex(grab.CaptureError, "duplicated Daily"):
            grab.capture(DAY, fixture(rows))

    def test_incomplete_or_wrong_workflow_refused(self):
        for patch in ({"status": "in_progress"}, {"name": "Singapore Shadow Collection"},
                      {"event": "push"}, {"run_attempt": 0},
                      {"conclusion": None}):
            with self.subTest(patch=patch):
                row = run()
                row.update(patch)
                with self.assertRaises((grab.CaptureError, audit.ReceiptError)):
                    grab.capture(DAY, fixture([row]))

    def test_foreign_day_run_refused(self):
        row = run(time="2026-10-08T01:00:00Z")
        with self.assertRaisesRegex(grab.CaptureError, "outside exact UTC day"):
            grab.capture(DAY, fixture([row]))

    def test_duplicate_critical_job_step_refused(self):
        step = job()
        step["steps"].append({"name": "Run pipeline", "conclusion": "success"})
        with self.assertRaisesRegex(grab.CaptureError, "duplicate guarded"):
            grab.capture(DAY, fixture(jobs={37671050416: [step]}))

    def test_multiple_jobs_fail_review_not_silently_ignored(self):
        fake = fixture(jobs={37671050416: [job(), job()]})
        with self.assertRaisesRegex(grab.CaptureError, "limit exceeded"):
            grab.capture(DAY, fake)

    def test_mismatched_run_to_job_identity_refused(self):
        step = job(run_id=12345)
        with self.assertRaisesRegex(grab.CaptureError, "invalid or unexpected"):
            grab.capture(DAY, fixture(jobs={37671050416: [step]}))

    def test_unknown_stage_outcome_stays_unknown(self):
        step = job()
        step["steps"][2]["conclusion"] = None
        result = grab.capture(DAY, fixture(jobs={37671050416: [step]}),
                              as_of_utc="2026-10-09T04:00:00Z")
        self.assertEqual(result["runs"][0]["steps"]["Run pipeline"], "unknown")

    def test_invalid_day_rejected(self):
        for invalid in ("2026-10-32", "20261007", "2026-10-07T00:00:00Z",
                        "2026-02-29"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(grab.CaptureError):
                    grab.capture(invalid, fixture([]))

    def test_future_day_rejected_before_network(self):
        future = datetime.now(timezone.utc).date().replace(year=2099).isoformat()
        fake = fixture([])
        with self.assertRaisesRegex(grab.CaptureError, "future UTC day"):
            grab.capture(future, fake)
        self.assertEqual(fake.seen, [])

    def test_unsafe_http_endpoint_blocked(self):
        for path in ("https://attacker.test/actions/runs",
                     "/actions/../admin", "/repos/wrong/actions/runs"):
            with self.subTest(path=path):
                with self.assertRaises(grab.CaptureError):
                    grab.transport(path, {"per_page": 100})

    def test_invalid_api_response_structures_refused(self):
        for doc in (None, {}, {"total_count": "1", "workflow_runs": []},
                    {"total_count": 1, "workflow_runs": "not-a-list"}):
            with self.subTest(doc=doc):
                def fake(path, params):
                    return doc
                with self.assertRaises(grab.CaptureError):
                    grab.capture(DAY, fake)

    def test_no_file_writes_or_user_network_for_help(self):
        root = Path(grab.__file__).resolve()
        p = subprocess.run([sys.executable, str(root), "--help"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("--created-utc-day", p.stdout)

    def test_secret_token_never_in_output_fields(self):
        fake = fixture(jobs={37671050416: [job()]})
        result = json.dumps(grab.capture(
            DAY, fake, as_of_utc="2026-10-09T04:00:00Z"))
        self.assertNotIn("Authorization", result)
        self.assertNotIn("Bearer", result)


if __name__ == "__main__":
    unittest.main()
