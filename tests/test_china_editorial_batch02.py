"""Real corpus batch 02: PLA Daily commentary versus issuer originals."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.prepare_china_editorial_batch import (
    INDEX, RECORDS, validate_batch, private_html, write_private,
)

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "research/china/editorial-batch-02-2026-10-15.json"
LANE_NAMES = (
    "strong_military_forum_commentary",
    "august_first_commentary",
    "military_camp_observation",
    "foreign_ministry_primary_issuer",
    "taiwan_affairs_office_primary_issuer",
)


def actual():
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    pages = {
        e["id"]: (RECORDS / ("%d.html" % e["id"])).read_text(encoding="utf-8")
        for e in batch["entries"]
    }
    return idx, batch, pages


class PlaDailyBatch02(unittest.TestCase):
    def test_real_25_stable_pla_daily_source_records_need_actual_editorial_review(self):
        args = actual()
        frozen = copy.deepcopy(args)
        report = validate_batch(*args)
        self.assertEqual(args, frozen)
        self.assertEqual(report["batch_id"], "china-2026-10-15-02")
        self.assertEqual(report["batch_records"], 25)
        self.assertEqual(report["preserved_records"], 5230)
        self.assertEqual(report["protected_brief_trail"], 0)
        self.assertEqual(report["source_counts"], {"pla_daily": 25})
        self.assertEqual(report["review_lane_counts"],
                         {label: 5 for label in sorted(LANE_NAMES)})
        self.assertEqual({e["date"][:7] for e in report["entries"]},
                         {"2026-05", "2026-06", "2026-07",
                          "2026-08", "2026-09"})
        self.assertEqual(
            sorted([e["date"][:7] for e in report["entries"]]).count("2026-05"), 5)
        self.assertFalse(report["owner_approved"])
        self.assertFalse(report["publication_enabled"])
        self.assertTrue(all(e["editorial_decision"] is None
                            and e["human_original_review"] == "pending"
                            and e["original_url"].startswith("http")
                            for e in report["entries"]))
        self.assertEqual(len({e["id"] for e in report["entries"]}), 25)
        self.assertTrue(all(e["stored_text_status"] for e in report["entries"]))

    def test_no_false_editor_approval_or_title_source_identity_swaps(self):
        idx, batch, pages = actual()
        batch["owner_approved"] = True
        with self.assertRaisesRegex(ValueError, "publication approval"):
            validate_batch(idx, batch, pages)
        idx, batch, pages = actual()
        batch["entries"][0]["source_title"] = "rewritten fake title"
        with self.assertRaisesRegex(ValueError, "identity drift"):
            validate_batch(idx, batch, pages)
        idx, batch, pages = actual()
        batch["entries"][0]["reviewer"] = "automated classifier"
        with self.assertRaisesRegex(ValueError, "reviewer or approval"):
            validate_batch(idx, batch, pages)
        idx, batch, pages = actual()
        batch["protected_source_trail_ids"] = [2265]
        with self.assertRaisesRegex(ValueError, "exact protected Brief-trail"):
            validate_batch(idx, batch, pages)

    def test_private_noindex_intake_and_unchanged_other_batches(self):
        report = validate_batch(*actual())
        html = private_html(report)
        self.assertEqual(html.count("class='case'"), 25)
        self.assertIn("PRIVATE DRAFT. NOT A SELECTION OR PUBLICATION.", html)
        self.assertIn("noindex,nofollow,noarchive", html)
        with tempfile.TemporaryDirectory() as temp:
            fresh = Path(temp) / "batch02"
            write_private(fresh, report)
            self.assertEqual(
                json.loads((fresh / "summary.json").read_text())["batch_id"],
                "china-2026-10-15-02")
            self.assertIn("record/479.html", (fresh / "review.html").read_text())
            self.assertIn("record/3997.html", (fresh / "review.html").read_text())


if __name__ == "__main__":
    unittest.main()
