"""Focus-first UX must not claim human curation or lose preserved records."""
import copy
from pathlib import Path
import unittest

from core.china_discovery import build_focus, CHINA_SOURCE_CAPS, FOCUS_TARGET

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    rows = []
    ident = 10000
    for source, amount in [
        ("pla_daily", 390),
        ("mod_china", 170),
        ("china_mil_online", 190),
        ("xinhua_mil", 100),
        ("global_times_mil", 80),
    ]:
        for n in range(amount):
            ident += 1
            rows.append({
                "id": ident, "source_slug": source, "desk_id": "china",
                "title_original": "海军与区域安全原创记录%d" % ident,
                "title_english": "", "published_date":
                    "2026-%02d-%02d" % (5+n%6, 1+n%27),
                "scraped_at": "2026-10-02 12:00:00",
                "state": "analyzed" if source != "xinhua_mil" else "not_selected",
                "in_trails": (n%17 == 0), "model_flagged": None,
            })
    for n in range(9):
        ident += 1
        rows.append({
            "id": ident, "source_slug": "sg_mindef_releases",
            "desk_id": "singapore", "title_original": "SG release %d" % n,
            "title_english": "", "published_date": "2026-10-01",
            "state": "awaiting_screening", "in_trails": False,
        })
    return rows


class ChinaFocusDiscoveryTest(unittest.TestCase):
    def test_source_balanced_focus_preserves_all_source_rows(self):
        data = fixture()
        frozen = copy.deepcopy(data)
        result = build_focus(data)
        self.assertEqual(data, frozen)
        self.assertEqual(result["china_total"], 930)
        self.assertEqual(result["china_focus"], 600)
        self.assertEqual(result["full_total"], 939)
        self.assertEqual(result["all_focus"], 609)
        self.assertEqual(result["source_counts"], CHINA_SOURCE_CAPS)
        self.assertEqual(len(result["ids"]), 609)
        self.assertEqual(len(set(result["ids"])), 609)
        self.assertEqual({x["id"] for x in result["rows"]}, set(result["ids"]))
        self.assertEqual(result["policy"],
                         "automated_research_focus_not_human_curated")
        for r in data[-9:]:
            self.assertIn(r["id"], result["ids"])
        self.assertNotIn("editor_approved", result)

    def test_known_bad_captures_never_promoted_and_originals_survive(self):
        data = fixture()
        for idx, ident in enumerate((2265, 2881, 419)):
            row = data[idx]
            row["id"] = ident
        result = build_focus(data)
        self.assertFalse({2265, 2881, 419} & set(result["ids"]))
        self.assertTrue({2265, 2881, 419}.issubset({r["id"] for r in data}))
        self.assertEqual(result["china_focus"], FOCUS_TARGET)

    def test_no_old_global_times_teaser_prominence(self):
        data = fixture()
        for r in data:
            if r["source_slug"] == "global_times_mil":
                r["scraped_at"] = "2026-08-03 12:30:00"
        result = build_focus(data)
        self.assertNotIn("global_times_mil", result["source_counts"])
        self.assertEqual(result["china_focus"], FOCUS_TARGET)
        self.assertEqual(len(result["ids"]), 609)

    def test_only_new_china_source_remains_preserved_not_auto_featured(self):
        data = fixture()
        data.append({
            "id": 77777, "source_slug": "new_source_without_editorial_policy",
            "desk_id": "china", "title_original": "新正式资料",
            "state": "analyzed", "published_date": "2026-10-01",
        })
        result = build_focus(data)
        self.assertNotIn(77777, result["ids"])
        self.assertIn(77777, {r["id"] for r in data})
        self.assertEqual(result["china_total"], 931)

    def test_small_limits_are_valid_and_title_duplicates_do_not_repeat(self):
        data = fixture()
        one = build_focus(data, china_target=1)
        self.assertEqual(one["china_focus"], 1)
        self.assertEqual(one["all_focus"], 10)
        for r in data[:15]:
            r["title_original"] = "同一重复原标题"
        result = build_focus(data)
        selected = [r for r in result["rows"] if r["desk_id"] == "china"]
        self.assertLessEqual(sum(r["title_original"] == "同一重复原标题"
                                 for r in selected), 1)

    def test_reject_duplicate_identity_and_invalid_limits(self):
        data = fixture()
        data[1]["id"] = data[0]["id"]
        with self.assertRaisesRegex(ValueError, "repeated"):
            build_focus(data)
        with self.assertRaisesRegex(ValueError, "target"):
            build_focus(fixture(), china_target=0)

    def test_browser_keeps_index_completeness_and_explicit_all_escape(self):
        template = (ROOT / "site/preview/templates/archive.html").read_text()
        js = (ROOT / "site/preview/browse.js").read_text()
        generator = (ROOT / "site/preview/generate_preview.py").read_text()
        self.assertIn('value="all">Full preserved record', template)
        self.assertIn('href="corpus.html"', template)
        self.assertIn("not individually fact-checked or editor-approved", template)
        self.assertIn("data-focus-records", template)
        self.assertIn('k === "scope" && v === "focus"', js)
        self.assertIn('get("scope") === "focus"', js)
        self.assertIn("d.records.length !== COUNT", js)
        self.assertIn("d.focus_ids.length !== FOCUS_COUNT", js)
        self.assertIn("focus = build_focus(data[\"corpus\"])", generator)
        self.assertIn('record/%d.html', generator)
        self.assertIn('data["corpus"]', generator)
        self.assertIn('"trail_ids"', generator)


if __name__ == "__main__":
    unittest.main()
