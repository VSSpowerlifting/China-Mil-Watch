"""Day 7 machine-only evidence acceptance: no signoff by implication."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts.indonesia_day7_machine_checkpoint import (
    DAY7, Day7Error, EXPECTED_DAYS, checkpoint, main,
)


class Day7MachineOnlyContracts(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.when = datetime(2026, 10, 14, 4, 7, tzinfo=timezone.utc)
        self.review = {
            "desk": "indonesia", "as_of": DAY7, "mode": "formal_commit_snapshot",
            "state_commit": self.sha, "state_ref": "shadow/indonesia-kemhan",
            "records": 27, "ledgers": 9, "qualifying_ledgers": 9,
            "findings": [], "missing_successful_days": [],
            "historical_backfill_run_ids": [], "review_holds": [],
            "human_review_completed": False, "promotion_authorized": False,
            "input_hashes": {"state/shadow.db": "b" * 64},
        }
        self.census = {
            "schema": "ipr-indonesia-authenticated-actions-census/1",
            "as_of": DAY7, "pinned_state_commit": self.sha,
            "source_workflow_id": 376840713,
            "source": "authenticated_repository_GitHub_Actions_API",
            "rights_approved": False,
            "independent_original_language_review": False,
            "production_eligible": False,
            "public_article_release_authorized": False,
            "result": {
                "schema": "ipr-indonesia-shared-actions-attempt-inventory/1",
                "verdict": "CONSISTENT_THROUGH_AS_OF_NOT_DAY7_SIGNOFF",
                "holds": [], "missing_scheduled_indonesia_days": [],
                "duplicate_scheduled_indonesia_days": [],
                "pinned_ledger_unmapped_count": 0,
                "scheduled_indonesia_days_observed": EXPECTED_DAYS,
                "run_listing_pagination_count_verified": True,
                "all_attempt_artifact_pages_count_verified": True,
                "counts": {
                    "indonesia_attempts": 8,
                    "indonesia_failures_or_cancellations": 0,
                    "indonesia_rerun_attempts": 0,
                    "indonesia_success_without_pinned_ledger": 0,
                    "ambiguous_shared_failures": 0,
                    "shared_unselected_attempts": 0,
                },
                "independent_human_source_review_completed": False,
                "day7_human_checkpoint_completed": False,
                "publication_authorized": False, "production_eligible": False,
            },
        }

    def validate(self, review=None, census=None, when=None):
        return checkpoint(review if review is not None else self.review,
                          census if census is not None else self.census,
                          self.sha, now=when if when is not None else self.when)

    def test_good_machine_data_never_authorizes_source_publication(self):
        result = self.validate()
        self.assertEqual(result["status"],
                         "MACHINE_EVIDENCE_CONSISTENT_HUMAN_REVIEW_PENDING")
        self.assertEqual(result["qualifying_ledgers"], 9)
        self.assertEqual(result["stored_private_originals"], 27)
        self.assertEqual(result["scheduled_dates_verified"], 7)
        self.assertEqual(result["indonesia_actions_attempts_verified"], 8)
        self.assertFalse(result["human_day7_signoff_completed"])
        self.assertFalse(result["qualified_for_production"])
        self.assertFalse(result["new_public_citations_approved"])
        self.assertTrue(result["publisher_geography_anomaly_still_held"])

    def test_early_evening_or_before_seventh_collection_is_a_hold(self):
        before = datetime(2026, 10, 13, 16, 52, 14, tzinfo=timezone.utc)
        with self.assertRaisesRegex(Day7Error, "before required collection slot"):
            self.validate(when=before)
        before_run = datetime(2026, 10, 13, 17, 16, 59, tzinfo=timezone.utc)
        with self.assertRaisesRegex(Day7Error, "before required collection slot"):
            self.validate(when=before_run)
        after = datetime(2026, 10, 13, 18, 10, tzinfo=timezone.utc)
        self.assertEqual(self.validate(when=after)["scheduled_dates_verified"], 7)

    def test_missing_or_duplicate_schedule_is_not_a_complete_day7(self):
        mutations = [
            lambda r: r["result"].update(scheduled_indonesia_days_observed=EXPECTED_DAYS[:-1]),
            lambda r: r["result"].update(missing_scheduled_indonesia_days=[DAY7]),
            lambda r: r["result"].update(duplicate_scheduled_indonesia_days=[DAY7]),
            lambda r: r["result"].update(holds=["unattributed_shared_workflow_attempt"]),
            lambda r: r["result"].update(verdict="HOLD"),
            lambda r: r["result"].update(pinned_ledger_unmapped_count=1),
            lambda r: r["result"]["counts"].update(indonesia_failures_or_cancellations=1),
            lambda r: r["result"]["counts"].update(shared_unselected_attempts=1),
            lambda r: r["result"]["counts"].update(indonesia_attempts=7),
            lambda r: r["result"].update(all_attempt_artifact_pages_count_verified=False),
        ]
        for mutation in mutations:
            census = copy.deepcopy(self.census)
            mutation(census)
            with self.subTest(mutation=mutation), self.assertRaises(Day7Error):
                self.validate(census=census)

    def test_copied_content_or_false_human_source_clearance_is_refused(self):
        mutations = [
            lambda r: r.update(findings=["original capture changed"]),
            lambda r: r.update(missing_successful_days=["2026-10-13"]),
            lambda r: r.update(review_holds=["publisher drift"]),
            lambda r: r.update(records=23),
            lambda r: r.update(qualifying_ledgers=8),
            lambda r: r.update(state_commit="f" * 40),
            lambda r: r.update(human_review_completed=True),
            lambda r: r.update(promotion_authorized=True),
            lambda r: r.update(as_of="2026-10-11"),
            lambda r: r["input_hashes"].update({"state/shadow.db": "bad"}),
        ]
        for mutation in mutations:
            report = copy.deepcopy(self.review)
            mutation(report)
            with self.subTest(mutation=mutation), self.assertRaises(Day7Error):
                self.validate(review=report)
        for field in ("rights_approved", "production_eligible",
                      "independent_original_language_review",
                      "public_article_release_authorized"):
            census = copy.deepcopy(self.census)
            census[field] = True
            with self.subTest(field=field), self.assertRaises(Day7Error):
                self.validate(census=census)

    def test_cli_failure_is_count_only_hold_not_exception(self):
        with tempfile.TemporaryDirectory(prefix="ipr-id-day7-") as td:
            home = Path(td)
            a = home / "review.json"
            b = home / "census.json"
            receipt = home / "receipt.json"
            a.write_text(json.dumps(self.review))
            b.write_text(json.dumps(self.census))
            with mock.patch(
                "scripts.indonesia_day7_machine_checkpoint.checkpoint",
                side_effect=Day7Error("confidential source bytes"),
            ):
                code = main(["--review-report", str(a),
                             "--census-report", str(b),
                             "--state-commit", self.sha,
                             "--receipt", str(receipt)])
            self.assertEqual(code, 2)
            value = receipt.read_text()
            self.assertIn("HOLD_DAY7_MACHINE_EVIDENCE_INCOMPLETE", value)
            self.assertNotIn("confidential source bytes", value)
            self.assertNotIn("source_body", value)


if __name__ == "__main__":
    unittest.main()
