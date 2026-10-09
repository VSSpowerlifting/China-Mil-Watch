"""Offline synthetic slot candidate tests: no publisher, network, state or writes."""
from __future__ import annotations

import copy
import unittest

from scripts import reconcile_shadow_slot_candidates as slots
from core.shadow_schedule import SOURCE_EXPLICIT, SOURCE_MANUAL, SOURCE_SCHEDULE


def contract():
    return {
        "source_slug": "id_kemhan_news",
        "state_branch": "shadow/indonesia-kemhan",
        "start_date": "2026-10-07", "cron_utc": "17:17", "grace_hours": 12,
    }


def run(run_id="37693074726-1", event="schedule", target="2026-10-07",
        started="2026-10-07T21:58:19Z", result="ok", new_records=3,
        source=SOURCE_SCHEDULE, **changes):
    row = {
        "source_slug": "id_kemhan_news",
        "state_branch": "shadow/indonesia-kemhan",
        "run_id": run_id,
        "target_date": target,
        "target_date_source": source,
        "github_event": event,
        "github_conclusion": "success",
        "ledger_health": "ok",
        "ledger_result": result,
        "started_utc": started,
        "finished_utc": started,
        "new_records": new_records,
        "action_identity_checked": True,
        "pinned_state_checked": True,
    }
    row.update(changes)
    return row


def assess(rows, as_of="2026-10-09T08:00:00Z", con=None):
    return slots.reconcile(contract() if con is None else con, rows, as_of)


def statuses(rows, **kwargs):
    return [x["status"] for x in assess(rows, **kwargs)["slots"]]


class CandidateSlots(unittest.TestCase):
    def test_schedule_success_with_records_is_only_candidate(self):
        report = assess([run()])
        self.assertEqual(report["slots"][0]["status"],
                         "scheduled_success_new_records_candidate")
        self.assertEqual(report["counts"]["candidate_supported"], 1)
        self.assertFalse(report["desk_production_eligible"])
        self.assertFalse(report["weekly_ai_writer_eligible"])
        self.assertFalse(report["supplied_actions_export_authenticated"])
        self.assertFalse(report["government_silence_established"])
        self.assertEqual(report["writes"], 0)

    def test_successful_no_publications_is_not_government_silence(self):
        row = run(result="ok_no_publications", new_records=0)
        report = assess([row])
        self.assertEqual(report["slots"][0]["status"],
                         "scheduled_success_no_new_records_candidate")
        self.assertTrue(report["slots"][0]["new_record_count_is_not_publication_completeness"])
        self.assertFalse(report["government_silence_established"])

    def test_delayed_cross_midnight_retains_nominal_schedule_slot(self):
        c = contract()
        c["cron_utc"] = "22:40"
        row = run(started="2026-10-08T01:15:00Z", target="2026-10-07")
        report = assess([row], con=c)
        self.assertEqual(report["slots"][0]["status"],
                         "scheduled_success_new_records_candidate")
        self.assertEqual(report["slots"][0]["logical_date"], "2026-10-07")

    def test_slot_not_overdue_until_grace_matures(self):
        self.assertEqual(statuses([], as_of="2026-10-07T23:00:00Z"),
                         ["pending_grace"])
        self.assertEqual(statuses([], as_of="2026-10-08T05:16:59Z"),
                         ["pending_grace", "pending_grace"])
        self.assertEqual(statuses([], as_of="2026-10-08T05:17:00Z"),
                         ["mature_slot_missing_from_supplied_evidence",
                          "pending_grace"])

    def test_mature_unobserved_does_not_claim_workflow_failed(self):
        report = assess([])
        self.assertGreater(report["counts"]["missing_from_supplied_evidence"], 0)
        self.assertFalse(report["all_historical_scheduled_attempts_exhaustively_observed"])
        self.assertFalse(report["automatic_recovery_dispatched"])

    def test_manual_implicit_target_never_recovers_slot(self):
        row = run(run_id="37700000000-1", event="workflow_dispatch",
                  source=SOURCE_MANUAL)
        self.assertEqual(statuses([row])[0], "only_nonqualifying_attempts_observed")

    def test_explicit_manual_target_can_be_recovery_candidate(self):
        row = run(run_id="37700000000-1", event="workflow_dispatch",
                  source=SOURCE_EXPLICIT)
        self.assertEqual(statuses([row])[0], "explicit_manual_recovery_candidate")

    def test_failed_scheduled_then_explicit_manual_recovery(self):
        failed = run(github_conclusion="failure", ledger_health="fail",
                     ledger_result="fail", new_records=0)
        recovery = run(run_id="37700000000-1", event="workflow_dispatch",
                       source=SOURCE_EXPLICIT)
        report = assess([failed, recovery])
        self.assertEqual(report["slots"][0]["status"],
                         "success_with_other_unresolved_attempt")
        self.assertEqual(report["counts"]["candidate_supported"], 0)

    def test_failed_only_is_not_success_even_with_new_records(self):
        failed = run(github_conclusion="failure", ledger_health="fail",
                     ledger_result="partial")
        self.assertEqual(statuses([failed])[0],
                         "attempt_present_but_not_attested_success")

    def test_unverified_success_is_not_counted(self):
        row = run(action_identity_checked=False)
        self.assertEqual(statuses([row])[0],
                         "attempt_present_but_not_attested_success")
        row["action_identity_checked"] = True
        row["pinned_state_checked"] = False
        self.assertEqual(statuses([row])[0],
                         "attempt_present_but_not_attested_success")

    def test_same_day_double_success_is_disputed(self):
        second = run(run_id="37700000000-1", event="workflow_dispatch",
                     source=SOURCE_EXPLICIT)
        self.assertEqual(statuses([run(), second])[0],
                         "conflicting_multiple_success_candidates")

    def test_scheduled_rerun_is_not_scheduled_success(self):
        row = run(run_id="37693074726-2", source=SOURCE_SCHEDULE)
        self.assertEqual(statuses([row])[0], "only_nonqualifying_attempts_observed")

    def test_scheduled_explicit_rerun_is_not_inferred_recovery(self):
        row = run(run_id="37693074726-2", source=SOURCE_EXPLICIT)
        self.assertEqual(statuses([row])[0], "only_nonqualifying_attempts_observed")

    def test_schedule_timestamp_mismatch_not_promoted(self):
        row = run(started="2026-10-08T22:01:00Z")
        self.assertEqual(statuses([row])[0], "only_nonqualifying_attempts_observed")

    def test_wrong_source_or_branch_never_cross_counts(self):
        for field, value in [
            ("source_slug", "kr_policy_mnd_releases"),
            ("state_branch", "shadow/korea-policy-briefing"),
        ]:
            with self.subTest(field=field):
                row = run()
                row[field] = value
                with self.assertRaisesRegex(slots.SlotEvidenceError, "identity mismatch"):
                    assess([row])

    def test_duplicate_attempt_identity_refused(self):
        with self.assertRaisesRegex(slots.SlotEvidenceError, "duplicate Actions"):
            assess([run(), copy.deepcopy(run())])

    def test_invalid_future_finished_timestamp_refused(self):
        with self.assertRaisesRegex(slots.SlotEvidenceError, "future"):
            assess([run(finished_utc="2026-10-10T00:00:00Z")])

    def test_naive_local_timestamp_refused(self):
        with self.assertRaisesRegex(slots.SlotEvidenceError, "zero-offset UTC"):
            assess([run(started_utc="2026-10-07T21:58:19")])

    def test_source_day_cannot_be_future_or_malformed(self):
        for day in ("2026-10-32", "2026-9-01", "2026-11-01"):
            with self.subTest(day=day), self.assertRaises(slots.SlotEvidenceError):
                assess([run(target_date=day)])

    def test_invalid_boolean_and_negative_record_count_refused(self):
        for patch in ({"action_identity_checked": "yes"},
                      {"pinned_state_checked": 1},
                      {"new_records": -1}):
            with self.subTest(patch=patch), self.assertRaises(slots.SlotEvidenceError):
                assess([run(**patch)])

    def test_explicit_source_on_schedule_never_claims_original_slot(self):
        self.assertEqual(statuses([run(source=SOURCE_EXPLICIT)])[0],
                         "only_nonqualifying_attempts_observed")

    def test_start_date_fixed_and_bounded(self):
        c = contract()
        c["start_date"] = "2026-09-01"
        with self.assertRaisesRegex(slots.SlotEvidenceError, "unbounded"):
            assess([], con=c)
        c["start_date"] = "2026-10-12"
        with self.assertRaises(slots.SlotEvidenceError):
            assess([], con=c)

    def test_noncanonical_contract_schedule_refused(self):
        c = contract()
        c["cron_utc"] = "17:99"
        with self.assertRaisesRegex(slots.SlotEvidenceError, "daily UTC"):
            assess([], con=c)

    def test_duplicate_unrelated_old_run_cannot_fill_report(self):
        older = run(target="2026-10-06", started="2026-10-06T21:58:19Z")
        report = assess([older])
        self.assertEqual(report["unscoped_observations"], [older["run_id"]])
        self.assertEqual(report["slots"][0]["status"],
                         "mature_slot_missing_from_supplied_evidence")

    def test_observation_list_is_bounded(self):
        with self.assertRaisesRegex(slots.SlotEvidenceError, "unbounded"):
            assess([run()] * 501)


if __name__ == "__main__":
    unittest.main()
