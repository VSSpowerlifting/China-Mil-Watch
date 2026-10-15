"""Fictional, source-free AFP/Kemhan held metadata candidate contracts."""
import copy
import json
import unittest

from core.crossdesk_official_metadata_candidates import (
    FAMILIES, IntakeHold, KEMHAN_HELD, build,
)


COMMIT = "a" * 40
BASE = {
    "schema": "ipr-private-shadow-desk-reader/1",
    "status": "private_research_not_source_admitted",
    "query": "", "desk_filter": "philippines",
    "sources": [{"source_slug": "ph_afp_articles",
                 "country": "philippines", "institution": "Armed Forces of the Philippines",
                 "state_commit": COMMIT, "stored_records": 1, "query_matches": 1}],
    "matched_total": 1,
    "results": [{"country": "philippines", "institution": "Armed Forces of the Philippines",
                 "source_slug": "ph_afp_articles", "identity": "afp:1399",
                 "url": "https://www.afp.mil.ph/news/test-exercise",
                 "title": "ORIGINAL HEADLINE DO NOT EXPORT",
                 "published_date": "2026-10-15", "first_seen_run": "12345-1",
                 "state_commit": COMMIT,
                 "review_status": "not_human_reviewed_for_public_use"}],
    "truncated": False, "source_body_text_exported": False,
    "automated_source_rights_approved": False,
    "human_source_review_completed": False,
    "production_records_changed": False,
    "country_desks_promoted": False,
    "public_release_authorized": False,
}


def indonesia():
    report = copy.deepcopy(BASE)
    report["desk_filter"] = "indonesia"
    report["sources"][0].update(source_slug="id_kemhan_news", country="indonesia",
                                institution="Indonesia Ministry of Defense — Kemhan Berita")
    report["results"][0].update(
        source_slug="id_kemhan_news", country="indonesia",
        institution="Indonesia Ministry of Defense — Kemhan Berita",
        identity="kemhan:/2026/10/15/notice.html",
        url="https://www.kemhan.go.id/2026/10/15/notice.html",
        first_seen_run="local-native-20261006-indonesia")
    return report


class CandidateTests(unittest.TestCase):
    def test_afp_candidate_held_without_original_headline(self):
        x = build(copy.deepcopy(BASE), "ph_afp_articles")
        self.assertEqual(x["candidate_count"], 1)
        self.assertEqual(x["records"][0]["official_issuer"], "ph_afp")
        self.assertIsNone(x["records"][0]["official_republisher"])
        self.assertFalse(x["public_release_enabled"])
        self.assertFalse(x["production_import_enabled"])
        self.assertNotIn("ORIGINAL HEADLINE", json.dumps(x))
        self.assertEqual(x["records"][0]["review_state"], "held")

    def test_indonesia_candidate_keeps_issuer_distinction(self):
        x = build(indonesia(), "id_kemhan_news")
        self.assertIsNone(x["records"][0]["official_issuer"])
        self.assertEqual(x["records"][0]["official_republisher"], "id_kemhan")
        self.assertNotIn("title_original", json.dumps(x))

    def test_stable_metadata_digests(self):
        one = build(indonesia(), "id_kemhan_news")
        two = build(indonesia(), "id_kemhan_news")
        self.assertEqual(one, two)
        other = indonesia()
        other["results"][0]["identity"] = "kemhan:/2026/10/15/another.html"
        other["results"][0]["url"] = "https://www.kemhan.go.id/2026/10/15/another.html"
        self.assertNotEqual(one["metadata_manifest_sha256"],
                            build(other, "id_kemhan_news")["metadata_manifest_sha256"])

    def test_geographic_discrepancy_is_always_held(self):
        r = indonesia()
        r["results"][0]["url"] = "https://www.kemhan.go.id" + KEMHAN_HELD
        r["results"][0]["identity"] = "kemhan:" + KEMHAN_HELD
        r["results"][0]["published_date"] = "2026-10-02"
        x = build(r, "id_kemhan_news")
        self.assertEqual(x["semantic_exception_count"], 1)
        self.assertEqual(x["records"][0]["semantic_exception_hold"],
                         "publisher_geography_discrepancy")

    def test_wrong_host_is_held(self):
        r = indonesia()
        r["results"][0]["url"] = "https://kemhan.gov.bad/2026/10/15/notice.html"
        with self.assertRaisesRegex(IntakeHold, "foreign_official_url"):
            build(r, "id_kemhan_news")

    def test_mismatched_kemhan_identity_is_held(self):
        r = indonesia()
        r["results"][0]["identity"] = "kemhan:/2026/10/15/other.html"
        with self.assertRaisesRegex(IntakeHold, "invalid_kemhan_official_identity"):
            build(r, "id_kemhan_news")

    def test_mismatched_kemhan_date_is_held(self):
        r = indonesia()
        r["results"][0]["published_date"] = "2026-10-14"
        with self.assertRaisesRegex(IntakeHold, "kemhan_date_and_url_disagree"):
            build(r, "id_kemhan_news")

    def test_fake_afp_path_is_held(self):
        r = copy.deepcopy(BASE)
        r["results"][0]["url"] = "https://www.afp.mil.ph/private/notice"
        with self.assertRaisesRegex(IntakeHold, "invalid_afp_official_identity"):
            build(r, "ph_afp_articles")

    def test_duplicate_is_rejected(self):
        r = copy.deepcopy(BASE)
        r["results"].append(copy.deepcopy(r["results"][0]))
        r["sources"][0]["stored_records"] = 2
        r["sources"][0]["query_matches"] = 2
        r["matched_total"] = 2
        with self.assertRaisesRegex(IntakeHold, "duplicate_source"):
            build(r, "ph_afp_articles")

    def test_truncated_or_search_report_is_held(self):
        for key, value in (("truncated", True), ("query", "secret"),
                           ("public_release_authorized", True)):
            with self.subTest(key=key):
                r = copy.deepcopy(BASE)
                r[key] = value
                with self.assertRaises(IntakeHold):
                    build(r, "ph_afp_articles")

    def test_unchanged_git_sha_must_match_every_record(self):
        r = copy.deepcopy(BASE)
        r["results"][0]["state_commit"] = "b" * 40
        with self.assertRaisesRegex(IntakeHold, "source_version"):
            build(r, "ph_afp_articles")

    def test_foreign_family_and_extra_source_columns_are_held(self):
        with self.assertRaisesRegex(IntakeHold, "unapproved_metadata_source_family"):
            build(copy.deepcopy(BASE), "ph_nsc_official_statements")
        r = copy.deepcopy(BASE)
        r["results"][0]["text_original"] = "PRIVATE DATA"
        with self.assertRaisesRegex(IntakeHold, "unexpected_source_record_fields"):
            build(r, "ph_afp_articles")

    def test_no_fabricated_completeness_for_zero_rows(self):
        r = copy.deepcopy(BASE)
        r["results"] = []
        r["matched_total"] = 0
        r["sources"][0]["stored_records"] = 0
        r["sources"][0]["query_matches"] = 0
        with self.assertRaisesRegex(IntakeHold, "incomplete_source_family_snapshot"):
            build(r, "ph_afp_articles")


if __name__ == "__main__":
    unittest.main()
