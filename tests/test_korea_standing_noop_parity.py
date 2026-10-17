"""Synthetic real-contract Korea no-op parity tests; no publisher network."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from scripts import verify_korea_standing_noop_parity as sut

IDS = ("156785286", "156785444")
MAIN = "origin/main"
PAGES = "origin/gh-pages"


def fixtures():
    registry = {"schema": sut.REGISTER, "records": [
        {"source_identity": "korea-policy:" + i,
         "original_text_sha256": "a" * 64} for i in IDS
    ]}
    blobs = {
        (MAIN, "research/korea_published_original_texts.json"):
            json.dumps(registry).encode(),
        (MAIN, "output/korea.html"): b"<html>current desk</html>",
        (PAGES, "korea.html"): b"<html>current desk</html>",
    }
    trees = {MAIN: set(), PAGES: set()}
    for i in IDS:
        route = "korea-originals/" + i + ".html"
        blobs[(MAIN, "output/" + route)] = ("official-" + i).encode()
        blobs[(PAGES, route)] = ("official-" + i).encode()
        trees[MAIN].add("output/" + route)
        trees[PAGES].add(route)
    return blobs, trees


class KoreaStandingNoopParityTests(unittest.TestCase):
    def setUp(self):
        self.blobs, self.trees = fixtures()

    def fake_git(self, *args):
        if args[0] == "show":
            ref, path = args[1].split(":", 1)
            if (ref, path) not in self.blobs:
                raise sut.NoopHold("korea_noop_git_object_missing")
            return self.blobs[ref, path]
        if args[:3] == ("ls-tree", "-r", "--name-only"):
            ref = args[3]
            return ("\n".join(sorted(self.trees[ref])) + "\n").encode()
        raise AssertionError("unexpected Git call")

    def check(self):
        with patch.object(sut, "git", side_effect=self.fake_git):
            return sut.verify_parity()

    def test_exact_two_originals_plus_current_desk_are_converged(self):
        result = self.check()
        self.assertEqual(result["routes_byte_identical"], 3)
        self.assertEqual(result["published_originals_verified"], 2)
        self.assertFalse(result["published"])
        self.assertEqual(result["new_original_texts"], 0)

    def test_changed_current_desk_never_silently_treated_as_noop(self):
        self.blobs[PAGES, "korea.html"] += b"stale"
        with self.assertRaisesRegex(sut.NoopHold, "current_main_pages_byte_drift"):
            self.check()

    def test_changed_original_blocks_noop_even_with_matching_desk(self):
        self.blobs[PAGES, "korea-originals/156785286.html"] = b"out-of-date"
        with self.assertRaisesRegex(sut.NoopHold, "current_main_pages_byte_drift"):
            self.check()

    def test_missing_original_on_pages_is_not_a_clean_noop(self):
        self.trees[PAGES].remove("korea-originals/156785444.html")
        with self.assertRaisesRegex(sut.NoopHold, "original_roster_not_converged"):
            self.check()

    def test_orphan_original_on_pages_is_not_a_clean_noop(self):
        self.trees[PAGES].add("korea-originals/999999999.html")
        with self.assertRaisesRegex(sut.NoopHold, "original_roster_not_converged"):
            self.check()

    def test_new_main_only_original_is_not_clean_noop(self):
        self.trees[MAIN].add("output/korea-originals/777777777.html")
        with self.assertRaisesRegex(sut.NoopHold, "original_roster_not_converged"):
            self.check()

    def test_invalid_registry_and_duplicates_are_rejected(self):
        key = MAIN, "research/korea_published_original_texts.json"
        raw = json.loads(self.blobs[key])
        raw["records"].append(raw["records"][0].copy())
        self.blobs[key] = json.dumps(raw).encode()
        with self.assertRaisesRegex(sut.NoopHold, "registry_invalid"):
            self.check()
        raw["records"] = []
        self.blobs[key] = json.dumps(raw).encode()
        with self.assertRaisesRegex(sut.NoopHold, "registry_invalid"):
            self.check()

    def test_unexpected_files_in_korean_original_pages_tree_are_rejected(self):
        self.trees[PAGES].add("korea-originals/source-hwpx.zip")
        with self.assertRaisesRegex(sut.NoopHold, "orphan_original_page"):
            self.check()

    def test_missing_current_main_registry_is_not_a_noop(self):
        del self.blobs[MAIN, "research/korea_published_original_texts.json"]
        with self.assertRaisesRegex(sut.NoopHold, "git_object_missing"):
            self.check()

    def test_workflow_noop_skips_writer_only_after_verified_parity(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        yaml = (root / ".github/workflows/korea_standing_original_text_production.yml"
                ).read_text(encoding="utf-8")
        self.assertIn("id: verified_noop", yaml)
        self.assertIn("python -m scripts.verify_korea_standing_noop_parity", yaml)
        self.assertIn('if: steps.verified_noop.outputs.verified != \'true\'', yaml)
        self.assertIn("git status --porcelain -- research/korea_published_original_texts.json", yaml)
        self.assertIn("git ls-remote", yaml)
        self.assertIn('test "$source_now" = "$(cat "$RUNNER_TEMP/korea-future-text-source-head")"', yaml)
        self.assertGreaterEqual(
            yaml.count("if: steps.verified_noop.outputs.verified != 'true'"), 5)
        self.assertIn("Refuse stale source capture or concurrent main write", yaml)


if __name__ == "__main__":
    unittest.main()
