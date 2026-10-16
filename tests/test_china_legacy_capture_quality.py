"""Read-only historical Global Times quality review never deletes/corrects."""
import copy
import unittest

from scripts.audit_china_legacy_capture_quality import ROOT, quality_cues, scan
from scripts.audit_china_original_source_notes import _original_record


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
            [3, "2026-07-05", 0, 0, "Older original collected after the fix", ""],
            [4, "2026-07-08", 1, 0, "Other desk", ""],
            [5, "2026-07-09", 0, 0, "Normal article", ""],
        ],
    }
    def html(text, collected_at="2026-07-06 16:01:17"):
        return ('<div class="original-text"><p>' + text
                + '</p></div><table><th scope="row">Original URL</th>'
                '<td class="prov-value"><a href="https://www.globaltimes.cn/test">Source</a></td>'
                '<tr><th scope="row">Collected at</th><td class="prov-value">'
                + collected_at + ' — collection metadata</td></tr></table>')
    pages = {
        1: html(("Unrelated articles ... " * 11) + "actual article fragment."),
        2: html("A very short excerpt about something else."),
        5: html("An actual report consisting of substantive reporting. " * 15),
        3: html("An actual later-captured report. " * 25,
                collected_at="2026-09-19 12:00:00"),
    }
    return index, pages


class HistoricalCaptureAuditTest(unittest.TestCase):
    def test_historical_scope_only_and_custody_untouched(self):
        index, pages = data()
        frozen = copy.deepcopy((index, pages))
        result = scan(index, pages)
        self.assertEqual((index, pages), frozen)
        self.assertEqual(result["legacy_records_scanned"], 3)
        self.assertEqual(result["all_global_times_records_examined"], 4)
        self.assertEqual(result["excluded_captured_after_repair"], 1)
        self.assertEqual(result["flagged_for_manual_quality_review"], 2)
        self.assertEqual({r["id"] for r in result["candidates"]}, {1, 2})
        self.assertEqual(result["unflagged_control_ids"], [5])
        self.assertTrue(any(r["published_brief_trail"] for r in result["candidates"]))
        self.assertEqual(result["all_source_records_preserved"], 5)
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["original_capture_repair_authorized"])

    def test_pre_fix_historical_controls_stay_retired_without_republication(self):
        # These nine original Global Times records were intentionally retired
        # with the 4,400-record China cull. The public repository no longer
        # carries their source bodies, so it cannot honestly re-evaluate their
        # historical capture quality. Their exact source-body review remains
        # a private historical task; synthetic cue calibration stays covered
        # in this module. Never reintroduce the removed pages as test fixtures.
        from scripts.reconcile_db import read_only
        from core.retired_article_urls import verify_no_active_retired_urls
        historical_ids = (170, 793, 1246, 1954, 2753, 3180, 3181, 792, 1630)
        with read_only(ROOT / "pla_watch.db") as con:
            self.assertEqual(verify_no_active_retired_urls(con), 4400)
            retired_ids = {r[0] for r in con.execute(
                "SELECT original_article_id FROM retired_article_urls")}
            live_ids = {r[0] for r in con.execute("SELECT id FROM articles")}
        for ident in historical_ids:
            with self.subTest(ident=ident):
                self.assertIn(ident, retired_ids)
                self.assertNotIn(ident, live_ids)
                self.assertFalse(
                    (ROOT / "output" / "record" / ("%d.html" % ident)).exists())
                self.assertFalse(
                    (ROOT / "output" / "article" / ("%d.html" % ident)).exists())

    def test_short_genuine_articles_can_trigger_review_without_deletion(self):
        result = quality_cues("Short real press statement")
        self.assertIn("very_short_capture", result["cues"])
        self.assertNotIn("verified_corrupt", result["cues"])
        self.assertEqual(quality_cues("ordinary text " * 50)["cues"], [])

    def test_calibrated_two_ellipsis_short_snippets_get_review_not_verdict(self):
        bad = "Unrelated first article ... Another unrelated teaser ... "
        self.assertIn("short_multi_teaser_capture_review", quality_cues(bad)["cues"])
        authentic_long = bad + ("Actual longer article body. " * 35)
        self.assertNotIn(
            "short_multi_teaser_capture_review", quality_cues(authentic_long)["cues"])
        self.assertNotIn("proven_corrupt", quality_cues(bad)["cues"])
        self.assertEqual(quality_cues("Clean original text. " * 40)["cues"], [])

    def test_no_silent_skips_for_missing_records(self):
        index, pages = data()
        del pages[1]
        with self.assertRaisesRegex(ValueError, "HTML missing"):
            scan(index, pages)
        index, pages = data()
        index["trail_ids"] = [999]
        with self.assertRaisesRegex(ValueError, "source trail"):
            scan(index, pages)

    def test_missing_collected_timestamp_is_not_guessed_from_publication(self):
        index, pages = data()
        pages[1] = pages[1].replace("Collected at", "Published at")
        with self.assertRaisesRegex(ValueError, "collection timestamp"):
            scan(index, pages)

    def test_missing_stored_prose_is_flagged_without_inventing_body(self):
        index, pages = data()
        pages[5] = pages[5][pages[5].index("<table>"):]
        result = scan(index, pages)
        match = next(r for r in result["candidates"] if r["id"] == 5)
        self.assertIn("unreadable_or_missing_stored_text", match["cues"])
        self.assertEqual(match["stored_characters"], 0)
        pages[5] = "<html><p>no provenance</p></html>"
        with self.assertRaisesRegex(ValueError, "collection timestamp"):
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
