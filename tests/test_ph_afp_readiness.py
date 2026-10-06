"""Current-main AFP contracts; original payload replay and publication safety."""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import textwrap
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from core.collection import status as st
from core.collection.contract import CollectionWindow
from scraper.sources import ph_afp as ph
from scripts import check_ph_afp_state as checker, shadow_collect_ph as runner
from tests import ph_afp_support as S

FIX = S.FIX / "live_20261006"


class CapturedSession:
    def __init__(self):
        self.receipts = json.loads((FIX / "requests.json").read_text())
        self.routes = {r["url"]: r for r in self.receipts}
        self.calls = []

    def get(self, url, headers, timeout, allow_redirects):
        assert allow_redirects is False and headers["User-Agent"] == ph.USER_AGENT
        self.calls.append(url)
        receipt = self.routes[url]  # unknown requests fail; never fall through to network
        payload = (FIX / receipt["file"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == receipt["sha256"]
        return S.FakeResponse(payload, receipt["status"], {
            "Content-Type": receipt["content_type"],
            "X-Robots-Tag": receipt["x_robots_tag"] or ""}, url)


class StateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"

    def run_fixture(self, run_id="r1", sess=None, cap=0):
        adapter = S.adapter(sess or S.session_for(details_ids=(1384,)), cap=cap)
        return runner.run(self.state, date(2026, 9, 26), 4000, cap, run_id,
                          "testcommit", adapter=adapter, revision_days=4000)


class TestCapturedTraversal(StateCase):
    def test_original_1088_row_walk_reconciles_all_11_pages_without_network(self):
        sess = CapturedSession()
        adapter = ph.PHAfpAdapter(S.FakeSource(), session=sess, cap=100,
                                  sleeper=lambda _: None)
        result = adapter.discover(CollectionWindow(date(2026, 10, 6), 14))
        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(result.references), 11)
        self.assertEqual(adapter.observed["listed_items"], 1088)
        self.assertEqual(adapter.observed["api_reported_count"], 1088)
        self.assertEqual(adapter.observed["list_pages"], 11)
        self.assertEqual(adapter.observed["listing_end"], "next_null")
        self.assertFalse(adapter.observed["count_mismatch"])
        self.assertEqual(sess.calls, [r["url"] for r in sess.receipts[:13]])

    def test_captured_recent_bodies_store_exact_originals_and_survive_duplicate_run(self):
        for run_id in ("captured1", "captured2"):
            before = checker.snapshot(self.state)
            adapter = ph.PHAfpAdapter(S.FakeSource(), session=CapturedSession(), cap=100,
                                      sleeper=lambda _: None)
            entry = runner.run(self.state, date(2026, 10, 6), 1, 100, run_id,
                               "testcommit", adapter=adapter)
            self.assertEqual(entry["health"], "ok")
            self.assertEqual(entry["stored_total"], 2)
            checker.verify(self.state, before, run_id, "testcommit")
        self.assertEqual(entry["duplicates"], 2)
        with sqlite3.connect(self.state / "shadow.db") as conn:
            rows = conn.execute("SELECT source_identity, published_date, text_original FROM shadow_records").fetchall()
            self.assertEqual({r[0]: (r[1], len(r[2])) for r in rows}, {
                "afp:1396": ("2026-10-06", 1481), "afp:1395": ("2026-10-05", 1291)})
            originals = [r[0] for r in conn.execute("SELECT payload FROM captures")]
            self.assertCountEqual(originals, [(FIX / ("%02d.bin" % i)).read_bytes() for i in (14, 15)])


class TestPolicyReadiness(unittest.TestCase):
    def test_direct_requests_ignore_environment_and_session_proxies(self):
        session = ph.requests.Session()
        session.proxies = {"https": "http://proxy.invalid:8080"}
        adapter = ph.PHAfpAdapter(S.FakeSource(), session=session, sleeper=lambda _: None)
        with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://proxy.invalid:8080",
                                          "ALL_PROXY": "http://proxy.invalid:8080"}), \
                mock.patch.object(session, "send", return_value=S.FakeResponse(
                    "User-agent: *\nAllow: /\n", url=ph.ROBOTS_WWW)) as send:
            adapter._send_once(ph.ROBOTS_WWW)
        self.assertFalse(session.trust_env)
        self.assertEqual(send.call_args.kwargs["proxies"], {})
        self.assertEqual(send.call_args.args[0].headers["User-Agent"], ph.USER_AGENT)

    def test_reviewed_policy_and_indexing_signal_changes_stop_before_articles(self):
        for change in ("www", "api", "header"):
            sess = CapturedSession()
            original = sess.get
            def get(url, **kwargs):
                response = original(url, **kwargs)
                if change == "www" and url == ph.ROBOTS_WWW:
                    response = S.FakeResponse("User-agent: *\nAllow: /\n", url=url)
                if change == "api" and url == ph.ROBOTS_API:
                    response.status_code = 410
                if change == "header" and url == ph.ROBOTS_API:
                    response.headers["X-Robots-Tag"] = "noarchive"
                return response
            sess.get = get
            source = runner.load_source()
            source.enabled = True
            adapter = ph.PHAfpAdapter(source, session=sess, sleeper=lambda _: None)
            with self.subTest(change=change):
                result = adapter.discover(CollectionWindow(date(2026, 10, 6), 14))
                self.assertEqual(result.status, st.AUTH_FAILURE)
                self.assertLessEqual(len(sess.calls), 2)
                self.assertTrue(adapter.evidence)

    def test_malformed_oversized_nontext_and_invalid_utf8_policy_fail_closed(self):
        responses = [S.FakeResponse("maintenance", headers={"Content-Type": "text/plain"}),
                     S.FakeResponse("<html>maintenance</html>", headers={"Content-Type": "text/html"}),
                     S.FakeResponse(b"User-agent: *\n#\xff", headers={"Content-Type": "text/plain"}),
                     S.FakeResponse("User-agent: *\n#" + "x" * ph.MAX_POLICY_BYTES,
                                    headers={"Content-Type": "text/plain"})]
        for response in responses:
            with self.subTest(payload=response.content[:30]):
                sess = S.session_for(robots_www=response)
                adapter = S.adapter(sess)
                self.assertEqual(adapter.discover(CollectionWindow(date(2026, 9, 26), 4000)).status,
                                 st.AUTH_FAILURE)
                self.assertEqual(sess.calls, [ph.ROBOTS_WWW])
                self.assertTrue(adapter.evidence)

    def test_partial_agent_match_obeys_named_group_and_supported_crawl_delay(self):
        rules = "User-agent: *\nAllow: /\n\nUser-agent: IndoPacificRecord\nDisallow: /articles/\n"
        sess = S.session_for(robots_api=rules, robots_api_status=200)
        adapter = S.adapter(sess)
        self.assertEqual(adapter.discover(CollectionWindow(date(2026, 9, 26), 4000)).status,
                         st.AUTH_FAILURE)
        self.assertEqual(sess.calls, [ph.ROBOTS_WWW, ph.ROBOTS_API])
        adapter.assert_robots_allow("User-agent: *\nCrawl-delay: 7\n", ph.LIST_URL)
        self.assertEqual(adapter._request_interval, 7)
        with self.assertRaises(ph.RobotsDisallowed):
            adapter.assert_robots_allow("User-agent: *\nCrawl-delay: unknown\n", ph.LIST_URL)

    def test_supported_delay_actually_spaces_requests(self):
        class Clock:
            t = 100.0
            def sleep(self, delay): self.t += delay
        clock = Clock()
        sess = S.session_for(robots_www="User-agent: *\nCrawl-delay: 7\n")
        stamps = []
        original = sess.get
        def get(*args, **kwargs):
            stamps.append(clock.t)
            return original(*args, **kwargs)
        sess.get = get
        with mock.patch.object(ph.time, "monotonic", side_effect=lambda: clock.t):
            S.adapter(sess, sleeper=clock.sleep).discover(CollectionWindow(date(2026, 9, 26), 4000))
        self.assertGreaterEqual(stamps[-1] - stamps[-2], 7)


class TestRunnerReadiness(StateCase):
    def rehearsal(self, run_id="sample", sess=None, target=date(2026, 10, 6), **kwargs):
        source = runner.load_source()
        source.enabled = True
        adapter = ph.PHAfpAdapter(source, session=sess or CapturedSession(),
                                  cap=100, sleeper=lambda _: None)
        return runner.run(self.state, target, 14, 100, run_id, "testcommit",
                          adapter=adapter, rehearsal=True, **kwargs)

    def test_rehearsal_walks_all_pages_and_explicitly_samples_without_clock(self):
        before = checker.snapshot(self.state)
        sess = CapturedSession()
        entry = self.rehearsal(sess=sess)
        self.assertEqual(entry["health"], "ok")
        self.assertEqual(entry["observed"]["listed_items"], 1088)
        self.assertEqual(entry["observed"]["list_pages"], 11)
        self.assertEqual((entry["discovered"], entry["selected"], entry["sample_unselected"]),
                         (11, 2, 9))
        self.assertEqual(entry["retrieved"], 2)
        self.assertEqual(len(sess.calls), 15)
        self.assertFalse((self.state / "clock.json").exists())
        self.assertIsNone(entry["shadow_day"])
        checker.verify(self.state, before, "sample", "testcommit")

    def test_rehearsal_keeps_an_existing_clock_and_immutable_records(self):
        adapter = ph.PHAfpAdapter(S.FakeSource(), session=CapturedSession(),
                                  sleeper=lambda _: None)
        runner.run(self.state, date(2026, 10, 6), 1, 100, "normal", "testcommit", adapter=adapter)
        before = checker.snapshot(self.state)
        entry = self.rehearsal()
        self.assertEqual(entry["duplicates"], 2)
        self.assertIsNone(entry["shadow_day"])
        checker.verify(self.state, before, "sample", "testcommit")

    def test_empty_recent_sample_window_is_not_article_egress_success(self):
        before = checker.snapshot(self.state)
        entry = self.rehearsal(target=date(2026, 11, 1))
        self.assertEqual(entry["result"], st.LISTING_FAILURE)
        self.assertEqual(entry["health"], "fail")
        checker.verify(self.state, before, "sample", "testcommit")

    def test_missing_sample_is_partial_and_never_starts_clock(self):
        sess = CapturedSession()
        last_url = sess.receipts[-1]["url"]
        original = sess.get
        def get(url, **kwargs):
            if url == last_url:
                return S.FakeResponse("unavailable", status_code=500, url=url,
                    headers={"Content-Type": "text/plain", "X-Robots-Tag": "noindex, nofollow"})
            return original(url, **kwargs)
        sess.get = get
        before = checker.snapshot(self.state)
        entry = self.rehearsal(sess=sess)
        self.assertEqual(entry["health"], "partial")
        self.assertEqual(entry["retrieved"], 1)
        self.assertFalse((self.state / "clock.json").exists())
        checker.verify(self.state, before, "sample", "testcommit")

    def test_rehearsal_cannot_expand_to_archive_or_run_as_cron(self):
        for limit in (0, 3):
            with self.assertRaises(ValueError): self.rehearsal(sample_limit=limit)
        with self.assertRaises(ValueError):
            runner.run(self.state, date(2026, 10, 6), 15, 100, "bad", "testcommit",
                       rehearsal=True)
        self.assertEqual(runner.main(["--state-dir", str(self.state), "--rehearsal",
                                      "--event-name", "schedule"]), 2)
        self.assertFalse(self.state.exists())

    def test_manual_cli_can_probe_disabled_source_but_does_not_enable_manifest(self):
        adapter = ph.PHAfpAdapter(S.FakeSource(), session=CapturedSession(),
                                  sleeper=lambda _: None)
        with mock.patch.object(runner, "PHAfpAdapter", return_value=adapter) as factory:
            self.assertEqual(runner.main(["--state-dir", str(self.state), "--rehearsal",
                "--event-name", "workflow_dispatch", "--target-date", "2026-10-06",
                "--run-id", "sample"]), 0)
        self.assertTrue(factory.call_args.args[0].enabled)
        self.assertFalse(runner.load_source().enabled)
        self.assertFalse((self.state / "clock.json").exists())

    def test_disabled_cli_makes_no_request_and_creates_no_state(self):
        with mock.patch.object(runner, "PHAfpAdapter") as adapter:
            self.assertEqual(runner.main(["--state-dir", str(self.state),
                                          "--target-date", "2026-10-06"]), 2)
        adapter.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_cap_overflow_retains_listing_evidence_but_no_clock_or_article(self):
        sess = S.session_for(details_ids=(1384, 1378))
        before = checker.snapshot(self.state)
        entry = self.run_fixture(sess=sess, cap=1)
        self.assertEqual(entry["result"], st.LISTING_FAILURE)
        self.assertIsNone(entry["shadow_day"])
        self.assertFalse((self.state / "shadow.db").exists())
        self.assertEqual(len(sess.calls), 3)
        checker.verify(self.state, before, "r1", "testcommit")

    def test_duplicate_attempt_id_is_refused_before_mutation_or_request(self):
        self.run_fixture()
        before = checker.snapshot(self.state)
        sess = S.session_for()
        with self.assertRaises(ValueError): self.run_fixture(sess=sess)
        self.assertEqual(checker.snapshot(self.state), before)
        self.assertEqual(sess.calls, [])

    def test_malformed_metadata_fails_even_an_apparently_quiet_window(self):
        for field, value, reason in (("published_at", None, ph.R_MISSING_PUBDATE),
                                      ("id", "²", ph.R_MISSING_ID)):
            with self.subTest(field=field):
                sess = S.session_for(details_ids=(1384,))
                entries = S.real_list_from_details((1384,))
                entries[0][field] = value
                sess.pages[S.page_url(1)] = S.list_page(entries)
                entry = self.run_fixture(sess=sess, run_id=field)
                self.assertEqual(entry["result"], st.LISTING_FAILURE)
                self.assertEqual(entry["rejections"][reason], 1)
                self.assertEqual(len(sess.calls), 3)
                self.assertFalse((self.state / "clock.json").exists())

    def test_article_policy_refusal_is_reflected_in_final_ledger(self):
        slug = S.detail_obj(1384)["slug"]
        sess = S.session_for(details_ids=(1384,), robots_api_status=200,
                             robots_api="User-agent: *\nDisallow: /articles/" + slug + "/\n")
        entry = self.run_fixture(sess=sess)
        self.assertEqual(entry["robots_status"], "disallowed")
        self.assertEqual(entry["result"], st.AUTH_FAILURE)
        self.assertEqual(entry["health"], "fail")

    def test_symlink_in_state_and_unsafe_attempt_id_are_refused(self):
        self.state.mkdir()
        (self.state / "shadow.db").symlink_to(Path(self.tmp.name) / "elsewhere")
        with self.assertRaises(ValueError): self.run_fixture()
        (self.state / "shadow.db").unlink()
        for run_id in ("../escape", "with space"):
            with self.assertRaises(ValueError): self.run_fixture(run_id=run_id)
        self.assertEqual(list(self.state.iterdir()), [])


class TestStatePublisher(StateCase):
    def test_completed_failure_publishes_new_evidence_without_rewriting_history(self):
        self.run_fixture()
        before = checker.snapshot(self.state)
        self.run_fixture(run_id="failed", sess=S.FakeSession())
        entry = checker.verify(self.state, before, "failed", "testcommit")
        self.assertEqual(entry["health"], "fail")

    def test_changed_or_deleted_history_and_sql_rows_block_publication(self):
        for target in ("ledger", "clock", "evidence", "row"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                self.state = Path(tmp) / "state"
                self.run_fixture()
                before = checker.snapshot(self.state)
                self.run_fixture(run_id="next")
                if target == "row":
                    with sqlite3.connect(self.state / "shadow.db") as conn:
                        conn.execute("UPDATE shadow_records SET title_original='derived mutation'")
                else:
                    name = next(n for n in before["files"] if n.startswith(target))
                    (self.state / name).unlink()
                with self.assertRaises(ValueError):
                    checker.verify(self.state, before, "next", "testcommit")

    def test_crash_wrong_provenance_sidecar_and_changed_payload_block_publication(self):
        before = checker.snapshot(self.state)
        with self.assertRaises(ValueError): checker.verify(self.state, before, "r1", "testcommit")
        self.run_fixture()
        with self.assertRaises(ValueError): checker.verify(self.state, before, "r1", "wrong")
        sidecar = self.state / "shadow.db-wal"
        sidecar.write_bytes(b"derived sidecar")
        with self.assertRaises(ValueError): checker.verify(self.state, before, "r1", "testcommit")
        sidecar.unlink()
        payload = next((self.state / "evidence" / "payloads").glob("*.bin"))
        payload.write_bytes(b"derived corruption")
        with self.assertRaises(ValueError): checker.verify(self.state, before, "r1", "testcommit")


class TestPreparedWorkflow(unittest.TestCase):
    def test_workflow_is_manual_unscheduled_isolated_and_keeps_job_failed(self):
        text = (S.REPO_ROOT / ".github/workflows/ph_afp_shadow.yml").read_text()
        self.assertIn("    if: github.event_name == 'workflow_dispatch'", text)
        self.assertIn("--rehearsal --sample-limit 2", text)
        self.assertIn("if: success() && inputs.publish_state", text)
        self.assertIn("default: false", text)
        self.assertNotRegex(text, r"(?m)^  schedule:|^\s+- cron:")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("continue-on-error: true", text)
        self.assertIn("scripts/check_ph_afp_state.py verify", text)
        self.assertIn("steps.collect.outcome == 'failure'", text)
        self.assertIn("HEAD:refs/heads/shadow/ph-afp", text)
        self.assertNotIn("--force", text)
        self.assertNotIn("site/render.py", text)
        self.assertIn('elif [ "$status" -eq 2 ]', text)

    def test_all_prepared_shell_blocks_parse(self):
        text = (S.REPO_ROOT / ".github/workflows/ph_afp_shadow.yml").read_text()
        blocks = re.findall(r"        run: \|\n((?:          .*\n|\n)+)", text)
        self.assertEqual(len(blocks), text.count("run: |"))
        self.assertTrue(blocks)
        for block in blocks:
            result = subprocess.run(["bash", "-n"], input=textwrap.dedent(block), text=True,
                                    capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_actual_publish_block_uses_only_state_ref_and_rejects_a_divergent_writer(self):
        # Local bare remote only. Exercise the exact prepared shell block,
        # rather than inferring push safety from a substring assertion.
        text = (S.REPO_ROOT / ".github/workflows/ph_afp_shadow.yml").read_text()
        block = next(textwrap.dedent(b) for b in re.findall(
            r"        run: \|\n((?:          .*\n|\n)+)", text) if "git push" in b)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            state_repo = root / "shadow-state"
            collector = root / "workspace" / "repo"
            collector.mkdir(parents=True)
            def git(*args):
                return subprocess.check_output(["git", *map(str, args)], stderr=subprocess.STDOUT,
                                               text=True).strip()
            git("init", "--bare", remote)
            git("init", collector)
            (collector / "proof.txt").write_text("local fixture collector\n")
            git("-C", collector, "add", "proof.txt")
            git("-C", collector, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                "commit", "-m", "fixture collector")
            commit = git("-C", collector, "rev-parse", "HEAD")
            git("init", state_repo)
            git("-C", state_repo, "checkout", "--orphan", "shadow/ph-afp")
            git("-C", state_repo, "remote", "add", "origin", remote)
            state = state_repo / "state"
            env = dict(os.environ, RUNNER_TEMP=str(root), GITHUB_WORKSPACE=str(root / "workspace"),
                       GITHUB_RUN_ID="fixture", GITHUB_RUN_ATTEMPT="1")
            def collect(run_id):
                before = checker.snapshot(state)
                runner.run(state, date(2026, 9, 26), 4000, 0, run_id, commit,
                           adapter=S.adapter(S.session_for(details_ids=(1384,))))
                checker.verify(state, before, run_id, commit)
            collect("fixture-1")
            result = subprocess.run(["bash", "-c", block], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(git("--git-dir", remote, "for-each-ref", "--format=%(refname)", "refs/heads"),
                             "refs/heads/shadow/ph-afp")
            other = root / "competing"
            git("clone", "--branch", "shadow/ph-afp", remote, other)
            (other / "state" / "competing.json").write_text("{}\n")
            git("-C", other, "add", "state")
            git("-C", other, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                "commit", "-m", "divergent fixture writer")
            git("-C", other, "push", "origin", "HEAD:refs/heads/shadow/ph-afp")
            competing_head = git("--git-dir", remote, "rev-parse", "refs/heads/shadow/ph-afp")
            collect("fixture-2")
            env["GITHUB_RUN_ATTEMPT"] = "2"
            result = subprocess.run(["bash", "-c", block], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("rejected", result.stderr)
            self.assertEqual(git("--git-dir", remote, "rev-parse", "refs/heads/shadow/ph-afp"), competing_head)
