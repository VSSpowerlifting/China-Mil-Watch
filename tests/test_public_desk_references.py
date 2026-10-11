"""Source-review metadata is not shadow collection or archive admission."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core.reviewed_source_links import (
    PHILIPPINES_SCHEMA, ReviewedLinkError, load_reviewed_links,
    load_public_desk_references,
)


def sample(source="ph_afp_articles"):
    host = "www.afp.mil.ph" if source == "ph_afp_articles" else "nsc.gov.ph"
    return {
        "id": "reviewed-official-sample",
        "source_slug": source,
        "source_url": "https://" + host + "/official-article",
        "title_original": "Verified original-language source-title placeholder",
        "language": "en", "published_date": "2026-10-08",
        "reviewed_by": "Named human reviewer",
        "reviewed_on": "2026-10-11", "state_commit": "a" * 40,
        "checks": {
            "source_page_opened": True, "title_checked": True,
            "publication_date_checked": True, "issuing_institution_checked": True,
            "link_publication_approved": True,
        },
    }


class PublicCountryLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "reviewed.json"

    def load(self, rows):
        self.path.write_text(json.dumps({
            "schema": PHILIPPINES_SCHEMA, "entries": rows,
        }), encoding="utf-8")
        return load_reviewed_links(self.path, today=date(2026, 10, 11),
                                   desk="philippines")

    def test_empty_register_remains_empty(self):
        self.assertEqual(self.load([]), [])
        self.assertEqual(load_public_desk_references("philippines"), [])

    def test_each_first_party_institution_can_be_separately_reviewed(self):
        a, b = sample(), sample("ph_nsc_official_statements")
        b["id"], b["published_date"] = "reviewed-nsc-sample", "2026-10-09"
        rows = self.load([a, b])
        self.assertEqual([r["source_slug"] for r in rows],
                         ["ph_nsc_official_statements", "ph_afp_articles"])
        for row in rows:
            for forbidden in ("checks", "text_original", "body"):
                self.assertNotIn(forbidden, row)

    def test_bodies_unchecked_receipts_and_wrong_hosts_fail_closed(self):
        changes = [
            {"checks": dict(sample()["checks"], link_publication_approved=False)},
            {"source_url": "https://www.afp.mil.ph.evil.example/article"},
            {"source_url": "https://nsc.gov.ph/wrong-institution"},
            {"source_url": "http://www.afp.mil.ph/article"},
            {"language": "vi"}, {"state_commit": "a" * 39},
            {"reviewed_on": "2026-10-12"},
            {"text_original": "private body data"},
        ]
        for change in changes:
            row = sample()
            row.update(change)
            with self.subTest(change=change), self.assertRaises(ReviewedLinkError):
                self.load([row])

    def test_duplicate_or_wrong_family_refused(self):
        row, duplicate = sample(), sample()
        duplicate["id"] = "different-id"
        with self.assertRaises(ReviewedLinkError):
            self.load([row, duplicate])
        bad = sample()
        bad["source_slug"] = "vn_mps_foreign_affairs_vi"
        with self.assertRaises(ReviewedLinkError):
            self.load([bad])

    def test_moit_publication_hold_cannot_be_overridden_by_json_flags(self):
        from core import reviewed_source_links as links
        with patch.object(links, "load_reviewed_links", return_value=[
            {"source_slug": "vn_moit_energy_vi"}]):
            with self.assertRaisesRegex(ReviewedLinkError, "MOIT"):
                load_public_desk_references("vietnam")

    def test_unrelated_desk_receives_no_shadow_references(self):
        self.assertEqual(load_public_desk_references("china"), [])


class PublicReferenceRenderContracts(unittest.TestCase):
    """Synthetic metadata only, never an approved source or committed page."""

    def test_approved_metadata_renders_without_js_or_private_body(self):
        import sys
        from unittest.mock import patch
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root / "site" / "preview"))
        import generate_preview as gp

        db = root / "pla_watch.db"
        if not db.is_file():
            self.skipTest("tracked production fixture absent")
        # Artificial reference is injected only into a throwaway build. Neither
        # curated public register is populated and no publisher is contacted.
        fixture = {
            "id": "synthetic-afp-display-only",
            "source_slug": "ph_afp_articles",
            "source_url": "https://www.afp.mil.ph/synthetic-review-fixture",
            "source_name": "Armed Forces of the Philippines",
            "title_original": "Fixture <untrusted> & metadata title",
            "language": "en",
            "published_date": "2026-10-08",
            "reviewed_on": "2026-10-11",
        }
        with tempfile.TemporaryDirectory(prefix="ipr-reference-render-") as tmp:
            destination = Path(tmp) / "site"
            with patch.object(gp, "load_public_desk_references",
                              side_effect=lambda desk: [fixture]
                              if desk == "philippines" else []):
                gp.build(destination, "Review Fixture", db,
                         snapshot=gp.snapshot_from_corpus(db))
            page = (destination / "philippines.html").read_text(encoding="utf-8")
            vietnam = (destination / "vietnam.html").read_text(encoding="utf-8")
            self.assertIn('data-reference-list', page)
            self.assertIn('data-reference-controls hidden', page)
            self.assertIn('data-source="ph_afp_articles"', page)
            self.assertIn('lang="en"', page)
            self.assertIn("Fixture &lt;untrusted&gt; &amp; metadata title", page)
            self.assertNotIn("Fixture <untrusted>", page)
            self.assertIn("https://www.afp.mil.ph/synthetic-review-fixture", page)
            self.assertIn("Armed Forces of the Philippines", page)
            self.assertNotIn("text_original", page)
            self.assertNotIn("body_original", page)
            self.assertIn("No individual source references have completed", vietnam)
            self.assertNotIn("synthetic-afp-display-only", vietnam)


if __name__ == "__main__":
    unittest.main()
