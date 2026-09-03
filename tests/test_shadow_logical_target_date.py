"""
The logical collection date of a shadow run.

Both real boundary cases below came out of the Singapore Day 7 and Day 14
checkpoint reviews and are preserved in the published review evidence on
`review/singapore-mindef`. They are the reason this resolver exists, so they
are pinned here as data rather than described in prose.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.collection import status as st
from core.shadow_schedule import (
    SOURCES, SOURCE_EXPLICIT, SOURCE_MANUAL, SOURCE_SCHEDULE, ScheduleError,
    parse_cron_utc, parse_iso_date, parse_run_attempt, resolve_target_date,
    scheduled_slot_date)

REPO_ROOT = Path(__file__).resolve().parent.parent
SG_CRON = "21:10"
JP_CRON = "22:40"


def utc(text):
    return datetime.fromisoformat(text)


class TestTheTwoRealDelayedRuns(unittest.TestCase):
    """The observed failures, as recorded by GitHub Actions."""

    def test_run_33027905549_belongs_to_2026_08_26(self):
        # created 2026-08-27T00:45:40Z; stamped 2026-08-27; nominal 2026-08-26
        self.assertEqual(
            resolve_target_date(utc("2026-08-27T00:45:40+00:00"), "schedule", SG_CRON),
            (date(2026, 8, 26), SOURCE_SCHEDULE))

    def test_run_33455386368_belongs_to_2026_08_31(self):
        # created 2026-09-01T00:35:45Z; stamped 2026-09-01; nominal 2026-08-31
        self.assertEqual(
            resolve_target_date(utc("2026-09-01T00:35:45+00:00"), "schedule", SG_CRON),
            (date(2026, 8, 31), SOURCE_SCHEDULE))

    def test_the_delayed_run_and_the_next_on_time_run_differ(self):
        """
        The property that stops two ledgers sharing one date. Before the fix
        both 33455386368 (00:35 on 09-01) and 33570252031 (23:16 on 09-01)
        stamped 2026-09-01.
        """
        delayed, _ = resolve_target_date(
            utc("2026-09-01T00:35:45+00:00"), "schedule", SG_CRON)
        on_time, _ = resolve_target_date(
            utc("2026-09-01T23:16:19+00:00"), "schedule", SG_CRON)
        self.assertEqual(delayed, date(2026, 8, 31))
        self.assertEqual(on_time, date(2026, 9, 1))
        self.assertNotEqual(delayed, on_time)

    def test_a_run_delayed_eight_hours_still_lands_on_its_own_slot(self):
        # run 33144486791, created 2026-08-28T05:20:55Z
        self.assertEqual(
            resolve_target_date(utc("2026-08-28T05:20:55+00:00"), "schedule", SG_CRON)[0],
            date(2026, 8, 27))

    def test_the_repaired_sequence_has_no_duplicate_and_no_gap(self):
        """Every real Singapore run from 08-24 to 09-02, in order."""
        started = ["2026-08-24T21:41:24+00:00", "2026-08-25T21:40:14+00:00",
                   "2026-08-27T00:45:40+00:00", "2026-08-28T05:20:55+00:00",
                   "2026-08-29T03:08:52+00:00", "2026-08-29T23:15:44+00:00",
                   "2026-08-30T23:27:04+00:00", "2026-09-01T00:35:45+00:00",
                   "2026-09-01T23:16:19+00:00", "2026-09-02T23:17:09+00:00"]
        got = [resolve_target_date(utc(s), "schedule", SG_CRON)[0] for s in started]
        self.assertEqual(got, sorted(got), "logical dates must be non-decreasing")
        self.assertEqual(len(set(got)), len(got), "no two runs share a logical date")
        self.assertEqual(got[0], date(2026, 8, 24))
        self.assertEqual(got[-1], date(2026, 9, 2))
        # a contiguous run of days: exactly one per calendar day, no hole
        self.assertEqual(
            got, [date(2026, 8, 24) + timedelta(days=i) for i in range(len(got))])


class TestSlotBoundary(unittest.TestCase):

    def test_before_the_cron_time_after_utc_midnight(self):
        self.assertEqual(
            scheduled_slot_date(utc("2026-09-03T00:00:01+00:00"), SG_CRON),
            date(2026, 9, 2))

    def test_one_minute_before_the_boundary(self):
        self.assertEqual(
            scheduled_slot_date(utc("2026-09-03T21:09:59+00:00"), SG_CRON),
            date(2026, 9, 2))

    def test_exactly_at_the_boundary_is_the_same_day(self):
        self.assertEqual(
            scheduled_slot_date(utc("2026-09-03T21:10:00+00:00"), SG_CRON),
            date(2026, 9, 3))

    def test_after_the_boundary_is_the_same_day(self):
        self.assertEqual(
            scheduled_slot_date(utc("2026-09-03T21:10:01+00:00"), SG_CRON),
            date(2026, 9, 3))

    def test_a_non_utc_offset_is_converted_not_assumed(self):
        # 2026-09-03T09:45+09:00 is 2026-09-03T00:45Z — before the slot.
        self.assertEqual(
            scheduled_slot_date(
                datetime.fromisoformat("2026-09-03T09:45:00+09:00"), SG_CRON),
            date(2026, 9, 2))


class TestJapanIsAffectedTheSameWay(unittest.TestCase):
    """22:40 UTC is eighty minutes from midnight — the more exposed cron."""

    def test_a_delayed_japan_run_belongs_to_the_previous_day(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-03T00:12:00+00:00"), "schedule", JP_CRON),
            (date(2026, 9, 2), SOURCE_SCHEDULE))

    def test_an_on_time_japan_run_keeps_its_own_day(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-02T22:41:30+00:00"), "schedule", JP_CRON),
            (date(2026, 9, 2), SOURCE_SCHEDULE))

    def test_consecutive_delayed_then_on_time_japan_runs_differ(self):
        a, _ = resolve_target_date(utc("2026-09-03T00:12:00+00:00"), "schedule", JP_CRON)
        b, _ = resolve_target_date(utc("2026-09-03T22:45:00+00:00"), "schedule", JP_CRON)
        self.assertNotEqual(a, b)


class TestTheRealJapanLedgerSequence(unittest.TestCase):
    """
    Japan is not the milder case. Its cron sits at 22:40 UTC and Actions has
    started every scheduled Japan run late enough to cross midnight, so every
    ledger written before the fix is stamped a day after its slot. These start
    times are the real ones, read from `shadow/jp-mod` on 2026-09-03.
    """

    #: (run id, started_utc, the date the ledger actually recorded)
    LEDGERS = (
        ("33032633240", "2026-08-27T02:14:34+00:00", "2026-08-27"),
        ("33036656277", "2026-08-27T03:32:42+00:00", "2026-08-27"),
        ("33147429840", "2026-08-28T06:17:51+00:00", "2026-08-28"),
        ("33232394996", "2026-08-29T03:51:06+00:00", "2026-08-29"),
        ("33283822684", "2026-08-30T00:39:51+00:00", "2026-08-30"),
        ("33345652417", "2026-08-31T00:48:45+00:00", "2026-08-31"),
        ("33458500053", "2026-09-01T01:23:11+00:00", "2026-09-01"),
        ("33575561889", "2026-09-02T00:30:21+00:00", "2026-09-02"),
        ("33700195896", "2026-09-03T00:36:36+00:00", "2026-09-03"),
    )

    def test_every_recorded_japan_ledger_is_a_day_late(self):
        for run_id, started, recorded in self.LEDGERS:
            with self.subTest(run=run_id):
                fixed, source = resolve_target_date(
                    utc(started), "schedule", JP_CRON, None, 1)
                self.assertEqual(source, SOURCE_SCHEDULE)
                self.assertEqual(
                    fixed, date.fromisoformat(recorded) - timedelta(days=1),
                    "run %s should belong to the day before %s"
                    % (run_id, recorded))

    def test_run_33700195896_belongs_to_2026_09_02(self):
        """
        The occurrence that happened *after* this defect was reported — the
        reason Japan could not be left for a follow-up change.
        """
        self.assertEqual(
            resolve_target_date(utc("2026-09-03T00:36:36+00:00"),
                                "schedule", JP_CRON, None, 1),
            (date(2026, 9, 2), SOURCE_SCHEDULE))

    def test_the_repaired_japan_sequence_has_no_duplicate_after_day_zero(self):
        """
        Day zero ran twice on 2026-08-27, so that pair stays a pair. Every
        other slot-dated run is distinct and consecutive.
        """
        fixed = [resolve_target_date(utc(s), "schedule", JP_CRON, None, 1)[0]
                 for _, s, _ in self.LEDGERS]
        self.assertEqual(fixed[0], fixed[1], "the day-zero pair is real")
        rest = fixed[1:]
        self.assertEqual(len(set(rest)), len(rest), "duplicate slot date")
        for earlier, later in zip(rest, rest[1:]):
            self.assertEqual(later - earlier, timedelta(days=1),
                             "gap in the repaired sequence")

    def test_the_changeover_duplicates_one_japan_date(self):
        """
        Stated rather than smoothed. The last execution-dated ledger carries
        2026-09-03; the first slot-dated run carries it too, so nominal
        2026-09-02 acquires no Japan ledger. Documented in PROJECT_STATE.md,
        DECISION_LOG.md and docs/SHADOW_REVIEW.md, and deliberately not fixed
        by rewriting a ledger.
        """
        last_pre_fix = date(2026, 9, 3)
        for executed_at in ("2026-09-03T23:05:00+00:00",
                            "2026-09-04T00:35:00+00:00"):
            with self.subTest(executed=executed_at):
                first_post_fix, _ = resolve_target_date(
                    utc(executed_at), "schedule", JP_CRON, None, 1)
                self.assertEqual(first_post_fix, last_pre_fix)

    def test_the_qualification_clock_does_not_read_the_target_date(self):
        """
        `shadow_day` is derived from `finished_utc` against day zero, so
        changing the logical date moves no day count in either collector.
        """
        for script in ("shadow_collect.py", "shadow_collect_japan.py"):
            with self.subTest(script=script):
                src = (REPO_ROOT / "scripts" / script).read_text(encoding="utf-8")
                body = src.split('entry["shadow_day"] =', 1)[1][:200]
                self.assertIn("finished_utc", body)
                self.assertNotIn("target_date", body)


class TestManualDispatchCannotMasqueradeAsASlot(unittest.TestCase):

    def test_manual_dispatch_records_the_actual_utc_date(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-03T00:45:00+00:00"),
                                "workflow_dispatch", SG_CRON),
            (date(2026, 9, 3), SOURCE_MANUAL))

    def test_manual_dispatch_does_not_borrow_the_previous_slot(self):
        """A hand-started run at 00:45 is not yesterday's scheduled run."""
        manual, _ = resolve_target_date(
            utc("2026-09-03T00:45:00+00:00"), "workflow_dispatch", SG_CRON)
        scheduled, _ = resolve_target_date(
            utc("2026-09-03T00:45:00+00:00"), "schedule", SG_CRON)
        self.assertNotEqual(manual, scheduled)

    def test_no_event_name_is_treated_as_manual(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-03T00:45:00+00:00"), None, SG_CRON)[1],
            SOURCE_MANUAL)

    def test_an_explicit_date_always_wins_and_says_so(self):
        self.assertEqual(
            resolve_target_date(utc("2026-09-03T00:45:00+00:00"), "schedule",
                                SG_CRON, "2026-07-04"),
            (date(2026, 7, 4), SOURCE_EXPLICIT))


class TestFailClosed(unittest.TestCase):

    def test_a_scheduled_run_without_a_cron_time_is_refused(self):
        """The old fallthrough is the bug; it must not be reachable silently."""
        with self.assertRaises(ScheduleError):
            resolve_target_date(utc("2026-09-03T00:45:00+00:00"), "schedule", None)

    def test_a_naive_timestamp_is_refused(self):
        with self.assertRaises(ScheduleError):
            resolve_target_date(datetime(2026, 9, 3, 0, 45), "schedule", SG_CRON)

    def test_a_malformed_explicit_date_is_refused(self):
        for bad in ("2026-9-3", "03-09-2026", "20260903", "yesterday", "", "  "):
            with self.subTest(bad=bad):
                with self.assertRaises(ScheduleError):
                    parse_iso_date(bad)

    def test_an_impossible_explicit_date_is_refused(self):
        with self.assertRaises(ScheduleError):
            parse_iso_date("2026-02-30")

    def test_a_malformed_cron_time_is_refused(self):
        for bad in ("24:00", "21:60", "9:10", "2110", "21:10:00", "", None):
            with self.subTest(bad=bad):
                with self.assertRaises(ScheduleError):
                    parse_cron_utc(bad)

    def test_a_valid_cron_time_parses(self):
        self.assertEqual(parse_cron_utc("21:10"), (21, 10))
        self.assertEqual(parse_cron_utc("00:00"), (0, 0))
        self.assertEqual(parse_cron_utc("23:59"), (23, 59))


class TestWorkflowsAgreeWithTheirCollectors(unittest.TestCase):
    """
    The cron in the YAML and the --cron-utc passed to the collector are two
    copies of one fact. A test is what keeps them equal.
    """

    CASES = (("singapore_shadow.yml", "shadow_collect.py"),
             ("japan_shadow.yml", "shadow_collect_japan.py"))

    def workflow(self, name):
        return (REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_each_workflow_passes_its_own_cron_time(self):
        for wf, script in self.CASES:
            with self.subTest(workflow=wf):
                text = self.workflow(wf)
                crons = re.findall(r"- cron:\s*'(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*'", text)
                self.assertEqual(len(crons), 1, "expected exactly one cron in %s" % wf)
                minute, hour = crons[0]
                passed = re.findall(r'--cron-utc\s+"(\d{2}):(\d{2})"', text)
                self.assertEqual(len(passed), 1, "expected one --cron-utc in %s" % wf)
                self.assertEqual((int(passed[0][0]), int(passed[0][1])),
                                 (int(hour), int(minute)),
                                 "%s cron and --cron-utc disagree" % wf)

    def test_each_workflow_passes_the_event_name(self):
        for wf, _ in self.CASES:
            with self.subTest(workflow=wf):
                self.assertIn('--event-name "${GITHUB_EVENT_NAME}"', self.workflow(wf))

    def test_neither_workflow_pins_a_literal_target_date(self):
        """
        A hard-coded date would defeat the resolver entirely. `--target-date`
        may appear only as the guarded dispatch variable, never as a literal.
        """
        for wf, _ in self.CASES:
            with self.subTest(workflow=wf):
                text = self.workflow(wf)
                self.assertEqual(
                    re.findall(r"--target-date\s+\S+", text),
                    ['--target-date "${TARGET_DATE}"'],
                    "%s passes --target-date as something other than the "
                    "guarded dispatch input" % wf)

    def test_each_workflow_passes_the_run_attempt(self):
        """Without it every re-run looks like a first attempt."""
        for wf, _ in self.CASES:
            with self.subTest(workflow=wf):
                self.assertIn('--run-attempt "${GITHUB_RUN_ATTEMPT}"',
                              self.workflow(wf))

    def test_each_workflow_offers_a_manual_target_date_input(self):
        """
        The recovery path for a refused re-run has to exist in the UI.

        Read as text, not with a parser: `tests/test_workflow_yaml_shape.py`
        records that PyYAML is deliberately not a dependency of this project,
        so a workflow assertion has to be structural.
        """
        for wf, _ in self.CASES:
            with self.subTest(workflow=wf):
                text = self.workflow(wf)
                block = re.search(
                    r"(?m)^  workflow_dispatch:\n((?:^    .*\n|^\n)*)", text)
                self.assertIsNotNone(
                    block, "%s has no indented workflow_dispatch block" % wf)
                body = block.group(1)
                self.assertRegex(body, r"(?m)^    inputs:$")
                self.assertRegex(body, r"(?m)^      target_date:$")
                self.assertRegex(body, r"(?m)^        required: false$")
                self.assertRegex(body, r"(?m)^        default: ''$")

    def test_the_dispatch_input_reaches_the_shell_through_the_environment(self):
        """
        `${{ inputs.target_date }}` interpolated into a `run:` body would be a
        script-injection sink. It travels as an environment variable instead,
        and the collector's own ISO-date check is what rejects its content.
        """
        for wf, _ in self.CASES:
            with self.subTest(workflow=wf):
                text = self.workflow(wf)
                self.assertEqual(
                    re.findall(r".*\$\{\{ inputs\.target_date \}\}.*", text),
                    ["          TARGET_DATE: ${{ inputs.target_date }}"],
                    "%s expands the dispatch input somewhere other than the "
                    "step's env: block" % wf)
                self.assertNotIn("${{ inputs", text.split("env:", 1)[0])

    def test_an_empty_dispatch_input_passes_no_target_date_at_all(self):
        """
        The guard, run as shell. An unset or empty input must produce zero
        arguments — passing `--target-date ""` would refuse every scheduled
        run, turning a recovery affordance into an outage.
        """
        guard = None
        for wf, _ in self.CASES:
            text = self.workflow(wf)
            start = text.index('if [ -n "${TARGET_DATE:-}" ]; then')
            end = text.index("fi\n", start) + 3
            snippet = textwrap.dedent(text[start:end])
            if guard is None:
                guard = snippet
            self.assertEqual(snippet, guard, "%s guards differently" % wf)

        script = ("set -euo pipefail\n" + guard
                  + 'printf "%s\\n" "$#"\nfor a in "$@"; do printf "[%s]\\n" "$a"; done\n')

        def sh(env):
            full = dict(os.environ)
            full.pop("TARGET_DATE", None)
            full.update(env)
            out = subprocess.run(["bash", "-c", script], env=full,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True)
            self.assertEqual(out.returncode, 0, out.stdout)
            return out.stdout.splitlines()

        self.assertEqual(sh({}), ["0"])
        self.assertEqual(sh({"TARGET_DATE": ""}), ["0"])
        self.assertEqual(sh({"TARGET_DATE": "2026-08-31"}),
                         ["2", "[--target-date]", "[2026-08-31]"])
        # A hostile value stays one argument and never reaches the shell as
        # syntax; `parse_iso_date` is what refuses it.
        self.assertEqual(sh({"TARGET_DATE": "2026-08-31; touch /tmp/pwned"}),
                         ["2", "[--target-date]", "[2026-08-31; touch /tmp/pwned]"])
        with self.assertRaises(ScheduleError):
            parse_iso_date("2026-08-31; touch /tmp/pwned")


class TestARerunIsRefusedRatherThanReDated(unittest.TestCase):
    """
    `GITHUB_RUN_ATTEMPT` begins at 1 and increments on each re-run. A re-run
    keeps the original run id, ref, commit and triggering event — but not the
    original moment. Re-running a scheduled job a day later therefore arrives
    looking like a first attempt while `started` names a different slot, and
    re-running a dispatch simply re-dates it. Neither is unambiguous, so
    neither is inferred.
    """

    LATER = utc("2026-09-03T11:00:00+00:00")

    def test_a_scheduled_rerun_without_a_date_is_refused(self):
        with self.assertRaises(ScheduleError) as caught:
            resolve_target_date(self.LATER, "schedule", SG_CRON, None, 2)
        self.assertIn("attempt 2", str(caught.exception))

    def test_a_scheduled_rerun_with_an_explicit_date_succeeds(self):
        """The explicit date stays authoritative on a re-run. It is the fix."""
        self.assertEqual(
            resolve_target_date(self.LATER, "schedule", SG_CRON,
                                "2026-08-31", 2),
            (date(2026, 8, 31), SOURCE_EXPLICIT))

    def test_a_dispatched_rerun_without_a_date_is_refused(self):
        """
        Manual dispatch is not the safe category. A re-run of a dispatch
        recomputes `datetime.now()`, so a re-run two days later would record
        the day of the re-run and say `manual-utc-date` while doing it.
        """
        with self.assertRaises(ScheduleError):
            resolve_target_date(self.LATER, "workflow_dispatch", None, None, 2)

    def test_a_dispatched_rerun_with_an_explicit_date_succeeds(self):
        self.assertEqual(
            resolve_target_date(self.LATER, "workflow_dispatch", None,
                                "2026-09-01", 3),
            (date(2026, 9, 1), SOURCE_EXPLICIT))

    def test_a_rerun_of_a_run_with_no_event_name_is_also_refused(self):
        with self.assertRaises(ScheduleError):
            resolve_target_date(self.LATER, None, None, None, 2)

    def test_the_refusal_names_the_recovery(self):
        """An error an operator cannot act on is only half a refusal."""
        with self.assertRaises(ScheduleError) as caught:
            resolve_target_date(self.LATER, "schedule", SG_CRON, None, 2)
        message = str(caught.exception)
        self.assertIn("target_date", message)
        self.assertIn("--target-date YYYY-MM-DD", message)
        self.assertIn("Run workflow", message)

    def test_attempt_one_is_the_ordinary_path_for_both_desks(self):
        """11:00 UTC precedes both crons, so both resolve to the day before."""
        for cron in (SG_CRON, JP_CRON):
            with self.subTest(cron=cron):
                self.assertEqual(
                    resolve_target_date(self.LATER, "schedule", cron, None, 1),
                    (date(2026, 9, 2), SOURCE_SCHEDULE))

    def test_the_default_attempt_is_one_so_local_calls_are_unaffected(self):
        self.assertEqual(
            resolve_target_date(self.LATER, "schedule", SG_CRON),
            (date(2026, 9, 2), SOURCE_SCHEDULE))


class TestTheRunAttemptItselfMustBeReadable(unittest.TestCase):
    """
    An attempt number this module cannot read is not treated as 1: it means the
    caller cannot tell a first run from a re-run, which is exactly the state in
    which a date must not be inferred.
    """

    GOOD = utc("2026-09-03T11:00:00+00:00")

    def test_a_positive_integer_parses_from_int_or_string(self):
        for value, expected in ((1, 1), ("1", 1), (7, 7), ("7", 7), (" 2 ", 2)):
            with self.subTest(value=value):
                self.assertEqual(parse_run_attempt(value), expected)

    def test_zero_is_refused(self):
        with self.assertRaises(ScheduleError) as caught:
            parse_run_attempt(0)
        self.assertIn("at least 1", str(caught.exception))

    def test_a_negative_attempt_is_refused(self):
        for value in (-1, "-1", "-0"):
            with self.subTest(value=value):
                with self.assertRaises(ScheduleError):
                    parse_run_attempt(value)

    def test_malformed_attempts_are_refused(self):
        for value in ("", "   ", None, "abc", "1.5", "2a", "one", "1e3",
                      "+1", "1_0", "\u0662"):
            with self.subTest(value=value):
                with self.assertRaises(ScheduleError):
                    parse_run_attempt(value)

    def test_a_malformed_attempt_is_refused_even_with_an_explicit_date(self):
        """
        Validated before anything else. An explicit date makes *this* run's
        date unambiguous, but an unreadable attempt number means the workflow
        contract itself is broken, and that should fail on its first run.
        """
        with self.assertRaises(ScheduleError):
            resolve_target_date(self.GOOD, "schedule", SG_CRON,
                                "2026-08-31", "not-a-number")

    def test_a_malformed_attempt_refuses_an_ordinary_scheduled_run(self):
        with self.assertRaises(ScheduleError):
            resolve_target_date(self.GOOD, "schedule", SG_CRON, None, "")


# ── the collectors, end to end ───────────────────────────────────────────────

def _load_collector(script):
    """
    Imported by path, the way the review-kit tests do it, so that importing one
    collector does not put the other's module name in `sys.modules`.
    """
    spec = importlib.util.spec_from_file_location(
        "collector_" + script.replace(".py", ""), REPO_ROOT / "scripts" / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Discovery:
    """
    Enough of a discovery result for the no-publications path. The status comes
    from the collector's own constant rather than a copy of its value: a stub
    that hardcoded the string would quietly take a different branch if the
    taxonomy ever moved.
    """
    status = st.OK_NO_PUBLICATIONS
    ok = False
    references = ()
    error_detail = None


class _StubAdapter:
    slug = "jp_mod_news_ja"

    def discover(self, window):
        return _Discovery()


class CollectorCase(unittest.TestCase):

    SCRIPT = None

    def setUp(self):
        self.mod = _load_collector(self.SCRIPT)
        # Outside the repository: both collectors refuse a state dir inside it.
        self.tmp = Path(tempfile.mkdtemp(prefix="logical-date-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = self.tmp / "state"

    def ledger(self):
        paths = sorted((self.state / "ledger").glob("*.json"))
        self.assertEqual(len(paths), 1, "expected exactly one ledger")
        return json.loads(paths[0].read_text(encoding="utf-8"))

    def argv(self, *extra):
        return ["--state-dir", str(self.state), "--run-id", "test-run",
                "--commit", "testsha"] + list(extra)


class TestTheCollectorsRecordTheProvenance(CollectorCase):
    """
    The wiring, not just the resolver: argparse -> resolve_target_date ->
    `run(target_source=...)` -> the ledger on disk. Asserted for both desks.
    """

    SCRIPT = "shadow_collect.py"

    def capture(self, *extra):
        """Run `main` with the storage layer replaced by a recorder."""
        seen = {}

        class Entry(dict):
            """Answers 0 for anything a desk's summary happens to print."""
            def __missing__(self, key):
                return 0

        def fake_run(state_dir, target, lookback, cap, run_id, commit,
                     adapter=None, target_source=None):
            seen.update(target=target, target_source=target_source)
            return Entry(result="ok", health="ok", content_hashes=[])

        real, self.mod.run = self.mod.run, fake_run
        try:
            code = self.mod.main(self.argv(*extra))
        finally:
            self.mod.run = real
        return code, seen

    def test_a_scheduled_first_attempt_records_the_slot(self):
        code, seen = self.capture("--event-name", "schedule",
                                  "--cron-utc", SG_CRON, "--run-attempt", "1")
        self.assertEqual(code, 0)
        self.assertEqual(seen["target_source"], SOURCE_SCHEDULE)

    def test_an_explicit_date_records_explicit(self):
        code, seen = self.capture("--target-date", "2026-08-31",
                                  "--event-name", "schedule",
                                  "--cron-utc", SG_CRON, "--run-attempt", "1")
        self.assertEqual(code, 0)
        self.assertEqual(seen["target"], date(2026, 8, 31))
        self.assertEqual(seen["target_source"], SOURCE_EXPLICIT)

    def test_a_dispatch_records_the_manual_date(self):
        code, seen = self.capture("--event-name", "workflow_dispatch",
                                  "--run-attempt", "1")
        self.assertEqual(code, 0)
        self.assertEqual(seen["target_source"], SOURCE_MANUAL)

    def test_a_rerun_exits_non_zero_and_writes_no_ledger(self):
        code, seen = self.capture("--event-name", "schedule",
                                  "--cron-utc", SG_CRON, "--run-attempt", "2")
        self.assertEqual(code, 2)
        self.assertEqual(seen, {})
        self.assertFalse(self.state.exists(),
                         "a refused run must not create state")

    def test_a_rerun_with_an_explicit_date_proceeds(self):
        code, seen = self.capture("--target-date", "2026-08-31",
                                  "--event-name", "schedule",
                                  "--cron-utc", SG_CRON, "--run-attempt", "2")
        self.assertEqual(code, 0)
        self.assertEqual(seen["target_source"], SOURCE_EXPLICIT)

    def test_a_malformed_run_attempt_exits_non_zero(self):
        for value in ("0", "-1", "abc", ""):
            with self.subTest(value=value):
                code, seen = self.capture("--event-name", "schedule",
                                          "--cron-utc", SG_CRON,
                                          "--run-attempt", value)
                self.assertEqual(code, 2)
                self.assertEqual(seen, {})

    def test_the_run_attempt_defaults_to_one_for_a_direct_local_call(self):
        """
        With GITHUB_RUN_ATTEMPT absent from the environment — which is what a
        direct local call looks like. Pinned rather than inherited: this suite
        runs inside Actions, and a *re-run of CI itself* would otherwise set
        the variable to 2 and fail a test about local behaviour.
        """
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_RUN_ATTEMPT", None)
            code, seen = self.capture("--event-name", "schedule",
                                      "--cron-utc", SG_CRON)
        self.assertEqual(code, 0)
        self.assertEqual(seen["target_source"], SOURCE_SCHEDULE)

    def test_the_run_attempt_is_read_from_the_environment_when_not_passed(self):
        """The env default is what makes a forgotten flag fail closed."""
        with mock.patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}):
            code, seen = self.capture("--event-name", "schedule",
                                      "--cron-utc", SG_CRON)
        self.assertEqual(code, 2)
        self.assertEqual(seen, {})

    def test_an_empty_environment_value_is_treated_as_a_first_attempt(self):
        """`os.environ.get(...) or "1"`: empty is absent, not malformed."""
        with mock.patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": ""}):
            code, seen = self.capture("--event-name", "schedule",
                                      "--cron-utc", SG_CRON)
        self.assertEqual(code, 0)
        self.assertEqual(seen["target_source"], SOURCE_SCHEDULE)


class TestJapanRecordsTheProvenanceToo(TestTheCollectorsRecordTheProvenance):
    """The identical contract, asserted against the other desk's collector."""

    SCRIPT = "shadow_collect_japan.py"


class TestBothCollectorsStartAtAll(CollectorCase):
    """
    `main` reads `os.environ` while building its parser, so a collector that
    does not import `os` raises `NameError` before parsing a single argument —
    a total outage that no test touching `run()` alone would ever see.
    """

    SCRIPT = "shadow_collect.py"

    def test_main_reaches_argument_parsing(self):
        for script in ("shadow_collect.py", "shadow_collect_japan.py"):
            with self.subTest(script=script):
                mod = _load_collector(script)
                with self.assertRaises(SystemExit):
                    mod.main(["--help"])

    def test_each_collector_imports_os_at_module_level(self):
        for script in ("shadow_collect.py", "shadow_collect_japan.py"):
            with self.subTest(script=script):
                self.assertTrue(hasattr(_load_collector(script), "os"))


class TestGeneratedLedgersCarryTheSource(CollectorCase):
    """A real ledger, written to disk by the real `run`, for each desk."""

    SCRIPT = "shadow_collect.py"

    def test_a_singapore_ledger_records_the_schedule_slot(self):
        self.mod.run(self.state, date(2026, 8, 31), 30, 40, "r", "c",
                     adapter=_StubAdapter(), target_source=SOURCE_SCHEDULE)
        entry = self.ledger()
        self.assertEqual(entry["target_date"], "2026-08-31")
        self.assertEqual(entry["target_date_source"], SOURCE_SCHEDULE)

    def test_a_japan_ledger_records_the_schedule_slot(self):
        jp = _load_collector("shadow_collect_japan.py")
        real, jp.load_sources = jp.load_sources, lambda: []
        try:
            jp.run(self.state, date(2026, 8, 31), 14, 40, "r", "c",
                   target_source=SOURCE_SCHEDULE)
        finally:
            jp.load_sources = real
        entry = self.ledger()
        self.assertEqual(entry["target_date"], "2026-08-31")
        self.assertEqual(entry["target_date_source"], SOURCE_SCHEDULE)

    def test_every_source_a_collector_can_record_is_a_declared_source(self):
        for source in SOURCES:
            with self.subTest(source=source):
                shutil.rmtree(self.state, ignore_errors=True)
                self.mod.run(self.state, date(2026, 8, 31), 30, 40, "r", "c",
                             adapter=_StubAdapter(), target_source=source)
                self.assertEqual(self.ledger()["target_date_source"], source)


# ── the reader ───────────────────────────────────────────────────────────────

class TestTheReviewReaderValidatesTheProvenance(unittest.TestCase):
    """
    Backward compatible by construction: `target_date_source` is optional, so
    every historical ledger still loads. A value it *does* carry must be one
    this repository can explain — an unreadable provenance is worse than none,
    because it looks like an answer.
    """

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "review_shadow_state_provenance",
            REPO_ROOT / "scripts" / "review_shadow_state.py")
        cls.rk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.rk)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ledger-provenance-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "ledger").mkdir(parents=True)

    def write(self, **extra):
        entry = {f: 0 for f in self.rk.LEDGER_REQUIRED}
        entry.update(run_id="r1", collector_commit="c",
                     started_utc="2026-08-31T21:12:00+00:00",
                     finished_utc="2026-08-31T21:13:00+00:00",
                     target_date="2026-08-31", robots_status="allowed",
                     listing_status="ok", result="ok", health="ok",
                     state_sha256_before=None, state_sha256_after="a" * 64,
                     shadow_day=1)
        entry.update(extra)
        (self.tmp / "ledger" / "20260831T211300-r1.json").write_text(
            json.dumps(entry, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def test_a_historical_ledger_without_the_field_still_loads(self):
        """The published Day 7 and Day 14 evidence has no such field."""
        self.write()
        loaded = self.rk.load_ledgers(self.tmp)
        self.assertEqual(len(loaded), 1)
        self.assertNotIn("target_date_source", loaded[0])

    def test_each_supported_value_is_accepted(self):
        for source in self.rk.TARGET_DATE_SOURCES:
            with self.subTest(source=source):
                self.write(target_date_source=source)
                loaded = self.rk.load_ledgers(self.tmp)
                self.assertEqual(loaded[0]["target_date_source"], source)

    def test_an_unknown_value_is_refused(self):
        for bad in ("execution-date", "schedule_slot", "SCHEDULE-SLOT",
                    "guessed", ""):
            with self.subTest(value=bad):
                self.write(target_date_source=bad)
                with self.assertRaises(self.rk.ReviewError) as caught:
                    self.rk.load_ledgers(self.tmp)
                self.assertIn("target_date_source", str(caught.exception))

    def test_a_malformed_value_is_refused(self):
        for bad in (None, 0, 1, [], {}, ["explicit"]):
            with self.subTest(value=bad):
                self.write(target_date_source=bad)
                with self.assertRaises(self.rk.ReviewError):
                    self.rk.load_ledgers(self.tmp)

    def test_the_refusal_names_the_ledger_and_the_accepted_values(self):
        self.write(target_date_source="execution-date")
        with self.assertRaises(self.rk.ReviewError) as caught:
            self.rk.load_ledgers(self.tmp)
        message = str(caught.exception)
        self.assertIn("20260831T211300-r1.json", message)
        for source in SOURCES:
            self.assertIn(source, message)

    def test_the_reader_and_the_collectors_accept_the_same_set(self):
        """
        The kit re-declares this tuple rather than importing it: its runtime
        imports are pinned to an allowlist by
        `test_the_kit_imports_nothing_network_capable`, and widening a real
        guard for three strings is the worse trade. This test is what keeps the
        two copies equal — the same treatment `KINDS` and `RELEASE_RE` get.
        """
        self.assertEqual(tuple(self.rk.TARGET_DATE_SOURCES), tuple(SOURCES))

    def test_the_field_is_not_required(self):
        self.assertNotIn("target_date_source", self.rk.LEDGER_REQUIRED)


class TestHistoricalLedgersAreNotRewritten(unittest.TestCase):
    """
    The fix is forward-only. Two completed human reviews reason about the
    existing ledgers, and the review tool's missing-day anomaly is a true
    statement about them.
    """

    def test_no_collector_writes_into_an_existing_ledger_file(self):
        for script in ("shadow_collect.py", "shadow_collect_japan.py"):
            with self.subTest(script=script):
                src = (REPO_ROOT / "scripts" / script).read_text(encoding="utf-8")
                for banned in ("backfill", "rewrite_ledger", "os.remove", "unlink("):
                    self.assertNotIn(banned, src)

    def test_the_review_tool_still_reports_missing_days(self):
        """Hiding the anomaly would remove the signal that found this bug."""
        src = (REPO_ROOT / "scripts" / "review_shadow_state.py").read_text(encoding="utf-8")
        self.assertIn("inside the observed collection period", src)


if __name__ == "__main__":
    unittest.main()
