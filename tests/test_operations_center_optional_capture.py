"""Explicit opt-in Actions capture; default unified Operations Center stays offline."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.desk_registry import load_registry
from scripts import capture_daily_actions_receipts as capture
from scripts import operations_center_unified as unified
from tests.test_capture_daily_actions_receipts import fixture, job, run
from tests.test_daily_run_receipts import cancelled, envelope


class OptionalDailyActionsContracts(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="ipr-ops-capture-optin-")
        self.addCleanup(folder.cleanup)
        self.temp = Path(folder.name)
        self.registry = load_registry()
        self.production = {"sources": [], "per_source_history_available": True,
                           "generated_at": "2026-10-09 01:00:00"}
        for desk in self.registry:
            if not desk.is_collecting:
                continue
            for source in desk.sources:
                self.production["sources"].append({
                    "desk_id": desk.slug, "source_slug": source.slug,
                    "articles_total": 1,
                    "last_article_date": "2026-10-08",
                    "last_successful_collection_at": "2026-10-08 13:00:00",
                    "silence_verdict": "within_cadence",
                    "config_health": "ok",
                    "latest_run_result": {"status": "ok", "is_failure": 0},
                })

    def paths(self):
        return self.temp / "ops.json", self.temp / "ops.html"

    def invoke(self, *args):
        output, html = self.paths()
        with patch.object(unified, "build_report", return_value=self.production):
            return unified.main([
                "--as-of", "2026-10-09", "--json", str(output),
                "--html", str(html), *args,
            ])

    def test_new_york_day_differs_from_utc_date_at_evening_cutover(self):
        utc = datetime(2026, 10, 10, 1, 30, tzinfo=timezone.utc)
        self.assertEqual("2026-10-09", unified.current_display_date(utc))
        self.assertEqual("2026-10-10",
                         unified.current_display_date(datetime(
                             2026, 10, 10, 5, 30, tzinfo=timezone.utc)))

    def test_new_york_default_handles_dst_and_refuses_naive_instant(self):
        self.assertEqual("2026-03-07",
                         unified.current_display_date(datetime(
                             2026, 3, 8, 4, 59, tzinfo=timezone.utc)))
        self.assertEqual("2026-03-08",
                         unified.current_display_date(datetime(
                             2026, 3, 8, 7, 1, tzinfo=timezone.utc)))
        with self.assertRaisesRegex(unified.UnifiedError, "explicit timezone"):
            unified.current_display_date(datetime(2026, 10, 9, 1, 0))

    def test_default_cli_avoids_github_even_when_token_configured(self):
        with patch.object(unified.capture, "capture",
                          side_effect=AssertionError("unexpected network")) as api:
            self.assertEqual(self.invoke(), 0)
        api.assert_not_called()
        output, html = self.paths()
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertNotIn("daily_actions_evidence", report)
        self.assertIn("Shadow collection evidence candidates",
                      html.read_text(encoding="utf-8"))

    def test_explicit_fetch_uses_real_metadata_shape_and_stays_unverified(self):
        raw = capture.capture(
            "2026-10-07",
            fixture([run()], jobs={37671050416: [job()]}),
            as_of_utc="2026-10-09T03:00:00Z",
        )
        with patch.object(unified.capture, "capture", return_value=raw) as api:
            self.assertEqual(self.invoke("--fetch-daily-utc-day",
                                         "2026-10-07"), 0)
        api.assert_called_once_with("2026-10-07")
        output, html = self.paths()
        report = json.loads(output.read_text(encoding="utf-8"))
        daily = report["daily_actions_evidence"]
        self.assertEqual(daily["supplied_attempt_count"], 1)
        self.assertEqual(daily["attempts"][0]["status"],
                         "cancelled_execution_extent_unknown")
        self.assertFalse(daily["input_origin_authenticated"])
        self.assertFalse(daily["collector_work_certified"])
        self.assertFalse(report["publication_authorized"])
        self.assertFalse(report["editor_delivery_authorized"])
        self.assertIn("NOT authenticated",
                      html.read_text(encoding="utf-8"))

    def test_fetch_unknown_green_guard_must_not_be_certified(self):
        row = run(conclusion="success")
        j = job()
        for step in j["steps"]:
            if step["name"] in capture.audit.STEP_NAMES:
                step["conclusion"] = "success"
        raw = capture.capture(
            "2026-10-07", fixture([row], jobs={row["id"]: [j]}),
            as_of_utc="2026-10-09T03:00:00Z",
        )
        with patch.object(unified.capture, "capture", return_value=raw):
            self.assertEqual(self.invoke("--fetch-daily-utc-day",
                                         "2026-10-07"), 0)
        report = json.loads(self.paths()[0].read_text(encoding="utf-8"))
        self.assertEqual(report["daily_actions_evidence"]["attempts"][0]["status"],
                         "green_workflow_work_not_established")
        self.assertFalse(report["daily_actions_evidence"]["collector_work_certified"])

    def test_no_network_when_existing_file_selected(self):
        path = self.temp / "operator-receipt.json"
        original = json.dumps(envelope([cancelled()]))
        path.write_text(original, encoding="utf-8")
        with patch.object(unified.capture, "capture",
                          side_effect=AssertionError("unexpected fetch")) as api:
            self.assertEqual(self.invoke("--daily-receipts", str(path)), 0)
        api.assert_not_called()
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        report = json.loads(self.paths()[0].read_text(encoding="utf-8"))
        self.assertEqual(report["daily_actions_evidence"]["supplied_attempt_count"], 1)

    def test_file_and_network_options_mutually_exclusive(self):
        path = self.temp / "operator.json"
        path.write_text("{}", encoding="utf-8")
        with patch.object(unified.capture, "capture") as api:
            with self.assertRaises(SystemExit):
                self.invoke("--daily-receipts", str(path),
                            "--fetch-daily-utc-day", "2026-10-07")
        api.assert_not_called()
        self.assertFalse(self.paths()[0].exists())
        self.assertFalse(self.paths()[1].exists())

    def test_fetch_failure_does_not_write_any_output(self):
        with patch.object(unified.capture, "capture",
                          side_effect=capture.CaptureError("bad API response")) as api:
            with self.assertRaises(SystemExit):
                self.invoke("--fetch-daily-utc-day", "2026-10-07")
        api.assert_called_once()
        self.assertFalse(self.paths()[0].exists())
        self.assertFalse(self.paths()[1].exists())

    def test_report_pair_new_external_files_created(self):
        output, html = self.paths()
        unified.write_report_pair(output, '{"status":"candidate"}', html,
                                  "<h1>Offline evidence</h1>")
        self.assertEqual(output.read_text(), '{"status":"candidate"}')
        self.assertIn("Offline evidence", html.read_text())

    def test_existing_second_report_not_overwritten_and_first_rolled_back(self):
        output, html = self.paths()
        html.write_text("Original report", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            unified.write_report_pair(output, '{"evidence":true}', html,
                                      "replacement")
        self.assertFalse(output.exists())
        self.assertEqual(html.read_text(encoding="utf-8"), "Original report")

    def test_second_report_io_failure_rolls_back_first(self):
        output, html = self.paths()
        original_open = Path.open

        def fail_html_open(path, *args, **kwargs):
            if path == html:
                raise OSError("synthetic second-report disk failure")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", autospec=True,
                          side_effect=fail_html_open):
            with self.assertRaisesRegex(OSError, "synthetic second-report"):
                unified.write_report_pair(output, '{"test":true}', html, "html")
        self.assertFalse(output.exists())
        self.assertFalse(html.exists())

    def test_future_display_receipt_fails_closed_without_output(self):
        bad = envelope([cancelled()])
        bad["runs"][0]["created_at"] = "2026-10-10T10:00:00Z"
        bad["runs"][0]["updated_at"] = "2026-10-10T11:00:00Z"
        bad["as_of_utc"] = "2026-10-10T12:00:00Z"
        with patch.object(unified.capture, "capture", return_value=bad):
            with self.assertRaises(SystemExit):
                self.invoke("--fetch-daily-utc-day", "2026-10-10")
        self.assertFalse(self.paths()[0].exists())
        self.assertFalse(self.paths()[1].exists())


if __name__ == "__main__":
    unittest.main()
