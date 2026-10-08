"""Synthetic-only regression tests for forward listing-window risk signals."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from scripts.vn_journal_forward_window_audit import audit_forward_windows
from scripts.vn_journal_window_drift import ObservationRefused
from tests.test_vn_journal_window_drift import observation


def candidate_dates(snapshot, category, dates):
    section = next(s for s in snapshot["sections"] if s["category"] == category)
    if len(dates) != len(section["candidates"]):
        raise ValueError("test data mismatch")
    for candidate, hint in zip(section["candidates"], dates):
        candidate["date_hint"] = hint
    return snapshot


class JournalForwardAuditTests(unittest.TestCase):
    def test_turnover_and_reappearance_are_not_publications_or_deletions(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z",
                            {"news": [26936, 26919]})
        second = observation("observed-b", "2026-10-09T03:00:00Z",
                             {"news": [26919, 26937]})
        third = observation("observed-c", "2026-10-10T05:00:00Z",
                            {"news": [26936, 26937]})
        result = audit_forward_windows([first, second, third],
                                       reference_gap_hours=24)
        news = result["transitions"][0]["windows"]["news"]
        self.assertEqual(news["previous_visible"], 2)
        self.assertEqual(news["overlap_count"], 1)
        self.assertEqual(news["previous_id_retention_fraction"], 0.5)
        self.assertEqual(news["first_observed_count"], 1)
        self.assertEqual(news["no_longer_visible_count"], 1)
        self.assertEqual(result["transitions"][1]["windows"]["news"]["reappeared_count"], 1)
        self.assertEqual(result["warning_counts"]["gaps_over_reference"], 2)
        self.assertFalse(news["new_publications_inferred"])
        self.assertFalse(news["publisher_deletion_inferred"])
        self.assertFalse(result["forward_capture_completeness_proven"])

    def test_union_overlaps_even_when_one_category_loses_sidebar_link(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z", {
            "news": [26936], "events-and-comments": [26936]
        })
        second = observation("observed-b", "2026-10-09T01:00:00Z", {
            "news": [26936], "events-and-comments": [26938]
        })
        result = audit_forward_windows([first, second])
        windows = result["transitions"][0]["windows"]
        self.assertEqual(windows["news"]["previous_id_retention_fraction"], 1)
        self.assertEqual(windows["events-and-comments"]["overlap_count"], 0)
        self.assertEqual(windows["union"]["no_longer_visible_count"], 0)
        self.assertEqual(result["transitions"][0]["zero_overlap_listing_pages"],
                         ["events-and-comments"])
        self.assertFalse(result["publisher_deletions_inferred"])

    def test_provisional_hint_drift_on_same_identity_requires_review(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z",
                            {"news": [26936]})
        second = observation("observed-b", "2026-10-09T01:00:00Z",
                             {"news": [26936]})
        candidate_dates(first, "news", ["2026-09-29"])
        candidate_dates(second, "news", ["2026-09-30"])
        result = audit_forward_windows([first, second])
        self.assertEqual(result["transitions"][0]["date_hint_changed_ids_to_review"],
                         ["vndj-en:26936"])
        self.assertEqual(result["warning_counts"]["date_hint_changed_ids"], 1)
        self.assertFalse(result["candidate_dates_verified"])

    def test_future_hint_is_compared_against_vietnam_local_calendar_day(self):
        first = observation("observed-a", "2026-10-07T18:00:00Z",
                            {"news": [26936]})
        second = observation("observed-b", "2026-10-08T18:00:00Z",
                             {"news": [26936]})
        # 18:00Z on October 7 is 01:00 local on October 8.
        candidate_dates(first, "news", ["2026-10-09"])
        candidate_dates(second, "news", ["2026-10-09"])
        result = audit_forward_windows([first, second])
        self.assertEqual(result["observations"][0]["observation_local_day_vietnam"],
                         "2026-10-08")
        self.assertEqual(result["observations"][1]["observation_local_day_vietnam"],
                         "2026-10-09")
        self.assertEqual(result["observations"][0]["future_hint_ids_to_review"],
                         ["vndj-en:26936"])
        self.assertEqual(result["observations"][1]["future_hint_ids_to_review"], [])
        self.assertEqual(result["warning_counts"]["future_date_hint_ids"], 1)

    def test_same_observation_day_cluster_is_cue_not_proof(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z", {
            "news": [26936, 26937, 26938]
        })
        second = observation("observed-b", "2026-10-09T01:00:00Z", {
            "news": [26936, 26937, 26938]
        })
        candidate_dates(first, "news", ["2026-10-08"] * 3)
        candidate_dates(second, "news", ["2026-10-08"] * 3)
        result = audit_forward_windows([first, second])
        clusters = result["observations"][0]["possible_site_clock_clusters"]
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["listing_page"], "news")
        self.assertEqual(len(clusters[0]["ids_to_review"]), 3)
        self.assertFalse(clusters[0]["suspected_clock_contamination_proven"])
        self.assertEqual(result["observations"][1]["possible_site_clock_clusters"], [])

    def test_stable_listing_and_no_warning_never_qualifies_collection(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z")
        second = observation("observed-b", "2026-10-09T01:00:00Z")
        result = audit_forward_windows([first, second])
        # Keep explicit zero-valued metrics in the stable report schema.
        self.assertTrue(all(count == 0 for count in result["warning_counts"].values()))
        self.assertIsNone(result["transitions"][0]["above_reference_gap"])
        self.assertFalse(result["eligible_for_shadow_activation"])
        self.assertFalse(result["historical_completeness_proven"])
        self.assertFalse(result["forward_capture_completeness_proven"])
        self.assertFalse(result["publisher_access_and_rights_validated_by_this_report"])
        self.assertTrue(result["needs_independent_rights_review"])
        self.assertFalse(result["journal_day_zero_started"])

    def test_observation_with_missing_date_hint_is_not_dropped(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z",
                            {"news": [26936, 26937]})
        second = observation("observed-b", "2026-10-09T01:00:00Z",
                             {"news": [26936, 26937]})
        candidate_dates(first, "news", [None, "2026-09-30"])
        candidate_dates(second, "news", [None, "2026-09-30"])
        result = audit_forward_windows([first, second])
        self.assertEqual(result["observations"][0]["listing_pages"]["news"]["null_date_hint_links"], 1)
        self.assertEqual(result["observations"][0]["visible_unique_ids"], 5)
        self.assertEqual(result["observations"][0]["null_date_hint_unique_ids"], 1)

    def test_invalid_reference_thresholds_refused(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z")
        second = observation("observed-b", "2026-10-09T01:00:00Z")
        for invalid in (True, False, 0, -2, float("nan"), float("inf"), 721, "24"):
            with self.subTest(value=str(invalid)), self.assertRaises(ObservationRefused):
                audit_forward_windows([first, second], reference_gap_hours=invalid)

    def test_reuses_strict_existing_validator_and_temporal_order(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z")
        second = observation("observed-b", "2026-10-09T01:00:00Z")
        bad = copy.deepcopy(second)
        bad["sections"][0]["publisher_html"] = "<p>Should not enter observation schema</p>"
        with self.assertRaises(ObservationRefused):
            audit_forward_windows([first, bad])
        same = copy.deepcopy(second)
        same["observation_id"] = "observed-a"
        with self.assertRaisesRegex(ObservationRefused, "duplicate evidence"):
            audit_forward_windows([first, same])
        with self.assertRaisesRegex(ObservationRefused, "increasing"):
            audit_forward_windows([second, first])

    def test_rejects_identity_conflict_across_two_runs(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z",
                            {"news": [26936]})
        second = observation("observed-b", "2026-10-09T01:00:00Z",
                             {"news": [26936]})
        second["sections"][0]["candidates"][0]["canonical_url"] = (
            "https://tapchiqptd.vn/en/news/changed-article/26936.html"
        )
        with self.assertRaisesRegex(ObservationRefused, "changed for one ID"):
            audit_forward_windows([first, second])

    def test_bounded_input_limits(self):
        first = observation("observed-a", "2026-10-08T01:00:00Z")
        with self.assertRaises(ObservationRefused):
            audit_forward_windows([first])
        with self.assertRaises(ObservationRefused):
            audit_forward_windows([first] * 91)

    def test_no_network_or_state_writes(self):
        import inspect
        from scripts import vn_journal_forward_window_audit
        code = inspect.getsource(vn_journal_forward_window_audit)
        for disallowed in ("requests.", "urlopen(", "sqlite3", "write_text(", "open(", "gh-pages"):
            with self.subTest(token=disallowed):
                self.assertNotIn(disallowed, code)


if __name__ == "__main__":
    unittest.main()
