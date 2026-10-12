"""Public publisher navigation is distinct from approved article references.

A verified institution-level link is useful on a research-status desk even
when no captured article may be released. This module must not make private
shadow records, article URLs, or production source counts public.
"""
import unittest
from urllib.parse import urlsplit

from core.desk_registry import load_registry
from tests.test_desk_rollout_contract import DeskCase


class PhilippinesPublisherEntrypointTests(DeskCase):
    def test_two_exact_institutional_entrypoints_are_first_party(self):
        desk = load_registry().get("philippines")
        self.assertEqual(desk.status, "shadow")
        self.assertFalse(desk.has_production_records)
        sources = desk.research["source_families"]
        self.assertEqual(
            [(s["name"], s.get("publisher_url")) for s in sources],
            [
                ("Armed Forces of the Philippines — first-party publications",
                 "https://www.afp.mil.ph/"),
                ("Philippine National Security Council — official statements",
                 "https://nsc.gov.ph/category/official-statements/"),
            ])
        for source in sources:
            url = urlsplit(source["publisher_url"])
            self.assertEqual(url.scheme, "https")
            self.assertIn(url.hostname, {"www.afp.mil.ph", "nsc.gov.ph"})
            self.assertFalse(url.username or url.password or url.query or url.fragment)
            self.assertNotIn("/articles/", url.path)

    def test_rendered_page_links_to_publishers_but_has_no_article_references(self):
        html = self.page("philippines.html")
        for url in ("https://www.afp.mil.ph/",
                    "https://nsc.gov.ph/category/official-statements/"):
            self.assertIn('href="' + url + '" rel="noopener noreferrer"', html)
        self.assertEqual(html.count("Open official publisher index"), 2)
        self.assertIn("external institution pages, not IPR-reviewed individual publications", html)
        self.assertIn("No individual source references have completed", html)
        self.assertNotIn("data-reference-list", html)
        self.assertNotIn("api.afp.mil.ph/articles/", html)
        self.assertNotIn('href="archive.html?desk=philippines"', html)

    def test_other_desk_does_not_inherit_philippine_publisher_links(self):
        html = self.page("vietnam.html")
        self.assertNotIn("https://www.afp.mil.ph/", html)
        self.assertNotIn("https://nsc.gov.ph/category/official-statements/", html)
        # The existence of Vietnam's own institutional links is tested by
        # the Vietnam source-navigation contract, not this Philippines test.


if __name__ == "__main__":
    unittest.main()
