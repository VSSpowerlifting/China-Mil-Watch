"""
Vietnam shadow review kit: formal and rehearsal packets, refusals, tamper
evidence, coverage, late listing, sign-off, and equivalence with the runner
and adapter it reviews.

Every state here is produced by scripts/shadow_collect_vietnam.py itself,
offline from the pinned Government News captures, at chosen UTC instants;
formal packets read it back from a real `shadow/vietnam` commit. Tampering is
applied to copies afterwards and labelled. A socket guard fails any real
connection.
"""
import ast
import hashlib
import io
import json
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from core import shadow_schedule
from core.collection import status as st
from scraper.sources import vn_vgp as vgp
from scripts import review_vietnam_shadow_state as kit
from scripts import shadow_collect_vietnam as runner
from tests.test_vn_vgp_adapter import (
    BIN, FakeResponse, LISTING_TEXT, LOOKBACK, MAY, PAGES, TARGET, URL, Rig, extract,
    item_block, routes)
from tests.test_vietnam_shadow_runner import EDITED_BODY, MOVED_URL, moved_listing

ROOT = Path(__file__).resolve().parents[1]
SCHED, EXPL = shadow_schedule.SOURCE_SCHEDULE, shadow_schedule.SOURCE_EXPLICIT
EARLY, LATE = "vgp-en:" + MAY[1], "vgp-en:" + MAY[0]      # 2026-05-21, 2026-05-24
#: What a runner ledger may carry beyond kit.LEDGER_REQUIRED, by exit path.
LEDGER_OPTIONAL = {"failed_endpoints", "deferred_urls", "corpus_range", "day_zero_utc"}


def without_may1():
    """Derived: the tag page as if MAY[1] had not yet been tagged."""
    start, end = item_block(MAY[1])
    return (LISTING_TEXT[:start] + LISTING_TEXT[end:]).encode("utf-8")


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


class Frozen(datetime):
    """The runner's clock, set per run so ledgers fall on chosen days."""
    at = None

    @classmethod
    def now(cls, tz=None):
        return cls.at


def collect(state, plan, enabled=True):
    entries = []
    for at, target, lookback, run_id, source, rig in plan:
        Frozen.at = datetime(*at, tzinfo=timezone.utc)
        manifest_source = runner.load_source()
        manifest_source.enabled = enabled
        with mock.patch.object(runner, "datetime", Frozen), \
                mock.patch.object(runner, "load_source", return_value=manifest_source):
            entries.append(runner.run(state, target, lookback, 40, run_id, "c" * 40,
                                      adapter=(rig or Rig()).adapter, target_source=source))
    return entries


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=Shadow Test", "-c", "user.email=shadow@test.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(cwd), check=True, capture_output=True, text=True).stdout.strip()


def commit_state(repo, state, branch="shadow/vietnam", message="state"):
    """`state/` as the workflow commits it, on an orphan branch of a scratch repo."""
    if not (repo / ".git").exists():
        repo.mkdir(parents=True)
        git(repo, "init", "-q")
    if git(repo, "symbolic-ref", "HEAD") != "refs/heads/" + branch:
        git(repo, "symbolic-ref", "HEAD", "refs/heads/" + branch)
        git(repo, "rm", "-rq", "--cached", "--ignore-unmatch", ".")
    shutil.rmtree(repo / "state", ignore_errors=True)
    shutil.copytree(state, repo / "state", symlinks=True)
    git(repo, "add", "-A", "state")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


#: Day zero is a quiet scheduled run; Government News had not yet tagged MAY[1]
#: when the first dispatch read May; the next read found it; a quiet day follows.
MAIN = [
    ((2026, 10, 6, 17, 40, 5), date(2026, 10, 6), 6, "9001-1", SCHED, None),
    ((2026, 10, 7, 17, 41, 9), TARGET, LOOKBACK, "9002-1", EXPL,
     "without-may1"),
    ((2026, 10, 8, 17, 39, 0), TARGET, LOOKBACK, "9003-1", EXPL, None),
    ((2026, 10, 9, 17, 36, 30), date(2026, 10, 9), 6, "9004-1", SCHED, None),
]


def rigs(plan):
    out = []
    for at, target, lookback, run_id, source, rig in plan:
        if rig == "without-may1":
            rig = Rig(routes({vgp.LISTING: FakeResponse(without_may1())}))
        elif rig == "edited":
            rig = Rig(routes({URL[MAY[0]]: FakeResponse(EDITED_BODY)}))
        elif rig == "moved":
            rig = Rig(routes({vgp.LISTING: FakeResponse(moved_listing()),
                              MOVED_URL: FakeResponse(BIN[MAY[0]])}))
        out.append((at, target, lookback, run_id, source, rig))
    return out


class KitCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls._tmp.name)
        cls.main_state = cls.base / "main" / "state"
        cls.main_entries = collect(cls.main_state, rigs(MAIN))
        cls.repo = cls.base / "repo"
        cls.head = commit_state(cls.repo, cls.main_state)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=self._tmp.name))

    def formal(self, commit=None, checkpoint="day-07", repo=None, as_of="2026-10-10",
               out=None):
        out = out or self.tmp / ("packet-%s" % len(list(self.tmp.iterdir())))
        return kit.build(None, out, as_of, state_commit=commit or self.head,
                         checkpoint=checkpoint, state_repo=repo or self.repo), out

    def rehearsal(self, state, as_of="2026-10-10"):
        out = self.tmp / ("rehearsal-%s" % len(list(self.tmp.iterdir())))
        return kit.build(state, out, as_of), out

    def copy_main(self):
        state = self.tmp / "copy" / "state"
        shutil.copytree(self.main_state, state)
        return state

    def ledger_paths(self, state):
        return sorted((state / "ledger").glob("*.json"))

    def edit_ledger(self, path, **changes):
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(changes)
        path.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")

    def refused(self, fragment, **kwargs):
        with self.assertRaises(kit.ReviewError) as caught:
            self.formal(**kwargs)
        self.assertIn(fragment, str(caught.exception))


class TestFormalPacket(KitCase):
    def test_the_runner_wrote_the_planned_history(self):
        self.assertEqual([(e["result"], e["new_records"], e["unchanged"], e["shadow_day"])
                          for e in self.main_entries],
                         [(st.OK_NO_PUBLICATIONS, 0, 0, 0), (st.OK, 1, 0, 1),
                          (st.OK, 1, 1, 1), (st.OK_NO_PUBLICATIONS, 0, 0, 2)])

    def test_a_formal_packet_binds_the_commit_and_reports_the_corpus(self):
        m, out = self.formal()
        tree = git(self.repo, "rev-parse", self.head + ":state")
        self.assertEqual((m["provenance"], m["formal"], m["state_commit"], m["state_tree"]),
                         ("git-verified-tree/1", True, self.head, tree))
        self.assertEqual(m["state_ref"], "shadow/vietnam")
        self.assertEqual((m["corpus_count"], m["version_count"], m["observation_count"],
                          m["capture_count"]), (2, 2, 3, 5))
        self.assertEqual(m["required_review_records"], [EARLY, LATE])
        self.assertEqual(m["corpus_range"], ["2026-05-21", "2026-05-24"])
        self.assertEqual((m["latest_shadow_day"], m["checkpoint_reached"]), (2, False))
        self.assertEqual(m["collecting_days"],
                         ["2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"])
        self.assertEqual(m["consecutive_collecting_days"], 4)
        self.assertEqual(m["state_chain_verdict"], "coherent")
        self.assertEqual(m["allowed_verdicts"], ["pass", "pass_with_findings", "fail"])
        self.assertEqual(m["shadow_period"], ["2026-09-30", "2026-10-09"])
        self.assertEqual(m["uncovered_dates"], [])
        report = (out / "review_report.md").read_text(encoding="utf-8")
        self.assertIn("DAY-07 HAS NOT ARRIVED", report)
        self.assertIn("An unfilled report is not evidence of a completed review", report)
        self.assertIn("Tier B government newsroom", report)
        self.assertNotIn("REHEARSAL", report)
        self.assertNotIn("publishable", report.lower())
        inventory = [json.loads(line) for line in
                     (out / "record_inventory.jsonl").read_text().splitlines()]
        self.assertEqual([r["identity"] for r in inventory], [EARLY, LATE])
        self.assertEqual(inventory[0]["byline"], "Thuy Dung")
        self.assertEqual(inventory[0]["published_at_original"], "2026-05-21T16:40:00+07:00")
        runs = [json.loads(line) for line in (out / "run_inventory.jsonl").read_text().splitlines()]
        self.assertEqual([r["run_id"] for r in runs], ["9001-1", "9002-1", "9003-1", "9004-1"])

    def test_the_late_tagged_item_is_the_only_anomaly(self):
        m, _ = self.formal()
        self.assertEqual(len(m["anomalies"]), 1, m["anomalies"])
        self.assertTrue(m["anomalies"][0].startswith(
            "late listing: %s, listed 2026-05-21T16:40 (Ha Noi), was absent from run "
            "9002-1's tag page" % EARLY))
        self.assertIn("first listed in run 9003-1; collected by a later run", m["anomalies"][0])

    def test_the_same_commit_and_as_of_give_byte_identical_packets(self):
        first, a = self.formal()
        second, b = self.formal()
        names = sorted(p.name for p in a.iterdir())
        self.assertEqual(names, sorted(p.name for p in b.iterdir()))
        for name in names:
            if name != "generation_context.json":
                self.assertEqual((a / name).read_bytes(), (b / name).read_bytes(), name)
        self.assertEqual(first["deterministic_sha256"], second["deterministic_sha256"])
        self.assertNotIn("generation_context.json", first["artifact_sha256"])
        context = json.loads((a / "generation_context.json").read_text())
        self.assertTrue(context["not_part_of_the_packet"])

    def test_the_signoff_template_is_unanswered(self):
        m, out = self.formal()
        template = json.loads((out / "signoff_template.json").read_text(encoding="utf-8"))
        self.assertEqual((template["desk"], template["signoff_schema"]),
                         ("vietnam", "vietnam-review-signoff/1"))
        self.assertEqual(template["automated_package_id"], m["deterministic_sha256"])
        self.assertEqual([r["identity"] for r in template["records"]], [EARLY, LATE])
        for record in template["records"]:
            self.assertEqual({record[f] for f in kit.CHECK_FIELDS}, {None})
        self.assertEqual([a["disposition"] for a in template["anomalies"]], [""])
        self.assertEqual((template["verdict"], template["reviewer"]), ("", ""))
        self.assertEqual(kit.check_signoff(out, out / "signoff_template.json")[:1],
                         ["reviewer is empty"])

    def test_inputs_are_unchanged_and_nothing_is_written_beside_them(self):
        state = self.copy_main()
        before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
        self.rehearsal(state)
        self.assertEqual(before, {p: p.read_bytes() for p in state.rglob("*") if p.is_file()})
        con = kit.open_readonly(state / "shadow.db")
        with self.assertRaises(sqlite3.OperationalError):
            con.execute("CREATE TABLE intruder (x)")
        con.close()


class TestRefusals(KitCase):
    def variant(self, mutate, message):
        """Commit a mutated copy of the main state on top of the state branch."""
        state = self.copy_main()
        mutate(state)
        repo = self.tmp / "repo"
        shutil.copytree(self.repo, repo, symlinks=True)
        return commit_state(repo, state, message=message), repo

    def test_a_commit_outside_the_state_history_is_refused(self):
        repo = self.tmp / "repo"
        shutil.copytree(self.repo, repo, symlinks=True)
        # Same tree, different history: a distinct root commit on another branch.
        stray = commit_state(repo, self.main_state, branch="stray", message="stray state")
        self.refused("not reachable from", commit=stray, repo=repo)

    def test_a_short_or_unknown_commit_is_refused(self):
        self.refused("full 40-character", commit=self.head[:12])
        self.refused("does not exist", commit="0" * 40)

    def test_another_desks_ledger_is_unrelated_state(self):
        commit, repo = self.variant(lambda s: self.edit_ledger(
            self.ledger_paths(s)[0], desk_id="singapore-mindef"), "foreign")
        self.refused("belongs to desk 'singapore-mindef'", commit=commit, repo=repo)

    def test_a_file_the_runner_never_writes_is_refused(self):
        commit, repo = self.variant(
            lambda s: (s / "notes.txt").write_text("hand-written", encoding="utf-8"), "notes")
        self.refused("never writes: notes.txt", commit=commit, repo=repo)

    def test_a_symlink_in_the_tree_is_refused(self):
        commit, repo = self.variant(
            lambda s: (s / "ledger" / "link.json").symlink_to("../clock.json"), "link")
        self.refused("regular files only", commit=commit, repo=repo)

    def test_a_database_of_another_shape_is_refused(self):
        def extra_table(s):
            with sqlite3.connect(str(s / "shadow.db")) as db:
                db.execute("CREATE TABLE shadow_notes (x)")
        commit, repo = self.variant(extra_table, "extra table")
        self.refused("creates exactly", commit=commit, repo=repo)

    def test_a_tree_without_a_clock_is_refused(self):
        commit, repo = self.variant(lambda s: (s / "clock.json").unlink(), "no clock")
        self.refused("no clock.json", commit=commit, repo=repo)

    def test_a_malformed_ledger_is_refused(self):
        commit, repo = self.variant(lambda s: self.edit_ledger(
            self.ledger_paths(s)[1], finished_utc=20261007), "malformed")
        self.refused("finished_utc; the Vietnam runner never writes that",
                     commit=commit, repo=repo)

    def test_arguments_that_mix_modes_or_targets_are_refused(self):
        with self.assertRaises(kit.ReviewError):
            kit.build(None, self.tmp / "p", "2026-10-10", state_commit=self.head,
                      checkpoint=None, state_repo=self.repo)
        with self.assertRaises(kit.ReviewError):
            kit.build(self.main_state, self.tmp / "p", "2026-10-10", state_commit=self.head,
                      checkpoint="day-07", state_repo=self.repo)
        with self.assertRaises(kit.ReviewError):
            kit.build(self.main_state, ROOT / "review-packet", "2026-10-10")
        with self.assertRaises(kit.ReviewError):
            kit.build(ROOT / "tests", self.tmp / "p", "2026-10-10")
        self.assertFalse((ROOT / "review-packet").exists())

    def test_the_cli_exits_2_on_refusal(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = kit.main(["--state-repo", str(self.repo), "--state-commit", "0" * 40,
                             "--checkpoint", "day-07", "--out", str(self.tmp / "p")])
        self.assertEqual(code, 2)
        self.assertIn("review refused", err.getvalue())


class TestTamperEvidence(KitCase):
    def anomalies(self, mutate):
        state = self.copy_main()
        mutate(state)
        m, _ = self.rehearsal(state)
        return m

    def test_altered_capture_bytes_are_found(self):
        def alter(s):
            path = sorted((s / "captures").glob("*.bin"))[0]
            path.write_bytes(path.read_bytes() + b" ")
        m = self.anomalies(alter)
        self.assertTrue(any("does not hash to its own name" in a for a in m["anomalies"]))

    def test_a_removed_ledger_breaks_the_chain_and_orphans_observations(self):
        m = self.anomalies(lambda s: self.ledger_paths(s)[1].unlink())
        self.assertEqual(m["state_chain_verdict"], "BROKEN")
        self.assertTrue(any("no ledger for this run" in a for a in m["anomalies"]))

    def test_ledger_counts_must_match_the_database(self):
        m = self.anomalies(lambda s: self.edit_ledger(self.ledger_paths(s)[1], new_records=2))
        self.assertIn("20261007T174109+0000-9002-1.json: ledger counts 2 new, the database "
                      "holds 1", m["anomalies"])

    def test_a_quiet_run_that_changed_the_database_is_flagged(self):
        m = self.anomalies(lambda s: self.edit_ledger(self.ledger_paths(s)[3],
                                                      state_sha256_after="0" * 64))
        self.assertIn("20261009T173630+0000-9004-1.json: a run with no publications changed "
                      "the database", m["anomalies"])

    def test_a_renamed_ledger_no_longer_matches_its_contents(self):
        def rename(s):
            path = self.ledger_paths(s)[2]
            path.rename(path.with_name(path.name.replace("9003-1", "9003-2")))
        m = self.anomalies(rename)
        self.assertTrue(any("does not match its contents" in a for a in m["anomalies"]))

    def test_an_edited_stored_text_is_found(self):
        def rewrite(s):
            with sqlite3.connect(str(s / "shadow.db")) as db:
                db.execute("UPDATE shadow_versions SET text_original = text_original || ' '"
                           " WHERE source_identity = ?", (LATE,))
        m = self.anomalies(rewrite)
        self.assertIn("%s: v%s:text:disagrees-with-blocks"
                      % (LATE, self.main_entries[1]["captures"][-1]["content_sha256"][:8]),
                      m["anomalies"])
        self.assertTrue(any("is not the last ledger's after-state" in a for a in m["anomalies"]))

    def test_a_foreign_collector_identity_is_found(self):
        m = self.anomalies(lambda s: self.edit_ledger(
            self.ledger_paths(s)[0], collector_identity="Mozilla/5.0"))
        self.assertTrue(any("is not the declared one" in a for a in m["anomalies"]))


class TestScenarios(KitCase):
    def build_state(self, plan, enabled=True):
        state = self.tmp / ("s%d" % len(list(self.tmp.iterdir()))) / "state"
        return state, collect(state, rigs(plan), enabled)

    def test_a_zero_record_period_has_nothing_to_pass(self):
        state, _ = self.build_state([((2026, 10, 6, 17, 40, 0), date(2026, 10, 6), 6,
                                      "1-1", SCHED, None)])
        repo = self.tmp / "zero-repo"
        commit = commit_state(repo, state)
        m, out = self.formal(commit=commit, repo=repo)
        self.assertEqual((m["corpus_count"], m["required_review_records"], m["anomalies"]),
                         (0, [], []))
        self.assertEqual(m["allowed_verdicts"], ["pass_with_findings", "fail"])
        report = (out / "review_report.md").read_text(encoding="utf-8")
        self.assertIn("No records to review", report)
        self.assertIn("evidence of listing access only", report)
        self.assertIn("A plain `pass` is not available for an empty corpus", report)
        signoff = filled(out, verdict="pass")
        self.assertIn("verdict 'pass' is not one of ['pass_with_findings', 'fail']",
                      kit.validate_signoff(m, signoff))

    def test_versions_and_the_collectors_own_anomalies_are_surfaced(self):
        state, entries = self.build_state([
            ((2026, 10, 6, 17, 40, 0), TARGET, LOOKBACK, "1-1", SCHED, None),
            ((2026, 10, 7, 17, 40, 0), TARGET, LOOKBACK, "2-1", SCHED, "edited"),
            ((2026, 10, 8, 17, 40, 0), TARGET, LOOKBACK, "3-1", SCHED, "moved"),
        ])
        self.assertEqual([(e["changed"], e["reverted"]) for e in entries],
                         [(0, 0), (1, 0), (0, 1)])
        m, out = self.rehearsal(state)
        collector = [a for a in m["anomalies"] if a.startswith("collector")]
        self.assertTrue(any(a.startswith("collector, run 3-1, %s: canonical_url_differs" % LATE)
                            for a in collector), collector)
        self.assertTrue(any(a.startswith("collector, run 3-1, %s: url_changed: first stored %s"
                                         % (LATE, URL[MAY[0]])) for a in collector))
        self.assertEqual(len(collector), len(entries[2]["anomalies"]))
        self.assertEqual(len(m["anomalies"]), len(collector), m["anomalies"])
        inventory = {r["identity"]: r for r in map(json.loads, (
            out / "record_inventory.jsonl").read_text().splitlines())}
        self.assertEqual([v["first_seen_run"] for v in inventory[LATE]["versions"]],
                         ["1-1", "2-1"])
        self.assertEqual(inventory[LATE]["current_content_sha256"],
                         inventory[LATE]["versions"][0]["content_sha256"])
        report = (out / "review_report.md").read_text(encoding="utf-8")
        self.assertIn("**Other stored versions:** `%s` (first seen in run 2-1)"
                      % inventory[LATE]["versions"][1]["content_sha256"][:12], report)

    def test_an_item_tagged_after_its_window_was_read_and_never_collected(self):
        state, _ = self.build_state([
            ((2026, 10, 6, 17, 40, 0), TARGET, LOOKBACK, "1-1", EXPL, "without-may1"),
            ((2026, 10, 7, 17, 40, 0), date(2026, 10, 7), 6, "2-1", SCHED, None),
        ])
        m, _ = self.rehearsal(state)
        late = [a for a in m["anomalies"] if a.startswith("late listing")]
        self.assertEqual(len(late), 1)
        self.assertIn("first listed in run 2-1; inside no later window, so it was NOT "
                      "collected", late[0])
        self.assertEqual(m["required_review_records"], [LATE])

    def test_missing_days_and_uncovered_dates_name_their_recovery(self):
        state, _ = self.build_state([
            ((2026, 10, 6, 17, 40, 0), date(2026, 10, 6), 6, "1-1", SCHED, None),
            ((2026, 10, 15, 17, 40, 0), date(2026, 10, 15), 6, "2-1", SCHED, None),
        ])
        repo = self.tmp / "gap-repo"
        commit = commit_state(repo, state)
        m, _ = self.formal(commit=commit, repo=repo)
        self.assertEqual((m["latest_shadow_day"], m["checkpoint_reached"]), (9, True))
        self.assertEqual(m["missing_collecting_days"],
                         ["2026-10-%02d" % d for d in range(7, 15)])
        self.assertEqual(m["consecutive_collecting_days"], 1)
        self.assertEqual(m["uncovered_dates"], [["2026-10-07", "2026-10-08"]])
        self.assertIn("logical dates 2026-10-07 to 2026-10-08, inside the shadow period, lie in "
                      "no proven window; recover by dispatching target_date 2026-10-08 (each "
                      "covers that date and the six before it)", m["anomalies"])

    def test_history_read_by_a_dated_dispatch_opens_no_gap(self):
        m, _ = self.formal()
        self.assertIn(["2026-05-21", "2026-05-24"], m["window_coverage"])
        self.assertEqual(m["uncovered_dates"], [])

    def test_a_disabled_source_is_neither_a_collecting_day_nor_an_anomaly(self):
        state, _ = self.build_state([
            ((2026, 10, 6, 17, 40, 0), date(2026, 10, 6), 6, "1-1", SCHED, None)])
        collect(state, [((2026, 10, 7, 3, 0, 0), date(2026, 10, 7), 6, "2-1", SCHED, Rig())],
                enabled=False)
        collect(state, [((2026, 10, 7, 17, 40, 0), date(2026, 10, 7), 6, "3-1", SCHED, Rig())])
        m, out = self.rehearsal(state)
        self.assertEqual(m["anomalies"], [])
        self.assertEqual(m["collecting_days"], ["2026-10-06", "2026-10-07"])
        runs = [json.loads(line) for line in (out / "run_inventory.jsonl").read_text().splitlines()]
        self.assertEqual([(r["result"], r["health"], r["shadow_day"]) for r in runs],
                         [(st.OK_NO_PUBLICATIONS, "ok", 0), (st.SKIPPED_DISABLED, "skipped", None),
                          (st.OK_NO_PUBLICATIONS, "ok", 1)])

    def test_a_failed_run_in_a_rehearsal_is_disclosed(self):
        state, _ = self.build_state([
            ((2026, 10, 6, 17, 40, 0), date(2026, 10, 6), 6, "1-1", SCHED, None)])
        collect(state, [((2026, 10, 7, 17, 40, 0), TARGET, LOOKBACK, "2-1", SCHED,
                         Rig(routes({URL[MAY[0]]: FakeResponse(b"gone", 404)})))])
        m, _ = self.rehearsal(state)
        self.assertTrue(any("run 2-1 did not succeed: fetch_failure" in a
                            for a in m["anomalies"]), m["anomalies"])


def filled(out, verdict="pass", answer=True):
    signoff = json.loads((out / "signoff_template.json").read_text(encoding="utf-8"))
    signoff.update(reviewer="A. Reviewer", attestation="I compared every record with its page.",
                   review_started_utc="2026-10-10T09:00:00+00:00",
                   review_completed_utc="2026-10-10T10:30:00+00:00", verdict=verdict)
    for record in signoff["records"]:
        record.update({f: answer for f in kit.CHECK_FIELDS})
    for anomaly in signoff["anomalies"]:
        anomaly["disposition"] = "Tagged late by the newsroom; collected by run 9003-1."
    return signoff


class TestSignoff(KitCase):
    def write(self, signoff):
        path = self.tmp / "signoff.json"
        path.write_text(json.dumps(signoff), encoding="utf-8")
        return path

    def test_a_complete_signoff_on_a_formal_packet_passes(self):
        m, out = self.formal()
        self.assertEqual(kit.check_signoff(out, self.write(filled(out))), [])
        with redirect_stdout(io.StringIO()) as printed:
            code = kit.main(["--out", str(out), "--check-signoff", str(self.write(filled(out)))])
        self.assertEqual((code, printed.getvalue().strip()), (0, "sign-off complete"))

    def test_pass_is_refused_when_a_check_failed(self):
        m, out = self.formal()
        signoff = filled(out)
        signoff["records"][0]["title_matches"] = False
        self.assertIn("verdict pass with a check answered false; use pass_with_findings or fail",
                      kit.validate_signoff(m, signoff))
        signoff["verdict"] = "pass_with_findings"
        self.assertEqual(kit.validate_signoff(m, signoff), [])

    def test_unanswered_checks_and_undisposed_anomalies_are_listed(self):
        m, out = self.formal()
        signoff = filled(out)
        signoff["records"][1]["body_appears_complete"] = "yes"
        signoff["anomalies"][0]["disposition"] = " "
        problems = kit.validate_signoff(m, signoff)
        self.assertIn("%s: body_appears_complete must be true or false, not 'yes'" % LATE, problems)
        self.assertTrue(any(p.startswith("anomaly has no disposition: late listing") for p in problems))

    def test_a_signoff_must_answer_this_packet(self):
        m, out = self.formal()
        signoff = filled(out)
        signoff["automated_package_id"] = "0" * 64
        signoff["records"] = signoff["records"][:1]
        problems = kit.validate_signoff(m, signoff)
        self.assertIn("automated_package_id does not name this packet", problems)
        self.assertIn("records must be exactly the 2 required identities", problems)

    def test_a_rehearsal_cannot_be_signed_off(self):
        m, out = self.rehearsal(self.main_state)
        self.assertIn("the packet is a rehearsal; only a formal packet can be signed off",
                      kit.validate_signoff(m, filled(out)))

    def test_an_altered_packet_is_refused(self):
        m, out = self.formal()
        manifest = json.loads((out / "review_manifest.json").read_text(encoding="utf-8"))
        manifest["allowed_verdicts"] = ["pass"]
        (out / "review_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(kit.ReviewError) as caught:
            kit.check_signoff(out, self.write(filled(out)))
        self.assertIn("the packet was altered", str(caught.exception))


class TestEquivalence(KitCase):
    """The kit re-declares what it needs; these pin it to the code it reviews."""

    def test_columns_are_exactly_the_runners_schema(self):
        con = sqlite3.connect(":memory:")
        con.executescript(runner.SCHEMA)
        tables = sorted(r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"))
        self.assertEqual(tables, sorted(kit.EXPECTED_COLUMNS))
        for table, cols in kit.EXPECTED_COLUMNS.items():
            self.assertEqual(tuple(r[1] for r in con.execute("PRAGMA table_info(%s)" % table)),
                             cols)

    def test_required_ledger_keys_match_every_runner_exit_path(self):
        state = self.tmp / "paths" / "state"
        collect(state, [((2026, 10, 6, 17, 40, 0), TARGET, LOOKBACK, "ok-1", SCHED, None)])
        robots = Rig(routes({vgp.ROBOTS: FakeResponse(b"User-agent: *\nDisallow: /\n",
                                                      headers={"Content-Type": "text/plain"})}))
        collect(state, [((2026, 10, 6, 17, 41, 0), TARGET, LOOKBACK, "robots-1", SCHED, robots)])
        collect(state, [((2026, 10, 6, 17, 42, 0), TARGET, LOOKBACK, "skip-1", SCHED, Rig())],
                enabled=False)
        collect(state, [((2026, 10, 6, 17, 43, 0), TARGET, LOOKBACK, "gone-1", SCHED,
                         Rig(routes({URL[MAY[1]]: FakeResponse(b"x", 404)})))])
        ledgers = [json.loads(p.read_text(encoding="utf-8"))
                   for p in sorted((state / "ledger").glob("*.json"))]
        self.assertEqual([e["result"] for e in ledgers],
                         [st.OK, st.AUTH_FAILURE, st.SKIPPED_DISABLED, st.FETCH_FAILURE])
        for entry in ledgers + [json.loads(p.read_text()) for p in
                                sorted((self.main_state / "ledger").glob("*.json"))]:
            with self.subTest(result=entry["result"], run=entry["run_id"]):
                self.assertEqual(set(kit.LEDGER_REQUIRED) - set(entry), set())
                self.assertLessEqual(set(entry) - set(kit.LEDGER_REQUIRED), LEDGER_OPTIONAL)

    def test_mirrored_constants_equal_the_adapters(self):
        for name in ("HOSTNAME", "LISTING", "IDENTITY_PREFIX", "CONTENT_HASH_RULE",
                     "USER_AGENT"):
            self.assertEqual(getattr(kit, name), getattr(vgp, name), name)
        self.assertEqual(kit.ARTICLE_PATH_RE.pattern, vgp.ARTICLE_PATH_RE.pattern)
        self.assertEqual(kit.TARGET_DATE_SOURCES, shadow_schedule.SOURCES)
        self.assertEqual((kit.DESK_IDENTITY, kit.SOURCE_SLUG),
                         (runner.DESK_ID, runner.load_source().slug))
        manifest = json.loads((ROOT / "shadow/vietnam/manifest.json").read_text())
        zone = ZoneInfo(manifest["desk"]["default_timezone"])
        for day in (date(2026, 1, 15), date(2026, 7, 15)):
            self.assertEqual(datetime(day.year, day.month, day.day, tzinfo=zone).utcoffset(),
                             kit.HANOI.utcoffset(None))

    def test_identity_hashing_and_text_assembly_match_every_captured_page(self):
        for item in sorted(PAGES):
            with self.subTest(item=item):
                result = extract(BIN[item], item_id=item)
                self.assertEqual(result.status, st.OK)
                doc = result.documents[0]
                x = doc.extra
                self.assertEqual(kit.content_sha256(doc.title_original, x["lead_original"],
                                                    x["blocks"]), x["content_sha256"])
                self.assertEqual(kit.assembled_text(x["lead_original"], x["blocks"]),
                                 doc.text_original)
                self.assertEqual(x["publication_kind"], kit.PUBLICATION_KIND)
                self.assertIn(x["body_status"], kit.BODY_STATUSES)
                stamp = kit.stamp_facts(x["published_at_original"])
                self.assertEqual(stamp, (doc.published_date, x["published_at_utc"]))
        for url in list(URL.values()) + [
                vgp.LISTING, "http://en.baochinhphu.vn/a-111260523144123151.htm",
                URL[MAY[0]] + "?x=1", URL[MAY[0]] + "#top", "https://baochinhphu.vn/a-1.htm",
                "https://en.baochinhphu.vn/a-b-12.htm", "https://en.baochinhphu.vn/12.htm",
                "not a url", ""]:
            self.assertEqual(kit.article_id(url), vgp.article_id(url), url)

    def test_the_kit_imports_no_adapter_network_or_production_code(self):
        tree = ast.parse((ROOT / "scripts/review_vietnam_shadow_state.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported - {"__future__", "argparse", "hashlib", "json", "re", "shutil",
                                     "sqlite3", "sys", "tempfile", "collections", "datetime",
                                     "pathlib", "urllib.parse"},
                         {"core.collection", "scripts.review_shadow_state"})

    def test_singapores_reviewer_and_publisher_are_not_redirected(self):
        from scripts import publish_shadow_review, review_shadow_state
        self.assertEqual((publish_shadow_review.DESK_IDENTITY, publish_shadow_review.REVIEW_BRANCH),
                         ("singapore-mindef", "review/singapore-mindef"))
        self.assertEqual(review_shadow_state.DESK_IDENTITY, "singapore-mindef")
        text = (ROOT / "scripts/review_vietnam_shadow_state.py").read_text()
        self.assertNotIn("publish_shadow_review", text)
        self.assertNotIn("review/vietnam", text)


if __name__ == "__main__":
    unittest.main()
