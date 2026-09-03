"""
The logical collection date of a shadow run.

Both real boundary cases below came out of the Singapore Day 7 and Day 14
checkpoint reviews and are preserved in the published review evidence on
`review/singapore-mindef`. They are the reason this resolver exists, so they
are pinned here as data rather than described in prose.
"""

from __future__ import annotations

import re
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.shadow_schedule import (
    SOURCE_EXPLICIT, SOURCE_MANUAL, SOURCE_SCHEDULE, ScheduleError,
    parse_cron_utc, parse_iso_date, resolve_target_date, scheduled_slot_date)

REPO_ROOT = Path(__file__).resolve().parent.parent
SG_CRON = "21:10"
JP_CRON = "22:40"


def utc(text):
    return datetime.fromisoformat(text)


class TestTheTwoRealDelayedRuns(unittest.TestCase):
    """The observed failures, as recorded by GitHub Actions."""

    def test_run_33027905549_belongs_to_2026_08_26(self):
        # created 2026-08-27T00:45:40Z; stamped 2026-08-27; nominal 2026-08-26
        self.assertEqual(
            resolve_target_date(utc("2026-08-27T00:45:40+00:00"), "schedule", SG_CRON),
            (date(2026, 8, 26), SOURCE_SCHEDULE))

    def test_run_33455386368_belongs_to_2026_08_31(self):
        # created 2026-09-01T00:35:45Z; stamped 2026-09-01; nominal 2026-08-31
        self.assertEqual(
            resolve_target_date(utc("2026-09-01T00:35:45+00:00"), "schedule", SG_CRON),
            (date(2026, 8, 31), SOURCE_SCHEDULE))

    def test_the_delayed_run_and_the_next_on_time_run_differ(self):
        """
        The property that stops two ledgers sharing one date. Before the fix
        both 33455386368 (00:35 on 09-01) and 33570252031 (23:16 on 09-01)
        stamped 2026-09-01.
        """
        delayed, _ = resolve_target_date(
            utc("2026-09-01T00:35:45+00:00"), "schedule", SG_CRON)
        on_time, _ = resolve_target_date(
            utc("2026-09-01T23:16:19+00:00"), "schedule", SG_CRON)
        self.assertEqual(delayed, date(2026, 8, 31))
        self.assertEqual(on_time, date(2026, 9, 1))
        self.assertNotEqual(delayed, on_time)

    def test_a_run_delayed_eight_hours_still_lands_on_its_own_slot(self):
        # run 33144486791, created 2026-08-28T05:20:55Z
        self.assertEqual(
            resolve_target_date(utc("2026-08-28T05:20:55+00:00"), "schedule", SG_CRON)[0],
            date(2026, 8, 27))

    def test_the_repaired_sequence_has_no_duplicate_and_no_gap(self):
        """Every real Singapore run from 08-24 to 09-02, in order."""
        started = ["2026-08-24T21:41:24+00:00", "2026-08-25T21:40:14+00:00",
                   "2026-08-27T00:45:40+00:00", "2026-08-28T05:20:55+00:00",
                   "2026-08-29T03:08:52+00:00", "2026-08-29T23:15:44+00:00",
                   "2026-08-30T23:27:04+00:00", "2026-09-01T00:35:45+00:00",
                   "2026-09-01T23:16:19+00:00", "2026-09-02T23:17:09+00:00"]
        got = [resolve_target_date(utc(s), "schedule", SG_CRON)[0] for s in started]
        self.assertEqual(got, sorted(got), "logical dates must be non-decreasing")
        self.assertEqual(len(set(got)), len(got), "no two runs share a logical date")
        self.assertEqual(got[0], date(2026, 8, 24))
        self.assertEqual(got[-1], date(2026, 9, 2))
        # a contiguous run of days: exactly one per calendar day, no hole
        self.assertEqual(
            got, [date(2026, 8, 24) + timedelta(days=i) for i in range(len(got))])


class TestSlotBoundary(unittest.TestCase):

    def test_before_the_cron_time_after_utc_midnight(self):
        self.assertEqual(
            scheduled_slot_date(utc("2026-09-03T00:00:01+00:00"), SG_CRON),
            date(2026, 9, 2))

    def test_one_minute_before_the_boundary(self):
        self.assertEqual(
            scheduled_slot_date(utc("2026-09-03T21:09:59+00:00"), SG_CRON),
            date(2026, 9, 2))

    def test_exactly_at_the_boundary_is_the_same_day(self):
        self.assertEqual(
            scheduled_slot_date(utc("2026-09-03T21:10:00+00:00"), SG_CRON),
            date(2026, 9, 3))

    def test_after_the_boundary_is_the_same_day(self):
        self.assertEqual(
            scheduled_slot_date(utc("2026-09-03T21:10:01+00:00"), SG_CRON),
            date(2026, 9, 3))

    def test_a_non_utc_offset_is_converted_not_assumed(self):
        # 2026-09-03T09:45+09:00 is 2026-09-03T00:45Z — before the slot.
        self.assertEqual(
            scheduled_slot_date(
                datetime.fromisoformat("2026-09-03T09:45:00+09:00"), SG_CRON),
            date(2026, 9, 2))


class TestJapanIsAffectedTheSameWay(unittest.TestCase):
    """22:40 UTC is eighty minutes from midnight — the more exposed cron."""

    def test_a_delayed_japan_run_belongs_to_the_previous_day(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-03T00:12:00+00:00"), "schedule", JP_CRON),
            (date(2026, 9, 2), SOURCE_SCHEDULE))

    def test_an_on_time_japan_run_keeps_its_own_day(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-02T22:41:30+00:00"), "schedule", JP_CRON),
            (date(2026, 9, 2), SOURCE_SCHEDULE))

    def test_consecutive_delayed_then_on_time_japan_runs_differ(self):
        a, _ = resolve_target_date(utc("2026-09-03T00:12:00+00:00"), "schedule", JP_CRON)
        b, _ = resolve_target_date(utc("2026-09-03T22:45:00+00:00"), "schedule", JP_CRON)
        self.assertNotEqual(a, b)


class TestManualDispatchCannotMasqueradeAsASlot(unittest.TestCase):

    def test_manual_dispatch_records_the_actual_utc_date(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-03T00:45:00+00:00"),
                                "workflow_dispatch", SG_CRON),
            (date(2026, 9, 3), SOURCE_MANUAL))

    def test_manual_dispatch_does_not_borrow_the_previous_slot(self):
        """A hand-started run at 00:45 is not yesterday's scheduled run."""
        manual, _ = resolve_target_date(
            utc("2026-09-03T00:45:00+00:00"), "workflow_dispatch", SG_CRON)
        scheduled, _ = resolve_target_date(
            utc("2026-09-03T00:45:00+00:00"), "schedule", SG_CRON)
        self.assertNotEqual(manual, scheduled)

    def test_no_event_name_is_treated_as_manual(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-03T00:45:00+00:00"), None, SG_CRON)[1],
            SOURCE_MANUAL)

    def test_an_explicit_date_always_wins_and_says_so(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-03T00:45:00+00:00"), "schedule",
                                SG_CRON, "2026-07-04"),
            (date(2026, 7, 4), SOURCE_EXPLICIT))


class TestFailClosed(unittest.TestCase):

    def test_a_scheduled_run_without_a_cron_time_is_refused(self):
        """The old fallthrough is the bug; it must not be reachable silently."""
        with self.assertRaises(ScheduleError):
            resolve_target_date(utc("2026-09-03T00:45:00+00:00"), "schedule", None)

    def test_a_naive_timestamp_is_refused(self):
        with self.assertRaises(ScheduleError):
            resolve_target_date(datetime(2026, 9, 3, 0, 45), "schedule", SG_CRON)

    def test_a_malformed_explicit_date_is_refused(self):
        for bad in ("2026-9-3", "03-09-2026", "20260903", "yesterday", "", "  "):
            with self.subTest(bad=bad):
                with self.assertRaises(ScheduleError):
                    parse_iso_date(bad)

    def test_an_impossible_explicit_date_is_refused(self):
        with self.assertRaises(ScheduleError):
            parse_iso_date("2026-02-30")

    def test_a_malformed_cron_time_is_refused(self):
        for bad in ("24:00", "21:60", "9:10", "2110", "21:10:00", "", None):
            with self.subTest(bad=bad):
                with self.assertRaises(ScheduleError):
                    parse_cron_utc(bad)

    def test_a_valid_cron_time_parses(self):
        self.assertEqual(parse_cron_utc("21:10"), (21, 10))
        self.assertEqual(parse_cron_utc("00:00"), (0, 0))
        self.assertEqual(parse_cron_utc("23:59"), (23, 59))


class TestWorkflowsAgreeWithTheirCollectors(unittest.TestCase):
    """
    The cron in the YAML and the --cron-utc passed to the collector are two
    copies of one fact. A test is what keeps them equal.
    """

    CASES = (("singapore_shadow.yml", "shadow_collect.py"),
             ("japan_shadow.yml", "shadow_collect_japan.py"))

    def workflow(self, name):
        return (REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_each_workflow_passes_its_own_cron_time(self):
        for wf, script in self.CASES:
            with self.subTest(workflow=wf):
                text = self.workflow(wf)
                crons = re.findall(r"- cron:\s*'(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*'", text)
                self.assertEqual(len(crons), 1, "expected exactly one cron in %s" % wf)
                minute, hour = crons[0]
                passed = re.findall(r'--cron-utc\s+"(\d{2}):(\d{2})"', text)
                self.assertEqual(len(passed), 1, "expected one --cron-utc in %s" % wf)
                self.assertEqual((int(passed[0][0]), int(passed[0][1])),
                                 (int(hour), int(minute)),
                                 "%s cron and --cron-utc disagree" % wf)

    def test_each_workflow_passes_the_event_name(self):
        for wf, _ in self.CASES:
            with self.subTest(workflow=wf):
                self.assertIn('--event-name "${GITHUB_EVENT_NAME}"', self.workflow(wf))

    def test_neither_workflow_pins_an_explicit_target_date(self):
        """A hard-coded date would defeat the resolver entirely."""
        for wf, _ in self.CASES:
            with self.subTest(workflow=wf):
                self.assertNotIn("--target-date", self.workflow(wf))


class TestHistoricalLedgersAreNotRewritten(unittest.TestCase):
    """
    The fix is forward-only. Two completed human reviews reason about the
    existing ledgers, and the review tool's missing-day anomaly is a true
    statement about them.
    """

    def test_no_collector_writes_into_an_existing_ledger_file(self):
        for script in ("shadow_collect.py", "shadow_collect_japan.py"):
            with self.subTest(script=script):
                src = (REPO_ROOT / "scripts" / script).read_text(encoding="utf-8")
                for banned in ("backfill", "rewrite_ledger", "os.remove", "unlink("):
                    self.assertNotIn(banned, src)

    def test_the_review_tool_still_reports_missing_days(self):
        """Hiding the anomaly would remove the signal that found this bug."""
        src = (REPO_ROOT / "scripts" / "review_shadow_state.py").read_text(encoding="utf-8")
        self.assertIn("inside the observed collection period", src)


if __name__ == "__main__":
    unittest.main()
