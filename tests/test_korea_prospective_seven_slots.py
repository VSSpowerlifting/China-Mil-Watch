"""Korea seven-slot candidate never rewrites its failed historical Day-7 window.

Offline synthetic ledger cases only; no HWPX bytes, publisher requests,
workflow dispatches, state changes, model use, source rights or publication.
"""
import unittest

from scripts import watch_korea_shadow_slots as watch
from scripts.korea_day7_machine_preflight import EXPECTED as ORIGINAL_DAY7_DATES
from tests.test_korea_shadow_slot_watchdog import CLOCK, SHA, originals, receipt


def followup_days(end=19):
    return originals() + [
        receipt("2026-10-%02d" % d, run="%d-1" % (400000 + d))
        for d in range(13, end + 1)
    ]


class KoreaProspectiveSevenLedgerCandidateTests(unittest.TestCase):
    def test_actual_october_14_pattern_has_six_of_seven_and_streak_two(self):
        report = watch.summarize(
            followup_days(14), CLOCK, commit=SHA,
            as_of="2026-10-15T00:00:00Z",
        )
        self.assertEqual(
            report["rolling_seven_mature_dates"],
            ["2026-10-%02d" % d for d in range(8, 15)],
        )
        self.assertEqual(
            report["rolling_seven_missing_scheduled_dates"], ["2026-10-12"]
        )
        self.assertFalse(report["rolling_seven_consecutive_ledger_candidate"])
        self.assertEqual(report["current_scheduled_ledger_streak_days"], 2)
        self.assertTrue(report["october_12_scheduled_gap_still_unrepaired"])
        self.assertEqual(report["status"], "HISTORICAL_SCHEDULED_GAPS_REMAIN")

    def test_seven_later_successful_ledger_days_are_only_candidate(self):
        report = watch.summarize(
            followup_days(19), CLOCK, commit=SHA,
            as_of="2026-10-20T00:00:00Z",
        )
        self.assertEqual(
            report["rolling_seven_mature_dates"],
            ["2026-10-%02d" % d for d in range(13, 20)],
        )
        self.assertEqual(report["rolling_seven_missing_scheduled_dates"], [])
        self.assertTrue(report["rolling_seven_consecutive_ledger_candidate"])
        self.assertEqual(report["current_scheduled_ledger_streak_days"], 7)
        self.assertTrue(report["october_12_scheduled_gap_still_unrepaired"])
        self.assertEqual(report["missing_scheduled_dates"], ["2026-10-12"])
        self.assertEqual(report["status"], "HISTORICAL_SCHEDULED_GAPS_REMAIN")
        self.assertEqual(
            report["rolling_seven_observation_kind"],
            "LEDGER_ONLY_CANDIDATE_NOT_AUTHENTICATED_ACTIONS",
        )
        for hold in (
            "authenticates_all_github_actions_attempts",
            "verifies_capture_bytes_or_publisher_completeness",
            "human_review_approved", "source_or_media_rights_approved",
            "production_eligible", "weekly_brief_eligible",
            "rolling_seven_production_admission_authorized",
        ):
            self.assertIs(report[hold], False, hold)
        # The historical source-contract must never be rewritten into a
        # rolling Day-7 pass or silently reassign the failed Oct 12 slot.
        self.assertEqual(
            ORIGINAL_DAY7_DATES,
            ["2026-10-%02d" % d for d in range(7, 14)],
        )

    def test_manual_recovery_of_october_12_never_counts_as_schedule(self):
        data = followup_days(14)
        data.append(receipt(
            "2026-10-12", run="909901-1", origin="explicit",
            result="ok",
        ))
        report = watch.summarize(
            data, CLOCK, commit=SHA,
            as_of="2026-10-15T00:00:00Z",
        )
        self.assertFalse(report["rolling_seven_consecutive_ledger_candidate"])
        self.assertEqual(
            report["rolling_seven_missing_scheduled_dates"], ["2026-10-12"],
        )
        self.assertEqual(
            report["source_dates_recovered_explicitly_but_not_scheduled"],
            ["2026-10-12"],
        )
        self.assertTrue(report["october_12_scheduled_gap_still_unrepaired"])

    def test_grace_window_and_new_missing_day_fail_candidate(self):
        data = followup_days(19)
        before_grace = watch.summarize(
            data, CLOCK, commit=SHA,
            as_of="2026-10-19T23:46:59Z",
        )
        self.assertEqual(before_grace["latest_mature_slot"], "2026-10-18")
        self.assertFalse(before_grace["rolling_seven_consecutive_ledger_candidate"])
        self.assertIn("2026-10-12", before_grace["rolling_seven_missing_scheduled_dates"])

        data.pop()  # Oct 19 does not appear in an authenticated ledger.
        missing = watch.summarize(
            data, CLOCK, commit=SHA,
            as_of="2026-10-20T00:00:00Z",
        )
        self.assertFalse(missing["rolling_seven_consecutive_ledger_candidate"])
        self.assertEqual(missing["rolling_seven_missing_scheduled_dates"], ["2026-10-19"])
        self.assertEqual(missing["current_scheduled_ledger_streak_days"], 0)
        self.assertTrue(missing["current_mature_slot_missing"])

    def test_invalid_rerun_and_failed_health_cannot_complete_window(self):
        original = followup_days(19)
        for key, value in (
            ("run_id", "999001-2"),
            ("target_date_source", "explicit"),
            ("health", "fail"),
            ("result", "robots_timeout"),
        ):
            data = [dict(x) for x in original]
            data[-1][key] = value
            if key == "run_id":
                with self.assertRaises(watch.KoreaWatchHold):
                    watch.summarize(
                        data, CLOCK, commit=SHA,
                        as_of="2026-10-20T00:00:00Z",
                    )
            else:
                report = watch.summarize(
                    data, CLOCK, commit=SHA,
                    as_of="2026-10-20T00:00:00Z",
                )
                self.assertFalse(report["rolling_seven_consecutive_ledger_candidate"])
                self.assertEqual(report["rolling_seven_missing_scheduled_dates"],
                                 ["2026-10-19"])


if __name__ == "__main__":
    unittest.main()
