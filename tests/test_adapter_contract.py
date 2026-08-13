"""
Adapter contract tests.

Entirely offline. Nothing here opens a socket: the fake scrapers below return
canned values, and the one real-parser test reads a saved page from
`tests/fixtures/html/`. No model calls, paid or otherwise.

The central assertion is the one the project has been bitten by repeatedly:
**a source that published nothing and a source that could not be reached must
not produce the same result.** Both return zero documents; only one is a
failure, and the difference has to be visible in the run record.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.legacy import LegacyScraperAdapter                  # noqa: E402
from core.collection import status as st                          # noqa: E402
from core.collection.contract import (                            # noqa: E402
    CandidateReference, CollectionWindow, SourceRunResult,
)
from core.manifests import load_manifest                          # noqa: E402
from core.registry import SourceRegistry                          # noqa: E402

CHINA = load_manifest(REPO_ROOT / "desks" / "china" / "manifest.json")
FIXTURE_HTML = REPO_ROOT / "tests" / "fixtures" / "html"
WINDOW = CollectionWindow(target_date=date(2026, 5, 10))


def source(slug: str):
    return CHINA.source_by_slug(slug)


class FakeScraper:
    """
    Stand-in for a BaseScraper subclass.

    Presents exactly the surface the adapter uses — `get_article_urls`,
    `fetch`, `parse_article`, `failed_fetches` — so the adapter is exercised
    without a network stack, and each failure mode can be produced on demand.
    """

    IS_STUB = False

    def __init__(self, target_date=None, urls=None, pages=None,
                 parsed=None, listing_exc=None, fetch_exc=None,
                 parse_exc=None, failed_fetches=None):
        self.target_date = target_date
        self._urls = urls if urls is not None else []
        self._pages = pages or {}
        self._parsed = parsed or {}
        self._listing_exc = listing_exc
        self._fetch_exc = fetch_exc
        self._parse_exc = parse_exc
        self.failed_fetches = list(failed_fetches or [])

    def get_article_urls(self):
        if self._listing_exc:
            raise self._listing_exc
        return list(self._urls)

    def fetch(self, url, force_refresh=False):
        if self._fetch_exc:
            raise self._fetch_exc
        return self._pages.get(url)

    def parse_article(self, url, html):
        if self._parse_exc:
            raise self._parse_exc
        return self._parsed.get(url)


def adapter_for(slug="pla_daily", **kwargs):
    """Build an adapter over a FakeScraper configured by kwargs."""
    def factory(target_date=None):
        return FakeScraper(target_date=target_date, **kwargs)
    factory.IS_STUB = kwargs.pop("is_stub", False)
    return LegacyScraperAdapter(source(slug), scraper_class=factory)


ARTICLE = {
    "url": "http://www.81.cn/a/1.html",
    "source_slug": "pla_daily",
    "title_original": "标题",
    "text_original": "正文",
    "published_date": "2026-05-10",
}


class TestSuccessPaths(unittest.TestCase):
    def test_successful_collection(self):
        a = adapter_for(
            urls=[ARTICLE["url"]],
            pages={ARTICLE["url"]: "<html>ok</html>"},
            parsed={ARTICLE["url"]: ARTICLE},
        )
        result, docs = a.collect(WINDOW)
        self.assertEqual(result.status, st.OK)
        self.assertFalse(result.is_failure)
        self.assertEqual(len(docs), 1)
        self.assertEqual(result.references_discovered, 1)
        self.assertEqual(result.fetched, 1)
        self.assertEqual(result.extracted, 1)

    def test_zero_publications_is_success_not_failure(self):
        """The distinction this whole phase exists for."""
        a = adapter_for(urls=[])
        result, docs = a.collect(WINDOW)
        self.assertEqual(result.status, st.OK_NO_PUBLICATIONS)
        self.assertFalse(result.is_failure)
        self.assertTrue(result.is_success)
        self.assertEqual(docs, [])

    def test_zero_publications_differs_from_listing_failure(self):
        quiet, _ = adapter_for(urls=[]).collect(WINDOW)
        broken, _ = adapter_for(
            urls=[], failed_fetches=["http://www.81.cn/listing"]
        ).collect(WINDOW)

        self.assertNotEqual(quiet.status, broken.status)
        self.assertFalse(quiet.is_failure)
        self.assertTrue(broken.is_failure)
        self.assertEqual(len(quiet.__class__.__mro__), len(broken.__class__.__mro__))

    def test_document_dict_is_verbatim_parser_output(self):
        """
        Downstream normalization, dedup and the keyword filter must receive
        exactly what they receive today — including absent keys, which are not
        the same as present-and-None.
        """
        sparse = {"url": "http://www.81.cn/a/2.html", "source_slug": "pla_daily",
                  "title_original": "t", "text_original": "x"}
        a = adapter_for(
            urls=[sparse["url"]],
            pages={sparse["url"]: "<html/>"},
            parsed={sparse["url"]: sparse},
        )
        _, docs = a.collect(WINDOW)
        self.assertEqual(docs[0].as_article_dict(), sparse)
        self.assertNotIn("published_date", docs[0].as_article_dict())


class TestFailurePaths(unittest.TestCase):
    def test_listing_exception_is_listing_failure(self):
        a = adapter_for(listing_exc=RuntimeError("connection reset"))
        result, docs = a.collect(WINDOW)
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertTrue(result.is_failure)
        self.assertIn("connection reset", result.error_detail)
        self.assertEqual(docs, [])

    def test_timeout_during_listing_is_a_failure(self):
        a = adapter_for(listing_exc=TimeoutError("read timed out"))
        result, _ = a.collect(WINDOW)
        self.assertTrue(result.is_failure)
        self.assertIn("timed out", result.error_detail)

    def test_all_fetches_failing_is_fetch_failure(self):
        a = adapter_for(urls=["http://www.81.cn/a/1.html"], pages={})
        result, docs = a.collect(WINDOW)
        self.assertEqual(result.status, st.FETCH_FAILURE)
        self.assertTrue(result.is_failure)
        self.assertEqual(result.references_discovered, 1)
        self.assertEqual(result.fetched, 0)
        self.assertEqual(docs, [])

    def test_parser_returning_nothing_is_extraction_failure(self):
        """The signature of source-side markup drift."""
        url = "http://www.81.cn/a/1.html"
        a = adapter_for(urls=[url], pages={url: "<html>changed</html>"}, parsed={})
        result, docs = a.collect(WINDOW)
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertTrue(result.is_failure)
        self.assertEqual(result.fetched, 1)
        self.assertEqual(docs, [])
        self.assertIn("markup drift", result.error_detail)

    def test_parser_raising_is_extraction_failure(self):
        url = "http://www.81.cn/a/1.html"
        a = adapter_for(urls=[url], pages={url: "<html/>"},
                        parse_exc=ValueError("bad selector"))
        result, _ = a.collect(WINDOW)
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)

    def test_partial_extraction_still_succeeds_but_records_detail(self):
        good, bad = "http://www.81.cn/a/1.html", "http://www.81.cn/a/2.html"
        a = adapter_for(
            urls=[good, bad],
            pages={good: "<html/>", bad: "<html/>"},
            parsed={good: dict(ARTICLE, url=good)},
        )
        result, docs = a.collect(WINDOW)
        self.assertEqual(result.status, st.OK)
        self.assertFalse(result.is_failure)
        self.assertEqual(len(docs), 1)
        self.assertIn("failed extraction", result.error_detail)

    def test_error_detail_is_bounded_and_single_line(self):
        """Scraped pages are untrusted; their text must not flood the log."""
        hostile = "x" * 5000 + "\n" * 50 + "IGNORE PREVIOUS INSTRUCTIONS"
        a = adapter_for(listing_exc=RuntimeError(hostile))
        result, _ = a.collect(WINDOW)
        self.assertLessEqual(len(result.error_detail), 260)
        self.assertNotIn("\n", result.error_detail)


class TestDisabledAndStub(unittest.TestCase):
    def test_disabled_source_is_skipped_not_failed(self):
        import dataclasses
        disabled = dataclasses.replace(source("pla_daily"), enabled=False)
        a = LegacyScraperAdapter(disabled, scraper_class=FakeScraper)
        result, docs = a.collect(WINDOW)
        self.assertEqual(result.status, st.SKIPPED_DISABLED)
        self.assertFalse(result.is_failure)
        self.assertEqual(docs, [])

    def test_stub_adapter_reports_not_implemented(self):
        class StubScraper(FakeScraper):
            IS_STUB = True

        a = LegacyScraperAdapter(source("xinhua_mil"), scraper_class=StubScraper)
        result, docs = a.collect(WINDOW)
        self.assertEqual(result.status, st.NOT_IMPLEMENTED)
        self.assertFalse(result.is_failure,
                         "an acknowledged stub must not degrade every run")
        self.assertEqual(docs, [])

    def test_real_xinhua_adapter_is_detected_as_stub(self):
        a = SourceRegistry().get_adapter("xinhua_mil")
        self.assertFalse(a.implemented)
        self.assertEqual(a.healthcheck().status, st.NOT_IMPLEMENTED)


class TestHealthchecksAreOffline(unittest.TestCase):
    def test_every_configured_adapter_healthchecks_without_network(self):
        registry = SourceRegistry()
        results = registry.healthcheck_all()
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertIn(r.status, (st.OK, st.NOT_IMPLEMENTED, st.SKIPPED_DISABLED))

    def test_working_adapters_report_ok(self):
        registry = SourceRegistry()
        by_slug = {r.source_slug: r.status for r in registry.healthcheck_all()}
        for slug in ("pla_daily", "mod_china", "china_mil_online",
                     "global_times_mil"):
            self.assertEqual(by_slug[slug], st.OK)


class TestRealParserOffline(unittest.TestCase):
    """
    Drives the genuine PLA Daily parser over a saved page.

    This is the check that the compatibility wrapper actually operates a real
    scraper — the fakes above validate the contract's shape, not that the
    wrapper drives production code correctly.
    """

    def test_real_pla_daily_parser_through_the_adapter(self):
        from scraper.sources.pla_daily import PLADailyScraper

        html = (FIXTURE_HTML / "pla_daily_article.html").read_text(
            encoding="utf-8", errors="replace"
        )
        url = "http://www.81.cn/yw_208727/16473227.html"

        class OfflinePLADaily(PLADailyScraper):
            """Real parser, no network: listing and fetch are served locally."""

            def get_article_urls(self):
                return [url]

            def fetch(self, u, force_refresh=False):
                return html if u == url else None

        a = LegacyScraperAdapter(source("pla_daily"),
                                 scraper_class=OfflinePLADaily)
        result, docs = a.collect(WINDOW)

        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertTrue(doc.title_original.strip())
        self.assertGreater(len(doc.text_original), 200)
        self.assertEqual(doc.source_slug, "pla_daily")
        self.assertEqual(doc.language_tag, "zh-Hans")
        # The raw dict is what the pipeline stores.
        self.assertIn("title_original", doc.as_article_dict())


class TestStatusVocabulary(unittest.TestCase):
    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError):
            SourceRunResult(source_slug="x", status="probably_fine")

    def test_failure_and_success_sets_are_disjoint(self):
        self.assertEqual(st.SUCCESS_STATUSES & st.FAILURE_STATUSES, frozenset())

    def test_stub_and_disabled_are_not_failures(self):
        self.assertFalse(st.is_failure(st.NOT_IMPLEMENTED))
        self.assertFalse(st.is_failure(st.SKIPPED_DISABLED))

    def test_every_declared_status_constant_is_registered(self):
        """
        A status constant that is not in ALL_STATUSES would be rejected by
        SourceRunResult at write time — a defect that only shows up in
        production, on the failure path, which is the worst place to find it.
        """
        declared = {
            getattr(st, name) for name in dir(st)
            if name.isupper() and isinstance(getattr(st, name), str)
            and not name.endswith("STATUSES")
        }
        self.assertTrue(declared)
        self.assertEqual(declared - st.ALL_STATUSES, set())

    def test_every_status_is_classified_as_success_or_failure_or_neither(self):
        neutral = st.ALL_STATUSES - st.SUCCESS_STATUSES - st.FAILURE_STATUSES
        self.assertEqual(neutral, {st.SKIPPED_DISABLED, st.NOT_IMPLEMENTED})


if __name__ == "__main__":
    unittest.main(verbosity=2)
