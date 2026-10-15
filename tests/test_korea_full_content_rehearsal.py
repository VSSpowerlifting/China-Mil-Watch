"""Synthetic, no-network full-content Korea private staging contract tests."""
from __future__ import annotations

import copy
import hashlib
import unittest

from core.korea_full_content_rehearsal import (
    ContentHold, DRAFT_SCHEMA, POLICY_URL, RIGHTS_SCHEMA, check_candidate,
    render_private_html, sha,
)


class KoreaContentPilot(unittest.TestCase):
    def setUp(self):
        self.identity = "korea-policy:156784297"
        self.version = "c" * 64
        self.original = {
            "source_identity": self.identity,
            "url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784297",
            "title_original": "합동 훈련 발표",
            "text_original": "국방부가 일정을 발표했다.\n훈련이 예정되어 있다.",
            "published_date": "2026-10-06",
        }
        self.stage = {
            "source_identity": self.identity,
            "candidate_version_sha256": self.version,
            "original_text_sha256": sha(self.original["text_original"]),
            "original_title_sha256": sha(self.original["title_original"]),
            "publisher_html_sha256": "d" * 64,
            "original_hwpx_sha256": "e" * 64,
            "canonical_source_url": self.original["url"],
            "publisher_posted_date": "2026-10-06",
            "editorial_exception": None,
            "source_slug": "kr_policy_mnd_releases",
            "institution_id": "kr_mnd",
            "publisher_institution_id": "kr_policy_briefing",
        }
        self.rights = {
            "schema": RIGHTS_SCHEMA,
            "source_identity": self.identity,
            "candidate_version_sha256": self.version,
            "publisher_html_sha256": "d" * 64,
            "notice_sha256": "f" * 64,
            "publisher_policy_url": POLICY_URL,
            "notice_marker": "KOGL_TYPE_1",
            "notice_scope": "publisher_text_only",
            "notice_observed_at_utc": "2026-10-15T22:00:00Z",
            "media_reuse_allowed": False,
            "hwpx_file_redistribution_allowed": False,
            "independently_approved": False,
        }
        self.draft = {
            "schema": DRAFT_SCHEMA,
            "source_identity": self.identity,
            "candidate_version_sha256": self.version,
            "original_text_sha256": self.stage["original_text_sha256"],
            "generated_at_utc": "2026-10-15T22:01:00Z",
            "model_id": "synthetic-test-generator",
            "content_label": "unreviewed_machine_draft",
            "translation_paragraphs": [
                {"source_index": 1,
                 "source_paragraph_sha256": sha("국방부가 일정을 발표했다."),
                 "text_en": "The ministry announced a schedule.",
                 "language": "en", "status": "machine_unreviewed"},
                {"source_index": 2,
                 "source_paragraph_sha256": sha("훈련이 예정되어 있다."),
                 "text_en": "An exercise is planned.",
                 "language": "en", "status": "machine_unreviewed"},
            ],
            "source_notes": [
                {"kind": "attributed_official_source_observation",
                 "text_en": "The ministry says the exercise is planned.",
                 "source_indices": [2], "status": "machine_unreviewed"},
            ],
        }

    def check(self):
        return check_candidate(self.stage, self.original, self.rights,
                               self.draft)

    def rejects(self, code):
        with self.assertRaisesRegex(ContentHold, "^" + code + "$"):
            self.check()

    def test_valid_synthetic_packet_remains_held(self):
        receipt = self.check()
        self.assertEqual("PRIVATE_REVIEW_ONLY", receipt["status"])
        self.assertEqual(2, receipt["translation_paragraph_count"])
        self.assertEqual(1, receipt["machine_note_count"])
        self.assertTrue(receipt["paragraph_alignment_structurally_verified"])
        for flag in ("rights_clearance_verified",
                     "original_document_redistribution_authorized",
                     "translation_publication_authorized",
                     "substantive_analysis_publication_authorized",
                     "claims_fact_checked", "media_publication_authorized"):
            self.assertIs(receipt[flag], False, flag)
        self.assertEqual(0, receipt["production_records_written"])
        self.assertEqual(0, receipt["public_files_written"])
        self.assertEqual(4, len(receipt["publication_holds"]))
        self.assertNotIn("The ministry", str(receipt))

    def test_source_text_mutation_fails_exact_capture_pin(self):
        self.original["text_original"] += " 수정"
        self.rejects("original_text_not_pinned_to_verified_hwpx_stage")

    def test_title_mutation_fails_capture_pin(self):
        self.original["title_original"] = "다른 제목"
        self.rejects("original_text_not_pinned_to_verified_hwpx_stage")

    def test_canonical_publisher_url_drift_fails(self):
        self.original["url"] = "https://example.org/"
        self.rejects("original_text_not_pinned_to_verified_hwpx_stage")

    def test_wrong_family_fails(self):
        self.stage["institution_id"] = "kr_other"
        self.rejects("source_family_outside_korea_pilot")

    def test_editorial_exception_never_overridden_by_model(self):
        self.stage["editorial_exception"] = "chronology_discrepancy"
        self.rejects("existing_korean_editorial_exception_hold")

    def test_fake_rights_approval_cannot_escalate(self):
        self.rights["independently_approved"] = True
        self.rejects("rights_pilot_scope_overstated")

    def test_fake_media_license_cannot_escalate(self):
        self.rights["media_reuse_allowed"] = True
        self.rejects("rights_pilot_scope_overstated")

    def test_full_hwpx_document_not_cleared(self):
        self.rights["hwpx_file_redistribution_allowed"] = True
        self.rejects("rights_pilot_scope_overstated")

    def test_wrong_license_marker_is_held(self):
        self.rights["notice_marker"] = "KOGL_TYPE_4"
        self.rejects("rights_pilot_scope_overstated")

    def test_publisher_capture_rights_pin_is_required(self):
        self.rights["publisher_html_sha256"] = "a" * 64
        self.rejects("rights_observation_not_source_version_bound")

    def test_missing_notice_digest_fails(self):
        self.rights["notice_sha256"] = None
        self.rejects("rights_notice_digest_missing")

    def test_self_asserted_extra_rights_field_is_rejected(self):
        self.rights["model_permission"] = True
        self.rejects("rights_observation_fields_invalid")

    def test_draft_source_version_drift_fails(self):
        self.draft["candidate_version_sha256"] = "b" * 64
        self.rejects("machine_draft_not_source_version_bound")

    def test_draft_label_cannot_imply_editorial_signoff(self):
        self.draft["content_label"] = "human_approved"
        self.rejects("machine_draft_not_source_version_bound")

    def test_missing_translation_fails(self):
        self.draft["translation_paragraphs"].pop()
        self.rejects("translation_paragraph_count_mismatch")

    def test_reordered_translations_fail(self):
        self.draft["translation_paragraphs"].reverse()
        self.rejects("translation_alignment_or_label_invalid")

    def test_wrong_paragraph_hash_fails(self):
        self.draft["translation_paragraphs"][1]["source_paragraph_sha256"] = "b" * 64
        self.rejects("translation_alignment_or_label_invalid")

    def test_translation_marked_human_is_rejected(self):
        self.draft["translation_paragraphs"][0]["status"] = "human_reviewed"
        self.rejects("translation_alignment_or_label_invalid")

    def test_unattributed_source_note_fails(self):
        self.draft["source_notes"][0]["source_indices"] = []
        self.rejects("machine_note_citation_not_supported_by_source_indices")

    def test_repeated_source_note_citation_fails(self):
        self.draft["source_notes"][0]["source_indices"] = [1, 1]
        self.rejects("machine_note_citation_not_supported_by_source_indices")

    def test_source_note_cannot_claim_human_editorial_judgment(self):
        self.draft["source_notes"][0]["status"] = "human_approved"
        self.rejects("machine_note_cannot_claim_editorial_judgment")

    def test_extra_model_generated_field_is_rejected(self):
        self.draft["republication_authorized"] = True
        self.rejects("machine_draft_fields_invalid")

    def test_invalid_future_or_unparseable_timestamp_fails(self):
        self.draft["generated_at_utc"] = "2026-02-31T10:00:00Z"
        self.rejects("draft_timestamp_invalid")

    def test_html_escaped_and_no_public_verdict(self):
        self.draft["translation_paragraphs"][0]["text_en"] = "<script>alert(1)</script>"
        self.draft["source_notes"][0]["text_en"] = "<img src=x>"
        html = render_private_html(self.stage, self.original, self.rights,
                                   self.draft)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img src=x&gt;", html)
        self.assertIn("noindex,nofollow,noarchive", html)
        self.assertIn("DO NOT PUBLISH", html)
        self.assertIn(self.original["url"], html)
        self.assertNotIn("<iframe", html)

    def test_real_publisher_date_not_model_date(self):
        self.original["published_date"] = "2026-10-07"
        self.rejects("original_text_not_pinned_to_verified_hwpx_stage")

    def test_stage_digests_must_be_valid(self):
        self.stage["original_hwpx_sha256"] = "untrusted"
        self.rejects("stage_source_digest_invalid")


if __name__ == "__main__":
    unittest.main()
