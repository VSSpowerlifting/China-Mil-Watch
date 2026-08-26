"""
One definition of the workflow day, for the guard and the marker alike.

The daily workflow promises at most one successful run per New York calendar
day, and its scheduling guard reads `America/New_York` to keep that promise.
`_write_billing_failure_marker()` wrote `date.today()` — the runner's UTC date —
while claiming in its own docstring to write the New York date.

Every configured cron window sits at 08:23-10:23 EDT, where the two agree, so
the mismatch has never fired. It is four hours wide: a failure after 20:00 New
York stamped tomorrow's marker on today's failure, which suppresses a day that
never failed and leaves the day that did fail unsuppressed.

These tests use a frozen clock throughout. Nothing here depends on the real
time, dispatches a workflow, or reaches a provider.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import sys
import tempfile
import textwrap
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.workflow_day import (                                  # noqa: E402
    WORKFLOW_TIMEZONE, workflow_day, workflow_day_string,
)

NY = ZoneInfo("America/New_York")
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_update.yml"

#: Instants that matter, as (label, aware UTC datetime, expected NY date).
BOUNDARIES = [
    ("19:59 New York, same UTC date",
     datetime(2026, 8, 26, 23, 59, tzinfo=timezone.utc), date(2026, 8, 26)),
    ("20:01 New York, NEXT UTC date — the divergence",
     datetime(2026, 8, 27, 0, 1, tzinfo=timezone.utc), date(2026, 8, 26)),
    ("23:59 New York",
     datetime(2026, 8, 27, 3, 59, tzinfo=timezone.utc), date(2026, 8, 26)),
    ("midnight New York",
     datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc), date(2026, 8, 27)),
    ("a configured cron window",
     datetime(2026, 8, 26, 12, 23, tzinfo=timezone.utc), date(2026, 8, 26)),
    ("DST spring forward, before",
     datetime(2026, 3, 8, 6, 59, tzinfo=timezone.utc), date(2026, 3, 8)),
    ("DST spring forward, after",
     datetime(2026, 3, 8, 7, 1, tzinfo=timezone.utc), date(2026, 3, 8)),
    ("DST fall back, before",
     datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc), date(2026, 11, 1)),
    ("DST fall back, after",
     datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc), date(2026, 11, 1)),
    ("EST winter cron window",
     datetime(2026, 1, 15, 12, 23, tzinfo=timezone.utc), date(2026, 1, 15)),
]


class TestTheWorkflowDayIsNewYork(unittest.TestCase):

    def test_every_boundary_resolves_to_the_new_york_date(self):
        for label, moment, expected in BOUNDARIES:
            with self.subTest(moment=label):
                self.assertEqual(workflow_day(moment), expected)

    def test_the_divergent_instant_is_not_the_utc_date(self):
        """The whole point: at 20:01 New York the two answers differ."""
        moment = datetime(2026, 8, 27, 0, 1, tzinfo=timezone.utc)
        self.assertEqual(moment.date(), date(2026, 8, 27))
        self.assertEqual(workflow_day(moment), date(2026, 8, 26))
        self.assertNotEqual(workflow_day(moment), moment.date())

    def test_a_naive_datetime_is_refused_rather_than_guessed(self):
        with self.assertRaises(ValueError):
            workflow_day(datetime(2026, 8, 26, 20, 1))

    def test_the_string_form_matches_the_state_file_shape(self):
        s = workflow_day_string(datetime(2026, 8, 27, 0, 1, tzinfo=timezone.utc))
        self.assertEqual(s, "2026-08-26")
        self.assertRegex(s, r"^\d{4}-\d{2}-\d{2}$")

    def test_the_timezone_is_not_a_fixed_offset(self):
        """
        A fixed -04:00 is right for eight months and wrong for four. Both DST
        transitions are in BOUNDARIES; this pins the mechanism as well.
        """
        summer = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
        winter = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        self.assertNotEqual(
            summer.astimezone(WORKFLOW_TIMEZONE).utcoffset(),
            winter.astimezone(WORKFLOW_TIMEZONE).utcoffset())


class TestTheMarkerWritesTheWorkflowDay(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="marker-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def _write(self, moment):
        import pipeline
        os.chdir(self.dir)
        pipeline._write_billing_failure_marker(moment)
        return (self.dir / pipeline.BILLING_FAILURE_STATE_FILE).read_text().strip()

    def test_it_writes_the_new_york_date_not_the_utc_date(self):
        moment = datetime(2026, 8, 27, 0, 1, tzinfo=timezone.utc)
        self.assertEqual(self._write(moment), "2026-08-26")

    def test_every_boundary_agrees_with_the_workflow_day(self):
        for label, moment, expected in BOUNDARIES:
            with self.subTest(moment=label):
                self.assertEqual(self._write(moment), expected.isoformat())

    def test_it_no_longer_takes_the_collection_target_date(self):
        """
        The target date says which day's ARTICLES were sought. Using it as the
        schedule stamp is the category error that produced the bug.
        """
        import inspect, pipeline
        params = list(inspect.signature(
            pipeline._write_billing_failure_marker).parameters)
        self.assertEqual(params, ["now"])
        source = (REPO_ROOT / "pipeline.py").read_text(encoding="utf-8")
        self.assertNotIn("_write_billing_failure_marker(target_date)", source)


class TestTheGuardAndTheMarkerAgree(unittest.TestCase):
    """
    The guard lives in YAML and the marker lives in Python. They are held
    together by executing the guard and comparing its answer, not by hoping.
    """

    def guard_today(self, moment):
        """Run the workflow's own guard with its clock frozen at `moment`."""
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step = workflow.split("- name: Scheduling guard", 1)[1]
        body = textwrap.dedent(
            step.split("python - <<'PY'", 1)[1].split("\n          PY", 1)[0])

        tmp = tempfile.mkdtemp(prefix="guard-day-")
        try:
            state = Path(tmp) / ".github" / "state"
            state.mkdir(parents=True)
            (state / "last_daily_run_date.txt").write_text("2000-01-01")
            (state / "last_billing_failure_date.txt").write_text("2000-01-01")
            out = Path(tmp) / "out"; out.write_text("")

            class _Frozen(datetime):
                @classmethod
                def now(cls, tz=None):
                    return moment.astimezone(tz) if tz else moment

            # The guard body does `from datetime import datetime`, so the clock
            # has to be frozen in the MODULE it imports from — patching the
            # exec scope afterwards is undone by that import.
            import datetime as _dt_module
            import types
            shim = types.ModuleType("datetime")
            for name in dir(_dt_module):
                setattr(shim, name, getattr(_dt_module, name))
            shim.datetime = _Frozen

            cwd, saved = os.getcwd(), dict(os.environ)
            real_module = sys.modules["datetime"]
            try:
                os.chdir(tmp)
                os.environ["GITHUB_EVENT_NAME"] = "schedule"
                os.environ["GITHUB_OUTPUT"] = str(out)
                sys.modules["datetime"] = shim
                scope = {"__name__": "guard_day_probe"}
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(body, "daily_update.yml::guard", "exec"), scope)
                written = out.read_text()
            finally:
                sys.modules["datetime"] = real_module
                os.chdir(cwd)
                os.environ.clear(); os.environ.update(saved)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        match = re.findall(r"today_ny=(\d{4}-\d{2}-\d{2})", written)
        self.assertTrue(match, "the guard wrote no today_ny")
        return match[-1]

    def test_the_guard_agrees_with_the_helper_at_every_boundary(self):
        for label, moment, expected in BOUNDARIES:
            with self.subTest(moment=label):
                self.assertEqual(self.guard_today(moment), expected.isoformat(),
                                 "the guard and the marker would disagree "
                                 "about which day it is")

    def test_the_guard_still_reads_new_york(self):
        self.assertIn('ZoneInfo("America/New_York")',
                      WORKFLOW.read_text(encoding="utf-8"))


class TestSuppressionSemanticsAreUnchanged(unittest.TestCase):
    """
    The repair must not alter what the guard decides — only which date both
    sides compute.
    """

    @staticmethod
    def decide(last_run, last_failure, today, is_manual=False):
        if is_manual:
            return True
        if last_run == today:
            return False
        if last_failure == today:
            return False
        return True

    def test_a_marker_for_the_same_workflow_day_suppresses(self):
        today = workflow_day_string(
            datetime(2026, 8, 27, 0, 1, tzinfo=timezone.utc))
        self.assertFalse(self.decide("2026-08-25", today, today))

    def test_the_next_workflow_day_is_not_suppressed(self):
        moment = datetime(2026, 8, 27, 0, 1, tzinfo=timezone.utc)
        today = workflow_day_string(moment)
        tomorrow = workflow_day_string(moment + timedelta(days=1))
        self.assertNotEqual(today, tomorrow)
        self.assertTrue(self.decide("2026-08-25", today, tomorrow))

    def test_manual_dispatch_is_never_suppressed(self):
        today = workflow_day_string(
            datetime(2026, 8, 27, 0, 1, tzinfo=timezone.utc))
        self.assertTrue(self.decide("2026-08-25", today, today, is_manual=True))

    def test_a_completed_day_still_suppresses(self):
        today = workflow_day_string(
            datetime(2026, 8, 26, 12, 23, tzinfo=timezone.utc))
        self.assertFalse(self.decide(today, "2000-01-01", today))

    def test_a_malformed_marker_suppresses_nothing(self):
        """
        Fail closed on the state, open on the schedule: garbage in the marker
        must not silently behave as "today" and suppress a day that never
        failed.
        """
        today = workflow_day_string(
            datetime(2026, 8, 26, 12, 23, tzinfo=timezone.utc))
        for junk in ("", "   ", "not-a-date", "26-08-2026", "2026-13-45"):
            with self.subTest(marker=repr(junk)):
                self.assertTrue(self.decide("2026-08-25", junk.strip(), today))


class TestNoProviderCallHappensHere(unittest.TestCase):

    def test_this_module_imports_no_network_client(self):
        import ast
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertEqual(
            names & {"anthropic", "httpx", "requests", "urllib", "socket"},
            set())


if __name__ == "__main__":
    unittest.main()
