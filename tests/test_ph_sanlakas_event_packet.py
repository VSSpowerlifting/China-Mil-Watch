"""Synthetic-only checks for an unsigned, AFP source-grounded event dossier."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import validate_ph_sanlakas_event_packet as validator  # noqa: E402


def fixture():
    data = json.loads(validator.PACKET.read_text(encoding="utf-8"))
    # These are *constructed synthetic testing rows*. Actual pinned bytes are
    # never presumed present in the checkout's Git history.
    archived = {}
    for record in data["records"]:
        ident = record["id"]
        text = "\n".join(
            x["evidence"][0]["exact_excerpt"] for x in data["claims"]
            if x["evidence"][0]["record_id"] == ident
        )
        archived[ident] = {
            "source_identity": ident,
            "title_original": record["title"],
            "source_url": record["source_url"],
            "published_at_original": record["published_at_original"],
            "text_sha256": record["content_sha256"],
            "capture_sha256": record["capture_sha256"],
            "text_status": "text",
            "text_original": "SYNTHETIC INDEPENDENT TEST TEXT ONLY\n" + text,
        }
    return data, archived


class ProvisionalPacketContract(unittest.TestCase):
    def setUp(self):
        self.packet, self.archived = fixture()

    def check(self, packet=None, archived=None):
        return validator.review_candidate(
            self.packet if packet is None else packet,
            self.archived if archived is None else archived,
        )

    def test_four_sources_two_events_eleven_grounded_claims(self):
        result = self.check()
        self.assertEqual(result["source_records_verified_against_pin"], 4)
        self.assertEqual(result["provisional_distinct_event_candidates"], 2)
        self.assertEqual(result["source_grounded_claim_count"], 11)
        self.assertTrue(result["all_review_flags_still_pending"])
        self.assertFalse(result["human_review_complete"])
        self.assertFalse(result["timeline_publication_approved"])
        self.assertEqual(result["record_topic_assignments"], 0)
        self.assertEqual(result["production_writes"], 0)

    def test_third_IAx_stage_does_not_become_third_event(self):
        grouped = {e["key"]: e for e in self.packet["event_candidates"]}
        self.assertEqual(
            grouped["sanlakas_exercise"]["record_ids"],
            ["afp:1391", "afp:1393", "afp:1394"],
        )
        self.assertEqual(
            grouped["jpscc_meeting"]["record_ids"], ["afp:1390"]
        )
        self.assertEqual(grouped["sanlakas_exercise"]["event_date_start"],
                         "2026-09-30")
        self.assertEqual(grouped["sanlakas_exercise"]["event_date_end"],
                         "2026-10-02")
        self.assertEqual(grouped["jpscc_meeting"]["event_date_start"],
                         "2026-09-29")

    def test_1390_cannot_be_relabelled_as_exercise_source(self):
        modified = copy.deepcopy(self.packet)
        modified["records"][0]["group"] = "sanlakas_exercise"
        with self.assertRaisesRegex(validator.EventReviewError, "reassigned"):
            self.check(modified)

    def test_1390_cannot_be_added_to_exercise_membership(self):
        modified = copy.deepcopy(self.packet)
        modified["event_candidates"][0]["record_ids"].append("afp:1390")
        with self.assertRaisesRegex(validator.EventReviewError, "grouping/date"):
            self.check(modified)

    def test_cannot_collapse_independent_meeting_into_exercise(self):
        modified = copy.deepcopy(self.packet)
        modified["event_candidates"].pop()
        with self.assertRaisesRegex(validator.EventReviewError, "two distinct"):
            self.check(modified)

    def test_article_date_cannot_replace_actual_exercise_date(self):
        modified = copy.deepcopy(self.packet)
        modified["event_candidates"][0]["event_date_end"] = "2026-10-03"
        with self.assertRaisesRegex(validator.EventReviewError, "grouping/date"):
            self.check(modified)
        modified = copy.deepcopy(self.packet)
        modified["records"][2]["published_at_original"] = "2026-10-01T00:00:00Z"
        with self.assertRaisesRegex(validator.EventReviewError, "published_at_original"):
            self.check(modified)

    def test_reject_changed_source_text_or_capture_digest(self):
        for field in ("content_sha256", "capture_sha256"):
            modified = copy.deepcopy(self.packet)
            modified["records"][0][field] = "0" * 64
            with self.subTest(field=field):
                with self.assertRaisesRegex(validator.EventReviewError, "provenance"):
                    self.check(modified)

    def test_unarchived_fake_article_cannot_enter_dossier(self):
        modified = copy.deepcopy(self.packet)
        modified["records"][0]["id"] = "afp:9999"
        with self.assertRaisesRegex(validator.EventReviewError, "source ID"):
            self.check(modified)

    def test_record_set_must_have_exact_identity_and_count(self):
        modified = copy.deepcopy(self.packet)
        modified["records"] = modified["records"][:-1]
        with self.assertRaisesRegex(validator.EventReviewError, "four distinct"):
            self.check(modified)
        modified = copy.deepcopy(self.packet)
        modified["records"][1] = modified["records"][0]
        with self.assertRaisesRegex(validator.EventReviewError, "repeated"):
            self.check(modified)

    def test_only_quotations_actually_in_original_body_are_accepted(self):
        modified = copy.deepcopy(self.packet)
        modified["claims"][0]["evidence"][0]["exact_excerpt"] = (
            "SYNTHETIC UNFOUNDED QUOTE NEVER IN ORIGINAL"
        )
        with self.assertRaisesRegex(validator.EventReviewError, "absent"):
            self.check(modified)

    def test_claims_cannot_be_cited_to_wrong_event_source(self):
        modified = copy.deepcopy(self.packet)
        modified["claims"][0]["evidence"][0]["record_id"] = "afp:1390"
        with self.assertRaisesRegex(validator.EventReviewError, "correct archived"):
            self.check(modified)
        modified = copy.deepcopy(self.packet)
        modified["claims"][0]["event_key"] = "jpscc_meeting"
        with self.assertRaisesRegex(validator.EventReviewError, "ungrounded"):
            self.check(modified)

    def test_duplicate_and_missing_claims_are_refused(self):
        modified = copy.deepcopy(self.packet)
        modified["claims"][1]["id"] = modified["claims"][0]["id"]
        with self.assertRaisesRegex(validator.EventReviewError, "duplicate"):
            self.check(modified)
        modified = copy.deepcopy(self.packet)
        modified["claims"].pop()
        with self.assertRaisesRegex(validator.EventReviewError, "number"):
            self.check(modified)

    def test_source_archived_body_missing_is_not_fabricated(self):
        edited = copy.deepcopy(self.archived)
        edited["afp:1394"]["text_original"] = ""
        with self.assertRaisesRegex(validator.EventReviewError, "full pinned"):
            self.check(archived=edited)

    def test_source_quote_not_present_in_archived_body_refused(self):
        edited = copy.deepcopy(self.archived)
        edited["afp:1394"]["text_original"] = "SYNTHETIC UNRELATED"
        with self.assertRaisesRegex(validator.EventReviewError, "absent"):
            self.check(archived=edited)

    def test_exact_historical_database_pin_required(self):
        modified = copy.deepcopy(self.packet)
        modified["archive"]["state_db_blob"] = "0" * 40
        with self.assertRaisesRegex(validator.EventReviewError, "immutable"):
            self.check(modified)
        modified = copy.deepcopy(self.packet)
        modified["archive"]["state_commit"] = "main"
        with self.assertRaisesRegex(validator.EventReviewError, "immutable"):
            self.check(modified)

    def test_unauthorized_editorial_flags_never_accepted(self):
        for flag in validator.LOCKED_FALSE:
            modified = copy.deepcopy(self.packet)
            modified["permissions"][flag] = True
            with self.subTest(flag=flag):
                with self.assertRaisesRegex(validator.EventReviewError, "cannot authorize"):
                    self.check(modified)

    def test_missing_warning_or_unresolved_name_flag_rejected(self):
        modified = copy.deepcopy(self.packet)
        modified["editorial_review_flags"][1]["status"] = "resolved"
        with self.assertRaisesRegex(validator.EventReviewError, "caveats"):
            self.check(modified)
        modified = copy.deepcopy(self.packet)
        modified["editorial_review_flags"].pop()
        with self.assertRaisesRegex(validator.EventReviewError, "caveats"):
            self.check(modified)

    def test_source_publisher_is_not_three_independent_confirmations(self):
        flags = self.packet["editorial_review_flags"]
        self.assertTrue(any(
            x["kind"] == "publisher_claim_not_independent_corroboration"
            for x in flags
        ))
        self.assertTrue(any(
            x["kind"] == "unresolved_name_variation" for x in flags
        ))
        self.assertTrue(any(
            x["kind"] == "event_date_vs_publication_date" for x in flags
        ))

    def test_cli_does_not_fake_missing_git_shadow_history(self):
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run(["git", "init", "-q"], cwd=temp, check=True)
            p = subprocess.run(
                [sys.executable,
                 str(ROOT / "scripts/validate_ph_sanlakas_event_packet.py"),
                 "--state-repo", temp],
                cwd=ROOT, capture_output=True, text=True
            )
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("pinned AFP Day-0 evidence unavailable", p.stderr)

    def test_mutated_schema_status_and_scope_are_rejected(self):
        for key, value in (
            ("schema", "production_event_v1"),
            ("status", "reviewed"),
            ("verification_scope", "independently_verified"),
        ):
            modified = copy.deepcopy(self.packet)
            modified[key] = value
            with self.subTest(key=key):
                with self.assertRaises(validator.EventReviewError):
                    self.check(modified)


if __name__ == "__main__":
    unittest.main()
