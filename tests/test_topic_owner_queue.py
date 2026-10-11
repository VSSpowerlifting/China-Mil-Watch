"""Adversarial checks of the provisional, never-approved owner review queue."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_topic_owner_queue import (  # noqa: E402
    ASSESSMENT,
    LEDGER,
    QUEUE,
    OwnerQueueError,
    _blob_sha,
    validate,
    validate_files,
)


class OwnerDecisionQueueContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw_ledger = LEDGER.read_bytes()
        raw_assessment = ASSESSMENT.read_bytes()
        cls.ledger = json.loads(raw_ledger.decode("utf-8"))
        cls.assessment = json.loads(raw_assessment.decode("utf-8"))
        cls.ledger_sha = _blob_sha(raw_ledger)
        cls.assessment_sha = _blob_sha(raw_assessment)
        cls.queue = json.loads(QUEUE.read_text(encoding="utf-8"))

    def source_check(self, queue):
        return validate(
            queue, self.ledger, self.assessment,
            self.ledger_sha, self.assessment_sha,
        )

    def assert_rejected(self, queue, reason):
        with self.assertRaisesRegex(OwnerQueueError, reason):
            self.source_check(queue)

    def fixture(self):
        return copy.deepcopy(self.queue)

    def first_case(self, queue):
        return queue["clusters"][0]["items"][0]

    def test_exact_saved_queue_validates_and_stays_unapproved(self):
        result = validate_files()
        self.assertEqual(result["case_count"], 19)
        self.assertEqual(result["group_count"], 7)
        self.assertEqual(result["human_decisions"], 0)
        self.assertTrue(result["all_source_pins_match"])
        self.assertFalse(result["production_writes"])

    def test_source_blobs_are_pinned_by_actual_git_hashes(self):
        refs = self.queue["source_refs"]
        self.assertEqual(refs["ledger_blob_sha"], self.ledger_sha)
        self.assertEqual(refs["assessment_blob_sha"], self.assessment_sha)

    def test_missing_one_case_refused(self):
        q = self.fixture()
        q["clusters"][0]["items"].pop()
        self.assert_rejected(q, "group record count differs")

    def test_duplicate_case_refused(self):
        q = self.fixture()
        q["clusters"][1]["items"][0]["pilot_id"] = "P01"
        self.assert_rejected(q, "duplicated, missing or reordered")

    def test_swapped_grouping_is_refused(self):
        q = self.fixture()
        q["clusters"][0]["ids"] = ["P05"]
        self.assert_rejected(q, "frozen policy case grouping")

    def test_missing_group_or_unknown_group_refused(self):
        q = self.fixture()
        q["clusters"].pop()
        self.assert_rejected(q, "expected seven editorial policy groups")
        q = self.fixture()
        q["clusters"][0]["key"] = "new_production_review"
        self.assert_rejected(q, "duplicate or unfamiliar policy cluster")

    def test_source_url_and_desk_tampering_are_refused(self):
        for key, value in [
            ("source_url", "https://fabricated.invalid/source"),
            ("desk_id", "russia"),
            ("source_date", "2001-01-01"),
            ("original_title", "invented title"),
            ("body_sha256", "0" * 64),
        ]:
            with self.subTest(key=key):
                q = self.fixture()
                self.first_case(q)[key] = value
                self.assert_rejected(q, "source provenance altered")

    def test_model_suggestions_cannot_be_edited_into_gold(self):
        for key, value in [
            ("initial_model_topics", ["human_approved"]),
            ("second_model_topics", []),
            ("owner_question", "No review needed"),
        ]:
            with self.subTest(key=key):
                q = self.fixture()
                self.first_case(q)[key] = value
                self.assert_rejected(q, "model suggestions have changed"
                                     if key != "owner_question" else
                                     "editorial question changed")

    def test_fabricated_approval_metadata_is_refused(self):
        for key, value in [
            ("owner_decision", "accept"),
            ("decision_rationale", "synthetic evidence"),
            ("reviewer", "not an actual human review"),
            ("reviewed_at_utc", "2026-10-08T03:00:00Z"),
        ]:
            with self.subTest(key=key):
                q = self.fixture()
                self.first_case(q)[key] = value
                self.assert_rejected(q, "no human may be manufactured")

    def test_queue_cannot_switch_to_complete(self):
        q = self.fixture()
        q["owner_review_complete"] = True
        self.assert_rejected(q, "completed/approved review")
        q = self.fixture()
        q["status"] = "approved_for_backfill"
        self.assert_rejected(q, "completed/approved review")

    def test_production_activation_flags_are_fail_closed(self):
        for key in ["production_assignment", "human_gold_labels",
                    "vocabulary_activation"]:
            with self.subTest(key=key):
                q = self.fixture()
                q["workflow_boundaries"][key] = True
                self.assert_rejected(q, "improperly authorizes")

    def test_changed_source_blob_pins_are_refused(self):
        for key in ["ledger_blob_sha", "assessment_blob_sha"]:
            with self.subTest(key=key):
                q = self.fixture()
                q["source_refs"][key] = "0" * 40
                self.assert_rejected(q, "frozen Git blob pin mismatch")

    def test_model_pilot_must_remain_explicitly_not_human_approved(self):
        review = copy.deepcopy(self.assessment)
        review["human_approved"] = True
        with self.assertRaisesRegex(OwnerQueueError, "approval state changed"):
            validate(
                self.fixture(), self.ledger, review,
                self.ledger_sha, self.assessment_sha,
            )

    def test_extra_label_or_auto_import_flag_is_refused(self):
        q = self.fixture()
        self.first_case(q)["db_assignment"] = ["gray_zone_coast_guard"]
        self.assert_rejected(q, "extra/missing fields")

    def test_editor_only_queue_must_not_masquerade_as_blind_review(self):
        q = self.fixture()
        q["purpose"] = "Independent reader packet"
        self.assert_rejected(q, "NOT suitable for blind review")

    def test_immutable_original_ledger_dispute_count(self):
        revised = copy.deepcopy(self.assessment)
        # Delete one issue, but leave record and its other fields untouched.
        first = next(
            row for row in revised["records"]
            if row["pilot_id"] == "P01"
        )
        first["owner_question"] = None
        with self.assertRaisesRegex(OwnerQueueError,
                                    "source owner-question count changed"):
            validate(
                self.fixture(), self.ledger, revised,
                self.ledger_sha, self.assessment_sha,
            )

    def test_duplicate_input_assessment_id_is_refused(self):
        revised = copy.deepcopy(self.assessment)
        revised["records"][1]["pilot_id"] = revised["records"][0]["pilot_id"]
        with self.assertRaisesRegex(OwnerQueueError, "duplicate ID"):
            validate(
                self.fixture(), self.ledger, revised,
                self.ledger_sha, self.assessment_sha,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
