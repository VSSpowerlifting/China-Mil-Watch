"""
The published "Last full update" is the day the run is having, not the day
before.

The defect
----------
`.github/state/last_daily_run_date.txt` is written by the LAST step of the
daily workflow, after validation, commit and deploy. That placement is
deliberate and must not change: it is the success boundary, and moving it
earlier would let a failed pipeline, a failed validator, a failed push or a
failed deployment record a success that never happened.

The render happens much earlier, inside `pipeline.py`. It read that marker.
At that instant the marker still holds the PREVIOUS successful run's date, so
every scheduled render published a "Last full update" exactly one day stale —
visible in production on every `Daily update: N` commit, each of which ships an
`output/index.html` reading `N-1`.

The repair
----------
The scheduling guard has already decided which logical day the run is for; it
prints that as `today_ny`, and it is the very value the success step will write
if the run finishes. The workflow hands that value to the render through
`PLA_WATCH_DAILY_RUN_DATE`, `site/render.py` turns it into an argument, and the
view model uses it instead of the marker. Nothing is written to disk, nothing
reads a clock, and the marker stays exactly where it was.

Everything here is offline: no dispatch, no collector, no network, no provider,
no write to the tracked database and no write to the tracked `output/`.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import core.viewmodel as vm                                          # noqa: E402
from core.viewmodel import (                                        # noqa: E402
    DAILY_RUN_DATE_ENV, InvalidDailyRunDate, PublicView,
    daily_run_date_from_env, normalize_daily_run_date,
)

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_update.yml"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
TRACKED_DB = REPO_ROOT / "pla_watch.db"
MARKER = REPO_ROOT / ".github" / "state" / "last_daily_run_date.txt"

#: The day under test and the day before it. Neither is today, and neither is
#: any date the tracked marker holds: a fixture that quoted the real state
#: would pass for the wrong reason the first morning the state moved.
N = "2026-11-17"
N_MINUS_1 = "2026-11-16"

#: An instant inside a configured cron window, on N. 13:23 UTC is 08:23 in New
#: York in November (EST), which is the first of the five windows.
ON_TIME = datetime(2026, 11, 17, 13, 23, tzinfo=timezone.utc)

#: The same slot, executed late — 23:20 New York, still N. Measured start times
#: for this workflow run 60-100 minutes behind the cron, and the guard is what
#: decides the day, so a delayed execution must still be N.
DELAYED = datetime(2026, 11, 18, 4, 20, tzinfo=timezone.utc)

#: Past New York midnight. A different workflow day by the guard's own
#: contract, included so "the render never recomputes" is tested against a
#: value that would actually differ if it did.
AFTER_MIDNIGHT = datetime(2026, 11, 18, 5, 20, tzinfo=timezone.utc)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def flat(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def rendered_full_update(out_dir: Path) -> str:
    """What a reader sees under "Last full update" on the home page."""
    text = flat((out_dir / "index.html").read_text(encoding="utf-8"))
    match = re.search(r"Last full update\s+(\S+)", text)
    assert match, "the home page carries no Last full update value"
    return match.group(1)


# ── The workflow's own guard, executed rather than paraphrased ───────────────

def run_guard(moment, marker_value, event="schedule", billing_value="2000-01-01"):
    """
    Execute the `Scheduling guard` body out of the YAML with a frozen clock.

    Lifted wholesale from `tests/test_workflow_day_contract.py`, because a
    paraphrase of the guard is not the guard. Returns `(should_run, today_ny)`.
    """
    step = WORKFLOW.read_text(encoding="utf-8").split(
        "- name: Scheduling guard", 1)[1]
    body = textwrap.dedent(
        step.split("python - <<'PY'", 1)[1].split("\n          PY", 1)[0])

    tmp = tempfile.mkdtemp(prefix="daily-fresh-guard-")
    try:
        state = Path(tmp) / ".github" / "state"
        state.mkdir(parents=True)
        (state / "last_daily_run_date.txt").write_text(marker_value)
        (state / "last_billing_failure_date.txt").write_text(billing_value)
        out = Path(tmp) / "out"
        out.write_text("")

        class _Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                return moment.astimezone(tz) if tz else moment

        import datetime as _dt_module
        import types
        shim = types.ModuleType("datetime")
        for attribute in dir(_dt_module):
            setattr(shim, attribute, getattr(_dt_module, attribute))
        shim.datetime = _Frozen

        cwd, saved = os.getcwd(), dict(os.environ)
        real_module = sys.modules["datetime"]
        try:
            os.chdir(tmp)
            os.environ["GITHUB_EVENT_NAME"] = event
            os.environ["GITHUB_OUTPUT"] = str(out)
            sys.modules["datetime"] = shim
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(body, "daily_update.yml::guard", "exec"),
                     {"__name__": "daily_fresh_guard_probe"})
            written = out.read_text()
        finally:
            sys.modules["datetime"] = real_module
            os.chdir(cwd)
            os.environ.clear()
            os.environ.update(saved)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    should_run = re.findall(r"should_run=(\w+)", written)
    today_ny = re.findall(r"today_ny=(\d{4}-\d{2}-\d{2})", written)
    assert should_run and today_ny, "the guard wrote no decision"
    return should_run[-1], today_ny[-1]


class RenderHarness(unittest.TestCase):
    """
    One scheduled render of the real corpus, with the marker held at `N-1`.

    The marker is a temporary file and `COMPLETED_RUN_MARKER` is redirected at
    it, so nothing in the working tree is touched. That redirection is also the
    point of the fixture: if the fix ever stopped working, the render would
    fall back to this file and the assertions would read `N-1`.
    """

    @classmethod
    def render(cls, environ, out_name="site", daily_run_date=None):
        r = load("daily_fresh_render", "site/render.py")
        gp = load("daily_fresh_gp", "site/preview/generate_preview.py")
        out = cls.tmp / out_name
        kwargs = {}
        if daily_run_date is not None:
            kwargs["daily_run_date"] = daily_run_date
        with mock.patch.object(vm, "COMPLETED_RUN_MARKER", cls.marker):
            report = r.render_site(
                r.INDO_PACIFIC_RECORD, output_dir=out, environ=environ,
                snapshot=gp.snapshot_from_corpus(TRACKED_DB),
                site_origin="https://daily-render-freshness.invalid",
                allow_test_origin=True, **kwargs)
        return out, report

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="daily-fresh-"))
        cls.marker = cls.tmp / "last_daily_run_date.txt"
        # The marker as it actually stands when the render runs: the previous
        # successful run's date, because this run has not reached its success
        # step and must not have.
        cls.marker.write_text(N_MINUS_1 + "\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestTheStaleDateSequence(RenderHarness):
    """
    The whole defect, in the order it happens on a real morning.

    Against the code before this change the last assertion reads `2026-11-16`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.should_run, cls.today_ny = run_guard(ON_TIME, marker_value=N_MINUS_1)
        # Exactly what the workflow step declares, with the guard's own output
        # substituted — no hand-written date reaches the render.
        cls.scheduled, cls.report = cls.render(
            {DAILY_RUN_DATE_ENV: cls.today_ny})

    def test_1_the_marker_holds_the_previous_day(self):
        self.assertEqual(self.marker.read_text(encoding="utf-8").strip(),
                         N_MINUS_1)

    def test_2_the_guard_admits_the_run_and_calls_it_todays(self):
        self.assertEqual(self.should_run, "true")
        self.assertEqual(self.today_ny, N)

    def test_3_the_render_happens_while_the_marker_still_says_yesterday(self):
        """
        The ordering that must not change. The marker is the success boundary;
        this render is upstream of validation, commit, push and deploy.
        """
        self.assertEqual(self.marker.read_text(encoding="utf-8").strip(),
                         N_MINUS_1)

    def test_4_the_page_publishes_the_day_the_run_is_for(self):
        self.assertEqual(rendered_full_update(self.scheduled), N)

    def test_5_the_page_does_not_publish_yesterday(self):
        self.assertNotEqual(rendered_full_update(self.scheduled), N_MINUS_1)

    def test_6_every_page_carrying_the_line_agrees(self):
        """One render, one date. A per-page divergence would be worse."""
        pages = [p for p in sorted(self.scheduled.rglob("*.html"))
                 if "Last full update" in p.read_text(encoding="utf-8")]
        self.assertTrue(pages, "no page carries the freshness line")
        for page in pages:
            text = flat(page.read_text(encoding="utf-8"))
            with self.subTest(page=str(page.relative_to(self.scheduled))):
                self.assertRegex(text, r"Last full update\s+" + re.escape(N))
                self.assertNotRegex(
                    text, r"Last full update\s+" + re.escape(N_MINUS_1))

    def test_7_the_report_names_the_date_it_rendered(self):
        self.assertEqual(self.report["daily_run_date"], N)

    def test_8_the_other_two_freshness_dates_are_untouched(self):
        """
        This change is about one of the three dates. Collection and analysis
        still come from the corpus, and a fix that moved them would be
        replacing one false claim with two.
        """
        f = PublicView(TRACKED_DB).freshness()
        text = flat((self.scheduled / "index.html").read_text(encoding="utf-8"))
        for label, value in (
                ("Records last collected", f.records_last_collected),
                ("Analysis last produced", f.analysis_last_produced)):
            with self.subTest(label=label):
                self.assertRegex(text,
                                 re.escape(label) + r"\s+" + re.escape(value))


class TestTheMarkerRemainsTheLocalDefault(RenderHarness):
    """
    An ordinary local or manual render — no run context — is unchanged.

    Rendered as a second build in the same fixture so the two paths are
    compared against the same corpus and the same marker file.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.local, cls.report = cls.render({}, out_name="local")

    def test_a_render_without_run_context_reads_the_marker(self):
        self.assertEqual(rendered_full_update(self.local), N_MINUS_1)

    def test_it_reports_no_run_date(self):
        self.assertIsNone(self.report["daily_run_date"])

    def test_this_is_the_state_the_defect_produced(self):
        """
        Named explicitly: `N-1` is not a bug here. It is the honest marker
        value for a build that is not a daily run. The bug was a SCHEDULED
        render producing it.
        """
        self.assertEqual(self.marker.read_text(encoding="utf-8").strip(),
                         N_MINUS_1)


class TestTheRenderLeavesNoResidue(RenderHarness):
    """
    Nothing on this path writes a marker file.

    A render that wrote the new date to disk to make the page correct would
    leave `.github/state/last_daily_run_date.txt` dirty in the runner's working
    tree, and every later step rebases, stages and pushes. That is the failure
    this design exists to avoid, so it is asserted rather than assumed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.before = MARKER.read_bytes()
        cls.before_stat = MARKER.stat().st_mtime_ns
        cls.out, _ = cls.render({DAILY_RUN_DATE_ENV: N}, out_name="residue")

    def test_the_tracked_marker_is_byte_identical_afterwards(self):
        self.assertEqual(MARKER.read_bytes(), self.before)

    def test_the_tracked_marker_was_not_even_rewritten(self):
        self.assertEqual(MARKER.stat().st_mtime_ns, self.before_stat)

    def test_the_fixture_marker_is_untouched_too(self):
        self.assertEqual(self.marker.read_text(encoding="utf-8").strip(),
                         N_MINUS_1)

    def test_the_state_directory_is_clean_in_git(self):
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", ".github/state"],
            cwd=str(REPO_ROOT), capture_output=True, text=True)
        if out.returncode != 0:            # not a checkout; nothing to assert
            self.skipTest("not a git working tree")
        self.assertEqual(out.stdout.strip(), "")

    def test_no_module_on_the_render_path_names_the_marker_file(self):
        """
        The constant in the view model is the only place the path is spelled,
        and it is read-only. Anywhere else would be a second writer.
        """
        for relative in ("pipeline.py", "site/render.py",
                         "site/preview/generate_preview.py"):
            with self.subTest(module=relative):
                self.assertNotIn(
                    "last_daily_run_date",
                    (REPO_ROOT / relative).read_text(encoding="utf-8"))

    def test_the_view_model_only_reads_the_marker(self):
        source = (REPO_ROOT / "core" / "viewmodel.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("last_daily_run_date"), 1)
        for writing in ("write_text", "open(", "os.replace", "mkdir"):
            with self.subTest(call=writing):
                self.assertNotIn(writing, source)


class TestTheDateIsNeverTakenFromAClock(unittest.TestCase):
    """
    The guard decides the day once. Everything downstream carries that
    decision; nothing re-derives it.
    """

    def test_the_resolver_reads_no_clock(self):
        source = (REPO_ROOT / "core" / "viewmodel.py").read_text(encoding="utf-8")
        for forbidden in ("datetime.now", ".now(", "utcnow", "today()",
                          "time.time", "st_mtime"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_render_seam_reads_no_clock(self):
        source = (REPO_ROOT / "site" / "render.py").read_text(encoding="utf-8")
        for forbidden in ("datetime.now", "utcnow", "today()", "time.time"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_a_delayed_execution_keeps_its_own_slot_date(self):
        """
        Measured starts for this workflow run 60-100 minutes late, and worse
        has happened. A run that starts at 23:20 New York is still that day's
        run, and the guard says so.
        """
        should_run, today_ny = run_guard(DELAYED, marker_value=N_MINUS_1)
        self.assertEqual(should_run, "true")
        self.assertEqual(today_ny, N)

    def test_the_render_does_not_recompute_the_day_it_finishes_on(self):
        """
        The value is fixed when the run is admitted. A render that ran on past
        New York midnight — which the guard would call a different day — still
        publishes the slot it was admitted for.
        """
        _, later_day = run_guard(AFTER_MIDNIGHT, marker_value=N_MINUS_1)
        self.assertNotEqual(later_day, N, "the fixture proves nothing")
        self.assertEqual(daily_run_date_from_env({DAILY_RUN_DATE_ENV: N}), N)
        self.assertEqual(
            PublicView(TRACKED_DB).freshness(daily_run_date=N).last_full_update,
            N)

    def test_the_builder_is_a_function_of_its_arguments(self):
        """
        `generate_preview.build()` must not read the environment itself. A
        variable left set in a shell would otherwise change what a local build
        publishes, and the single seam would stop being single.
        """
        source = (REPO_ROOT / "site" / "preview"
                  / "generate_preview.py").read_text(encoding="utf-8")
        self.assertNotIn(DAILY_RUN_DATE_ENV, source)
        self.assertIn("daily_run_date", source)


class TestInvalidDatesFailClosed(unittest.TestCase):
    """
    A supplied date that cannot be trusted stops the build.

    Falling back to the marker would reinstate the stale date while reporting
    success — the exact shape of the defect being removed.
    """

    UNUSABLE = ("", "   ", "\t", "2026-9-5", "26-11-17", "2026-011-17",
                "2026-13-01", "2026-02-30", "2026-11-31", "0000-00-00",
                "tomorrow", "2026-11-17T00:00:00", "2026-11-17Z",
                "2026-11-17\n2026-11-18", "N", "${{ steps.timecheck.outputs }}")

    def test_every_unusable_environment_value_raises(self):
        for value in self.UNUSABLE:
            with self.subTest(value=value):
                with self.assertRaises(InvalidDailyRunDate):
                    daily_run_date_from_env({DAILY_RUN_DATE_ENV: value})

    def test_an_absent_variable_is_not_an_error(self):
        self.assertIsNone(daily_run_date_from_env({}))

    def test_the_view_model_refuses_an_unusable_explicit_date(self):
        view = PublicView(TRACKED_DB)
        for value in ("", "2026-13-01", "tomorrow", 20261117, None.__class__):
            with self.subTest(value=value):
                with self.assertRaises(InvalidDailyRunDate):
                    view.freshness(daily_run_date=value)

    def test_the_render_seam_refuses_an_unusable_explicit_date(self):
        r = load("daily_fresh_render_invalid", "site/render.py")
        with self.assertRaises(InvalidDailyRunDate):
            r.render_site(r.INDO_PACIFIC_RECORD, output_dir=None,
                          environ={}, daily_run_date="2026-13-01")

    def test_the_render_seam_refuses_an_unusable_environment_value(self):
        r = load("daily_fresh_render_invalid_env", "site/render.py")
        with self.assertRaises(InvalidDailyRunDate):
            r.render_site(r.INDO_PACIFIC_RECORD, output_dir=None,
                          environ={DAILY_RUN_DATE_ENV: "not-a-date"})

    def test_it_fails_before_anything_is_written(self):
        """
        The refusal has to come before the corpus read and the tree build, so
        a broken wire leaves no half-built output behind.
        """
        r = load("daily_fresh_render_early", "site/render.py")
        tmp = Path(tempfile.mkdtemp(prefix="daily-fresh-early-"))
        try:
            out = tmp / "site"
            with self.assertRaises(InvalidDailyRunDate):
                r.render_site(r.INDO_PACIFIC_RECORD, output_dir=out,
                              environ={DAILY_RUN_DATE_ENV: "2026-02-30"},
                              site_origin="https://early.invalid",
                              allow_test_origin=True)
            self.assertFalse(out.exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_refusal_names_the_wire_that_broke(self):
        with self.assertRaises(InvalidDailyRunDate) as caught:
            daily_run_date_from_env({DAILY_RUN_DATE_ENV: "nope"})
        self.assertIn(DAILY_RUN_DATE_ENV, str(caught.exception))
        with self.assertRaises(InvalidDailyRunDate) as caught:
            normalize_daily_run_date("nope", "daily_run_date")
        self.assertIn("daily_run_date", str(caught.exception))

    def test_a_usable_date_survives_surrounding_whitespace(self):
        """
        The guard writes a bare date, but a shell that appended a newline has
        still named the day unambiguously. Only the surroundings are forgiven:
        anything inside the value is refused above.
        """
        for padded in ("\n" + N + "\n", " " + N, N + "  ", "\t" + N + "\t"):
            with self.subTest(value=padded):
                self.assertEqual(
                    daily_run_date_from_env({DAILY_RUN_DATE_ENV: padded}), N)


# ── The workflow wiring, exactly ─────────────────────────────────────────────

STEP = re.compile(r"^      - name: (.+)$", re.M)


def steps_of(text: str):
    """`(name, body)` per step, in order. Bodies exclude leading comments."""
    marks = list(STEP.finditer(text))
    out = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[mark.start():end]
        # Trailing comment block belongs to the NEXT step, so cut it off.
        body = re.split(r"\n      # ──", body)[0]
        out.append((mark.group(1).strip(), body))
    return out


class WorkflowCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.steps = steps_of(cls.text)
        cls.by_name = dict(cls.steps)
        cls.order = [name for name, _ in cls.steps]

    def step(self, name):
        self.assertIn(name, self.by_name, "the workflow lost a step")
        return self.by_name[name]


class TestTheWorkflowHandsTheGuardsDateToTheRender(WorkflowCase):

    def test_the_guard_still_publishes_its_decision(self):
        guard = self.step("Scheduling guard")
        self.assertIn('f.write(f"today_ny={today_str}\\n")', guard)
        self.assertIn('ZoneInfo("America/New_York")', guard)

    def test_the_pipeline_step_receives_the_guards_date(self):
        pipeline = self.step("Run pipeline")
        self.assertIn(
            "PLA_WATCH_DAILY_RUN_DATE: ${{ steps.timecheck.outputs.today_ny }}",
            pipeline)

    def test_the_environment_name_matches_the_one_the_code_reads(self):
        self.assertEqual(DAILY_RUN_DATE_ENV, "PLA_WATCH_DAILY_RUN_DATE")
        self.assertIn(DAILY_RUN_DATE_ENV, self.step("Run pipeline"))

    def test_the_render_and_the_marker_quote_the_same_output(self):
        """
        One authority. If these two ever diverge, the site publishes a date the
        run is about to contradict in the very next commit.
        """
        pipeline = self.step("Run pipeline")
        success = self.step("Record successful run")
        expression = "steps.timecheck.outputs.today_ny"
        self.assertIn(expression, pipeline)
        self.assertIn(expression, success)

    def test_the_pipeline_step_gained_nothing_else(self):
        pipeline = self.step("Run pipeline")
        env_keys = re.findall(r"^          (\w+):", pipeline, re.M)
        self.assertEqual(sorted(env_keys),
                         ["ANTHROPIC_API_KEY", "PLA_WATCH_DAILY_RUN_DATE"])
        self.assertIn("run: python pipeline.py", pipeline)
        self.assertIn("id: pipeline", pipeline)
        self.assertIn("if: steps.timecheck.outputs.should_run == 'true'",
                      pipeline)

    def test_no_other_workflow_supplies_a_run_date(self):
        """
        Only the daily workflow has a scheduling guard, so only it has a
        logical date to hand over. Anything else rendering must keep reading
        the marker.
        """
        for workflow in sorted(WORKFLOW_DIR.glob("*.yml")):
            if workflow == WORKFLOW:
                continue
            with self.subTest(workflow=workflow.name):
                self.assertNotIn(DAILY_RUN_DATE_ENV,
                                 workflow.read_text(encoding="utf-8"))

    def test_the_date_is_not_pinned_as_a_literal_anywhere(self):
        body = "\n".join(b for _, b in self.steps)
        self.assertNotRegex(body, r"PLA_WATCH_DAILY_RUN_DATE:\s*\d{4}-")


class TestTheSuccessBoundaryDidNotMove(WorkflowCase):
    """
    The marker is still written once, last, and only on a run that got there.
    """

    def test_only_one_step_writes_the_marker(self):
        writes = [name for name, body in self.steps
                  if "> .github/state/last_daily_run_date.txt" in body]
        self.assertEqual(writes, ["Record successful run"])

    def test_only_one_step_stages_the_marker(self):
        staged = [name for name, body in self.steps
                  if "git add .github/state/last_daily_run_date.txt" in body]
        self.assertEqual(staged, ["Record successful run"])

    def test_the_render_step_writes_no_marker(self):
        pipeline = self.step("Run pipeline")
        self.assertNotIn("last_daily_run_date", pipeline)
        self.assertNotIn("git ", pipeline)

    def test_the_marker_is_written_after_publication(self):
        for earlier in ("Run pipeline", "Validate rendered output",
                        "Commit updated database and site output",
                        "Deploy to GitHub Pages"):
            with self.subTest(step=earlier):
                self.assertLess(self.order.index(earlier),
                                self.order.index("Record successful run"))

    def test_the_marker_step_is_still_gated_on_plain_success(self):
        success = self.step("Record successful run")
        self.assertIn("if: steps.timecheck.outputs.should_run == 'true'",
                      success)
        for unconditional in ("always()", "failure()", "!cancelled()"):
            with self.subTest(gate=unconditional):
                self.assertNotIn(unconditional, success)

    def test_the_marker_step_still_pushes_to_main(self):
        success = self.step("Record successful run")
        self.assertIn("git pull --rebase --autostash origin main", success)
        self.assertIn("git push origin main", success)

    def test_the_marker_step_still_guards_its_staging_scope(self):
        success = self.step("Record successful run")
        self.assertIn("Scope violation", success)
        self.assertIn("verify_db_current.py", success)
        self.assertNotIn("--repair", success)


class TestSurroundingSemanticsAreIntact(WorkflowCase):
    """
    The change is one environment key. Everything the daily run depends on to
    fail safely has to still be there, and each of these has a real incident
    behind it.
    """

    def test_reruns_are_still_serialised_and_never_cancelled(self):
        self.assertIn("group: daily-update", self.text)
        self.assertIn("cancel-in-progress: false", self.text)

    def test_the_five_retry_windows_and_manual_dispatch_remain(self):
        self.assertEqual(len(re.findall(r"- cron: '", self.text)), 5)
        self.assertIn("workflow_dispatch:", self.text)

    def test_a_repeat_run_on_the_same_day_is_still_refused(self):
        should_run, today_ny = run_guard(ON_TIME, marker_value=N)
        self.assertEqual(should_run, "false")
        self.assertEqual(today_ny, N)

    def test_a_manual_dispatch_still_bypasses_the_guard(self):
        should_run, today_ny = run_guard(ON_TIME, marker_value=N,
                                         event="workflow_dispatch")
        self.assertEqual(should_run, "true")
        self.assertEqual(today_ny, N)

    def test_a_billing_failure_still_suppresses_later_windows(self):
        should_run, _ = run_guard(ON_TIME, marker_value=N_MINUS_1,
                                  billing_value=N)
        self.assertEqual(should_run, "false")

    def test_the_checkout_still_takes_the_tip_of_main(self):
        checkout = self.step("Check out repository")
        self.assertIn("ref: main", checkout)
        self.assertIn("fetch-depth: 0", checkout)

    def test_collection_is_still_salvaged_when_a_later_step_fails(self):
        persist = self.step("Persist scraped articles (if pipeline failed)")
        self.assertIn("failure()", persist)
        self.assertIn("steps.pipeline.outcome == 'success'", persist)
        self.assertIn("steps.pipeline.outcome == 'failure'", persist)
        self.assertIn("git add pla_watch.db", persist)
        self.assertNotIn("output/", persist.split("run: |", 1)[-1])

    def test_the_billing_marker_step_still_runs_always(self):
        billing = self.step(
            "Commit billing-failure marker (if the account was blocked)")
        self.assertIn("always()", billing)
        self.assertIn("github.event_name != 'workflow_dispatch'", billing)

    def test_every_rebase_is_still_an_autostash_rebase_onto_main(self):
        rebases = [line.strip() for line in self.text.splitlines()
                   if line.strip().startswith("git pull")]
        self.assertEqual(len(rebases), 4, "a rebase step appeared or vanished")
        for line in rebases:
            with self.subTest(line=line):
                self.assertEqual(line,
                                 "git pull --rebase --autostash origin main")

    def test_nothing_force_pushes(self):
        self.assertNotIn("--force", self.text)
        self.assertNotIn("push -f", self.text)

    def test_the_validator_still_stands_between_render_and_publication(self):
        self.assertLess(self.order.index("Run pipeline"),
                        self.order.index("Validate rendered output"))
        self.assertLess(self.order.index("Validate rendered output"),
                        self.order.index(
                            "Commit updated database and site output"))
        self.assertIn("python scripts/validate_output.py",
                      self.step("Validate rendered output"))

    def test_the_health_gate_is_still_last(self):
        self.assertEqual(self.order[-1], "Health gate")


if __name__ == "__main__":
    unittest.main()
