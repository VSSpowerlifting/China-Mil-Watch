"""
Xinhua Military adapter — offline, against recorded fixtures.

Every page here was captured from www.news.cn on 2026-09-16 with the project
user agent and committed under tests/fixtures/xinhua_mil/. No test in this file
makes a network request: a live probe that becomes a required offline
dependency turns an outage at a source into a red build, which teaches the
suite to be ignored.
"""

from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bs4 import BeautifulSoup                                    # noqa: E402

from scraper.sources import xinhua_mil as X                      # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "xinhua_mil"
CAPTURE_DATE = datetime.date(2026, 9, 16)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestCanonicalUrl(unittest.TestCase):
    """Identity is a pure function of the discovered link, or it is nothing."""

    def test_a_relative_listing_link_becomes_an_absolute_https_url(self):
        self.assertEqual(
            X.canonical_url("/milpro/20260915/" + "a" * 32 + "/c.html"),
            "https://www.news.cn/milpro/20260915/" + "a" * 32 + "/c.html")

    def test_query_and_fragment_are_dropped(self):
        base = "/milpro/20260915/" + "b" * 32 + "/c.html"
        self.assertEqual(X.canonical_url(base + "?from=rss#top"),
                         "https://www.news.cn" + base)

    def test_a_bare_host_is_normalised(self):
        path = "/milpro/20260915/" + "c" * 32 + "/c.html"
        self.assertEqual(X.canonical_url("https://news.cn" + path),
                         "https://www.news.cn" + path)

    def test_a_foreign_host_is_refused(self):
        self.assertIsNone(X.canonical_url(
            "https://example.com/milpro/20260915/" + "d" * 32 + "/c.html"))

    def test_a_non_article_path_is_refused(self):
        for href in ("/milpro/", "/politics/20260915/x/c.html", "",
                     "/milpro/2026915/" + "e" * 32 + "/c.html",
                     "/milpro/20260915/tooshort/c.html"):
            with self.subTest(href=href):
                self.assertIsNone(X.canonical_url(href))

    def test_identity_is_the_hex_segment(self):
        path = "/milpro/20260915/" + "f" * 32 + "/c.html"
        self.assertEqual(X.article_identity("https://www.news.cn" + path),
                         "f" * 32)

    def test_a_malformed_path_date_yields_no_date(self):
        self.assertIsNone(X.url_date(
            "https://www.news.cn/milpro/20261332/" + "a" * 32 + "/c.html"))


class TestListing(unittest.TestCase):
    """Discovery: what the server-rendered listing actually carries."""

    @classmethod
    def setUpClass(cls):
        cls.soup = BeautifulSoup(fixture("listing.html"), "lxml")
        cls.urls = []
        for anchor in cls.soup.find_all("a", href=True):
            url = X.canonical_url(anchor["href"])
            if url and url not in cls.urls:
                cls.urls.append(url)

    def test_the_listing_is_server_rendered(self):
        """The whole premise: no JavaScript, and links are in the HTML."""
        self.assertGreater(
            len(self.urls), 50,
            "the listing carried almost no article links — if this fails, "
            "re-measure before assuming the adapter is wrong")

    def test_every_discovered_url_is_canonical_and_unique(self):
        self.assertEqual(len(self.urls), len(set(self.urls)))
        for url in self.urls:
            self.assertTrue(url.startswith("https://www.news.cn/milpro/"))
            self.assertIsNotNone(X.article_identity(url))

    def test_identity_never_collides(self):
        identities = [X.article_identity(u) for u in self.urls]
        self.assertEqual(len(identities), len(set(identities)))

    def test_every_url_carries_a_parseable_date(self):
        for url in self.urls:
            with self.subTest(url=url):
                self.assertIsNotNone(X.url_date(url))

    def test_the_window_selects_only_dates_inside_it(self):
        scraper = X.XinhuaMilScraper(target_date=CAPTURE_DATE)
        start = CAPTURE_DATE - datetime.timedelta(days=X._LOOKBACK_DATES - 1)
        selected = [u for u in self.urls
                    if start <= X.url_date(u) <= CAPTURE_DATE]
        self.assertTrue(selected, "the capture day selected nothing")
        for url in selected:
            self.assertGreaterEqual(X.url_date(url), start)
            self.assertLessEqual(X.url_date(url), CAPTURE_DATE)
        self.assertLess(len(selected), len(self.urls),
                        "the window excluded nothing, so it is not a window")
        del scraper

    def test_the_window_excludes_the_archive_rail(self):
        """The listing carries a rail reaching back years; it must not enter."""
        oldest = min(X.url_date(u) for u in self.urls)
        self.assertLess(oldest, CAPTURE_DATE - datetime.timedelta(days=90),
                        "fixture no longer contains an archive rail")
        start = CAPTURE_DATE - datetime.timedelta(days=X._LOOKBACK_DATES - 1)
        self.assertLess(oldest, start)


class TestArticleExtraction(unittest.TestCase):
    """Retrieval, extraction and encoding on four recorded articles."""

    PAGES = ("article_globalhawk.html", "article_energy_targets.html",
             "article_hormuz_transits.html", "article_mq1_downed.html")

    def parsed(self, name, url=None):
        scraper = X.XinhuaMilScraper(target_date=CAPTURE_DATE)
        url = url or ("https://www.news.cn/milpro/20260915/"
                      + "a" * 32 + "/c.html")
        return scraper.parse_article(url, fixture(name))

    def test_every_recorded_article_yields_a_title_and_prose(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                article = self.parsed(name)
                self.assertIsNotNone(article)
                self.assertTrue(article["title_original"].strip())
                self.assertTrue(
                    article["text_original"].strip(),
                    "a recorded article extracted no prose")

    def test_chinese_survives_extraction_intact(self):
        """Encoding integrity: the body is Chinese, not mojibake."""
        article = self.parsed("article_globalhawk.html")
        self.assertIn("新华社", article["text_original"])
        self.assertIn("无人侦察机", article["title_original"])
        for bad in ("â", "Ã", "�"):
            self.assertNotIn(bad, article["text_original"])

    def test_the_title_does_not_carry_the_agency_suffix(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertNotIn("新华网",
                                 self.parsed(name)["title_original"])

    def test_the_date_comes_from_the_path(self):
        url = "https://www.news.cn/milpro/20260915/" + "a" * 32 + "/c.html"
        self.assertEqual(
            self.parsed("article_globalhawk.html", url)["published_date"],
            "2026-09-15")

    def test_the_path_wins_when_the_meta_tag_disagrees(self):
        """A silent tie-break is how a date defect survives."""
        url = "https://www.news.cn/milpro/20260101/" + "a" * 32 + "/c.html"
        article = self.parsed("article_globalhawk.html", url)
        self.assertEqual(article["published_date"], "2026-01-01")

    def test_the_stored_url_is_canonical(self):
        messy = ("https://news.cn/milpro/20260915/" + "a" * 32
                 + "/c.html?from=timeline")
        self.assertEqual(
            self.parsed("article_globalhawk.html", messy)["url"],
            "https://www.news.cn/milpro/20260915/" + "a" * 32 + "/c.html")

    def test_extraction_is_deterministic(self):
        """Same bytes in, same record out — twice."""
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertEqual(self.parsed(name), self.parsed(name))


class TestHonestFailure(unittest.TestCase):
    """What the adapter does when there is nothing to report."""

    def scraper(self):
        return X.XinhuaMilScraper(target_date=CAPTURE_DATE)

    def test_a_media_only_shell_yields_no_body_rather_than_a_caption(self):
        shell = ('<html><head><title>图集 -新华网</title>'
                 '<meta name="publishdate" content="2026-09-15"></head>'
                 '<body><h1>图集：演习现场</h1><div id="detail">'
                 '<center><img src="a.jpg"/></center></div></body></html>')
        article = self.scraper().parse_article(
            "https://www.news.cn/milpro/20260915/" + "a" * 32 + "/c.html",
            shell)
        self.assertEqual(article["text_original"], "")
        self.assertEqual(article["title_original"], "图集：演习现场")

    def test_a_page_with_no_detail_container_yields_no_body(self):
        page = ("<html><body><h1>标题</h1><p>"
                + "这是导航文字。" * 20 + "</p></body></html>")
        article = self.scraper().parse_article(
            "https://www.news.cn/milpro/20260915/" + "a" * 32 + "/c.html",
            page)
        self.assertEqual(article["text_original"], "",
                         "prose was imported from outside the article body")

    def test_a_titleless_page_is_refused(self):
        self.assertIsNone(self.scraper().parse_article(
            "https://www.news.cn/milpro/20260915/" + "a" * 32 + "/c.html",
            "<html><body><div id='detail'><p>正文正文正文正文</p></div>"
            "</body></html>"))

    def test_the_stub_marker_is_gone(self):
        """`IS_STUB` told the health report this source cannot collect."""
        self.assertFalse(getattr(X.XinhuaMilScraper, "IS_STUB", False))


if __name__ == "__main__":
    unittest.main()
