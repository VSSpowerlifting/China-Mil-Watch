"""Synthetic exact-source Korea original page projection; zero authorizations."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.korea_published_originals import (
    PublishedKoreaHold, SCHEMA, read_release_index, render_original_page,
)

RID = "156784297"
URL = ("https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + RID)
CONTENT = "국방부 원문 테스트 — <script>alert('x')</script>.\n" * 12


def sha(data):
    return hashlib.sha256(data).hexdigest()


class KoreaPublishedOriginals(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.texts = self.root / "texts"
        self.texts.mkdir()
        self.index = self.root / "index.json"
        self.original = self.texts / (RID + ".txt")
        self.original.write_text(CONTENT, encoding="utf-8")
        self.row = {
            "source_identity": "korea-policy:" + RID,
            "official_url": URL,
            "publisher_posted_date": "2026-10-15",
            "source_git_commit": "a" * 40,
            "original_text_sha256": sha(CONTENT.encode()),
            "policy_sha256": "b" * 64,
            "source_html_sha256": "c" * 64,
            "release_decision_sha256": "d" * 64,
            "released_at_utc": "2026-10-15T23:00:00Z",
        }

    def write(self, records):
        self.index.write_text(json.dumps({"schema": SCHEMA, "records": records}),
                              encoding="utf-8")

    def read(self):
        return read_release_index(self.index, self.texts)

    def rejects(self, code):
        with self.assertRaisesRegex(PublishedKoreaHold, "^" + code + "$"):
            self.read()

    def test_empty_release_registry_generates_zero_original_pages(self):
        self.write([])
        self.assertEqual([], self.read())

    def test_exact_approved_source_projection_escapes_original_html(self):
        self.write([self.row])
        records = self.read()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["route"], "korea-originals/" + RID + ".html")
        markup = render_original_page(records[0])
        self.assertIn("https://www.korea.kr/guide/copyRight.do", markup)
        self.assertIn(URL, markup)
        self.assertIn("indopacificrecord.org/korea-originals/" + RID, markup)
        self.assertIn("&lt;script&gt;", markup)
        self.assertNotIn("<script>", markup)
        self.assertIn("pre lang=\"ko\"", markup)
        self.assertNotIn("<iframe", markup)
        self.assertNotIn("noindex", markup)
        self.assertNotIn(".hwpx", markup)

    def test_source_body_hash_drift_blocks_republication(self):
        self.write([self.row])
        self.original.write_text(CONTENT + " 수정", encoding="utf-8")
        self.rejects("korea_public_original_text_hash_drift")

    def test_nonofficial_article_url_is_rejected(self):
        self.write([{**self.row, "official_url": "https://evil.invalid/article"}])
        self.rejects("korea_public_original_official_url_mismatch")

    def test_duplicate_source_identity_is_rejected(self):
        self.write([self.row, self.row])
        self.rejects("korea_public_original_identity_invalid")

    def test_noncanonical_release_time_is_rejected(self):
        self.write([{**self.row, "released_at_utc": "2026-02-30T12:00:00Z"}])
        self.rejects("korea_public_original_date_invalid")

    def test_missing_release_decision_hash_is_rejected(self):
        self.write([{**self.row, "release_decision_sha256": ""}])
        self.rejects("korea_public_original_digest_or_custody_missing")

    def test_unexpected_copyright_or_original_media_field_is_rejected(self):
        self.write([{**self.row, "hwpx_file": "original.hwpx"}])
        self.rejects("korea_public_original_row_unrecognized")

    def test_untrusted_source_script_cannot_be_exec_in_markup(self):
        self.write([self.row])
        html = render_original_page(self.read()[0])
        self.assertNotIn("<script", html)
        self.assertEqual(html.count("&lt;script&gt;"), 12)

    def test_text_cannot_be_a_symlink(self):
        self.write([self.row])
        real = self.texts / "underlying.txt"
        self.original.rename(real)
        self.original.symlink_to(real)
        self.rejects("korea_public_original_text_missing_or_oversize")


if __name__ == "__main__":
    unittest.main()
