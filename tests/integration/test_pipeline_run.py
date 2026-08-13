"""
Offline integration test for the REAL `pipeline.run()`.

Review found that the collection loop, the per-source attribution fold, the
all-duplicate/all-filtered refinements and the collection→degraded wiring were
verified only by a throwaway development probe. This is that probe, promoted to
the suite.

It calls the production `pipeline.run()` with a temporary database, a temporary
output directory and controlled adapters. No network, no model calls (the run is
`no_analysis=True`, which stops before the first LLM call), and the tracked
`pla_watch.db` and `output/` are asserted untouched.
"""

from __future__ import annotations

import hashlib
import importlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.legacy import LegacyScraperAdapter                 # noqa: E402
from core.collection import status as st                         # noqa: E402
from core.manifests import load_manifest                         # noqa: E402
from core.registry import SourceRegistry                         # noqa: E402
from migrations.runner import apply_all, connect                 # noqa: E402
from tests.test_migrations import build_legacy_db                # noqa: E402

CHINA = load_manifest(REPO_ROOT / "desks" / "china" / "manifest.json")
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "html" / "pla_daily_article.html"
TRACKED_DB = REPO_ROOT / "pla_watch.db"
TRACKED_OUTPUT = REPO_ROOT / "output"


class FakeScraper:
    """Offline stand-in exposing the BaseScraper surface the adapter uses."""

    IS_STUB = False

    def __init__(self, target_date=None, urls=(), pages=None, parsed=None,
                 listing_exc=None, failed_fetches=()):
        self.target_date = target_date
        self._urls = list(urls)
        self._pages = pages or {}
        self._parsed = parsed or {}
        self._listing_exc = listing_exc
        self.failed_fetches = list(failed_fetches)

    def get_article_urls(self):
        if self._listing_exc:
            raise self._listing_exc
        return list(self._urls)

    def fetch(self, url, force_refresh=False):
        return self._pages.get(url)

    def parse_article(self, url, html):
        return self._parsed.get(url)


def scraper_factory(**kwargs):
    stub = kwargs.pop("is_stub", False)

    class _Factory(FakeScraper):
        IS_STUB = stub

        def __init__(self, target_date=None):
            super().__init__(target_date=target_date, **kwargs)

    return _Factory


def article(url, title=None, body=None):
    """
    A relevant article. The title defaults to one derived from the URL because
    the pipeline collapses same-title PLA Daily reposts before URL/hash dedup —
    identical titles across two URLs are treated as one syndicated story, which
    is correct behaviour and would otherwise make count assertions misleading.
    """
    tag = url.rstrip("/").rsplit("/", 1)[-1]
    return {
        "url": url, "source_slug": "pla_daily",
        "title_original": title or ("解放军演习报道 %s" % tag),
        "text_original": body or (
            "正文内容，足够长以通过关键词过滤。解放军 演习 %s" % tag),
        "published_date": "2026-05-10",
    }


class PipelineRunCase(unittest.TestCase):
    """Runs the production pipeline against temporary storage."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db_path = self.tmp / "pipeline.db"
        self.out_dir = self.tmp / "output"
        self.cache_dir = self.tmp / "cache"
        self.out_dir.mkdir()
        self.cache_dir.mkdir()

        build_legacy_db(self.db_path, articles=0)
        conn = connect(self.db_path)
        apply_all(conn)
        conn.close()

        self.tracked_db_digest = (
            hashlib.sha256(TRACKED_DB.read_bytes()).hexdigest()
            if TRACKED_DB.exists() else None
        )
        self.tracked_output_listing = sorted(
            p.name for p in TRACKED_OUTPUT.iterdir()
        ) if TRACKED_OUTPUT.exists() else None

        import config
        import storage.db as dbmod
        self._config = config
        self._dbmod = dbmod
        self._saved = (config.DB_PATH, config.OUTPUT_DIR, config.CACHE_DIR,
                       dbmod.DB_PATH)
        config.DB_PATH = self.db_path
        config.OUTPUT_DIR = self.out_dir
        config.CACHE_DIR = self.cache_dir
        dbmod.DB_PATH = self.db_path

        self.pipeline = importlib.import_module("pipeline")
        self.pipeline.OUTPUT_DIR = self.out_dir
        self.pipeline.CACHE_DIR = self.cache_dir

    def tearDown(self):
        (self._config.DB_PATH, self._config.OUTPUT_DIR,
         self._config.CACHE_DIR, self._dbmod.DB_PATH) = self._saved
        import core.registry as reg
        reg._DEFAULT = None
        self._tmp.cleanup()

    # -- harness ----------------------------------------------------------

    def run_pipeline(self, adapters_by_slug, sources=None):
        """
        Drive the real pipeline.run() with controlled adapters.

        `no_analysis=True` keeps the run entirely offline: collection, dedup,
        the keyword filter and storage all execute; the LLM stage does not.
        """
        import core.registry as reg

        class ControlledRegistry(SourceRegistry):
            def get_adapter(self, slug):
                src = self.get_source(slug)
                factory = adapters_by_slug.get(slug)
                if factory is None:
                    return super().get_adapter(slug)
                return LegacyScraperAdapter(src, scraper_class=factory)

        registry = ControlledRegistry()
        reg._DEFAULT = registry
        self.pipeline.get_registry = lambda refresh=False: registry

        self.pipeline.run(
            sources=sources or sorted(adapters_by_slug),
            target_date=date(2026, 5, 10),
            dry_run=False,
            no_analysis=True,
        )
        return registry

    def results(self):
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT * FROM source_run_results ORDER BY source_slug"
            ).fetchall()
            return {r["source_slug"]: dict(r) for r in rows}
        finally:
            con.close()

    def run_status(self):
        con = sqlite3.connect(str(self.db_path))
        try:
            return con.execute(
                "SELECT status FROM scrape_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        finally:
            con.close()


class TestHealthyAndDegradedRun(PipelineRunCase):
    def test_mixed_run_records_every_source_and_degrades(self):
        url = "http://www.81.cn/x/a1.html"
        adapters = {
            "pla_daily": scraper_factory(
                urls=[url], pages={url: "<html/>"}, parsed={url: article(url)}),
            "mod_china": scraper_factory(
                urls=[], failed_fetches=["http://www.mod.gov.cn/listing"]),
            "china_mil_online": scraper_factory(urls=[]),
            "xinhua_mil": scraper_factory(urls=[], is_stub=True),
        }
        self.run_pipeline(adapters)
        res = self.results()

        # every configured source produced a row — none crowded out
        self.assertEqual(set(res), set(adapters))

        self.assertEqual(res["pla_daily"]["status"], st.OK)
        self.assertEqual(res["pla_daily"]["is_failure"], 0)
        self.assertEqual(res["pla_daily"]["new_documents"], 1)

        # listing failure, not silence
        self.assertEqual(res["mod_china"]["status"], st.LISTING_FAILURE)
        self.assertEqual(res["mod_china"]["is_failure"], 1)

        # healthy silence, not failure
        self.assertEqual(res["china_mil_online"]["status"], st.OK_NO_PUBLICATIONS)
        self.assertEqual(res["china_mil_online"]["is_failure"], 0)

        # acknowledged stub, not healthy silence and not a failure
        self.assertEqual(res["xinhua_mil"]["status"], st.NOT_IMPLEMENTED)
        self.assertEqual(res["xinhua_mil"]["is_failure"], 0)

        # one required source failing degrades the aggregate run
        self.assertEqual(self.run_status(), "degraded")

    def test_successful_source_survives_another_source_failure(self):
        url = "http://www.81.cn/x/a2.html"
        adapters = {
            "pla_daily": scraper_factory(
                urls=[url], pages={url: "<html/>"}, parsed={url: article(url)}),
            "mod_china": scraper_factory(
                listing_exc=RuntimeError("connection reset")),
        }
        self.run_pipeline(adapters)

        con = sqlite3.connect(str(self.db_path))
        stored = con.execute(
            "SELECT COUNT(*) FROM articles WHERE url=?", (url,)).fetchone()[0]
        con.close()
        self.assertEqual(stored, 1, "a failing source must not discard another's work")
        self.assertEqual(self.results()["pla_daily"]["status"], st.OK)
        self.assertEqual(self.run_status(), "degraded")

    def test_all_healthy_run_completes(self):
        url = "http://www.81.cn/x/a3.html"
        adapters = {
            "pla_daily": scraper_factory(
                urls=[url], pages={url: "<html/>"}, parsed={url: article(url)}),
            "china_mil_online": scraper_factory(urls=[]),
        }
        self.run_pipeline(adapters)
        self.assertEqual(self.run_status(), "completed")

    def test_stub_alone_does_not_degrade(self):
        url = "http://www.81.cn/x/a4.html"
        adapters = {
            "pla_daily": scraper_factory(
                urls=[url], pages={url: "<html/>"}, parsed={url: article(url)}),
            "xinhua_mil": scraper_factory(urls=[], is_stub=True),
        }
        self.run_pipeline(adapters)
        self.assertEqual(self.run_status(), "completed")


class TestCountAttribution(PipelineRunCase):
    def test_counts_attributed_to_the_right_source(self):
        u1, u2 = "http://www.81.cn/x/b1.html", "http://www.81.cn/x/b2.html"
        adapters = {
            "pla_daily": scraper_factory(
                urls=[u1, u2],
                pages={u1: "<html/>", u2: "<html/>"},
                parsed={u1: article(u1), u2: article(u2)}),
            "china_mil_online": scraper_factory(urls=[]),
        }
        self.run_pipeline(adapters)
        res = self.results()
        pd = res["pla_daily"]
        self.assertEqual(pd["references_discovered"], 2)
        self.assertEqual(pd["fetched"], 2)
        self.assertEqual(pd["extracted"], 2)
        self.assertEqual(pd["new_documents"], 2)
        self.assertEqual(pd["duplicates"], 0)
        self.assertEqual(res["china_mil_online"]["references_discovered"], 0)

    def test_all_duplicates_refinement(self):
        """Second run over the same article: healthy, but nothing new."""
        url = "http://www.81.cn/x/b3.html"
        factory = scraper_factory(
            urls=[url], pages={url: "<html/>"}, parsed={url: article(url)})
        self.run_pipeline({"pla_daily": factory})
        self.assertEqual(self.results()["pla_daily"]["status"], st.OK)

        self.run_pipeline({"pla_daily": factory})
        res = self.results()["pla_daily"]
        self.assertEqual(res["status"], st.OK_ALL_DUPLICATES)
        self.assertEqual(res["is_failure"], 0)
        self.assertEqual(res["new_documents"], 0)
        self.assertEqual(res["duplicates"], 1)
        self.assertEqual(self.run_status(), "completed")

    def test_all_filtered_refinement(self):
        """Collected fine; the keyword gate kept none of it."""
        url = "http://www.81.cn/x/b4.html"
        irrelevant = {
            "url": url, "source_slug": "pla_daily",
            "title_original": "花园里的花开了",
            "text_original": "今天天气很好，公园里有很多人在散步和拍照。",
            "published_date": "2026-05-10",
        }
        adapters = {"pla_daily": scraper_factory(
            urls=[url], pages={url: "<html/>"}, parsed={url: irrelevant})}
        self.run_pipeline(adapters)
        res = self.results()["pla_daily"]
        self.assertEqual(res["status"], st.OK_ALL_FILTERED)
        self.assertEqual(res["is_failure"], 0)
        self.assertEqual(res["new_documents"], 0)
        self.assertEqual(res["relevance_rejected"], 1)
        self.assertEqual(self.run_status(), "completed")


class TestRegistryDrivenSelection(PipelineRunCase):
    def test_unknown_slug_is_recorded_not_silently_skipped(self):
        url = "http://www.81.cn/x/c1.html"
        adapters = {"pla_daily": scraper_factory(
            urls=[url], pages={url: "<html/>"}, parsed={url: article(url)})}
        self.run_pipeline(adapters, sources=["pla_daily", "not_a_real_source"])
        res = self.results()
        self.assertIn("not_a_real_source", res)
        self.assertEqual(res["not_a_real_source"]["status"], st.UNKNOWN_SOURCE)
        self.assertEqual(res["not_a_real_source"]["is_failure"], 1)
        self.assertEqual(self.run_status(), "degraded")

    def test_sources_come_from_the_manifest(self):
        registry = SourceRegistry()
        self.assertEqual(sorted(registry.slugs), sorted(self.pipeline.SCRAPERS.keys()))


class TestProductionStateUntouched(PipelineRunCase):
    def test_tracked_db_and_output_untouched(self):
        url = "http://www.81.cn/x/d1.html"
        self.run_pipeline({"pla_daily": scraper_factory(
            urls=[url], pages={url: "<html/>"}, parsed={url: article(url)})})

        if self.tracked_db_digest is not None:
            self.assertEqual(
                hashlib.sha256(TRACKED_DB.read_bytes()).hexdigest(),
                self.tracked_db_digest,
                "the pipeline test mutated the tracked production database",
            )
        if self.tracked_output_listing is not None:
            self.assertEqual(
                sorted(p.name for p in TRACKED_OUTPUT.iterdir()),
                self.tracked_output_listing,
                "the pipeline test wrote into the tracked output tree",
            )

    def test_no_analysis_run_writes_no_site(self):
        """`--no-analysis` must not regenerate output (DECISION_LOG 2026-07-31)."""
        url = "http://www.81.cn/x/d2.html"
        self.run_pipeline({"pla_daily": scraper_factory(
            urls=[url], pages={url: "<html/>"}, parsed={url: article(url)})})
        self.assertEqual(list(self.out_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
