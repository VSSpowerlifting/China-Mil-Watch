"""JCG shadow candidate parser and provenance contracts (network-free)."""
import hashlib
import json
import unittest
from pathlib import Path
from datetime import date
from types import SimpleNamespace

from core.collection import status as st
from core.collection.contract import CandidateReference, CaptureResult, CollectionWindow
from scraper.sources.jp_jcg_en import (
    JCGEnglishAdapter, LISTING, canon, source_date,
)


def jcg_source():
    return SimpleNamespace(slug="jp_jcg_press_en", enabled=True)


def listing(*rows):
    entries = "".join(
        '<dt><p class="topics-date">' + when + '</p></dt>'
        '<dd><a class="arrow-link" href="/e/topics_archive/article' + ident +
        '.html">' + title + '</a></dd>'
        for when, ident, title in rows
    )
    return ('<html><main><article class="main-article">'
            '<section class="topics has-pd"><dl class="topics-list">' +
            entries + '</dl></section></article></main></html>')


def article(ident, title, when="06 10 2026", iso="2026-10-06", body=None):
    body = body or (
        "Japan Coast Guard instructors delivered maritime law enforcement "
        "capacity-building training to the Philippine Coast Guard. " * 3
    )
    return ('<html><header><h1 class="main-logo">IGNORE WEBSITE NAV</h1></header>'
            '<main><article class="main-article">'
            '<section class="topics topics-article">'
            '<h1 class="entry-title">' + title + '</h1>'
            '<time datetime="' + iso + '">' + when + '</time>'
            '<div class="topics-article__main tich-text">'
            '<p>' + body + '</p>'
            '<p>Full published HTML original; <a href="upload/file.pdf">'
            'press PDF</a>.</p></div></section></article></main>'
            '<footer>IGNORE FOOTER</footer></html>')


class JCGSourceContracts(unittest.TestCase):
    def setUp(self):
        self.adapter = JCGEnglishAdapter(jcg_source())

    def test_declaration_is_disabled_and_outside_production_discovery(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "shadow/jp_jcg/manifest.json").read_text())
        self.assertEqual(manifest["desk"]["desk_id"], "japan_jcg")
        self.assertEqual(manifest["desk"]["public_status"], "shadow")
        self.assertFalse(manifest["desk"]["active"])
        self.assertEqual(len(manifest["sources"]), 1)
        self.assertFalse(manifest["sources"][0]["enabled"])
        self.assertEqual(manifest["sources"][0]["slug"], "jp_jcg_press_en")
        self.assertFalse((root / "desks/japan/manifest.json").exists())

    def test_dates_are_publisher_calendar_dates(self):
        self.assertEqual(source_date("06 10 2026"), "2026-10-06")
        self.assertEqual(source_date("2026-10-06"), "2026-10-06")
        self.assertEqual(source_date("2026.10.06"), "2026-10-06")
        self.assertEqual(source_date("October 6, 2026"), "2026-10-06")
        self.assertEqual(source_date("06 October, 2026"), "2026-10-06")
        with self.assertRaises(ValueError):
            source_date("last updated 2026-10-06")
        with self.assertRaises(ValueError):
            source_date("32 10 2026")

    def test_strict_first_party_canonical_identity(self):
        self.assertEqual(canon("https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html"),
                         "https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html")
        for url in ("http://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html",
                    "https://www.kaiho.mlit.go.jp/e/topics_archive/index.html",
                    "https://evil.example/e/topics_archive/article9455.html",
                    "https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html?a=1",
                    "https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html#title"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                canon(url)

    def test_index_preserves_repeated_titles_as_distinct_urls(self):
        s = listing(("06 10 2026", "9455", "Capacity Building Support for the PCG"),
                    ("06 10 2026", "9453", "Capacity Building Support for the PCG"),
                    ("29 09 2026", "9436", "BAKAMLA Cooperation"))
        page = self.adapter.parse_listing(s, (LISTING, None), 1)
        self.assertEqual([x["url"].split("/")[-1] for x in page.items],
                         ["article9455.html", "article9453.html", "article9436.html"])
        self.assertEqual([x["date"] for x in page.items],
                         ["2026-10-06", "2026-10-06", "2026-09-29"])
        self.assertIsNone(page.next_request)

    def test_no_silent_list_omissions_or_date_pairing_across_year_groups(self):
        with self.assertRaisesRegex(ValueError, "pairs incomplete"):
            self.adapter.parse_listing(listing(("06 10 2026", "9455", "Name")).replace(
                '<p class="topics-date">', '<p class="wrong-date">'),
                (LISTING, None), 1)
        with self.assertRaisesRegex(ValueError, "chronology"):
            self.adapter.parse_listing(
                listing(("29 09 2026", "9436", "Older"),
                        ("06 10 2026", "9455", "Newer")), (LISTING, None), 1)
        with self.assertRaisesRegex(ValueError, "repeated"):
            self.adapter.parse_listing(
                listing(("06 10 2026", "9455", "A"), ("06 10 2026", "9455", "B")),
                (LISTING, None), 1)
        with self.assertRaisesRegex(ValueError, "URL"):
            self.adapter.parse_listing(listing(("06 10 2026", "foo", "Bad URL")),
                                       (LISTING, None), 1)

    def test_unqualified_historical_format_counted_not_misrepresented(self):
        html = listing(("06 10 2026", "9455", "Recent"),
                       ("11 08 2025", "old-pdf", "Historical PDF"))
        page = self.adapter.parse_listing(html, (LISTING, None), 1)
        self.assertEqual(len(page.items), 1)
        self.assertEqual(self.adapter.listing_observation["publisher_index_rows_total"], 2)
        self.assertEqual(self.adapter.listing_observation["outside_declared_pilot_scope"], 1)
        self.assertEqual(self.adapter.listing_observation["pilot_source_begin"], "2026-09-01")

    def test_article_extracts_only_tightly_scoped_html_original(self):
        url = "https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html"
        parsed = self.adapter.parse_article(article("9455", "PCG Training"), url)
        self.assertEqual(parsed.title_original, "PCG Training")
        self.assertEqual(parsed.published_date, "2026-10-06")
        self.assertEqual(parsed.language_tag, "en")
        self.assertEqual(parsed.extra["source_identity"], "jcg-en:9455")
        self.assertEqual(parsed.extra["html_datetime_verdict"], "matches_visible")
        self.assertEqual(parsed.extra["body_scope"], "published_html_text_only")
        self.assertFalse(parsed.extra["attachments_collected"])
        self.assertEqual(parsed.extra["attachment_urls"],
                         ["https://www.kaiho.mlit.go.jp/e/topics_archive/upload/file.pdf"])
        self.assertIn("maritime law enforcement", parsed.text_original)
        self.assertNotIn("IGNORE", parsed.text_original)

    def test_observed_2021_stale_html_datetime_is_disclosed_not_hidden(self):
        url = "https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html"
        html = article("9455", "PCG Training", iso="2021-3-1")
        doc = self.adapter.parse_article(html, url)
        self.assertEqual(doc.published_date, "2026-10-06")
        self.assertEqual(doc.extra["html_datetime_original"], "2021-3-1")
        self.assertEqual(doc.extra["html_datetime_verdict"],
                         "observed_stale_template_2021-3-1")
        self.assertEqual(doc.extra["date_basis"],
                         "visible_publisher_time_and_archive_listing")

    def test_title_date_and_body_missing_rejected(self):
        url = "https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html"
        for broken in (
            article("9455", "PCG Training", iso="2026-10-07"),
            article("9455", "PCG Training", iso="2024-09-06"),
            article("9455", "PCG Training", body="read the linked PDF"),
            article("9455", "PCG Training").replace("topics-article__main", "WRONG"),
            article("9455", "PCG Training").replace("entry-title", "WRONG"),
            article("9455", "PCG Training").replace("<time", "<span"),
        ):
            with self.subTest(broken=broken[:80]), self.assertRaises(ValueError):
                self.adapter.parse_article(broken, url)

    def test_capture_hash_and_listing_article_consistency(self):
        url = "https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html"
        ref = CandidateReference(url, "jp_jcg_press_en", LISTING, "2026-10-06")
        self.adapter.references[url] = {"title": "PCG Training",
                                        "date": "2026-10-06", "url": url}
        text = article("9455", "PCG Training")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        capture = CaptureResult(ref, st.OK, url, body=text, payload_sha256=digest)
        response = self.adapter.extract(capture)
        self.assertEqual(response.status, st.OK)
        self.assertEqual(len(response.documents), 1)
        self.assertEqual(response.documents[0].extra["capture_sha256"], digest)
        self.assertEqual(response.documents[0].extra["content_sha256"],
                         hashlib.sha256(response.documents[0].text_original.encode()).hexdigest())
        capture.payload_sha256 = "bad"
        self.assertEqual(self.adapter.extract(capture).status, st.EXTRACTION_FAILURE)
        capture.payload_sha256 = digest
        capture.reference = CandidateReference(url, "jp_jcg_press_en", LISTING, "2026-10-07")
        self.assertEqual(self.adapter.extract(capture).status, st.EXTRACTION_FAILURE)


if __name__ == "__main__":
    unittest.main()
