"""No-network proof that a manually dispatched, trusted JCG Actions observer is inert."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.attest_vietnam_run_state import PREFIX
from scripts.audit_jcg_daily_gate import (
    AttestationHold, BRANCH, TRUSTED_OBSERVER_REF, VARIABLE,
    gate_from_trusted_actions_context, observe, main,
)
from tests.test_jcg_daily_gate_audit import FakeAPI

VALID = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REPOSITORY": "VSSpowerlifting/China-Mil-Watch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_WORKFLOW_REF": TRUSTED_OBSERVER_REF,
    "GITHUB_SHA": "a" * 40,
    "GITHUB_TOKEN": "synthetic-never-transmitted",
    "IPR_JCG_OBSERVED_GATE": "false",
}
GATE_API = PREFIX + "/actions/variables/" + VARIABLE


class ActionsGateObservationTests(unittest.TestCase):
    def test_current_false_is_a_hold_and_skips_repository_variable_api(self):
        context_gate = gate_from_trusted_actions_context(dict(VALID))
        self.assertIs(context_gate, False)
        api = FakeAPI(enabled=True, runs=False)  # contradictory fake endpoint is never used
        result = observe(api, as_of="2026-10-11", actions_gate=context_gate)
        self.assertFalse(result["current_gate_enabled"])
        self.assertIn("verified_actions_vars_context_at_manual_dispatch",
                      result["current_gate_observed_via"])
        self.assertEqual(result["state"], "held_for_review")
        self.assertNotIn(GATE_API, api.calls)
        self.assertFalse(result["historic_gate_values_known"])
        self.assertFalse(result["production_desk_promotion_authorized"])

    def test_current_true_cannot_invent_continuity_or_human_signoff(self):
        env = dict(VALID, IPR_JCG_OBSERVED_GATE="true")
        api = FakeAPI(enabled=False, runs=True, job="success",
                      with_scheduled_ledger=True)
        result = observe(api, as_of="2026-10-11",
                         actions_gate=gate_from_trusted_actions_context(env))
        self.assertEqual(result["state"], "bounded_observations_only")
        self.assertEqual(result["scheduled_success_days_correlated_with_ledger"],
                         ["2026-10-09"])
        self.assertNotIn(GATE_API, api.calls)
        for key in ("historic_gate_values_known", "complete_scheduled_attempt_history_proven",
                    "human_day_7_review_approved", "source_licence_or_publication_authorized",
                    "daily_collection_authorized_by_this_tool",
                    "production_desk_promotion_authorized"):
            self.assertIs(result[key], False)

    def test_unset_or_untrusted_context_fails_closed(self):
        for key, bad in (
            ("IPR_JCG_OBSERVED_GATE", ""),
            ("IPR_JCG_OBSERVED_GATE", "TRUE"),
            ("GITHUB_ACTIONS", "false"),
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_REPOSITORY", "someone/fork"),
            ("GITHUB_REF", "refs/heads/feature"),
            ("GITHUB_WORKFLOW_REF", "VSSpowerlifting/China-Mil-Watch/.github/workflows/"
             "jcg_guarded_daily_shadow.yml@refs/heads/main"),
            ("GITHUB_SHA", "a" * 39 + "Z"),
        ):
            env = dict(VALID, **{key: bad})
            with self.subTest(key=key, bad=bad), self.assertRaises(AttestationHold):
                gate_from_trusted_actions_context(env)

    def test_false_context_cannot_be_overridden_by_fake_variable_api(self):
        api = FakeAPI(enabled=True, runs=True, job="skipped")
        report = observe(api, as_of="2026-10-11", actions_gate=False)
        self.assertFalse(report["current_gate_enabled"])
        self.assertEqual(report["state"], "held_for_review")
        self.assertNotIn(GATE_API, api.calls)

    def test_nonboolean_context_never_permitted(self):
        api = FakeAPI()
        for bad in ("false", 0, {}, []):
            with self.subTest(bad=bad), self.assertRaises(AttestationHold):
                observe(api, as_of="2026-10-11", actions_gate=bad)
        self.assertEqual(api.calls, [])

    def test_manual_cli_runs_with_readonly_actions_token_and_no_variable_api(self):
        api = FakeAPI(enabled=False, runs=True, job="skipped")
        data = io.StringIO()
        with patch.dict("os.environ", VALID, clear=True), \
             patch("scripts.audit_jcg_daily_gate.GithubRead", return_value=api), \
             redirect_stdout(data):
            rc = main(["--as-of", "2026-10-11", "--approve-github-read",
                       "--gate-from-actions-context"])
        self.assertEqual(rc, 1)  # observation succeeded, but review remains held
        item = json.loads(data.getvalue())
        self.assertEqual(item["state"], "held_for_review")
        self.assertFalse(item["current_gate_enabled"])
        self.assertNotIn(GATE_API, api.calls)

    def test_observer_workflow_is_manual_readonly_not_a_collector(self):
        from pathlib import Path
        workflow = (
            Path(__file__).resolve().parents[1] /
            ".github/workflows/jcg_gate_readonly_observation.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertIn("acknowledge_read_only_review", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("actions: read", workflow)
        self.assertIn("${{ vars.JCG_SHADOW_DAILY_ENABLED }}", workflow)
        for prohibited in (
            "\n  schedule:", "contents: write", "workflow_call:",
            "shadow_collect_desk", "git push ", "curl ", "wget ",
        ):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, workflow)

    def test_failed_context_cli_fails_before_any_api_call(self):
        api = FakeAPI()
        data = io.StringIO()
        bad = dict(VALID, GITHUB_EVENT_NAME="pull_request")
        with patch.dict("os.environ", bad, clear=True), \
             patch("scripts.audit_jcg_daily_gate.GithubRead", return_value=api), \
             redirect_stdout(data):
            rc = main(["--as-of", "2026-10-11", "--approve-github-read",
                       "--gate-from-actions-context"])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(data.getvalue())["state"], "blocked")
        self.assertEqual(api.calls, [])


if __name__ == "__main__":
    unittest.main()
