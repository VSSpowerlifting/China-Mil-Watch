"""Read-only China duplicate audit: false merges, protection and fidelity cues."""
import copy
import unittest

from scripts.audit_china_duplicate_candidates import (
    duplicate_candidates, normalized_title, text_quality_warning)


def fixture():
    title = "福建海警位金门附近海域依法开展常态执法巡查"
    return {
        "snapshot": {"date": "2026-10-14", "records": 8},
        "fields": ["id", "date", "source", "state", "title_en", "title_orig"],
        "sources": [
            {"code": "pla_daily", "desk": {"code": "china"}},
            {"code": "mod_china", "desk": {"code": "china"}},
            {"code": "sg_mindef_releases", "desk": {"code": "singapore"}},
        ],
        "states": [{"code": "analyzed"}, {"code": "not_selected"}],
        "trail_ids": [2],
        "records": [
            [1, "2026-05-01", 0, 0, "", title],
            [2, "2026-05-02", 1, 1, "", title],
            [3, "2026-06-01", 0, 0, "", title],
            [4, "2026-06-02", 0, 0, "", title],
            [5, "2026-06-05", 0, 0, "", title],
            [6, "2026-06-07", 0, 0, "", title],
            [7, "2026-06-01", 2, 0, "", title],
            [8, "2026-07-01", 0, 0, "", "短"],
        ],
    }


class ChinaDuplicateCandidatesTest(unittest.TestCase):
    def test_date_bounded_groups_and_recurring_headlines(self):
        original = fixture()
        frozen = copy.deepcopy(original)
        report = duplicate_candidates(original)
        self.assertEqual(original, frozen)
        self.assertEqual(report["china_stored_records"], 7)
        self.assertEqual(report["candidate_group_count"], 3)
        self.assertEqual(report["records_in_candidate_groups"], 6)
        self.assertEqual(
            report["possible_redundant_occurrences_not_cleared_for_removal"], 3)
        self.assertEqual(report["cross_outlet_group_count"], 1)
        self.assertEqual(report["recurring_headline_family_count"], 1)
        self.assertEqual(
            {tuple(x["record_ids"]) for x in report["candidate_groups"]},
            {(1, 2), (3, 4), (5, 6)})
        self.assertTrue(report["never_a_publication_allowlist"])
        self.assertTrue(any(
            g["protected_trail_ids"] == [2] for g in report["candidate_groups"]))
        self.assertTrue(all(g["status"] == "requires_original_text_and_issuer_review"
                            for g in report["candidate_groups"]))

    def test_unimportant_format_differences_trigger_review_not_deletion(self):
        d = fixture()
        d["records"][1][5] = "【双语】福建海警位金门附近海域，依法开展常态执法巡查"
        self.assertEqual(duplicate_candidates(d)["candidate_group_count"], 3)
        self.assertEqual(normalized_title("【双语】今日，美军演训！"),
                         normalized_title("今日美军演训"))

    def test_corrupt_schema_missing_citations_and_bad_dates_fail_closed(self):
        d = fixture()
        del d["trail_ids"]
        with self.assertRaises(ValueError):
            duplicate_candidates(d)
        d = fixture()
        d["records"].append(list(d["records"][0]))
        with self.assertRaises(ValueError):
            duplicate_candidates(d)
        d = fixture()
        d["records"][0][1] = "not-a-date"
        with self.assertRaises(ValueError):
            duplicate_candidates(d)
        with self.assertRaises(ValueError):
            duplicate_candidates(fixture(), day_span=8)

    def test_stored_text_inspected_without_footer_contamination(self):
        messy = ('<div class="original-text"><p>Story ... other ... various ... '
                 'unrelated ... items ... many ... teasers.</p></div>'
                 '<footer>Unrelated repeated links ... ... ...</footer>')
        flagged = text_quality_warning(messy)
        self.assertEqual(flagged["status"], "needs_manual_review")
        self.assertIn("many_teaser_ellipses_possible_page_feed", flagged["reasons"])
        self.assertEqual(flagged["ellipsis_count"], 6)
        clean = '<div class="original-text"><p>' + ("文件正文" * 40) + '</p></div>'
        self.assertEqual(text_quality_warning(clean)["status"],
                         "no_heuristic_warning")
        self.assertEqual(text_quality_warning("<p>missing</p>")["status"],
                         "needs_manual_review")
        with_void = ('<div class="original-text"><p>' + ("本文。" * 45)
                     + '<br>continued</p></div>')
        self.assertEqual(text_quality_warning(with_void)["status"],
                         "no_heuristic_warning")


if __name__ == "__main__":
    unittest.main()
