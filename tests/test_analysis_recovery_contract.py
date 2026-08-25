"""
Recovery contract for an account-level analysis block.

The incident this pins is 2026-08-25, run 533 (`32853064669`). The Anthropic API
returned HTTP 400 `invalid_request_error` — "You have reached your specified API
usage limits. You will regain access on 2026-09-01 at 00:00 UTC." — on the first
of 55 queued articles. Collection had already completed and stored 35 records;
zero analyses ran; the run exited 2; the workflow persisted the database and
wrote the billing marker.

Nothing was stranded, and that is exactly why these tests exist. The recovery
depended on four separate properties holding at once, none of which was pinned:

  1. the analysis queue is selected by RECORD STATE, not by which run inserted
     the record, so yesterday's unscreened rows are picked up tomorrow;
  2. the backlog gets a reserved share of the daily cap, so a day that scrapes
     more than the cap cannot starve the records the outage left behind;
  3. the billing marker is scoped to ONE DATE, so it suppresses the remaining
     paid retries that day and nothing after it;
  4. the marker's date and the guard's date are the same date.

Property 4 is currently true by coincidence of scheduling rather than by
construction: the marker is written from `date.today()` (UTC on a GitHub
runner) while the workflow guard compares against America/New_York. Every
configured cron window sits at 08:23–10:23 EDT, where the two agree. A cron
moved past 20:00 EDT would write tomorrow's marker against today's guard and
suppress a day that never failed. The test below fails if that ever becomes
possible.

Nothing here calls a provider, opens the tracked database for writing, or
touches `output/`.
"""

from __future__ import annotations

import ast
import contextlib
import io
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import textwrap
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TRACKED_DB = REPO_ROOT / "pla_watch.db"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_update.yml"
PIPELINE = REPO_ROOT / "pipeline.py"
STORAGE = REPO_ROOT / "storage" / "db.py"

#: The exact message the API returned on 2026-08-25. Kept verbatim because the
#: classifier matches on its text, and a reworded marker list that no longer
#: matched it would turn an account block back into 55 doomed per-article calls.
USAGE_LIMIT_MESSAGE = (
    "Error code: 400 - {'type': 'error', 'error': {'type': "
    "'invalid_request_error', 'message': 'You have reached your specified API "
    "usage limits. You will regain access on 2026-09-01 at 00:00 UTC.'}}"
)

#: The other account-level wording this project has actually seen, 2026-08-07.
CREDIT_MESSAGE = (
    "Error code: 400 - {'type': 'error', 'error': {'type': "
    "'invalid_request_error', 'message': 'Your credit balance is too low to "
    "access the Anthropic API'}}"
)


class _FakeStatusError(Exception):
    """Stands in for `anthropic.APIStatusError` without importing the SDK."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class TestAnAccountBlockIsNotAnArticleFailure(unittest.TestCase):
    """
    The classification that stopped the run at 1 of 55 instead of 55 of 55.

    On 2026-07-31 nothing distinguished the two cases and the pipeline made 40
    further doomed calls. The distinction is the whole reason the incident cost
    one attempt rather than a queue's worth.
    """

    def classify(self, status, message):
        from analysis.analyzer import _classify_status_error
        return _classify_status_error(_FakeStatusError(status, message))

    def test_the_usage_limit_message_aborts_the_run(self):
        from analysis.analyzer import FatalAPIError
        self.assertIsInstance(self.classify(400, USAGE_LIMIT_MESSAGE),
                              FatalAPIError)

    def test_the_credit_exhaustion_message_aborts_the_run(self):
        from analysis.analyzer import FatalAPIError
        self.assertIsInstance(self.classify(400, CREDIT_MESSAGE), FatalAPIError)

    def test_an_ordinary_400_is_still_a_per_article_failure(self):
        """
        A 400 is not fatal on its own — the status is how a malformed request
        for ONE article arrives. Treating every 400 as an account block would
        abort a whole run over a single bad document.
        """
        from analysis.analyzer import AnalysisError, FatalAPIError
        result = self.classify(400, "Error code: 400 - prompt is too long")
        self.assertIsInstance(result, AnalysisError)
        self.assertNotIsInstance(result, FatalAPIError)

    def test_the_always_account_level_statuses_abort_without_reading_the_text(self):
        from analysis.analyzer import FatalAPIError, _FATAL_STATUS_CODES
        self.assertEqual(_FATAL_STATUS_CODES, frozenset({401, 402, 403}))
        for status in sorted(_FATAL_STATUS_CODES):
            with self.subTest(status=status):
                self.assertIsInstance(self.classify(status, "no useful text"),
                                      FatalAPIError)

    def test_the_marker_list_still_matches_both_messages_it_was_written_for(self):
        from analysis.analyzer import _FATAL_MESSAGE_MARKERS
        for message in (USAGE_LIMIT_MESSAGE, CREDIT_MESSAGE):
            with self.subTest(message=message[:48]):
                lowered = message.lower()
                self.assertTrue(
                    any(m in lowered for m in _FATAL_MESSAGE_MARKERS),
                    "no marker matches a message this project has actually "
                    "received; an account block would be retried per article")


class TestTheQueueIsSelectedByStateNotByRun(unittest.TestCase):
    """
    Property 1. If either selector filtered on `scrape_run_id`, the 30 records
    run 121 stored would have been invisible to run 122 and stranded forever.
    """

    def source(self):
        return STORAGE.read_text(encoding="utf-8")

    def _sql_of(self, func_name):
        tree = ast.parse(self.source())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return " ".join(
                    n.value for n in ast.walk(node)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                )
        self.fail("%s not found" % func_name)

    def test_unscored_selection_is_a_pure_state_predicate(self):
        sql = " ".join(self._sql_of("get_articles_unscored").split())
        self.assertIn("passed_relevance IS NULL", sql)
        self.assertNotIn("scrape_run_id", sql,
                         "unscored selection filtered by run — records from an "
                         "earlier run would never be picked up")

    def test_pending_selection_resumes_anything_scored_but_unanalyzed(self):
        sql = " ".join(self._sql_of("get_articles_pending_analysis").split())
        self.assertIn("passed_relevance = 1", sql)
        self.assertIn("analyzed_at IS NULL", sql)
        self.assertNotIn("scrape_run_id", sql)

    def test_both_selectors_return_every_matching_row_with_no_ceiling(self):
        """
        A LIMIT here would cap recovery below the daily cap and hide the rest.
        The cap belongs in the pipeline, where it is logged and reserved
        against, not in the query.
        """
        for func in ("get_articles_unscored", "get_articles_pending_analysis"):
            with self.subTest(selector=func):
                self.assertNotIn("LIMIT", self._sql_of(func).upper())


class TestTheBacklogCannotBeStarved(unittest.TestCase):
    """
    Property 2. `(new + backlog)[:cap]` would spend the entire cap on fresh
    scrapes every single day — the daily scrape rate is above the cap — and the
    outage backlog would never move.
    """

    def test_a_share_of_the_cap_is_reserved_for_the_backlog(self):
        from config import BACKLOG_RESERVE_FRACTION, DAILY_ANALYSIS_CAP
        self.assertGreater(BACKLOG_RESERVE_FRACTION, 0)
        self.assertLess(BACKLOG_RESERVE_FRACTION, 1)
        self.assertGreaterEqual(round(DAILY_ANALYSIS_CAP * BACKLOG_RESERVE_FRACTION), 1)

    def test_the_reservation_survives_a_day_that_scrapes_more_than_the_cap(self):
        """
        The arithmetic the pipeline performs, applied to the incident's own
        numbers: 30 new arrivals against an 802-deep queue.
        """
        from config import BACKLOG_RESERVE_FRACTION, DAILY_ANALYSIS_CAP
        cap = DAILY_ANALYSIS_CAP
        for new_count in (0, 5, 30, cap, cap * 3):
            with self.subTest(new=new_count):
                backlog = 802
                backlog_slots = min(backlog,
                                    max(1, round(cap * BACKLOG_RESERVE_FRACTION)))
                new_take = min(new_count, cap - backlog_slots)
                backlog_take = min(backlog, cap - new_take)
                self.assertGreater(
                    backlog_take, 0,
                    "a day scraping %d articles starved the backlog" % new_count)
                self.assertLessEqual(new_take + backlog_take, cap)

    def test_recent_unscreened_records_drain_before_the_archive(self):
        """
        The live-window split. Without it the 30 records from the outage sit
        behind ~769 older ones and cannot reach the edition covering their own
        week — the 2026-08-02 finding, and the reason this ordering exists.
        """
        from config import LIVE_BACKLOG_DAYS
        self.assertGreaterEqual(LIVE_BACKLOG_DAYS, 7)
        source = PIPELINE.read_text(encoding="utf-8")
        self.assertIn("live_rows", source)
        self.assertIn("archive_rows", source)
        self.assertIn("live_rows + archive_rows", source,
                      "the live/archive ordering was removed; recent "
                      "unscreened records fall behind the archive again")


class TestTheBillingMarkerIsScopedToOneDay(unittest.TestCase):
    """
    Property 3. The marker exists to stop the remaining PAID retries on the day
    of the block. If it ever suppressed the following day, an outage would
    become permanent silence and every later collection would be lost.
    """

    GUARD_STATE = REPO_ROOT / ".github" / "state" / "last_daily_run_date.txt"
    GUARD_FAIL = REPO_ROOT / ".github" / "state" / "last_billing_failure_date.txt"

    @staticmethod
    def _run_guard(last_run, last_failure, is_manual=False):
        """
        Execute the workflow's ACTUAL guard body against temporary state files.

        The body is extracted from `daily_update.yml` and run, not transcribed:
        a transcription keeps passing after someone edits the workflow, which is
        the one way these assertions could quietly become decorative. It reads
        the real clock, so the cases below are expressed relative to today —
        which is also how the guard is experienced in production.
        """
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step = workflow.split("- name: Scheduling guard", 1)[1]
        body = textwrap.dedent(
            step.split("python - <<'PY'", 1)[1].split("\n          PY", 1)[0])

        tmp = tempfile.mkdtemp(prefix="guard-")
        try:
            state = Path(tmp) / ".github" / "state"
            state.mkdir(parents=True)
            (state / "last_daily_run_date.txt").write_text(last_run)
            (state / "last_billing_failure_date.txt").write_text(last_failure)
            out = Path(tmp) / "github_output"
            out.write_text("")

            cwd = os.getcwd()
            saved = dict(os.environ)
            stdout = io.StringIO()
            try:
                os.chdir(tmp)
                os.environ["GITHUB_EVENT_NAME"] = (
                    "workflow_dispatch" if is_manual else "schedule")
                os.environ["GITHUB_OUTPUT"] = str(out)
                with contextlib.redirect_stdout(stdout):
                    exec(compile(body, "daily_update.yml::Scheduling guard",
                                 "exec"), {"__name__": "guard_under_test"})
                written = out.read_text()
            finally:
                os.chdir(cwd)
                os.environ.clear()
                os.environ.update(saved)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        match = re.search(r"should_run=(\w+)", written)
        assert match, "the guard wrote no decision to GITHUB_OUTPUT"
        return match.group(1) == "true"

    @staticmethod
    def _ny(offset_days=0):
        from datetime import timedelta
        return (datetime.now(ZoneInfo("America/New_York"))
                + timedelta(days=offset_days)).strftime("%Y-%m-%d")

    def test_a_marker_written_today_blocks_todays_remaining_windows(self):
        """The incident's own shape: yesterday ran, today failed on billing."""
        self.assertFalse(self._run_guard(last_run=self._ny(-1),
                                         last_failure=self._ny(0)))

    def test_a_marker_written_yesterday_does_not_block_today(self):
        """
        The property the whole recovery rests on. If this ever returns False,
        one billing outage becomes permanent silence and every later day's
        collection is lost.
        """
        self.assertTrue(self._run_guard(last_run=self._ny(-2),
                                        last_failure=self._ny(-1)))

    def test_an_old_marker_does_not_block_anything(self):
        """Dates far enough back that they cannot collide with the real clock."""
        self.assertTrue(self._run_guard(last_run=self._ny(-30),
                                        last_failure=self._ny(-29)))

    def test_a_completed_day_still_blocks_a_repeat_run(self):
        self.assertFalse(self._run_guard(last_run=self._ny(0),
                                         last_failure="2026-08-09"))

    def test_a_manual_dispatch_is_never_blocked_by_the_marker(self):
        """The documented recovery route has to stay open on the failing day."""
        self.assertTrue(self._run_guard(last_run=self._ny(-1),
                                        last_failure=self._ny(0),
                                        is_manual=True))

    def test_a_failed_day_is_not_recorded_as_a_completed_day(self):
        """
        The success marker is written after deploy, under implicit success().
        A failed run must leave it alone, or the day is recorded as done and
        the collection that did happen is never republished.
        """
        workflow = WORKFLOW.read_text(encoding="utf-8")
        success_step = workflow.split("Record successful run", 1)[1]
        self.assertIn("last_daily_run_date.txt", success_step)
        self.assertNotIn("always()", success_step.split("- name:", 1)[0],
                         "the success marker became unconditional")

    def test_the_two_markers_are_separate_files(self):
        from pipeline import BILLING_FAILURE_STATE_FILE
        self.assertNotEqual(BILLING_FAILURE_STATE_FILE,
                            ".github/state/last_daily_run_date.txt")
        self.assertTrue(self.GUARD_STATE.is_file())
        self.assertTrue(self.GUARD_FAIL.is_file())


class TestTheMarkerDateAgreesWithTheGuardDate(unittest.TestCase):
    """
    Property 4, and the one that is currently true by coincidence.

    `_write_billing_failure_marker` writes `date.today()` — UTC on a GitHub
    runner. The guard compares against America/New_York. They agree only while
    every cron window falls on the same calendar date in both zones.
    """

    def cron_windows(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        schedule = workflow.split("schedule:", 1)[1].split("workflow_dispatch", 1)[0]
        return re.findall(r"cron:\s*'(\d+)\s+(\d+)\s+\*\s+\*\s+\*'", schedule)

    def test_the_workflow_still_declares_cron_windows(self):
        self.assertTrue(self.cron_windows(), "no cron windows found to check")

    def test_every_cron_window_lands_on_one_date_in_both_zones(self):
        ny = ZoneInfo("America/New_York")
        # Both DST phases, so a schedule that is safe in August but not in
        # January cannot pass.
        for probe in (date(2026, 1, 15), date(2026, 8, 25)):
            for minute, hour in self.cron_windows():
                utc = datetime(probe.year, probe.month, probe.day,
                               int(hour), int(minute), tzinfo=timezone.utc)
                with self.subTest(cron="%s %s" % (minute, hour), on=probe):
                    self.assertEqual(
                        utc.date(), utc.astimezone(ny).date(),
                        "cron %s:%s UTC falls on a different New York date. "
                        "The billing marker is written from the runner's UTC "
                        "date and the scheduling guard reads New York — this "
                        "window would write a marker for a day that never "
                        "failed, or fail to write one for a day that did."
                        % (hour, minute))

    def test_the_marker_is_written_from_the_runs_target_date(self):
        source = PIPELINE.read_text(encoding="utf-8")
        self.assertIn("_write_billing_failure_marker(target_date)", source)
        self.assertIn("target   = args.date or date.today()", source)


class TestRecoveryIsIdempotentAgainstTheStoredCorpus(unittest.TestCase):
    """
    A retry must not re-analyze what is already analyzed. Re-running is the
    documented response to this incident, so paying twice for the same records
    would make the runbook itself expensive.
    """

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="recovery-"))
        cls.db = cls.tmp / "copy.db"
        shutil.copy(TRACKED_DB, cls.db)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def conn(self):
        c = sqlite3.connect(str(self.db))
        c.execute("PRAGMA query_only=ON")
        return c

    def test_an_analyzed_record_matches_neither_selector(self):
        """The two selectors are disjoint from the analyzed set."""
        c = self.conn()
        try:
            overlap = c.execute(
                "SELECT COUNT(*) FROM articles "
                " WHERE analyzed_at IS NOT NULL "
                "   AND (passed_relevance IS NULL OR "
                "        (passed_relevance = 1 AND analyzed_at IS NULL))"
            ).fetchone()[0]
        finally:
            c.close()
        self.assertEqual(overlap, 0,
                         "an already-analyzed record would be re-queued and "
                         "paid for again")

    def test_the_state_partition_is_exhaustive_and_disjoint(self):
        c = self.conn()
        try:
            total = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            parts = c.execute("""
                SELECT SUM(CASE WHEN passed_relevance IS NULL THEN 1 ELSE 0 END),
                       SUM(CASE WHEN passed_relevance = 0 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN passed_relevance = 1
                                 AND analyzed_at IS NOT NULL THEN 1 ELSE 0 END),
                       SUM(CASE WHEN passed_relevance = 1
                                 AND analyzed_at IS NULL THEN 1 ELSE 0 END)
                  FROM articles""").fetchone()
        finally:
            c.close()
        self.assertEqual(sum(parts), total,
                         "the four processing states do not partition the "
                         "corpus; a record in no state is a record nothing "
                         "will ever pick up")

    def test_collection_stores_a_record_before_any_paid_call(self):
        """
        The property that made this incident survivable at all. If storage
        happened after analysis, an account block would discard the day's
        collection — the 2026-07-17→24 loss mode.
        """
        source = PIPELINE.read_text(encoding="utf-8")
        stored_at = source.index("Stored %d new articles")
        analysis_at = source.index("from analysis.analyzer import Analyzer")
        self.assertLess(stored_at, analysis_at,
                        "articles are no longer stored before the first paid "
                        "call; an account block would now lose the day")


class TestNoProviderCallHappensInThisSuite(unittest.TestCase):
    """
    Checked structurally rather than by scanning for strings: a scan would
    match the very list it is scanning for, and the question is what this
    module IMPORTS, not what it mentions.
    """

    NETWORKED = {"anthropic", "httpx", "requests", "urllib", "http", "socket"}

    def test_this_module_imports_no_network_client(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & self.NETWORKED, set(),
                         "this suite imports a network client")

    def test_the_analyzer_is_never_instantiated_here(self):
        """
        `Analyzer.__init__` builds a real client. The classifier is a pure
        function and is tested directly, so nothing here needs one.
        """
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        calls = [n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertNotIn("Analyzer", calls)


if __name__ == "__main__":
    unittest.main()
