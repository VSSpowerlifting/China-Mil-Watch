"""Preserve PACOM source scope while introducing separate official USCC links."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
class USCCPublicTemplateTests(unittest.TestCase):
    def test_separate_admitted_production_lane(self):
        template=(ROOT/"site/preview/templates/desk.html").read_text(encoding="utf-8")
        generator=(ROOT/"site/preview/generate_preview.py").read_text(encoding="utf-8")
        self.assertIn('data-uscc-official-link=',template)
        self.assertIn('data-us-pacom-link=',template)
        self.assertIn('uscc_official_links=uscc_links',generator)
        self.assertIn('load_uscc_live_links(db_path)',generator)
        self.assertIn('if desk.slug == "us-indopacific" else []',generator)
        self.assertIn('not U.S. Pacific Command statements',template)
        self.assertIn("No U.S. production",template)

if __name__ == "__main__":
    unittest.main()
