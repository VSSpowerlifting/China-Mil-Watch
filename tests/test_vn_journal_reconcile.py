"""Synthetic-only integration of journal category hints with article dates."""
import json
import unittest
from dataclasses import replace

from scraper.sources import vn_journal_listing as listing
from scraper.sources import vn_journal_article as article_parser
from scraper.sources.vn_journal_reconcile import (
    ReconciliationRefused, reconcile_article,
)
from tests.test_vn_journal_article import URL, page


def fixture_observations(*, hint="09/30/2026", include_article=True,
                         second_hint=None, second_url=None):
    observations = []
    for i, (category, url) in enumerate(listing.CATEGORY_URLS.items()):
        target = ("https://tapchiqptd.vn/en/news/fictional-other/%d.html" % (28001+i))
        if include_article and i in (0, 1):
            target = second_url if i == 1 and second_url else URL
        label = second_hint if i == 1 and second_hint is not None else hint
        html = ("<html><body><div class='listing-row'>"
                "<a href='%s'>Synthetic journal link</a>"
                "<span>%s</span></div></body></html>" % (target, label))
        observations.append(listing.parse_category_html(html, url))
    return observations


def article():
    return article_parser.parse_desktop_article(page(), URL)


class JournalListingArticleReconciliationTests(unittest.TestCase):
    def test_matching_article_date_and_source_identity(self):
        result = reconcile_article(fixture_observations(), article())
        self.assertEqual(result["source_identity"], "vndj-en:26936")
        self.assertEqual(result["article_page_date"], "2026-09-30")
        self.assertEqual(result["listing_date_hint"], "2026-09-30")
        self.assertEqual(result["listing_date_status"], "matches_article_date")
        self.assertEqual(result["listing_pages_observed"], ["news", "theory-and-practice"])
        self.assertEqual(result["source_type"], "journal_commentary_not_ministry_directive")
        self.assertFalse(result["editorial_review_required"])
        self.assertFalse(result["article_date_human_verified"])
        self.assertFalse(result["full_text_retention_authorized"])

    def test_listing_disagreement_is_visible_not_overwritten(self):
        result = reconcile_article(fixture_observations(hint="09/29/2026"), article())
        self.assertEqual(result["listing_date_status"], "date_hint_disagrees")
        self.assertEqual(result["article_page_date"], "2026-09-30")
        self.assertEqual(result["listing_date_hint"], "2026-09-29")
        self.assertTrue(result["editorial_review_required"])

    def test_missing_hint_does_not_turn_site_clock_into_date(self):
        result = reconcile_article(fixture_observations(hint="No article date printed"), article())
        self.assertEqual(result["listing_date_status"], "no_listing_date_hint")
        self.assertIsNone(result["listing_date_hint"])
        self.assertTrue(result["editorial_review_required"])

    def test_not_visible_is_not_publication_deletion(self):
        result = reconcile_article(fixture_observations(include_article=False), article())
        self.assertEqual(result["listing_date_status"], "not_visible_in_observed_pages")
        self.assertEqual(result["listing_pages_observed"], [])
        self.assertIsNone(result["listing_date_hint"])
        self.assertFalse(result["historical_completeness_proven"])
        self.assertTrue(result["editorial_review_required"])

    def test_original_body_and_author_never_leak_into_result(self):
        payload = json.dumps(reconcile_article(fixture_observations(), article()))
        for text in ("Synthetic academy report", "EXAMPLE AUTHOR", "Synthetic photograph caption",
                     "First substantive fictional paragraph", "Wednesday, September"):
            self.assertNotIn(text, payload)
        self.assertEqual(json.loads(payload)["public_record_authorized"], False)

    def test_listing_page_does_not_define_permalinks_category(self):
        observations = fixture_observations()
        self.assertEqual(observations[0].candidates[0].category_page, "news")
        self.assertEqual(observations[0].candidates[0].category_from_permalink, "theory-and-practice")
        result = reconcile_article(observations, article())
        self.assertIn("news", result["listing_pages_observed"])
        self.assertNotIn("ministry_directive", result["source_type"].replace("not_ministry_directive", ""))

    def test_cross_category_hint_conflict_refused(self):
        observations = fixture_observations(second_hint="09/29/2026")
        with self.assertRaisesRegex(ReconciliationRefused, "conflicting listing hints"):
            reconcile_article(observations, article())

    def test_cross_category_url_collision_refused(self):
        observations = fixture_observations(
            second_url="https://tapchiqptd.vn/en/theory-and-practice/different-slug/26936.html")
        with self.assertRaisesRegex(ReconciliationRefused, "conflicting canonical URLs"):
            reconcile_article(observations, article())

    def test_article_parser_date_field_must_match_original_stamp(self):
        damaged = replace(article(), published_date="2026-09-29")
        with self.assertRaisesRegex(ReconciliationRefused, "parser fields disagree"):
            reconcile_article(fixture_observations(), damaged)

    def test_article_reuse_or_author_name_claim_refused(self):
        for field in ("full_text_reuse_authorized", "author_name_verified"):
            modified = replace(article(), **{field: True})
            with self.subTest(field=field):
                with self.assertRaisesRegex(ReconciliationRefused, "source/provenance"):
                    reconcile_article(fixture_observations(), modified)

    def test_listing_verified_date_claim_refused(self):
        observations = fixture_observations()
        first = observations[0]
        candidate = replace(first.candidates[0], article_date_verified=True)
        observations[0] = replace(first, candidates=(candidate,))
        with self.assertRaisesRegex(ReconciliationRefused, "verified-date"):
            reconcile_article(observations, article())

    def test_incomplete_or_duplicate_listing_page_refused(self):
        observations = fixture_observations()
        with self.assertRaisesRegex(ReconciliationRefused, "exactly four"):
            reconcile_article(observations[:3], article())
        observations[1] = observations[0]
        with self.assertRaisesRegex(ReconciliationRefused, "duplicated category"):
            reconcile_article(observations, article())

    def test_article_absent_from_parser_type_refused(self):
        with self.assertRaisesRegex(ReconciliationRefused, "offline journal article"):
            reconcile_article(fixture_observations(), {"url": URL})

    def test_no_network_or_db_io_in_reconciliation_module(self):
        import inspect
        from scraper.sources import vn_journal_reconcile
        code = inspect.getsource(vn_journal_reconcile)
        for forbidden in ("requests.", "urlopen(", "sqlite3", "write_text(", "open(", "datetime.now("):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
