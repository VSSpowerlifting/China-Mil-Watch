"""Fail-closed staging of only reviewed country output from a scratch build."""
from pathlib import Path
import tempfile
import unittest

from scripts.guard_country_research_output_scope import REVIEWED_OUTPUT_PATHS
from scripts.stage_country_research_output import stage_country_output


class CountryScratchStagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-country-stage-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.scratch, self.output = root / "scratch", root / "output"
        self.scratch.mkdir()
        self.output.mkdir()
        for name in REVIEWED_OUTPUT_PATHS:
            relative = Path(name).relative_to("output")
            (self.scratch / relative).write_text("fresh:" + name, encoding="utf-8")
            (self.output / relative).write_text("old:" + name, encoding="utf-8")
        for name in ("analysis.html", "briefs-catalog.css", "sitemap.xml"):
            (self.scratch / name).write_text("UNREVIEWED NEW", encoding="utf-8")
            (self.output / name).write_text("APPROVED OLD", encoding="utf-8")

    def test_exact_allowlist_and_all_unrelated_files_unchanged(self):
        filenames = stage_country_output(self.scratch, self.output)
        self.assertEqual(filenames, tuple(sorted(REVIEWED_OUTPUT_PATHS)))
        for name in REVIEWED_OUTPUT_PATHS:
            relative = Path(name).relative_to("output")
            self.assertEqual((self.output / relative).read_text(),
                             "fresh:" + name)
        for name in ("analysis.html", "briefs-catalog.css", "sitemap.xml"):
            self.assertEqual((self.output / name).read_text(), "APPROVED OLD")

    def test_missing_file_rejects_without_partial_copy(self):
        (self.scratch / "japan.html").unlink()
        with self.assertRaisesRegex(ValueError, "missing approved"):
            stage_country_output(self.scratch, self.output)
        self.assertEqual((self.output / "vietnam.html").read_text(),
                         "old:output/vietnam.html")

    def test_empty_and_non_utf8_source_reject_without_partial_copy(self):
        for payload in (b"", b"\xff"):
            with self.subTest(payload=payload):
                (self.scratch / "japan.html").write_bytes(payload)
                with self.assertRaises(ValueError):
                    stage_country_output(self.scratch, self.output)
                self.assertEqual((self.output / "vietnam.html").read_text(),
                                 "old:output/vietnam.html")

    def test_identical_source_and_target_rejected(self):
        with self.assertRaisesRegex(ValueError, "disjoint"):
            stage_country_output(self.output, self.output)

    def test_symlink_source_rejected_even_when_target_exists(self):
        path = self.scratch / "japan.html"
        path.unlink()
        path.symlink_to(self.output / "japan.html")
        with self.assertRaisesRegex(ValueError, "symlink"):
            stage_country_output(self.scratch, self.output)

    def test_symlink_target_rejected_even_when_source_exists(self):
        path = self.output / "japan.html"
        path.unlink()
        path.symlink_to(self.scratch / "japan.html")
        with self.assertRaisesRegex(ValueError, "symlink"):
            stage_country_output(self.scratch, self.output)

    def test_unrelated_scratch_assets_are_not_copied(self):
        (self.scratch / "new-private-asset.jpg").write_bytes(b"new")
        stage_country_output(self.scratch, self.output)
        self.assertFalse((self.output / "new-private-asset.jpg").exists())


if __name__ == "__main__":
    unittest.main()
