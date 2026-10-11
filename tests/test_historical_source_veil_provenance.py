"""Historical source photographs require a match in their issue's own source trail.

Tests grant no permission to reuse existing opened-article photos on new
catalogue surfaces; they write only to ephemeral fixture directories.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import pw_env


class SourceVeilGate(unittest.TestCase):
    DATE = "2026-05-16"
    PHOTO_URL = "https://www.81.cn/example/own-article.html"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="historical-veil-gate-")
        self.addCleanup(self.temp.cleanup)
        self.media = Path(self.temp.name)
        self.patch = patch.object(pw_env, "PW_MEDIA_DIR", self.media)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.media / pw_env.source_veil_name(self.DATE)).write_bytes(b"test-only-derivative")
        (self.media / f"{self.DATE}-source-image.json").write_text(
            json.dumps({"article_url": self.PHOTO_URL,
                        "note": "Fixture-only legacy note; not catalogue credit"}),
            encoding="utf-8")

    def resolve(self, trail):
        return pw_env.source_veil_for_edition(self.DATE, {"source_trail": trail})

    def test_unmatched_article_url_is_not_a_source_veil(self):
        self.assertIsNone(self.resolve([{"url": "https://www.81.cn/different-article.html",
                                         "title": "Different article", "source": "PLA Daily"}]))

    def test_missing_or_empty_trail_is_not_provenance(self):
        self.assertIsNone(self.resolve([]))
        self.assertIsNone(pw_env.source_veil_for_edition(self.DATE))

    def test_matching_article_url_preserves_trail_attribution(self):
        veil = self.resolve([{"url": self.PHOTO_URL,
                              "title": "Matching source report", "source": "PLA Daily"}])
        self.assertIsNotNone(veil)
        self.assertEqual(veil["kind"], "source")
        self.assertEqual(veil["source_id"], "PLA Daily")
        self.assertEqual(veil["source_page"], self.PHOTO_URL)
        self.assertIn("Matching source report", veil["alt"])

    def test_scheme_and_trailing_slash_variation_matches_existing_key(self):
        veil = self.resolve([{"url": "http://www.81.cn/example/own-article.html/",
                              "title": "Same article", "source": "PLA Daily"}])
        self.assertIsNotNone(veil)

    def test_missing_derivative_fails_closed(self):
        (self.media / pw_env.source_veil_name(self.DATE)).unlink()
        self.assertIsNone(self.resolve([{"url": self.PHOTO_URL}]))

    def test_curated_editorial_photo_precedence_is_unchanged(self):
        curated = {"kind": "editorial", "id": "existing-license-cleared-photo"}
        with patch.object(pw_env, "editorial_veil_for_edition", return_value=curated):
            self.assertIs(pw_env.veil_for_edition(self.DATE, sidecar={"source_trail": []}),
                          curated)


class PublishedHistoricalAssociation(unittest.TestCase):
    """Metadata association does not establish image-to-article rights or ownership."""

    def test_existing_source_photo_metadata_matches_edition_trails(self):
        repo = Path(__file__).resolve().parent.parent
        media = repo / "output" / "the-pla-watch" / "media"
        posts = repo / "output" / "the-pla-watch" / "posts"
        if not media.is_dir() or not posts.is_dir():
            self.skipTest("historical output tree absent")
        metas = sorted(media.glob("*-source-image.json"))
        if not metas:
            self.skipTest("no published source metadata")
        for meta_file in metas:
            date = meta_file.name.removesuffix("-source-image.json")
            sidecar_file = posts / f"{date}.json"
            with self.subTest(date=date):
                self.assertTrue(sidecar_file.is_file())
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
                url = pw_env._norm_url(meta.get("article_url"))
                self.assertTrue(url)
                self.assertTrue(any(pw_env._norm_url(e.get("url")) == url
                                    for e in sidecar.get("source_trail") or []),
                                f"{date}: image metadata lacks a trail-linked URL")


if __name__ == "__main__":
    unittest.main()
