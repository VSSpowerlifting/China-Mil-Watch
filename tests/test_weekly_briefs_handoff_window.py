"""Offline tests for Friday Briefs editorial handoff reporting-window gates."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from scripts.weekly_briefs_handoff_window import (
    ReportingWindowRefused, resolve_handoff_window,
)


def utc(value: str):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


class HandoffWindowTests(unittest.TestCase):
    def test_scheduled_current_friday_uses_sunday_through_friday(self):
        window = resolve_handoff_window(
            event="schedule", now=utc("2026-10-09T20:17:00"),
            sending_email=True,
        )
        self.assertEqual(window, {
            "IPR_EDITOR_WEEK_START": "2026-10-04",
            "IPR_EDITOR_AS_OF": "2026-10-09",
            "IPR_EDITOR_WEEK_END": "2026-10-10",
        })

    def test_scheduled_friday_crossing_midnight_utc_still_local_friday(self):
        # 01:30 UTC Saturday is still 21:30 Eastern Friday.
        result = resolve_handoff_window(
            event="schedule", now=utc("2026-10-10T01:30:00"),
            sending_email=True,
        )
        self.assertEqual(result["IPR_EDITOR_AS_OF"], "2026-10-09")

    def test_delayed_scheduled_runner_after_local_midnight_refused(self):
        with self.assertRaisesRegex(ReportingWindowRefused, "outside local Friday"):
            resolve_handoff_window(
                event="schedule", now=utc("2026-10-10T05:00:00"),
                sending_email=True,
            )

    def test_scheduled_offday_refused_even_without_email(self):
        with self.assertRaisesRegex(ReportingWindowRefused, "outside local Friday"):
            resolve_handoff_window(event="schedule",
                                   now=utc("2026-10-12T20:17:00"))

    def test_manual_preview_defaults_to_last_reached_friday(self):
        result = resolve_handoff_window(
            event="workflow_dispatch", now=utc("2026-10-08T04:15:00"),
        )
        self.assertEqual(result["IPR_EDITOR_AS_OF"], "2026-10-02")

    def test_manual_email_for_old_friday_needs_explicit_replay(self):
        when = utc("2026-10-08T04:15:00")
        with self.assertRaisesRegex(ReportingWindowRefused,
                                    "allow_historical_send"):
            resolve_handoff_window(event="workflow_dispatch", now=when,
                                   sending_email=True)
        result = resolve_handoff_window(event="workflow_dispatch", now=when,
                                        sending_email=True,
                                        allow_historical_send=True)
        self.assertEqual(result["IPR_EDITOR_AS_OF"], "2026-10-02")

    def test_manual_email_on_friday_does_not_need_historical_override(self):
        result = resolve_handoff_window(
            event="workflow_dispatch", now=utc("2026-10-09T20:17:00"),
            sending_email=True,
        )
        self.assertEqual(result["IPR_EDITOR_AS_OF"], "2026-10-09")

    def test_explicit_manual_past_week_preview_and_send(self):
        now = utc("2026-10-16T18:00:00")
        preview = resolve_handoff_window(
            event="workflow_dispatch", now=now, reporting_friday="2026-10-02",
        )
        self.assertEqual(preview["IPR_EDITOR_AS_OF"], "2026-10-02")
        with self.assertRaisesRegex(ReportingWindowRefused,
                                    "allow_historical_send"):
            resolve_handoff_window(event="workflow_dispatch", now=now,
                                   reporting_friday="2026-10-02",
                                   sending_email=True)

    def test_future_invalid_and_overly_old_fridays_refused(self):
        now = utc("2026-10-08T18:00:00")
        for value, expected in (
            ("2026-10-09", "future Friday"),
            ("2026-10-08", "must identify a Friday"),
            ("20261002", "must identify a Friday"),
            ("not-a-date", "must be a valid"),
            ("2026-01-02", "beyond 91 days"),
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ReportingWindowRefused, expected):
                    resolve_handoff_window(event="workflow_dispatch", now=now,
                                           reporting_friday=value)

    def test_scheduled_overrides_refused(self):
        when = utc("2026-10-09T20:17:00")
        for options in (
            {"reporting_friday": "2026-10-02"},
            {"allow_historical_send": True},
        ):
            with self.assertRaisesRegex(ReportingWindowRefused,
                                        "cannot override"):
                resolve_handoff_window(event="schedule", now=when,
                                       **options)

    def test_spring_daylight_saving_and_fall_standard_time(self):
        for value, date_str in (
            ("2027-03-19T20:17:00", "2027-03-19"),
            ("2027-11-12T20:17:00", "2027-11-12"),
        ):
            with self.subTest(value=value):
                result = resolve_handoff_window(event="schedule",
                                                now=utc(value))
                self.assertEqual(result["IPR_EDITOR_AS_OF"], date_str)

    def test_time_must_be_aware_and_event_supported(self):
        with self.assertRaisesRegex(ReportingWindowRefused, "timezone"):
            resolve_handoff_window(event="schedule",
                                   now=datetime(2026, 10, 9, 16, 17))
        with self.assertRaisesRegex(ReportingWindowRefused,
                                    "unsupported GitHub"):
            resolve_handoff_window(event="pull_request",
                                   now=utc("2026-10-09T20:17:00"))

    def test_workflow_has_single_delivery_boolean_for_guard_and_send(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/weekly_briefs_editorial_handoff.yml"
                    ).read_text(encoding="utf-8")
        self.assertEqual(workflow.count("SHOULD_SEND: " + "$" + "{{"), 1)
        self.assertIn('sending_email=os.environ["SHOULD_SEND"] == "true"',
                      workflow)
        self.assertIn('if [[ "$SHOULD_SEND" == "true" ]]; then',
                      workflow)
        self.assertIn("inputs.allow_historical_send == true", workflow)
        self.assertIn("inputs.reporting_friday || ''", workflow)
        self.assertIn("from scripts.weekly_briefs_handoff_window import resolve_handoff_window",
                      workflow)
        self.assertLess(workflow.index("Resolve guarded New York Friday"),
                        workflow.index("Create read-only Friday-bounded source scaffold"))


if __name__ == "__main__":
    unittest.main()
