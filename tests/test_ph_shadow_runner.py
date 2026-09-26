"""
Philippines (AFP) shadow runner: isolation, preservation, dedup, revisions,
failure handling.

Every run here uses a temporary state directory OUTSIDE the repository and a
fake session serving saved responses. No network, no tracked-database access.
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

from core.collection import status as st                         # noqa: E402
from core.manifests import load_all_desks                        # noqa: E402
from scraper.sources import ph_afp as ph                          # noqa: E402
from scripts import shadow_collect_ph as runner                   # noqa: E402
from tests import ph_afp_support as S                             # noqa: E402

TARGET = date(2026, 9, 26)
PRESS_IDS = (1384, 1378, 1312, 1211, 1331, 1330, 1365, 834)


def do_run(state, sess, lookback=4000, cap=0, run_id="r1", adapter=None,
           revision_days=4000):
    """`revision_days` defaults wide so a repeat run re-reads every held item;
    the tests of the held-item skip pass a narrow one explicitly."""
    a = adapter or S.adapter(sess, cap=cap)
    return runner.run(state, TARGET, lookback, cap, run_id, "testcommit",
                      adapter=a, revision_days=revision_days)


def detail_calls(sess):
    return [c for c in sess.calls if "/articles/" in c and "?" not in c
            and "robots" not in c]


def tree_fingerprint(root: Path):
    """File count, total bytes and newest mtime: cheap and change-sensitive."""
    count = size = newest = 0
    for path in root.rglob("*"):
        if path.is_file():
            stat = path.stat()
            count += 1
            size += stat.st_size
            newest = max(newest, stat.st_mtime_ns)
    return count, size, newest


class StateCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = Path(self._tmp.name) / "state"

    def db(self):
        return sqlite3.connect(str(self.state / "shadow.db"))

    def rows(self, sql, *args):
        conn = self.db()
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def ledgers(self):
        return sorted((self.state / "ledger").glob("*.json"))


class TestIsolation(StateCase):

    def test_a_state_directory_inside_the_repository_is_refused(self):
        inside = REPO_ROOT / "tmp_ph_state_should_never_exist"
        with self.assertRaises(SystemExit):
            runner.run(inside, TARGET, 0, 1, "r", "c",
                       adapter=S.adapter(S.session_for()))
        self.assertFalse(inside.exists())

    def test_the_repository_root_itself_is_refused(self):
        with self.assertRaises(SystemExit):
            runner.assert_isolated(REPO_ROOT)

    def test_the_cli_refuses_a_state_directory_inside_the_repository(self):
        with self.assertRaises(SystemExit):
            runner.main(["--state-dir", str(REPO_ROOT / "tmp_ph_state_x"),
                         "--target-date", "2026-09-26"])

    def test_a_scheduled_event_without_a_cron_time_is_refused_before_any_request(self):
        rc = runner.main(["--state-dir", str(self.state),
                          "--event-name", "schedule"])
        self.assertEqual(rc, 2)
        self.assertFalse(self.state.exists())

    def test_the_runner_names_no_production_path_in_code(self):
        source = (REPO_ROOT / "scripts" / "shadow_collect_ph.py").read_text(
            encoding="utf-8")
        body = source.split('"""', 2)[2]     # the docstring may say what it avoids
        self.assertNotIn("pla_watch.db", body)
        self.assertNotIn("output/", body)
        self.assertNotIn("import storage", body)

    def test_a_full_run_leaves_the_tracked_database_and_output_untouched(self):
        db = REPO_ROOT / "pla_watch.db"
        before_db = hashlib.sha256(db.read_bytes()).hexdigest()
        before_out = tree_fingerprint(REPO_ROOT / "output")
        do_run(self.state, S.session_for(details_ids=PRESS_IDS))
        self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(), before_db)
        self.assertEqual(tree_fingerprint(REPO_ROOT / "output"), before_out)
        self.assertFalse((REPO_ROOT / "pla_watch.db-wal").exists())

    def test_the_manifest_is_not_discoverable_as_a_production_desk(self):
        self.assertEqual(sorted(load_all_desks()), ["china", "singapore"])
        self.assertTrue((REPO_ROOT / "shadow" / "ph_afp" / "manifest.json").is_file())
        self.assertFalse((REPO_ROOT / "desks" / "philippines").exists())

    def test_no_declared_desk_or_pipeline_or_workflow_reaches_the_pilot(self):
        for rel in ("pipeline.py", "desks/registry.json", "core/registry.py"):
            with self.subTest(file=rel):
                text = (REPO_ROOT / rel).read_text(encoding="utf-8")
                self.assertNotIn("ph_afp", text)
                self.assertNotIn("shadow_collect_ph", text)
        for path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
            with self.subTest(file=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("shadow_collect_ph", text)
                self.assertNotIn("ph_afp", text)

    def test_the_source_is_disabled_in_the_manifest_and_in_the_loaded_source(self):
        self.assertFalse(runner.load_source().enabled)


class TestFirstRun(StateCase):

    def setUp(self):
        super().setUp()
        self.sess = S.session_for(details_ids=PRESS_IDS)
        self.entry = do_run(self.state, self.sess)

    def test_every_press_item_is_stored(self):
        self.assertEqual(self.entry["result"], st.OK)
        self.assertEqual(self.entry["health"], "ok")
        self.assertEqual(self.entry["inserted"], 8)
        self.assertEqual(self.entry["stored_total"], 8)
        self.assertEqual(self.entry["retrieved"], 8)
        self.assertEqual(self.entry["duplicates"], 0)

    def test_the_date_range_captured_is_reported_from_the_stored_records(self):
        self.assertEqual(self.entry["corpus_range"], ["2022-04-18", "2026-09-15"])

    def test_metadata_only_records_are_stored_and_counted_apart(self):
        # 1331, 1330, 1365, 834 carry no text in the payload
        self.assertEqual(self.entry["inserted_no_text"], 4)
        self.assertEqual(self.entry["stored_with_text"], 4)
        rows = self.rows("SELECT text_original, text_status FROM shadow_records"
                         " WHERE source_identity = 'afp:1331'")
        self.assertEqual(rows, [("", "no_text")])

    def test_the_original_payload_is_preserved_byte_for_byte(self):
        slug = S.detail_obj(1384)["slug"]
        served = self.sess.details[slug]
        rows = self.rows("SELECT payload, payload_sha256, requested_url,"
                         " final_url, http_status FROM captures"
                         " WHERE source_identity = 'afp:1384'")
        self.assertEqual(len(rows), 1)
        payload, sha, requested, final, status = rows[0]
        self.assertEqual(bytes(payload), served)
        self.assertEqual(sha, hashlib.sha256(served).hexdigest())
        self.assertEqual(requested, "https://api.afp.mil.ph/articles/%s/" % slug)
        self.assertEqual(final, requested)
        self.assertEqual(status, 200)

    def test_the_record_carries_the_source_url_and_its_capture_hash(self):
        slug = S.detail_obj(1384)["slug"]
        url, cap_sha = self.rows(
            "SELECT url, capture_sha256 FROM shadow_records"
            " WHERE source_identity = 'afp:1384'")[0]
        self.assertEqual(url, "https://www.afp.mil.ph/news/%s" % slug)
        stored = self.rows("SELECT payload_sha256 FROM captures"
                           " WHERE source_identity = 'afp:1384'")[0][0]
        self.assertEqual(cap_sha, stored)

    def test_the_stated_offset_and_the_utc_instant_are_both_stored(self):
        row = self.rows("SELECT published_date, published_at_original,"
                        " published_at_utc FROM shadow_records"
                        " WHERE source_identity = 'afp:834'")[0]
        self.assertEqual(row, ("2023-04-22", "2023-04-22T06:08:33+08:00",
                               "2023-04-21T22:08:33+00:00"))

    def test_the_ledger_records_the_policy_the_run_observed(self):
        obs = self.entry["observed"]
        self.assertEqual(obs["api_robots_status"], 404)
        self.assertEqual(obs["www_robots_status"], 200)
        self.assertEqual(obs["api_x_robots_tag"], "noindex, nofollow")
        self.assertEqual(self.entry["robots_status"], "allowed")

    def test_the_api_total_is_recorded_beside_what_was_captured_not_instead_of_it(self):
        obs = self.entry["observed"]
        self.assertEqual(obs["listed_items"], 8)
        self.assertEqual(self.entry["stored_total"], 8)
        self.assertIn("api_reported_count", obs)

    def test_a_ledger_is_written_and_the_clock_starts(self):
        self.assertEqual(len(self.ledgers()), 1)
        clock = json.loads((self.state / "clock.json").read_text())
        self.assertEqual(clock["day_zero_run_id"], "r1")
        self.assertEqual(self.entry["shadow_day"], 0)

    def test_state_hashes_bracket_the_run(self):
        self.assertIsNone(self.entry["state_sha256_before"])
        self.assertIsNotNone(self.entry["state_sha256_after"])

    def test_the_ledger_carries_hashes_only_for_records_that_have_text(self):
        self.assertEqual(len(self.entry["content_hashes"]), 4)
        empty = hashlib.sha256(b"").hexdigest()
        self.assertNotIn(empty, self.entry["content_hashes"])

    def test_two_ids_with_identical_text_are_reported_and_not_merged(self):
        # 1330 and 1331 are the same statement twice; both are image-only, so
        # they carry no text to hash and are NOT counted as shared-text groups.
        self.assertEqual(self.entry["content_hash_shared_groups"], 0)
        self.assertEqual(self.rows(
            "SELECT COUNT(*) FROM shadow_records WHERE title_original LIKE"
            " 'AFP Statement on Misleading%'")[0][0], 2)


class TestDeduplication(StateCase):

    def test_a_second_identical_run_adds_nothing(self):
        sess = S.session_for(details_ids=PRESS_IDS)
        do_run(self.state, sess, run_id="r1")
        captures_before = self.rows("SELECT COUNT(*) FROM captures")[0][0]
        e2 = do_run(self.state, sess, run_id="r2")
        self.assertEqual(e2["inserted"], 0)
        self.assertEqual(e2["duplicates"], 8)
        self.assertEqual(e2["result"], st.OK_ALL_DUPLICATES)
        self.assertEqual(e2["stored_total"], 8)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM captures")[0][0],
                         captures_before)
        self.assertEqual(len(self.ledgers()), 2)

    def test_held_items_older_than_the_watch_window_are_not_requested_again(self):
        sess = S.session_for(details_ids=PRESS_IDS)
        do_run(self.state, sess, run_id="r1")
        before = len(detail_calls(sess))
        e2 = do_run(self.state, sess, run_id="r2", revision_days=14)
        # 1384 (2026-09-15) and 1378 (2026-09-14) are inside 14 days of the
        # target and are re-read; the other six are held and old, so untouched
        self.assertEqual(e2["skipped_held"], 6)
        self.assertEqual(e2["duplicates"], 2)
        self.assertEqual(len(detail_calls(sess)) - before, 2)
        self.assertEqual(e2["result"], st.OK_ALL_DUPLICATES)
        self.assertEqual(e2["health"], "ok")

    def test_a_retry_fetches_only_what_is_missing(self):
        sess = S.session_for(details_ids=PRESS_IDS)
        missing_slug = S.detail_obj(1211)["slug"]
        held_back = sess.details.pop(missing_slug)
        e1 = do_run(self.state, sess, run_id="r1")
        self.assertEqual(e1["health"], "partial")
        self.assertEqual(e1["inserted"], 7)
        sess.details[missing_slug] = held_back
        before = len(detail_calls(sess))
        e2 = do_run(self.state, sess, run_id="r2", revision_days=0)
        self.assertEqual(e2["inserted"], 1)
        self.assertEqual(e2["skipped_held"], 7)
        self.assertEqual(len(detail_calls(sess)) - before, 1)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM shadow_records")[0][0], 8)
        self.assertEqual(e2["health"], "ok")

    def test_the_first_seen_run_is_never_rewritten(self):
        sess = S.session_for(details_ids=PRESS_IDS)
        do_run(self.state, sess, run_id="r1")
        do_run(self.state, sess, run_id="r2")
        runs = {r[0] for r in self.rows(
            "SELECT DISTINCT first_seen_run FROM shadow_records")}
        self.assertEqual(runs, {"r1"})

    def test_a_view_counter_change_alone_is_not_a_revision(self):
        do_run(self.state, S.session_for(details_ids=PRESS_IDS), run_id="r1")

        def bump(d):
            d["hits"] = d["hits"] + 9999
        e2 = do_run(self.state, S.session_for(details_ids=PRESS_IDS,
                                              mutate=bump), run_id="r2")
        self.assertEqual(e2["revisions"], 0)
        self.assertEqual(e2["duplicates"], 8)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM revisions")[0][0], 0)

    def test_a_url_already_held_under_another_identity_is_a_collision_not_a_duplicate(self):
        do_run(self.state, S.session_for(details_ids=(1384,)), run_id="r1")

        def reassign(d):
            d["id"] = 9999
        sess = S.session_for(details_ids=(1384,), mutate=reassign)
        # the listing still says 1384, so the detail is an identity mismatch
        e2 = do_run(self.state, sess, run_id="r2")
        self.assertEqual(e2["extraction_failures"], 1)
        self.assertEqual(e2["rejections"][ph.R_IDENTITY_MISMATCH], 1)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM shadow_records")[0][0], 1)

    def test_a_slug_reused_by_a_new_id_is_recorded_as_a_collision(self):
        do_run(self.state, S.session_for(details_ids=(1384,)), run_id="r1")

        def new_id_same_slug(d):
            d["id"] = 5000
        sess = S.session_for(details_ids=(1384,))
        # rewrite BOTH listing and detail to the new id, keeping the slug
        slug = S.detail_obj(1384)["slug"]
        entry = S.list_entry(S.detail_obj(1384))
        entry["id"] = 5000
        sess.pages[S.page_url(1)] = S.list_page([entry])
        d = S.detail_obj(1384)
        new_id_same_slug(d)
        sess.details[slug] = json.dumps(d).encode("utf-8")
        e2 = do_run(self.state, sess, run_id="r2")
        self.assertEqual(e2["identity_collisions"], 1)
        self.assertEqual(e2["inserted"], 0)
        self.assertEqual(e2["health"], "partial")
        ident = self.rows("SELECT source_identity FROM shadow_records")[0][0]
        self.assertEqual(ident, "afp:1384")     # the held record is untouched


class TestRevisions(StateCase):

    def revise(self, d):
        d["body_html"] = d["body_html"] + "<p>CORRECTION: figure amended.</p>"

    def test_a_changed_article_is_a_revision_and_the_original_is_preserved(self):
        s1 = S.session_for(details_ids=(1384,))
        do_run(self.state, s1, run_id="r1")
        original = self.rows("SELECT text_original, source_fingerprint"
                             " FROM shadow_records")[0]
        e2 = do_run(self.state, S.session_for(details_ids=(1384,),
                                              mutate=self.revise), run_id="r2")
        self.assertEqual(e2["revisions"], 1)
        self.assertEqual(e2["inserted"], 0)
        self.assertEqual(e2["duplicates"], 0)
        self.assertEqual(e2["result"], st.OK)
        # the first-seen record is exactly what it was
        self.assertEqual(self.rows("SELECT text_original, source_fingerprint"
                                   " FROM shadow_records")[0], original)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM shadow_records")[0][0], 1)
        # both payloads survive
        caps = self.rows("SELECT capture_id, source_fingerprint, payload"
                         " FROM captures ORDER BY capture_id")
        self.assertEqual(len(caps), 2)
        self.assertNotEqual(caps[0][1], caps[1][1])
        self.assertNotIn("CORRECTION", bytes(caps[0][2]).decode("utf-8"))
        self.assertIn("CORRECTION", bytes(caps[1][2]).decode("utf-8"))

    def test_the_revision_row_links_the_two_captures(self):
        do_run(self.state, S.session_for(details_ids=(1384,)), run_id="r1")
        do_run(self.state, S.session_for(details_ids=(1384,),
                                         mutate=self.revise), run_id="r2")
        rev = self.rows("SELECT source_identity, run_id, prior_fingerprint,"
                        " new_fingerprint, prior_capture_id, new_capture_id"
                        " FROM revisions")
        self.assertEqual(len(rev), 1)
        ident, run_id, prior, new, pc, nc = rev[0]
        self.assertEqual((ident, run_id, pc, nc), ("afp:1384", "r2", 1, 2))
        self.assertNotEqual(prior, new)

    def test_a_revision_seen_twice_is_recorded_once(self):
        do_run(self.state, S.session_for(details_ids=(1384,)), run_id="r1")
        revised = S.session_for(details_ids=(1384,), mutate=self.revise)
        do_run(self.state, revised, run_id="r2")
        e3 = do_run(self.state, revised, run_id="r3")
        self.assertEqual(e3["revisions"], 0)
        self.assertEqual(e3["duplicates"], 1)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM revisions")[0][0], 1)

    def test_an_edited_slug_is_a_revision_and_the_new_url_is_preserved(self):
        do_run(self.state, S.session_for(details_ids=(1384,)), run_id="r1")
        old_slug = S.detail_obj(1384)["slug"]
        new_slug = old_slug + "-corrected"
        d = S.detail_obj(1384)
        d["slug"] = new_slug
        entry = S.list_entry(d)
        sess = S.FakeSession(
            pages={S.page_url(1): S.list_page([entry])},
            details={new_slug: json.dumps(d).encode("utf-8")})
        e2 = do_run(self.state, sess, run_id="r2")
        # same id, so it is not a second record; different slug, so it is not
        # a silent duplicate either
        self.assertEqual(e2["inserted"], 0)
        self.assertEqual(e2["revisions"], 1)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM shadow_records")[0][0], 1)
        urls = [r[0] for r in self.rows(
            "SELECT requested_url FROM captures ORDER BY capture_id")]
        self.assertTrue(urls[0].endswith("/%s/" % old_slug))
        self.assertTrue(urls[1].endswith("/%s/" % new_slug))

    def test_a_retitled_article_is_a_revision(self):
        do_run(self.state, S.session_for(details_ids=(1384,)), run_id="r1")
        e2 = do_run(self.state, S.session_for(
            details_ids=(1384,), mutate=lambda d: d.update(title="Retitled")),
            run_id="r2")
        self.assertEqual(e2["revisions"], 1)


class TestFailureHandling(StateCase):

    def test_a_listing_failure_is_a_failed_run_and_writes_no_records(self):
        e = do_run(self.state, S.FakeSession())
        self.assertEqual(e["result"], st.LISTING_FAILURE)
        self.assertEqual(e["health"], "fail")
        self.assertEqual(e["stored_total"] if "stored_total" in e else 0, 0)
        self.assertFalse((self.state / "shadow.db").exists())
        self.assertFalse((self.state / "clock.json").exists())
        self.assertIsNone(e["shadow_day"])
        self.assertEqual(len(self.ledgers()), 1)

    def test_a_disallow_is_recorded_as_a_refusal_not_an_outage(self):
        e = do_run(self.state, S.session_for(robots_api_status=200,
                                             robots_api=S.ROBOTS_DENY_ARTICLES))
        self.assertEqual(e["result"], st.AUTH_FAILURE)
        self.assertEqual(e["robots_status"], "disallowed")
        self.assertEqual(e["health"], "fail")

    def test_a_challenge_on_the_listing_is_recorded_and_the_run_stops(self):
        sess = S.FakeSession(pages={S.page_url(1): S.FakeResponse(
            S.CHALLENGE_HTML, 200, {"Content-Type": "text/html"})})
        e = do_run(self.state, sess)
        self.assertEqual(e["result"], st.ACCESS_CHALLENGED)
        self.assertEqual(e["health"], "fail")
        self.assertEqual(e["robots_status"], "disallowed")

    def test_a_failed_run_does_not_advance_an_existing_clock(self):
        do_run(self.state, S.session_for(details_ids=(1384,)), run_id="r1")
        e2 = do_run(self.state, S.FakeSession(), run_id="r2")
        self.assertIsNone(e2["shadow_day"])
        self.assertEqual(e2["day_zero_utc"],
                         json.loads((self.state / "clock.json").read_text())
                         ["day_zero_utc"])

    def test_a_refused_item_stops_the_run_instead_of_asking_again(self):
        sess = S.session_for(details_ids=PRESS_IDS)
        first_slug = S.detail_obj(1384)["slug"]      # newest, fetched first
        sess.details[first_slug] = S.FakeResponse(
            b"no", 403, {"Content-Type": "text/plain"})
        e = do_run(self.state, sess)
        self.assertEqual(e["result"], st.AUTH_FAILURE)
        self.assertEqual(e["aborted"], "access_refused")
        self.assertEqual(e["health"], "fail")
        detail_calls = [c for c in sess.calls if "/articles/" in c
                        and "?" not in c and "robots" not in c]
        self.assertEqual(len(detail_calls), 1)

    def test_consecutive_unretrievable_items_stop_the_run(self):
        sess = S.session_for(details_ids=PRESS_IDS)
        sess.details.clear()                          # every detail is a 404
        e = do_run(self.state, sess)
        self.assertEqual(e["aborted"], "consecutive_failures")
        self.assertEqual(e["result"], st.FETCH_FAILURE)
        self.assertEqual(e["fetch_failures"], runner.MAX_CONSECUTIVE_FAILURES)
        detail_calls = [c for c in sess.calls if "/articles/" in c
                        and "?" not in c and "robots" not in c]
        self.assertEqual(len(detail_calls), runner.MAX_CONSECUTIVE_FAILURES)

    def test_scattered_failures_alongside_successes_are_partial_not_failed(self):
        sess = S.session_for(details_ids=PRESS_IDS)
        del sess.details[S.detail_obj(1378)["slug"]]
        e = do_run(self.state, sess)
        self.assertEqual(e["result"], st.OK)
        self.assertEqual(e["health"], "partial")
        self.assertEqual(e["fetch_failures"], 1)
        self.assertEqual(e["inserted"], 7)
        self.assertIn("1 fetch failure", e["error_detail"])
        # the ledger names the item that failed and why, not just a count
        self.assertEqual(len(e["failure_log"]), 1)
        logged = e["failure_log"][0]
        self.assertEqual(logged["url"], ph.canonical_url(
            S.detail_obj(1378)["slug"]))
        self.assertEqual(logged["status"], st.FETCH_FAILURE)
        self.assertEqual(logged["http_status"], 404)

    def test_an_extraction_failure_is_counted_apart_from_a_fetch_failure(self):
        def drift(d):
            if d["id"] == 1378:
                d.pop("body_html")
        e = do_run(self.state, S.session_for(details_ids=PRESS_IDS, mutate=drift))
        self.assertEqual(e["extraction_failures"], 1)
        self.assertEqual(e["failure_log"][0]["status"], st.EXTRACTION_FAILURE)
        self.assertIn("body_html", e["failure_log"][0]["detail"])
        self.assertEqual(e["fetch_failures"], 0)
        self.assertEqual(e["inserted"], 7)
        self.assertEqual(e["health"], "partial")

    def test_every_item_failing_extraction_is_a_failed_run(self):
        def drift(d):
            d.pop("body_html")
        e = do_run(self.state, S.session_for(details_ids=(1384, 1378),
                                             mutate=drift))
        self.assertEqual(e["result"], st.EXTRACTION_FAILURE)
        self.assertEqual(e["health"], "fail")

    def test_an_off_host_redirect_on_every_item_is_a_failed_run(self):
        sess = S.session_for(details_ids=(1384, 1378),
                             final_url="https://evil.test/articles/x/")
        e = do_run(self.state, sess)
        self.assertEqual(e["result"], st.DISALLOWED_REDIRECT)
        self.assertEqual(e["redirect_refusals"], 2)
        self.assertEqual(e["health"], "fail")

    def test_an_empty_window_is_a_successful_run(self):
        e = do_run(self.state, S.session_for(details_ids=(1384,)),
                   lookback=0)
        self.assertEqual(e["result"], st.OK_NO_PUBLICATIONS)
        self.assertEqual(e["health"], "ok")
        self.assertEqual(e["rejections"][ph.R_OUTSIDE_WINDOW], 1)

    def test_a_transport_error_on_every_item_is_a_run_status_not_a_crash(self):
        sess = S.session_for(details_ids=PRESS_IDS)
        sess.raise_on = {"/articles/": S.Boom}
        # listing pages also contain "/articles/", so scope to detail routes
        sess.raise_on = {}
        for i in PRESS_IDS:
            sess.raise_on["/articles/%s/" % S.detail_obj(i)["slug"]] = S.Boom
        e = do_run(self.state, sess)
        self.assertEqual(e["health"], "fail")
        self.assertEqual(e["aborted"], "consecutive_failures")


class TestCli(StateCase):

    def test_the_exit_code_follows_health(self):
        # main() builds its own adapter, so drive the mapping through a stub.
        original = runner.PHAfpAdapter
        try:
            runner.PHAfpAdapter = lambda src, cap=100: S.adapter(
                S.session_for(details_ids=(1384,)), cap=cap)
            rc = runner.main(["--state-dir", str(self.state),
                              "--target-date", "2026-09-26",
                              "--lookback-days", "4000", "--cap", "0"])
            self.assertEqual(rc, 0)
            runner.PHAfpAdapter = lambda src, cap=100: S.adapter(
                S.FakeSession(), cap=cap)
            rc = runner.main(["--state-dir", str(self.state),
                              "--target-date", "2026-09-27",
                              "--lookback-days", "4000", "--cap", "0"])
            self.assertEqual(rc, 1)
        finally:
            runner.PHAfpAdapter = original


if __name__ == "__main__":
    unittest.main()
