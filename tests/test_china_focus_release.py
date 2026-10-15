"""Fail-closed tests for the narrowly scoped China archive publication."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.stage_china_focus_output import RELEASE_FILES, stage


def fixture():
    return {
        "snapshot": {"date": "2026-10-14", "records": 3},
        "fields": ["id", "date", "source", "state", "title_en", "title_orig"],
        "records": [[1, "2026-10-14", 0, 0, "One", "原文"],
                    [2, "2026-10-14", 0, 0, "Two", "另文"],
                    [3, "2026-10-14", 1, 0, "Three", "SG"]],
        "sources": [{"code": "pla_daily", "desk": {"code": "china"}},
                    {"code": "sg_mindef_releases", "desk": {"code": "singapore"}}],
        "trail_ids": [2, 3],
    }


class ChinaFocusOutputReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.public = Path(self.tmp.name) / "public"
        self.render = Path(self.tmp.name) / "scratch"
        self.public.mkdir()
        self.render.mkdir()
        self.before = fixture()
        self.after = dict(fixture(), focus_ids=[1, 3],
                          focus_policy="automated_research_focus_not_human_curated")
        self.write(self.public, self.before)
        self.write(self.render, self.after)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def write(directory, index):
        (directory / "corpus-index.json").write_text(json.dumps(index))
        (directory / "archive.html").write_text(
            'Research focus | Full preserved record | '
            'not individually fact-checked or editor-approved. '
            'Every record is also reachable by publication week: '
            '<a href="corpus.html">full preserved records</a>')
        (directory / "browse.js").write_text(
            'const fields = "focus_ids scope preserved records";')

    def frozen(self):
        return [(self.public / name).read_bytes() for name in RELEASE_FILES]

    def test_three_file_release_preserves_canonical_full_index(self):
        baseline = self.frozen()
        report = stage(self.render, self.public, expected_china=1)
        self.assertEqual(report["china_focus"], 1)
        self.assertEqual(report["non_china"], 1)
        self.assertEqual(set(report["paths"]), set(RELEASE_FILES))
        self.assertNotEqual(baseline, self.frozen())
        self.assertEqual(self.frozen(),
                         [(self.render / name).read_bytes() for name in RELEASE_FILES])

    def test_refuses_full_source_record_mutation_without_staging(self):
        bad = json.loads((self.render / "corpus-index.json").read_text())
        bad["records"][0][4] = "Improperly rewritten historic title"
        self.write(self.render, bad)
        baseline = self.frozen()
        with self.assertRaisesRegex(ValueError, "preserved corpus/index drift"):
            stage(self.render, self.public, expected_china=1)
        self.assertEqual(self.frozen(), baseline)

    def test_refuses_missing_other_desk(self):
        self.after["focus_ids"] = [1]
        self.write(self.render, self.after)
        with self.assertRaisesRegex(ValueError, "desk visibility"):
            stage(self.render, self.public, expected_china=1)

    def test_refuses_bad_historical_capture(self):
        prior = fixture()
        prior["records"][0][0] = 2265
        self.write(self.public, prior)
        self.write(self.render, dict(prior, focus_ids=[2265, 3],
                                   focus_policy="automated_research_focus_not_human_curated"))
        with self.assertRaisesRegex(ValueError, "compromised"):
            stage(self.render, self.public, expected_china=1)

    def test_refuses_other_historical_body_hold(self):
        old = fixture()
        old["records"][0][0] = 419
        self.write(self.public, old)
        self.write(self.render, dict(
            old, focus_ids=[419, 3],
            focus_policy="automated_research_focus_not_human_curated"))
        with self.assertRaisesRegex(ValueError, "compromised"):
            stage(self.render, self.public, expected_china=1)

    def test_refuses_untruthful_archive_copy(self):
        (self.render / "archive.html").write_text("small selected archive")
        with self.assertRaisesRegex(ValueError, "disclosure"):
            stage(self.render, self.public, expected_china=1)

    def test_refuses_browse_budget_excess(self):
        (self.render / "browse.js").write_text("x" * 9501)
        with self.assertRaisesRegex(ValueError, "9500-byte"):
            stage(self.render, self.public, expected_china=1)

    def test_refuses_duplicate_focus_ids(self):
        self.after["focus_ids"] = [1, 1, 3]
        self.write(self.render, self.after)
        with self.assertRaisesRegex(ValueError, "membership"):
            stage(self.render, self.public, expected_china=1)


if __name__ == "__main__":
    unittest.main()
