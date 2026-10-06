"""Offline Vietnam runner, provenance, versions, isolation and state-branch rehearsals."""
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
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from core.collection import status as st
from scraper.sources import vn_vgp as vgp
from scripts import shadow_collect_vietnam as runner
from tests.test_vn_vgp_adapter import (
    BIN, FakeResponse, LISTING_BIN, LISTING_TEXT, LOOKBACK, MAY, MOD_CHALLENGE, ROBOTS_BIN,
    Rig, TARGET, URL, edited, item_block, page, robots_rig, routes)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/vietnam_shadow.yml"
RAW = WORKFLOW.read_text(encoding="utf-8")
CODE = "\n".join(line for line in RAW.splitlines() if not line.lstrip().startswith("#"))
IDS = sorted("vgp-en:" + i for i in MAY)


def setUpModule():
    def refuse(*_args, **_kwargs):
        raise AssertionError("network access attempted in an offline test")
    global _GUARDS
    _GUARDS = [mock.patch.object(socket.socket, "connect", refuse),
               mock.patch("socket.getaddrinfo", refuse),
               mock.patch("socket.create_connection", refuse)]
    for guard in _GUARDS:
        guard.start()


def tearDownModule():
    for guard in _GUARDS:
        guard.stop()


def step(name):
    match = re.search(r"^      - name: " + re.escape(name) + r"\n(.*?)(?=^      - name: |\Z)",
                      RAW, re.M | re.S)
    return match.group(1)


def shell(name):
    return textwrap.dedent(step(name).split("run: |\n", 1)[1])


def moved_listing():
    """Derived: the tag page linking MAY[0] under a different slug, same id."""
    start, end = item_block(MAY[0])
    block = LISTING_TEXT[start:end].replace("viet-nam-russia-hold-", "vietnam-russia-hold-")
    return (LISTING_TEXT[:start] + block + LISTING_TEXT[end:]).encode("utf-8")


MOVED_URL = URL[MAY[0]].replace("viet-nam-russia-hold-", "vietnam-russia-hold-")
EDITED_BODY = page(MAY[0], ("Both sides pledged", "The two sides pledged")).encode("utf-8")


class RunnerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"

    def go(self, rig=None, target=TARGET, lookback=LOOKBACK, cap=40, run_id="r1"):
        self.rig = rig or Rig()
        return runner.run(self.state, target, lookback, cap, run_id, "collector-sha",
                          adapter=self.rig.adapter)

    def query(self, sql, *args):
        with sqlite3.connect(str(self.state / "shadow.db")) as db:
            return db.execute(sql, args).fetchall()

    def ledgers(self):
        return sorted((self.state / "ledger").glob("*.json"))


class TestRunner(RunnerCase):
    def test_the_two_may_reports_are_stored_with_provenance(self):
        entry = self.go()
        self.assertEqual((entry["result"], entry["health"]), (st.OK, "ok"))
        self.assertEqual([entry[k] for k in ("discovered", "selected", "retrieved", "new_records")],
                         [2, 2, 2, 2])
        rows = self.query("SELECT source_identity, url, canonical_url, published_date,"
                          " published_at_original, published_at_utc, publication_kind,"
                          " version_count, language_tag FROM shadow_records ORDER BY 1")
        self.assertEqual([r[0] for r in rows], IDS)
        for row in rows:
            item = row[0].split(":")[1]
            self.assertEqual((row[1], row[2]), (URL[item], URL[item]))
            self.assertTrue(row[4].endswith("+07:00") and row[5].endswith("+00:00"))
            self.assertEqual((row[6], row[7], row[8]), ("newsroom report", 1, "en"))
        versions = self.query("SELECT source_identity, first_capture_sha256, text_original"
                              " FROM shadow_versions ORDER BY 1")
        for ident, capture_sha, text in versions:
            payload = (self.state / "captures" / (capture_sha + ".bin")).read_bytes()
            self.assertEqual(payload, BIN[ident.split(":")[1]])
            self.assertEqual(hashlib.sha256(payload).hexdigest(), capture_sha)
        # NBSP survives storage: the database holds the text as published.
        self.assertIn(" ", dict((v[0], v[2]) for v in versions)["vgp-en:" + MAY[1]])
        outcomes = self.query("SELECT outcome, http_status, final_url = requested_url"
                              " FROM shadow_observations")
        self.assertEqual(sorted(outcomes), [("new", 200, 1), ("new", 200, 1)])

    def test_ledger_carries_listing_evidence_identity_and_every_request(self):
        entry = self.go()
        self.assertEqual((entry["robots_status"], entry["listing_status"]), ("read", st.OK))
        report = entry["listing_report"]
        self.assertEqual((report["coverage"], report["items_listed"], report["oldest_listed"]),
                         ("proven", 24, "2023-11-16"))
        self.assertEqual((entry["window_start"], entry["target_date"]), ("2026-05-21", "2026-05-24"))
        self.assertEqual(entry["collector_identity"], vgp.USER_AGENT)
        self.assertEqual((entry["collector_commit"], entry["target_date_source"]),
                         ("collector-sha", "explicit"))
        self.assertEqual((entry["cap"], entry["request_ceiling"]), (40, 42))
        self.assertEqual(entry["content_hash_rule"], vgp.CONTENT_HASH_RULE)
        self.assertEqual([c["role"] for c in entry["captures"]],
                         ["robots", "listing", "article", "article"])
        for kept in entry["captures"]:
            stored = (self.state / "captures" / (kept["payload_sha256"] + ".bin")).read_bytes()
            self.assertEqual(len(stored), kept["payload_bytes"])
        self.assertEqual((self.state / "captures" / (hashlib.sha256(ROBOTS_BIN).hexdigest()
                                                     + ".bin")).read_bytes(), ROBOTS_BIN)
        self.assertEqual((self.state / "captures" / (hashlib.sha256(LISTING_BIN).hexdigest()
                                                     + ".bin")).read_bytes(), LISTING_BIN)
        self.assertEqual([r["url"] for r in entry["requests"]],
                         [vgp.ROBOTS, vgp.LISTING, URL[MAY[0]], URL[MAY[1]]])
        self.assertEqual(entry["corpus_range"], ["2026-05-21", "2026-05-24"])
        self.assertEqual((entry["stored_total"], entry["versions_total"]), (2, 2))
        on_disk = json.loads(self.ledgers()[0].read_text(encoding="utf-8"))
        self.assertEqual(on_disk["run_id"], "r1")
        self.assertFalse([c for c in on_disk["captures"] if "payload" in c])
        # Every listed item and its listed time, for late-listing review.
        self.assertEqual(len(on_disk["listing_report"]["listed"]), 24)
        self.assertIn([MAY[1], "2026-05-21T16:40"], on_disk["listing_report"]["listed"])

    def test_a_current_quiet_window_is_an_honest_empty_success(self):
        entry = self.go(target=date(2026, 10, 5), lookback=6)
        self.assertEqual((entry["result"], entry["health"]), (st.OK_NO_PUBLICATIONS, "ok"))
        self.assertEqual((entry["selected"], entry["new_records"], entry["stored_total"]), (0, 0, 0))
        self.assertEqual(self.rig.urls, [vgp.ROBOTS, vgp.LISTING])
        clock = json.loads((self.state / "clock.json").read_text())
        self.assertEqual((clock["day_zero_run_id"], entry["shadow_day"]), ("r1", 0))

    def test_a_quiet_run_leaves_an_existing_database_byte_identical(self):
        first = self.go(target=date(2026, 10, 5), lookback=6)
        self.assertIsNone(first["state_sha256_before"])
        self.assertEqual(self.query("SELECT COUNT(*) FROM shadow_records"), [(0,)])
        stored = self.go(run_id="r2")
        db = (self.state / "shadow.db").read_bytes()
        quiet = self.go(target=date(2026, 10, 6), lookback=6, run_id="r3")
        self.assertEqual(quiet["result"], st.OK_NO_PUBLICATIONS)
        self.assertEqual(quiet["state_sha256_before"], stored["state_sha256_after"])
        self.assertEqual(quiet["state_sha256_after"], quiet["state_sha256_before"])
        self.assertEqual((self.state / "shadow.db").read_bytes(), db)

    def test_unprovable_history_fails_before_fetching_and_does_not_start_clock(self):
        entry = self.go(target=date(2023, 11, 22), lookback=6)
        self.assertEqual((entry["result"], entry["health"]), (st.LISTING_FAILURE, "fail"))
        self.assertIn("coverage unprovable", entry["error_detail"])
        self.assertEqual((entry["selected"], len(self.rig.urls)), (0, 2))
        self.assertFalse((self.state / "clock.json").exists())
        self.assertEqual(len(self.ledgers()), 1)
        self.assertEqual([c["role"] for c in entry["captures"]], ["robots", "listing"])
        self.assertIsNone(entry["shadow_day"])
        # The ledger on disk, not just the returned entry, keeps both requests.
        on_disk = json.loads(self.ledgers()[0].read_text(encoding="utf-8"))
        self.assertEqual([r["url"] for r in on_disk["requests"]], [vgp.ROBOTS, vgp.LISTING])

    def test_cap_overflow_is_a_refusal_with_every_candidate_named(self):
        entry = self.go(cap=1)
        self.assertEqual(entry["result"], st.LISTING_FAILURE)
        self.assertEqual(entry["deferred_urls"], [URL[MAY[0]], URL[MAY[1]]])
        self.assertEqual((entry["retrieved"], entry["request_ceiling"]), (0, 3))
        self.assertEqual(self.rig.urls, [vgp.ROBOTS, vgp.LISTING])
        self.assertFalse((self.state / "shadow.db").exists())

    def test_the_runner_sets_the_adapter_request_ceiling(self):
        built = {}
        real = runner.VNVgpAdapter

        def build(source, max_requests):
            built["max_requests"] = max_requests
            self.rig = Rig(max_requests=max_requests)
            return self.rig.adapter
        with mock.patch.object(runner, "VNVgpAdapter", side_effect=build):
            entry = runner.run(self.state, TARGET, LOOKBACK, 5, "r1", "c")
        self.assertIs(runner.VNVgpAdapter, real)
        self.assertEqual((built["max_requests"], entry["result"]), (7, st.OK))

    def test_duplicates_add_observations_never_versions_or_rewrites(self):
        first = self.go()
        old = {p: p.read_bytes() for p in self.state.rglob("*") if p.is_file()
               and p.name != "shadow.db"}
        second = self.go(run_id="r2")
        self.assertEqual((second["result"], second["new_records"], second["unchanged"]),
                         (st.OK_ALL_DUPLICATES, 0, 2))
        self.assertEqual(second["state_sha256_before"], first["state_sha256_after"])
        self.assertEqual(self.query("SELECT COUNT(*) FROM shadow_versions"), [(2,)])
        self.assertEqual(self.query("SELECT COUNT(*), COUNT(DISTINCT run_id) FROM shadow_observations"),
                         [(4, 2)])
        self.assertEqual(self.query("SELECT DISTINCT first_seen_run, last_seen_run, version_count"
                                    " FROM shadow_records"), [("r1", "r2", 1)])
        self.assertEqual(old, {p: p.read_bytes() for p in old})
        self.assertEqual(len(list((self.state / "captures").glob("*.bin"))), 4)
        self.assertEqual(json.loads((self.state / "clock.json").read_text())["day_zero_run_id"], "r1")

    def test_an_edit_is_a_new_version_and_a_return_is_a_reversion(self):
        self.go()
        original = self.query("SELECT current_content_sha256 FROM shadow_records"
                              " WHERE source_identity = ?", "vgp-en:" + MAY[0])[0][0]
        changed = self.go(Rig(routes({URL[MAY[0]]: FakeResponse(EDITED_BODY)})), run_id="r2")
        self.assertEqual((changed["result"], changed["changed"], changed["unchanged"]), (st.OK, 1, 1))
        edited_hash = self.query("SELECT current_content_sha256, version_count FROM shadow_records"
                                 " WHERE source_identity = ?", "vgp-en:" + MAY[0])[0]
        self.assertNotEqual(edited_hash[0], original)
        self.assertEqual(edited_hash[1], 2)
        texts = [r[0] for r in self.query("SELECT text_original FROM shadow_versions"
                                          " WHERE source_identity = ? ORDER BY first_seen_run",
                                          "vgp-en:" + MAY[0])]
        self.assertIn("Both sides pledged", texts[0])
        self.assertIn("The two sides pledged", texts[1])
        reverted = self.go(run_id="r3")
        self.assertEqual((reverted["result"], reverted["reverted"]), (st.OK, 1))
        self.assertEqual(self.query("SELECT current_content_sha256, version_count FROM shadow_records"
                                    " WHERE source_identity = ?", "vgp-en:" + MAY[0]),
                         [(original, 2)])
        self.assertEqual(self.query("SELECT outcome FROM shadow_observations WHERE source_identity = ?"
                                    " ORDER BY run_id", "vgp-en:" + MAY[0]),
                         [("new",), ("changed",), ("reverted",)])

    def test_a_moved_url_keeps_one_publication_and_records_both_urls(self):
        self.go()
        rig = Rig(routes({vgp.LISTING: FakeResponse(moved_listing()),
                          MOVED_URL: FakeResponse(BIN[MAY[0]])}))
        entry = self.go(rig, run_id="r2")
        self.assertEqual((entry["result"], entry["unchanged"], entry["stored_total"]),
                         (st.OK_ALL_DUPLICATES, 2, 2))
        found = [a["anomaly"] for a in entry["anomalies"] if a["url"] == MOVED_URL]
        self.assertTrue(any(a.startswith("canonical_url_differs") for a in found))
        self.assertTrue(any(a.startswith("url_changed: first stored %s" % URL[MAY[0]]) for a in found))
        self.assertEqual(self.query("SELECT url FROM shadow_records WHERE source_identity = ?",
                                    "vgp-en:" + MAY[0]), [(URL[MAY[0]],)])
        self.assertEqual(self.query("SELECT requested_url FROM shadow_observations WHERE run_id = 'r2'"
                                    " AND source_identity = ?", "vgp-en:" + MAY[0]), [(MOVED_URL,)])

    def test_a_challenge_stops_the_run_and_names_what_was_not_tried(self):
        rig = Rig(routes({URL[MAY[0]]: FakeResponse(MOD_CHALLENGE)}))
        entry = self.go(rig)
        self.assertEqual((entry["result"], entry["health"]), (st.ACCESS_CHALLENGED, "fail"))
        self.assertEqual((entry["challenged"], entry["access_failures"]), (1, 1))
        # No retry, and no further request to a host that has refused us.
        self.assertEqual(rig.urls, [vgp.ROBOTS, vgp.LISTING, URL[MAY[0]]])
        self.assertEqual(entry["deferred_urls"], [URL[MAY[1]]])
        self.assertEqual(entry["failures"][0]["url"], URL[MAY[0]])
        self.assertEqual(entry["error_detail"], "incomplete run; state must not be pushed")
        self.assertEqual((entry["retrieved"], entry["new_records"]), (0, 0))
        self.assertFalse((self.state / "clock.json").exists())

    def test_a_forbidden_article_stops_the_run_but_a_missing_one_does_not(self):
        rig = Rig(routes({URL[MAY[0]]: FakeResponse(b"forbidden", 403)}))
        entry = self.go(rig)
        self.assertEqual((entry["result"], entry["access_failures"]), (st.AUTH_FAILURE, 1))
        self.assertEqual((entry["deferred_urls"], entry["failures"][0]["http_status"]),
                         ([URL[MAY[1]]], 403))
        self.assertNotIn(URL[MAY[1]], rig.urls)
        rig = Rig(routes({URL[MAY[0]]: FakeResponse(b"gone", 404)}))
        entry = self.go(rig, run_id="r2")
        self.assertEqual(rig.urls[-1], URL[MAY[1]])
        self.assertNotIn("deferred_urls", entry)

    def test_fetch_and_extraction_failures_are_distinguished(self):
        entry = self.go(Rig(routes({URL[MAY[0]]: FakeResponse(b"gone", 404)})))
        self.assertEqual((entry["result"], entry["fetch_failures"], entry["extraction_failures"]),
                         (st.FETCH_FAILURE, 1, 0))
        self.assertEqual(entry["failures"][0]["http_status"], 404)
        truncated = BIN[MAY[1]][:-300]
        entry = self.go(Rig(routes({URL[MAY[1]]: FakeResponse(truncated)})), run_id="r2")
        self.assertEqual((entry["result"], entry["fetch_failures"], entry["extraction_failures"]),
                         (st.EXTRACTION_FAILURE, 0, 1))
        self.assertIn("truncation", entry["failures"][0]["detail"])
        stored = self.state / "captures" / (hashlib.sha256(truncated).hexdigest() + ".bin")
        self.assertEqual(stored.read_bytes(), truncated)

    def test_robots_refusal_preserves_status_and_never_reads_listing(self):
        rig = robots_rig("User-agent: *\nDisallow: /\n")
        entry = self.go(rig)
        self.assertEqual(entry["result"], st.AUTH_FAILURE)
        self.assertEqual(rig.urls, [vgp.ROBOTS])
        self.assertEqual(entry["robots_status"], "read")
        on_disk = json.loads(self.ledgers()[0].read_text(encoding="utf-8"))
        self.assertEqual([r["url"] for r in on_disk["requests"]], [vgp.ROBOTS])
        self.assertEqual(entry["failed_endpoints"], [vgp.LISTING])

    def test_an_unexpected_adapter_error_still_leaves_a_failed_ledger(self):
        rig = Rig()
        with mock.patch.object(rig.adapter, "discover", side_effect=RuntimeError("derived crash")):
            entry = self.go(rig)
        self.assertEqual((entry["result"], entry["health"]), (st.ADAPTER_ERROR, "fail"))
        self.assertIn("derived crash", entry["error_detail"])
        self.assertEqual(len(self.ledgers()), 1)

    def test_disabled_source_performs_no_network_or_database_write(self):
        source = runner.load_source()
        source.enabled = False
        rig = Rig()
        with mock.patch.object(runner, "load_source", return_value=source):
            entry = self.go(rig)
        self.assertEqual(entry["result"], st.SKIPPED_DISABLED)
        self.assertEqual(rig.urls, [])
        self.assertFalse((self.state / "shadow.db").exists())

    def test_state_child_symlinks_are_refused_before_a_write(self):
        self.state.mkdir()
        (self.state / "shadow.db").symlink_to(Path(self.tmp.name) / "outside.db")
        with self.assertRaises(ValueError):
            self.go()
        self.assertFalse((Path(self.tmp.name) / "outside.db").exists())

    def test_a_corrupt_prior_capture_is_refused_without_overwriting_it(self):
        self.go()
        capture = self.state / "captures" / (hashlib.sha256(BIN[MAY[0]]).hexdigest() + ".bin")
        capture.write_bytes(b"derived corruption")
        entry = self.go(run_id="r2")
        self.assertEqual((entry["result"], entry["new_records"], entry["unchanged"]),
                         (st.ADAPTER_ERROR, 0, 0))
        self.assertIn("disagrees with its filename", entry["error_detail"])
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
        for kw in ({"lookback": -1}, {"cap": 0}, {"run_id": "../escape"}, {"run_id": ""}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.go(**kw)
        self.assertFalse(self.state.exists())

    def test_no_production_import_or_storage_path_exists_in_executable_code(self):
        tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual({m for m in imports if m.split(".")[0] in ("core", "scraper")},
                         {"core.collection", "core.collection.contract", "core.shadow_schedule",
                          "scraper.sources.vn_vgp"})
        plain = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertFalse({"requests", "storage", "pipeline", "config", "anthropic"} & plain)
        literals = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        self.assertFalse(any(x in s for s in literals for x in ("pla_watch.db", "output/", "gh-pages")))
        self.assertFalse((ROOT / "desks/vietnam").exists())


class TestSchedule(RunnerCase):
    def setUp(self):
        super().setUp()
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
        entry = json.loads(self.ledgers()[0].read_text())
        self.assertEqual((entry["target_date"], entry["target_date_source"]),
                         ("2026-10-01", "explicit"))
        self.assertEqual(entry["result"], st.OK_NO_PUBLICATIONS)

    def test_rerun_without_date_is_refused_before_writing(self):
        self.assertEqual(self.invoke("--run-attempt", "2"), 2)
        self.assertFalse(self.state.exists())

    def test_the_documented_slot_resolves_to_the_ha_noi_day_just_ended(self):
        cases = [(datetime(2026, 10, 2, 17, 35, tzinfo=timezone.utc), date(2026, 10, 2)),
                 (datetime(2026, 10, 3, 1, 0, tzinfo=timezone.utc), date(2026, 10, 2)),
                 (datetime(2026, 10, 2, 17, 34, tzinfo=timezone.utc), date(2026, 10, 1))]
        for now, expected in cases:
            with self.subTest(now=now), mock.patch.object(runner, "datetime") as clock:
                clock.now.return_value = now
                with mock.patch.object(runner, "run", return_value={"health": "ok"}) as run, \
                        redirect_stdout(io.StringIO()):
                    runner.main(["--state-dir", str(self.state), "--event-name", "schedule",
                                 "--cron-utc", "17:35", "--run-attempt", "1"])
                    self.assertEqual(run.call_args.args[1], expected)
                    self.assertEqual(run.call_args.kwargs["target_source"], "schedule-slot")

    def test_a_dispatch_records_its_own_utc_date(self):
        with mock.patch.object(runner, "datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 3, 1, tzinfo=timezone.utc)
            with mock.patch.object(runner, "run", return_value={"health": "ok"}) as run, \
                    redirect_stdout(io.StringIO()):
                runner.main(["--state-dir", str(self.state), "--event-name", "workflow_dispatch",
                             "--cron-utc", "17:35"])
        self.assertEqual(run.call_args.args[1], date(2026, 10, 3))
        self.assertEqual(run.call_args.kwargs["target_source"], "manual-utc-date")

    def test_failed_collection_fails_the_command(self):
        self.assertEqual(self.invoke("--target-date", "2023-11-22"), 1)

    def test_ledger_filename_collision_never_rewrites_evidence(self):
        entry = self.go()
        before = {p: p.read_bytes() for p in self.ledgers()}
        with mock.patch.object(runner, "datetime") as clock:
            clock.now.return_value = datetime.fromisoformat(entry["finished_utc"])
            clock.fromisoformat.side_effect = datetime.fromisoformat
            with self.assertRaises(FileExistsError):
                runner._finish(entry, self.state, self.state / "shadow.db")
        self.assertEqual(before, {p: p.read_bytes() for p in before})


class TestWorkflow(unittest.TestCase):
    def test_dispatch_only_with_the_activation_slot_documented_not_declared(self):
        on = RAW.split("\non:\n", 1)[1].split("\nconcurrency:", 1)[0]
        self.assertEqual(re.findall(r"(?m)^  (\w+):", on), ["workflow_dispatch"])
        self.assertNotRegex(CODE, r"(?m)^\s*schedule:")
        self.assertNotRegex(CODE, r"(?m)^\s*-\s*cron:")
        documented = re.findall(r"(?m)^#\s+- cron: '(\d+) (\d+) \* \* \*'$", RAW)
        self.assertEqual(documented, [("35", "17")])
        self.assertIn('--cron-utc "17:35"', CODE)

    def test_any_schedule_must_match_the_cron_the_collector_is_told(self):
        # Declared crons (none yet) and the documented activation slot alike.
        crons = re.findall(r"(?m)^\s*(?:#\s+)?- cron: '(\d+) (\d+) \* \* \*'", RAW)
        told = re.findall(r'--cron-utc "(\d\d):(\d\d)"', CODE)
        self.assertEqual((len(told), len(crons)), (1, 1))
        for minute, hour in crons:
            self.assertEqual(("%02d" % int(hour), "%02d" % int(minute)), told[0])

    def test_permissions_and_identity(self):
        self.assertRegex(RAW, r"(?m)^permissions:\n  contents: read$")
        job = RAW.split("jobs:\n  shadow:\n", 1)[1]
        self.assertNotRegex(job, r"(?m)^    if:")
        self.assertIn("    permissions:\n      contents: write\n", job)
        self.assertIn("persist-credentials: false", job)
        self.assertEqual(runner.USER_AGENT,
                         "ChinaMilWatch-ShadowCollector/0.1 "
                         "(+https://chinamilwatch.org; research archive; contact via site)")

    def test_only_vietnam_state_can_be_pushed_without_force(self):
        self.assertEqual(re.findall(r"git push[^\n]+", CODE), ["git push origin shadow/vietnam"])
        self.assertNotIn("--force", CODE)
        self.assertNotIn("push -f", CODE)
        self.assertIn("checkout --orphan shadow/vietnam", CODE)
        self.assertIn('elif [ "$status" -eq 2 ]', CODE)
        for forbidden in ("pla_watch.db", "output/", "deploy", "pages", "pipeline.py", "analysis",
                          "singapore", "ph-nsc", "shadow/us", "jp-mod", "anthropic"):
            self.assertNotIn(forbidden, CODE.lower())

    def test_dispatch_is_isolated_and_date_aware(self):
        self.assertIn("cancel-in-progress: false", RAW)
        self.assertIn("group: vietnam-shadow", RAW)
        self.assertIn("TARGET_DATE: ${{ inputs.target_date }}", RAW)
        self.assertIn('set -- --target-date "$TARGET_DATE"', RAW)
        self.assertIn('if [ -n "${TARGET_DATE:-}" ]', RAW)
        self.assertIn('--commit "$(git rev-parse HEAD)"', RAW)
        self.assertIn('--state-dir "${RUNNER_TEMP}/shadow-state/state"', RAW)
        self.assertIn("python scripts/shadow_collect_vietnam.py", RAW)
        self.assertIn("--lookback-days 6 --cap 40", RAW)

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
        self.assertIn("state/ledger state/clock.json state/captures",
                      step("Assert the ledger is append-only"))


class TestStateBranchRehearsal(RunnerCase):
    """The workflow's own shell steps against a local bare remote, with real runs."""

    def setUp(self):
        super().setUp()
        base = Path(self.tmp.name)
        self.remote = base / "remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        self.env = dict(os.environ, RUNNER_TEMP=str(base / "runner"),
                        GITHUB_WORKSPACE=str(base / "workspace"), GITHUB_RUN_ID="test",
                        GITHUB_RUN_ATTEMPT="1", STATE_REMOTE=str(self.remote))
        Path(self.env["RUNNER_TEMP"]).mkdir()
        repo = Path(self.env["GITHUB_WORKSPACE"]) / "repo"
        repo.mkdir(parents=True)
        for cmd in (["git", "init", str(repo)],
                    ["git", "-C", str(repo), "config", "user.name", "test"],
                    ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
                    ["git", "-C", str(repo), "commit", "--allow-empty", "-m", "collector"]):
            subprocess.run(cmd, check=True, capture_output=True)

    def execute(self, name):
        return subprocess.run(["bash", "-c", shell(name)], env=self.env, capture_output=True,
                              text=True)

    def checkout(self):
        for name in ("Check out shadow state", "Assert the state checkout is not the repository"):
            result = self.execute(name)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.state = Path(self.env["RUNNER_TEMP"]) / "shadow-state" / "state"

    def git(self, *args):
        return subprocess.check_output(["git", "--git-dir", str(self.remote)] + list(args), text=True)

    def test_bootstrap_two_runs_and_a_refused_divergent_writer(self):
        self.checkout()
        first = self.go(run_id="test-1")
        self.assertEqual(first["result"], st.OK)
        for name in ("Assert the ledger is append-only", "Publish shadow state"):
            result = self.execute(name)
            self.assertEqual(result.returncode, 0, result.stderr)
        first_ledgers = set(self.git("ls-tree", "-r", "--name-only", "shadow/vietnam",
                                     "state/ledger").split())
        # A second job, as the workflow runs it: a fresh clone of the remote.
        self.env.update(RUNNER_TEMP=str(Path(self.tmp.name) / "runner-2"), GITHUB_RUN_ID="test2")
        Path(self.env["RUNNER_TEMP"]).mkdir()
        self.checkout()
        second = self.go(run_id="test2-1")
        self.assertEqual(second["result"], st.OK_ALL_DUPLICATES)
        self.assertEqual(second["state_sha256_before"], first["state_sha256_after"])
        for name in ("Assert the ledger is append-only", "Publish shadow state"):
            self.assertEqual(self.execute(name).returncode, 0)
        log = self.git("log", "--format=%s", "shadow/vietnam").splitlines()
        self.assertEqual(log, ["shadow(vietnam): run test2-1", "shadow(vietnam): run test-1"])
        tree = self.git("ls-tree", "-r", "--name-only", "shadow/vietnam").split()
        self.assertTrue(all(p.startswith("state/") for p in tree))
        self.assertTrue(first_ledgers < set(p for p in tree if p.startswith("state/ledger/")))
        self.assertIn("state/clock.json", tree)
        self.assertEqual(self.git("branch", "--format=%(refname:short)").strip(), "shadow/vietnam")
        # A stale writer from before the second run is refused, not merged or forced.
        stale = Path(self.tmp.name) / "stale"
        stale.mkdir()
        subprocess.run(["git", "clone", "--branch", "shadow/vietnam", str(self.remote),
                        str(stale / "shadow-state")], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(stale / "shadow-state"), "reset", "--hard", "HEAD~1"],
                       check=True, capture_output=True)
        (stale / "shadow-state" / "state" / "evidence.txt").write_text("stale writer")
        self.env["RUNNER_TEMP"] = str(stale)
        refused = self.execute("Publish shadow state")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("rejected", refused.stderr)
        self.assertEqual(len(self.git("log", "--format=%H", "shadow/vietnam").split()), 2)

    def test_a_rewritten_ledger_or_capture_stops_the_job(self):
        self.checkout()
        self.go(run_id="test-1")
        self.assertEqual(self.execute("Publish shadow state").returncode, 0)
        for victim in (sorted((self.state / "ledger").glob("*.json"))[0],
                       next((self.state / "captures").glob("*.bin")),
                       self.state / "clock.json"):
            original = victim.read_bytes()
            victim.write_bytes(original + b" ")
            result = self.execute("Assert the ledger is append-only")
            self.assertNotEqual(result.returncode, 0, victim)
            victim.write_bytes(original)
        self.assertEqual(self.execute("Assert the ledger is append-only").returncode, 0)

    def test_wal_sidecars_are_never_committed(self):
        self.checkout()
        self.go(run_id="test-1")
        (self.state / "shadow.db-wal").write_bytes(b"derived")
        result = self.execute("Publish shadow state")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("WAL/SHM", result.stdout + result.stderr)
        self.assertEqual(self.git("branch", "--format=%(refname:short)").strip(), "")


if __name__ == "__main__":
    unittest.main()
