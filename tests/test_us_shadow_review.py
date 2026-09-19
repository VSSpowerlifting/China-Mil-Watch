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
        self.assertIn("ELIGIBLE FOR HUMAN REVIEW", joined)
        self.assertNotIn("PROMOTE", joined.upper().replace("PROMOTION", ""))
        self.assertIn("never a sufficient one", joined)
        self.assertIn("strongest result this tool can return", joined)
        self.assertIn("human editorial decision", joined)

    def test_a_failing_check_outranks_a_long_history(self):
        report = review.verdict(["2026-08-%02d" % d for d in range(1, 31)],
                                ["FAIL something is wrong"])
        self.assertIn("NOT READY", " ".join(report))

    def test_the_verdict_restates_the_framing_when_eligible(self):
        """The moment someone is most tempted to forget what this stream is."""
        joined = " ".join(review.verdict(
            ["2026-08-%02d" % d for d in range(1, 31)], ["ok   fine"]))
        for phrase in ("DVIDS USINDOPACOM-tagged reference stream",
                       "Tier B DoD media-service feed",
                       "not presently a peer of the China Desk",
                       "access_blocked"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, joined)

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

    def test_the_us_reviewer_borrows_no_singapore_constant(self):
        """
        The word "singapore" appears in this reviewer as an Indo-Pacific PLACE
        NAME in the diagnostic indicator list, which is correct and must stay.
        What must not appear is Singapore's desk identity, state branch, source
        slug or release-URL host -- the constants that would mean this tool was
        judging one desk by another's rules.
        """
        source = (REPO_ROOT / "scripts"
                  / "review_us_shadow_state.py").read_text(encoding="utf-8")
        body = source.split('"""', 2)[2].lower()
        for borrowed in ("mindef", "singapore-mindef", "sg_mindef",
                         "shadow/singapore", "latest-releases"):
            self.assertNotIn(borrowed, body, borrowed)
        # And the place name is present for the reason stated above.
        self.assertIn("singapore", [t.lower() for t in review.INDICATOR_TERMS])


if __name__ == "__main__":
    unittest.main()


class TestTheCheckpointReportDescribesTheStream(ReviewCase):
    """
    The nine things a reviewer needs in order to judge scope fitness without
    rerunning collection. Every one is a measurement; none is a gate.
    """

    def test_it_reports_the_total_eligible_news_records(self):
        self.collect()
        self.assertEqual(review.review(self.state)["eligible_news_records"], 3)

    def test_the_indicator_is_labelled_diagnostic_not_dispositive(self):
        self.collect()
        ind = review.review(self.state)["indicator"]
        self.assertEqual(ind["total"], 3)
        self.assertIn("diagnostic", ind["kind"])
        self.assertIn("not dispositive", ind["kind"])

    def test_the_indicator_counts_titles_generously(self):
        matched, hits = review.indicator_count([
            "Alaska, Kosovo youth build friendships",     # alaska -> hit
            "7th Fleet transits the Taiwan Strait",       # two terms -> 1 hit
            "Fort McCoy retiree appreciation day",        # no term
        ])
        self.assertEqual(matched, 2)
        self.assertEqual(len(hits), 2)

    def test_off_scope_themes_name_what_the_volume_actually_is(self):
        themes, misses, unmatched = review.off_scope_themes([
            "NCG-1 Announces FY27 CPO Pinning",
            "Fort McCoy Commemorative Area welcomes retiree visitors",
            "Guam readiness exercise concludes",          # indicator -> excluded
        ])
        labels = dict(themes)
        self.assertEqual(misses, 2)
        self.assertIn("ceremonial / recognition", labels)

    def test_the_indicator_overstates_rather_than_understates(self):
        """
        "Korean War soldier accounted for" is an interment story. The term
        list scores it as Indo-Pacific because it contains "korea".

        That is the intended direction of the error, and the reason every
        surface calls the count a diagnostic: it is a CEILING on Indo-Pacific
        presence, not an estimate of it. A list tuned to be accurate would be
        a classifier, and a classifier at this point in the pipeline is the
        filter the editorial decision ruled out.
        """
        matched, _ = review.indicator_count(["Korean War soldier accounted for"])
        self.assertEqual(matched, 1)
        _, misses, _ = review.off_scope_themes(["Korean War soldier accounted for"])
        self.assertEqual(misses, 0)

    def test_it_reports_publication_geography_and_units(self):
        self.collect()
        dist = review.review(self.state)["distributions"]
        # Every sampled article is a US domestic location, which is the point.
        self.assertTrue(dist["locations"])
        self.assertTrue(dist["units"])
        for loc in dist["locations"]:
            self.assertNotEqual(loc, "unrecorded")
        self.assertIn("188WG", dist["units"])

    def test_it_reports_duplicate_and_media_only_rates(self):
        self.collect(run_id="r1")
        self.collect(run_id="r2")
        rates = review.review(self.state)["rates"]
        self.assertEqual(rates["duplicates"], 3)
        self.assertEqual(rates["media_only"], 12)      # 6 per run, two runs
        self.assertGreater(rates["feed_items_seen"], rates["media_only"])

    def test_it_reports_daily_volume(self):
        self.collect()
        vol = review.review(self.state)["daily_volume"]
        self.assertEqual(vol["days"], 1)
        self.assertEqual(vol["total"], 3)
        self.assertEqual(vol["busiest_day"], "2026-09-16")

    def test_it_states_retention_pressure_as_a_count_not_a_duration(self):
        self.collect()
        joined = " ".join(review.review(self.state)["findings"])
        self.assertIn("fixed item count", joined)
        self.assertIn("unrecoverable", joined)

    def test_the_representative_sample_spreads_across_the_corpus(self):
        rows = [("u%d" % i, str(i), "title %d" % i, "body", "2026-09-%02d" % (i + 1))
                for i in range(30)]
        sample = review.representative_titles(rows, limit=5)
        self.assertEqual(len(sample), 5)
        self.assertEqual(len(set(sample)), 5)
        self.assertEqual(sample[0], "title 0")
        self.assertNotEqual(sample, [r[2] for r in rows[:5]])

    def test_a_small_corpus_is_sampled_whole(self):
        self.collect()
        sample = review.review(self.state)["representative_titles"]
        self.assertEqual(len(sample), 3)

    def test_scope_fitness_is_an_explicit_and_separate_verdict(self):
        self.collect()
        report = review.review(self.state)
        joined = " ".join(report["scope_fitness"])
        self.assertIn("SCOPE FITNESS:", joined)
        # Separate from the checkpoint verdict on purpose.
        self.assertNotIn("SCOPE FITNESS", " ".join(report["verdict"]))

    def test_a_low_indicator_share_reports_poor_fitness_for_a_human(self):
        lines = " ".join(review.scope_fitness({}, 15, 171, [], 156))
        self.assertIn("SCOPE FITNESS: POOR", lines)
        self.assertIn("editorial judgement for a human", lines)
        self.assertIn("OVERSTATES", lines)

    def test_a_high_indicator_share_still_defers_to_reading_the_corpus(self):
        lines = " ".join(review.scope_fitness({}, 160, 171, [], 11))
        self.assertIn("SCOPE FITNESS: STRONG", lines)
        self.assertIn("not a substitute for reading", lines)

    def test_scope_fitness_never_promotes_at_any_share(self):
        for matched in (0, 15, 90, 171):
            lines = " ".join(review.scope_fitness({}, matched, 171, [], 0))
            with self.subTest(matched=matched):
                self.assertNotIn("PROMOTE", lines.upper())

    def test_the_report_carries_the_framing_line(self):
        self.collect()
        framing = review.review(self.state)["framing"]
        for phrase in ("DVIDS USINDOPACOM-tagged reference stream",
                       "Tier B DoD media-service feed",
                       "not presently a peer of the China Desk",
                       "access_blocked"):
            self.assertIn(phrase, framing)

    def test_the_indicator_is_never_used_to_drop_a_record(self):
        # Every accepted record survives regardless of its title.
        self.collect()
        report = review.review(self.state)
        self.assertEqual(report["eligible_news_records"],
                         report["corpus"]["records"])
        self.assertGreater(report["corpus"]["records"],
                           report["indicator"]["matched"])


class TestTheIndicatorMatchesWordsNotFragments(unittest.TestCase):
    """
    Generous is not the same as wrong.

    The term list is deliberately a ceiling on Indo-Pacific presence, but a
    substring match made it a ceiling built partly on false matches: "india"
    fired on "Indiana", "laos" on "chaos", "guam" on nothing useful. Word
    boundaries keep the generosity and drop the nonsense.
    """

    def test_india_does_not_fire_on_indiana(self):
        self.assertEqual(review.indicator_count(
            ["Indiana National Guard unit returns home"])[0], 0)

    def test_india_and_indian_both_fire_on_the_real_thing(self):
        self.assertEqual(review.indicator_count(
            ["U.S., Indian Army forces begin Command Post Exercise"])[0], 1)
        self.assertEqual(review.indicator_count(["India visit concludes"])[0], 1)

    def test_laos_does_not_fire_on_chaos(self):
        self.assertEqual(review.indicator_count(["Managing chaos at sea"])[0], 0)

    def test_the_aor_states_are_covered(self):
        for title in ("Exercise concludes in the Philippines",
                      "Vietnam partnership deepens",
                      "Papua New Guinea engagement",
                      "Transit of the Taiwan Strait",
                      "Port call in Yokosuka"):
            with self.subTest(title=title):
                self.assertEqual(review.indicator_count([title])[0], 1, title)

    def test_the_list_remains_a_ceiling_not_an_estimate(self):
        # A Bering Sea interment story still scores. That is intended: the
        # count bounds Indo-Pacific presence from above and is never a verdict.
        self.assertEqual(review.indicator_count(
            ["Korean War soldier laid to rest in Maryland"])[0], 1)


class TestGeographyIsReportedAtTheGranularityDvidsRecorded(ReviewCase):
    """
    DVIDS records some items as "US" or "IN" with no place. Counting those
    beside full placenames makes an absence of detail read as a dominant
    location, which is how "US=11" ended up looking like a finding.
    """

    def test_country_and_place_are_reported_separately(self):
        self.collect()
        dist = review.review(self.state)["distributions"]
        self.assertIn("countries", dist)
        self.assertIn("locations", dist)
        self.assertIn("country_only", dist)

    def test_a_country_only_value_is_counted_as_such(self):
        self.collect()
        con = sqlite3.connect(str(self.state / "shadow.db"))
        try:
            con.execute("UPDATE shadow_records SET location='US' WHERE rowid=1")
            con.commit()
        finally:
            con.close()
        report = review.review(self.state)
        self.assertEqual(report["distributions"]["country_only"], 1)
        self.assertTrue(any("country only" in f for f in report["findings"]))

    def test_the_country_is_read_from_the_tail_of_the_place(self):
        self.collect()
        countries = review.review(self.state)["distributions"]["countries"]
        self.assertIn("US", countries)
