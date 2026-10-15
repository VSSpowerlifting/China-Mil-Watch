"""Public Philippines/Vietnam source-navigation beta cannot imply source admission."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "site/preview/templates/desk.html"
REGISTRY = ROOT / "desks/registry.json"
EXPECTED = {
    "philippines": {
        "www.afp.mil.ph",
        "nsc.gov.ph",
    },
    "vietnam": {
        "en.baochinhphu.vn",
        "bocongan.gov.vn",
        "moit.gov.vn",
    },
}


class PublisherDirectoryBetaContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.registry = {x["slug"]: x for x in
                        json.loads(REGISTRY.read_text(encoding="utf-8"))["desks"]}

    def test_offline_renderer_template_parses(self):
        env = Environment(loader=FileSystemLoader(str(TEMPLATE.parent)),
                          autoescape=True)
        env.parse(self.template)

    def test_neither_desk_is_promoted_or_given_production_records(self):
        for slug in EXPECTED:
            desk = self.registry[slug]
            self.assertEqual(desk["status"], "shadow")
            self.assertFalse(desk["has_production_records"])
            self.assertTrue(desk["public"])
            self.assertIsNone(desk.get("manifest"))

    def test_uses_only_first_party_official_source_index_urls(self):
        for slug, hosts in EXPECTED.items():
            sources = self.registry[slug]["research"]["source_families"]
            urls = [x["publisher_url"] for x in sources if x.get("publisher_url")]
            self.assertTrue(urls)
            self.assertEqual({urlsplit(x).hostname for x in urls}, hosts)
            for u in urls:
                p = urlsplit(u)
                self.assertEqual(p.scheme, "https")
                self.assertIsNone(p.port)
                self.assertIsNone(p.username)
                self.assertIsNone(p.password)
                self.assertFalse(p.fragment)

    def test_beta_is_separate_from_human_approved_individual_links(self):
        start = self.template.index("{# Early-access, external-only navigation:")
        end = self.template.index("{# Public Korea renders", start)
        beta = self.template[start:end]
        self.assertIn("desk.slug in ('philippines', 'vietnam')", beta)
        self.assertIn("desk.status == 'shadow'", beta)
        self.assertIn("desk.research.source_families", beta)
        self.assertIn("source.publisher_url", beta)
        self.assertIn('id="official-publisher-access"', beta)
        self.assertIn("not independently approved IPR", beta)
        self.assertIn("not a live IPR", beta)
        self.assertIn("All articles, documents, images and associated rights remain", beta)
        for forbidden in ("public_source_links", "state/shadow.db",
                          "original_api_response_utf8", "text_original",
                          "production_eligible=True", "weekly_AI_model_eligible=True"):
            self.assertNotIn(forbidden, beta)
        self.assertIn("No individual source references have completed the public-link review.", self.template)
        self.assertIn('href="#official-publisher-access"', self.template)

    def test_unreviewed_individual_source_lists_stay_empty(self):
        files = {
            "philippines": ("research/philippines_reviewed_links.json",
                            "philippines-reviewed-source-links/1"),
            "vietnam": ("research/vietnam_reviewed_links.json",
                        "vietnam-reviewed-source-links/1"),
        }
        for slug, (path, schema) in files.items():
            doc = json.loads((ROOT / path).read_text(encoding="utf-8"))
            self.assertEqual(doc["schema"], schema)
            self.assertEqual(doc["entries"], [])


if __name__ == "__main__":
    unittest.main()
