"""Nine publisher links are rendered as a separate, non-corpus U.S. directory."""
import json
import unittest
from pathlib import Path

from core.us_pacom_official_links import load_us_pacom_official_links
from scripts import review_us_pacom_official_link_docket as docket

ROOT = Path(__file__).resolve().parents[1]

class USPublisherLinkDirectoryTests(unittest.TestCase):
    def test_nine_pinned_readonly_official_references(self):
        rows = load_us_pacom_official_links()
        self.assertEqual(len(rows), 9)
        self.assertEqual({r["source_identity"] for r in rows},
                         {"us-pacom:"+x[0] for x in docket.PINS})
        self.assertEqual({r["section"] for r in rows},
                         {"news_article", "press_release"})
        self.assertTrue(all(r["source_url"].startswith("https://www.pacom.mil/")
                            and "title_original" not in r
                            and "text_original" not in r
                            and "analysis" not in r
                            and r["neutral_label"].startswith("PACOM ")
                            for r in rows))

    def test_public_template_is_separate_from_source_corpus(self):
        template = (ROOT/"site/preview/templates/desk.html").read_text(encoding="utf-8")
        gen = (ROOT/"site/preview/generate_preview.py").read_text(encoding="utf-8")
        self.assertIn("data-us-pacom-link=", template)
        self.assertIn("desk.slug == 'us-indopacific'", template)
        self.assertIn("us_pacom_official_links=us_pacom_links", gen)
        self.assertIn("if desk.slug == \"us-indopacific\" else []", gen)
        self.assertIn("not IPR-collected", template)
        self.assertIn("automated access restrictions", template)
        self.assertIn("No U.S. production", template)

    def test_site_registry_stays_access_blocked_with_zero_records(self):
        registry = json.loads((ROOT/"desks/registry.json").read_text(encoding="utf-8"))
        desk = next(d for d in registry["desks"] if d["slug"]=="us-indopacific")
        self.assertEqual(desk["status"], "access_blocked")
        self.assertIs(desk["manifest"], None)
        self.assertFalse(desk["has_production_records"])
        self.assertTrue(desk["public"])

if __name__ == "__main__":
    unittest.main()
