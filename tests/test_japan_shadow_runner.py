"""
Japan shadow runner — isolation, ledger integrity, and honest counters.

The runner is the piece that can do damage: it opens a database, writes files,
and runs on a schedule. These tests pin the properties that keep it harmless —
it writes only inside its state directory, it never names production, and the
numbers it reports match what actually happened.

They also pin the one judgment that is Japan-specific and easy to get wrong by
copying Singapore: a challenged item is a **disclosed gap**, not a failed run.
Japan's HTML estate is behind a bot-mitigation challenge, so a normal run has
most items challenged. A taxonomy that called that `fail` would be permanently
red and therefore useless.

No network. The adapter is driven by a stub session.
"""
import ast
import importlib.util
import json
import re
import sqlite3
import sys
import tempfile
import os
import subprocess
import textwrap
import unittest
from unittest import mock
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection import status as st                     # noqa: E402
from core.collection.contract import (CandidateReference, CaptureResult,
                                      DiscoveryResult, ExtractionResult, ExtractedDocument)
from scraper.sources import jp_mod                           # noqa: E402
from tests.test_jp_mod_adapter import (                      # noqa: E402
    FEED, PDF_URL, Response, Session, challenge, feed_ok, pdf_ok)

_spec = importlib.util.spec_from_file_location(
    "shadow_collect_japan", ROOT / "scripts" / "shadow_collect_japan.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)


def executable_source(path: Path) -> str:
    """
    The module's code with docstrings and comments removed.

    Scanning raw text for a forbidden name flags the sentence "never opens
    `pla_watch.db`" in the docstring that promises not to — a guard that fails
    on the documentation of the property it is guarding. The isolation claim is
    about what the code *does*, so the prose is stripped before matching.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)) or not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            body.pop(0)
    return ast.unparse(tree) if hasattr(ast, "unparse") else "\n".join(
        repr(n) for n in ast.walk(tree))


def make_adapter(routes, validators=None):
    class Source:
        slug = "jp_mod_releases"
    return jp_mod.JPModAdapter(Source(), session=Session(routes),
                               sleep=lambda _s: None, validators=validators)


ALL_FEEDS = {jp_mod.FEEDS[0]: feed_ok, jp_mod.FEEDS[1]: feed_ok}


def routes_with_pdf():
    r = dict(ALL_FEEDS)
    r[PDF_URL] = pdf_ok()
    return r


class RunnerCase(unittest.TestCase):

    #: The fixture feed is dated 2026-08-24..26. The bootstrap cutoff defaults
    #: to the day the first run happens, which would put the whole fixture
    #: before it and leave these tests measuring an empty run. Seeding an
    #: explicit earlier cutoff keeps them about what they are about — counters,
    #: state and the ledger — and the cutoff itself is covered by
    #: tests/test_japan_bootstrap_contract.py.
    SEEDED_CUTOFF = "2026-08-01"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = Path(self._tmp.name) / "state"
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / "bootstrap.json").write_text(json.dumps({
            "cutoff_utc": self.SEEDED_CUTOFF + "T00:00:00+00:00",
            "cutoff_date": self.SEEDED_CUTOFF,
            "established_run": "seed",
        }) + "\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def go(self, routes=None, **kw):
        return runner.run(
            self.state, date(2026, 8, 26), 30, 40, "run-1", "deadbeef",
            adapter=make_adapter(routes or routes_with_pdf()), **kw)


# ------------------------------------------------------------------ isolation

class TestIsolation(RunnerCase):

    def test_it_refuses_a_state_dir_inside_the_repository(self):
        with self.assertRaises(SystemExit):
            runner.run(ROOT / "state", date(2026, 8, 26), 30, 40, "r", "c",
                       adapter=make_adapter(ALL_FEEDS))

    def test_it_refuses_the_repository_root_itself(self):
        with self.assertRaises(SystemExit):
            runner.run(ROOT, date(2026, 8, 26), 30, 40, "r", "c",
                       adapter=make_adapter(ALL_FEEDS))

    def test_it_writes_only_inside_the_state_directory(self):
        before = {p for p in ROOT.rglob("*") if ".git" not in p.parts}
        self.go()
        after = {p for p in ROOT.rglob("*") if ".git" not in p.parts}
        self.assertEqual(before, after,
                         "the runner created or removed a path in the repo")

    def test_it_never_names_the_production_database_or_output(self):
        source = executable_source(ROOT / "scripts" / "shadow_collect_japan.py")
        for forbidden in ("pla_watch.db", "OUTPUT_DIR", "output/", "gh-pages"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_it_imports_nothing_from_the_production_pipeline(self):
        source = executable_source(ROOT / "scripts" / "shadow_collect_japan.py")
        for forbidden in ("import pipeline", "from pipeline",
                          "import storage", "from storage", "from config"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_isolation_guard_still_catches_a_real_reference(self):
        """
        Narrowing the scan to executable code must not have blunted it. A real
        assignment naming the production database has to fail.
        """
        import tempfile as _tf
        with _tf.NamedTemporaryFile("w", suffix=".py", delete=False,
                                    encoding="utf-8") as fh:
            fh.write('"""Never opens pla_watch.db."""\n'
                     'DB = "pla_watch.db"\n')
            probe = Path(fh.name)
        try:
            self.assertIn("pla_watch.db", executable_source(probe))
        finally:
            probe.unlink()

    def test_the_isolation_guard_ignores_the_promise_in_the_docstring(self):
        import tempfile as _tf
        with _tf.NamedTemporaryFile("w", suffix=".py", delete=False,
                                    encoding="utf-8") as fh:
            fh.write('"""Never opens pla_watch.db."""\n'
                     'VALUE = 1\n')
            probe = Path(fh.name)
        try:
            self.assertNotIn("pla_watch.db", executable_source(probe))
        finally:
            probe.unlink()

    def test_the_manifest_is_not_under_desks(self):
        self.assertFalse((ROOT / "desks" / "japan").exists())
        self.assertTrue((ROOT / "shadow" / "jp_mod" / "manifest.json").exists())

    def test_the_japan_source_is_enabled_only_in_shadow(self):
        m = json.loads((ROOT / "shadow" / "jp_mod" / "manifest.json")
                       .read_text("utf-8"))
        self.assertTrue(m["sources"][0]["enabled"])
        self.assertFalse(m["desk"]["active"])
        self.assertEqual(m["desk"]["public_status"], "shadow")
        registry = json.loads((ROOT / "desks/registry.json").read_text())
        japan = next(d for d in registry["desks"] if d["slug"] == "japan")
        self.assertEqual(japan["status"], "shadow")
        self.assertTrue(japan["public"])
        self.assertFalse(japan["has_production_records"])
        self.assertEqual(japan["manifest"], "shadow/jp_mod/manifest.json")


# ------------------------------------------------------------------- counters

class TestHonestCounters(RunnerCase):

    def test_a_normal_run_stores_the_pdf_and_records_the_challenged_html(self):
        entry = self.go()
        self.assertEqual(entry["selected"], 6)
        self.assertEqual(entry["inserted"], 1)      # the one PDF item
        self.assertEqual(entry["challenged"], 5)    # the five HTML items
        self.assertEqual(entry["fetch_failures"], 0)

    def test_a_challenged_item_is_not_counted_as_a_fetch_failure(self):
        entry = self.go()
        self.assertEqual(entry["fetch_failures"], 0)
        self.assertEqual(entry["extraction_failures"], 0)

    def test_a_partially_challenged_run_is_ok_but_flagged_partial(self):
        entry = self.go()
        self.assertEqual(entry["result"], st.OK)
        self.assertEqual(entry["health"], "partial",
                         "a run with a disclosed gap must not read as clean")

    def test_the_gap_is_stated_in_the_ledger_entry(self):
        entry = self.go()
        self.assertIn("challenge", (entry["error_detail"] or "").lower())
        self.assertEqual(len(entry["challenged_urls"]), 5)

    def test_everything_challenged_is_degraded_not_a_listing_failure(self):
        routes = dict(ALL_FEEDS)
        routes[PDF_URL] = challenge()
        entry = self.go(routes)
        self.assertEqual(entry["result"], st.ACCESS_CHALLENGED)
        self.assertEqual(entry["health"], "degraded")

    def test_a_dead_feed_is_a_listing_failure(self):
        entry = self.go({jp_mod.FEEDS[0]: Response(500),
                         jp_mod.FEEDS[1]: Response(500)})
        self.assertEqual(entry["result"], st.LISTING_FAILURE)
        self.assertEqual(entry["health"], "fail")

    def test_counts_reconcile_with_what_was_selected(self):
        entry = self.go()
        accounted = (entry["inserted"] + entry["duplicates"]
                     + entry["challenged"] + entry["fetch_failures"]
                     + entry["extraction_failures"])
        self.assertEqual(accounted, entry["selected"],
                         "every selected item must land in exactly one bucket")


# ---------------------------------------------------------------------- state

class TestPolicyLedger(RunnerCase):

    def test_policy_refusal_is_failed_evidence_not_an_empty_or_partial_success(self):
        for response, status in [(challenge(), st.ACCESS_CHALLENGED),
                                 (Response(403), st.AUTH_FAILURE),
                                 (Response(200, text="User-agent: *\nDisallow: /j/\n",
                                           headers={"Content-Type": "text/plain"}), st.AUTH_FAILURE)]:
            with self.subTest(status=status, body=response.text):
                a = make_adapter({jp_mod.ROBOTS: response})
                entry = runner.run(self.state, date(2026, 8, 26), 30, 40,
                                   "policy-" + status, "deadbeef", adapter=a)
                self.assertEqual((entry["result"], entry["health"]), (status, "fail"))
                self.assertEqual(entry["robots_status"], status)
                self.assertEqual(entry["listing_status"], status)
                self.assertEqual(entry["stored_total"], 0)
                self.assertIsNone(entry["shadow_day"])
                self.assertFalse((self.state / "clock.json").exists())
                self.assertTrue(entry["policy_failures"])
                self.assertEqual([u for u, _ in a._session.calls], [jp_mod.ROBOTS])
                with mock.patch.object(runner, "run", return_value=entry):
                    self.assertEqual(runner.main(["--state-dir", str(self.state),
                                                  "--target-date", "2026-08-26"]), 1)

    def test_policy_failure_preserves_prior_corpus_clock_bootstrap_and_ledgers(self):
        self.go()
        prior = {p: p.read_bytes() for p in self.state.rglob("*") if p.is_file()}
        entry = runner.run(self.state, date(2026, 8, 26), 30, 40, "policy-failure",
                           "deadbeef", adapter=make_adapter({jp_mod.ROBOTS: challenge()}))
        for p, data in prior.items():
            self.assertEqual(p.read_bytes(), data, str(p))
        self.assertEqual(entry["state_sha256_before"], entry["state_sha256_after"])
        self.assertEqual(entry["stored_total"], 1)
        self.assertIsNone(entry["shadow_day"])

    def test_two_feeds_share_one_policy_refusal_and_no_listing_request(self):
        session = Session({jp_mod.ROBOTS: challenge()})
        real_adapter = jp_mod.JPModAdapter
        with mock.patch.object(runner, "JPModAdapter", side_effect=lambda src, **kw:
                               real_adapter(src, session=session, sleep=lambda _: None, **kw)):
            entry = runner.run(self.state, date(2026, 8, 26), 30, 40,
                               "both-feeds-refused", "deadbeef")
        self.assertEqual([u for u, _ in session.calls], [jp_mod.ROBOTS])
        self.assertEqual(len(entry["policy_failures"]), 2)
        self.assertEqual(entry["health"], "fail")

    def test_allowed_is_observed_and_an_absent_file_is_recorded_separately(self):
        entry = self.go()
        bucket = entry["sources"][0]
        self.assertEqual(entry["robots_status"], "allowed")
        self.assertEqual(bucket["robots_observation"]["http_status"], 200)
        self.assertIn("payload_sha256", bucket["robots_observation"])
        routes = routes_with_pdf()
        routes[jp_mod.ROBOTS] = Response(404)
        entry = runner.run(self.state, date(2026, 8, 26), 30, 40,
                           "absent-policy", "deadbeef", adapter=make_adapter(routes))
        self.assertEqual(entry["robots_status"], "absent")
        self.assertEqual(entry["sources"][0]["robots_observation"]["http_status"], 404)

class TestStateAndLedger(RunnerCase):

    def test_the_state_database_holds_the_stored_record(self):
        self.go()
        conn = sqlite3.connect(str(self.state / "shadow.db"))
        rows = conn.execute("SELECT url, title_original, language_tag "
                            "FROM shadow_records").fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], PDF_URL)
        self.assertEqual(rows[0][1], "日米合同委員会合意について")
        self.assertEqual(rows[0][2], "ja")

    def test_unretrieved_items_are_rows_not_absences(self):
        self.go()
        conn = sqlite3.connect(str(self.state / "shadow.db"))
        rows = conn.execute("SELECT url, reason FROM shadow_unretrieved").fetchall()
        conn.close()
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r[1] == "access_challenged" for r in rows))

    def test_an_unretrieved_item_seen_again_increments_rather_than_duplicates(self):
        self.go()
        runner.run(self.state, date(2026, 8, 26), 30, 40, "run-2", "c",
                   adapter=make_adapter(routes_with_pdf()))
        conn = sqlite3.connect(str(self.state / "shadow.db"))
        n, seen = conn.execute(
            "SELECT COUNT(*), MAX(seen_count) FROM shadow_unretrieved").fetchone()
        conn.close()
        self.assertEqual(n, 5)
        self.assertEqual(seen, 2)

    def test_a_second_run_stores_no_duplicate_record(self):
        self.go()
        entry = runner.run(self.state, date(2026, 8, 26), 30, 40, "run-2", "c",
                           adapter=make_adapter(routes_with_pdf()))
        self.assertEqual(entry["inserted"], 0)
        self.assertEqual(entry["duplicates"], 1)

    def test_validators_are_stored_for_the_next_run(self):
        self.go()
        conn = sqlite3.connect(str(self.state / "shadow.db"))
        rows = conn.execute("SELECT url, etag FROM shadow_validators").fetchall()
        conn.close()
        self.assertEqual(rows, [(PDF_URL, '"pdf-1"')])

    def test_a_ledger_entry_is_written_per_run(self):
        self.go()
        self.assertEqual(len(list((self.state / "ledger").glob("*.json"))), 1)
        runner.run(self.state, date(2026, 8, 26), 30, 40, "run-2", "c",
                   adapter=make_adapter(routes_with_pdf()))
        self.assertEqual(len(list((self.state / "ledger").glob("*.json"))), 2)

    def test_the_ledger_chains_the_state_hash(self):
        first = self.go()
        second = runner.run(self.state, date(2026, 8, 26), 30, 40, "run-2", "c",
                            adapter=make_adapter(routes_with_pdf()))
        self.assertIsNone(first["state_sha256_before"])
        self.assertEqual(second["state_sha256_before"],
                         first["state_sha256_after"],
                         "each run must start from the hash the last one left")

    def test_day_zero_is_written_once_and_never_rewritten(self):
        self.go()
        clock = json.loads((self.state / "clock.json").read_text("utf-8"))
        runner.run(self.state, date(2026, 8, 27), 30, 40, "run-2", "c",
                   adapter=make_adapter(routes_with_pdf()))
        self.assertEqual(
            json.loads((self.state / "clock.json").read_text("utf-8")), clock)

    def test_a_failed_run_does_not_start_the_clock(self):
        self.go({jp_mod.FEEDS[0]: Response(500), jp_mod.FEEDS[1]: Response(500)})
        self.assertFalse((self.state / "clock.json").exists())

    def test_the_ledger_entry_is_deterministic_json(self):
        self.go()
        path = next((self.state / "ledger").glob("*.json"))
        body = path.read_text("utf-8")
        self.assertEqual(body, json.dumps(json.loads(body), indent=1,
                                          sort_keys=True) + "\n")

    def test_no_wal_or_shm_sidecar_survives_the_run(self):
        self.go()
        for suffix in ("-wal", "-shm"):
            with self.subTest(suffix=suffix):
                self.assertFalse((self.state / ("shadow.db" + suffix)).exists())


class TestSourceEnablement(unittest.TestCase):
    def configured(self, change):
        manifest = json.loads(runner.MANIFEST.read_text())
        change(manifest)
        with mock.patch.object(Path, "read_text", return_value=json.dumps(manifest)):
            return runner.load_sources()

    def test_disabled_and_missing_enabled_sources_are_excluded(self):
        def change(manifest):
            manifest["sources"][0]["enabled"] = False
            manifest["sources"][1].pop("enabled")
        self.assertEqual(self.configured(change), [])

    def test_not_collected_excludes_even_an_enabled_source(self):
        def change(manifest):
            for source in manifest["sources"]:
                source["enabled"] = True
        self.assertEqual([src.slug for src in self.configured(change)],
                         ["jp_mod_news_ja", "jp_mod_siteupdate_ja"])


class QueueAdapter:
    """Clearly derived URLs/bodies, exercising the runner without transport."""
    slug = "jp_mod_news_ja"

    def __init__(self, refs, statuses=None):
        self.refs = refs
        self.statuses = statuses or {}
        self._titles = {r.url: "derived fixture" for r in refs}
        self.fetched = []

    def discover(self, window):
        return DiscoveryResult(self.slug, st.OK, list(self.refs))

    def fetch(self, ref):
        self.fetched.append(ref.url)
        return CaptureResult(ref, self.statuses.get(ref.url, st.OK), ref.url)

    def extract(self, capture):
        return ExtractionResult(self.slug, st.OK, [ExtractedDocument(
            capture.requested_url, self.slug, self._titles[capture.requested_url],
            "derived body", capture.reference.hint_published_date, language_tag="ja",
            extra={"publication_kind": "press release", "content_sha256": "derived-hash"})])


def queued_ref(n, day="2026-08-20"):
    return CandidateReference("https://www.mod.go.jp/j/press/derived-%d.pdf" % n,
                              QueueAdapter.slug, hint_published_date=day)


class TestSelectionDoesNotStarve(RunnerCase):
    def test_repeated_failures_do_not_starve_evicted_never_attempted_urls(self):
        refs = [queued_ref(n) for n in range(3)]
        failures = {ref.url: st.FETCH_FAILURE for ref in refs}
        for n in range(3):
            adapter = QueueAdapter(refs if n == 0 else [], failures)
            entry = self.collect(adapter, run_id="fail-%d" % n)
            self.assertEqual(adapter.fetched, [refs[n].url])
            self.assertEqual((entry["unretrieved_total"], entry["health"]), (3, "fail"))
            self.assertEqual(entry["deferred"], 2)

    def test_off_feed_challenges_still_disclose_an_outstanding_gap(self):
        ref = queued_ref(1)
        self.collect(QueueAdapter([ref], {ref.url: st.ACCESS_CHALLENGED}))
        adapter = QueueAdapter([])
        entry = self.collect(adapter, run_id="r2")
        self.assertEqual(adapter.fetched, [])
        self.assertEqual(entry["unretrieved_total"], 1)
        self.assertEqual(entry["outstanding_challenged"], 1)
        self.assertEqual((entry["result"], entry["health"]), (st.ACCESS_CHALLENGED, "degraded"))

    def test_a_stored_pdf_does_not_hide_fetch_or_extraction_failures(self):
        refs = [queued_ref(1), queued_ref(2)]
        for extraction in (False, True):
            with self.subTest(extraction=extraction):
                adapter = QueueAdapter(refs, {} if extraction else {refs[1].url: st.FETCH_FAILURE})
                original = adapter.extract
                if extraction:
                    adapter.extract = lambda capture: (
                        ExtractionResult(adapter.slug, st.EXTRACTION_FAILURE, error_detail="derived failure")
                        if capture.requested_url == refs[1].url else original(capture))
                entry = self.collect(adapter, cap=2, run_id="partial-%s" % extraction)
                self.assertEqual(entry["health"], "partial")
                self.assertEqual(entry["unretrieved_total"], 1)

    def test_a_new_challenge_does_not_mask_an_open_pdf_route_failure(self):
        refs = [queued_ref(1), queued_ref(2)]
        entry = self.collect(QueueAdapter(refs, {refs[0].url: st.ACCESS_CHALLENGED,
                                                 refs[1].url: st.FETCH_FAILURE}), cap=2)
        self.assertEqual((entry["result"], entry["health"]), (st.FETCH_FAILURE, "fail"))

    def test_a_failed_feed_is_disclosed_alongside_a_successful_feed(self):
        good, bad = QueueAdapter([queued_ref(1)]), QueueAdapter([])
        bad.discover = lambda window: DiscoveryResult(bad.slug, st.LISTING_FAILURE,
                                                       failed_endpoints=["derived endpoint"])
        with mock.patch.object(runner, "load_sources", return_value=[good, bad]), \
                mock.patch.object(runner, "JPModAdapter", side_effect=[good, bad]):
            entry = runner.run(self.state, date(2026, 8, 26), 14, 40, "r1", "c")
        self.assertEqual((entry["inserted"], entry["listing_failures"], entry["health"]),
                         (1, 1, "partial"))
        self.assertEqual(entry["sources"][1]["failed_endpoints"], ["derived endpoint"])

    def test_legacy_off_feed_gap_is_unassigned_and_not_silently_healthy(self):
        ref = queued_ref(1)
        with sqlite3.connect(str(self.state / "shadow.db")) as db:
            db.executescript(runner.SCHEMA)
            db.execute("INSERT INTO shadow_unretrieved VALUES (?,?,?,?,?,?,?)",
                       (ref.url, "historical title", "2026-08-20", st.FETCH_FAILURE,
                        "original", "original", 1))
        adapter = QueueAdapter([])
        entry = self.collect(adapter)
        self.assertEqual(adapter.fetched, [])
        self.assertEqual((entry["unretrieved_total"], entry["health"]), (1, "partial"))
        self.assertEqual(entry["unassigned_gap_urls"], [ref.url])
        with sqlite3.connect(str(self.state / "shadow.db")) as db:
            self.assertEqual(db.execute("SELECT title_original, first_seen_run, last_seen_run,"
                                        " source_slug FROM shadow_unretrieved").fetchone(),
                             ("historical title", "original", "original", None))

    def test_an_orphan_validator_or_304_does_not_claim_a_stored_body(self):
        ref = queued_ref(1)
        with sqlite3.connect(str(self.state / "shadow.db")) as db:
            db.executescript(runner.SCHEMA)
            db.execute("INSERT INTO shadow_validators VALUES (?,?,?,?)", (ref.url, "old", None, "old"))
            self.assertEqual(runner.load_validators(db), {})
        entry = self.collect(QueueAdapter([ref], {ref.url: st.OK_ALL_DUPLICATES}))
        self.assertEqual((entry["duplicates"], entry["fetch_failures"], entry["unretrieved_total"]),
                         (0, 1, 1))

    def collect(self, adapter, cap=1, run_id="r1"):
        return runner.run(self.state, date(2026, 8, 26), 14, cap, run_id, "c", adapter=adapter)

    def test_old_challenges_and_stored_urls_do_not_consume_the_next_cap(self):
        old = [queued_ref(n) for n in range(40)]
        statuses = {ref.url: st.ACCESS_CHALLENGED for ref in old[:-1]}
        first = self.collect(QueueAdapter(old, statuses), cap=40)
        ledger = next((self.state / "ledger").glob("*.json"))
        old_bytes = ledger.read_bytes()
        newer = [queued_ref(40, "2026-08-25"), queued_ref(41, "2026-08-26")]
        second_adapter = QueueAdapter(old + newer, statuses)
        second = self.collect(second_adapter, cap=2, run_id="r2")
        self.assertEqual(second_adapter.fetched, [ref.url for ref in newer])
        self.assertEqual((second["inserted"], second["known_challenged"], second["deferred"]),
                         (2, 39, 0))
        self.assertEqual(second["revalidation_deferred"], 1)
        self.assertEqual(second["result"], st.OK)
        self.assertEqual(second["health"], "partial")
        self.assertEqual(second["state_sha256_before"], first["state_sha256_after"])
        self.assertEqual(ledger.read_bytes(), old_bytes)

    def test_overflow_survives_feed_turnover_and_drains_under_the_same_cap(self):
        refs = [queued_ref(n) for n in range(3)]
        first = self.collect(QueueAdapter(refs))
        self.assertEqual(first["deferred_urls"], [ref.url for ref in refs[1:]])
        second_adapter = QueueAdapter([])
        second = self.collect(second_adapter, run_id="r2")
        self.assertEqual(second["discovered"], 0)
        self.assertEqual(second["carried_pending"], 2)
        self.assertEqual(second_adapter.fetched, [refs[1].url])
        third = self.collect(QueueAdapter([]), run_id="r3")
        self.assertEqual(third["inserted"], 1)
        self.assertEqual(third["deferred"], 0)
        with sqlite3.connect(str(self.state / "shadow.db")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0], 3)
            # The gap rows remain as provenance even after later retrieval.
            self.assertEqual(db.execute("SELECT COUNT(*) FROM shadow_unretrieved").fetchone()[0], 2)

    def test_transient_failures_wait_behind_never_seen_items(self):
        old, newer = queued_ref(1), queued_ref(2, "2026-08-26")
        self.collect(QueueAdapter([old], {old.url: st.FETCH_FAILURE}))
        adapter = QueueAdapter([old, newer], {old.url: st.FETCH_FAILURE})
        entry = self.collect(adapter, run_id="r2")
        self.assertEqual(adapter.fetched, [newer.url])
        self.assertEqual(entry["inserted"], 1)
        self.assertEqual(entry["deferred_urls"], [old.url])

    def test_pdf_validators_still_revalidate_when_capacity_remains(self):
        first = self.go()
        routes = dict(ALL_FEEDS)
        routes[PDF_URL] = Response(304)
        second = runner.run(self.state, date(2026, 8, 26), 14, 40, "r2", "c",
                            adapter=make_adapter(routes, {PDF_URL: {"etag": '"pdf-1"'}}))
        self.assertEqual((second["duplicates"], second["known_challenged"], second["challenged"]),
                         (1, 5, 0))
        self.assertEqual(second["result"], st.OK_ALL_DUPLICATES)
        self.assertEqual(second["health"], "partial")

    def test_existing_state_gets_only_a_forward_schema_extension(self):
        with sqlite3.connect(str(self.state / "shadow.db")) as db:
            db.executescript(runner.SCHEMA)
            db.execute("INSERT INTO shadow_unretrieved VALUES (?,?,?,?,?,?,?)",
                       (queued_ref(1).url, "historical title", "2026-08-20",
                        st.ACCESS_CHALLENGED, "original", "original", 1))
        adapter = QueueAdapter([queued_ref(1), queued_ref(2)])
        entry = self.collect(adapter)
        self.assertEqual(adapter.fetched, [queued_ref(2).url])
        with sqlite3.connect(str(self.state / "shadow.db")) as db:
            row = db.execute("SELECT first_seen_run, title_original, reason FROM shadow_unretrieved"
                             " WHERE url = ?", (queued_ref(1).url,)).fetchone()
        self.assertEqual(row, ("original", "historical title", st.ACCESS_CHALLENGED))

    def test_all_disabled_sources_do_not_collect_or_start_clock(self):
        with mock.patch.object(runner, "load_sources", return_value=[]), \
                mock.patch.object(runner, "JPModAdapter") as adapter:
            entry = runner.run(self.state, date(2026, 8, 26), 14, 40, "r", "c")
        adapter.assert_not_called()
        self.assertEqual(entry["result"], st.SKIPPED_DISABLED)
        self.assertFalse((self.state / "clock.json").exists())

    def test_completed_failure_is_publishable_but_a_crash_or_changed_hash_is_not(self):
        raw = (ROOT / ".github/workflows/japan_shadow.yml").read_text()
        body = raw.split("      - name: Verify the completed attempt and immutable history\n", 1)[1]
        body = textwrap.dedent(body.split("run: |\n", 1)[1]
                               .split("      - name:", 1)[0].split("\n      #", 1)[0])
        self.assertIn("continue-on-error: true", raw)
        self.assertIn("if: steps.collect.outcome == 'failure'", raw)
        self.assertLess(raw.index("- name: Publish shadow state"),
                        raw.index("- name: Report collection failure"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # The executable verification block expects the same layout as Actions.
            subprocess.run(["git", "init", str(root / "shadow-state")], check=True, capture_output=True)
            (root / "workspace").mkdir()
            (root / "workspace/repo").symlink_to(ROOT, target_is_directory=True)
            state = root / "shadow-state/state"
            state.mkdir()
            (state / "bootstrap.json").write_text((self.state / "bootstrap.json").read_text())
            commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
            failed = runner.run(state, date(2026, 8, 26), 14, 1, "test-1", commit,
                                adapter=QueueAdapter([queued_ref(1), queued_ref(2)],
                                                     {queued_ref(1).url: st.FETCH_FAILURE}))
            self.assertEqual(failed["result"], st.FETCH_FAILURE)
            env = dict(os.environ, RUNNER_TEMP=str(root), GITHUB_WORKSPACE=str(root / "workspace"),
                       GITHUB_RUN_ID="test", GITHUB_RUN_ATTEMPT="1",
                       PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
            def verify():
                return subprocess.run(["bash", "-c", body], env=env, capture_output=True)
            checked = verify()
            self.assertEqual(checked.returncode, 0, checked.stderr.decode())
            # Failed gap rows are now durable input: the next cap admits the newer URL.
            next_adapter = QueueAdapter([queued_ref(1), queued_ref(2)])
            runner.run(state, date(2026, 8, 26), 14, 1, "next-1", commit, adapter=next_adapter)
            self.assertEqual(next_adapter.fetched, [queued_ref(2).url])
            self.assertNotEqual(verify().returncode, 0)  # old completed hash no longer matches
            env["GITHUB_RUN_ATTEMPT"] = "2"          # crash: no ledger for this attempt
            self.assertNotEqual(verify().returncode, 0)


if __name__ == "__main__":
    unittest.main()


class TestTheWorkflowCannotEscapeItsStateBranch(unittest.TestCase):
    """
    The workflow is the only part of this collector that runs unattended with a
    write token. What it is allowed to touch is therefore a contract, not a
    convention.

    Assertions run against the workflow's *executable* lines. The file's header
    comment promises "no Pages step" and "no output/ generation"; matching raw
    text would find those promises and read them as violations.
    """

    PATH = ROOT / ".github" / "workflows" / "japan_shadow.yml"

    @classmethod
    def setUpClass(cls):
        cls.raw = cls.PATH.read_text(encoding="utf-8")
        cls.code = "\n".join(
            line for line in cls.raw.splitlines()
            if not line.lstrip().startswith("#"))

    def test_the_workflow_exists(self):
        self.assertTrue(self.PATH.is_file())

    def test_it_requests_only_contents_write(self):
        block = re.search(r"^permissions:\n((?:  .*\n)+)", self.code, re.M)
        self.assertIsNotNone(block)
        self.assertEqual(block.group(1).strip(), "contents: write")

    def test_it_pushes_only_the_shadow_state_branch(self):
        pushes = re.findall(r"git push \S+ (\S+)", self.code)
        self.assertEqual(set(pushes), {"shadow/jp-mod"})

    def test_it_never_pushes_main_or_gh_pages(self):
        for ref in ("main", "gh-pages"):
            with self.subTest(ref=ref):
                self.assertNotIn("git push origin %s" % ref, self.code)

    def test_it_never_force_pushes(self):
        for flag in ("--force", "--force-with-lease", "push -f"):
            with self.subTest(flag=flag):
                self.assertNotIn(flag, self.code)

    def test_it_has_no_deploy_or_pages_step(self):
        lowered = self.code.lower()
        for smell in ("deploy-pages", "upload-pages-artifact", "configure-pages",
                      "peaceiris/actions-gh-pages", "github-pages"):
            with self.subTest(smell=smell):
                self.assertNotIn(smell, lowered)

    def test_it_never_names_the_production_database_or_output(self):
        for forbidden in ("pla_watch.db", "output/"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.code)

    def test_it_does_not_invoke_the_production_pipeline(self):
        for forbidden in ("pipeline.py", "site/render.py", "generate_preview.py",
                          "validate_output.py"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.code)

    def test_it_runs_the_japan_runner_and_nothing_else(self):
        scripts = re.findall(r"python (scripts/\S+)", self.code)
        self.assertEqual(scripts, ["scripts/shadow_collect_japan.py"])

    def test_it_runs_once_a_day(self):
        crons = re.findall(r"- cron: '([^']+)'", self.code)
        self.assertEqual(len(crons), 1, "one scheduled run per day, no burst")

    def test_its_schedule_does_not_collide_with_another_collector(self):
        mine = re.findall(r"- cron: '([^']+)'", self.code)[0]
        others = []
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            if path.name == self.PATH.name:
                continue
            others += re.findall(r"- cron: '([^']+)'",
                                 path.read_text(encoding="utf-8"))
        self.assertNotIn(mine, others)

    def test_it_refuses_to_commit_a_sidecar(self):
        self.assertIn("shadow.db-wal", self.code)
        self.assertIn("shadow.db-shm", self.code)

    def test_it_asserts_the_collector_checkout_stayed_clean(self):
        self.assertIn("git status --porcelain", self.code)

    def test_the_state_directory_is_outside_the_checkout(self):
        self.assertIn("${RUNNER_TEMP}/shadow-state", self.code)
        self.assertNotIn("--state-dir repo/", self.code)
