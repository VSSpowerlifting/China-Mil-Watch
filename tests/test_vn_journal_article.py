"""Synthetic-only National Defence Journal article parser regression tests."""
import unittest
from scraper.sources import vn_journal_article as journal

URL = ("https://tapchiqptd.vn/en/theory-and-practice/"
       "military-technical-academy-proactively-embraces-international-integration-and-elevates-int/"
       "26936.html")
MOBILE_URL = ("https://m.tapchiqptd.vn/en/theory-and-practice/"
              "military-technical-academy-proactively-embraces-international-integration-and-elevates-int-"
              "26936.html")
STAMP = "Wednesday, September 30, 2026, 14:48 (GMT+7)"


def page(date=STAMP, title="Synthetic academy report", body=None, external=""):
    body = body if body is not None else (
        "<p>First substantive fictional paragraph about cooperation.</p>"
        "<table><tr><td><img src='/demo.png'></td></tr><tr><td>"
        "Synthetic photograph caption</td></tr></table>"
        "<p>Second fictional paragraph about training.</p>"
        "<p><strong><em>Major General, Prof., PhD EXAMPLE AUTHOR</em></strong></p>"
    )
    return (
        "<html><body>"
        "<div id='header_menu'><span id='subTopMenu-time'>"
        "<p>Thursday, October 8, 2026, 09:00 (GMT+7)</p></span></div>"
        "<div class='page-main-left-newsdt'>"
        "<div class='newsdt-page-ct'>"
        "<div class='newsdt-page-ct-time'><span>" + date + "</span></div>"
        "<div class='newsdt-page-ct-tit'>" + title + "</div>"
        "<div class='newsdt-page-ct-text'>" + body + "</div>"
        "</div><div id='tag-widget'>TAG synthetic headline</div>"
        "<div class='news-other'>Recommended unrelated item</div></div>"
        + external + "</body></html>"
    )


class JournalExtractorTests(unittest.TestCase):
    def test_exact_article_specific_boundaries(self):
        result = journal.parse_desktop_article(page(), URL)
        self.assertEqual(result.url, URL)
        self.assertEqual(result.source_identity, "vndj-en:26936")
        self.assertEqual(result.published_date, "2026-09-30")
        self.assertEqual(result.published_date_original, STAMP)
        self.assertEqual(result.title_original, "Synthetic academy report")
        self.assertEqual(result.author_credit_original,
                         "Major General, Prof., PhD EXAMPLE AUTHOR")
        self.assertEqual(result.language_tag, "en")
        self.assertEqual([kind for kind, _ in result.body_blocks],
                         ["paragraph", "caption_or_table", "paragraph"])
        self.assertIn("Synthetic photograph caption", result.text_original)
        for excluded in ("TAG synthetic headline", "Recommended unrelated",
                         "October 8", "EXAMPLE AUTHOR", "subTopMenu-time"):
            self.assertNotIn(excluded, result.text_original)
        self.assertFalse(result.author_name_verified)
        self.assertFalse(result.full_text_reuse_authorized)

    def test_no_author_is_invented(self):
        body = ("<p>Original fictional article lead</p>"
                "<p>Article ends without a signed author.</p>")
        record = journal.parse_desktop_article(page(body=body), URL)
        self.assertIsNone(record.author_credit_original)
        self.assertIn("Article ends without", record.text_original)
        self.assertEqual(len(record.body_blocks), 2)

    def test_terminal_rank_qualified_credit_with_trailing_role(self):
        body = ("<p>Fictional article body.</p>"
                "<p><strong><em>Major General, Prof., PhD EXAMPLE AUTHOR</em></strong>"
                ", Deputy Director of the Academy</p>")
        record = journal.parse_desktop_article(page(body=body), URL)
        self.assertEqual(record.author_credit_original,
                         "Major General, Prof., PhD EXAMPLE AUTHOR , Deputy Director of the Academy")
        self.assertNotIn("Deputy Director", record.text_original)
        self.assertEqual(len(record.body_blocks), 1)

    def test_rank_mentioned_in_body_does_not_automatically_remove_prose(self):
        body = ("<p>A report about a Major General's service.</p>"
                "<p><em>Professor of strategy, quoted in the story.</em></p>")
        record = journal.parse_desktop_article(page(body=body), URL)
        self.assertIsNone(record.author_credit_original)
        self.assertEqual(len(record.body_blocks), 2)

    def test_bad_or_current_page_clock_refused(self):
        with self.assertRaisesRegex(journal.ExtractionRefused, "publication date"):
            journal.parse_desktop_article(page(date="October 8, 2026"), URL)
        with self.assertRaisesRegex(journal.ExtractionRefused, "publication date"):
            journal.parse_desktop_article(page(date="Monday, September 30, 2026, 14:48 (GMT+7)"),
                                          URL)

    def test_missing_article_fields_never_fall_back_to_navigation(self):
        html = page().replace('class="no-such-field"', 'class="x"')
        html = html.replace("class='newsdt-page-ct-tit'", "class='missing-title'")
        with self.assertRaisesRegex(journal.ExtractionRefused, "article headline"):
            journal.parse_desktop_article(html, URL)
        html = page().replace("class='newsdt-page-ct-text'", "class='missing-body'")
        with self.assertRaisesRegex(journal.ExtractionRefused, "article body"):
            journal.parse_desktop_article(html, URL)

    def test_duplicate_main_article_blocks_refuse(self):
        html = page(external=(
            "<div class='page-main-left-newsdt'><div class='newsdt-page-ct'>"
            "<div class='newsdt-page-ct-time'><span>" + STAMP + "</span></div>"
            "<div class='newsdt-page-ct-tit'>Ambiguous duplicate</div>"
            "<div class='newsdt-page-ct-text'><p>Test</p></div></div></div>"
        ))
        with self.assertRaisesRegex(journal.ExtractionRefused, "article container"):
            journal.parse_desktop_article(html, URL)

    def test_unexpected_body_container_children_fail_closed(self):
        html = page(body="<p>Valid lead</p><div class='unknown'>Other prose</div>")
        with self.assertRaisesRegex(journal.ExtractionRefused, "unknown journal body structure"):
            journal.parse_desktop_article(html, URL)

    def test_title_only_shell_refused(self):
        html = page(title="Synthetic academy report",
                    body="<p>Synthetic academy report</p>")
        with self.assertRaisesRegex(journal.ExtractionRefused, "only a title"):
            journal.parse_desktop_article(html, URL)

    def test_mobile_and_query_string_not_accepted_by_desktop_parser(self):
        with self.assertRaisesRegex(journal.ExtractionRefused, "desktop canonical"):
            journal.parse_desktop_article(page(), MOBILE_URL)
        with self.assertRaisesRegex(journal.ExtractionRefused, "unrecognized journal URL"):
            journal.parse_desktop_article(page(), URL + "?print=1")


if __name__ == "__main__":
    unittest.main()
