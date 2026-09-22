"""
Singapore scheduled production: the seam that lets the governed Singapore
adapter run through the same scheduled pipeline China does.

Three things this pins:

  * `SourceAdapter.collect()` exists generically, so a scheduled `pipeline.py`
    run can call it for `sg_mindef_releases` without raising `AttributeError`
    -- the gap `desks/singapore/manifest.json` opened by registering a source
    whose adapter had discover/fetch/extract but no `collect()`.
  * `LegacyScraperAdapter`, and therefore every China source, resolves to its
    own `collect()` unchanged -- this file's addition is provably invisible
    to China's collection path, not merely assumed to be.
  * The governed holds (`15aug26-speech`, `16sep26-speech`; DECISION_LOG.md,
    2026-09-21) are excluded by a live `discover()`/`collect()` call, not
    only by the one-time historical promotion that already ran. MINDEF's own
    sitemap still lists both, so nothing but this filter stops a scheduled
    run from reintroducing them.

Everything here is offline: fake HTTP responses, no network, no tracked-
database access.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                          # noqa: E402
from core.collection.contract import (                            # noqa: E402
    CollectionWindow, SourceAdapter, SourceRunResult)
from core.collection.health import aggregate_status                # noqa: E402
from core.registry import SourceRegistry                           # noqa: E402
from adapters.legacy import LegacyScraperAdapter                   # noqa: E402
from scraper.sources import sg_mindef as sg                        # noqa: E402

HELD_URL_1 = ("https://www.mindef.gov.sg/news-and-events/"
              "latest-releases/15aug26-speech/")
HELD_URL_2 = ("https://www.mindef.gov.sg/news-and-events/"
              "latest-releases/16sep26-speech/")
ORDINARY_URL = ("https://www.mindef.gov.sg/news-and-events/"
                 "latest-releases/20sep26-nr1/")

SITEMAP_WITH_HOLDS = """<?xml version="1.0" encoding="UTF-8"?>
<urlset>
<url><loc>%s</loc><lastmod>2026-08-15</lastmod></url>
<url><loc>%s</loc><lastmod>2026-09-16</lastmod></url>
<url><loc>%s</loc><lastmod>2026-09-20</lastmod></url>
</urlset>
""" % (HELD_URL_1, HELD_URL_2, ORDINARY_URL)

SITEMAP_ONLY_HOLDS = """<?xml version="1.0" encoding="UTF-8"?>
<urlset>
<url><loc>%s</loc><lastmod>2026-08-15</lastmod></url>
<url><loc>%s</loc><lastmod>2026-09-16</lastmod></url>
</urlset>
""" % (HELD_URL_1, HELD_URL_2)

ROBOTS_ALLOW = "User-Agent: *\nAllow: /\n"

ITEM_HTML = (
    '<html><head><meta property="og:title" content="A safe release">'
    "</head><body><h1>A safe release</h1><p>" + ("Body text. " * 40) +
    "</p></body></html>"
)


def window() -> CollectionWindow:
    return CollectionWindow(target_date=date(2026, 9, 22), lookback_days=365)


class FakeResponse:
    def __init__(self, text="", status_code=200, headers=None, url=""):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html"}
        self.url = url


class FakeSession:
    """Serves a sitemap carrying both governed holds plus one ordinary release."""

    def __init__(self, sitemap_text=SITEMAP_WITH_HOLDS, item_html=ITEM_HTML):
        self.sitemap_text = sitemap_text
        self.item_html = item_html
        self.calls = []

    def get(self, url, timeout=None, headers=None):
        self.calls.append(url)
        if url == sg.ROBOTS:
            return FakeResponse(ROBOTS_ALLOW, 200)
        if url == sg.SITEMAP:
            return FakeResponse(self.sitemap_text, 200)
        return FakeResponse(self.item_html, 200, url=url)


def sg_source():
    return SourceRegistry().get_source("sg_mindef_releases")


def sg_adapter(session=None):
    return sg.SGMindefAdapter(sg_source(), session=session or FakeSession(),
                               sleeper=lambda _s: None)


class TestGenericCollectClosesTheGap(unittest.TestCase):
    """The AttributeError this task exists to fix."""

    def test_sg_mindef_adapter_has_a_working_collect(self):
        self.assertTrue(hasattr(sg.SGMindefAdapter, "collect"))
        self.assertIs(sg.SGMindefAdapter.collect, SourceAdapter.collect)

    def test_registry_get_adapter_returns_something_collectible(self):
        """
        The exact call `pipeline.py` makes for every source in
        `available_slugs()`. No network: proving the attribute exists is
        enough to show the AttributeError this task fixes cannot recur.
        """
        adapter = SourceRegistry().get_adapter("sg_mindef_releases")
        self.assertTrue(callable(adapter.collect))

    def test_china_adapters_are_unaffected_by_the_new_base_method(self):
        """
        `LegacyScraperAdapter` -- what every China source resolves to --
        already defines its own `collect()`. Method resolution order means
        adding `collect()` to the shared `SourceAdapter` base class is
        invisible to it. This is the guarantee, checked directly, not an
        argument about it.
        """
        self.assertIsNot(LegacyScraperAdapter.collect, SourceAdapter.collect)
        registry = SourceRegistry()
        china_slugs = registry.slugs_for_desk("china")
        self.assertTrue(china_slugs, "expected at least one china source")
        for slug in china_slugs:
            adapter = registry.get_adapter(slug)
            with self.subTest(slug=slug):
                self.assertIsInstance(adapter, LegacyScraperAdapter)
                self.assertIs(type(adapter).collect,
                              LegacyScraperAdapter.collect)


class TestHeldRecordsStayExcludedFromLiveCollection(unittest.TestCase):
    """
    DECISION_LOG.md (2026-09-21) held `15aug26-speech` and `16sep26-speech`
    out of the promoted corpus. That promotion was a one-time batch write; it
    never taught a live collector to refuse these URLs. This is the
    enforcement that does.
    """

    def test_discover_never_returns_a_held_reference(self):
        result = sg_adapter().discover(window())
        urls = [r.url for r in result.references]
        self.assertNotIn(HELD_URL_1, urls)
        self.assertNotIn(HELD_URL_2, urls)
        # The filter excludes named holds, not everything: the one ordinary
        # release in the fixture still comes through.
        self.assertIn(ORDINARY_URL, urls)

    def test_collect_never_produces_a_held_document(self):
        result, documents = sg_adapter().collect(window())
        urls = [d.url for d in documents]
        self.assertNotIn(HELD_URL_1, urls)
        self.assertNotIn(HELD_URL_2, urls)
        self.assertEqual(result.references_discovered, 1)
        self.assertEqual(result.status, st.OK)

    def test_a_sitemap_of_only_held_records_is_silence_not_a_crash(self):
        """
        Filtering holds out entirely must land on the same 'nothing to
        report' status an empty-but-healthy day uses -- not a failure status,
        which would misreport a governance exclusion as an outage.
        """
        result = sg_adapter(FakeSession(sitemap_text=SITEMAP_ONLY_HOLDS)) \
            .discover(window())
        self.assertEqual(result.status, st.OK_NO_PUBLICATIONS)
        self.assertEqual(result.references, [])

    def test_held_slugs_match_the_governed_decision(self):
        self.assertEqual(sg.HELD_RELEASE_SLUGS,
                          frozenset({"15aug26-speech", "16sep26-speech"}))


class TestSingaporeFailureDegradesRunButNeverFailsIt(unittest.TestCase):
    """
    `aggregate_status()` is the desk-agnostic rule that already protects
    every source, including China's five: one failing source degrades a run,
    it does not fail one that collected real work elsewhere. A Singapore
    failure exercises that same existing rule -- it gets no special case and
    needs none.
    """

    @staticmethod
    def _ok(slug, new_documents=3):
        return SourceRunResult(source_slug=slug, status=st.OK,
                                new_documents=new_documents)

    def test_singapore_adapter_error_alongside_healthy_china_is_degraded(self):
        results = [
            self._ok("pla_daily"),
            self._ok("xinhua_mil"),
            SourceRunResult(source_slug="sg_mindef_releases",
                             status=st.ADAPTER_ERROR,
                             error_detail="adapter raised"),
        ]
        self.assertEqual(aggregate_status(results), "degraded")

    def test_singapore_failing_alone_among_all_sources_is_failed(self):
        """
        The one case where a Singapore outage alone should read as a hard
        failure: nothing at all was collected that run. `aggregate_status`
        already draws this line for any single-source run; confirmed here so
        a future change to Singapore's wiring can't silently mark a
        whole-run outage 'degraded'.
        """
        results = [SourceRunResult(source_slug="sg_mindef_releases",
                                    status=st.ADAPTER_ERROR)]
        self.assertEqual(aggregate_status(results), "failed")

    def test_china_results_are_not_mutated_by_singapores_failure(self):
        """
        A `SourceRunResult` carries only its own source's counts. There is no
        shared mutable object a Singapore failure could reach into.
        """
        china = self._ok("pla_daily")
        singapore = SourceRunResult(source_slug="sg_mindef_releases",
                                     status=st.ADAPTER_ERROR)
        aggregate_status([china, singapore])
        self.assertEqual(china.status, st.OK)
        self.assertEqual(china.new_documents, 3)


class TestSingaporeFreshnessLanguageIsUntouchedByThisChange(unittest.TestCase):
    """
    The public "Last successful collection: None" copy is computed in
    `core/viewmodel.py` from `source_run_results`, gated on an actual
    non-failing row existing for the desk. This patch does not modify that
    file, its query, or any template -- so the copy can only change once a
    real scheduled run writes a real row, never from this PR by itself.
    """

    def test_viewmodel_freshness_query_symbol_is_present_and_unrenamed(self):
        import core.viewmodel as vm
        source = Path(vm.__file__).read_text(encoding="utf-8")
        self.assertIn("_last_successful_run_by_desk", source)


if __name__ == "__main__":
    unittest.main()
