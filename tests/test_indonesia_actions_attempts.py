"""Fail-closed test of shared Korea/Indonesia Actions attempt inventory."""
import copy
import unittest

from scripts import audit_indonesia_actions_attempts as inventory
from scripts import audit_indonesia_shadow_provenance as p


def run(id, date, desk="indonesia", event="schedule", conclusion="success"):
    return {
        "id": id, "run_attempt": 1, "workflow_id": p.WORKFLOW_ID,
        "name": p.WORKFLOW_NAME, "event": event, "status": "completed",
        "conclusion": conclusion, "head_branch": "main",
        "created_at": date, "head_sha": "a" * 40,
    }


def artifact(id, desk="indonesia", attempt=1):
    return {"total_count": 1, "artifacts": [
        {"name": "candidate-shadow-%s-%s-%s" % (desk, id, attempt)}]}


class ActionsInventory(unittest.TestCase):
    def setUp(self):
        self.rows = [
            run(101, "2026-10-06T21:21:12Z", event="workflow_dispatch"),
            run(102, "2026-10-07T21:58:19Z"),
            run(103, "2026-10-07T22:00:00Z"),
        ]
        self.pages = [{"total_count": 3, "workflow_runs": self.rows}]
        self.artifacts = {"101": artifact(101), "102": artifact(102),
                          "103": artifact(103, "korea")}
        self.ledgers = [{"run_id": "local-native-20261006-indonesia"},
                        {"run_id": "101-1"}, {"run_id": "102-1"}]

    def report(self):
        return inventory.scan(self.pages, self.artifacts, self.ledgers,
                              as_of="2026-10-07")

    def test_full_shared_workflow_with_korea_is_clean(self):
        r = self.report()
        self.assertEqual(r["verdict"], "CONSISTENT_THROUGH_AS_OF_NOT_DAY7_SIGNOFF")
        self.assertEqual(r["counts"]["indonesia_attempts"], 2)
        self.assertEqual(r["counts"]["korea_attempts"], 1)
        self.assertEqual(r["scheduled_indonesia_days_observed"], ["2026-10-07"])
        self.assertEqual(r["missing_scheduled_indonesia_days"], [])
        self.assertFalse(r["source_rights_approved"])
        self.assertFalse(r["day7_human_checkpoint_completed"])
        self.assertFalse(r["publication_authorized"])

    def test_failed_indonesia_attempt_is_not_covered_by_successful_ledger(self):
        self.rows.append(run(104, "2026-10-07T23:30:00Z", conclusion="failure"))
        self.artifacts["104"] = artifact(104)
        self.pages[0]["total_count"] = 4
        r = self.report()
        self.assertEqual(r["verdict"], "HOLD")
        self.assertEqual(r["counts"]["indonesia_failures_or_cancellations"], 1)
        self.assertIn("indonesia_non_successful_workflow_attempt", r["holds"])
        self.assertIn("indonesia_workflow_attempt_without_pinned_ledger", r["holds"])

    def test_unselected_failure_is_shared_hold_not_assumed_korea(self):
        self.rows.append(run(104, "2026-10-07T23:30:00Z", conclusion="failure"))
        self.artifacts["104"] = {"total_count": 0, "artifacts": []}
        self.pages[0]["total_count"] = 4
        r = self.report()
        self.assertEqual(r["counts"]["ambiguous_shared_failures"], 1)
        self.assertIn("shared_workflow_unattributed_run", r["holds"])

    def test_missing_indonesia_slot_is_not_filled_by_korea(self):
        self.artifacts["102"] = artifact(102, "korea")
        r = self.report()
        self.assertEqual(r["verdict"], "HOLD")
        self.assertEqual(r["missing_scheduled_indonesia_days"], ["2026-10-07"])
        self.assertEqual(r["pinned_ledger_unmapped_count"], 1)

    def test_wrong_artifact_run_id_and_cross_desk_are_rejected(self):
        self.artifacts["102"] = artifact(99)
        with self.assertRaisesRegex(p.ProvenanceError, "artifact"):
            self.report()
        self.artifacts["102"] = {"total_count": 2, "artifacts": [
            artifact(102)["artifacts"][0], artifact(102, "korea")["artifacts"][0]]}
        with self.assertRaisesRegex(p.ProvenanceError, "multi-desk"):
            self.report()

    def test_repeated_run_and_artifact_pagination_does_not_silently_pass(self):
        self.pages[0]["total_count"] = 4
        with self.assertRaisesRegex(p.ProvenanceError, "incomplete"):
            self.report()
        self.pages[0]["total_count"] = 3
        self.artifacts["102"]["total_count"] = 4
        with self.assertRaisesRegex(p.ProvenanceError, "incomplete"):
            self.report()

    def test_run_attempt_two_requires_disposition(self):
        self.rows[1]["run_attempt"] = 2
        self.artifacts["102"] = artifact(102, attempt=2)
        self.ledgers[2]["run_id"] = "102-2"
        r = self.report()
        self.assertEqual(r["counts"]["indonesia_rerun_attempts"], 1)
        self.assertEqual(r["verdict"], "HOLD")

    def test_late_scheduled_attempt_is_attributed_to_prior_day(self):
        self.rows[1]["created_at"] = "2026-10-08T01:04:00Z"
        r = self.report()
        self.assertEqual(r["scheduled_indonesia_days_observed"], ["2026-10-07"])
        self.assertEqual(r["verdict"], "CONSISTENT_THROUGH_AS_OF_NOT_DAY7_SIGNOFF")

    def test_manual_run_never_repairs_missing_scheduled_date(self):
        self.rows[1]["event"] = "workflow_dispatch"
        r = self.report()
        self.assertEqual(r["verdict"], "HOLD")
        self.assertEqual(r["missing_scheduled_indonesia_days"], ["2026-10-07"])

    def test_unsafe_inputs_cannot_be_treated_as_full_run_inventory(self):
        self.artifacts.pop("103")
        with self.assertRaisesRegex(p.ProvenanceError, "cover every"):
            self.report()
        self.artifacts["103"] = artifact(103, "korea")
        self.rows[2]["workflow_id"] = 123
        with self.assertRaisesRegex(p.ProvenanceError, "different workflow"):
            self.report()


if __name__ == "__main__":
    unittest.main()
