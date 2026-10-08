"""No-network synthetic tests for human-gated Vietnam publisher citations.

All URL/content/reviewer fields here are deliberately FAKE fixtures. A green
test is neither a review of a real page nor approval to publish a source.
"""
from __future__ import annotations

import copy
import unittest

from core import brief_contract as bc
from core.brief_collection import brief_view, linked_prose
from core.brief_external_evidence import (
    CHECKS, SCHEMA, SCOPE, SOURCE_NAME, SOURCE_SLUG,
    validate_external_evidence,
)
from tests.test_ipr_briefs import complete, registry


REF = "mps-vi:10000000"
URL = "https://bocongan.gov.vn/bai-viet/test-fixture-10000000"
REGISTRY = registry(live=("china", "singapore"), shadow=("vietnam",))


def example():
    return {
        "schema": SCHEMA,
        "source_identity": REF,
        "desk": "vietnam",
        "source_slug": SOURCE_SLUG,
        "source_name": SOURCE_NAME,
        "url": URL,
        "original_title": "Thông tin đối ngoại (synthetic fixture)",
        "lang": "vi",
        "date": "2026-10-05",
        "state_commit": "a" * 40,
        "content_sha256": "b" * 64,
        "original_summary":
            "Synthetic, original English synopsis for testing source display; not an actual ministry finding.",
        "human_review": {
            "reviewed_by": "Fixture human reviewer",
            "reviewed_on": "2026-10-08",
            "scope": SCOPE,
            "checks": {name: True for name in CHECKS},
        },
    }


def sample():
    draft = complete()
    draft.update(week_start="2026-10-04", week_ending="2026-10-10")
    for item in draft["source_trail"]:
        item["date"] = "2026-10-05"
    draft["opening_note"] += " [External " + REF + "]"
    draft["external_evidence"] = [example()]
    return draft


class ReviewedExternalBriefsTests(unittest.TestCase):
    def test_valid_reviewed_reference_is_not_live_desk_coverage(self):
        value = sample()
        self.assertEqual(validate_external_evidence(value, REGISTRY), [])
        self.assertEqual(bc.validate_brief(value, REGISTRY), [])
        self.assertEqual(value["desks"], ["china", "singapore"])
        self.assertEqual(len(value["source_trail"]), 2)
        self.assertNotIn("vietnam", bc.eligible_desks(REGISTRY))

    def test_missing_or_unapproved_review_is_refused(self):
        for mode in ("no-review", "false-check", "unknown-check",
                     "wrong-scope", "late-review"):
            value = sample()
            if mode == "no-review":
                value["external_evidence"][0]["human_review"] = None
            elif mode == "false-check":
                value["external_evidence"][0]["human_review"]["checks"]["original_summary_fact_checked"] = False
            elif mode == "unknown-check":
                value["external_evidence"][0]["human_review"]["checks"]["extra"] = True
            elif mode == "wrong-scope":
                value["external_evidence"][0]["human_review"]["scope"] = "full-body-reproduction"
            else:
                value["editorial_status"] = "approved"
                value["approval"] = {"approved_by": "Test", "approved_on": "2026-10-07"}
            with self.subTest(mode=mode):
                self.assertTrue(validate_external_evidence(value, REGISTRY))

    def test_spoofed_urls_wrong_identity_and_source_family_refused(self):
        replacements = [
            ("url", "https://bocongan.gov.vn.evil.example/bai-viet/test-fixture-10000000"),
            ("url", "http://bocongan.gov.vn/bai-viet/test-fixture-10000000"),
            ("url", "https://bocongan.gov.vn/bai-viet/test-fixture-10000001"),
            ("url", "https://bocongan.gov.vn:444/bai-viet/test-fixture-10000000"),
            ("source_slug", "vn_journal_english"),
            ("source_identity", "mps-vi:000001"),
            ("lang", "en"),
            ("date", "2026-10-02"),
            ("content_sha256", "not-a-hash"),
        ]
        for field, entry in replacements:
            value = sample()
            value["external_evidence"][0][field] = entry
            with self.subTest(field=field, value=entry):
                self.assertTrue(validate_external_evidence(value, REGISTRY))

    def test_unknown_and_unused_external_citations_refused(self):
        value = sample()
        value["opening_note"] = "No reference here."
        self.assertIn("never cited", " ".join(validate_external_evidence(value, REGISTRY)))
        value = sample()
        value["opening_note"] += " [External mps-vi:20000000]"
        self.assertIn("no verified reference", " ".join(
            validate_external_evidence(value, REGISTRY)))

    def test_no_external_evidence_never_allows_orphan_markers(self):
        value = sample()
        del value["external_evidence"]
        self.assertIn("no verified reference", " ".join(
            validate_external_evidence(value, REGISTRY)))
        value["opening_note"] = "No external citations."
        self.assertEqual(validate_external_evidence(value, REGISTRY), [])

    def test_duplicate_and_existing_production_url_refused(self):
        value = sample()
        value["external_evidence"].append(copy.deepcopy(example()))
        self.assertIn("duplicated", " ".join(validate_external_evidence(value, REGISTRY)))
        value = sample()
        value["source_trail"][0]["url"] = URL
        self.assertIn("already archived", " ".join(
            validate_external_evidence(value, REGISTRY)))

    def test_unreviewed_body_or_translation_fields_refused(self):
        for field in ("article_body", "text_english", "full_translation", "raw_html"):
            value = sample()
            value["external_evidence"][0][field] = "forbidden"
            with self.subTest(field=field):
                self.assertIn("invalid fields", " ".join(
                    validate_external_evidence(value, REGISTRY)))

    def test_desk_not_in_registry_and_conflicting_desk_refused(self):
        value = sample()
        no_vietnam = registry(live=("china", "singapore"))
        self.assertTrue(validate_external_evidence(value, no_vietnam))
        value["desks"].append("vietnam")
        self.assertIn("masquerade", " ".join(
            validate_external_evidence(value, REGISTRY)))

    def test_html_output_links_original_source_and_escapes_untrusted_prose(self):
        body = 'A <script>alert(1)</script> note [External ' + REF + ']'
        rendered = linked_prose(body)
        self.assertIn("href=\"#ext-mps-vi-10000000\"", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        value = sample()
        view = brief_view(
            "fixture-only", value,
            desk_names={"china": "China Desk", "singapore": "Singapore Desk",
                        "vietnam": "Vietnam Desk"},
            state_labels={}, state_order=[], language_label=lambda x: x,
        )
        self.assertEqual(len(view["external_evidence"]), 1)
        self.assertEqual(view["external_evidence"][0]["url"], URL)
        self.assertEqual(view["external_evidence"][0]["anchor"], "ext-mps-vi-10000000")
        self.assertEqual(view["trail_count"], 2)
        self.assertEqual(len(view["desks"]), 2)


if __name__ == "__main__":
    unittest.main()
