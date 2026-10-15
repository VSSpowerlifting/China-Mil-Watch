"""Read-only historical Global Times quality review never deletes/corrects."""
import copy
import unittest

from scripts.audit_china_legacy_capture_quality import quality_cues, scan


def data():
    index = {
        "snapshot": {"date": "2026-10-14", "records": 5},
        "fields": ["id", "date", "source", "state", "title_en", "title_orig"],
        "sources": [
            {"code": "global_times_mil", "desk": {"code": "china"}},
            {"code": "sg_mindef_releases", "desk": {"code": "singapore"}},
        ],
        "states": [{"code": "analyzed"}, {"code": "not_selected"}],
        "trail_ids": [1],
        "records": [
            [1, "2026-07-06", 0, 1, "Missile test", ""],
            [2, "2026-07-08", 0, 0, "Joint Sea 2026", ""],
            [3, "2026-09-17", 0, 0, "After repaired extractor", ""],
            [4, "2026-07-08", 1, 0, "Other desk", ""],
            [5, "2026-07-09", 0, 0, "Normal article", ""],
        ],
    }
    def html(text):
        return ('<div class="original-text"><p>' + text
                + '</p></div><table><th scope="row">Original URL</th>'
                '<td class="prov-value"><a href="https://www.globaltimes.cn/test">Source</a></td></table>')
    pages = {
        1: html(("Unrelated articles ... " * 11) + "actual article fragment."),
        2: html("A very short excerpt about something else."),
        5: html("An actual report consisting of substantive reporting. " * 15),
    }
    return index, pages


class HistoricalCaptureAuditTest(unittest.TestCase):
    def test_historical_scope_only_and_custody_untouched(self):
        index, pages = data()
        frozen = copy.deepcopy((index, pages))
        result = scan(index, pages)
        self.assertEqual((index, pages), frozen)
        self.assertEqual(result["legacy_records_scanned"], 3)
        self.assertEqual(result["flagged_for_manual_quality_review"], 2)
        self.assertEqual({r["id"] for r in result["candidates"]}, {1, 2})
        self.assertTrue(any(r["published_brief_trail"] for r in result["candidates"]))
        self.assertEqual(result["all_source_records_preserved"], 5)
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["original_capture_repair_authorized"])

    def test_short_genuine_articles_can_trigger_review_without_deletion(self):
        result = quality_cues("Short real press statement")
        self.assertIn("short_capture_review", result["cues"])
        self.assertNotIn("verified_corrupt", result["cues"])
        self.assertEqual(quality_cues("ordinary text " * 50)["cues"], [])

    def test_no_silent_skips_for_missing_records(self):
        index, pages = data()
        del pages[1]
        with self.assertRaisesRegex(ValueError, "HTML missing"):
            scan(index, pages)
        index, pages = data()
        index["trail_ids"] = [999]
        with self.assertRaisesRegex(ValueError, "source trail"):
            scan(index, pages)

    def test_wrong_source_and_repeated_id_fail_closed(self):
        index, pages = data()
        index["records"].append(list(index["records"][0]))
        with self.assertRaisesRegex(ValueError, "repeated"):
            scan(index, pages)
        index, pages = data()
        index["records"][0][2] = 999
        with self.assertRaisesRegex(ValueError, "source index"):
            scan(index, pages)

    def test_real_ellipsis_cues_are_not_a_factual_claim(self):
        suspect = quality_cues("Different headline ... Another teaser ... Third teaser ... End.")
        self.assertIn("multiple_ellipsis_teaser_cues", suspect["cues"])
        self.assertGreaterEqual(suspect["ellipsis_count"], 3)
        self.assertIn("short_capture_review", suspect["cues"])


if __name__ == "__main__":
    unittest.main()
