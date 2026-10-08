"""Synthetic-only cross-check of AFP Actions run identity; no network or human approvals."""
from __future__ import annotations

import copy
import unittest
from scripts import audit_ph_afp_actions_provenance as proof


class ActionsContracts(unittest.TestCase):
    def setUp(self):
        self.ledgers = []
        self.actions = []
        for day, run, sha in (
            ("2026-10-07", 37631681338, "5" * 40),
            ("2026-10-08", 37788547061, "6" * 40),
        ):
            self.ledgers.append({
                "run_id": str(run) + "-1", "target_date": day,
                "collector_commit": sha,
            })
            self.actions.append({
                "id": run, "run_attempt": 1, "workflow_id": proof.WORKFLOW_ID,
                "name": proof.WORKFLOW_NAME, "event": "schedule",
                "status": "completed", "conclusion": "success",
                "head_branch": "main", "head_sha": sha,
                "created_at": day + "T13:51:00Z",
            })
        self.scorecard = {
            "immutable_state_commit": "a" * 40,
            "window_start": "2026-10-07", "window_end": "2026-10-13",
            "as_of_utc_date": "2026-10-08",
            "all_seven_ledger_slots_supported": False,
            "slots": [
                {"date": "2026-10-%02d" % day,
                 "status": ("ledger_success_unverified_actions" if day <= 8 else
                            "future_not_due"),
                 "run_id": (self.ledgers[day - 7]["run_id"] if day <= 8 else None)}
                for day in range(7, 14)
            ],
        }

    def test_two_production_like_runs_are_not_seven_or_qualified(self):
        page = {"total_count": 2, "workflow_runs": self.actions}
        out = proof.compare(self.scorecard, self.ledgers,
                            proof.parse_export(page))
        self.assertEqual(out["matched_scheduled_successes"], 2)
        self.assertFalse(out["all_seven_positive_runs_matched"])
        self.assertFalse(out["production_eligible"])
        self.assertFalse(out["weekly_ai_writer_eligible"])
        self.assertFalse(out["export_query_scope_independently_authenticated"])
        self.assertFalse(out["historical_failed_and_rerun_attempts_exhaustively_audited"])

    def test_divided_paginated_export_checks_total(self):
        pages = [
            {"total_count": 2, "workflow_runs": [self.actions[0]]},
            {"total_count": 2, "workflow_runs": [self.actions[1]]},
        ]
        self.assertEqual(len(proof.parse_export(pages)), 2)
        for corrupted in (
            pages[:1],
            [pages[0], {"total_count": 3, "workflow_runs": [self.actions[1]]}],
            [pages[0], {"total_count": 2, "workflow_runs": [self.actions[0]]}],
        ):
            with self.subTest(corrupted=corrupted), \
                    self.assertRaises(proof.ActionsProvenanceError):
                proof.parse_export(corrupted)

    def test_no_manual_rehearsal_is_treated_as_a_schedule(self):
        action = dict(self.actions[0], event="workflow_dispatch")
        self.assertIn("not_a_scheduled_workflow_event",
                      proof.check_action(self.ledgers[0], action))

    def test_failed_run_and_wrong_workflow_are_not_counted(self):
        for mutation, issue in (
            ({"conclusion": "failure"}, "actions_not_successful"),
            ({"workflow_id": 123}, "workflow_identity_mismatch"),
            ({"name": "Wrong"}, "workflow_identity_mismatch"),
            ({"head_branch": "shadow/ph-afp"}, "not_main_branch"),
            ({"head_sha": "b" * 40}, "collector_commit_mismatch"),
            ({"run_attempt": 2}, "run_attempt_mismatch"),
        ):
            with self.subTest(mutation=mutation):
                action = dict(self.actions[0], **mutation)
                self.assertIn(issue, proof.check_action(self.ledgers[0], action))

    def test_wrong_day_schedule_is_held_for_manual_review(self):
        action = dict(self.actions[0], created_at="2026-10-08T13:51:00Z")
        self.assertIn("created_outside_scheduled_utc_date",
                      proof.check_action(self.ledgers[0], action))

    def test_absent_run_is_explicitly_unverified(self):
        self.assertEqual(proof.check_action(self.ledgers[0], None),
                         ["actions_run_missing_from_export"])

    def test_seven_matched_still_does_not_grant_approval(self):
        score = copy.deepcopy(self.scorecard)
        score["all_seven_ledger_slots_supported"] = True
        ledgers = copy.deepcopy(self.ledgers)
        actions = copy.deepcopy(self.actions)
        for day in range(9, 14):
            run_id = 90000000000 + day
            sha = ("%040x" % day)
            ledgers.append({"run_id": str(run_id) + "-1",
                            "target_date": "2026-10-%02d" % day,
                            "collector_commit": sha})
            actions.append(dict(self.actions[0], id=run_id,
                                head_sha=sha,
                                created_at="2026-10-%02dT13:51:00Z" % day))
            score["slots"][day - 7]["status"] = "ledger_success_unverified_actions"
            score["slots"][day - 7]["run_id"] = str(run_id) + "-1"
        out = proof.compare(score, ledgers, proof.parse_export(
            {"total_count": 7, "workflow_runs": actions}))
        self.assertTrue(out["all_seven_positive_runs_matched"])
        self.assertFalse(out["production_eligible"])
        self.assertFalse(out["human_reviews_or_reuse_rights_approved"])

    def test_unpaired_scheduled_run_is_disclosed_not_silent(self):
        extra = dict(self.actions[0], id=99999999999, conclusion="failure")
        out = proof.compare(self.scorecard, self.ledgers,
                            proof.parse_export({"total_count": 3,
                                                "workflow_runs": self.actions + [extra]}))
        self.assertEqual([x["id"] for x in out["other_scheduled_runs_in_export"]],
                         [99999999999])


if __name__ == "__main__":
    unittest.main()
