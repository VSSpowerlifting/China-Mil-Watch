"""Offline NSC runner, provenance, isolation and state-branch rehearsals."""
import ast
import hashlib
import io
import json
import os
import re
import socket
import sqlite3
import subprocess
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from core.collection import status as st
from scripts import shadow_collect_ph_nsc as runner
from tests.test_ph_nsc_adapter import (
    ARTICLE_URL, ARTICLE_BIN, CHALLENGE, FakeResponse, Rig, TARGET, routes)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ph_nsc_shadow.yml"
RAW = WORKFLOW.read_text()


def step(name):
    match = re.search(r"^      - name: " + re.escape(name) + r"\n(.*?)(?=^      - name: |\Z)",
                      RAW, re.M | re.S)
    return match.group(1)


def shell(name):
    return textwrap.dedent(step(name).split("run: |\n", 1)[1])


class RunnerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"
        guard = mock.patch.object(socket.socket, "connect",
                                  side_effect=AssertionError("real network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)

    def go(self, rig=None, target=TARGET, lookback=22, cap=40, run_id="r1"):
        self.rig = rig or Rig()
        return runner.run(self.state, target, lookback, cap, run_id, "collector-sha",
                          adapter=self.rig.adapter)

    def rows(self):
        with sqlite3.connect(str(self.state / "shadow.db")) as db:
            return db.execute("SELECT url, source_identity, text_original, site_byline,"
                              " published_at_original, published_at_utc, capture_sha256"
                              " FROM shadow_records ORDER BY source_identity").fetchall()


class TestRunner(RunnerCase):
    def test_the_real_two_statements_are_stored_with_source_provenance(self):
        entry = self.go()
        self.assertEqual((entry["result"], entry["health"]), (st.OK, "ok"))
        self.assertEqual([entry[k] for k in ("discovered", "selected", "retrieved", "inserted")],
                         [2, 2, 2, 2])
        rows = self.rows()
        self.assertEqual([r[1] for r in rows], ["nsc:2269", "nsc:3108"])
        self.assertEqual([len(r[2]) for r in rows], [1808, 1272])
        for row in rows:
            self.assertEqual(row[3], "National Security Council")
            self.assertTrue(row[4].endswith("+08:00"))
            self.assertTrue(row[5].endswith("+00:00"))
            payload = (self.state / "captures" / (row[6] + ".bin")).read_bytes()
            self.assertIn(payload, ARTICLE_BIN.values())
            self.assertEqual(hashlib.sha256(payload).hexdigest(), row[6])

    def test_listing_evidence_and_identity_are_in_the_ledger(self):
        entry = self.go()
        self.assertEqual(entry["robots_status"], "read")
        self.assertEqual(entry["listing_status"], st.OK)
        self.assertEqual(entry["listing_report"]["items_listed"], 6)
        self.assertEqual(entry["listing_report"]["oldest"], "2026-06-03")
        self.assertEqual(entry["listing_report"]["window_start"], "2026-06-16")
        self.assertFalse(entry["listing_report"]["pagination_markup_seen"])
        self.assertTrue(entry["collector_identity"].startswith("ChinaMilWatch-ShadowCollector/0.1 "))
        self.assertEqual(entry["collector_commit"], "collector-sha")
        self.assertEqual(entry["target_date_source"], "explicit")
        self.assertEqual(len(entry["captures"]), 2)

    def test_a_current_prospective_window_is_an_honest_empty_success(self):
        entry = self.go(target=date(2026, 10, 2), lookback=6)
        self.assertEqual(entry["result"], st.OK_NO_PUBLICATIONS)
        self.assertEqual(entry["inserted"], 0)
        self.assertEqual(len(self.rig.urls), 2)  # robots and category only

    def test_unprovable_history_fails_before_fetching_and_does_not_start_clock(self):
        entry = self.go(lookback=35)
        self.assertEqual((entry["result"], entry["health"]), (st.LISTING_FAILURE, "fail"))
        self.assertIn("coverage unprovable", entry["error_detail"])
        self.assertEqual(entry["selected"], 0)
        self.assertEqual(len(self.rig.urls), 2)
        self.assertFalse((self.state / "clock.json").exists())
        self.assertEqual(len(list((self.state / "ledger").glob("*.json"))), 1)

    def test_cap_overflow_is_a_refusal_with_every_candidate_named(self):
        entry = self.go(cap=1)
        self.assertEqual(entry["result"], st.LISTING_FAILURE)
        self.assertEqual(set(entry["deferred_urls"]), set(ARTICLE_URL.values()))
        self.assertEqual(entry["retrieved"], 0)

    def test_duplicates_preserve_database_clock_and_old_ledger_bytes(self):
        first = self.go()
        old = {p: p.read_bytes() for p in self.state.rglob("*.json")}
        second = self.go(run_id="r2")
        self.assertEqual((second["result"], second["inserted"], second["duplicates"]),
                         (st.OK_ALL_DUPLICATES, 0, 2))
        self.assertEqual(second["state_sha256_before"], first["state_sha256_after"])
        self.assertEqual(second["state_sha256_after"], first["state_sha256_after"])
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(old, {p: p.read_bytes() for p in old})

    def test_a_challenge_fails_without_retry_and_preserves_the_gap_evidence(self):
        rig = Rig(routes({ARTICLE_URL[1]: FakeResponse(CHALLENGE)}))
        entry = self.go(rig)
        self.assertEqual(entry["result"], st.ACCESS_CHALLENGED)
        self.assertEqual((entry["challenged"], entry["access_failures"]), (1, 1))
        self.assertEqual(rig.urls.count(ARTICLE_URL[1]), 1)
        self.assertEqual(entry["failures"][0]["url"], ARTICLE_URL[1])
        self.assertFalse((self.state / "clock.json").exists())

    def test_robots_refusal_preserves_status_and_never_reads_listing(self):
        from tests.test_ph_nsc_adapter import robots_rig
        rig = robots_rig("User-agent: *\nDisallow: /\n")
        entry = self.go(rig)
        self.assertEqual(entry["result"], st.AUTH_FAILURE)
        self.assertEqual(len(rig.urls), 1)
        self.assertEqual(entry["robots_status"], "read")
        self.assertTrue(entry["failed_endpoints"])

    def test_fetch_and_extraction_failures_are_distinguished(self):
        with mock.patch.object(runner.PHNscAdapter, "extract") as extract:
            from core.collection.contract import ExtractionResult
            extract.return_value = ExtractionResult("ph_nsc_official_statements",
                                                    st.EXTRACTION_FAILURE, error_detail="derived failure")
            entry = self.go()
        self.assertEqual((entry["extraction_failures"], entry["fetch_failures"]), (2, 0))
        self.assertEqual(entry["result"], st.EXTRACTION_FAILURE)
        self.assertEqual(len(list((self.state / "captures").glob("*.bin"))), 2)

    def test_an_unexpected_adapter_error_still_leaves_a_failed_ledger(self):
        rig = Rig()
        with mock.patch.object(rig.adapter, "discover", side_effect=RuntimeError("derived crash")):
            entry = self.go(rig)
        self.assertEqual(entry["result"], st.ADAPTER_ERROR)
        self.assertEqual(entry["health"], "fail")
        self.assertEqual(len(list((self.state / "ledger").glob("*.json"))), 1)

    def test_disabled_source_performs_no_network_or_database_write(self):
        source = runner.load_source()
        source.enabled = False
        rig = Rig()
        with mock.patch.object(runner, "load_source", return_value=source):
            entry = self.go(rig)
        self.assertEqual(entry["result"], st.SKIPPED_DISABLED)
        self.assertEqual(rig.urls, [])
        self.assertFalse((self.state / "shadow.db").exists())

    def test_enabled_healthcheck_is_offline_and_truthful(self):
        from tests.test_ph_nsc_adapter import EnabledSource
        rig = Rig(source=EnabledSource)
        self.assertEqual(rig.adapter.healthcheck().status, st.OK)
        self.assertEqual(rig.urls, [])

    def test_state_child_symlinks_are_refused_before_a_write(self):
        self.state.mkdir()
        (self.state / "shadow.db").symlink_to(Path(self.tmp.name) / "outside.db")
        with self.assertRaises(ValueError):
            self.go()
        self.assertFalse((Path(self.tmp.name) / "outside.db").exists())

    def test_a_corrupt_prior_capture_is_refused_without_overwriting_it(self):
        self.go()
        capture = next((self.state / "captures").glob("*.bin"))
        capture.write_bytes(b"derived corruption")
        entry = self.go(run_id="r2")
        self.assertEqual((entry["result"], entry["inserted"]), (st.ADAPTER_ERROR, 0))
        self.assertEqual(capture.read_bytes(), b"derived corruption")

    def test_state_is_refused_inside_worktree_primary_checkout_or_symlink(self):
        for path in (ROOT, ROOT / "state"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                runner.assert_isolated(path)
        primary = Path(self.tmp.name).resolve() / "primary"
        (primary / ".git").mkdir(parents=True)
        nested = primary / ".worktrees" / "collector"
        nested.mkdir(parents=True)
        with mock.patch.object(runner, "REPO_ROOT", nested):
            with self.assertRaises(ValueError):
                runner.assert_isolated(primary / "state")
            runner.assert_isolated(Path(self.tmp.name) / "external-state")
        link = Path(self.tmp.name) / "inside"
        link.symlink_to(ROOT, target_is_directory=True)
        with self.assertRaises(ValueError):
            runner.assert_isolated(link / "state")

    def test_input_validation_happens_before_writes(self):
        for kw in ({"lookback": -1}, {"cap": 0}, {"run_id": "../escape"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.go(**kw)
        self.assertFalse(self.state.exists())

    def test_no_production_import_or_storage_path_exists_in_executable_code(self):
        tree = ast.parse(Path(runner.__file__).read_text())
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertFalse(set(imports) & {"config", "storage.db", "pipeline"})
        literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        self.assertFalse(any(x in literals for x in ("pla_watch.db", "output/", "gh-pages")))
        self.assertFalse((ROOT / "desks/philippines").exists())


class TestSchedule(RunnerCase):
    def setUp(self):
        super().setUp()
        # main() defaults --run-id, --event-name and --run-attempt from the
        # Actions environment; a CI rerun (attempt 2) must not change a date.
        env = {k: v for k, v in os.environ.items()
               if k not in ("GITHUB_RUN_ID", "GITHUB_EVENT_NAME")}
        env["GITHUB_RUN_ATTEMPT"] = "1"
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def invoke(self, *extra):
        real_run = runner.run
        with mock.patch.object(runner, "run", side_effect=lambda *a, **kw:
                               real_run(*a, **kw, adapter=Rig().adapter)), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return runner.main(["--state-dir", str(self.state), "--run-id", "cli"] + list(extra))

    def test_explicit_recovery_date_and_provenance_reach_the_ledger(self):
        self.assertEqual(self.invoke("--target-date", "2026-10-01", "--run-attempt", "2"), 0)
        entry = json.loads(next((self.state / "ledger").glob("*.json")).read_text())
        self.assertEqual((entry["target_date"], entry["target_date_source"]), ("2026-10-01", "explicit"))

    def test_rerun_without_date_is_refused_before_writing(self):
        self.assertEqual(self.invoke("--run-attempt", "2"), 2)
        self.assertFalse(self.state.exists())

    def test_schedule_slot_and_manual_dates_use_shared_resolver(self):
        now = datetime(2026, 10, 3, 1, tzinfo=timezone.utc)
        with mock.patch.object(runner, "datetime") as clock:
            clock.now.return_value = now
            with mock.patch.object(runner, "run", return_value={"health": "ok"}) as run, \
                    redirect_stdout(io.StringIO()):
                runner.main(["--state-dir", str(self.state), "--event-name", "schedule",
                             "--cron-utc", "10:10", "--run-attempt", "1"])
                self.assertEqual(run.call_args.args[1], date(2026, 10, 2))
                self.assertEqual(run.call_args.kwargs["target_source"], "schedule-slot")
                runner.main(["--state-dir", str(self.state), "--event-name", "workflow_dispatch"])
                self.assertEqual(run.call_args.args[1], date(2026, 10, 3))
                self.assertEqual(run.call_args.kwargs["target_source"], "manual-utc-date")

    def test_failed_collection_fails_the_command(self):
        self.assertEqual(self.invoke("--target-date", "2026-06-01"), 1)

    def test_ledger_filename_collision_never_rewrites_evidence(self):
        entry = self.go()
        before = {p: p.read_bytes() for p in (self.state / "ledger").glob("*.json")}
        with mock.patch.object(runner, "datetime") as clock:
            clock.now.return_value = datetime.fromisoformat(entry["finished_utc"])
            clock.fromisoformat.side_effect = datetime.fromisoformat
            with self.assertRaises(FileExistsError):
                runner._finish(entry, self.state, self.state / "shadow.db")
        self.assertEqual(before, {p: p.read_bytes() for p in before})


class TestWorkflow(unittest.TestCase):
    def test_collection_is_enabled_for_owner_approved_public_shadow(self):
        self.assertRegex(RAW, r"(?m)^permissions:\n  contents: read$")
        job = RAW.split("jobs:\n  shadow:\n", 1)[1]
        self.assertNotRegex(job, r"(?m)^    if:")
        self.assertIn("    permissions:\n      contents: write\n", job)
        self.assertEqual(runner.USER_AGENT,
                         "ChinaMilWatch-ShadowCollector/0.1 "
                         "(+https://chinamilwatch.org; research archive; contact via site)")

    def test_only_shadow_state_can_be_pushed_without_force(self):
        code = "\n".join(line for line in RAW.splitlines() if not line.lstrip().startswith("#"))
        self.assertEqual(re.findall(r"git push[^\n]+", code), ["git push origin shadow/ph-nsc"])
        self.assertNotIn("--force", code)
        self.assertNotIn("push -f", code)
        self.assertIn("checkout --orphan shadow/ph-nsc", code)
        self.assertIn('elif [ "$status" -eq 2 ]', code)
        for forbidden in ("pla_watch.db", "output/", "deploy", "pages", "pipeline.py", "analysis"):
            self.assertNotIn(forbidden, code.lower())

    def test_schedule_and_dispatch_are_isolated_and_date_aware(self):
        self.assertIn("contents: write", RAW)
        self.assertIn("cancel-in-progress: false", RAW)
        self.assertIn("group: ph-nsc-shadow", RAW)
        self.assertIn("--cron-utc \"10:10\"", RAW)
        self.assertIn("- cron: '10 10 * * *'", RAW)
        self.assertIn("TARGET_DATE: ${{ inputs.target_date }}", RAW)
        self.assertIn('set -- --target-date "$TARGET_DATE"', RAW)
        self.assertIn('if [ -n "${TARGET_DATE:-}" ]', RAW)
        self.assertIn('--commit "$(git rev-parse HEAD)"', RAW)
        self.assertIn('--state-dir "${RUNNER_TEMP}/shadow-state/state"', RAW)

    def test_failure_evidence_is_uploaded_even_if_state_is_not_pushed(self):
        self.assertIn("if: success()", step("Publish shadow state"))
        for name in ("Preserve run evidence", "Assert the ledger is append-only",
                     "Assert the collector left the repository untouched"):
            self.assertIn("if: always()", step(name))
        self.assertIn("actions/upload-artifact@v4", RAW)
        self.assertIn("${{ runner.temp }}/shadow-state/state/", RAW)
        self.assertIn("retention-days: 90", RAW)
        self.assertIn("shadow.db-wal", RAW)
        self.assertIn("shadow.db-shm", RAW)
        self.assertIn("git status --porcelain", RAW)

    def test_actual_bootstrap_publish_and_divergence_against_a_bare_remote(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            remote = base / "remote.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            env = dict(os.environ, RUNNER_TEMP=str(base / "runner"),
                       GITHUB_WORKSPACE=str(base / "workspace"), GITHUB_RUN_ID="test", GITHUB_RUN_ATTEMPT="1",
                       STATE_REMOTE=str(remote))
            Path(env["RUNNER_TEMP"]).mkdir()
            repo = Path(env["GITHUB_WORKSPACE"]) / "repo"
            repo.mkdir(parents=True)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            for cmd in (["git", "-C", str(repo), "config", "user.name", "test"],
                        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
                        ["git", "-C", str(repo), "commit", "--allow-empty", "-m", "collector"]):
                subprocess.run(cmd, check=True, capture_output=True)
            def execute(name):
                return subprocess.run(["bash", "-c", shell(name)], env=env, capture_output=True, text=True)
            self.assertEqual(execute("Check out shadow state").returncode, 0)
            self.assertEqual(execute("Assert the state checkout is not the repository").returncode, 0)
            state_repo = Path(env["RUNNER_TEMP"]) / "shadow-state"
            state = state_repo / "state"
            state.mkdir()
            (state / "evidence.txt").write_text("first")
            self.assertEqual(execute("Publish shadow state").returncode, 0)
            other = base / "other"
            subprocess.run(["git", "clone", "--branch", "shadow/ph-nsc", str(remote), str(other)],
                           check=True, capture_output=True)
            (state / "evidence.txt").write_text("second")
            self.assertEqual(execute("Publish shadow state").returncode, 0)
            (other / "state/evidence.txt").write_text("stale writer")
            env["RUNNER_TEMP"] = str(base / "stale")
            Path(env["RUNNER_TEMP"]).mkdir()
            other.rename(Path(env["RUNNER_TEMP"]) / "shadow-state")
            refused = execute("Publish shadow state")
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("rejected", refused.stderr)
            branches = subprocess.check_output(["git", "--git-dir", str(remote), "branch", "--format=%(refname:short)"], text=True)
            self.assertEqual(branches.strip(), "shadow/ph-nsc")


if __name__ == "__main__":
    unittest.main()
