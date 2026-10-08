"""Synthetic evidence only; no publisher text, network, DB or generated output."""
import copy
import unittest

from scripts.vn_journal_window_drift import (
    CATEGORIES, ObservationRefused, compare_observations, validate_observation,
)


def observation(name, date, candidates=()):
    """A synthetic four-page observation with visible numeric IDs by section."""
    sections = []
    for index, (category, url) in enumerate(CATEGORIES.items()):
        # A valid observed listing cannot be represented as an empty page.
        ids = candidates.get(category, [27001 + index]) if isinstance(candidates, dict) else (candidates or [27001 + index])
        sections.append({
            "category": category,
            "listing_url": url,
            "response_sha256": "a" * 64,
            "candidates": [{
                "source_identity": "vndj-en:%d" % ident,
                "canonical_url": "https://tapchiqptd.vn/en/theory-and-practice/synthetic-article/%d.html" % ident,
                "date_hint": "2026-09-30",
            } for ident in ids],
        })
    return {
        "schema": "ipr-vndj-listing-observation/1",
        "source_slug": "vn_national_defence_journal_en",
        "observed_at": date,
        "observation_id": name,
        "sections": sections,
        "source_html_retained": False,
        "article_text_retained": False,
        "pagination_proven": False,
        "historical_completeness_proven": False,
    }


class WindowDriftTest(unittest.TestCase):
    def test_first_seen_disappearance_and_reappearance(self):
        a = observation("first-run", "2026-10-08T01:00:00Z", {"news": [26936, 26919]})
        b = observation("second-run", "2026-10-09T01:00:00Z", {"news": [26919, 26937]})
        c = observation("third-run", "2026-10-10T01:00:00Z", {"news": [26936, 26937]})
        result = compare_observations([a, b, c])
        x = result["transitions"][0]["sections"]["news"]
        self.assertEqual(x["first_observed_ids"], ["vndj-en:26937"])
        self.assertEqual(x["no_longer_visible_ids"], ["vndj-en:26936"])
        self.assertEqual(x["retained"], 1)
        y = result["transitions"][1]["sections"]["news"]
        self.assertEqual(y["first_observed_ids"], [])
        self.assertEqual(y["reappeared_ids"], ["vndj-en:26936"])
        self.assertEqual(y["no_longer_visible_ids"], ["vndj-en:26919"])
        self.assertFalse(result["publisher_deletion_inferred"])
        self.assertFalse(result["historical_completeness_proven"])

    def test_recommendation_link_can_recur_on_multiple_listing_pages(self):
        a = observation("first-run", "2026-10-08T01:00:00Z", {"news": [26936], "events-and-comments": [26936]})
        b = observation("second-run", "2026-10-09T01:00:00Z", {"news": [26936]})
        result = compare_observations([a, b])
        self.assertEqual(result["transitions"][0]["sections"]["union"]["before_visible"], 3)
        self.assertEqual(result["transitions"][0]["sections"]["events-and-comments"]["no_longer_visible_ids"], ["vndj-en:26936"])
        self.assertEqual(result["transitions"][0]["sections"]["union"]["no_longer_visible_ids"], [])

    def test_rejects_authorized_retention_flag(self):
        p = observation("first-run", "2026-10-08T01:00:00Z")
        p["source_html_retained"] = True
        with self.assertRaises(ObservationRefused):
            validate_observation(p)

    def test_rejects_conflicting_permalink(self):
        p = observation("first-run", "2026-10-08T01:00:00Z", {"news": [26936], "theory-and-practice": [26936]})
        p["sections"][1]["candidates"][0]["canonical_url"] = "https://tapchiqptd.vn/en/news/other-article/26936.html"
        with self.assertRaisesRegex(ObservationRefused, "two canonical"):
            validate_observation(p)

    def test_rejects_wrong_identity_or_host(self):
        p = observation("first-run", "2026-10-08T01:00:00Z", {"news": [26936]})
        p["sections"][0]["candidates"][0]["source_identity"] = "vndj-en:26919"
        with self.assertRaisesRegex(ObservationRefused, "disagree"):
            validate_observation(p)
        p = observation("first-run", "2026-10-08T01:00:00Z", {"news": [26936]})
        p["sections"][0]["candidates"][0]["canonical_url"] = "https://evil.example/en/news/other/26936.html"
        with self.assertRaises(ObservationRefused):
            validate_observation(p)

    def test_rejects_missing_or_duplicate_category_and_prose(self):
        p = observation("first-run", "2026-10-08T01:00:00Z")
        p["sections"].pop()
        with self.assertRaises(ObservationRefused):
            validate_observation(p)
        p = observation("first-run", "2026-10-08T01:00:00Z")
        p["sections"][1] = copy.deepcopy(p["sections"][0])
        with self.assertRaises(ObservationRefused):
            validate_observation(p)
        p = observation("first-run", "2026-10-08T01:00:00Z")
        p["sections"][0]["html"] = "publisher HTML is forbidden"
        with self.assertRaises(ObservationRefused):
            validate_observation(p)

    def test_rejects_date_hint_and_bad_time_order(self):
        p = observation("first-run", "2026-10-08T01:00:00Z", {"news": [26936]})
        p["sections"][0]["candidates"][0]["date_hint"] = "2026-02-30"
        with self.assertRaisesRegex(ObservationRefused, "invalid date"):
            validate_observation(p)
        a = observation("first-run", "2026-10-09T01:00:00Z")
        b = observation("second-run", "2026-10-08T01:00:00Z")
        with self.assertRaisesRegex(ObservationRefused, "increasing"):
            compare_observations([a, b])

    def test_rejects_contradictory_local_dates_and_duplicate_ids(self):
        p = observation("first-run", "2026-10-08T01:00:00Z", {"news": [26936], "theory-and-practice": [26936]})
        p["sections"][1]["candidates"][0]["date_hint"] = "2026-09-29"
        with self.assertRaisesRegex(ObservationRefused, "contradictory"):
            validate_observation(p)
        p = observation("first-run", "2026-10-08T01:00:00Z", {"news": [26936]})
        p["sections"][0]["candidates"].append(copy.deepcopy(p["sections"][0]["candidates"][0]))
        with self.assertRaisesRegex(ObservationRefused, "repeated identity"):
            validate_observation(p)

    def test_rejects_canonical_url_drift_across_snapshots(self):
        a = observation("first-run", "2026-10-08T01:00:00Z", {"news": [26936]})
        b = observation("second-run", "2026-10-09T01:00:00Z", {"news": [26936]})
        b["sections"][0]["candidates"][0]["canonical_url"] = (
            "https://tapchiqptd.vn/en/theory-and-practice/changed-slug/26936.html"
        )
        with self.assertRaisesRegex(ObservationRefused, "changed for one ID"):
            compare_observations([a, b])

    def test_rejects_fake_completeness_and_aggregate_only(self):
        p = observation("first-run", "2026-10-08T01:00:00Z")
        p["historical_completeness_proven"] = True
        with self.assertRaises(ObservationRefused):
            validate_observation(p)
        p = observation("first-run", "2026-10-08T01:00:00Z")
        p["sections"][0]["candidate_count"] = 18
        with self.assertRaises(ObservationRefused):
            validate_observation(p)


if __name__ == "__main__":
    unittest.main()
