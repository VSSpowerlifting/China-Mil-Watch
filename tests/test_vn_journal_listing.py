"""Offline-only tests: four National Defence Journal category lists, no HTTP."""
import unittest

from scraper.sources import vn_journal_listing as l


def url(id, section="theory-and-practice", slug="fictional-article"):
    return ("https://tapchiqptd.vn/en/" + section + "/" + slug +
            "/" + str(id) + ".html")


def html(rows, extra=""):
    return "<html><body><div class='site-header'>Thursday, October 08, 2026, 08:30 (GMT+7)</div>" + "".join(
        '<div class="item"><a href="%s">Synthetic item</a><span>%s</span></div>' %
        (href, date)
        for href,date in rows
    )+ extra +"</body></html>"


class JournalCategoryListingTest(unittest.TestCase):
    def test_one_page_extracts_dated_candidates_without_site_clock(self):
        page=l.parse_category_html(html([
            (url(26936), "Wednesday, September 30, 2026, 14:48 (GMT+7)"),
            (url(26919, "research-and-discussion"),"Monday, September 28, 2026, 15:17 (GMT+7)"),
        ]),l.CATEGORY_URLS["theory-and-practice"])
        self.assertEqual(len(page.candidates),2)
        self.assertEqual(page.dated_hint_count,2)
        dates={x.source_identity:x.date_hint for x in page.candidates}
        self.assertEqual(dates["vndj-en:26936"],"2026-09-30")
        self.assertEqual(dates["vndj-en:26919"],"2026-09-28")
        self.assertFalse(page.completeness_proven)
        self.assertFalse(page.pagination_verified)
        self.assertTrue(all(not x.article_date_verified for x in page.candidates))

    def test_undated_sidebar_repetition_dedupes_with_dated_primary(self):
        link=url(26936)
        page=l.parse_category_html(html([(link,"Wednesday, September 30, 2026, 14:48 (GMT+7)")],
          "<div class='most-read'><a href='%s'>Repeat</a></div>" % link),
          l.CATEGORY_URLS["theory-and-practice"])
        self.assertEqual(len(page.candidates),1)
        self.assertEqual(page.duplicate_links,1)
        self.assertEqual(page.candidates[0].date_hint,"2026-09-30")

    def test_page_header_site_clock_does_not_create_date_hint(self):
        item=url(26936)
        page=l.parse_category_html(html([(item,"This story lacks a date")]),
                                   l.CATEGORY_URLS["theory-and-practice"])
        self.assertEqual(page.candidates[0].date_hint,None)
        self.assertEqual(page.dated_hint_count,0)

    def test_ambiguous_multiple_article_links_in_one_wrapper_get_no_date(self):
        page=l.parse_category_html(
          "<html><body><div class='group'><a href='%s'>A</a>"
          "<a href='%s'>B</a><span>Wednesday, September 30, 2026, 14:48 (GMT+7)</span>"
          "</div></body></html>" % (url(26936),url(26937)),
          l.CATEGORY_URLS["theory-and-practice"])
        self.assertEqual(len(page.candidates),2)
        self.assertEqual(page.dated_hint_count,0)

    def test_live_site_clock_in_ancestor_cannot_become_article_date(self):
        # The header clock and one linked article may share a wrapper.
        # That does not make the clock an article publication date.
        html_text = (
            "<html><body><div class='shared-layout'>"
            "<span id='subTopMenu-time'>Thursday, October 08, 2026, 10:23 (GMT+7)</span>"
            "<div class='undated-story'><a href='%s'>Synthetic story</a></div>"
            "</div></body></html>" % url(26936)
        )
        page = l.parse_category_html(html_text, l.CATEGORY_URLS["news"])
        self.assertEqual(len(page.candidates), 1)
        self.assertIsNone(page.candidates[0].date_hint)
        self.assertEqual(page.dated_hint_count, 0)

    def test_local_article_date_remains_valid_beside_site_clock(self):
        html_text = (
            "<html><body><div class='shared-layout'>"
            "<span id='subTopMenu-time'>Thursday, October 08, 2026, 10:23 (GMT+7)</span>"
            "<div class='local-story'><a href='%s'>Synthetic story</a>"
            "<span>Wednesday, September 30, 2026, 14:48 (GMT+7)</span></div>"
            "</div></body></html>" % url(26936)
        )
        page = l.parse_category_html(html_text, l.CATEGORY_URLS["news"])
        self.assertEqual(page.candidates[0].date_hint, "2026-09-30")
        self.assertEqual(page.dated_hint_count, 1)

    def test_bad_date_weekday_is_refused_not_silently_corrected(self):
        with self.assertRaisesRegex(l.ListingRefused,"inconsistent"):
            l.parse_category_html(
              html([(url(26936),"Monday, September 30, 2026, 14:48 (GMT+7)")]),
              l.CATEGORY_URLS["theory-and-practice"])

    def test_disallows_mobile_alias_and_redirect_query_in_discovery(self):
        legitimate=url(26936)
        extra=(
            "<a href='https://m.tapchiqptd.vn/en/theory-and-practice/fictional-article-26936.html'>mobile</a>"
            "<a href='%s?x=1'>query</a>"
            "<a href='http://tapchiqptd.vn/en/theory-and-practice/fictional-article/26936.html'>HTTP</a>"
            "<a href='https://untrusted.example/en/theory-and-practice/fictional-article/26936.html'>foreign</a>"
        ) % legitimate
        page=l.parse_category_html(html([(legitimate,"09/30/2026")],extra),
                                   l.CATEGORY_URLS["theory-and-practice"])
        self.assertEqual(len(page.candidates),1)
        self.assertEqual(page.duplicate_links,0)
        self.assertEqual(page.dated_hint_count,1)

    def test_identity_collision_rejected(self):
        s=html([
            (url(26936),"09/30/2026"),
            (url(26936,slug="inconsistent-slug"),"09/30/2026"),
        ])
        with self.assertRaisesRegex(l.ListingRefused,"different canonical"):
            l.parse_category_html(s,l.CATEGORY_URLS["theory-and-practice"])

    def test_unknown_category_url_and_empty_html_refused(self):
        with self.assertRaisesRegex(l.ListingRefused,"unexpected"):
            l.parse_category_html(html([(url(26936),"09/30/2026")]),
                                  "https://tapchiqptd.vn/en/news-54.html?page=2")
        with self.assertRaisesRegex(l.ListingRefused,"no canonical"):
            l.parse_category_html("<html><body><div>Only decoration</div></body></html>",
                                  l.CATEGORY_URLS["news"])

    def test_union_reconciles_overlapping_ids_without_claiming_completeness(self):
        pages=[]
        for name in l.CATEGORY_URLS:
            pages.append(l.parse_category_html(html([
                (url(26936),"09/30/2026"),
                (url(26937,slug="second"),"09/29/2026"),
            ]),l.CATEGORY_URLS[name]))
        combined=l.merge_category_observations(pages)
        self.assertEqual(combined["observed_category_count"],4)
        self.assertTrue(combined["all_four_categories_observed"])
        self.assertEqual(combined["unique_observed_article_count"],2)
        self.assertEqual(combined["dated_hint_count"],2)
        self.assertFalse(combined["pagination_proven"])
        self.assertFalse(combined["full_date_bounded_completeness_proven"])
        self.assertFalse(combined["source_body_retention_authorized"])

    def test_conflicting_category_dates_refused(self):
        a=l.parse_category_html(html([(url(26936),"09/30/2026")]),l.CATEGORY_URLS["news"])
        b=l.parse_category_html(html([(url(26936),"09/29/2026")]),l.CATEGORY_URLS["theory-and-practice"])
        with self.assertRaisesRegex(l.ListingRefused,"inconsistent"):
            l.merge_category_observations([a,b])

    def test_duplicate_page_observations_refused(self):
        a=l.parse_category_html(html([(url(26936),"09/30/2026")]),l.CATEGORY_URLS["news"])
        with self.assertRaisesRegex(l.ListingRefused,"duplicate category"):
            l.merge_category_observations([a,a])


if __name__=="__main__":
    unittest.main()
