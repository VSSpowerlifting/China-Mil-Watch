"""Pure, offline B0 source-parity controls. Does not contact publishers."""
from __future__ import annotations

import copy
import unittest

from scripts.check_dossier_b0_preservation import (
    BASE, DESK, INSTITUTION, RECORDS, SOURCE, verify_record,
)


def valid(rid=4454):
    pub, slug, anchors, _group = RECORDS[rid]
    return {
        "id": rid, "published_date": pub, "url": BASE + slug + "/",
        "source_slug": SOURCE, "desk_id": DESK,
        "institution_id": INSTITUTION, "source_language_tag": "en",
        "title_original": "Publisher original title (untouched)",
        "text_original": "Official publisher report. " * 11
                         + " ".join(anchors) + ". End of record.",
        "passed_relevance": None,
    }


class TestDossierB0Preservation(unittest.TestCase):
    def test_valid_synthetic_preserved_row(self):
        r = verify_record(valid(), RECORDS[4454])
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["review_holds"], [])
        self.assertTrue(r["all_anchors_present"])
        self.assertEqual(len(r["stored_original_sha256"]), 64)

    def test_wrong_url_never_accepted(self):
        r = valid()
        r["url"] = "https://www.mindef.gov.sg/news-and-events/latest-releases/OTHER/"
        self.assertIn("url-mismatch", verify_record(r, RECORDS[4454])["errors"])

    def test_missing_record_refused(self):
        r = verify_record(None, RECORDS[4454])
        self.assertIn("missing-record", r["errors"])

    def test_wrong_issuing_institution_refused(self):
        r = valid()
        r["institution_id"] = "sg_other"
        self.assertIn("institution_id-mismatch", verify_record(r, RECORDS[4454])["errors"])

    def test_wrong_desk_refused(self):
        r = valid()
        r["desk_id"] = "china"
        self.assertIn("desk_id-mismatch", verify_record(r, RECORDS[4454])["errors"])

    def test_wrong_date_refused(self):
        r = valid()
        r["published_date"] = "2026-07-31"
        self.assertIn("published_date-mismatch", verify_record(r, RECORDS[4454])["errors"])

    def test_missing_original_text_refused(self):
        r = valid()
        r["text_original"] = ""
        s = verify_record(r, RECORDS[4454])
        self.assertIn("missing-or-incomplete-original-body", s["errors"])
        self.assertIn("stored-body-anchor-mismatch", s["errors"])

    def test_different_english_translation_does_not_prove_original(self):
        r = valid()
        r["text_original"] = "Unrelated article body. " * 15
        r["text_english"] = "rimpac steadfast"
        self.assertIn("stored-body-anchor-mismatch", verify_record(r, RECORDS[4454])["errors"])

    def test_invalid_source_manifest_refused(self):
        self.assertIn("source-not-enabled-in-declared-manifest",
                      verify_record(valid(), RECORDS[4454], valid_manifest=False)["errors"])

    def test_screened_negative_is_review_hold(self):
        r = valid()
        r["passed_relevance"] = 0
        result = verify_record(r, RECORDS[4454])
        self.assertIn("screened-not-selected-human-review-required", result["review_holds"])
        self.assertEqual(result["errors"], [])
        # Preserved body is sound; the source's selection permission is NOT.
        self.assertFalse(not result["review_holds"])

    def test_no_original_text_leaks_to_result(self):
        r = valid()
        r["text_original"] += " PRIVATE_PUBLISHER_TEXT_MARKER"
        result = verify_record(r, RECORDS[4454])
        self.assertNotIn("PRIVATE_PUBLISHER_TEXT_MARKER", str(result))

    def test_multiple_reports_one_activity_group(self):
        self.assertEqual(RECORDS[4466][-1], RECORDS[4472][-1])
        self.assertNotEqual(RECORDS[4466][0], RECORDS[4472][0])

    def test_each_expected_record_has_distinct_url(self):
        self.assertEqual(len({BASE + spec[1] + "/" for spec in RECORDS.values()}), len(RECORDS))


if __name__ == "__main__":
    unittest.main()
