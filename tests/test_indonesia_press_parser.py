"""Offline-only contracts for the UNREGISTERED Siaran Pers parser prototype.

Synthetic inputs derive from the immutable real Kemhan *Berita* HTML fixtures
to exercise a page-family substitution. They are NOT genuine Siaran Pers raw
captures and must never be presented as source-fidelity validation.
"""
import socket
import unittest
from datetime import date
from unittest import mock
from bs4 import BeautifulSoup

from scraper.sources.id_kemhan import LISTING as NEWS
from scraper.sources.id_kemhan_press import (
    LISTING, PressBody, parse_press_article, parse_press_listing, listing_url,
)
from tests.test_indonesia_korea_shadow import fixture, ROWS


class PressParserPreview(unittest.TestCase):
    def setUp(self):
        guard = mock.patch.object(socket.socket, "connect",
                                  side_effect=AssertionError("network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)

    @staticmethod
    def synthetic_listing():
        # BERITA real fixture with source family names changed for simulation.
        return fixture("kemhan-news.bin").decode("utf-8").replace(NEWS, LISTING)

    @staticmethod
    def synthetic_article():
        row = next(r for r in ROWS if r.get("capture") == "kemhan-article.bin")
        return row["url"], fixture(row["capture"]).decode("utf-8")

    def test_parser_not_enabled_as_source_adapter_or_manifest(self):
        from core.collection.contract import SourceAdapter
        from scripts.shadow_collect_desk import DESKS
        from core.manifests import load_all_desks
        self.assertFalse(issubclass(type(parse_press_listing), SourceAdapter))
        self.assertNotIn("id_kemhan_press", DESKS)
        self.assertNotIn("indonesia", load_all_desks())

    def test_source_family_and_page_guard(self):
        self.assertEqual(listing_url(LISTING, 1), LISTING)
        self.assertEqual(listing_url(LISTING + "/page/2", 2),
                         LISTING + "/page/2")
        for link, page in [(NEWS, 1), (LISTING, 0), (LISTING + "/page/3", 2)]:
            with self.subTest(link=link), self.assertRaises(ValueError):
                listing_url(link, page)

    def test_simulated_press_page_extracts_only_labeled_rows(self):
        page = parse_press_listing(self.synthetic_listing())
        self.assertEqual(len(page.records), 10)
        self.assertEqual(page.next_url, LISTING + "/page/2")
        self.assertEqual([r.published_date for r in page.records],
                         sorted((r.published_date for r in page.records), reverse=True))
        self.assertTrue(all("www.kemhan.go.id" in r.url for r in page.records))

    def test_real_berita_page_does_not_masquerade_as_press(self):
        with self.assertRaises(ValueError):
            parse_press_listing(fixture("kemhan-news.bin").decode())

    def test_missing_category_label_refused(self):
        soup = BeautifulSoup(self.synthetic_listing(), "html.parser")
        first = soup.select_one(".listing-news")
        for link in first.select('a[href="' + LISTING + '"]'):
            link.decompose()
        with self.assertRaisesRegex(ValueError, "not labeled"):
            parse_press_listing(str(soup))

    def test_page_marker_drift_refused(self):
        soup = BeautifulSoup(self.synthetic_listing(), "html.parser")
        soup.select_one("a.active").string = "17"
        with self.assertRaisesRegex(ValueError, "page index"):
            parse_press_listing(str(soup))

    def test_wrong_listing_date_refused(self):
        soup = BeautifulSoup(self.synthetic_listing(), "html.parser")
        soup.select_one(".listing-news small").string = "Senin, 1 Januari 2024"
        with self.assertRaisesRegex(ValueError, "publication date"):
            parse_press_listing(str(soup))

    def test_next_page_missing_refused(self):
        soup = BeautifulSoup(self.synthetic_listing(), "html.parser")
        for anchor in soup.select('a[href="' + LISTING + '/page/2"]'):
            anchor.decompose()
        with self.assertRaisesRegex(ValueError, "next page missing"):
            parse_press_listing(str(soup))

    def test_original_news_body_replayed_only_as_synthetic_article_proof(self):
        url, html = self.synthetic_article()
        from scraper.sources.id_kemhan import KemhanAdapter
        from core.manifests import load_manifest
        from pathlib import Path
        source = load_manifest(Path(__file__).resolve().parents[1] /
                               "shadow/id_kemhan/manifest.json").sources[0]
        original = KemhanAdapter(source).parse_article(html, url)
        doc = parse_press_article(html, url=url, listed_title=original.title_original,
                                  listed_date=original.published_date)
        self.assertIsInstance(doc, PressBody)
        self.assertEqual(doc.url, original.url)
        self.assertEqual(doc.published_date, original.published_date)
        self.assertIn("Jakarta", doc.original_text)
        self.assertNotIn("Statistik Pengunjung", doc.original_text)
        self.assertEqual(doc.publication_kind, "official_press_release")

    def test_page_date_canonical_and_heading_mismatch_fail_closed(self):
        url, html = self.synthetic_article()
        from scraper.sources.id_kemhan import KemhanAdapter
        from core.manifests import load_manifest
        from pathlib import Path
        source = load_manifest(Path(__file__).resolve().parents[1] /
                               "shadow/id_kemhan/manifest.json").sources[0]
        original = KemhanAdapter(source).parse_article(html, url)
        kw = dict(url=url, listed_title=original.title_original,
                  listed_date=original.published_date)
        with self.assertRaisesRegex(ValueError, "listed and URL"):
            parse_press_article(html, **{**kw, "listed_date": "2026-10-05"})
        with self.assertRaisesRegex(ValueError, "title disagrees"):
            parse_press_article(html, **{**kw, "listed_title": "Forged agreement"})
        with self.assertRaisesRegex(ValueError, "canonical"):
            parse_press_article(html.replace('rel="canonical"', 'rel="other"'), **kw)

    def test_empty_article_body_never_borrowed_from_sidebar(self):
        url, html = self.synthetic_article()
        from scraper.sources.id_kemhan import KemhanAdapter
        from core.manifests import load_manifest
        from pathlib import Path
        source = load_manifest(Path(__file__).resolve().parents[1] /
                               "shadow/id_kemhan/manifest.json").sources[0]
        original = KemhanAdapter(source).parse_article(html, url)
        soup = BeautifulSoup(html, "html.parser")
        article = soup.select_one(".def-page.article")
        for child in list(article.find_all(recursive=False)):
            if child.name in ("p", "div", "ol", "ul", "table", "blockquote"):
                child.decompose()
        with self.assertRaisesRegex(ValueError, "missing/short"):
            parse_press_article(str(soup), url=url,
                                listed_title=original.title_original,
                                listed_date=original.published_date)


if __name__ == "__main__":
    unittest.main()
