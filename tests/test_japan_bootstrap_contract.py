"""
What the first Japan run is allowed to do, and what it must never do.

The rule this suite replaced was a rolling `today - 14 days` window followed by
`kept[:cap]`. Measured against the real news feed on 2026-08-26, that meant: of
142 items, 21 were processed and **121 were dropped for being older**. The run
reported "21 discovered". Eighty-five percent of the feed left no trace — not a
count, not a URL, nothing a reader could use to tell the difference between "the
ministry published nothing else" and "this collector chose not to look".

Two failures are possible here and both are silent, so both are tested against
directly:

  * **backfill** — a first run that marches through the entire feed history,
    hammering a ministry for documents it was never asked to hold;
  * **sampling** — a first run that takes a fixed number of items and reports
    the result as though it were the feed.

The contract that replaces it: an explicit cutoff, persisted on the first run
and never rewritten; everything after it handled; everything before it recorded
as history and never fetched; and a cap that defers rather than discards.
"""
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection import status as st                          # noqa: E402
from core.collection.contract import CandidateReference           # noqa: E402
from scraper.sources import jp_mod                                # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "shadow_collect_japan", ROOT / "scripts" / "shadow_collect_japan.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

CUTOFF = "2026-08-20"


def ref(day, slug="jp_mod_news_ja", suffix=".pdf"):
    return CandidateReference(url="https://www.mod.go.jp/j/press/news/%s%s"
                                  % (day.replace("-", ""), suffix),
                              source_slug=slug, hint_published_date=day)


def spread(first, last):
    """One reference per day across an inclusive range."""
    a = date.fromisoformat(first); b = date.fromisoformat(last)
    return [ref((a + timedelta(days=i)).isoformat())
            for i in range((b - a).days + 1)]


class TestTheCutoffIsExplicitAndPersisted(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_first_run_writes_a_cutoff_file(self):
        now = datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc)
        rec = runner.establish_cutoff(self.state, now, "run-1")
        self.assertTrue((self.state / "bootstrap.json").is_file())
        self.assertEqual(rec["cutoff_date"], "2026-08-27")
        self.assertEqual(rec["established_run"], "run-1")

    def test_a_later_run_never_rewrites_it(self):
        first = runner.establish_cutoff(
            self.state, datetime(2026, 8, 27, tzinfo=timezone.utc), "run-1")
        later = runner.establish_cutoff(
            self.state, datetime(2026, 12, 1, tzinfo=timezone.utc), "run-99")
        self.assertEqual(first, later)
        self.assertEqual(later["established_run"], "run-1")

    def test_the_cutoff_is_a_date_not_a_rolling_window(self):
        """
        A rolling window cannot be audited: the set it admits changes daily, so
        no reader can say which items were ever eligible.
        """
        source = (ROOT / "scripts" / "shadow_collect_japan.py").read_text("utf-8")
        self.assertIn("cutoff_date", source)
        adapter = (ROOT / "scraper" / "sources" / "jp_mod.py").read_text("utf-8")
        self.assertNotIn("def select_window", adapter)


class TestTheFirstRunDoesNotBackfill(unittest.TestCase):
    """A first run must not march through the ministry's whole back catalogue."""

    def test_history_is_recorded_but_never_placed_in_scope(self):
        refs = spread("2026-06-01", "2026-08-27")
        in_scope, pre, deferred, undated = jp_mod.partition_refs(refs, CUTOFF, 100)
        self.assertTrue(pre, "expected history before the cutoff")
        for r in in_scope:
            with self.subTest(url=r.url):
                self.assertGreaterEqual(r.hint_published_date, CUTOFF)

    def test_every_pre_cutoff_item_is_accounted_for(self):
        refs = spread("2026-06-01", "2026-08-27")
        in_scope, pre, deferred, undated = jp_mod.partition_refs(refs, CUTOFF, 100)
        self.assertEqual(len(in_scope) + len(pre) + len(deferred), len(refs),
                         "every discovered item must land in exactly one bucket")

    def test_the_real_feed_shape_does_not_become_a_backfill(self):
        """
        The measured feed: 142 items, 2026-06-01 to 2026-08-26. With a cutoff of
        2026-08-20 a first run must take the handful after it, not all 142.
        """
        refs = spread("2026-06-01", "2026-08-26")
        in_scope, pre, deferred, undated = jp_mod.partition_refs(refs, CUTOFF, 40)
        self.assertLess(len(in_scope), 20)
        self.assertGreater(len(pre), 60)

    def test_no_body_is_fetched_for_pre_bootstrap_items(self):
        source = (ROOT / "scripts" / "shadow_collect_japan.py").read_text("utf-8")
        block = source[source.index("def record_pre_bootstrap"):
                       source.index("def load_validators")]
        for forbidden in ("adapter.fetch", "adapter.extract", "_get("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, block)


class TestTheCapDefersRatherThanSamples(unittest.TestCase):
    """
    A cap that silently truncates is a sample presented as a feed. This one has
    to hand the overflow back, counted.
    """

    def test_overflow_is_returned_as_deferred_not_dropped(self):
        refs = spread("2026-08-20", "2026-09-30")          # 42 in scope
        in_scope, pre, deferred, undated = jp_mod.partition_refs(refs, CUTOFF, 10)
        self.assertEqual(len(in_scope), 10)
        self.assertEqual(len(deferred), len(refs) - 10)
        self.assertEqual(len(in_scope) + len(deferred), len(refs))

    def test_nothing_is_lost_when_the_cap_bites(self):
        refs = spread("2026-08-20", "2026-09-30")
        in_scope, pre, deferred, undated = jp_mod.partition_refs(refs, CUTOFF, 5)
        seen = {r.url for r in in_scope} | {r.url for r in deferred} | {r.url for r in pre}
        self.assertEqual(seen, {r.url for r in refs})

    def test_the_oldest_in_scope_items_go_first_so_nothing_starves(self):
        refs = spread("2026-08-20", "2026-09-30")
        in_scope, _, deferred, _ = jp_mod.partition_refs(refs, CUTOFF, 3)
        self.assertEqual([r.hint_published_date for r in in_scope],
                         ["2026-08-20", "2026-08-21", "2026-08-22"])

    def test_a_generous_cap_defers_nothing(self):
        refs = spread("2026-08-20", "2026-08-25")
        in_scope, _, deferred, _ = jp_mod.partition_refs(refs, CUTOFF, 500)
        self.assertEqual(deferred, [])
        self.assertEqual(len(in_scope), len(refs))

    def test_a_fixed_sample_size_is_not_hardcoded_anywhere(self):
        adapter = (ROOT / "scraper" / "sources" / "jp_mod.py").read_text("utf-8")
        self.assertNotIn("[:40]", adapter)
        self.assertNotIn("[:20]", adapter)


class TestUndatedItemsAreKeptAndCounted(unittest.TestCase):

    def test_an_undated_item_stays_in_scope(self):
        refs = [CandidateReference(url="https://www.mod.go.jp/j/press/x.pdf",
                                   source_slug="jp_mod_news_ja",
                                   hint_published_date=None)]
        in_scope, pre, deferred, undated = jp_mod.partition_refs(refs, CUTOFF, 40)
        self.assertEqual(len(in_scope), 1)
        self.assertEqual(len(undated), 1)
        self.assertEqual(pre, [])

    def test_an_unparseable_date_is_treated_as_undated_not_discarded(self):
        r = CandidateReference(url="https://www.mod.go.jp/j/press/y.pdf",
                               source_slug="jp_mod_news_ja",
                               hint_published_date="not-a-date")
        in_scope, pre, deferred, undated = jp_mod.partition_refs([r], CUTOFF, 40)
        self.assertEqual(len(in_scope), 1)
        self.assertEqual(len(undated), 1)


class TestReorderedAndDuplicateFeeds(unittest.TestCase):

    def test_feed_order_does_not_change_the_partition(self):
        refs = spread("2026-06-01", "2026-08-27")
        a = jp_mod.partition_refs(refs, CUTOFF, 40)
        b = jp_mod.partition_refs(list(reversed(refs)), CUTOFF, 40)
        self.assertEqual([r.url for r in a[0]], [r.url for r in b[0]])
        self.assertEqual({r.url for r in a[1]}, {r.url for r in b[1]})

    def test_canonical_form_is_the_identity(self):
        self.assertEqual(
            jp_mod.canonical_url("/j/press/news/2026/08/25a.pdf"),
            jp_mod.canonical_url(
                "https://www.mod.go.jp/j/press/news/2026/08/25a.pdf?x=1#f"))


class TestTheRequestFlowStaysControlled(unittest.TestCase):

    def test_one_worker_and_a_pause_between_requests(self):
        self.assertGreaterEqual(jp_mod.REQUEST_INTERVAL, 1.0)

    def test_the_retry_budget_is_small(self):
        self.assertLessEqual(jp_mod.MAX_RETRIES, 2)

    def test_there_is_no_concurrency(self):
        source = (ROOT / "scraper" / "sources" / "jp_mod.py").read_text("utf-8")
        for forbidden in ("ThreadPool", "concurrent.futures", "asyncio",
                          "multiprocessing"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_a_challenged_html_item_costs_no_request_at_all(self):
        source = (ROOT / "scraper" / "sources" / "jp_mod.py").read_text("utf-8")
        block = source[source.index("    def fetch("):source.index("    def extract(")]
        head = block[:block.index("try:")]
        self.assertIn("if not is_pdf(reference.url):", head)
        # The source names the symbol, not its value.
        self.assertIn("st.ACCESS_CHALLENGED", head)


if __name__ == "__main__":
    unittest.main()


class TestPreBootstrapHistoryIsActuallyPersisted(unittest.TestCase):
    """
    A run that finds nothing in scope still has history to record, and that is
    exactly the run that used to lose it: the early return closed the database
    without committing, so the ledger reported 288 pre-bootstrap entries while
    the table held none. Found by a dry run, not by a unit test, so here is the
    unit test.
    """

    def _run(self, refs):
        import shutil
        from core.collection.contract import DiscoveryResult

        class Adapter:
            slug = "jp_mod_news_ja"
            _titles = {r.url: "t" for r in refs}

            def discover(self, window):
                return DiscoveryResult(source_slug=self.slug, status=st.OK,
                                       references=list(refs))

            def fetch(self, ref):     # never reached for pre-bootstrap items
                raise AssertionError("a pre-bootstrap item must not be fetched")

        tmp = tempfile.mkdtemp(prefix="preboot-")
        try:
            state = Path(tmp) / "state"
            entry = runner.run(state, date(2026, 8, 27), 0, 40, "run-1", "c",
                               adapter=Adapter())
            conn = sqlite3.connect(str(state / "shadow.db"))
            rows = conn.execute(
                "SELECT url, published_date FROM shadow_pre_bootstrap").fetchall()
            conn.close()
            return entry, rows
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_history_survives_a_run_that_collects_nothing(self):
        refs = spread("2026-06-01", "2026-08-26")
        entry, rows = self._run(refs)
        self.assertEqual(entry["selected"], 0)
        self.assertEqual(entry["pre_bootstrap"], len(refs))
        self.assertEqual(len(rows), len(refs),
                         "the ledger counted history the database did not keep")

    def test_the_ledger_total_matches_the_table(self):
        refs = spread("2026-06-01", "2026-08-26")
        entry, rows = self._run(refs)
        self.assertEqual(entry["pre_bootstrap_total"], len(rows))

    def test_such_a_run_is_not_described_as_nothing_published(self):
        """The feeds carried plenty; nothing was in scope. Different claims."""
        entry, _ = self._run(spread("2026-06-01", "2026-08-26"))
        self.assertIn("predate the collection cutoff",
                      entry["error_detail"] or "")

    def test_the_history_table_has_no_body_column(self):
        """Recording that a document exists must not become storing it."""
        import shutil
        tmp = tempfile.mkdtemp(prefix="preboot-")
        try:
            state = Path(tmp) / "state"
            self._run(spread("2026-06-01", "2026-06-03"))
            state.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(":memory:")
            conn.executescript(runner.SCHEMA)
            cols = [d[1] for d in
                    conn.execute("PRAGMA table_info(shadow_pre_bootstrap)")]
            conn.close()
            for forbidden in ("text_original", "body", "content_sha256"):
                with self.subTest(column=forbidden):
                    self.assertNotIn(forbidden, cols)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
