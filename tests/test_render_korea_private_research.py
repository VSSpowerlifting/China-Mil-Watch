"""Actual three-source no-send preview must remain private, source-linked and held."""
import os
import tempfile
import unittest
from pathlib import Path

from core import korea_private_research_candidates as kr
from scripts import render_korea_private_research as private


class KoreaPrivatePreviewTests(unittest.TestCase):
    def test_real_research_packet_renders_attributed_not_raw_source_text(self):
        rows = kr.load()
        page = private.preview(rows, week_ending="2026-10-17")
        for item in rows:
            self.assertIn(item["source_id"], page)
            self.assertIn(item["source_url"], page)
            self.assertIn(item["summary"], page)
            self.assertIn(item["hwpx_capture_sha256"], page)
            self.assertIn(item["publisher_html_capture_sha256"], page)
        self.assertEqual(page.count("**Cautions:**"), 3)
        self.assertIn("not a published Brief", page)
        self.assertIn("not complete; no images", page)
        self.assertIn("156785161 disputed", page)
        self.assertNotIn("본문", page)
        self.assertNotIn("<external_source", page)

    def test_private_file_never_overwrites_or_enters_repo(self):
        rows = kr.load()
        md = private.preview(rows, week_ending="2026-10-17")
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "owner-only.md"
            self.assertEqual(private.write_private(str(out), md), str(out))
            self.assertEqual(out.read_text(encoding="utf-8"), md)
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(kr.KoreaResearchHold):
                private.write_private(str(out), md)
            link = Path(folder) / "linked.md"
            link.symlink_to(out)
            with self.assertRaises(kr.KoreaResearchHold):
                private.write_private(str(link), md)
            with self.assertRaises(kr.KoreaResearchHold):
                private.write_private("relative-preview.md", md)
            repo_path = kr.ROOT / "do-not-create-korea-preview.md"
            with self.assertRaises(kr.KoreaResearchHold):
                private.write_private(str(repo_path), md)
            self.assertFalse(repo_path.exists())

    def test_cli_must_demand_explicit_private_research_acknowledgement(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "manual-preview.md"
            with self.assertRaises(SystemExit):
                private.main(["--out", str(out)])
            self.assertFalse(out.exists())
            self.assertEqual(
                private.main(["--out", str(out), "--explicit-local-only"]), 0)
            self.assertTrue(out.exists())
            self.assertIn("KR-MND-W42-02", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
