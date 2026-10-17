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
        from markupsafe import escape
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
        self.assertNotIn('data-korea-production-lanes', self.page)
        self.assertIn("0</strong>", self.page)
        # The real public official-source bibliography is now listed, while
        # this separately generated source-review preview stays noindex.
        self.assertIn('href="korea.html"', self.directory)
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

    def test_production_status_flip_still_refused(self):
        from dataclasses import replace
        from core.desk_registry import DeskRegistry, load_registry
        original = load_registry()
        changed = DeskRegistry(entries=[
            replace(e, status="live", has_production_records=True)
            if e.slug == "korea" else e for e in original.entries
        ])
        with tempfile.TemporaryDirectory(prefix="ipr-korea-flip-") as tmp:
            output = Path(tmp) / "must-not-build"
            with patch.object(self.gp, "load_registry", return_value=changed):
                with self.assertRaisesRegex(ValueError, "production admission"):
                    self.gp.build(output, "No live Korea", ROOT / "pla_watch.db")
            self.assertFalse(output.exists())

    def test_normal_public_build_contains_fixed_korea_only(self):
        from core.desk_registry import load_registry
        from core.korea_public_bibliography import load_public_korea_links
        desk = load_registry().get("korea")
        self.assertTrue(desk.public)
        self.assertEqual(desk.status, "shadow")
        self.assertIsNone(desk.manifest_path)
        self.assertFalse(desk.has_production_records)
        self.assertIn("korea", [d.slug for d in load_registry().public_entries])
        self.assertEqual(len(load_public_korea_links()), 5)


if __name__ == "__main__":
    unittest.main()



class KoreaPrivateStructuralProjectionTests(unittest.TestCase):
    """Synthetic signoffs exercise website layout only, never human proof."""

    def setUp(self):
        from core.korea_reference_gate import APPROVAL_SCHEMA, STATE_SHA, load_candidates
        from tests.test_korea_reference_gate import synthetic_approval
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-korea-structural-web-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = load_candidates()
        self.sample = synthetic_approval(self.rows[1])
        self.packet = self.root / "synthetic-review.json"
        self.packet.write_text(json.dumps({
            "schema": APPROVAL_SCHEMA,
            "state_commit": STATE_SHA,
            "entries": [self.sample],
        }), encoding="utf-8")
        import sys
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as gp
        self.gp = gp

    def preview(self):
        out = self.root / "site-private-approved-projection"
        result = self.gp.build(
            out, "IPR Korea Private Synthetic QA", ROOT / "pla_watch.db",
            snapshot=self.gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
            review_korea=True, korea_review_packet=self.packet)
        return result, out

    def test_one_structural_reference_and_four_held_source_rows(self):
        result, output = self.preview()
        page = (output / "korea.html").read_text(encoding="utf-8")
        self.assertEqual(result["korea_private_structural_preview_rows"], 1)
        self.assertEqual(page.count('data-review-status="private-structural-only"'), 1)
        self.assertEqual(page.count('data-review-status="hold"'), 4)
        self.assertIn(self.sample["english_description"], page)
        self.assertIn("signoffs unauthenticated", page)
        self.assertIn("human-approved references authenticated by this tool", page)
        self.assertIn("not an official government translation", page)
        self.assertNotIn(self.sample["human_korean_review"]["reviewer"], page)
        self.assertNotIn(self.sample["source_rights_review"]["reviewer"], page)
        self.assertNotIn(self.sample["owner_publication_approval"]["reviewer"], page)
        self.assertNotIn("text_original", page)
        self.assertNotIn("body_original", page)
        self.assertIn('href="korea.html"',
                      (output / "desks.html").read_text(encoding="utf-8"))
        self.assertFalse((output / "sitemap.xml").exists())
        self.assertIn('content="noindex, nofollow"', page)
        self.assertEqual(result["indexable_pages"], 0)

    def test_changed_hash_or_unreviewed_rights_refused_before_build(self):
        import copy
        for change in ("text_hash", "rights_false", "source_identity"):
            with self.subTest(change=change):
                item = copy.deepcopy(self.sample)
                if change == "text_hash":
                    item["content_sha256"] = "b"*64
                elif change == "rights_false":
                    item["source_rights_review"]["nontext_media_excluded"] = False
                else:
                    item["source_identity"] = "korea-policy:156780000"
                self.packet.write_text(json.dumps({
                    "schema": "ipr-korea-source-admission/1",
                    "state_commit": "dcb43b9c4edb471d6def5876701ec4a2e39d5264",
                    "entries": [item],
                }), encoding="utf-8")
                dest = self.root / ("refused-" + change)
                with self.assertRaises(ValueError):
                    self.gp.build(dest, "Must not publish",
                                  ROOT / "pla_watch.db", review_korea=True,
                                  korea_review_packet=self.packet)
                self.assertFalse(dest.exists(), "invalid reviewer packet left partial preview files")

    def test_packet_not_accepted_for_normal_site_or_from_repository(self):
        dest = self.root / "normal-release"
        with self.assertRaisesRegex(ValueError, "only in private review mode"):
            self.gp.build(dest, "No Korea",
                          ROOT / "pla_watch.db", korea_review_packet=self.packet)
        self.assertFalse(dest.exists())
        # Even synthetic packets checked into the public repository are refused.
        with self.assertRaisesRegex(ValueError, "outside repository"):
            self.gp.build(dest, "Bad packet path",
                          ROOT / "pla_watch.db", review_korea=True,
                          korea_review_packet=ROOT / "research/korea_reference_candidates.json")
        self.assertFalse(dest.exists())

    def test_structural_packet_never_makes_origin_or_sitemap_eligible(self):
        with self.assertRaisesRegex(ValueError, "no origin"):
            self.gp.build(self.root / "origin-refused", "No",
                          ROOT / "pla_watch.db", review_korea=True,
                          korea_review_packet=self.packet,
                          site_origin="https://indopacificrecord.org")
        self.assertFalse((self.root / "origin-refused").exists())
