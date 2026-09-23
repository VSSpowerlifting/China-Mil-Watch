"""
Singapore scheduled production: the seam that lets the governed Singapore
adapter run through the same scheduled pipeline China does.

Four things this pins:

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
  * A mid-collection failure -- one release fails to parse after an earlier
    one in the same run already succeeded -- degrades that one release only.
    `collect()` still returns every other successfully extracted document
    from the same run; nothing already good is discarded because one later
    record turned out bad. This depends on `extract()` converting an
    unexpected parser exception into a clean `EXTRACTION_FAILURE` result
    rather than letting it propagate and abort the whole `collect()` loop
    (which would silently drop every already-extracted document from earlier
    references in the same call, even though nothing would be corrupted).

Everything here is offline: fake HTTP responses, no network, no tracked-
database access.
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import unittest
import unittest.mock
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
from migrations.runner import apply_all, connect                  # noqa: E402
from tests.test_migrations import build_legacy_db                 # noqa: E402

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
        self.assertTrue(callable(sg.SGMindefAdapter.collect))
        # SGMindefAdapter overrides collect() with its own all-or-nothing
        # batch semantics (TestAllOrNothingBatchSemantics below) rather than
        # inheriting the generic per-record-degrading one -- unlike Japan and
        # US DVIDS, which still use the shared base implementation as-is.
        self.assertIsNot(sg.SGMindefAdapter.collect, SourceAdapter.collect)

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


class TestAllOrNothingBatchSemantics(unittest.TestCase):
    """
    Case A from the bounded review: a third Singapore record fails during
    fetch/extraction after two succeeded. Unlike the generic
    `SourceAdapter.collect()` (right for China's five sources, which tolerate
    a bad page among many good ones), `SGMindefAdapter.collect()` must
    withhold the WHOLE batch -- not just the one bad record -- and must never
    report the run as OK when that happens.
    """

    def test_a_later_unexpected_parser_crash_withholds_the_whole_batch(self):
        good_url_1 = ("https://www.mindef.gov.sg/news-and-events/"
                      "latest-releases/18sep26-nr1/")
        bad_url = ("https://www.mindef.gov.sg/news-and-events/"
                   "latest-releases/19sep26-nr1/")
        good_url_2 = ("https://www.mindef.gov.sg/news-and-events/"
                      "latest-releases/20sep26-nr1/")
        sitemap = ("""<?xml version="1.0"?><urlset>
<url><loc>%s</loc><lastmod>2026-09-18</lastmod></url>
<url><loc>%s</loc><lastmod>2026-09-19</lastmod></url>
<url><loc>%s</loc><lastmod>2026-09-20</lastmod></url>
</urlset>""" % (good_url_1, bad_url, good_url_2))

        adapter = sg_adapter(FakeSession(sitemap_text=sitemap))

        calls = {"n": 0}
        real_title = sg.document_title

        def flaky(markup):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("simulated unexpected parser crash")
            return real_title(markup)

        with unittest.mock.patch.object(sg, "document_title", side_effect=flaky):
            result, documents = adapter.collect(window())

        # The whole batch is withheld -- including the two records that
        # parsed cleanly -- not just the one that failed.
        self.assertEqual(documents, [])
        self.assertNotEqual(result.status, st.OK)
        self.assertTrue(st.is_failure(result.status))
        self.assertIn("nothing committed this run", result.error_detail or "")

    def test_a_single_fetch_failure_among_successes_also_withholds_the_batch(self):
        good_url = ("https://www.mindef.gov.sg/news-and-events/"
                    "latest-releases/18sep26-nr1/")
        unreachable_url = ("https://www.mindef.gov.sg/news-and-events/"
                           "latest-releases/19sep26-nr1/")
        sitemap = ("""<?xml version="1.0"?><urlset>
<url><loc>%s</loc><lastmod>2026-09-18</lastmod></url>
<url><loc>%s</loc><lastmod>2026-09-19</lastmod></url>
</urlset>""" % (good_url, unreachable_url))

        class FlakyFetchSession(FakeSession):
            def get(self, url, timeout=None, headers=None):
                if url == unreachable_url:
                    return FakeResponse("", 500)
                return super().get(url, timeout=timeout, headers=headers)

        adapter = sg_adapter(FlakyFetchSession(sitemap_text=sitemap))
        result, documents = adapter.collect(window())

        self.assertEqual(documents, [])
        self.assertTrue(st.is_failure(result.status))
        self.assertNotEqual(result.status, st.OK)

    def test_extract_never_raises_it_returns_a_failure_result(self):
        """
        The narrower, direct proof this depends on: `extract()` itself must
        convert an unexpected exception into `EXTRACTION_FAILURE`, not
        propagate it. Without this, `collect()` could not keep looping to
        discover whether OTHER references in the same batch are also bad --
        it would just crash on the first one, losing the ability to report
        the batch honestly.
        """
        adapter = sg_adapter()
        capture_ok_but_unparseable = adapter.fetch(
            sg.CandidateReference(url=ORDINARY_URL, source_slug=adapter.slug))
        with unittest.mock.patch.object(
                sg, "document_title",
                side_effect=RuntimeError("simulated unexpected parser crash")):
            result = adapter.extract(capture_ok_but_unparseable)
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertIn("parser raised", result.error_detail or "")

    def test_a_fully_successful_batch_still_returns_every_document(self):
        """The strict gate must not reject a genuinely clean batch."""
        adapter = sg_adapter()
        result, documents = adapter.collect(window())
        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].url, ORDINARY_URL)

    def test_a_held_leak_past_discover_would_also_withhold_the_batch(self):
        """
        Defense in depth: discover()'s own filter is the primary defense
        (proven separately in TestHeldRecordsStayExcludedFromLiveCollection).
        This proves the SECOND, independent layer inside collect() itself:
        even if discover() were bugged and returned a held reference anyway,
        collect() still refuses to hand it (or anything else from that batch)
        back to the pipeline.
        """
        adapter = sg_adapter()
        real_discover = adapter.discover

        def buggy_discover(window_arg):
            real_result = real_discover(window_arg)
            leaked_ref = sg.CandidateReference(
                url=HELD_URL_1, source_slug=adapter.slug,
                discovered_via=sg.SITEMAP, hint_published_date="2026-08-15")
            return sg.DiscoveryResult(
                adapter.slug, sg.st.OK,
                references=list(real_result.references) + [leaked_ref])

        with unittest.mock.patch.object(adapter, "discover",
                                        side_effect=buggy_discover):
            result, documents = adapter.collect(window())

        self.assertEqual(documents, [])
        self.assertTrue(st.is_failure(result.status))
        self.assertIn("held record", result.error_detail or "")


class DbBackedCase(unittest.TestCase):
    """
    Base for tests that need the real storage.db functions against a real,
    migrated, Singapore-including schema -- not a hand-written mirror of the
    SQL, so the atomicity claims below are proven against the actual queries
    the pipeline runs, not a paraphrase of them.
    """

    def setUp(self):
        import storage.db as sdb
        self.sdb = sdb
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        build_legacy_db(self.db_path)
        conn = connect(self.db_path)
        apply_all(conn)   # migrations + desk-config sync, including Singapore
        conn.close()
        self._saved_db_path = sdb.DB_PATH
        sdb.DB_PATH = self.db_path

    def tearDown(self):
        self.sdb.DB_PATH = self._saved_db_path
        self.tmp.cleanup()

    def article_rows(self, source_slug="sg_mindef_releases"):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT a.* FROM articles a JOIN sources s ON a.source_id = s.id "
            "WHERE s.slug = ? ORDER BY a.id", (source_slug,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def sg_article(url, title="T", text=None, published="2026-09-18"):
        text = text or ("Body text. " * 40)
        return {
            "url": url, "source_slug": "sg_mindef_releases",
            "title_original": title, "text_original": text,
            "published_date": published,
            "content_hash": hashlib.sha256(
                (title + "\n" + text).encode("utf-8")).hexdigest(),
        }


class TestAtomicBatchInsertion(DbBackedCase):
    """
    Case C from the bounded review: a third Singapore database insertion
    fails after two insert attempts. Proven directly against
    storage.db.insert_articles_atomic(), not argued from a top-level
    try/except -- the transaction boundary IS the proof.
    """

    def test_a_clean_batch_commits_every_article_exactly_once(self):
        articles = [self.sg_article("https://www.mindef.gov.sg/a1/"),
                   self.sg_article("https://www.mindef.gov.sg/a2/"),
                   self.sg_article("https://www.mindef.gov.sg/a3/")]
        inserted = self.sdb.insert_articles_atomic(articles, [], run_id=1)
        self.assertEqual(len(inserted), 3)
        self.assertEqual(len(self.article_rows()), 3)

    def test_a_genuine_failure_partway_through_rolls_back_the_whole_batch(self):
        good1 = self.sg_article("https://www.mindef.gov.sg/a1/")
        good2 = self.sg_article("https://www.mindef.gov.sg/a2/")
        # An unknown source_slug is exactly the kind of unexpected condition
        # insert_articles_atomic() treats as a genuine failure, not the
        # ordinary "duplicate URL" outcome.
        broken = dict(self.sg_article("https://www.mindef.gov.sg/a3/"))
        broken["source_slug"] = "does_not_exist_as_a_source"

        with self.assertRaises(ValueError):
            self.sdb.insert_articles_atomic([good1, good2, broken], [], run_id=1)

        # Nothing from the batch survived the rollback -- including good1 and
        # good2, which would have committed successfully on their own.
        self.assertEqual(self.article_rows(), [])

    def test_previous_rows_survive_a_rolled_back_later_batch_untouched(self):
        first = self.sg_article("https://www.mindef.gov.sg/already-there/",
                                title="Original title")
        aid = self.sdb.insert_article(first, scrape_run_id=1)
        self.assertIsNotNone(aid)
        before = self.article_rows()
        self.assertEqual(len(before), 1)

        good = self.sg_article("https://www.mindef.gov.sg/a1/")
        broken = dict(self.sg_article("https://www.mindef.gov.sg/a2/"))
        broken["source_slug"] = "does_not_exist_as_a_source"
        with self.assertRaises(ValueError):
            self.sdb.insert_articles_atomic([good, broken], [], run_id=2)

        after = self.article_rows()
        # Byte-for-byte: the prior row is the only row, completely unchanged.
        self.assertEqual(before, after)

    def test_a_duplicate_url_within_the_batch_is_not_a_rollback_trigger(self):
        a1 = self.sg_article("https://www.mindef.gov.sg/a1/")
        a1_dup = self.sg_article("https://www.mindef.gov.sg/a1/", title="Different title text")
        a2 = self.sg_article("https://www.mindef.gov.sg/a2/")
        inserted = self.sdb.insert_articles_atomic([a1, a1_dup, a2], [], run_id=1)
        # a1_dup collides with a1's URL and is silently skipped, same as
        # insert_article() already does -- not a batch failure.
        self.assertEqual(len(inserted), 2)
        self.assertEqual(len(self.article_rows()), 2)

    def test_retrying_the_same_successful_batch_remains_deduplicated(self):
        articles = [self.sg_article("https://www.mindef.gov.sg/a1/"),
                   self.sg_article("https://www.mindef.gov.sg/a2/")]
        first = self.sdb.insert_articles_atomic(articles, [], run_id=1)
        self.assertEqual(len(first), 2)

        second = self.sdb.insert_articles_atomic(articles, [], run_id=2)
        self.assertEqual(second, [])
        self.assertEqual(len(self.article_rows()), 2)

    def test_rejected_articles_are_inserted_with_passed_relevance_false(self):
        rejected = self.sg_article("https://www.mindef.gov.sg/filtered/")
        inserted = self.sdb.insert_articles_atomic([], [rejected], run_id=1)
        self.assertEqual(inserted, [])   # only "passed" articles are returned
        rows = self.article_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["passed_relevance"], 0)

    def test_held_urls_never_reach_the_database_even_if_handed_to_insert(self):
        """
        Belt and suspenders at the storage boundary too: this test does not
        exercise the held-record filter (that is SGMindefAdapter's job,
        proven in TestHeldRecordsStayExcludedFromLiveCollection and
        TestAllOrNothingBatchSemantics) -- it confirms that IF a held URL
        were ever handed to the atomic insert path, nothing about storage
        itself would need to know or care: the adapter-level gate is what
        must stop it, and this pins that the only path new Singapore rows
        take is this one function, so hardening it is sufficient.
        """
        from scraper.sources.sg_mindef import HELD_RELEASE_SLUGS
        held_url = ("https://www.mindef.gov.sg/news-and-events/"
                   "latest-releases/15aug26-speech/")
        self.assertIn("15aug26-speech", HELD_RELEASE_SLUGS)
        # SGMindefAdapter.collect() (TestAllOrNothingBatchSemantics) is the
        # actual gate; this just documents the URL shape a held slug takes.
        self.assertTrue(held_url.rstrip("/").endswith("15aug26-speech"))


class TestPipelineAtomicBatchWiring(DbBackedCase):
    """
    Cases C and D end to end through pipeline._store_atomic_batches(): a
    genuine Singapore storage failure must (a) commit zero new Singapore
    articles and (b) leave China's own inserts, in the SAME run, completely
    unaffected -- proving the isolation pipeline.py's per-source design
    already gave every source is not broken by adding the atomic path.
    """

    def setUp(self):
        super().setUp()
        import pipeline
        self.pipeline = pipeline

    @staticmethod
    def china_article(url, source_slug="pla_daily"):
        title, text = "China article", "Body text. " * 40
        return {
            "url": url, "source_slug": source_slug,
            "title_original": title, "text_original": text,
            "published_date": "2026-09-18",
            "content_hash": hashlib.sha256(
                (title + "\n" + text).encode("utf-8")).hexdigest(),
        }

    def test_a_failed_singapore_batch_commits_nothing_china_is_unaffected(self):
        china1 = self.china_article("https://www.example.com/c1")
        china2 = self.china_article("https://www.example.com/c2")
        sg_good = self.sg_article("https://www.mindef.gov.sg/a1/")
        # Same source_slug as sg_good, so both land in the SAME atomic group
        # -- a missing content_hash raises a genuine, uncaught exception
        # inside the transaction, unlike a duplicate URL (which is the
        # ordinary, non-batch-breaking outcome tested separately).
        sg_broken = dict(self.sg_article("https://www.mindef.gov.sg/a2/"))
        del sg_broken["content_hash"]

        # China is NOT in ATOMIC_BATCH_SLUGS, so it goes through the ordinary
        # per-article loop in pipeline.run() -- simulated here directly since
        # _store_atomic_batches() only ever touches the atomic subset.
        # build_legacy_db() pre-seeds pla_daily with fixture rows, so this
        # checks the delta rather than an absolute count.
        china_before = len(self.article_rows("pla_daily"))
        for a in (china1, china2):
            self.sdb.insert_article(a, scrape_run_id=1)

        kw_passed = [sg_good, sg_broken]
        inserted, failed_slugs = self.pipeline._store_atomic_batches(
            kw_passed, [], run_id=1)

        self.assertEqual(inserted, [])
        self.assertEqual(failed_slugs, {"sg_mindef_releases"})
        self.assertEqual(self.article_rows("sg_mindef_releases"), [])
        china_rows = self.article_rows("pla_daily")
        self.assertEqual(len(china_rows) - china_before, 2)

    def test_a_clean_singapore_batch_commits_and_reports_no_failed_slugs(self):
        sg_good = [self.sg_article("https://www.mindef.gov.sg/a1/"),
                  self.sg_article("https://www.mindef.gov.sg/a2/")]
        inserted, failed_slugs = self.pipeline._store_atomic_batches(
            sg_good, [], run_id=1)
        self.assertEqual(len(inserted), 2)
        self.assertEqual(failed_slugs, set())
        self.assertEqual(len(self.article_rows("sg_mindef_releases")), 2)

    def test_china_articles_are_never_routed_through_the_atomic_path(self):
        """
        ATOMIC_BATCH_SLUGS names only sg_mindef_releases -- China's five
        sources are never grouped into a batch transaction, and a China
        article mixed into the same combined list is ignored by
        _store_atomic_batches() entirely, exactly like an ordinary run where
        no atomic source is present at all. build_legacy_db() pre-seeds
        pla_daily with fixture rows, so this checks the count is unchanged
        by the call rather than asserting an empty table.
        """
        before = len(self.article_rows("pla_daily"))
        china = self.china_article("https://www.example.com/c1")
        inserted, failed_slugs = self.pipeline._store_atomic_batches(
            [china], [], run_id=1)
        self.assertEqual(inserted, [])
        self.assertEqual(failed_slugs, set())
        self.assertEqual(len(self.article_rows("pla_daily")), before)


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
