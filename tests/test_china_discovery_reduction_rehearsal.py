"""Culling rehearsal contracts, not public archive selection."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.rehearse_china_discovery_reduction import (
    POLICY, evaluate, create_private_report,
)

# Frozen October 14 evidence (5,230 records, 5,144 China records).
# Live output/corpus-index.json advances with daily collection and is not
# the source of truth for exact 2026-10-14 historical audit assertions.
INDEX = Path(__file__).resolve().parent / "fixtures/china-corpus-index-2026-10-14.json"


def inputs():
    return (
        json.loads(INDEX.read_text(encoding="utf-8")),
        json.loads(POLICY.read_text(encoding="utf-8")),
    )


class ChinaDiscoveryReductionRehearsalTest(unittest.TestCase):
    def test_exact_archive_math_and_no_editorial_inclusion(self):
        idx, p = inputs()
        orig = copy.deepcopy((idx, p))
        x = evaluate(idx, p)
        self.assertEqual((idx, p), orig)
        self.assertEqual(x["all_preserved"], 5230)
        self.assertEqual(x["china_preserved"], 5144)
        self.assertEqual(x["china_mechanical_visible"], 2461)
        self.assertEqual(x["china_mechanical_not_prominent"], 2683)
        self.assertEqual(x["china_mechanical_reduction_percent"], 52.16)
        self.assertEqual(x["china_editorially_approved"], 0)
        self.assertEqual(x["future_target_min"], 500)
        self.assertEqual(x["future_target_max"], 700)
        self.assertEqual(x["published_trail_ids_preserved"], 182)
        self.assertFalse(x["publication_enabled"])
        self.assertEqual({r["id"] for r in x["machine_cohort"]} &
                         {2849, 2391}, set())
        self.assertIn(2265, {r["id"] for r in x["machine_cohort"]})
        self.assertIn(2881, {r["id"] for r in x["machine_cohort"]})
        self.assertEqual(len({r["id"] for r in x["preserved"]}), 5230)

    def test_no_auto_owner_approval_or_reviewer_selection(self):
        for key, value in [
            ("publication_enabled", True), ("owner_approved", True),
            ("editorial_selection_manifest", {"ids": [2849]}),
            ("mechanical_only_rule", "published_owner_reviewed"),
        ]:
            with self.subTest(key=key):
                idx, p = inputs()
                p[key] = value
                with self.assertRaisesRegex(ValueError, "publication authority"):
                    evaluate(idx, p)

    def test_frozen_snapshot_does_not_silently_accept_daily_collection(self):
        idx, p = inputs()
        idx["snapshot"] = {"date": "2026-10-15", "records": 5231}
        idx["records"].append([5237, "2026-10-15", 0, 0, "", "新资料"])
        with self.assertRaisesRegex(ValueError, "frozen rehearsal snapshot"):
            evaluate(idx, p)

    def test_false_negative_and_published_citation_trails_are_guarded(self):
        idx, p = inputs()
        p["exception_alerts"] = [
            x for x in p["exception_alerts"] if x["id"] != 2391]
        with self.assertRaisesRegex(ValueError, "known screened-out"):
            evaluate(idx, p)
        idx, p = inputs()
        idx["trail_ids"] = [x for x in idx["trail_ids"] if x != 2265]
        with self.assertRaisesRegex(ValueError, "source alert drift"):
            evaluate(idx, p)
        idx, p = inputs()
        p["exception_alerts"][0]["title"] = "changed original"
        with self.assertRaisesRegex(ValueError, "source alert drift"):
            evaluate(idx, p)

    def test_unexpected_record_count_or_duplicate_rejected(self):
        idx, p = inputs()
        idx["snapshot"]["records"] = 5231
        p["baseline_snapshot"]["records"] = 5231
        with self.assertRaisesRegex(ValueError, "source counts"):
            evaluate(idx, p)
        idx, p = inputs()
        idx["records"].append(idx["records"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate(idx, p)
        idx, p = inputs()
        p["expected_china_analyzed_cohort"] = 2462
        with self.assertRaisesRegex(ValueError, "machine-reviewed subset"):
            evaluate(idx, p)

    def test_private_noindex_two_views_and_no_repo_mutations(self):
        idx, p = inputs()
        result = evaluate(idx, p)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "fresh-private"
            output = create_private_report(dest, result)
            self.assertEqual(output, dest)
            screened = (dest / "screened.html").read_text()
            full = (dest / "preserved.html").read_text()
            summary = json.loads((dest / "summary.json").read_text())
            self.assertEqual(screened.count("<li>"), 2461)
            self.assertEqual(full.count("<li>"), 5230)
            self.assertIn("PRIVATE, UNAPPROVED", screened)
            self.assertIn("noindex,nofollow,noarchive", full)
            self.assertNotIn("record/2849.html", screened)
            self.assertIn("record/2849.html", full)
            self.assertIn("record/2265.html", screened)
            self.assertEqual(summary["china_editorially_approved"], 0)
            self.assertEqual(
                summary["source_breakdown"]["pla_daily"]["full"], 4173)
            self.assertEqual(sorted(p.name for p in dest.iterdir()),
                             ["preserved.html", "screened.html", "summary.json"])
            with self.assertRaisesRegex(ValueError, "fresh external"):
                create_private_report(dest, result)
            with self.assertRaisesRegex(ValueError, "fresh external"):
                create_private_report(INDEX.parent / "forbidden-private", result)
            with self.assertRaisesRegex(ValueError, "fresh external"):
                create_private_report(Path(tmp) / "link" / "subdir", result)
            with self.assertRaisesRegex(ValueError, "fresh external"):
                create_private_report(Path("relative-private"), result)


if __name__ == "__main__":
    unittest.main()
