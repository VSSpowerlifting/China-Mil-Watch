"""Korea's shared-workflow history must not be inferred from green ledgers."""
import copy
import unittest

from scripts import audit_indonesia_shadow_provenance as provenance
from scripts import audit_korea_actions_attempts as audit

NOW = "2026-10-07T23:55:00Z"


def action(ident, stamp, desk="korea", event="schedule", status="completed",
           conclusion="success", attempt=1):
    return {"id": ident, "run_attempt": attempt,
            "workflow_id": provenance.WORKFLOW_ID,
            "name": provenance.WORKFLOW_NAME, "event": event,
            "status": status, "conclusion": conclusion, "head_branch": "main",
            "created_at": stamp, "head_sha": "a" * 40}


def artifact(ident, desk="korea", attempt=1):
    return {"total_count": 1, "artifacts": [
        {"name": "candidate-shadow-%s-%d-%d" % (desk, ident, attempt)}]}


def ledger(ident, target, source, health="ok", result="ok_all_duplicates"):
    return {"desk": "korea", "run_id": ident,
            "target_date": target, "target_date_source": source,
            "health": health, "result": result}


class KoreaSharedActionsCensus(unittest.TestCase):
    def setUp(self):
        self.actions = [
            action(101, "2026-10-06T21:22:00Z", event="workflow_dispatch"),
            action(102, "2026-10-07T21:58:19Z", desk="indonesia"),
            action(103, "2026-10-07T22:17:12Z"),
        ]
        self.artifacts = {"101": artifact(101), "102": artifact(102, "indonesia"),
                          "103": artifact(103)}
        self.ledgers = [
            ledger(audit.LOCAL, "2026-10-06", "manual-utc-date", result="ok"),
            ledger("101-1", "2026-10-06", "manual-utc-date"),
            ledger("103-1", "2026-10-07", "schedule-slot"),
        ]

    def check(self, now=NOW):
        return audit.scan([{"total_count": len(self.actions),
                            "workflow_runs": self.actions}],
                          self.artifacts, self.ledgers, as_of_utc=now)

    def test_clean_korea_receipt_does_not_authenticate_or_approve_anything(self):
        r = self.check()
        self.assertEqual(r["verdict"], "CONSISTENT_UNAUTHENTICATED_CENSUS_ONLY")
        self.assertEqual(r["counts"]["korea_attempts"], 2)
        self.assertEqual(r["counts"]["indonesia_attempts"], 1)
        self.assertEqual(r["mature_scheduled_dates"], ["2026-10-07"])
        self.assertEqual(r["holds"], [])
        for name in ("github_export_independently_authenticated",
                     "human_day7_review_completed", "production_eligible",
                     "public_new_sources_approved", "sunday_brief_eligible"):
            self.assertIs(r[name], False)

    def test_not_yet_mature_slot_remains_pending(self):
        r = self.check("2026-10-08T18:00:00Z")
        self.assertEqual(r["verdict"], "PENDING_SCHEDULED_GRACE")
        self.assertEqual(r["pending_dates"], ["2026-10-08"])
        self.assertEqual(r["holds"], [])

    def test_mature_missing_day_is_a_hold(self):
        r = self.check("2026-10-08T23:48:00Z")
        self.assertEqual(r["verdict"], "HOLD")
        self.assertEqual(r["missing_dates"], ["2026-10-08"])

    def test_failed_korea_action_cannot_hide_behind_successful_ledger(self):
        self.actions.append(action(104, "2026-10-07T23:00:00Z",
                                   status="completed", conclusion="failure"))
        self.artifacts["104"] = artifact(104)
        r = self.check()
        self.assertIn("korea_failed_cancelled_or_unfinished_workflow", r["holds"])
        self.assertIn("korea_action_attempt_without_pinned_ledger", r["holds"])
        self.assertEqual(r["counts"]["korea_failed_or_cancelled"], 1)
        self.assertEqual(r["verdict"], "HOLD")

    def test_empty_artifact_on_shared_failed_run_is_unattributed_global_hold(self):
        self.actions.append(action(104, "2026-10-07T23:00:00Z",
                                   status="completed", conclusion="cancelled"))
        self.artifacts["104"] = {"total_count": 0, "artifacts": []}
        r = self.check()
        self.assertEqual(r["counts"]["unattributed_attempts"], 1)
        self.assertIn("shared_workflow_unattributed_attempt", r["holds"])

    def test_manual_recovery_never_proves_scheduled_day(self):
        self.actions[2]["event"] = "workflow_dispatch"
        self.ledgers[2]["target_date_source"] = "manual-utc-date"
        r = self.check()
        self.assertEqual(r["missing_dates"], ["2026-10-07"])
        self.assertEqual(r["verdict"], "HOLD")

    def test_late_start_just_after_midnight_maps_to_previous_nominal_slot(self):
        self.actions[2]["created_at"] = "2026-10-08T01:10:00Z"
        r = self.check("2026-10-08T02:00:00Z")
        self.assertEqual(r["verdict"], "PENDING_SCHEDULED_GRACE")
        self.assertEqual(r["holds"], [])

    def test_duplicate_scheduled_attempts_trigger_hold(self):
        self.actions.append(action(104, "2026-10-07T23:00:00Z"))
        self.artifacts["104"] = artifact(104)
        self.ledgers.append(ledger("104-1", "2026-10-07", "schedule-slot"))
        r = self.check()
        self.assertEqual(r["duplicate_dates"], ["2026-10-07"])
        self.assertEqual(r["verdict"], "HOLD")

    def test_rerun_requires_explicit_disposition_even_with_green_ledger(self):
        self.actions[2]["run_attempt"] = 2
        self.artifacts["103"] = artifact(103, attempt=2)
        self.ledgers[2]["run_id"] = "103-2"
        r = self.check()
        self.assertIn("korea_rerun_needs_attempt_history_review", r["holds"])

    def test_original_ledger_date_cannot_disagree_with_schedule_slot(self):
        self.ledgers[2]["target_date"] = "2026-10-06"
        self.assertIn("korea_schedule_slot_and_ledger_disagree",
                      self.check()["holds"])

    def test_missing_original_local_bootstrap_is_a_hold(self):
        self.ledgers.pop(0)
        self.assertIn("original_local_day_zero_missing_or_unhealthy",
                      self.check()["holds"])

    def test_unmapped_or_unhealthy_shadow_ledger_holds(self):
        self.ledgers.append(ledger("999-1", "2026-10-07", "schedule-slot"))
        self.assertIn("pinned_korea_ledger_absent_from_actions_inventory",
                      self.check()["holds"])
        self.ledgers.pop()
        self.ledgers[2]["health"] = "failed"
        self.assertIn("korea_ledger_not_a_successful_original_capture",
                      self.check()["holds"])

    def test_cross_desk_artifacts_and_pagination_are_refused(self):
        self.artifacts["103"] = {"total_count": 2, "artifacts": [
            artifact(103)["artifacts"][0],
            artifact(103, "indonesia")["artifacts"][0]]}
        with self.assertRaises(provenance.ProvenanceError):
            self.check()
        self.artifacts["103"] = artifact(103)
        self.artifacts.pop("102")
        with self.assertRaisesRegex(provenance.ProvenanceError, "every workflow"):
            self.check()
        self.artifacts["102"] = artifact(102, "indonesia")
        with self.assertRaisesRegex(provenance.ProvenanceError, "incomplete"):
            audit.scan([{"total_count": 4, "workflow_runs": self.actions}],
                       self.artifacts, self.ledgers, as_of_utc=NOW)


if __name__ == "__main__":
    unittest.main()
