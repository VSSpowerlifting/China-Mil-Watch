"""True full-site Korea release prototype, strictly unreachable publicly."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class KoreaSitePreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as gp
        cls.gp = gp
        cls.temp = tempfile.TemporaryDirectory(prefix="ipr-korea-web-")
        cls.path = Path(cls.temp.name) / "private-publication"
        cls.result = gp.build(
            cls.path, "Korea Site Review", ROOT / "pla_watch.db",
            snapshot=gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
            review_korea=True)
        cls.page = (cls.path / "korea.html").read_text(encoding="utf-8")
        cls.directory = (cls.path / "desks.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_exact_five_genuine_original_titles_and_dates(self):
        from core.korea_reference_gate import load_candidates
        candidates = load_candidates()
        from html import escape
        self.assertEqual(self.page.count('data-review-status="hold"'), 5)
        self.assertIn("South Korea — limited source-reference pilot", self.page)
        for candidate in candidates:
            with self.subTest(identity=candidate["source_identity"]):
                self.assertIn(escape(candidate["title_original"]), self.page)
                self.assertIn(candidate["source_url"].replace("&", "&amp;"), self.page)
                self.assertIn(candidate["content_sha256"], self.page)
        self.assertIn("2026-10-04", self.page)
        self.assertIn("2026-10-06", self.page)

    def test_private_is_not_an_approved_public_korea_desk(self):
        self.assertIn('content="noindex, nofollow"', self.page)
        self.assertIn("Private design review", self.page)
        self.assertIn("not published IPR records", self.page)
        self.assertIn("human-approved references", self.page)
        self.assertIn("0</strong>", self.page)
        self.assertNotIn('href="korea.html"', self.directory)
        self.assertNotIn("korea.html", self.directory)
        self.assertFalse((self.path / "sitemap.xml").exists())
        self.assertIsNone(self.result["site_origin"])
        self.assertEqual(self.result["indexable_pages"], 0)
        self.assertTrue((self.path / "desk-references.css").exists())

    def test_korean_body_media_and_unapproved_translation_never_exported(self):
        for forbidden in (
            "우리 군은 북한의 최근 연이은 미사일 발사를 준비 단계부터",
            "강신철 장관은 먼저 환영 의장행사에 참석",
            "인디팩", "published Korean translation", "reader_state.json",
            "body_original", "text_original", "download.do?fileId="
        ):
            self.assertNotIn(forbidden, self.page)

    def test_bounded_preview_refuses_any_origin_even_synthetic(self):
        with tempfile.TemporaryDirectory(prefix="ipr-korea-reject-") as tmp:
            for opts in (
                {"site_origin": "https://example.com", "allow_test_origin": True},
                {"site_origin": "https://indo-pacific-record.example"},
                {"gallery": True},
                {"allow_synthetic_briefs": True},
            ):
                with self.subTest(opts=opts):
                    destination = Path(tmp) / ("attempt" + str(len(opts)))
                    with self.assertRaises(ValueError):
                        self.gp.build(destination, "Unapproved", ROOT / "pla_watch.db",
                                      snapshot=self.gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
                                      review_korea=True, **opts)

    def test_existing_destination_refused_without_deletion(self):
        with tempfile.TemporaryDirectory(prefix="ipr-korea-existing-") as tmp:
            dest = Path(tmp) / "protected"
            dest.mkdir()
            (dest / "keep.txt").write_text("Do not remove")
            with self.assertRaises(ValueError):
                self.gp.build(dest, "Nope", ROOT / "pla_watch.db",
                              review_korea=True)
            self.assertEqual((dest / "keep.txt").read_text(), "Do not remove")

    def test_normal_public_build_still_excludes_korea(self):
        from core.desk_registry import load_registry
        desk = load_registry().get("korea")
        self.assertFalse(desk.public)
        self.assertIsNone(desk.manifest_path)
        self.assertFalse(desk.has_production_records)
        self.assertNotIn("korea", [d.slug for d in load_registry().public_entries])


if __name__ == "__main__":
    unittest.main()
