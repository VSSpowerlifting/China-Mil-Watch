"""
What the Japan feeds actually are, and what the manifest is allowed to say.

The first manifest called this source "Japan MOD / Joint Staff — official
releases" in languages `["ja", "en"]`. Categorising both feeds in full on
2026-08-26 showed all three parts of that to be wrong:

    /j/rss/news.xml    142 items — /j/press/ 105, /j/approach/ 37
                       134 HTML, 8 PDF
    /j/rss/update.xml  391 items — /j/press/ 126, /j/budget/ 93, /j/profile/ 76,
                       /j/approach/ 63, /j/policy/ 21, /j/presiding/ 11,
                       /j/kids/ 1 — 342 HTML, 0 PDF

Neither feed carries a single Joint Staff (`/js/`) item. Neither carries a
single English (`/en/`) item. And `update.xml` is not a press-release feed at
all — it reports any page the ministry publishes or revises, including budget
tables and a children's page.

Two failure modes follow, and these tests refuse both:

  * calling all of it "official releases" fabricates a document type;
  * keeping only the items that look like releases is silent sampling.

Everything is kept, and every record says which family it came from.
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.sources import jp_mod                                # noqa: E402

MANIFEST = json.loads(
    (ROOT / "shadow" / "jp_mod" / "manifest.json").read_text(encoding="utf-8"))

_spec = importlib.util.spec_from_file_location(
    "shadow_collect_japan", ROOT / "scripts" / "shadow_collect_japan.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

COLLECTED = [s for s in MANIFEST["sources"] if not s.get("_not_collected")]
DECLARED_ONLY = [s for s in MANIFEST["sources"] if s.get("_not_collected")]


class TestTheManifestClaimsOnlyWhatTheFeedsCarry(unittest.TestCase):

    def test_no_collected_source_claims_the_joint_staff(self):
        for s in COLLECTED:
            with self.subTest(slug=s["slug"]):
                self.assertNotIn("joint staff", s["display_name"].lower())
                self.assertNotIn("統合幕僚監部", s["display_name"])

    def test_no_collected_source_claims_english(self):
        for s in COLLECTED:
            with self.subTest(slug=s["slug"]):
                self.assertEqual(s["language_tags"], ["ja"])

    def test_the_desk_declares_only_japanese(self):
        self.assertEqual(MANIFEST["desk"]["supported_language_tags"], ["ja"])

    def test_no_collected_source_calls_itself_a_press_release_feed_wholesale(self):
        """`update.xml` is a whole-site stream; calling it releases is the bug."""
        update = [s for s in COLLECTED if "siteupdate" in s["slug"]][0]
        self.assertNotIn("press release", update["display_name"].lower())
        scope = " ".join(update["declared_scope"]).lower()
        self.assertIn("not a press-release feed", scope)

    def test_each_collected_feed_declares_its_own_single_endpoint(self):
        for s in COLLECTED:
            with self.subTest(slug=s["slug"]):
                self.assertEqual(len(s["discovery_endpoints"]), 1)

    def test_the_two_feeds_are_registered_separately(self):
        self.assertEqual(len(COLLECTED), 2)
        self.assertEqual({s["slug"] for s in COLLECTED},
                         {"jp_mod_news_ja", "jp_mod_siteupdate_ja"})

    def test_each_declared_scope_states_measured_counts(self):
        for s in COLLECTED:
            scope = " ".join(s["declared_scope"])
            with self.subTest(slug=s["slug"]):
                self.assertIn("2026-08-26", scope)
                self.assertIn("Joint Staff (/js/) items: 0", scope)
                self.assertIn("English (/en/) items: 0", scope)

    def test_the_joint_staff_stays_declared_and_distinguishable(self):
        js = [s for s in DECLARED_ONLY if s["slug"] == "jp_joint_staff_en"]
        self.assertEqual(len(js), 1)
        self.assertFalse(js[0]["enabled"])
        self.assertIsNone(js[0]["adapter"])

    def test_the_english_estate_stays_declared_and_distinguishable(self):
        en = [s for s in DECLARED_ONLY if s["slug"] == "jp_mod_press_en"]
        self.assertEqual(len(en), 1)
        self.assertFalse(en[0]["enabled"])
        self.assertIsNone(en[0]["adapter"])

    def test_nothing_is_enabled(self):
        for s in MANIFEST["sources"]:
            with self.subTest(slug=s["slug"]):
                self.assertFalse(s["enabled"])

    def test_the_access_notes_state_the_retrieval_fraction(self):
        notes = " ".join(MANIFEST["access_notes"])
        self.assertIn("8 of 142", notes)
        self.assertIn("134 of 142", notes)
        self.assertIn("partial retrieval, not coverage", notes)

    def test_the_manifest_never_claims_qualification(self):
        raw = json.dumps(MANIFEST, ensure_ascii=False).lower()
        for claim in ("fully qualified", "complete coverage", "full coverage",
                      "qualified desk"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, raw)


class TestOnlyCollectableSourcesAreCollected(unittest.TestCase):

    def test_load_sources_returns_the_two_reachable_feeds(self):
        self.assertEqual([s.slug for s in runner.load_sources()],
                         ["jp_mod_news_ja", "jp_mod_siteupdate_ja"])

    def test_load_sources_never_returns_a_declared_only_source(self):
        slugs = {s.slug for s in runner.load_sources()}
        for s in DECLARED_ONLY:
            with self.subTest(slug=s["slug"]):
                self.assertNotIn(s["slug"], slugs)

    def test_each_source_carries_its_own_endpoint_to_the_adapter(self):
        for src in runner.load_sources():
            a = jp_mod.JPModAdapter(src, session=object())
            with self.subTest(slug=src.slug):
                self.assertEqual(a.feeds, tuple(src.discovery_endpoints))
                self.assertEqual(len(a.feeds), 1)


class TestKindsAreLabelsNotFilters(unittest.TestCase):
    """
    Every URL family measured in either feed must get a name of its own. An
    unrecognised family must still get a name rather than disappearing — the
    moment a family can be dropped, the counters describe a corpus the collector
    chose instead of the one the ministry published.
    """

    MEASURED = {
        "/j/press/news/2026/08/25a.pdf": "press release",
        "/j/press/other.html": "press material",
        "/j/approach/x.html": "defense exchange or policy item",
        "/j/budget/x.html": "budget document",
        "/j/profile/x.html": "ministry profile page",
        "/j/policy/x.html": "policy document",
        "/j/presiding/x.html": "presiding-office page",
        "/j/kids/x.html": "public education page",
    }

    def test_every_measured_family_has_its_own_label(self):
        for path, expected in self.MEASURED.items():
            with self.subTest(path=path):
                self.assertEqual(
                    jp_mod.publication_kind("https://www.mod.go.jp" + path),
                    expected)

    def test_the_labels_are_distinct(self):
        self.assertEqual(len(set(self.MEASURED.values())),
                         len(self.MEASURED.values()))

    def test_an_unknown_family_is_named_not_dropped(self):
        kind = jp_mod.publication_kind("https://www.mod.go.jp/j/brandnew/x.html")
        self.assertTrue(kind)
        self.assertIn("unclassified", kind)

    def test_a_budget_page_is_never_called_a_release(self):
        kind = jp_mod.publication_kind("https://www.mod.go.jp/j/budget/x.html")
        self.assertNotIn("release", kind)

    def test_no_keyword_filter_exists_in_the_adapter(self):
        source = (ROOT / "scraper" / "sources" / "jp_mod.py").read_text("utf-8")
        for smell in ("KEYWORD", "keywords", "relevance", "if any(w in title"):
            with self.subTest(smell=smell):
                self.assertNotIn(smell, source)


if __name__ == "__main__":
    unittest.main()
