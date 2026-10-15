"""Synthetic no-network AFP GitHub attempt and job provenance checks."""
import unittest
from copy import deepcopy
from datetime import date, timedelta
from scripts.audit_ph_afp_attempt_history import (
    AttemptAuditError, WORKFLOW_ID, WORKFLOW_NAME, read_runs, validate,
)


def fixture():
    first = date(2026, 10, 7)
    runs, histories, slots = [], {}, []
    for i in range(7):
        rid = 70001 + i
        day = (first + timedelta(days=i)).isoformat()
        row = dict(id=rid, workflow_id=WORKFLOW_ID, name=WORKFLOW_NAME,
                   event="schedule", head_branch="main", head_sha="a"*40,
                   created_at=day+"T12:00:00Z", status="completed",
                   conclusion="success", run_attempt=1)
        runs.append(row)
        histories[rid] = {1: {
            "run": dict(row),
            "job_pages": [{"total_count": 1, "jobs": [
                {"id": 80001+i, "run_id": rid, "run_attempt": 1,
                 "status": "completed", "conclusion": "success"}]}]}}
        slots.append({"date": day, "run_id": "%d-1" % rid,
                      "status": "actions_success_matches_ledger"})
    return ([{"total_count": len(runs), "workflow_runs": runs}],
            histories,
            {"protocol": "ipr_ph_afp_actions_positive_match_v1",
             "github_workflow_id": WORKFLOW_ID,
             "all_seven_positive_runs_matched": True,
             "no_unmatched_scheduled_runs_visible_in_review_window": True,
             "slots": slots})


class BoundedAttemptJobAuditTests(unittest.TestCase):
    def check(self, inputs):
        pages, histories, assessment = inputs
        return validate(read_runs(pages, "2026-10-14"), histories, assessment)

    def test_genuine_positive_attempt_receipts_remain_nonapproving(self):
        result = self.check(fixture())
        self.assertEqual(result["verified_visible_run_attempts"], 7)
        self.assertEqual(result["verified_visible_attempt_jobs"], 7)
        self.assertTrue(result["seven_positive_first_attempt_jobs_verified"])
        for field in ("deleted_or_missing_historical_runs_exhaustively_verified",
                      "human_source_reviews_approved", "source_rights_approved",
                      "production_admission_authorized",
                      "weekly_model_email_or_publication_authorized"):
            self.assertFalse(result[field])

    def test_prior_retry_attempt_cannot_disappear(self):
        pages, histories, assessment = fixture()
        pages[0]["workflow_runs"][0]["run_attempt"] = 2
        with self.assertRaises(AttemptAuditError):
            self.check((pages, histories, assessment))

    def test_job_failure_on_positive_slot_refused(self):
        pages, histories, assessment = fixture()
        histories[70001][1]["job_pages"][0]["jobs"][0]["conclusion"] = "failure"
        with self.assertRaises(AttemptAuditError):
            self.check((pages, histories, assessment))

    def test_job_attached_to_wrong_attempt_refused(self):
        pages, histories, assessment = fixture()
        histories[70001][1]["job_pages"][0]["jobs"][0]["run_attempt"] = 2
        with self.assertRaises(AttemptAuditError):
            self.check((pages, histories, assessment))

    def test_missing_job_page_refused(self):
        pages, histories, assessment = fixture()
        histories[70001][1]["job_pages"][0]["total_count"] = 2
        with self.assertRaises(AttemptAuditError):
            self.check((pages, histories, assessment))

    def test_wrong_head_sha_refused(self):
        pages, histories, assessment = fixture()
        histories[70001][1]["run"]["head_sha"] = "b" * 40
        with self.assertRaises(AttemptAuditError):
            self.check((pages, histories, assessment))

    def test_duplicate_scheduled_date_refused(self):
        pages, histories, assessment = fixture()
        assessment["slots"][1]["date"] = "2026-10-07"
        with self.assertRaises(AttemptAuditError):
            self.check((pages, histories, assessment))

    def test_hidden_extra_scheduled_run_refused(self):
        pages, histories, assessment = fixture()
        extra = dict(pages[0]["workflow_runs"][0])
        extra.update(id=99991, conclusion="failure")
        pages[0]["workflow_runs"].append(extra)
        pages[0]["total_count"] += 1
        histories[99991] = {1: {"run": dict(extra),
            "job_pages": [{"total_count": 1, "jobs": [{
                "id": 99001, "run_id": 99991, "run_attempt": 1,
                "status": "completed", "conclusion": "failure"}]}]}}
        with self.assertRaises(AttemptAuditError):
            self.check((pages, histories, assessment))

    def test_manual_failed_run_is_audited_but_not_counted_as_day(self):
        pages, histories, assessment = fixture()
        extra = dict(pages[0]["workflow_runs"][0])
        extra.update(id=99991, event="workflow_dispatch", conclusion="failure")
        pages[0]["workflow_runs"].append(extra)
        pages[0]["total_count"] += 1
        histories[99991] = {1: {"run": dict(extra),
            "job_pages": [{"total_count": 1, "jobs": [{
                "id": 99001, "run_id": 99991, "run_attempt": 1,
                "status": "completed", "conclusion": "failure"}]}]}}
        self.assertEqual(self.check((pages, histories, assessment))
                         ["verified_visible_run_attempts"], 8)

    def test_invalid_bounds_or_partial_run_export_refused(self):
        pages, histories, assessment = fixture()
        with self.assertRaises(AttemptAuditError):
            read_runs(pages, "2026-10-10")
        pages[0]["total_count"] += 1
        with self.assertRaises(AttemptAuditError):
            self.check((pages, histories, assessment))


if __name__ == "__main__":
    unittest.main()
