"""No-network seven-day GitHub Actions metadata receipt composition contracts."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scripts import audit_daily_run_receipts as audit
from scripts import capture_daily_actions_receipts as capture
from scripts import capture_daily_actions_window as window
from tests.test_daily_run_receipts import cancelled


NOW = "2026-10-09T23:45:00Z"
DAYS = ("2026-10-07", "2026-10-08", "2026-10-09")


def attempt(day, run_id):
    row = cancelled()
    row["run_id"] = run_id
    row["created_at"] = day + "T18:00:00Z"
    row["updated_at"] = day + "T20:00:00Z"
    return row


def fake_factory(rows_by_day, *, claimed_asof=None, corrupted=None):
    calls = []
    def fake(day, *, as_of_utc):
        calls.append((day, as_of_utc))
        output = {
            "schema": audit.SCHEMA,
            "as_of_utc": claimed_asof or as_of_utc,
            "runs": copy.deepcopy(rows_by_day.get(day, [])),
        }
        if corrupted is not None:
            output = corrupted(day, output)
        return output
    fake.calls = calls
    return fake


class SevenDayMetadataWindow(unittest.TestCase):
    def test_one_date_no_attempts_does_not_claim_no_publications(self):
        fake = fake_factory({})
        raw = window.merge_window("2026-10-07", "2026-10-07",
                                  fetch_day=fake, as_of_utc=NOW)
        self.assertEqual(raw["runs"], [])
        self.assertEqual(fake.calls, [("2026-10-07", NOW)])
        verdict = audit.interpret(raw)
        self.assertFalse(verdict["complete_actions_history_established"])
        self.assertFalse(verdict["no_publications_inferred"])
        self.assertFalse(verdict["publication_authorized"])

    def test_three_days_combine_and_sort_run_evidence(self):
        fake = fake_factory({
            "2026-10-07": [attempt("2026-10-07", 7001)],
            "2026-10-08": [attempt("2026-10-08", 8002),
                           attempt("2026-10-08", 8001)],
            "2026-10-09": [attempt("2026-10-09", 9001)],
        })
        raw = window.merge_window("2026-10-07", "2026-10-09",
                                  fetch_day=fake, as_of_utc=NOW)
        self.assertEqual([r["run_id"] for r in raw["runs"]],
                         [7001, 8001, 8002, 9001])
        self.assertEqual([d for d, _ in fake.calls], list(DAYS))
        self.assertEqual(raw["as_of_utc"], NOW)
        self.assertEqual(audit.interpret(raw)["provided_attempts"], 4)

    def test_all_days_called_even_when_middle_day_has_no_runs(self):
        fake = fake_factory({"2026-10-07": [attempt("2026-10-07", 1)],
                             "2026-10-09": [attempt("2026-10-09", 3)]})
        raw = window.merge_window("2026-10-07", "2026-10-09",
                                  fetch_day=fake, as_of_utc=NOW)
        self.assertEqual([x[0] for x in fake.calls], list(DAYS))
        self.assertEqual(len(raw["runs"]), 2)
        self.assertFalse(audit.interpret(raw)["missing_run_dates_inferred"])

    def test_exactly_seven_utc_days_allowed(self):
        fake = fake_factory({})
        raw = window.merge_window("2026-10-03", "2026-10-09",
                                  fetch_day=fake, as_of_utc=NOW)
        self.assertEqual(len(fake.calls), 7)
        self.assertEqual(raw["runs"], [])

    def test_eight_day_window_refused_before_fetch(self):
        fake = fake_factory({})
        with self.assertRaisesRegex(window.WindowError, "exceeds seven"):
            window.merge_window("2026-10-02", "2026-10-09",
                                fetch_day=fake, as_of_utc=NOW)
        self.assertEqual(fake.calls, [])

    def test_reverse_window_refused_before_fetch(self):
        fake = fake_factory({})
        with self.assertRaisesRegex(window.WindowError, "end precedes start"):
            window.merge_window("2026-10-09", "2026-10-07",
                                fetch_day=fake, as_of_utc=NOW)
        self.assertEqual(fake.calls, [])

    def test_future_day_refused_before_fetch(self):
        future = (datetime.now(timezone.utc).date()
                  + timedelta(days=3)).isoformat()
        fake = fake_factory({})
        with self.assertRaisesRegex(window.WindowError, "future UTC"):
            window.merge_window(future, future,
                                fetch_day=fake)
        self.assertEqual(fake.calls, [])

    def test_malformed_calendar_date_refused_without_fetch(self):
        for invalid in ("2026-02-29", "2026-10-34", "20261009"):
            with self.subTest(invalid=invalid):
                fake = fake_factory({})
                with self.assertRaises(capture.CaptureError):
                    window.merge_window(invalid, "2026-10-09",
                                        fetch_day=fake, as_of_utc=NOW)
                self.assertEqual(fake.calls, [])

    def test_asof_before_window_end_refused_before_fetch(self):
        fake = fake_factory({})
        with self.assertRaisesRegex(window.WindowError, "as-of precedes"):
            window.merge_window("2026-10-07", "2026-10-09",
                                fetch_day=fake,
                                as_of_utc="2026-10-08T23:00:00Z")
        self.assertEqual(fake.calls, [])

    def test_invalid_asof_without_timezone_refused_before_fetch(self):
        fake = fake_factory({})
        with self.assertRaises(audit.ReceiptError):
            window.merge_window("2026-10-07", "2026-10-09",
                                fetch_day=fake, as_of_utc="2026-10-09T23:45:00")
        self.assertEqual(fake.calls, [])

    def test_refuse_missing_middle_day_instead_of_partial_output(self):
        fake = fake_factory({})
        def error(day, *, as_of_utc):
            if day == "2026-10-08":
                raise capture.CaptureError("GitHub 502")
            return fake(day, as_of_utc=as_of_utc)
        with self.assertRaisesRegex(capture.CaptureError, "GitHub 502"):
            window.merge_window("2026-10-07", "2026-10-09",
                                fetch_day=error, as_of_utc=NOW)
        self.assertEqual(fake.calls, [("2026-10-07", NOW)])

    def test_forged_daily_schema_refused(self):
        fake = fake_factory({}, corrupted=lambda day, d:
                            dict(d, schema="ipr-operations-snapshot/1"))
        with self.assertRaisesRegex(window.WindowError, "unexpected schema"):
            window.merge_window("2026-10-07", "2026-10-07",
                                fetch_day=fake, as_of_utc=NOW)

    def test_mismatched_daily_asof_refused(self):
        fake = fake_factory({}, claimed_asof="2026-10-09T20:00:00Z")
        with self.assertRaisesRegex(window.WindowError, "schema or as-of"):
            window.merge_window("2026-10-07", "2026-10-07",
                                fetch_day=fake, as_of_utc=NOW)

    def test_cross_day_misattribution_refused(self):
        fake = fake_factory({"2026-10-07": [attempt("2026-10-08", 77)]})
        with self.assertRaisesRegex(window.WindowError, "wrong UTC capture date"):
            window.merge_window("2026-10-07", "2026-10-07",
                                fetch_day=fake, as_of_utc=NOW)

    def test_reused_run_identity_across_days_refused(self):
        # Corrupt a second day's result to reuse the same identifier; the
        # cross-day UTC check runs first, so use a different creation date.
        fake = fake_factory({"2026-10-07": [attempt("2026-10-07", 17)],
                             "2026-10-08": [attempt("2026-10-08", 17)]})
        with self.assertRaisesRegex(window.WindowError, "duplicate run attempt"):
            window.merge_window("2026-10-07", "2026-10-08",
                                fetch_day=fake, as_of_utc=NOW)

    def test_combined_200_attempt_limit(self):
        fake = fake_factory({
            "2026-10-07": [attempt("2026-10-07", i + 1000) for i in range(100)],
            "2026-10-08": [attempt("2026-10-08", i + 2000) for i in range(100)],
        })
        raw = window.merge_window("2026-10-07", "2026-10-08",
                                  fetch_day=fake, as_of_utc=NOW)
        self.assertEqual(len(raw["runs"]), 200)
        more = fake_factory({
            "2026-10-07": [attempt("2026-10-07", i + 1000) for i in range(100)],
            "2026-10-08": [attempt("2026-10-08", i + 2000) for i in range(101)],
        })
        with self.assertRaisesRegex(window.WindowError, "exceeds 200"):
            window.merge_window("2026-10-07", "2026-10-08",
                                fetch_day=more, as_of_utc=NOW)

    def test_unexpected_run_fields_refused_by_actual_classifier(self):
        bad = attempt("2026-10-07", 171)
        bad["publication_authorized"] = True
        fake = fake_factory({"2026-10-07": [bad]})
        with self.assertRaises(audit.ReceiptError):
            window.merge_window("2026-10-07", "2026-10-07",
                                fetch_day=fake, as_of_utc=NOW)

    def test_no_false_model_queue_or_collection_authority(self):
        fake = fake_factory({"2026-10-08": [attempt("2026-10-08", 808)]})
        raw = window.merge_window("2026-10-08", "2026-10-08",
                                  fetch_day=fake, as_of_utc=NOW)
        verdict = audit.interpret(raw)
        for key in ("supplied_actions_export_authenticated",
                    "complete_actions_history_established",
                    "archive_capture_verified",
                    "analysis_queue_current_state_verified",
                    "production_health_certified",
                    "publication_authorized", "editor_delivery_authorized"):
            self.assertFalse(verdict[key], key)
        self.assertEqual(verdict["supplied_pipeline_backlog_snapshots"], [])

    def test_cli_help_never_fetches_or_writes_repository(self):
        proc = subprocess.run(
            [sys.executable, str(Path(window.__file__).resolve()), "--help"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--from-utc-day", proc.stdout)
        self.assertIn("--through-utc-day", proc.stdout)


if __name__ == "__main__":
    unittest.main()
