"""
The US desk must describe what it actually collects.

The DVIDS route is open, compliant and retrievable. It is also *unit-tagged
public affairs*, and on the measured feed roughly nine items in ten announce no
Indo-Pacific content at all. That gap between what the route is called and what
it carries is the desk's dominant limitation, and prose is the only place it can
be stated -- so these tests hold the prose to it.

They also hold the line that the pacom.mil finding is not reinterpreted. A
different host with a readable policy is an alternative route; it is not
permission that pacom.mil withheld.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.desk_registry import load_registry                    # noqa: E402
from scraper.sources import us_dvids as us                      # noqa: E402

SHADOW_DIR = REPO_ROOT / "shadow" / "us_indopacom"
MANIFEST = json.loads((SHADOW_DIR / "manifest.json").read_text(encoding="utf-8"))
README = (SHADOW_DIR / "README.md").read_text(encoding="utf-8")
#: Assertions about prose must not depend on where a line happens to wrap.
README_FLAT = re.sub(r"\s+", " ", README)
SOURCE = MANIFEST["sources"][0]
ADAPTER_SRC = (REPO_ROOT / "scraper" / "sources" / "us_dvids.py").read_text(
    encoding="utf-8")
SCOPE = " ".join(SOURCE["declared_scope"])

#: Phrases that would claim the desk carries command releases.
OVERCLAIMS = (
    "command release wire",
    "command-release wire" + " for the command",
    "official usindopacom releases",
    "us indo-pacific command releases",
    "press releases and readouts",
)


class TestTheManifestClaimsOnlyWhatTheFeedCarries(unittest.TestCase):

    def test_the_declared_scope_says_the_feed_is_unit_tagged(self):
        self.assertIn("tagged", SCOPE.lower())

    def test_the_declared_scope_denies_being_a_command_release_wire(self):
        self.assertRegex(SCOPE.lower(), r"not a usindopacom command-release")

    def test_the_declared_scope_states_measured_counts(self):
        self.assertRegex(SCOPE, r"\b428\b")          # items in the feed
        self.assertRegex(SCOPE, r"\b171\b")          # news items
        self.assertRegex(SCOPE, r"2026-09-17")       # when it was measured

    def test_the_declared_scope_states_that_only_news_has_prose(self):
        self.assertIn("/news/", SCOPE)
        for medium in ("image", "video", "audio"):
            self.assertIn(medium, SCOPE.lower(), medium)

    def test_the_declared_scope_names_the_identity_it_uses(self):
        self.assertIn("guid", SCOPE.lower())

    def test_the_declared_scope_refuses_the_teaser_as_a_body(self):
        self.assertIn("teaser", SCOPE.lower())

    def test_no_overclaim_appears_anywhere_in_the_manifest(self):
        blob = json.dumps(MANIFEST).lower()
        for phrase in OVERCLAIMS:
            self.assertNotIn(phrase, blob, phrase)

    def test_the_publisher_is_named_as_dvids_not_as_the_command(self):
        inst = MANIFEST["institutions"][0]
        self.assertIn("dvids", inst["name_original"].lower())
        self.assertIn("not", inst["notes"].lower())
        self.assertIn("pacific command", inst["notes"].lower())

    def test_the_source_is_tier_b_not_tier_a(self):
        self.assertEqual(SOURCE["authority_tier"], "B")
        self.assertIn("tier b", SCOPE.lower())

    def test_nothing_is_enabled(self):
        self.assertFalse(SOURCE["enabled"])
        self.assertFalse(MANIFEST["desk"]["active"])
        self.assertEqual(MANIFEST["desk"]["public_status"], "shadow")

    def test_the_manifest_declares_itself_a_shadow_manifest(self):
        self.assertTrue(MANIFEST["_shadow"])

    def test_the_manifest_is_not_discoverable_by_production(self):
        self.assertFalse((REPO_ROOT / "desks" / "us_indopacific").exists())
        discovered = {p.parent.name
                      for p in (REPO_ROOT / "desks").glob("*/manifest.json")}
        self.assertEqual(discovered, {"china"})


class TestTheReadmeStatesTheDominantLimitation(unittest.TestCase):

    def test_the_readme_reports_the_indo_pacific_keyword_fraction(self):
        self.assertRegex(README_FLAT, r"15\s*/\s*171")
        self.assertIn("9%", README)

    def test_the_readme_calls_the_scope_gap_a_limitation(self):
        limits = README.split("## Known limitations", 1)[1].lower()
        self.assertIn("scope", limits)
        self.assertIn("editorial", limits)

    def test_the_readme_says_the_window_is_a_count_not_a_duration(self):
        self.assertIn("unrecoverable", README)
        self.assertIn("428", README)

    def test_the_readme_says_no_backfill_may_be_improvised(self):
        self.assertRegex(README.lower(), r"no backfill|backfill mechanism")

    def test_the_readme_says_the_desk_is_not_launched(self):
        self.assertIn("Not launched", README)
        self.assertIn("Day zero has not been reached", README)


class TestThePacomFindingIsNotReinterpreted(unittest.TestCase):

    def test_the_readme_restates_the_403_on_robots_itself(self):
        self.assertIn("403", README)
        self.assertIn("robots.txt", README)
        self.assertRegex(README.lower(), r"pacom\.mil")

    def test_the_readme_calls_dvids_a_different_host_not_a_workaround(self):
        self.assertIn("not a workaround", README_FLAT.lower())

    def test_the_registry_entry_stays_access_blocked(self):
        desk = load_registry().get("us-indopacific")
        self.assertEqual(desk.status, "access_blocked")
        self.assertFalse(desk.is_collecting)
        self.assertEqual(desk.enabled_source_count, 0)

    def test_the_registry_still_points_at_no_manifest(self):
        # Wiring the shadow manifest into the registry would begin promoting
        # the desk. It stays unwired until collection has run and been
        # reviewed.
        raw = json.loads((REPO_ROOT / "desks" / "registry.json").read_text(
            encoding="utf-8"))
        entry = [d for d in raw["desks"] if d["slug"] == "us-indopacific"][0]
        self.assertIsNone(entry["manifest"])
        self.assertFalse(entry["has_production_records"])

    def test_the_adapter_never_names_a_blocked_host_as_a_permitted_one(self):
        for blocked in ("pacom.mil", "defense.gov"):
            self.assertNotIn(blocked, " ".join(us.PERMITTED_HOSTS))

    def test_the_adapter_docstring_explains_why_dvids_is_not_a_workaround(self):
        head = ADAPTER_SRC.split('"""')[1].lower()
        self.assertIn("pacom.mil", head)
        self.assertIn("403", head)
        self.assertIn("not a workaround", head)


class TestNoEvasionMechanismExists(unittest.TestCase):

    def test_the_adapter_declares_a_single_honest_user_agent(self):
        agents = re.findall(r'User-Agent"\s*:\s*([A-Za-z_]+)', ADAPTER_SRC)
        self.assertEqual(set(agents), {"USER_AGENT"})

    def test_no_proxy_configuration_exists(self):
        for token in ("proxies", "proxy", "socks"):
            self.assertNotIn(token, ADAPTER_SRC.lower(), token)

    def test_no_cookie_or_referer_spoofing_exists(self):
        for token in ("cookie", "referer", "referrer"):
            self.assertNotIn(token, ADAPTER_SRC.lower(), token)

    def test_discovery_uses_the_feed_and_nothing_else(self):
        self.assertEqual(SOURCE["discovery_endpoints"],
                         ["https://www.dvidshub.net/rss/unit/USINDOPACOM"])
        self.assertIn("/rss/unit/USINDOPACOM", us.FEED)

    def test_no_identifier_enumeration_exists(self):
        # A loop over a numeric id range would be enumeration of a namespace
        # the feed did not offer.
        self.assertNotIn("range(", ADAPTER_SRC.split("def discover")[1]
                         .split("def fetch")[0])

    def test_the_disallowed_paths_are_never_constructed(self):
        for path in ("/search/", "/tags/", "/download/", "/mediarequest/"):
            self.assertNotIn('"%s' % path, ADAPTER_SRC)


if __name__ == "__main__":
    unittest.main()
