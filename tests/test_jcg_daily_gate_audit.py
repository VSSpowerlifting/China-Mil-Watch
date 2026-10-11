"""No-network Japan JCG scheduling gate audit regression tests."""
from __future__ import annotations

import base64
import copy
import io
import json
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts.attest_vietnam_run_state import PREFIX, sha_blob
from scripts.audit_jcg_daily_gate import (
    AttestationHold, BRANCH, MAX_RUNS, SCHEMA, VARIABLE,
    WORKFLOW, main, observe,
)

HEAD = "a" * 40
CLOCK = {"desk": "japan_jcg", "day_zero_utc": "2026-10-08T18:57:32.592661+00:00",
         "day_zero_run_id": "37828199188-1"}
NAME_DAY0 = "20261008T185732.592661+0000-37828199188-1.json"
NAME_DAY1 = "20261009T191423.000000+0000-38110000001-1.json"
RUN = 38110000001
RUN_KEY = PREFIX + "/actions/workflows/jcg_guarded_daily_shadow.yml/runs?event=schedule&per_page=30&page=1"


def blob(obj):
    data = json.dumps(obj, sort_keys=True).encode("utf-8")
    return {"encoding": "base64", "content": base64.b64encode(data).decode(),
            "sha": sha_blob(data)}


def ledger(*, run_id="37828199188-1", day="2026-10-08", origin="explicit",
           desk="japan_jcg", anomalies=None):
    return {"desk": desk, "run_id": run_id, "target_date": day,
            "target_date_source": origin, "day_zero_utc": CLOCK["day_zero_utc"],
            "health": "ok", "result": "ok", "anomalies": anomalies or []}


class FakeAPI:
    def __init__(self, *, enabled=False, runs=True, job="skipped",
                 with_scheduled_ledger=False, source_anomaly=False):
        self.routes = {}
        self.calls = []
        self.refs = 0
        self.routes[PREFIX + "/actions/variables/" + VARIABLE] = {
            "name": VARIABLE, "value": "true" if enabled else "false"}
        self.routes[PREFIX + "/git/ref/heads/" + BRANCH] = {
            "ref": "refs/heads/" + BRANCH, "object": {"sha": HEAD}}
        self.routes[PREFIX + "/contents/state/clock.json?ref=" + HEAD] = blob(CLOCK)
        files = [NAME_DAY0]
        self.routes[PREFIX + "/contents/state/ledger/" + NAME_DAY0 +
                    "?ref=" + HEAD] = blob(ledger())
        if with_scheduled_ledger:
            files.append(NAME_DAY1)
            self.routes[PREFIX + "/contents/state/ledger/" + NAME_DAY1 +
                        "?ref=" + HEAD] = blob(ledger(
                            run_id=str(RUN) + "-1", day="2026-10-09",
                            origin="schedule-slot",
                            anomalies=["robots MIME warning"] if source_anomaly else []))
        self.routes[PREFIX + "/contents/state/ledger?ref=" + HEAD] = [
            {"name": name} for name in files]
        self.routes[RUN_KEY] = {
            "total_count": 1 if runs else 0,
            "workflow_runs": [{
                "id": RUN, "run_attempt": 1, "event": "schedule",
                "path": WORKFLOW, "status": "completed",
                "run_started_at": "2026-10-09T19:14:11Z",
            }] if runs else []}
        self.routes[PREFIX + "/actions/runs/{}/attempts/1/jobs?per_page=30".format(RUN)] = {
            "total_count": 1,
            "jobs": [{"name": "shadow", "status": "completed",
                      "conclusion": job}],
        }

    def get(self, path):
        self.calls.append(path)
        if path not in self.routes:
            raise AssertionError("Unexpected GitHub URL: " + path)
        return copy.deepcopy(self.routes[path])


class JCGDailyGateTests(unittest.TestCase):
    def test_disabled_current_gate_and_skipped_job_are_not_failed_source(self):
        api = FakeAPI()
        report = observe(api, as_of="2026-10-11")
        self.assertEqual(report["schema"], SCHEMA)
        self.assertFalse(report["current_gate_enabled"])
        self.assertEqual(report["scheduled_attempts_seen"], 1)
        self.assertEqual(report["scheduled_attempts"][0]["job_outcome"], "skipped")
        self.assertEqual(report["scheduled_success_days_correlated_with_ledger"], [])
        self.assertEqual(report["published_source_ledgers"], 1)
        self.assertEqual(report["state"], "held_for_review")
        self.assertFalse(report["historic_gate_values_known"])
        self.assertFalse(report["human_day_7_review_approved"])
        self.assertFalse(report["source_licence_or_publication_authorized"])
        self.assertFalse(report["daily_collection_authorized_by_this_tool"])
        self.assertFalse(report["production_desk_promotion_authorized"])
        self.assertEqual(api.calls.count(PREFIX + "/git/ref/heads/" + BRANCH), 2)

    def test_enabled_now_and_historical_skip_does_not_claim_failed_publication(self):
        report = observe(FakeAPI(enabled=True), as_of="2026-10-11")
        self.assertEqual(report["scheduled_attempts"][0]["job_outcome"], "skipped")
        self.assertIn("enabled now, but no successful scheduled collection day is verified",
                      report["review_reasons"])
        self.assertEqual(report["scheduled_success_days_correlated_with_ledger"], [])

    def test_green_job_needs_matching_immutable_ledger_not_just_ci_green(self):
        report = observe(FakeAPI(enabled=True, job="success"),
                         as_of="2026-10-11")
        self.assertEqual(report["state"], "held_for_review")
        self.assertIn(str(RUN) + "-1", report["mismatch_attempts_needing_review"])
        self.assertEqual(report["scheduled_success_days_correlated_with_ledger"], [])

    def test_correlated_scheduled_run_is_bounded_not_qualification(self):
        report = observe(FakeAPI(enabled=True, job="success",
                                 with_scheduled_ledger=True),
                         as_of="2026-10-11")
        self.assertEqual(report["state"], "bounded_observations_only")
        self.assertEqual(report["scheduled_success_days_correlated_with_ledger"],
                         ["2026-10-09"])
        self.assertFalse(report["complete_scheduled_attempt_history_proven"])
        self.assertFalse(report["human_day_7_review_approved"])
        self.assertFalse(report["production_desk_promotion_authorized"])

    def test_successful_collection_with_source_anomaly_is_held(self):
        report = observe(FakeAPI(enabled=True, job="success",
                                 with_scheduled_ledger=True,
                                 source_anomaly=True),
                         as_of="2026-10-11")
        self.assertEqual(report["state"], "held_for_review")
        self.assertEqual(report["source_anomalies_observed"], 1)
        self.assertIn(str(RUN) + "-1", report["mismatch_attempts_needing_review"])

    def test_complete_absence_of_scheduled_runs_not_proven_silence(self):
        report = observe(FakeAPI(enabled=False, runs=False),
                         as_of="2026-10-11")
        self.assertEqual(report["scheduled_attempts_seen"], 0)
        self.assertEqual(report["published_source_ledgers"], 1)
        self.assertIn("no scheduled job attempts observed in bounded inventory",
                      report["review_reasons"])
        self.assertFalse(report["complete_scheduled_attempt_history_proven"])

    def test_unknown_gate_or_different_source_is_blocked(self):
        api = FakeAPI()
        api.routes[PREFIX + "/actions/variables/" + VARIABLE]["value"] = "unknown"
        with self.assertRaisesRegex(AttestationHold, "variable"):
            observe(api, as_of="2026-10-11")
        api = FakeAPI()
        key = PREFIX + "/contents/state/ledger/" + NAME_DAY0 + "?ref=" + HEAD
        data = json.loads(base64.b64decode(api.routes[key]["content"]))
        data["desk"] = "japan_mod"
        api.routes[key] = blob(data)
        with self.assertRaisesRegex(AttestationHold, "source ledger"):
            observe(api, as_of="2026-10-11")

    def test_bad_blob_and_moving_branch_ref_are_blocked(self):
        api = FakeAPI()
        api.routes[PREFIX + "/contents/state/clock.json?ref=" + HEAD]["sha"] = "0"*40
        with self.assertRaisesRegex(AttestationHold, "blob SHA"):
            observe(api, as_of="2026-10-11")

        class Moving(FakeAPI):
            def get(self, path):
                x = super().get(path)
                if path == PREFIX + "/git/ref/heads/" + BRANCH:
                    self.refs += 1
                    if self.refs > 1:
                        x["object"]["sha"] = "b" * 40
                return x
        with self.assertRaisesRegex(AttestationHold, "moved"):
            observe(Moving(), as_of="2026-10-11")

    def test_failures_and_skips_do_not_claim_success_and_state_only_is_held(self):
        for job in ("failure", "cancelled", "timed_out", "skipped"):
            report = observe(FakeAPI(enabled=True, job=job,
                                     with_scheduled_ledger=True),
                             as_of="2026-10-11")
            with self.subTest(job=job):
                self.assertEqual(report["state"], "held_for_review")
                self.assertEqual(report["scheduled_success_days_correlated_with_ledger"], [])
                self.assertIn(str(RUN) + "-1", report["mismatch_attempts_needing_review"])

    def test_ambiguous_missing_or_oversized_job_index_is_blocked(self):
        for shape in (
            {"total_count": 0, "jobs": []},
            {"total_count": 2, "jobs": [{"name": "shadow", "status": "completed",
                                       "conclusion": "success"}]},
            {"total_count": 31, "jobs": []},
        ):
            api = FakeAPI()
            key = PREFIX + "/actions/runs/{}/attempts/1/jobs?per_page=30".format(RUN)
            api.routes[key] = shape
            with self.subTest(shape=shape), self.assertRaises(AttestationHold):
                observe(api, as_of="2026-10-11")
        api = FakeAPI()
        api.routes[RUN_KEY]["total_count"] = MAX_RUNS + 1
        with self.assertRaisesRegex(AttestationHold, "inventory"):
            observe(api, as_of="2026-10-11")

    def test_invalid_logical_day_and_duplicate_ledger_inventory_rejected(self):
        api = FakeAPI()
        key = PREFIX + "/contents/state/ledger?ref=" + HEAD
        api.routes[key].append({"name": NAME_DAY0})
        with self.assertRaisesRegex(AttestationHold, "duplicate"):
            observe(api, as_of="2026-10-11")
        with self.assertRaises(AttestationHold):
            observe(FakeAPI(), as_of="2030-01-01")
        with self.assertRaises(AttestationHold):
            observe(FakeAPI(), as_of="2026-10-07")

    def test_cli_is_inert_without_explicit_flag_and_token(self):
        with redirect_stderr(io.StringIO()), patch(
                "scripts.audit_jcg_daily_gate.GithubRead") as g:
            with self.assertRaises(SystemExit):
                main(["--as-of", "2026-10-11"])
            with patch.dict("os.environ", {}, clear=True), self.assertRaises(SystemExit):
                main(["--as-of", "2026-10-11", "--approve-github-read"])
            g.assert_not_called()


if __name__ == "__main__":
    unittest.main()
