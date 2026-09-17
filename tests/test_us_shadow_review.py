"""
US shadow checkpoint review: it measures, and it never promotes.

These tests also hold the boundary the brief drew: the US desk is not reviewed
by Singapore's kit. Singapore's reviewer is bound to its own desk identity,
state branch, release-URL pattern and source slug, so pointing it at the US
would either judge one desk by another's rules or turn one tool into two.
"""

from __future__ import annotations

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
import scripts.review_us_shadow_state as review                 # noqa: E402
import scripts.shadow_collect_us as runner                      # noqa: E402
from tests.test_us_dvids_adapter import FakeSession, FakeSource  # noqa: E402

TARGET = date(2026, 9, 16)


def make_adapter(session=None, cap=40):
    return us.USDvidsAdapter(FakeSource(), session=session or FakeSession(),
                             cap=cap, sleeper=lambda _s: None)


class ReviewCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = Path(self._tmp.name) / "state"
        self.addCleanup(self._tmp.cleanup)

    def collect(self, run_id="r1", session=None):
        return runner.run(self.state, TARGET, 7, 40, run_id, "commit",
                          adapter=make_adapter(session))

    def stamp_days(self, days):
        """Re-date the ledger so continuity and day counting can be tested."""
        files = sorted((self.state / "ledger").glob("*.json"))
        self.assertEqual(len(files), len(days))
        for path, day in zip(files, days):
            entry = json.loads(path.read_text(encoding="utf-8"))
            entry["finished_utc"] = "%sT12:00:00+00:00" % day
            path.write_text(json.dumps(entry, indent=1, sort_keys=True),
                            encoding="utf-8")


class TestTheReviewerRefusesWhatItCannotReview(ReviewCase):

    def test_it_refuses_the_repository_working_tree(self):
        with self.assertRaises(review.ReviewError) as caught:
            review.review(REPO_ROOT)
        self.assertIn("refusing to review state", str(caught.exception))

    def test_it_refuses_a_directory_inside_the_repository(self):
        with self.assertRaises(review.ReviewError):
            review.review(REPO_ROOT / "scripts")

    def test_it_refuses_a_state_copy_with_no_ledger(self):
        empty = Path(self._tmp.name) / "empty"
        empty.mkdir()
        with self.assertRaises(review.ReviewError):
            review.review(empty)

    def test_it_refuses_an_empty_ledger(self):
        empty = Path(self._tmp.name) / "noruns"
        (empty / "ledger").mkdir(parents=True)
        with self.assertRaises(review.ReviewError) as caught:
            review.review(empty)
        self.assertIn("nothing has been collected", str(caught.exception))

    def test_it_refuses_an_unreadable_ledger_entry(self):
        self.collect()
        broken = sorted((self.state / "ledger").glob("*.json"))[0]
        broken.write_text("{not json", encoding="utf-8")
        with self.assertRaises(review.ReviewError) as caught:
            review.review(self.state)
        self.assertIn("not readable JSON", str(caught.exception))


class TestTheReviewerMeasuresACleanCorpus(ReviewCase):

    def test_a_single_good_run_passes_every_corpus_check(self):
        self.collect()
        report = review.review(self.state)
        failures = [f for f in report["findings"] if f.startswith("FAIL")]
        self.assertEqual(failures, [])
        self.assertTrue(report["passed"])

    def test_it_reports_the_record_and_identity_counts(self):
        self.collect()
        report = review.review(self.state)
        self.assertEqual(report["corpus"]["records"], 3)
        self.assertEqual(report["corpus"]["distinct_urls"], 3)
        self.assertEqual(report["corpus"]["distinct_identities"], 3)
        self.assertEqual(report["corpus"]["empty_bodies"], 0)

    def test_it_reconciles_the_rejection_taxonomy(self):
        self.collect()
        report = review.review(self.state)
        self.assertEqual(report["rejections"][us.R_NOT_NEWS_MEDIA], 6)
        self.assertIn("ok   every rejection reason is a declared one",
                      report["findings"])

    def test_an_undeclared_rejection_reason_is_a_failure(self):
        self.collect()
        path = sorted((self.state / "ledger").glob("*.json"))[0]
        entry = json.loads(path.read_text(encoding="utf-8"))
        entry["rejections"]["invented_reason"] = 4
        path.write_text(json.dumps(entry), encoding="utf-8")
        report = review.review(self.state)
        self.assertFalse(report["passed"])
        self.assertTrue(any("does not declare" in f
                            for f in report["findings"]))

    def test_an_empty_body_in_the_corpus_is_a_failure(self):
        self.collect()
        con = sqlite3.connect(str(self.state / "shadow.db"))
        try:
            con.execute("UPDATE shadow_records SET text_original = '' "
                        "WHERE rowid = 1")
            con.commit()
        finally:
            con.close()
        report = review.review(self.state)
        self.assertFalse(report["passed"])
        self.assertTrue(any("empty body" in f and f.startswith("FAIL")
                            for f in report["findings"]))

    def test_an_identity_that_disagrees_with_its_url_is_a_failure(self):
        self.collect()
        con = sqlite3.connect(str(self.state / "shadow.db"))
        try:
            con.execute("UPDATE shadow_records SET source_identity = '999' "
                        "WHERE rowid = 1")
            con.commit()
        finally:
            con.close()
        report = review.review(self.state)
        self.assertFalse(report["passed"])
        self.assertTrue(any("identity disagrees" in f
                            for f in report["findings"]))

    def test_a_foreign_desk_entry_in_the_ledger_is_a_failure(self):
        self.collect()
        path = sorted((self.state / "ledger").glob("*.json"))[0]
        entry = json.loads(path.read_text(encoding="utf-8"))
        entry["desk"] = "singapore-mindef"
        path.write_text(json.dumps(entry), encoding="utf-8")
        report = review.review(self.state)
        self.assertFalse(report["passed"])
        self.assertTrue(any("another desk" in f for f in report["findings"]))


class TestTheClockAndTheGapsAreMeasuredNotAssumed(ReviewCase):

    def test_day_zero_must_be_the_first_successful_run(self):
        self.collect(run_id="r1")
        clock = self.state / "clock.json"
        clock.write_text(json.dumps({"day_zero_utc": "2026-01-01T00:00:00+00:00",
                                     "day_zero_run_id": "someone_else"}),
                         encoding="utf-8")
        report = review.review(self.state)
        self.assertFalse(report["passed"])
        self.assertTrue(any("day zero names run" in f
                            for f in report["findings"]))

    def test_a_gap_between_collecting_days_is_reported_as_unrecoverable(self):
        self.collect(run_id="r1")
        self.collect(run_id="r2")
        self.stamp_days(["2026-09-16", "2026-09-19"])
        report = review.review(self.state)
        self.assertFalse(report["passed"])
        gap = [f for f in report["findings"] if "UNRECOVERABLE" in f]
        self.assertEqual(len(gap), 1)
        self.assertIn("2 day(s) missing", gap[0])

    def test_consecutive_days_report_no_gap(self):
        self.collect(run_id="r1")
        self.collect(run_id="r2")
        self.stamp_days(["2026-09-16", "2026-09-17"])
        report = review.review(self.state)
        self.assertIn("ok   no gap between collecting days",
                      report["findings"])
        self.assertEqual(len(report["collecting_days"]), 2)

    def test_two_runs_on_one_day_are_one_collecting_day(self):
        self.collect(run_id="r1")
        self.collect(run_id="r2")
        self.stamp_days(["2026-09-16", "2026-09-16"])
        report = review.review(self.state)
        self.assertEqual(len(report["collecting_days"]), 1)

    def test_a_failed_run_is_not_a_collecting_day(self):
        self.collect(run_id="r1", session=FakeSession(feed_status=500))
        report_days = review.collecting_days(review.load_ledger(self.state))
        self.assertEqual(report_days, [])

    def test_two_consecutive_failures_are_a_failure_finding(self):
        self.collect(run_id="r1", session=FakeSession(feed_status=500))
        self.collect(run_id="r2", session=FakeSession(feed_status=500))
        report = review.review(self.state)
        self.assertTrue(any(f.startswith("FAIL") and "streak" in f
                            for f in report["findings"]))


class TestTheVerdictNeverPromotes(ReviewCase):

    def test_a_clean_short_history_is_not_ready(self):
        self.collect()
        report = review.review(self.state)
        joined = " ".join(report["verdict"])
        self.assertIn("NOT READY", joined)
        self.assertIn("1 day(s)", joined)

    def test_thirty_clean_days_reach_eligible_for_review_only(self):
        report = review.verdict(["2026-08-%02d" % d for d in range(1, 31)],
                                ["ok   everything"])
        joined = " ".join(report)
        self.assertIn("ELIGIBLE FOR REVIEW", joined)
        self.assertNotIn("PROMOTE", joined.upper().replace("PROMOTION", ""))
        self.assertIn("never a sufficient one", joined)
        self.assertIn("human editorial decision", joined)

    def test_a_failing_check_outranks_a_long_history(self):
        report = review.verdict(["2026-08-%02d" % d for d in range(1, 31)],
                                ["FAIL something is wrong"])
        self.assertIn("NOT READY", " ".join(report))

    def test_the_verdict_restates_the_scope_caveat_when_eligible(self):
        report = review.verdict(["2026-08-%02d" % d for d in range(1, 31)],
                                ["ok   fine"])
        self.assertIn("public affairs", " ".join(report))

    def test_the_tool_writes_nothing_anywhere(self):
        self.collect()
        before = {p: p.read_bytes() for p in self.state.rglob("*")
                  if p.is_file()}
        review.review(self.state)
        after = {p: p.read_bytes() for p in self.state.rglob("*")
                 if p.is_file()}
        self.assertEqual(after, before)


class TestTheUSDeskIsNotReviewedBySingaporesKit(unittest.TestCase):

    def test_singapores_reviewer_is_bound_to_singapore(self):
        import scripts.review_shadow_state as sg
        self.assertEqual(sg.DESK_IDENTITY, "singapore-mindef")
        self.assertEqual(sg.STATE_BRANCH, "shadow/singapore-mindef")

    def test_the_two_reviewers_do_not_share_a_desk_identity(self):
        import scripts.review_shadow_state as sg
        self.assertNotEqual(sg.DESK_IDENTITY, review.DESK_IDENTITY)
        self.assertNotEqual(sg.STATE_BRANCH, review.STATE_BRANCH)

    def test_the_us_reviewer_checks_things_singapores_has_no_concept_of(self):
        source = (REPO_ROOT / "scripts"
                  / "review_us_shadow_state.py").read_text(encoding="utf-8")
        self.assertIn("check_rejections", source)
        self.assertIn("UNRECOVERABLE", source)

    def test_the_us_reviewer_names_no_singapore_constant(self):
        source = (REPO_ROOT / "scripts"
                  / "review_us_shadow_state.py").read_text(encoding="utf-8")
        body = source.split('"""', 2)[2]
        self.assertNotIn("mindef", body.lower())
        self.assertNotIn("singapore", body.lower())


if __name__ == "__main__":
    unittest.main()
