"""Indonesia's public link register remains empty until actual named signoff.

Synthetic fixtures in this module are NOT release decisions or public references.
"""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from core.reviewed_source_links import (
    INDONESIA_SCHEMA, ReviewedLinkError, load_public_desk_references,
    load_reviewed_links,
)


def fixture():
    return {
        "id": "id-kemhan-berita-fixture",
        "source_slug": "id_kemhan_news",
        "source_url": "https://www.kemhan.go.id/2026/10/09/contoh-berita-resmi.html",
        "title_original": "Contoh judul berita resmi kementerian pertahanan",
        "language": "id",
        "published_date": "2026-10-09",
        "reviewed_by": "Synthetic named reviewer",
        "reviewed_on": "2026-10-13",
        "state_commit": "a" * 40,
        "checks": {
            "source_page_opened": True,
            "title_checked": True,
            "publication_date_checked": True,
            "issuing_institution_checked": True,
            "link_publication_approved": True,
        },
    }


class IndonesiaPublicLinkGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-id-references-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "links.json"

    def load(self, rows, *, today=date(2026, 10, 13)):
        self.path.write_text(json.dumps({
            "schema": INDONESIA_SCHEMA, "entries": rows,
        }, ensure_ascii=False), encoding="utf-8")
        return load_reviewed_links(self.path, desk="indonesia", today=today)

    def test_real_public_register_stays_empty_with_private_pilot_unadmitted(self):
        self.assertEqual(load_public_desk_references("indonesia"), [])
        self.assertEqual(self.load([]), [])
        from core.desk_registry import load_registry
        d = load_registry().get("indonesia")
        self.assertEqual(d.status, "shadow")
        self.assertFalse(d.has_production_records)
        self.assertIsNone(d.manifest_path)

    def test_synthetic_approved_metadata_only(self):
        row = self.load([fixture()])[0]
        self.assertEqual(row["source_slug"], "id_kemhan_news")
        self.assertEqual(row["language"], "id")
        self.assertEqual(row["source_name"], "Kementerian Pertahanan Republik Indonesia")
        self.assertEqual(row["published_date"], "2026-10-09")
        for forbidden in ("checks", "body", "text_original", "capture_sha256"):
            self.assertNotIn(forbidden, row)

    def test_false_approval_and_missing_human_name_fail_closed(self):
        for field, value in [
            ("reviewed_by", ""), ("reviewed_on", "2026-10-14"),
            ("state_commit", "0" * 39), ("language", "en"),
            ("source_slug", "id_kemhan_siaran_pers"),
            ("text_original", "private article body"),
            ("publisher_body_republication_approved", True),
        ]:
            case = fixture()
            case[field] = value
            with self.subTest(field=field), self.assertRaises(ReviewedLinkError):
                self.load([case])
        case = fixture()
        case["checks"]["link_publication_approved"] = False
        with self.assertRaises(ReviewedLinkError):
            self.load([case])

    def test_official_url_and_exact_dated_path_required(self):
        for url in (
            "http://www.kemhan.go.id/2026/10/09/contoh-berita-resmi.html",
            "https://evil.example/2026/10/09/contoh-berita-resmi.html",
            "https://www.kemhan.go.id.evil.example/2026/10/09/contoh.html",
            "https://www.kemhan.go.id/category/berita",
            "https://www.kemhan.go.id/2026/10/09/contoh-berita-resmi.html?share=1",
            "https://www.kemhan.go.id/2026/10/09/contoh-berita-resmi.html#share",
            "https://www.kemhan.go.id/2026/10/08/contoh-berita-resmi.html",
            "https://www.kemhan.go.id/2026/02/30/contoh-berita-resmi.html",
            "https://www.kemhan.go.id/2026/10/09/../10/contoh-berita-resmi.html",
            "https://www.kemhan.go.id:444/2026/10/09/contoh-berita-resmi.html",
            "https://www.kemhan.go.id/siaran-pers/2026/10/09/contoh.html",
        ):
            case = fixture()
            case["source_url"] = url
            with self.subTest(url=url), self.assertRaises(ReviewedLinkError):
                self.load([case])

    def test_duplicate_or_unexpected_metadata_refused(self):
        a = fixture()
        b = copy.deepcopy(a)
        b["id"] = "different-reference-id"
        with self.assertRaises(ReviewedLinkError):
            self.load([a, b])
        self.path.write_text(
            '{"schema":"indonesia-reviewed-source-links/1",'
            '"schema":"indonesia-reviewed-source-links/1","entries":[]}',
            encoding="utf-8",
        )
        with self.assertRaises(ReviewedLinkError):
            load_reviewed_links(self.path, desk="indonesia")


    def test_synthetic_reviewed_link_renders_on_existing_public_indonesia_route(self):
        """Rehearse the real site template, not a guessed future Indonesia page."""
        import sys
        from unittest.mock import patch

        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "site" / "preview"))
        import generate_preview as gp

        db = root / "pla_watch.db"
        if not db.is_file():
            self.skipTest("tracked production fixture absent")
        approved_fixture = self.load([fixture()])[0]
        destination = Path(self.tmp.name) / "synthetic-site"
        with patch.object(gp, "load_public_desk_references",
                          side_effect=lambda desk: [approved_fixture] if desk == "indonesia" else []):
            gp.build(destination, "Synthetic Indonesia Reference Test", db,
                     snapshot=gp.snapshot_from_corpus(db))
        html = (destination / "indonesia.html").read_text(encoding="utf-8")
        self.assertIn('data-reference-list', html)
        self.assertIn('lang="id"', html)
        self.assertIn(approved_fixture["source_url"], html)
        self.assertIn(approved_fixture["title_original"], html)
        self.assertIn("None collected", html)
        self.assertNotIn("text_original", html)
        self.assertNotIn("body_original", html)
        self.assertNotIn(approved_fixture["source_url"],
                         (destination / "philippines.html").read_text(encoding="utf-8"))
        self.assertEqual(load_public_desk_references("indonesia"), [])


if __name__ == "__main__":
    unittest.main()
