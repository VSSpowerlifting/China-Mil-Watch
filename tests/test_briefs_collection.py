"""
The Indo-Pacific Record Briefs collection and its page renderer.

What is locked here:

  * the collection is the existing issues, unchanged and in the same order,
    plus approved briefs; with no brief the site builds byte-for-byte as before;
  * drafts are withheld, a synthetic fixture never reaches a tree with an
    origin, and no real brief is published while No. 14 is unreconciled;
  * a brief's Signal Veil needs metadata, a derivative, and an exact
    article-URL match into its own source trail;
  * the briefs feed carries briefs only, and the legacy feed is not touched;
  * the brief page has the article anatomy and states where it was published.

All brief data is the synthetic fixture in tests/fixtures/briefs/.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))

import generate_preview as gp                                    # noqa: E402
from core import brief_collection as bc                          # noqa: E402
from core.brief_contract import UNRECONCILED_ISSUES              # noqa: E402
from core.desk_registry import load_registry                     # noqa: E402
from tests import brief_fixtures                                 # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"
LEGACY_FEED = REPO_ROOT / "output" / "the-pla-watch" / "feed.xml"
SLUG = brief_fixtures.FIXTURE_SLUG
TEST_ORIGIN = "https://briefs-review.test"


def fixture_sidecar() -> dict:
    return json.loads((brief_fixtures.FIXTURE_DIR / (SLUG + ".json"))
                      .read_text(encoding="utf-8"))


def real_brief(sidecar: dict) -> dict:
    """The fixture as if it were a real approved brief: not marked synthetic."""
    s = copy.deepcopy(sidecar)
    s.pop("synthetic", None)
    s.pop("fixture_note", None)
    return s


def build(out: Path, **kw) -> dict:
    return gp.build(out, gp.PUBLIC_TITLE, TRACKED_DB,
                    snapshot=gp.snapshot_from_corpus(TRACKED_DB), **kw)


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


class _Tmp(unittest.TestCase):
    def tmp(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="briefs-"))
        self.addCleanup(shutil.rmtree, d, True)
        return d

    def write_brief(self, briefs: Path, slug: str, sidecar: dict) -> Path:
        briefs.mkdir(parents=True, exist_ok=True)
        path = briefs / (slug + ".json")
        path.write_text(json.dumps(sidecar), encoding="utf-8")
        return path


# ── Loading ───────────────────────────────────────────────────────────────────

class TestLoading(_Tmp):

    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry()
        cls.editions = gp.load_editions(REPO_ROOT)

    def test_no_brief_directory_is_exactly_the_existing_issues(self):
        c = bc.load_collection(self.editions, self.registry,
                               briefs_dir=self.tmp() / "absent")
        self.assertEqual(c.briefs, ())
        self.assertEqual(len(c.rows), len(self.editions))
        for row, edition in zip(c.rows, self.editions):
            self.assertIs(row["entry"], edition)
        self.assertIs(c.lead, self.editions[0])

    def test_the_repository_has_no_real_brief_yet(self):
        self.assertFalse(any(gp.BRIEFS_SOURCE.glob("*.json")),
                         "a real brief sidecar exists; this PR adds none")

    def test_no_14_stays_unreconciled(self):
        self.assertEqual(UNRECONCILED_ISSUES, frozenset({14}))

    def test_a_synthetic_fixture_is_refused_by_default(self):
        with self.assertRaises(bc.CollectionError) as cm:
            bc.load_collection(self.editions, self.registry,
                               briefs_dir=brief_fixtures.FIXTURE_DIR)
        self.assertIn("synthetic rendering fixture", str(cm.exception))

    def test_a_synthetic_fixture_loads_only_when_allowed(self):
        c = bc.load_collection(self.editions, self.registry,
                               briefs_dir=brief_fixtures.FIXTURE_DIR,
                               allow_synthetic=True)
        self.assertEqual([b["slug"] for b in c.briefs], [SLUG])
        self.assertEqual(c.rows[0]["kind"], "brief")
        # The existing issues follow, unchanged and in their own order.
        self.assertEqual([r["entry"] for r in c.rows[1:]], self.editions)

    def test_a_real_brief_is_refused_while_no_14_is_unreconciled(self):
        briefs = self.tmp() / "briefs"
        self.write_brief(briefs, "real-brief", real_brief(fixture_sidecar()))
        with self.assertRaises(bc.CollectionError) as cm:
            bc.load_collection(self.editions, self.registry, briefs_dir=briefs)
        self.assertIn("unreconciled", str(cm.exception))
        self.assertIn("real-brief", str(cm.exception))
        # The owner's ruling, simulated: the same brief then loads.
        c = bc.load_collection(self.editions, self.registry, briefs_dir=briefs,
                               unreconciled=frozenset())
        self.assertEqual(len(c.briefs), 1)

    def test_a_draft_is_withheld_and_produces_no_row(self):
        draft = real_brief(fixture_sidecar())
        draft.update(editorial_status="draft", issue_number=None)
        draft.pop("approval")
        briefs = self.tmp() / "briefs"
        self.write_brief(briefs, "a-draft", draft)
        c = bc.load_collection(self.editions, self.registry, briefs_dir=briefs)
        self.assertEqual(c.withheld, ("a-draft",))
        self.assertEqual(c.briefs, ())
        self.assertEqual(len(c.rows), len(self.editions))

    def test_a_brief_that_breaks_the_contract_fails_closed(self):
        broken = fixture_sidecar()
        broken["desks"] = ["china"]
        briefs = self.tmp() / "briefs"
        self.write_brief(briefs, "broken", broken)
        with self.assertRaises(bc.CollectionError) as cm:
            bc.load_collection(self.editions, self.registry, briefs_dir=briefs,
                               allow_synthetic=True)
        self.assertIn("broken.json", str(cm.exception))

    def test_an_unaddressable_slug_is_refused(self):
        for stem in ("Bad_Slug", "index", "feed"):
            with self.subTest(stem=stem):
                briefs = self.tmp() / "briefs"
                self.write_brief(briefs, stem, fixture_sidecar())
                with self.assertRaises(bc.CollectionError):
                    bc.load_collection(self.editions, self.registry,
                                       briefs_dir=briefs, allow_synthetic=True)

    def test_a_brief_cannot_take_an_existing_issue_number(self):
        clash = fixture_sidecar()
        clash["issue_number"] = self.editions[0]["issue"]
        briefs = self.tmp() / "briefs"
        self.write_brief(briefs, "clash", clash)
        with self.assertRaises(bc.CollectionError) as cm:
            bc.load_collection(self.editions, self.registry, briefs_dir=briefs,
                               allow_synthetic=True)
        self.assertIn("assigned twice", str(cm.exception))


class TestProvenance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.editions = gp.load_editions(REPO_ROOT)
        cls.collection = bc.load_collection(
            cls.editions, load_registry(), briefs_dir=None)

    def test_each_existing_issue_states_what_it_was_published_as(self):
        for row in self.collection.rows:
            e = row["entry"]
            with self.subTest(issue=e["issue"]):
                if e["era"] == "historical":
                    self.assertEqual(row["provenance"],
                                     "Published as The PLA Watch under "
                                     "China Mil Watch")
                else:
                    self.assertTrue(row["provenance"].startswith(
                        "Published as The PLA Watch by Indo-Pacific Record"))

    def test_no_14_keeps_its_stored_identity_and_claims_no_approval(self):
        row = next(r for r in self.collection.rows
                   if r["entry"]["issue"] == 14)
        self.assertEqual(row["kind"], "issue")
        self.assertEqual(row["provenance"],
                         "Published as The PLA Watch by Indo-Pacific Record"
                         " · Retrospective edition")
        self.assertNotIn("approv", row["provenance"].lower())

    def test_a_brief_says_it_is_a_brief(self):
        entry = bc.brief_entry(SLUG, fixture_sidecar())
        self.assertEqual(bc.provenance(entry),
                         "Published as an Indo-Pacific Record brief")


# ── Signal Veil provenance ────────────────────────────────────────────────────

class TestBriefVeil(_Tmp):

    def staged(self, veil=True):
        return brief_fixtures.stage(self.tmp(), veil=veil)

    def test_resolves_from_the_briefs_own_trail(self):
        briefs = self.staged()
        v = bc.brief_veil(SLUG, fixture_sidecar(), briefs / bc.MEDIA_DIRNAME)
        self.assertIsNotNone(v)
        self.assertEqual(v["source_page"], "https://fixture-b.invalid/news/b1")
        self.assertEqual(v["anchor"], "r-9100011")
        self.assertEqual(v["route"], "media/%s-veil.jpg" % SLUG)
        self.assertIn("Fixture record B1", v["alt"])

    def test_an_article_outside_the_trail_is_not_provenance(self):
        briefs = self.staged()
        sidecar = fixture_sidecar()
        sidecar["source_trail"] = [e for e in sidecar["source_trail"]
                                   if e["record_id"] != 9100011]
        self.assertIsNone(
            bc.brief_veil(SLUG, sidecar, briefs / bc.MEDIA_DIRNAME))

    def test_a_missing_derivative_or_metadata_is_the_text_led_hero(self):
        briefs = self.staged(veil=False)
        self.assertIsNone(
            bc.brief_veil(SLUG, fixture_sidecar(), briefs / bc.MEDIA_DIRNAME))
        briefs = self.staged()
        (briefs / bc.MEDIA_DIRNAME / bc.source_image_name(SLUG)).unlink()
        self.assertIsNone(
            bc.brief_veil(SLUG, fixture_sidecar(), briefs / bc.MEDIA_DIRNAME))

    def test_the_synthetic_image_is_deterministic(self):
        a = self.tmp() / "a.jpg"
        b = self.tmp() / "b.jpg"
        brief_fixtures.write_synthetic_veil(a)
        brief_fixtures.write_synthetic_veil(b)
        self.assertEqual(a.read_bytes(), b.read_bytes())


# ── Feed ──────────────────────────────────────────────────────────────────────

class TestBriefsFeed(unittest.TestCase):

    def test_the_feed_carries_briefs_only(self):
        entry = bc.brief_entry(SLUG, fixture_sidecar())
        feed = bc.build_briefs_feed([entry], origin=TEST_ORIGIN)
        ids = re.findall(r"<id>([^<]+)</id>", feed)
        self.assertEqual(ids, ["%s/briefs/feed.xml" % TEST_ORIGIN,
                               "%s/briefs/%s.html" % (TEST_ORIGIN, SLUG)])
        self.assertNotIn("the-pla-watch", feed)
        self.assertNotIn("China Mil Watch", feed)
        self.assertEqual(feed, bc.build_briefs_feed([entry], origin=TEST_ORIGIN))

    def test_no_feed_is_built_without_a_brief(self):
        with self.assertRaises(bc.CollectionError):
            bc.build_briefs_feed([], origin=TEST_ORIGIN)


# ── The site build ────────────────────────────────────────────────────────────

class TestSiteBuild(unittest.TestCase):
    """One plain build, one with the fixture (no origin), and one real-shaped
    brief built with a test origin and the owner's ruling simulated."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="briefs-build-"))
        cls.legacy_feed_before = LEGACY_FEED.read_bytes()
        build(cls.root / "plain", briefs_dir=cls.root / "no-briefs")
        stage = brief_fixtures.stage(cls.root / "stage")
        build(cls.root / "fixture", briefs_dir=stage,
              allow_synthetic_briefs=True)
        cls.brief_html = (cls.root / "fixture" / "briefs"
                          / (SLUG + ".html")).read_text(encoding="utf-8")

        real_dir = cls.root / "real" / "briefs"
        shutil.copytree(brief_fixtures.FIXTURE_DIR, real_dir)
        (real_dir / (SLUG + ".json")).write_text(
            json.dumps(real_brief(fixture_sidecar())), encoding="utf-8")
        brief_fixtures.write_synthetic_veil(
            real_dir / bc.MEDIA_DIRNAME / bc.veil_name(SLUG))
        original = gp.load_collection
        gp.load_collection = functools.partial(original,
                                               unreconciled=frozenset())
        try:
            build(cls.root / "origin", briefs_dir=real_dir,
                  site_origin=TEST_ORIGIN, allow_test_origin=True)
        finally:
            gp.load_collection = original

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def page(self, build_name, route):
        return (self.root / build_name / route).read_text(encoding="utf-8")

    # Boundaries

    def test_synthetic_briefs_are_refused_with_an_origin(self):
        with self.assertRaises(SystemExit) as cm:
            build(self.root / "refused", briefs_dir=brief_fixtures.FIXTURE_DIR,
                  allow_synthetic_briefs=True, site_origin=TEST_ORIGIN,
                  allow_test_origin=True)
        self.assertIn("synthetic", str(cm.exception))

    def test_no_command_line_or_production_path_admits_fixtures(self):
        import inspect
        render = (REPO_ROOT / "site" / "render.py").read_text(encoding="utf-8")
        self.assertNotIn("allow_synthetic", render)
        self.assertNotIn("allow_synthetic", inspect.getsource(gp.main))

    def test_a_site_with_no_brief_ships_no_brief_route(self):
        plain = self.root / "plain"
        self.assertFalse((plain / "briefs").exists())
        self.assertFalse((plain / "briefs.css").exists())

    def test_the_legacy_feed_is_untouched(self):
        self.assertEqual(LEGACY_FEED.read_bytes(), self.legacy_feed_before)

    # Pages

    def test_the_fixture_page_is_noindex_and_labelled_synthetic(self):
        self.assertIn(gp.NOINDEX_TAG, self.brief_html)
        self.assertIn("Synthetic test fixture.", self.brief_html)
        self.assertNotIn('rel="canonical"', self.brief_html)

    def test_the_page_has_the_article_anatomy_in_order(self):
        order = ["s-development", "s-coverage", "s-opening", "s-stood-out",
                 "s-compare", "s-why", "s-routine", "s-term", "s-watching",
                 "s-sources", "s-cite"]
        positions = [self.brief_html.index('id="%s"' % a) for a in order]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(self.brief_html.count("<h1"), 1)

    def test_analysis_is_the_current_navigation_item(self):
        self.assertIn('href="../analysis.html" aria-current="page"',
                      self.brief_html)

    def test_every_citation_and_the_veil_credit_point_into_the_trail(self):
        anchors = set(re.findall(r'<li id="(r-\d+)"', self.brief_html))
        self.assertEqual(len(anchors), 6)
        for target in re.findall(r'href="#(r-\d+)"', self.brief_html):
            self.assertIn(target, anchors)

    def test_the_veil_is_credited_to_its_cited_article(self):
        self.assertIn('class="brief-veil"', self.brief_html)
        self.assertEqual(self.brief_html.count("Context, not evidence"), 2)
        self.assertIn('href="https://fixture-b.invalid/news/b1"', self.brief_html)
        self.assertTrue((self.root / "fixture" / "briefs" / "media"
                         / bc.veil_name(SLUG)).is_file())

    def test_model_flag_appears_only_on_the_flagged_record(self):
        self.assertEqual(self.brief_html.count(
            '<span class="evidence evidence--model">Model-flagged</span>'), 1)
        self.assertNotIn("Significant", self.brief_html)

    def test_titles_carry_the_records_own_language(self):
        self.assertNotIn('lang="zh-Hans"', self.brief_html)
        self.assertEqual(len(re.findall(r'class="brief-record-title"[^>]*lang="en"',
                                        self.brief_html)), 6)

    def test_the_brief_leads_analysis_and_the_home_band(self):
        analysis = self.page("fixture", "analysis.html")
        self.assertLess(analysis.index('href="briefs/%s.html"' % SLUG),
                        analysis.index("the-pla-watch/posts/"))
        home = self.page("fixture", "index.html")
        band = home[home.index('id="analysis"'):]
        self.assertIn('href="briefs/%s.html"' % SLUG, band)
        self.assertNotIn("the-pla-watch/posts/", band[:band.index("</section>")])
        for html in (analysis, home):
            self.assertIn("Synthetic test fixture. Not a published brief.", html)

    def test_the_series_page_is_not_changed_by_a_brief(self):
        self.assertEqual(self.page("plain", "pla-watch.html"),
                         self.page("fixture", "pla-watch.html"))

    def test_no_number_after_14_is_shown_as_a_real_issue(self):
        for route in ("analysis.html", "index.html", "pla-watch.html"):
            with self.subTest(route=route):
                self.assertNotIn("No. 15", self.page("plain", route))

    def test_existing_issue_urls_are_unchanged(self):
        html = self.page("plain", "analysis.html")
        for e in gp.load_editions(REPO_ROOT):
            self.assertIn('href="%s"' % e["url"], html)

    # With an origin

    def test_a_real_brief_gets_a_feed_sitemap_entry_and_canonical(self):
        out = self.root / "origin"
        feed = (out / "briefs" / "feed.xml").read_text(encoding="utf-8")
        url = "%s/briefs/%s.html" % (TEST_ORIGIN, SLUG)
        self.assertIn("<id>%s</id>" % url, feed)
        self.assertIn("<loc>%s</loc>" % url,
                      (out / "sitemap.xml").read_text(encoding="utf-8"))
        page = (out / "briefs" / (SLUG + ".html")).read_text(encoding="utf-8")
        self.assertIn('<link rel="canonical" href="%s">' % url, page)
        self.assertIn('type="application/atom+xml"',
                      (out / "analysis.html").read_text(encoding="utf-8"))

    def test_the_briefs_feed_shares_no_id_with_the_legacy_feed(self):
        legacy = set(re.findall(r"<id>([^<]+)</id>",
                                LEGACY_FEED.read_text(encoding="utf-8")))
        feed = (self.root / "origin" / "briefs" / "feed.xml").read_text(
            encoding="utf-8")
        self.assertFalse(legacy & set(re.findall(r"<id>([^<]+)</id>", feed)))


if __name__ == "__main__":
    unittest.main()
