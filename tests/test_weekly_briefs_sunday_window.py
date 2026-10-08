"""Offline Sunday IPR Briefs handoff date and freshness gates."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from scripts.weekly_briefs_sunday_window import SundayHandoffRefused, resolve_sunday_handoff


def utc(timestamp):
    return datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)


def window(date_time, *, event="schedule", marker="2026-10-11",
           send=True, target="", historical=False, friday=False):
    return resolve_sunday_handoff(
        event=event, now=date_time, reporting_saturday=target,
        send_email=send, allow_historical_send=historical,
        sunday_daily_marker=marker, friday_delivery_enabled=friday,
    )


class SundayHandoffTests(unittest.TestCase):
    def test_sunday_complete_week_and_marker(self):
        r = window(utc("2026-10-11T19:17:00"))
        self.assertEqual(r, {
            "IPR_SUNDAY_WEEK_START": "2026-10-04",
            "IPR_SUNDAY_AS_OF": "2026-10-10",
            "IPR_SUNDAY_WEEK_END": "2026-10-10",
            "IPR_SUNDAY_SHOULD_SEND": "true",
        })

    def test_current_sunday_missing_stale_or_future_marker_blocks(self):
        for marker in ("", "2026-10-10", "2026-10-12"):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(SundayHandoffRefused, "success marker"):
                    window(utc("2026-10-11T19:17:00"), marker=marker)
        with self.assertRaisesRegex(SundayHandoffRefused, "success marker"):
            window(utc("2026-10-11T19:17:00"), marker="",
                   event="workflow_dispatch", send=False)

    def test_delayed_scheduled_job_after_sunday_midnight_refused(self):
        with self.assertRaisesRegex(SundayHandoffRefused, "outside New York-local Sunday"):
            window(utc("2026-10-12T05:30:00"))

    def test_utc_monday_early_is_still_new_york_sunday(self):
        r = window(utc("2026-10-12T02:00:00"))
        self.assertEqual(r["IPR_SUNDAY_AS_OF"], "2026-10-10")

    def test_dual_service_send_refused_but_preview_allowed(self):
        with self.assertRaisesRegex(SundayHandoffRefused, "parallel services"):
            window(utc("2026-10-11T19:17:00"), friday=True)
        r = window(utc("2026-10-11T19:17:00"), friday=True,
                   event="workflow_dispatch", send=False)
        self.assertEqual(r["IPR_SUNDAY_SHOULD_SEND"], "false")

    def test_manual_historical_send_requires_explicit_override(self):
        now = utc("2026-10-15T16:00:00")
        with self.assertRaisesRegex(SundayHandoffRefused, "allow_historical_send"):
            window(now, event="workflow_dispatch", send=True)
        r = window(now, event="workflow_dispatch", send=True,
                   historical=True)
        self.assertEqual(r["IPR_SUNDAY_AS_OF"], "2026-10-10")
        self.assertEqual(r["IPR_SUNDAY_SHOULD_SEND"], "true")

    def test_saturday_is_not_complete_even_with_manual_override(self):
        with self.assertRaisesRegex(SundayHandoffRefused, "has not ended"):
            window(utc("2026-10-10T20:00:00"), event="workflow_dispatch",
                   send=True, historical=True, marker="")

    def test_manual_historical_preview_stays_unsent_and_needs_no_marker(self):
        now = utc("2026-10-15T16:00:00")
        r = window(now, event="workflow_dispatch", send=False, marker="",
                   target="2026-10-03")
        self.assertEqual(r["IPR_SUNDAY_AS_OF"], "2026-10-03")
        self.assertEqual(r["IPR_SUNDAY_SHOULD_SEND"], "false")

    def test_future_wrong_weekday_and_overold_fridays_refused(self):
        now = utc("2026-10-15T16:00:00")
        for target, expected in (
            ("2026-10-17", "future Saturday"),
            ("2026-10-16", "must be a Saturday"),
            ("20261010", "must be a valid YYYY-MM-DD"),
            ("nonsense", "must be a valid"),
            ("2026-06-06", "older than 91 days"),
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(SundayHandoffRefused, expected):
                    window(now, event="workflow_dispatch", send=False, target=target)

    def test_scheduled_replays_and_offday_refused(self):
        now = utc("2026-10-11T19:17:00")
        with self.assertRaisesRegex(SundayHandoffRefused, "historical"):
            window(now, target="2026-10-03")
        with self.assertRaisesRegex(SundayHandoffRefused, "historical"):
            window(now, historical=True)
        with self.assertRaisesRegex(SundayHandoffRefused, "flag"):
            window(now, send=False)
        with self.assertRaisesRegex(SundayHandoffRefused, "unsupported"):
            window(now, event="push")

    def test_spring_and_fall_local_time_not_utc_date(self):
        examples = (
            ("2027-03-21T19:17:00", "2027-03-20", "2027-03-21"),
            ("2027-11-14T19:17:00", "2027-11-13", "2027-11-14"),
        )
        for timestamp, saturday, marker in examples:
            with self.subTest(timestamp=timestamp):
                r = window(utc(timestamp), marker=marker)
                self.assertEqual(r["IPR_SUNDAY_AS_OF"], saturday)

    def test_no_timezone_refused(self):
        with self.assertRaisesRegex(SundayHandoffRefused, "timezone"):
            window(datetime(2026, 10, 11, 14, 0))

    def test_separate_workflow_secret_and_replay_boundary(self):
        project = Path(__file__).resolve().parents[1]
        yaml = (project / ".github" / "workflows" /
                "sunday_briefs_editorial_handoff.yml").read_text(encoding="utf-8")
        friday = (project / ".github" / "workflows" /
                  "weekly_briefs_editorial_handoff.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", yaml)
        self.assertIn("IPR_SUNDAY_EDITOR_DELIVERY_ENABLED", yaml)
        self.assertIn("last_daily_run_date.txt", yaml)
        self.assertIn("IPR_EDITOR_DELIVERY_ENABLED", yaml)
        self.assertIn("vars.IPR_SUNDAY_EDITOR_DELIVERY_ENABLED == 'true'", yaml)
        self.assertIn("python -m scripts.weekly_editorial_handoff", yaml)
        self.assertIn("--full-week", yaml)
        self.assertIn("permissions:\n  contents: read", yaml)
        self.assertNotIn("contents: write", yaml)
        self.assertNotIn("IPR_SUNDAY_EDITOR_DELIVERY_ENABLED", friday)
        self.assertLess(yaml.index("Verify reporting Saturday"),
                        yaml.index("Create read-only full Saturday-ending"))
        self.assertLess(yaml.index("Create read-only full Saturday-ending"),
                        yaml.index("Generate source-cited Sunday manuscript"))


if __name__ == "__main__":
    unittest.main()
