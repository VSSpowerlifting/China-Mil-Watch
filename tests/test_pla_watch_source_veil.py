"""A source photograph can represent only the edition that cites its article."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import pw_env


class SourceVeilAssociationTests(unittest.TestCase):
    def test_unrelated_article_image_falls_back_to_text(self):
        with tempfile.TemporaryDirectory() as root:
            media = Path(root)
            (media / "2026-08-15-source-image.json").write_text(json.dumps({
                "article_url": "http://www.81.cn/yw_208727/16479044.html",
                "note": "Cited article photograph",
            }), encoding="utf-8")
            (media / "2026-08-15-veil.jpg").write_bytes(b"image placeholder")
            with patch.object(pw_env, "PW_MEDIA_DIR", media):
                unrelated = {"source_trail": [{
                    "url": "http://www.81.cn/yw_208727/16479246.html",
                    "source": "PLA Daily",
                    "title": "Different article",
                }]}
                self.assertIsNone(pw_env.source_veil_for_edition(
                    "2026-08-15", sidecar=unrelated))

                cited = {"source_trail": [{
                    "url": "https://www.81.cn/yw_208727/16479044.html",
                    "source": "PLA Daily",
                    "title": "Cited article",
                }]}
                veil = pw_env.source_veil_for_edition(
                    "2026-08-15", sidecar=cited)
                self.assertEqual(veil["source_id"], "PLA Daily")
                self.assertEqual(veil["subject"], "Cited article")


if __name__ == "__main__":
    unittest.main()
