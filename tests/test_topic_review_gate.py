"""Contracts for the source-first, non-applying human topic review gate."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.topic_review_gate import (  # noqa: E402
    ReviewGateError,
    blind_packet,
    compare_model_passes,
    make_template,
    validate_decisions,
)


def fixture_review():
    """TEST ONLY: synthetic payload is not a human submission."""
    value = make_template()
    value["reviewer"] = {
        "name": "SYNTHETIC TEST FIXTURE - NOT A HUMAN",
        "independent_reading_attested": True,
    }
    return value


def mark_abstain(entry):
    entry["decision"] = "abstain"
    entry["rationale"] = "SYNTHETIC TEST CASE: deliberately no topics."
    entry["read_full_source"] = True
    entry["reviewed_at_utc"] = "2026-10-07T23:45:00Z"


class BlindPacket(unittest.TestCase):
    def test_blind_packet_contains_all_source_identity_without_model_reasons(self):
        text = blind_packet()
        self.assertIn("## P01", text)
        self.assertIn("## P60", text)
        self.assertIn("南部战区新闻发言人发表谈话", text)
        self.assertIn("http://www.81.cn/yw_208727/16491198.html", text)
        self.assertIn("source body", text.lower())
        # These model-authored interpretations MUST NOT leak into the blind packet.
        self.assertNotIn("Local coast_guard label is not evidence", text)
        self.assertNotIn("Source describes a maritime-area military interception.", text)
        self.assertNotIn("Define when military warning/expulsion", text)
        self.assertEqual(sum(line.startswith("## P") for line in text.splitlines()), 60)

    def test_template_is_unsigned_and_proposal_free(self):
        data = make_template()
        self.assertEqual(data["protocol_version"], 1)
        self.assertEqual(data["taxonomy"]["taxonomy_version"], 1)
        self.assertEqual(len(data["records"]), 60)
        self.assertEqual(data["reviewer"]["name"], "")
        self.assertFalse(data["reviewer"]["independent_reading_attested"])
        self.assertTrue(all(r["decision"] == "pending" and r["topics"] == []
                            for r in data["records"]))
        self.assertTrue(all("recommended_topics" not in r and "proposals" not in r
                            for r in data["records"]))

    def test_unaltered_template_is_valid_but_not_completed(self):
        result = validate_decisions(make_template())
        self.assertEqual(result["reviewed"], 0)
        self.assertEqual(result["counts"]["pending"], 60)
        with self.assertRaisesRegex(ReviewGateError, "requires all records"):
            validate_decisions(make_template(), require_complete=True)


class FailClosedReview(unittest.TestCase):
    def test_one_signed_record_is_valid_partial_review(self):
        review = fixture_review()
        mark_abstain(review["records"][0])
        result = validate_decisions(review)
        self.assertEqual(result["reviewed"], 1)
        self.assertEqual(result["counts"]["pending"], 59)

    def test_missing_reviewer_identity_and_attestation_fail(self):
        review = fixture_review()
        mark_abstain(review["records"][0])
        review["reviewer"]["name"] = ""
        with self.assertRaisesRegex(ReviewGateError, "named reviewer"):
            validate_decisions(review)
        review["reviewer"]["name"] = "TEST ONLY"
        review["reviewer"]["independent_reading_attested"] = False
        with self.assertRaisesRegex(ReviewGateError, "named reviewer"):
            validate_decisions(review)

    def test_source_identity_and_reference_hash_are_immutable(self):
        review = make_template()
        review["records"][0]["body_sha256"] = "0" * 64
        with self.assertRaisesRegex(ReviewGateError, "identity changed"):
            validate_decisions(review)
        review = make_template()
        review["pilot"]["ledger_sha256"] = "1" * 64
        with self.assertRaisesRegex(ReviewGateError, "frozen review contract"):
            validate_decisions(review)
        review = make_template()
        review["taxonomy"]["taxonomy_sha256"] = "1" * 64
        with self.assertRaisesRegex(ReviewGateError, "frozen review contract"):
            validate_decisions(review)

    def test_duplicate_record_id_is_rejected(self):
        review = make_template()
        review["records"][1] = copy.deepcopy(review["records"][0])
        with self.assertRaisesRegex(ReviewGateError, "appears twice"):
            validate_decisions(review)

    def test_unknown_topic_and_duplicate_topics_fail_closed(self):
        review = fixture_review()
        row = review["records"][0]
        row.update({
            "decision": "classified", "topics": ["fabricated_topic"],
            "rationale": "Fixture", "read_full_source": True,
            "reviewed_at_utc": "2026-10-07T23:45:00Z",
        })
        with self.assertRaisesRegex(ReviewGateError, "unknown topic"):
            validate_decisions(review)
        row["topics"] = ["maritime_security", "maritime_security"]
        with self.assertRaisesRegex(ReviewGateError, "duplicate"):
            validate_decisions(review)
        row["topics"] = ["maritime_security"]
        self.assertEqual(validate_decisions(review)["reviewed"], 1)

    def test_abstention_cannot_carry_label_and_classified_requires_label(self):
        review = fixture_review()
        row = review["records"][0]
        mark_abstain(row)
        row["topics"] = ["maritime_security"]
        with self.assertRaisesRegex(ReviewGateError, "nonclassified decision"):
            validate_decisions(review)
        row["decision"] = "classified"
        row["topics"] = []
        with self.assertRaisesRegex(ReviewGateError, "at least one topic"):
            validate_decisions(review)

    def test_invalid_timestamp_and_unread_source_are_refused(self):
        review = fixture_review()
        row = review["records"][0]
        mark_abstain(row)
        row["reviewed_at_utc"] = "2026-10-07T20:45:00-04:00"
        with self.assertRaisesRegex(ReviewGateError, "must end with Z"):
            validate_decisions(review)
        row["reviewed_at_utc"] = "2026-10-07T23:45:00Z"
        row["read_full_source"] = False
        with self.assertRaisesRegex(ReviewGateError, "full source reading"):
            validate_decisions(review)

    def test_pending_judgment_and_malformed_reviewer_rejected(self):
        review = fixture_review()
        review["records"][0]["topics"] = ["maritime_security"]
        with self.assertRaisesRegex(ReviewGateError, "pending record contains judgment"):
            validate_decisions(review)
        review = make_template()
        review["reviewer"]["independent_reading_attested"] = "yes"
        with self.assertRaisesRegex(ReviewGateError, "must be boolean"):
            validate_decisions(review)

    def test_comparison_will_not_expose_model_judgments_for_partial_review(self):
        review = fixture_review()
        mark_abstain(review["records"][0])
        with self.assertRaisesRegex(ReviewGateError, "requires all records"):
            compare_model_passes(review)

    def test_comparison_after_fully_signed_fixture_is_descriptive(self):
        review = fixture_review()
        for record in review["records"]:
            mark_abstain(record)
        report = compare_model_passes(review)
        self.assertIn("60 records", report)
        self.assertIn("Second model pass", report)
        self.assertIn("not accuracy", report)
        self.assertIn("| P01 |", report)

    def test_v2_not_available_without_explicit_v2_vocabulary(self):
        # On a later main with v2, this test must remain valid as a
        # version-selection contract rather than asserting nonexistence.
        try:
            v2 = make_template(2)
        except FileNotFoundError:
            return
        self.assertEqual(v2["taxonomy"]["taxonomy_version"], 2)
        self.assertIn("military_hadr", v2["taxonomy"]["topic_slugs"])
        self.assertNotIn("military_hadr", make_template()["taxonomy"]["topic_slugs"])
        with self.assertRaisesRegex(ReviewGateError, "cross-version comparison"):
            # Only after a full review could this branch be reached.
            review = v2
            review["reviewer"] = {
                "name": "SYNTHETIC TEST FIXTURE - NOT A HUMAN",
                "independent_reading_attested": True,
            }
            for record in review["records"]:
                mark_abstain(record)
            compare_model_passes(review, version=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
