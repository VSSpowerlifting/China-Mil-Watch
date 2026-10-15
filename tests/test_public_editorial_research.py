"""No-network contracts for permanent linked official references in IPR research."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from core.public_editorial_research import (
    PublicationHold, load_catalog, published_for_desk,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = date(2026, 10, 15)


def fixture():
    return {
        "schema": "ipr-permanent-editorial-desk-research/1",
        "entries": [{
            "desk": "indonesia",
            "ipr_page": "briefs/approved-ipr-research.html",
            "ipr_title": "Illustrative IPR-authored research title",
            "published_on": "2026-10-15",
            "approved_by": "Editorial Test Fixture",
            "approved_on": "2026-10-14",
            "approval_commit": "a" * 40,
            "source_links": [{
                "source_slug": "id_kemhan_news",
                "publisher_url": "https://www.kemhan.go.id/2026/10/14/example.html",
                "title_original": "Contoh judul resmi dari sumber Indonesia",
                "publisher_date": "2026-10-14",
                "issuer": "Kementerian Pertahanan",
                "source_identity": "kemhan:20261014-example",
                "source_state_commit": None,
                "capture_sha256": None,
            }],
        }],
    }


class PermanentResearchSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "catalog.json"

    def verify(self, doc):
        self.path.write_text(json.dumps(doc), encoding="utf-8")
        return load_catalog(self.path, today=NOW)

    def assert_rejected(self, doc):
        with self.assertRaises(PublicationHold):
            self.verify(doc)

    def test_real_catalog_only_reuses_prior_owner_approved_brief(self):
        rows = load_catalog(today=NOW)
        self.assertEqual(len(rows), 1)
        item = rows[0]
        self.assertEqual(item["desk"], "vietnam")
        self.assertEqual(item["ipr_page"], "briefs/what-is-being-built-in-laos.html")
        self.assertEqual(item["approved_by"], "Benjamin Yang")
        self.assertEqual(item["approved_on"], "2026-10-13")
        self.assertEqual(item["approval_commit"], "504e8a95cb53e6fe500695aaa051f9dca82d8fe1")
        self.assertEqual(len(item["source_links"]), 3)
        self.assertEqual([x["source_slug"] for x in item["source_links"]],
                         ["vn_government_news_editorial", "vn_government_news_editorial",
                          "vn_mps_foreign_affairs_vi"])
        self.assertTrue(all(x["capture_sha256"] is None for x in item["source_links"]))
        self.assertEqual(published_for_desk("indonesia"), [])

    def test_good_metadata_links_only_and_no_false_private_copy_claim(self):
        entries = self.verify(fixture())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["desk"], "indonesia")
        source = entries[0]["source_links"][0]
        self.assertIsNone(source["capture_sha256"])
        self.assertNotIn("source_body", source)
        self.assertNotIn("media_url", source)
        self.assertNotIn("privately_preserved", source)

    def test_optional_capture_digest_remains_only_identifier(self):
        doc = fixture()
        s = doc["entries"][0]["source_links"][0]
        s["capture_sha256"] = "f"*64
        self.assert_rejected(doc)
        s["source_state_commit"] = "e"*40
        approved = self.verify(doc)
        self.assertEqual(approved[0]["source_links"][0]["capture_sha256"], "f"*64)

    def test_rejects_unreviewed_source_bodies_images_and_links_to_other_hosts(self):
        for bad in [
            {"body_original": "protected original text"},
            {"photo_url": "https://www.kemhan.go.id/photo.jpg"},
            {"html_snapshot": "<main>government content</main>"},
            {"publisher_url": "https://www.kemhan.go.id.attacker.example/page"},
            {"publisher_url": "http://www.kemhan.go.id/page"},
            {"publisher_url": "https://username@www.kemhan.go.id/page"},
            {"publisher_url": "https://www.kemhan.go.id:444/page"},
            {"publisher_url": "https://www.kemhan.go.id/path#frag"},
            {"publisher_url": "https://www.afp.mil.ph/source"},
            {"source_slug": "ph_afp_articles"},
            {"capture_sha256": "f"*64},
        ]:
            with self.subTest(bad=bad):
                doc = fixture()
                doc["entries"][0]["source_links"][0].update(bad)
                self.assert_rejected(doc)

    def test_duplicate_json_keys_refused(self):
        self.path.write_text('{"schema":"ipr-permanent-editorial-desk-research/1","schema":"x","entries":[]}')
        with self.assertRaises(PublicationHold):
            load_catalog(self.path, today=NOW)

    def test_missing_named_approval_or_future_record_refused(self):
        cases = [
            ("approved_by", ""),
            ("approved_on", "2026-10-16"),
            ("published_on", "2026-10-16"),
            ("approval_commit", "short"),
            ("ipr_page", "https://example.org/page.html"),
            ("ipr_page", "../output/hidden.html"),
            ("desk", "china"),
            ("source_links", []),
        ]
        for key,value in cases:
            with self.subTest(key=key,value=value):
                doc = fixture()
                doc["entries"][0][key] = value
                self.assert_rejected(doc)

    def test_original_date_follows_publication_only_backward(self):
        doc = fixture()
        doc["entries"][0]["source_links"][0]["publisher_date"] = "2026-10-16"
        self.assert_rejected(doc)

    def test_no_photographic_storage_and_no_private_custody_verdict_api(self):
        src = (ROOT/"core/public_editorial_research.py").read_text()
        for forbidden in ("requests.get(", "urllib.request.urlopen(", "git push", 
                          "photos/", "photo_bytes", "content_original",
                          "private_copy_verified", "send_mail(", "smtp."):
            self.assertNotIn(forbidden, src)
        self.assertIn("bibliographic", src)
        self.assertIn("source_state_commit", src)

if __name__ == "__main__":
    unittest.main()
