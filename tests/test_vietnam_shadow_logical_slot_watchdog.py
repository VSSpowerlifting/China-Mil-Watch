"""No-network tests for Vietnam MPS logical schedule watchdog.

Synthetic ledgers are not official source facts or sign-off. The production
runner re-verifies a pinned Git branch and all capture/version evidence first.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.watch_vietnam_shadow_slots import (
    STATE_BRANCH, SOURCE, WatchdogRefused, matured_latest,
    summarize, verify_actual_state, main,
)

SHA = "a" * 40
FIRST = "2026-10-07T17:16:33+00:00"
AS_OF_GRACE = "2026-10-09T06:16:00Z"
AS_OF_OVERDUE = "2026-10-09T06:17:00Z"


def record(logical_day, *, run_id, provenance="schedule-slot", health="ok",
           started=None, finished=None):
    return {
        "run_id": run_id,
        "target_date": logical_day,
        "target_date_source": provenance,
        "health": health,
        "started_utc": started or (logical_day + "T23:05:53+00:00"),
        "finished_utc": finished or (logical_day + "T23:06:07+00:00"),
    }


def evidence():
    return {
        "source_slug": SOURCE,
        "clock": {"day_zero_utc": FIRST, "day_zero_run_id": "bootstrap"},
        "runs": [
            record("2026-10-05", run_id="bootstrap", provenance="explicit",
                   started="2026-10-07T17:16:23+00:00",
                   finished=FIRST),
            record("2026-10-07", run_id="scheduled-377",
                   started="2026-10-07T23:05:53+00:00",
                   finished="2026-10-07T23:06:07+00:00"),
        ],
    }


class VietnamWatchdogTests(unittest.TestCase):
    def test_mature_slot_considers_github_runner_delay_grace(self):
        self.assertEqual(matured_latest(AS_OF_GRACE).isoformat(), "2026-10-07")
        self.assertEqual(matured_latest(AS_OF_OVERDUE).isoformat(), "2026-10-08")
        self.assertEqual(matured_latest("2026-10-08T21:15:00Z").isoformat(),
                         "2026-10-07")
        self.assertEqual(matured_latest("2026-10-11T15:07:00Z").isoformat(),
                         "2026-10-10")
        with self.assertRaises(WatchdogRefused):
            matured_latest("2026-10-08T12:00:00")
        with self.assertRaises(WatchdogRefused):
            matured_latest("2026-10-08T12:00:00-04:00")

    def test_live_october_seven_ledgers_are_not_prematurely_alerted(self):
        result = summarize(evidence(), state_commit=SHA,
                           as_of="2026-10-08T21:15:00Z")
        self.assertEqual(result["status"], "verified-scheduled-slots-present")
        self.assertEqual(result["evaluated_slots"], 1)
        self.assertEqual(result["present_slots"], 1)
        self.assertEqual(result["overdue_logical_dates"], [])
        self.assertEqual(result["latest_successful_logical_date"], "2026-10-07")
        self.assertTrue(result["do_not_use_actions_rerun"])
        self.assertFalse(result["collection_window_complete_for_editorial"])
        self.assertFalse(result["government_silence_established"])

    def test_missing_october_eight_is_overdue_only_after_grace(self):
        self.assertEqual(summarize(evidence(), state_commit=SHA,
                                   as_of=AS_OF_GRACE)["overdue_logical_dates"], [])
        overdue = summarize(evidence(), state_commit=SHA, as_of=AS_OF_OVERDUE)
        self.assertEqual(overdue["overdue_logical_dates"], ["2026-10-08"])
        self.assertEqual(overdue["status"], "overdue-logical-slots")
        self.assertTrue(overdue["manual_recovery_required_if_overdue"])
        self.assertEqual(overdue["manual_recovery_input"], "target_date")

    def test_completed_explicit_recovery_closes_original_missing_day(self):
        e = evidence()
        e["runs"].append(record(
            "2026-10-08", run_id="manual-386",
            provenance="explicit",
            started="2026-10-09T06:18:00+00:00",
            finished="2026-10-09T06:19:00+00:00"))
        d = summarize(e, state_commit=SHA, as_of="2026-10-09T07:00:00Z")
        self.assertEqual(d["overdue_logical_dates"], [])
        self.assertEqual(d["status"], "verified-scheduled-slots-present")
        self.assertEqual(d["present_slots"], 2)

    def test_failed_target_run_is_not_silent_success(self):
        e = evidence()
        e["runs"].append(record(
            "2026-10-08", run_id="scheduled-fail", health="fail",
            started="2026-10-08T23:05:00+00:00",
            finished="2026-10-08T23:06:00+00:00"))
        d = summarize(e, state_commit=SHA, as_of=AS_OF_OVERDUE)
        self.assertEqual(d["overdue_logical_dates"], ["2026-10-08"])

    def test_lookup_overdue_dates_is_bounded(self):
        x = summarize(evidence(), state_commit=SHA,
                      as_of="2026-11-20T18:20:00Z")
        self.assertLessEqual(x["evaluated_slots"], 30)
        self.assertNotIn("2026-10-08", x["overdue_logical_dates"])
        self.assertGreater(len(x["overdue_logical_dates"]), 0)

    def test_foreign_wrong_branch_or_forged_ledger_refused(self):
        for field, replacement in (
            ("source_slug", "vn_moit_energy_vi"),
            ("clock", None),
        ):
            e = evidence()
            e[field] = replacement
            with self.assertRaises(WatchdogRefused):
                summarize(e, state_commit=SHA, as_of=AS_OF_GRACE)
        e = evidence()
        e["runs"][1]["run_id"] = "bootstrap"
        with self.assertRaisesRegex(WatchdogRefused, "duplicate"):
            summarize(e, state_commit=SHA, as_of=AS_OF_GRACE)
        e = evidence()
        e["runs"][1]["target_date_source"] = "guess"
        with self.assertRaises(WatchdogRefused):
            summarize(e, state_commit=SHA, as_of=AS_OF_GRACE)
        e = evidence()
        e["runs"][1]["target_date"] = "2026-02-30"
        with self.assertRaises(WatchdogRefused):
            summarize(e, state_commit=SHA, as_of=AS_OF_GRACE)

    def test_readonly_actual_state_verification_happens_before_inspection(self):
        with patch("scripts.watch_vietnam_shadow_slots.formal.resolve_state_repo",
                   return_value=Path("/fake/verified")), \
             patch("scripts.watch_vietnam_shadow_slots.formal.verify_state_commit",
                   return_value={"state_commit": SHA}) as verified, \
             patch("scripts.watch_vietnam_shadow_slots.formal.export_state_tree",
                   return_value=Path("/fake/state")) as export, \
             patch("scripts.watch_vietnam_shadow_slots.ministry.review",
                   return_value=evidence()) as reviewer:
            result = verify_actual_state(Path("/tmp/mps"), SHA,
                                         as_of=AS_OF_GRACE)
        verified.assert_called_once_with(Path("/fake/verified"), SHA, STATE_BRANCH)
        export.assert_called_once()
        reviewer.assert_called_once_with(Path("/fake/state"), SOURCE)
        self.assertEqual(result["status"], "verified-scheduled-slots-present")

    def test_cli_rejects_future_asof_and_no_public_output(self):
        import scripts.watch_vietnam_shadow_slots as watch
        from io import StringIO
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            with patch.object(watch, "verify_actual_state",
                              return_value=summarize(
                                  evidence(), state_commit=SHA,
                                  as_of=AS_OF_OVERDUE)), \
                 patch("sys.stdout", StringIO()) as log:
                result = main(["--state-repo", str(path), "--state-commit", SHA,
                               "--out", str(path / "private.json")])
            self.assertEqual(result, 0)
            self.assertNotIn("bocongan.gov.vn", log.getvalue())
            saved = json.loads((path / "private.json").read_text())
            self.assertFalse(saved["email_sent"])
            self.assertFalse(saved["desk_qualified"])
            with patch.object(watch, "verify_actual_state",
                              return_value=saved), \
                 patch("sys.stdout", StringIO()):
                with self.assertRaisesRegex(SystemExit, "REFUSED"):
                    main(["--state-repo", str(path), "--state-commit", SHA,
                          "--require-current-slot"])
            with self.assertRaises(WatchdogRefused):
                main(["--state-repo", str(path), "--state-commit", SHA,
                      "--as-of-utc", "2099-10-09T12:00:00Z"])


if __name__ == "__main__":
    unittest.main()
