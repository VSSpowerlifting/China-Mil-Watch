"""Synthetic, publisher-free Korea scheduled-slot watcher contracts."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import watch_korea_shadow_slots as watch

SHA = "a" * 40
CLOCK = {"desk": "korea", "day_zero_utc": "2026-10-06T16:52:01.420713+00:00",
         "day_zero_run_id": "local-native-20261006-korea"}


def receipt(d, *, run, origin="schedule-slot", health="ok",
            result="ok_all_duplicates"):
    return {"desk": "korea", "run_id": run, "target_date": d,
            "target_date_source": origin, "health": health, "result": result,
            "started_utc": d + "T20:40:00+00:00",
            "finished_utc": d + "T20:41:00+00:00"}


def originals():
    data = [receipt("2026-10-06", run="local-native-20261006-korea",
                    origin="explicit", result="ok")]
    for i, d in enumerate(range(6, 12)):
        data.append(receipt("2026-10-%02d" % d, run="%d-1" % (37533278839 + i),
                            result="ok" if d == 8 else "ok_all_duplicates"))
    return data


class KoreaWatchTests(unittest.TestCase):
    def test_maturation_never_alerts_before_six_hour_grace(self):
        self.assertEqual(watch.matured_slot("2026-10-13T23:46:59Z").isoformat(),
                         "2026-10-12")
        self.assertEqual(watch.matured_slot("2026-10-13T23:47:00Z").isoformat(),
                         "2026-10-13")
        self.assertEqual(watch.matured_slot("2026-10-14T06:07:00Z").isoformat(),
                         "2026-10-13")
        with self.assertRaises(watch.KoreaWatchHold):
            watch.matured_slot("2026-10-13T23:47:00-04:00")
        with self.assertRaises(watch.KoreaWatchHold):
            watch.matured_slot("2026-10-13T23:47:00")

    def test_live_october_six_to_eleven_metadata_reports_october_twelve_gap(self):
        report = watch.summarize(
            originals(), CLOCK, commit=SHA, as_of="2026-10-13T01:30:00Z")
        self.assertEqual(report["latest_mature_slot"], "2026-10-12")
        self.assertEqual(report["successful_scheduled_slots"], 5)
        self.assertEqual(report["missing_scheduled_dates"], ["2026-10-12"])
        self.assertEqual(report["status"], "CURRENT_SCHEDULED_SLOT_MISSING")
        self.assertTrue(report["current_mature_slot_missing"])
        self.assertFalse(report["production_eligible"])
        self.assertFalse(report["authenticates_all_github_actions_attempts"])

    def test_manual_recovery_covers_source_date_but_never_fabricates_schedule(self):
        data = originals()
        data.append(receipt("2026-10-12", run="9991-1", origin="explicit",
                            result="ok"))
        report = watch.summarize(
            data, CLOCK, commit=SHA, as_of="2026-10-13T23:47:10Z")
        self.assertEqual(report["missing_scheduled_dates"],
                         ["2026-10-12", "2026-10-13"])
        self.assertEqual(
            report["source_dates_recovered_explicitly_but_not_scheduled"],
            ["2026-10-12"])
        self.assertEqual(
            report["source_dates_without_successful_scheduled_or_explicit_recovery"],
            ["2026-10-13"])
        self.assertFalse(report["weekly_brief_eligible"])
        self.assertFalse(report["source_or_media_rights_approved"])

    def test_later_success_does_not_hide_prior_failure(self):
        data = originals()
        data.append(receipt("2026-10-13", run="384001-1", result="ok"))
        report = watch.summarize(
            data, CLOCK, commit=SHA, as_of="2026-10-13T23:48:00Z")
        self.assertFalse(report["current_mature_slot_missing"])
        self.assertEqual(report["status"], "HISTORICAL_SCHEDULED_GAPS_REMAIN")
        self.assertEqual(report["missing_scheduled_dates"], ["2026-10-12"])
        self.assertFalse(report["human_review_approved"])

    def test_failure_and_foreign_provenance_never_count_as_scheduled(self):
        for changed in ({"health": "fail"}, {"result": "robots_timeout"}):
            data = originals()
            data.append(dict(receipt("2026-10-12", run="38323793488-1"), **changed))
            report = watch.summarize(
                data, CLOCK, commit=SHA, as_of="2026-10-13T01:30:00Z")
            self.assertEqual(report["missing_scheduled_dates"], ["2026-10-12"])
        for bad in ({"run_id": "38323793488-2"},
                    {"target_date_source": "guess"},
                    {"target_date": "2026-02-30"},
                    {"desk": "indonesia"}):
            data = originals()
            data.append(dict(receipt("2026-10-12", run="38323793488-1"), **bad))
            with self.assertRaises(watch.KoreaWatchHold):
                watch.summarize(data, CLOCK, commit=SHA,
                                as_of="2026-10-13T01:30:00Z")

    def test_duplicated_ids_foreign_clock_or_unpinned_commit_fail(self):
        data = originals()
        data.append(dict(data[-1]))
        with self.assertRaisesRegex(watch.KoreaWatchHold, "duplicate"):
            watch.summarize(data, CLOCK, commit=SHA,
                            as_of="2026-10-13T01:30:00Z")
        with self.assertRaises(watch.KoreaWatchHold):
            watch.summarize(originals(), dict(CLOCK, desk="indonesia"),
                            commit=SHA, as_of="2026-10-13T01:30:00Z")
        with self.assertRaises(watch.KoreaWatchHold):
            watch.summarize(originals(), CLOCK, commit="main",
                            as_of="2026-10-13T01:30:00Z")

    def test_readonly_sparse_checkout_reuses_immutable_ledger_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            clock = path / "state" / "clock.json"
            clock.parent.mkdir()
            clock.write_text(json.dumps(CLOCK), encoding="utf-8")
            with patch.object(watch, "pinned_ledger_checkout",
                              return_value=(SHA, originals())) as verifier:
                report = watch.inspect_checkout(
                    path, as_of="2026-10-13T01:30:00Z")
                verifier.assert_called_once_with(path)
                self.assertEqual(report["state_commit"], SHA)
                self.assertEqual(report["status"], "CURRENT_SCHEDULED_SLOT_MISSING")

    def test_workflow_is_source_free_and_readonly_with_a_delayed_slot_check(self):
        raw = (Path(__file__).resolve().parents[1] / ".github" /
               "workflows/korea_shadow_slot_watchdog.yml"
               ).read_text(encoding="utf-8")
        self.assertIn("7 6 * * *", raw)
        self.assertIn("permissions:\n  contents: read", raw)
        self.assertIn("shadow/korea-policy-briefing", raw)
        self.assertIn("state/ledger", raw)
        self.assertIn("state/clock.json", raw)
        self.assertIn("scripts.watch_korea_shadow_slots", raw)
        self.assertIn("--fail-current-gap", raw)
        for forbidden in ("git push", "actions/upload-artifact",
                          "workflow_dispatch --ref", "ANTHROPIC_API_KEY",
                          "IPR_SMTP_APP_PASSWORD",
                          "state/captures/*.bin", "state/shadow.db\n",
                          "git merge", "gh workflow run"):
            self.assertNotIn(forbidden, raw)


if __name__ == "__main__":
    unittest.main()
