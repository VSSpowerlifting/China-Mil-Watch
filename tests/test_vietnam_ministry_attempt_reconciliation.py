"""Synthetic tests for Vietnam three-source Actions/ledger attempt reconciliation."""
import copy
import json
import unittest

from scripts.vietnam_ministry_attempt_reconciliation import (
    SCHEMA, SOURCES, WORKFLOW, AttemptEvidenceRefused, reconcile, strict_json,
)


def action(run=37700200951, attempt=1, event="schedule", conclusion="success",
           target="2026-10-07"):
    return {
        "run_id": run, "run_attempt": attempt, "event": event,
        "conclusion": conclusion,
        "run_url": "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/%d" % run,
        "target_date": target,
        "target_date_basis": (
            None if target is None else
            "verified_schedule_slot" if event == "schedule" else "verified_dispatch_input"
        ),
    }


def ledger(run="37700200951-1", result="ok", target="2026-10-07",
           source="schedule-slot", at="2026-10-07T23:06:07+00:00"):
    return {
        "run_id": run, "result": result, "health": "ok", "target_date": target,
        "target_date_source": source, "collector_commit": "a" * 40,
        "finished_utc": at,
    }


def packet():
    p = {
        "schema": SCHEMA, "workflow": WORKFLOW,
        "review_window": {"from": "2026-10-07", "through": "2026-10-14"},
        "expected_target_dates": ["2026-10-07"],
        "github_attempts": [action()],
        "source_ledgers": {},
    }
    for i, (slug, branch) in enumerate(sorted(SOURCES.items())):
        r = ledger(at="2026-10-07T23:06:%02d+00:00" % (7+i),
                   result=("ok" if i == 0 else "ok_no_publications"))
        p["source_ledgers"][slug] = {
            "state_branch": branch, "state_commit": ("%040x" % (i+1)),
            "runs": [r],
        }
    return p


class AttemptReconciliationTests(unittest.TestCase):
    def test_successful_triplet_matches_without_forging_completeness(self):
        output = reconcile(packet())
        self.assertEqual(output["github_attempts_supplied"], 1)
        self.assertEqual(output["per_source_ledger_counts"],
                         {slug: 1 for slug in sorted(SOURCES)})
        self.assertEqual(output["warnings"], [])
        self.assertFalse(output["github_attempt_inventory_independently_proven_exhaustive"])
        self.assertFalse(output["failed_attempt_artifacts_independently_verified"])
        self.assertFalse(output["day_7_human_signoff_complete"])
        self.assertFalse(output["desk_qualified"])
        self.assertFalse(output["production_promotion_authorized"])

    def test_failed_initial_attempt_is_visible_not_silently_discarded(self):
        data = packet()
        data["github_attempts"].insert(0, action(
            37656171920, 1, "workflow_dispatch", "failure", None))
        data["github_attempts"].insert(1, action(
            37656171920, 2, "workflow_dispatch", "success", "2026-10-07"))
        for slug, value in data["source_ledgers"].items():
            value["runs"].insert(0, ledger(
                "37656171920-2", target="2026-10-07", source="explicit",
                at="2026-10-07T17:16:33+00:00"))
        output = reconcile(data)
        self.assertEqual([w["kind"] for w in output["warnings"]],
                         ["non_successful_workflow_attempt"])
        self.assertEqual(output["warnings"][0]["run_id"], "37656171920-1")

    def test_successfully_completed_actions_run_missing_moit_publication(self):
        data = packet()
        slug = "vn_moit_energy_vi"
        data["source_ledgers"][slug]["runs"] = []
        output = reconcile(data)
        kinds = [x["kind"] for x in output["warnings"]]
        self.assertIn("successful_workflow_missing_source_ledger", kinds)
        self.assertIn("expected_day_without_fully_evidenced_three_source_attempt", kinds)
        self.assertIn("source_latest_committed_attempts_diverge", kinds)

    def test_state_published_despite_failed_job_flagged_for_review(self):
        data = packet()
        data["github_attempts"][0]["conclusion"] = "failure"
        out = reconcile(data)
        self.assertEqual(
            sum(x["kind"] == "published_state_for_non_successful_workflow"
                for x in out["warnings"]), 3)
        self.assertTrue(any(x["kind"] == "non_successful_workflow_attempt"
                            for x in out["warnings"]))
        self.assertFalse(out["all_scheduled_slots_proven_complete"])

    def test_ledger_without_action_receipt_never_silently_accepted(self):
        data = packet()
        data["github_attempts"] = []
        data["expected_target_dates"] = []
        warnings = reconcile(data)["warnings"]
        self.assertEqual(sum(x["kind"] == "source_ledger_missing_actions_receipt"
                             for x in warnings), 3)

    def test_latest_source_run_mismatch_flagged_even_after_valid_history(self):
        data = packet()
        slug = "vn_moit_energy_vi"
        data["source_ledgers"][slug]["runs"].append(
            ledger("37710000000-1", target="2026-10-08",
                   at="2026-10-08T23:06:00+00:00"))
        data["github_attempts"].append(action(37710000000, target="2026-10-08"))
        result = reconcile(data)
        kinds = [x["kind"] for x in result["warnings"]]
        self.assertIn("successful_workflow_missing_source_ledger", kinds)
        self.assertIn("source_latest_committed_attempts_diverge", kinds)

    def test_target_date_claim_cannot_hide_schedule_dispatch_disagreement(self):
        data = packet()
        data["github_attempts"][0]["target_date_basis"] = "verified_dispatch_input"
        with self.assertRaisesRegex(AttemptEvidenceRefused, "target-date provenance"):
            reconcile(data)
        data = packet()
        data["source_ledgers"]["vn_mps_foreign_affairs_vi"]["runs"][0]["target_date_source"] = "explicit"
        with self.assertRaisesRegex(AttemptEvidenceRefused, "basis disagrees"):
            reconcile(data)

    def test_source_and_action_logical_day_must_agree_when_both_grounded(self):
        data = packet()
        data["source_ledgers"]["vn_mps_foreign_affairs_vi"]["runs"][0]["target_date"] = "2026-10-08"
        with self.assertRaisesRegex(AttemptEvidenceRefused, "logical day disagrees"):
            reconcile(data)

    def test_target_unverified_generates_warning_without_guessing_from_utc(self):
        data = packet()
        data["github_attempts"][0]["target_date"] = None
        data["github_attempts"][0]["target_date_basis"] = None
        data["expected_target_dates"] = []
        warnings = reconcile(data)["warnings"]
        self.assertEqual(sum(x["kind"] == "actions_target_date_unverified"
                             for x in warnings), 3)
        self.assertFalse(reconcile(data)["all_scheduled_slots_proven_complete"])

    def test_scheduled_rerun_cannot_be_presented_as_clean(self):
        data = packet()
        data["github_attempts"].append(action(37700200951, 2, target="2026-10-07"))
        warnings = reconcile(data)["warnings"]
        self.assertIn("scheduled_workflow_rerun_requires_review",
                      [x["kind"] for x in warnings])

    def test_malicious_duplicate_evidence_identity_refused(self):
        data = packet()
        data["github_attempts"].append(copy.deepcopy(data["github_attempts"][0]))
        with self.assertRaisesRegex(AttemptEvidenceRefused, "duplicate GitHub run attempt"):
            reconcile(data)
        data = packet()
        k = next(iter(SOURCES))
        data["source_ledgers"][k]["runs"].append(copy.deepcopy(data["source_ledgers"][k]["runs"][0]))
        with self.assertRaisesRegex(AttemptEvidenceRefused, "duplicate/bad"):
            reconcile(data)

    def test_wrong_branch_and_production_source_refused(self):
        data = packet()
        data["source_ledgers"]["vn_moit_energy_vi"]["state_branch"] = "shadow/vietnam"
        with self.assertRaisesRegex(AttemptEvidenceRefused, "source state branch"):
            reconcile(data)
        data = packet()
        data["source_ledgers"]["vn_national_defence_journal_en"] = {
            "state_branch": "shadow/vietnam_journal", "state_commit": "1"*40, "runs": []}
        with self.assertRaisesRegex(AttemptEvidenceRefused, "exactly three"):
            reconcile(data)

    def test_broken_url_date_and_hash_refused(self):
        data = packet()
        data["github_attempts"][0]["run_url"] = "https://example.com/actions/runs/37700200951"
        with self.assertRaisesRegex(AttemptEvidenceRefused, "URL mismatches"):
            reconcile(data)
        data = packet()
        data["review_window"]["through"] = "2026-02-30"
        with self.assertRaisesRegex(AttemptEvidenceRefused, "invalid calendar"):
            reconcile(data)
        data = packet()
        data["source_ledgers"]["vn_moit_energy_vi"]["state_commit"] = "bad"
        with self.assertRaisesRegex(AttemptEvidenceRefused, "source state branch"):
            reconcile(data)

    def test_input_timestamp_requires_explicit_utc(self):
        data = packet()
        data["source_ledgers"]["vn_mps_foreign_affairs_vi"]["runs"][0]["finished_utc"] = "2026-10-07T23:06:07"
        with self.assertRaisesRegex(AttemptEvidenceRefused, "explicit UTC"):
            reconcile(data)

    def test_duplicate_raw_json_fields_refused(self):
        with self.assertRaisesRegex(AttemptEvidenceRefused, "duplicate evidence JSON key"):
            strict_json('{"run_id":1,"run_id":2}')

    def test_no_publisher_access_or_local_writes(self):
        import inspect
        from scripts import vietnam_ministry_attempt_reconciliation as module
        source = inspect.getsource(module)
        for forbidden in ("requests.", "urllib.request", "subprocess.", "sqlite3",
                          "write_text(", "open(", "datetime.now(", "git push"):
            with self.subTest(value=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
