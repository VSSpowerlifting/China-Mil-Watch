"""Read-only seven-desk HADR source-packet provenance and negative tests."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_topic_v2_crossdesk_hadr import (  # noqa: E402
    CrossDeskEvidenceError,
    _git_blob_sha,
    validate,
    validate_files,
)

LEDGER = ROOT / "research" / "topic_pilot_v1" / "ledger.json"
PACKET = ROOT / "research" / "topic_v2_crossdesk_hadr" / "packet.json"


class CrossDeskPacket(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = LEDGER.read_bytes()
        cls.ledger = json.loads(raw.decode("utf-8"))
        cls.sha = _git_blob_sha(raw)
        cls.packet = json.loads(PACKET.read_text(encoding="utf-8"))

    def assert_refused(self, packet, message):
        with self.assertRaisesRegex(CrossDeskEvidenceError, message):
            validate(packet, self.ledger, self.sha)

    def copy(self):
        return copy.deepcopy(self.packet)

    def test_actual_packet_replays_original_pilot_source_fields(self):
        result = validate_files()
        self.assertEqual(result["cases"], 11)
        self.assertEqual(result["desk_count"], 7)
        self.assertEqual(result["event_contexts"], 9)
        self.assertEqual(result["roles"], {
            "negative_control": 4,
            "positive_candidate": 6,
            "unassessable_body": 1,
        })
        self.assertFalse(result["human_approval"])

    def test_stored_git_object_hash_of_original_ledger_matches_pin(self):
        self.assertEqual(self.sha, self.packet["pilot_ledger_blob_sha"])

    def test_two_philippines_mentions_are_not_two_event_contexts(self):
        items = {r["pilot_id"]: r for r in self.packet["cases"]}
        self.assertEqual(items["P51"]["event_key"], items["P52"]["event_key"])
        self.assertEqual(items["P35"]["event_key"], items["P36"]["event_key"])
        self.assertEqual(items["P36"]["body_chars"], 0)
        self.assertEqual(items["P36"]["evidence"], [])

    def test_all_seven_desks_are_represented_but_only_five_have_hadr_candidates(self):
        items = self.packet["cases"]
        self.assertEqual({r["desk_id"] for r in items}, {
            "china", "singapore", "japan", "philippines",
            "indonesia", "vietnam", "korea",
        })
        self.assertEqual({
            r["desk_id"] for r in items
            if r["role"] == "positive_candidate"
        }, {"china", "singapore", "japan", "philippines", "indonesia"})

    def test_changed_original_source_url_fails(self):
        packet = self.copy()
        packet["cases"][0]["source_url"] = "https://unverified.invalid/item"
        self.assert_refused(packet, "source content or identity drift")

    def test_changed_original_language_quote_fails(self):
        packet = self.copy()
        packet["cases"][0]["evidence"][0]["quote"] = "fabricated quote"
        self.assert_refused(packet, "source excerpt provenance mismatch")

    def test_changed_original_excerpt_offsets_fail(self):
        packet = self.copy()
        packet["cases"][0]["evidence"][0]["start"] += 1
        self.assert_refused(packet, "source excerpt provenance mismatch")

    def test_changed_source_body_hash_fails(self):
        packet = self.copy()
        packet["cases"][0]["body_sha256"] = "0" * 64
        self.assert_refused(packet, "source content or identity drift")

    def test_origin_commit_and_database_blob_are_immutable(self):
        for field in ("origin_commit", "origin_blob", "origin_path",
                      "origin_ref", "storage_table"):
            with self.subTest(field=field):
                packet = self.copy()
                packet["cases"][0][field] = "different"
                self.assert_refused(packet, "archived origin pin drift")

    def test_duplicate_ledger_selection_fails(self):
        packet = self.copy()
        packet["cases"][1]["pilot_id"] = packet["cases"][0]["pilot_id"]
        self.assert_refused(packet, "duplicate case ID")

    def test_unreviewed_question_cannot_be_marked_human_approved(self):
        packet = self.copy()
        packet["cases"][0]["owner_approval"] = {
            "name": "synthetic review", "approved": True
        }
        self.assert_refused(packet, "case attempts to assert human approval")
        packet = self.copy()
        packet["cases"][0]["review_state"] = "human_approved"
        self.assert_refused(packet, "case attempts to assert human approval")

    def test_bodyless_infographic_cannot_borrow_neighboring_text(self):
        packet = self.copy()
        missing = next(x for x in packet["cases"] if x["pilot_id"] == "P36")
        missing["evidence"] = copy.deepcopy(packet["cases"][0]["evidence"])
        self.assert_refused(packet, "source excerpt count drift")

    def test_event_family_cannot_claim_independent_sanlakas_events(self):
        packet = self.copy()
        second = next(x for x in packet["cases"] if x["pilot_id"] == "P52")
        second["event_key"] = "synthetic_new_event"
        self.assert_refused(packet, "case role or event family changed")

    def test_no_silent_scope_upgrade_or_gold_label_assertion(self):
        packet = self.copy()
        packet["classification_status"] = "human_approved"
        self.assert_refused(packet, "wrongly asserts classification authority")
        packet = self.copy()
        packet["target_taxonomy_version"] = 3
        self.assert_refused(packet, "taxonomy versions are inconsistent")

    def test_seven_desks_does_not_mean_seven_positive_desk_samples(self):
        packet = self.copy()
        vietnam = next(x for x in packet["cases"] if x["pilot_id"] == "P44")
        vietnam["role"] = "positive_candidate"
        self.assert_refused(packet, "case role or event family changed")

    def test_edited_or_wrong_git_blob_reference_fails(self):
        packet = self.copy()
        packet["pilot_ledger_blob_sha"] = "0" * 40
        self.assert_refused(packet, "frozen pilot Git blob SHA mismatch")

    def test_packet_cannot_disguise_model_selected_evidence(self):
        packet = self.copy()
        packet["selection_note"] = "All evidence independently approved."
        self.assert_refused(packet, "disclose non-human model-selected origin")


if __name__ == "__main__":
    unittest.main(verbosity=2)
