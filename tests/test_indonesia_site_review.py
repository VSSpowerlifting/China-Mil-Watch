"""The REAL site desk template preview stays privately isolated and held."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_indonesia_site_review import render_private
from scripts.preview_indonesia_reference_pilot import load


class IndonesiaSiteEquivalentReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-indonesia-site-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_private_real_template_links_noindex_and_no_corpus(self):
        page = render_private(self.root / "render")
        html = page.read_text(encoding="utf-8")
        expected = load()["candidates"]
        self.assertTrue(page.exists())
        self.assertIn('content="noindex, nofollow"', html)
        self.assertIn('data-surface="desk"', html)
        self.assertIn("Indonesia Desk", html)
        self.assertIn("NOT APPROVED FOR PUBLICATION", html)
        self.assertIn("0</strong><span>independently human-approved links", html)
        self.assertIn("0</strong><span>admitted public archive records", html)
        self.assertIn("private-disconnected-indonesia-reference-review", html)
        self.assertNotIn("data-reference-list", html)
        self.assertNotIn("text_original", html)
        self.assertNotIn("body_original", html)
        self.assertNotIn("<script src=\"desk-references.js\"", html)
        self.assertEqual(html.count('target="_blank"'), len(expected))
        for row in expected:
            self.assertIn(row["source_url"], html)
            self.assertIn(row["title_original"], html)
        receipt = json.loads((page.parent / "PRIVATE_HOLD_RECEIPT.json").read_text())
        self.assertFalse(receipt["human_review_approved"])
        self.assertFalse(receipt["rights_reuse_approved"])
        self.assertFalse(receipt["public_release_authorized"])
        self.assertFalse(receipt["production_changed"])
        self.assertFalse(receipt["registry_changed"])
        for asset in ("styles.css", "fonts.css", "surfaces.css",
                      "support.css", "desk-references.css",
                      "assets/identity/selected-ipr/ipr-navy-160.png"):
            self.assertTrue((page.parent / asset).is_file(), asset)

    def test_no_overwrite_and_no_repo_output(self):
        path = self.root / "release"
        render_private(path)
        with self.assertRaisesRegex(ValueError, "new absolute"):
            render_private(path)
        with self.assertRaisesRegex(ValueError, "new absolute"):
            render_private(Path("output/indonesia"))
        from scripts.build_indonesia_site_review import ROOT
        with self.assertRaises(ValueError):
            render_private(ROOT / "output" / "indonesia-render-fixture")

    def test_forged_rights_or_public_release_rejected_without_partial_page(self):
        current = load()
        bads = [
            ("owner_release_approved", True),
            ("day7_review_completed", True),
            ("public_renderer_consumes_this_file", True),
        ]
        for num, (field, value) in enumerate(bads):
            with self.subTest(field=field):
                malformed = copy.deepcopy(current)
                malformed[field] = value
                candidate_file = self.root / ("held-%s.json" % num)
                candidate_file.write_text(json.dumps(malformed), encoding="utf-8")
                target = self.root / ("no-page-%s" % num)
                with self.assertRaises(ValueError):
                    render_private(target, candidate_file)
                self.assertFalse(target.exists())
        bad = copy.deepcopy(current)
        bad["candidates"][0]["body_original"] = "UNLICENSED"
        candidate_file = self.root / "unsafe.json"
        candidate_file.write_text(json.dumps(bad), encoding="utf-8")
        target = self.root / "no-body-page"
        with self.assertRaises(ValueError):
            render_private(target, candidate_file)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
