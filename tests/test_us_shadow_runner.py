"""
US Indo-Pacific shadow runner: isolation, idempotence, and the ledger.

The runner's job is to collect into a state directory that can never be the
repository, and to leave behind a record honest enough that a reviewer can tell
what the run did without rerunning it.

Everything runs from saved bounded fixtures into a temporary directory. No
network, no tracked-database access, no writes inside the working tree.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                        # noqa: E402
from scraper.sources import us_dvids as us                      # noqa: E402
import scripts.shadow_collect_us as runner                      # noqa: E402
from tests.test_us_dvids_adapter import (                       # noqa: E402
    FakeSession, FakeSource, ROBOTS_DENY_ALL)

TRACKED_DB = REPO_ROOT / "pla_watch.db"
PRODUCTION_OUT = REPO_ROOT / "output"
TARGET = date(2026, 9, 16)


def make_adapter(session=None, cap=40):
    return us.USDvidsAdapter(FakeSource(), session=session or FakeSession(),
                             cap=cap, sleeper=lambda _s: None)


def tree_fingerprint(path: Path):
    """Hash of every file under `path`, so any write at all is visible."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        h.update(str(f.relative_to(path)).encode())
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


class RunnerCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = Path(self._tmp.name) / "state"
        self.addCleanup(self._tmp.cleanup)

    def run_once(self, session=None, run_id="r1", cap=40, lookback=7):
        return runner.run(self.state, TARGET, lookback, cap, run_id, "commit",
                          adapter=make_adapter(session, cap))

    def records(self):
        con = sqlite3.connect(str(self.state / "shadow.db"))
        try:
            return con.execute(
                "SELECT url, source_identity, title_original, text_original,"
                " published_date FROM shadow_records").fetchall()
        finally:
            con.close()

    def ledger(self):
        return sorted((self.state / "ledger").glob("*.json"))


class TestTheRunnerCannotReachProduction(RunnerCase):

    def test_it_refuses_a_state_directory_inside_the_repository(self):
        with self.assertRaises(SystemExit) as caught:
            runner.run(REPO_ROOT / "scratch_state", TARGET, 7, 40, "r", "c",
                       adapter=make_adapter())
        self.assertIn("refusing to write shadow state", str(caught.exception))

    def test_it_refuses_the_repository_root_itself(self):
        with self.assertRaises(SystemExit):
            runner.run(REPO_ROOT, TARGET, 7, 40, "r", "c",
                       adapter=make_adapter())

    def test_a_full_run_leaves_the_tracked_database_untouched(self):
        before = (TRACKED_DB.read_bytes() if TRACKED_DB.exists() else None)
        self.run_once()
        after = (TRACKED_DB.read_bytes() if TRACKED_DB.exists() else None)
        self.assertEqual(
            hashlib.sha256(before).hexdigest() if before else None,
            hashlib.sha256(after).hexdigest() if after else None)

    def test_a_full_run_creates_no_wal_or_shm_beside_the_tracked_database(self):
        self.run_once()
        self.assertFalse((REPO_ROOT / "pla_watch.db-wal").exists())
        self.assertFalse((REPO_ROOT / "pla_watch.db-shm").exists())

    def test_a_full_run_leaves_the_output_tree_untouched(self):
        before = tree_fingerprint(PRODUCTION_OUT)
        self.run_once()
        self.assertEqual(tree_fingerprint(PRODUCTION_OUT), before)

    def test_the_runner_module_names_no_production_path_in_code(self):
        source = (REPO_ROOT / "scripts" / "shadow_collect_us.py").read_text(
            encoding="utf-8")
        body = source.split('"""', 2)[2]
        self.assertNotIn("pla_watch.db", body)
        self.assertNotIn("output/", body)

    def test_the_manifest_lives_outside_the_desks_directory(self):
        self.assertTrue(runner.MANIFEST.exists())
        self.assertNotIn("desks", runner.MANIFEST.relative_to(REPO_ROOT).parts)

    def test_the_declared_source_is_not_enabled(self):
        self.assertFalse(runner.load_source().enabled)


class TestOneRunIsHonestAboutWhatItDid(RunnerCase):

    def test_a_successful_run_stores_only_news_records(self):
        entry = self.run_once()
        self.assertEqual(entry["result"], st.OK)
        self.assertEqual(entry["health"], "ok")
        self.assertEqual(entry["inserted"], 3)
        for url, _, _, _, _ in self.records():
            self.assertIn("/news/", url)

    def test_every_stored_record_has_a_non_empty_body(self):
        self.run_once()
        rows = self.records()
        self.assertTrue(rows)
        for url, ident, title, text, published in rows:
            self.assertTrue(text.strip(), url)
            self.assertGreater(len(text.strip()), us.MIN_BODY_CHARS, url)
            self.assertTrue(title.strip(), url)
            self.assertTrue(ident.isdigit(), url)
            self.assertRegex(published, r"^\d{4}-\d{2}-\d{2}$")

    def test_rejections_are_counted_in_the_ledger_not_discarded(self):
        entry = self.run_once()
        self.assertEqual(entry["rejections"][us.R_NOT_NEWS_MEDIA], 6)
        self.assertEqual(entry["rejected_total"],
                         sum(entry["rejections"].values()))
        self.assertGreater(entry["rejected_total"], 0)

    def test_the_three_items_without_captured_bodies_are_extraction_failures(self):
        # The feed fixture carries six news items; three have saved article
        # pages. The other three must be reported as extraction failures, not
        # quietly absent from every number in the ledger.
        entry = self.run_once()
        self.assertEqual(entry["selected"], 6)
        self.assertEqual(entry["retrieved"], 3)
        self.assertEqual(entry["fetch_failures"], 3)
        self.assertEqual(entry["inserted"], 3)

    def test_the_ledger_entry_is_written_once_and_is_readable(self):
        entry = self.run_once()
        files = self.ledger()
        self.assertEqual(len(files), 1)
        on_disk = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(on_disk["run_id"], entry["run_id"])
        self.assertEqual(on_disk["desk"], "us-indopacom")
        self.assertEqual(on_disk["result"], st.OK)

    def test_the_state_hash_records_the_database_before_and_after(self):
        entry = self.run_once()
        self.assertIsNone(entry["state_sha256_before"])
        self.assertIsNotNone(entry["state_sha256_after"])
        actual = hashlib.sha256(
            (self.state / "shadow.db").read_bytes()).hexdigest()
        self.assertEqual(entry["state_sha256_after"], actual)

    def test_day_zero_is_recorded_once_and_derived_thereafter(self):
        first = self.run_once(run_id="r1")
        clock = json.loads((self.state / "clock.json").read_text())
        self.assertEqual(clock["day_zero_run_id"], "r1")
        self.assertEqual(first["shadow_day"], 0)
        second = self.run_once(run_id="r2")
        self.assertEqual(
            json.loads((self.state / "clock.json").read_text()), clock)
        self.assertEqual(second["day_zero_utc"], clock["day_zero_utc"])

    def test_a_failed_run_neither_starts_nor_advances_the_clock(self):
        entry = self.run_once(session=FakeSession(robots=ROBOTS_DENY_ALL))
        self.assertEqual(entry["result"], st.AUTH_FAILURE)
        self.assertEqual(entry["health"], "fail")
        self.assertIsNone(entry["shadow_day"])
        self.assertFalse((self.state / "clock.json").exists())


class TestASecondRunChangesNothing(RunnerCase):

    def test_the_second_run_inserts_nothing_and_reports_all_duplicates(self):
        first = self.run_once(run_id="r1")
        second = self.run_once(run_id="r2")
        self.assertEqual(first["inserted"], 3)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["duplicates"], 3)
        self.assertEqual(second["result"], st.OK_ALL_DUPLICATES)
        self.assertEqual(second["health"], "ok")

    def test_the_stored_corpus_is_identical_after_the_second_run(self):
        self.run_once(run_id="r1")
        before = self.records()
        self.run_once(run_id="r2")
        self.assertEqual(self.records(), before)

    def test_the_corpus_total_does_not_grow(self):
        first = self.run_once(run_id="r1")
        second = self.run_once(run_id="r2")
        self.assertEqual(first["stored_total"], second["stored_total"])

    def test_no_url_and_no_identity_is_ever_stored_twice(self):
        self.run_once(run_id="r1")
        self.run_once(run_id="r2")
        self.run_once(run_id="r3")
        rows = self.records()
        urls = [r[0] for r in rows]
        idents = [r[1] for r in rows]
        self.assertEqual(len(set(urls)), len(urls))
        self.assertEqual(len(set(idents)), len(idents))

    def test_first_seen_run_still_names_the_run_that_found_each_record(self):
        self.run_once(run_id="r1")
        self.run_once(run_id="r2")
        con = sqlite3.connect(str(self.state / "shadow.db"))
        try:
            seen = {r[0] for r in con.execute(
                "SELECT DISTINCT first_seen_run FROM shadow_records")}
        finally:
            con.close()
        self.assertEqual(seen, {"r1"})

    def test_each_run_appends_its_own_ledger_entry(self):
        self.run_once(run_id="r1")
        self.run_once(run_id="r2")
        self.assertEqual(len(self.ledger()), 2)

    def test_the_database_that_stores_the_same_identity_twice_is_refused(self):
        # Defence in depth: even if the runner's duplicate check were removed,
        # the schema refuses a second row for the same DVIDS document.
        self.run_once(run_id="r1")
        con = sqlite3.connect(str(self.state / "shadow.db"))
        try:
            row = con.execute("SELECT source_identity FROM shadow_records "
                              "LIMIT 1").fetchone()
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute(
                    "INSERT INTO shadow_records (url, source_identity,"
                    " source_slug, title_original, text_original,"
                    " published_date, language_tag, publication_kind,"
                    " content_sha256) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("https://www.dvidshub.net/news/999999/other", row[0],
                     "us_dvids_indopacom", "t", "b", "2026-09-16", "en",
                     "public affairs release", "x"))
        finally:
            con.close()


class TestFailuresAreDistinguishedFromSilence(RunnerCase):

    def test_a_robots_refusal_is_an_auth_failure_and_fails_the_job(self):
        entry = self.run_once(session=FakeSession(robots_status=403))
        self.assertEqual(entry["result"], st.AUTH_FAILURE)
        self.assertEqual(entry["health"], "fail")
        self.assertEqual(entry["robots_status"], "disallowed")

    def test_an_unreadable_feed_is_a_listing_failure_and_stores_nothing(self):
        entry = self.run_once(session=FakeSession(feed_status=500))
        self.assertEqual(entry["result"], st.LISTING_FAILURE)
        self.assertEqual(entry["inserted"], 0)
        self.assertFalse((self.state / "shadow.db").exists())

    def test_an_empty_window_is_a_success_not_a_failure(self):
        entry = runner.run(self.state, date(2020, 1, 1), 1, 40, "r", "c",
                           adapter=make_adapter())
        self.assertEqual(entry["result"], st.OK_NO_PUBLICATIONS)
        self.assertEqual(entry["health"], "ok")

    def test_a_403_and_a_404_in_one_run_are_counted_separately(self):
        # The fixture session serves 403 for the three items it holds and 404
        # for the three it does not. A refusal and an absence are different
        # facts about a source and the ledger must not merge them.
        entry = self.run_once(session=FakeSession(article_status=403))
        self.assertEqual(entry["access_failures"], 3)
        self.assertEqual(entry["fetch_failures"], 3)
        self.assertEqual(entry["retrieved"], 0)
        self.assertEqual(entry["inserted"], 0)
        # A refusal outranks an absence when naming the run's outcome.
        self.assertEqual(entry["result"], st.AUTH_FAILURE)
        self.assertEqual(entry["health"], "fail")

    def test_the_ledger_records_a_failure_with_its_reason(self):
        self.run_once(session=FakeSession(feed_status=500))
        entry = json.loads(self.ledger()[0].read_text(encoding="utf-8"))
        self.assertEqual(entry["health"], "fail")
        self.assertTrue(entry["error_detail"])


class TestResultsAreDeterministic(RunnerCase):

    def test_two_independent_runs_produce_the_same_corpus(self):
        first = self.run_once(run_id="r1")
        rows_a = self.records()
        with tempfile.TemporaryDirectory() as other:
            state_b = Path(other) / "state"
            second = runner.run(state_b, TARGET, 7, 40, "r1", "commit",
                                adapter=make_adapter())
            con = sqlite3.connect(str(state_b / "shadow.db"))
            try:
                rows_b = con.execute(
                    "SELECT url, source_identity, title_original,"
                    " text_original, published_date FROM shadow_records"
                ).fetchall()
            finally:
                con.close()
        self.assertEqual(rows_a, rows_b)
        self.assertEqual(first["content_hashes"], second["content_hashes"])

    def test_the_content_hash_is_the_hash_of_the_stored_body(self):
        self.run_once()
        con = sqlite3.connect(str(self.state / "shadow.db"))
        try:
            rows = con.execute("SELECT text_original, content_sha256 "
                               "FROM shadow_records").fetchall()
        finally:
            con.close()
        for text, digest in rows:
            self.assertEqual(
                hashlib.sha256(text.encode("utf-8")).hexdigest(), digest)

    def test_publication_dates_and_their_utc_instants_are_both_preserved(self):
        self.run_once()
        con = sqlite3.connect(str(self.state / "shadow.db"))
        try:
            rows = con.execute(
                "SELECT published_date, published_at_utc,"
                " published_at_original FROM shadow_records").fetchall()
        finally:
            con.close()
        for local, utc, original in rows:
            self.assertRegex(local, r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(utc.endswith("+00:00"))
            self.assertIn("-0400", original)


if __name__ == "__main__":
    unittest.main()
