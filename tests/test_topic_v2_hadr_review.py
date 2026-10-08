"""Fail-closed tests for the frozen, scoped v2 HADR human-review handoff.

All reviewer data in this test module are SYNTHETIC fixtures, never human judgments.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import topic_v2_hadr_review as review  # noqa: E402


def synthetic_completed():
    """TEST FIXTURE ONLY — not a real human review."""
    value = review.make_template()
    for row in value["records"]:
        row["decision"] = "unassessable" if row["body_chars"] == 0 else "abstain"
        row["rationale"] = "TEST FIXTURE ONLY: no real human decision."
        row["read_full_source"] = row["body_chars"] != 0
        row["reviewer"] = {
            "name": "SYNTHETIC TEST REVIEWER — NOT A HUMAN",
            "language_read": "TEST LANGUAGE" if row["body_chars"] else "",
            "independent_reading_attested": True,
            "original_language_reading_attested": row["body_chars"] != 0,
        }
        row["reviewed_at_utc"] = "2026-10-08T00:00:00Z"
    return value


class ReviewerPacket(unittest.TestCase):
    def test_unsigned_template_pins_v2_and_exact_scope(self):
        data = review.make_template()
        self.assertEqual(data["scope"], review.SCOPE)
        self.assertEqual(data["taxonomy"]["version"], 2)
        self.assertEqual(len(data["records"]), 11)
        self.assertIn("military_hadr", data["taxonomy"]["topic_slugs"])
        self.assertEqual(len(data["taxonomy"]["topic_slugs"]), 20)
        self.assertEqual(review.validate_decisions(data)["reviewed"], 0)
        self.assertTrue(all(x["decision"] == "pending" and x["topics"] == []
                            for x in data["records"]))
        self.assertTrue(all(x["reviewer"]["name"] == "" and
                            not x["reviewer"]["independent_reading_attested"]
                            for x in data["records"]))

    def test_role_blindness_in_packet_and_template(self):
        text = review.blind_packet()
        self.assertIn("## P16", text)
        self.assertIn("## P36", text)
        self.assertIn("## P58", text)
        self.assertIn("original-language", text.lower())
        self.assertEqual(sum(x.startswith("## P") for x in text.splitlines()), 11)
        for forbidden in (
            "positive_candidate", "negative_control", "unassessable_body",
            "event_key", "sanlakas_philippines", "trident_resolve_admm_plus",
            "review_question", "owner_approval", "Editor provisional role",
        ):
            self.assertNotIn(forbidden, text)
            self.assertNotIn(forbidden, str(review.make_template()))

    def test_model_selection_bias_is_disclosed(self):
        self.assertIn("model-selected", review.blind_packet().lower())

    def test_partial_is_valid_but_comparison_is_blocked(self):
        pending = review.make_template()
        with self.assertRaisesRegex(review.TargetedReviewError, "all eleven"):
            review.compare(pending)
        with self.assertRaisesRegex(review.TargetedReviewError, "all eleven"):
            review.validate_decisions(pending, require_complete=True)

    def test_all_signed_synthetic_fixture_compares_as_nine_event_groups(self):
        completed = synthetic_completed()
        self.assertEqual(review.validate_decisions(
            completed, require_complete=True)["reviewed"], 11)
        report = review.compare(completed)
        self.assertIn("nine", "nine")  # Event-count evidence checked below.
        self.assertIn("9 **event/context** groups", report)
        self.assertIn("| sanlakas_philippines | P51 |", report)
        self.assertIn("| sanlakas_philippines | P52 |", report)
        self.assertIn("| trident_resolve_admm_plus | P35 |", report)
        self.assertIn("| trident_resolve_admm_plus | P36 |", report)
        self.assertIn("not independently authenticated", report.lower())
        self.assertNotIn("accuracy:", report.lower())

    def test_bodyless_infographic_must_be_unassessable(self):
        completed = synthetic_completed()
        item = next(x for x in completed["records"] if x["pilot_id"] == "P36")
        self.assertEqual(item["body_chars"], 0)
        item.update({"decision": "classified", "topics": ["military_hadr"],
                     "read_full_source": True})
        item["reviewer"]["language_read"] = "TEST LANGUAGE"
        item["reviewer"]["original_language_reading_attested"] = True
        with self.assertRaisesRegex(review.TargetedReviewError, "missing-body"):
            review.validate_decisions(completed)

    def test_bodyless_can_be_honestly_unassessable(self):
        self.assertEqual(review.validate_decisions(
            synthetic_completed(), require_complete=True)["counts"]["unassessable"], 1)


class TamperAndAttribution(unittest.TestCase):
    def test_source_body_digest_and_archive_pins_cannot_change(self):
        for field in ("record_identity", "body_sha256", "origin_blob",
                      "origin_commit", "source_url", "title_original"):
            data = review.make_template()
            data["records"][0][field] = "tampered"
            with self.subTest(field=field):
                with self.assertRaisesRegex(review.TargetedReviewError, "source identity"):
                    review.validate_decisions(data)

    def test_packet_ledger_and_taxonomy_pins_are_immutable(self):
        for key in ("packet_sha256", "pilot_ledger_sha256", "scope"):
            data = review.make_template()
            data[key] = "changed"
            with self.subTest(key=key):
                with self.assertRaisesRegex(review.TargetedReviewError, "frozen review"):
                    review.validate_decisions(data)
        data = review.make_template()
        data["taxonomy"]["version"] = 1
        with self.assertRaisesRegex(review.TargetedReviewError, "frozen review"):
            review.validate_decisions(data)

    def test_duplicate_and_missing_records_fail(self):
        data = review.make_template()
        data["records"][1] = copy.deepcopy(data["records"][0])
        with self.assertRaisesRegex(review.TargetedReviewError, "duplicate"):
            review.validate_decisions(data)
        data = review.make_template()
        data["records"].pop()
        with self.assertRaisesRegex(review.TargetedReviewError, "exactly eleven"):
            review.validate_decisions(data)

    def test_unapproved_fields_forbidden(self):
        data = review.make_template()
        data["records"][0]["owner_approval"] = True
        with self.assertRaisesRegex(review.TargetedReviewError, "extra"):
            review.validate_decisions(data)
        data = review.make_template()
        data["human_approval"] = True
        with self.assertRaisesRegex(review.TargetedReviewError, "top-level"):
            review.validate_decisions(data)

    def test_unknown_topic_and_duplicate_topic_are_refused(self):
        data = synthetic_completed()
        row = data["records"][0]
        row.update({"decision": "classified", "topics": ["made_up_slug"]})
        with self.assertRaisesRegex(review.TargetedReviewError, "unsupported v2"):
            review.validate_decisions(data)
        row["topics"] = ["military_hadr", "military_hadr"]
        with self.assertRaisesRegex(review.TargetedReviewError, "duplicate"):
            review.validate_decisions(data)
        row["topics"] = ["military_hadr"]
        self.assertEqual(review.validate_decisions(data)["reviewed"], 11)

    def test_nonclassification_cannot_carry_topics(self):
        data = synthetic_completed()
        data["records"][0]["topics"] = ["military_hadr"]
        with self.assertRaisesRegex(review.TargetedReviewError, "cannot carry"):
            review.validate_decisions(data)

    def test_pending_cannot_carry_reviewer(self):
        data = review.make_template()
        data["records"][0]["reviewer"]["name"] = "SYNTHETIC"
        with self.assertRaisesRegex(review.TargetedReviewError, "pending"):
            review.validate_decisions(data)

    def test_each_record_requires_a_real_name_and_attestation(self):
        data = synthetic_completed()
        row = data["records"][0]
        row["reviewer"]["name"] = ""
        with self.assertRaisesRegex(review.TargetedReviewError, "named independent reviewer"):
            review.validate_decisions(data)
        row["reviewer"]["name"] = "SYNTHETIC ONLY"
        row["reviewer"]["independent_reading_attested"] = False
        with self.assertRaisesRegex(review.TargetedReviewError, "named independent reviewer"):
            review.validate_decisions(data)

    def test_original_language_and_full_source_attestations(self):
        data = synthetic_completed()
        row = data["records"][0]
        row["read_full_source"] = False
        with self.assertRaisesRegex(review.TargetedReviewError, "full original-language"):
            review.validate_decisions(data)
        row["read_full_source"] = True
        row["reviewer"]["original_language_reading_attested"] = False
        with self.assertRaisesRegex(review.TargetedReviewError, "full original-language"):
            review.validate_decisions(data)
        row["reviewer"]["original_language_reading_attested"] = True
        row["reviewer"]["language_read"] = ""
        with self.assertRaisesRegex(review.TargetedReviewError, "full original-language"):
            review.validate_decisions(data)

    def test_timestamp_is_real_utc_and_rationale_is_present(self):
        data = synthetic_completed()
        row = data["records"][0]
        row["reviewed_at_utc"] = "2026-10-07T20:00:00-04:00"
        with self.assertRaisesRegex(review.TargetedReviewError, "UTC"):
            review.validate_decisions(data)
        row["reviewed_at_utc"] = "2026-10-08T00:00:00Z"
        row["rationale"] = ""
        with self.assertRaisesRegex(review.TargetedReviewError, "rationale"):
            review.validate_decisions(data)

    def test_missing_historical_objects_never_become_live_source_fallback(self):
        # Exact replay is opt-in to the pre-existing pinned historical verifier.
        # Validation makes no requests to external URLs or production databases.
        with patch.object(review.evidence, "validate_files",
                          side_effect=review.evidence.CrossDeskEvidenceError("missing historical blob")):
            with self.assertRaisesRegex(review.evidence.CrossDeskEvidenceError,
                                        "missing historical"):
                review.make_template()


if __name__ == "__main__":
    unittest.main()
