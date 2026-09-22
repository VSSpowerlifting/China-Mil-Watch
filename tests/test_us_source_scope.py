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

    #: The six statements the framing must make wherever the source is
    #: described. Each is a separate claim; dropping any one of them lets the
    #: desk be read as something it is not.
    REQUIRED_FRAMING = (
        ("named stream", r"dvids usindopacom-tagged reference stream"),
        ("tier B media service", r"tier b dod media-service feed"),
        ("tagging is not authorship",
         r"unit tagging does not imply command authorship or comprehensive\s+"
         r"indo-pacific relevance"),
        ("not a command-release wire",
         r"not a complete usindopacom command-release wire"),
        ("not a China Desk peer", r"not presently a peer of the china desk"),
        ("desk stays blocked",
         r"us indo-pacific reference desk remains .?access_blocked"),
        ("evaluates, does not presuppose",
         r"evaluates whether this source can support that desk\s+later"),
    )

    def test_the_declared_scope_carries_every_required_framing_statement(self):
        flat = re.sub(r"\s+", " ", SCOPE.lower())
        for label, pattern in self.REQUIRED_FRAMING:
            with self.subTest(statement=label):
                self.assertRegex(flat, re.sub(r"\\s\+", " ", pattern))

    def test_the_source_is_named_as_a_reference_stream(self):
        self.assertEqual(SOURCE["display_name"],
                         "DVIDS USINDOPACOM-tagged reference stream")

    def test_the_declared_scope_states_that_no_filter_is_applied(self):
        low = SCOPE.lower()
        self.assertIn("no relevance filter is applied", low)
        self.assertIn("complete eligible", low)

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
        self.assertEqual(discovered, {"china", "singapore"})


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


class TestTheFramingAppearsEverywhereTheSourceIsDescribed(unittest.TestCase):
    """
    One canonical framing, not six drifting paraphrases.

    A description that lives in a manifest, a README, three module docstrings
    and a shared doc will drift unless something checks all six. The claim most
    likely to be softened first is the one that costs the most to keep: that
    this is not presently a peer of the China Desk.
    """

    SURFACES = {
        "manifest": SHADOW_DIR / "manifest.json",
        "readme": SHADOW_DIR / "README.md",
        "adapter": REPO_ROOT / "scraper" / "sources" / "us_dvids.py",
        "runner": REPO_ROOT / "scripts" / "shadow_collect_us.py",
        "reviewer": REPO_ROOT / "scripts" / "review_us_shadow_state.py",
        "shared doc": REPO_ROOT / "docs" / "SHADOW_COLLECTION.md",
    }

    REQUIRED = (
        ("named stream", "dvids usindopacom-tagged reference stream"),
        ("tier B media service", "tier b dod media-service feed"),
        ("tagging is not authorship",
         "unit tagging does not imply command authorship or comprehensive "
         "indo-pacific relevance"),
        ("not a command-release wire",
         "not a complete usindopacom command-release wire"),
        ("not a China Desk peer", "not presently a peer of the china desk"),
        ("desk stays blocked", "us indo-pacific reference desk remains"),
        ("evaluates, does not presuppose",
         "evaluates whether this source can support that desk later"),
    )

    @classmethod
    def flat(cls, path):
        return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").lower())

    def test_every_surface_carries_every_required_statement(self):
        for surface, path in self.SURFACES.items():
            text = self.flat(path)
            for label, phrase in self.REQUIRED:
                with self.subTest(surface=surface, statement=label):
                    self.assertIn(phrase, text)

    def test_access_blocked_is_stated_not_merely_implied(self):
        for surface, path in self.SURFACES.items():
            with self.subTest(surface=surface):
                self.assertIn("access_blocked", self.flat(path))

    #: Phrases that assert the thing the framing denies. A bare substring test
    #: cannot be used for these: the README names several of them precisely to
    #: call them misrepresentations, so a match is only a failure when it is
    #: NOT inside a denial.
    OVERCLAIMS = ("peer of the china desk", "counterpart to the china desk",
                  "equivalent to the china desk", "promoted to public",
                  "command releases from usindopacom")

    #: Words that make the surrounding sentence a denial rather than a claim.
    DENIALS = ("not ", "never", "misrepresentation", "must not", "cannot",
               "would be", "rather than")

    def test_no_surface_asserts_what_the_framing_denies(self):
        for surface, path in self.SURFACES.items():
            text = self.flat(path)
            for phrase in self.OVERCLAIMS:
                for sentence in text.split("."):
                    if phrase not in sentence:
                        continue
                    with self.subTest(surface=surface, phrase=phrase):
                        self.assertTrue(
                            any(d in sentence for d in self.DENIALS),
                            "%s asserts %r outside a denial: %r"
                            % (surface, phrase, sentence.strip()[:160]))

    def test_the_china_desk_comparison_is_always_a_denial(self):
        # The claim most likely to be softened first, checked on its own.
        readme = self.flat(SHADOW_DIR / "README.md")
        self.assertIn("not presently a peer of the china desk", readme)
        self.assertIn("misrepresentation", readme)


class TestTheCompleteEligibleStreamIsCollected(unittest.TestCase):
    """
    No relevance filter, by explicit editorial decision.

    Filtering on title keywords at collection would decide the usefulness
    question the shadow phase exists to measure, and would leave a corpus
    shaped by a guess rather than by the source. The keyword count is a
    diagnostic in the checkpoint report; it is never a gate.
    """

    def test_the_adapter_has_no_keyword_list_at_all(self):
        # A keyword list is the mechanism a filter would need. Its absence is
        # easier to verify than the absence of filtering.
        for token in ("keyword", "indo-pacific", "indopacific", "relevance"):
            self.assertNotIn(token, ADAPTER_SRC.lower().split('"""', 2)[2],
                             token)

    def test_nothing_is_rejected_for_being_off_topic(self):
        self.assertNotIn("off_topic", us.REJECTION_REASONS)
        self.assertNotIn("not_relevant", us.REJECTION_REASONS)
        for reason in us.REJECTION_REASONS:
            self.assertNotIn("relevan", reason)

    def test_every_rejection_reason_is_structural_not_editorial(self):
        # Each reason names something absent, malformed, duplicated or
        # non-textual -- never a judgement about what the document is about.
        structural = {
            us.R_NOT_NEWS_MEDIA, us.R_FOREIGN_HOST, us.R_UNPARSEABLE_URL,
            us.R_MISSING_GUID, us.R_IDENTITY_MISMATCH, us.R_MISSING_LINK,
            us.R_MISSING_TITLE, us.R_MISSING_PUBDATE,
            us.R_UNPARSEABLE_PUBDATE, us.R_OUTSIDE_WINDOW,
            us.R_DUPLICATE_IN_FEED,
        }
        self.assertEqual(set(us.REJECTION_REASONS), structural)

    def test_the_readme_states_the_no_filter_policy(self):
        low = README.lower()
        self.assertIn("no relevance filter is applied", low)
        self.assertIn("diagnostic", low)
