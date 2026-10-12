"""Synthetic fail-closed checks: no Day 7 source admission by implication."""
import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from scripts.korea_day7_machine_preflight import EvidenceHold, EXPECTED, assess, main

CHECKED = datetime(2026, 10, 14, 0, 10, tzinfo=timezone.utc)


class KoreaDay7PreflightTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "desk": "korea", "as_of": "2026-10-13",
            "mode": "formal_commit_snapshot",
            "state_ref": "shadow/korea-policy-briefing",
            "state_commit": "a" * 40,
            "findings": [], "missing_successful_days": [], "review_holds": [],
            "historical_backfill_run_ids": [],
            "records": 5, "ledgers": 8, "qualifying_ledgers": 8,
            "input_hashes": {"state/shadow.db": "b" * 64},
            "human_review_completed": False, "promotion_authorized": False,
        }
        self.slots = {
            "schema": "ipr-shadow-slot-candidates/1",
            "source_slug": "kr_policy_mnd_releases",
            "state_branch": "shadow/korea-policy-briefing",
            "start_date": EXPECTED[0], "cron_utc": "17:47", "grace_hours": 6,
            "slots": [
                {"logical_date": day,
                 "status": "scheduled_success_no_new_records_candidate",
                 "observed_run_ids": [str(300001+i)+"-1"],
                 "new_record_count_is_not_publication_completeness": True}
                for i, day in enumerate(EXPECTED)
            ],
            "counts": {"candidate_supported": 7, "pending": 0,
                       "review_required": 0, "missing_from_supplied_evidence": 0},
            "unscoped_observations": [],
            "supplied_actions_export_authenticated": False,
            "source_capture_chain_verified_by_this_audit": False,
            "all_historical_scheduled_attempts_exhaustively_observed": False,
            "desk_production_eligible": False, "weekly_ai_writer_eligible": False,
            "editor_delivery_authorized": False, "writes": 0,
        }

    def test_good_supplied_machine_evidence_still_has_all_decision_holds(self):
        row = assess(self.report, self.slots, CHECKED)
        self.assertEqual(row["scheduled_slot_candidates_count"], 7)
        self.assertIn("ACTIONS_CENSUS_HELD", row["status"])
        for flag in ("authenticated_all_actions_attempts",
                     "independent_korean_human_review_completed",
                     "source_and_attachment_rights_approved",
                     "human_day7_signoff_completed", "production_eligible",
                     "sunday_brief_eligible", "new_public_references_approved"):
            self.assertIs(row[flag], False)

    def test_before_last_nominal_slot_and_six_hour_grace_refused(self):
        for moment in (
            datetime(2026, 10, 13, 16, 52, tzinfo=timezone.utc),
            datetime(2026, 10, 13, 17, 47, tzinfo=timezone.utc),
            datetime(2026, 10, 13, 23, 46, tzinfo=timezone.utc),
        ):
            with self.subTest(moment=moment), self.assertRaises(EvidenceHold):
                assess(self.report, self.slots, moment)

    def test_bad_formal_source_review_fails_closed(self):
        for key, value in (
            ("as_of", "2026-10-12"),
            ("mode", "rehearsal"),
            ("state_commit", "a"*39),
            ("findings", ["missing HWPX"]),
            ("missing_successful_days", ["2026-10-13"]),
            ("records", 4), ("qualifying_ledgers", 7),
            ("promotion_authorized", True), ("human_review_completed", True),
        ):
            with self.subTest(key=key):
                obj = copy.deepcopy(self.report)
                obj[key] = value
                with self.assertRaises(EvidenceHold):
                    assess(obj, self.slots, CHECKED)

    def test_missing_wrong_or_ambiguous_action_slot_fails_closed(self):
        cases = [
            lambda s: s["slots"].pop(),
            lambda s: s["slots"][0].update(status="pending_grace"),
            lambda s: s["slots"][0].update(status="explicit_manual_recovery_candidate"),
            lambda s: s["slots"][0].update(observed_run_ids=["999-2"]),
            lambda s: s["slots"][0].update(observed_run_ids=s["slots"][1]["observed_run_ids"]),
            lambda s: s["slots"][0].update(logical_date="2026-10-08"),
            lambda s: s["counts"].update(review_required=1),
            lambda s: s.update(cron_utc="17:17"),
            lambda s: s.update(supplied_actions_export_authenticated=True),
            lambda s: s.update(all_historical_scheduled_attempts_exhaustively_observed=True),
            lambda s: s.update(unscoped_observations=["unknown"]),
        ]
        for change in cases:
            with self.subTest(change=change):
                obj = copy.deepcopy(self.slots)
                change(obj)
                with self.assertRaises(EvidenceHold):
                    assess(self.report, obj, CHECKED)

    def test_cli_before_day7_writes_only_private_hold_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            review, slots, receipt = (root/"report.json", root/"slots.json",
                                     root/"held.json")
            review.write_text(json.dumps(self.report))
            slots.write_text(json.dumps(self.slots))
            with patch(
                    "scripts.korea_day7_machine_preflight.assess",
                    side_effect=EvidenceHold("sensitive Korean body")):
                rc = main(["--formal-review", str(review),
                           "--slot-candidates", str(slots),
                           "--receipt", str(receipt)])
            self.assertEqual(rc, 2)
            self.assertIn("HOLD_DAY7_MACHINE_EVIDENCE_INCOMPLETE",
                          receipt.read_text())
            self.assertNotIn("sensitive Korean body", receipt.read_text())
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
