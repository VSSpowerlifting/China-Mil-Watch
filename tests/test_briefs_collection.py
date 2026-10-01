"""
The Indo-Pacific Record Briefs collection and its page renderer.

What is locked here:

  * the collection is one list: the existing issues, unchanged and in the same
    order, plus approved briefs. The issues first published as The PLA Watch
    are earlier Briefs in it, not a second collection (DECISION_LOG
    2026-09-30): the newest item leads, whichever series it began in, and
    "in development" appears only when the list is empty;
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
        self.assertIn("already assigned to an existing issue", str(cm.exception))
        # Not even the fixture's own opt-in exempts it from that rule.
        self.assertNotIn("unreconciled", str(cm.exception))

    def test_a_real_brief_cannot_take_an_existing_issue_number(self):
        # With the owner's ruling simulated, so the unreconciled gate is not
        # what refuses it: the number is.
        for taken in sorted({e["issue"] for e in self.editions}):
            with self.subTest(number=taken):
                clash = real_brief(fixture_sidecar())
                clash["issue_number"] = taken
                briefs = self.tmp() / "briefs"
                self.write_brief(briefs, "clash", clash)
                with self.assertRaises(bc.CollectionError) as cm:
                    bc.load_collection(self.editions, self.registry,
                                       briefs_dir=briefs,
                                       unreconciled=frozenset())
                self.assertIn("already assigned to an existing issue",
                              str(cm.exception))

    def test_a_real_brief_with_a_new_number_is_still_refused_by_default(self):
        # The refusal comes from the contract itself, not only from the
        # loader's aggregate check, so a hand-numbered sidecar fails on its
        # own line and no later step can wave it through.
        briefs = self.tmp() / "briefs"
        for number in (15, 9001):
            with self.subTest(number=number):
                brief = real_brief(fixture_sidecar())
                brief["issue_number"] = number
                self.write_brief(briefs, "hand-numbered", brief)
                with self.assertRaises(bc.CollectionError) as cm:
                    bc.load_collection(self.editions, self.registry,
                                       briefs_dir=briefs)
                self.assertIn("writing one by hand does not assign it",
                              str(cm.exception))

    def test_the_fixture_is_never_eligible_without_the_test_opt_in(self):
        # Neither its 9001 nor the ruling simulated as made lets the loader
        # publish a synthetic sidecar unless the caller passes allow_synthetic.
        for kw in ({}, {"unreconciled": frozenset()}):
            with self.subTest(kw=kw):
                with self.assertRaises(bc.CollectionError) as cm:
                    bc.load_collection(self.editions, self.registry,
                                       briefs_dir=brief_fixtures.FIXTURE_DIR,
                                       **kw)
                self.assertIn("synthetic rendering fixture", str(cm.exception))
        self.assertEqual(fixture_sidecar()["issue_number"], 9001)

    def test_the_synthetic_exemption_reaches_no_real_brief(self):
        # Marking a numbered brief "synthetic" is what the exemption needs, so
        # the exemption's edge is the flag, and the flag is not a public path.
        marked = fixture_sidecar()                         # synthetic: true, 9001
        briefs = self.tmp() / "briefs"
        self.write_brief(briefs, "marked", marked)
        with self.assertRaises(bc.CollectionError):
            bc.load_collection(self.editions, self.registry, briefs_dir=briefs)
        unmarked = real_brief(marked)
        self.write_brief(briefs, "marked", unmarked)
        with self.assertRaises(bc.CollectionError) as cm:
            bc.load_collection(self.editions, self.registry, briefs_dir=briefs,
                               allow_synthetic=True)
        self.assertIn("unreconciled", str(cm.exception))


class TestUnifiedCollection(unittest.TestCase):
    """
    The earlier issues and the native Briefs are one list (DECISION_LOG
    2026-09-30): newest first, each item once, the newest item leading
    whichever series it began in, and empty only when nothing is published.
    """

    @classmethod
    def setUpClass(cls):
        cls.editions = gp.load_editions(REPO_ROOT)
        cls.registry = load_registry()

    def collection(self, **kw):
        return bc.load_collection(self.editions, self.registry,
                                  briefs_dir=None, **kw)

    def test_the_newest_earlier_issue_is_the_lead_when_no_brief_exists(self):
        c = self.collection()
        self.assertIs(c.lead, self.editions[0])
        self.assertEqual(c.lead["issue"], 14)
        self.assertEqual(c.lead_row["kind"], "issue")

    def test_a_brief_numbered_after_the_issues_leads_and_they_follow(self):
        stage = brief_fixtures.stage(Path(tempfile.mkdtemp(prefix="unify-")))
        self.addCleanup(shutil.rmtree, stage.parent, True)
        c = bc.load_collection(self.editions, self.registry, briefs_dir=stage,
                               allow_synthetic=True)
        self.assertEqual(c.lead["slug"], SLUG)
        self.assertEqual([r["kind"] for r in c.rows],
                         ["brief"] + ["issue"] * len(self.editions))

    def test_ordering_is_newest_first_and_deterministic(self):
        c = self.collection()
        dates = [r["entry"]["date"] for r in c.rows]
        self.assertEqual(dates, sorted(dates, reverse=True))
        shuffled = list(reversed(self.editions))
        again = bc.load_collection(shuffled, self.registry, briefs_dir=None)
        self.assertEqual([r["entry"]["slug"] for r in again.rows],
                         [r["entry"]["slug"] for r in c.rows])

    # Chronology, not numbering, decides the lead (owner ruling 2026-09-30):
    # a brief may be unnumbered, and no number can be assigned while an issue
    # is unreconciled, so a number says nothing safe about recency.

    @staticmethod
    def row(slug, date, issue=None, kind="brief"):
        return {"kind": kind, "provenance": "",
                "entry": {"slug": slug, "date": date, "issue": issue}}

    def test_a_newer_unnumbered_brief_leads_an_older_numbered_issue(self):
        rows = [self.row("issue-14", "2026-08-15", 14, "issue"),
                self.row("newer-unnumbered", "2026-09-19")]
        ordered = bc.order_rows(rows)
        self.assertEqual([r["entry"]["slug"] for r in ordered],
                         ["newer-unnumbered", "issue-14"])
        self.assertIsNone(ordered[0]["entry"]["issue"])

    def test_an_older_unnumbered_brief_does_not_lead_a_newer_issue(self):
        rows = [self.row("older-unnumbered", "2026-08-01"),
                self.row("issue-14", "2026-08-15", 14, "issue")]
        self.assertEqual([r["entry"]["slug"] for r in bc.order_rows(rows)],
                         ["issue-14", "older-unnumbered"])

    def test_the_same_week_breaks_ties_by_number_then_slug(self):
        rows = [self.row("b-tie", "2026-08-15"),
                self.row("issue-14", "2026-08-15", 14, "issue"),
                self.row("a-tie", "2026-08-15")]
        want = ["issue-14", "a-tie", "b-tie"]
        for arrangement in (rows, rows[::-1], rows[1:] + rows[:1]):
            self.assertEqual(
                [r["entry"]["slug"] for r in bc.order_rows(arrangement)], want)

    def test_an_unreadable_date_sorts_last_not_first(self):
        rows = [self.row("undated", "not-a-date"),
                self.row("dated", "2026-08-15")]
        self.assertEqual([r["entry"]["slug"] for r in bc.order_rows(rows)],
                         ["dated", "undated"])

    def test_a_numbered_brief_that_is_newer_leads_by_date_not_number(self):
        stage = brief_fixtures.stage(Path(tempfile.mkdtemp(prefix="order-")))
        self.addCleanup(shutil.rmtree, stage.parent, True)
        c = bc.load_collection(self.editions, self.registry, briefs_dir=stage,
                               allow_synthetic=True)
        self.assertEqual(c.lead["slug"], SLUG)
        self.assertGreater(c.lead["date"], self.editions[0]["date"])

    def test_no_issue_appears_twice(self):
        c = self.collection()
        for field_name in ("issue", "url", "slug"):
            values = [r["entry"][field_name] for r in c.rows]
            with self.subTest(field=field_name):
                self.assertEqual(len(values), len(set(values)))

    def test_combining_the_sources_refuses_a_duplicate(self):
        doubled = list(self.editions) + [dict(self.editions[0])]
        with self.assertRaises(bc.CollectionError) as cm:
            bc.load_collection(doubled, self.registry, briefs_dir=None)
        self.assertIn("appears twice", str(cm.exception))

    def test_numbering_and_stored_identity_are_exactly_the_sidecars(self):
        c = self.collection()
        expected = {e["slug"]: (e["issue"], e["title"], e["date"], e["url"],
                                e["era"], e["series_name"], e["publication"])
                    for e in self.editions}
        got = {r["entry"]["slug"]: (r["entry"]["issue"], r["entry"]["title"],
                                    r["entry"]["date"], r["entry"]["url"],
                                    r["entry"]["era"], r["entry"]["series_name"],
                                    r["entry"]["publication"])
               for r in c.rows}
        self.assertEqual(got, expected)
        self.assertEqual(sorted(n for n, *_ in got.values()),
                         list(range(1, len(self.editions) + 1)))

    def test_the_collection_is_empty_only_with_no_issue_and_no_brief(self):
        empty = bc.load_collection([], self.registry, briefs_dir=None)
        self.assertIsNone(empty.lead)
        self.assertIsNone(empty.lead_row)
        self.assertEqual(empty.rows, ())
        self.assertIsNotNone(self.collection().lead)


class TestZeroStateOnlyWhenTheCollectionIsEmpty(unittest.TestCase):
    """A real build whose edition list is exactly what the test injects."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="briefs-zero-"))
        original = gp.load_editions
        gp.load_editions = lambda root: []
        try:
            build(cls.root / "empty", briefs_dir=cls.root / "no-briefs")
        finally:
            gp.load_editions = original

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def page(self, route):
        return (self.root / "empty" / route).read_text(encoding="utf-8")

    def test_analysis_says_briefs_are_in_development(self):
        html = self.page("analysis.html")
        self.assertIn('id="briefs-development"', html)
        self.assertIn("Briefs in development", html)
        self.assertNotIn('id="briefs-lead-title"', html)
        self.assertNotIn('id="briefs-published"', html)
        collections = html[html.index('<h3 id="collections">Collections</h3>'):
                           html.index('<h3 id="series">Series</h3>')]
        self.assertIn("In development", collections)
        self.assertIn('<td data-label="Briefs" class="num">0</td>', collections)

    def test_the_home_band_says_briefs_are_in_development(self):
        home = self.page("index.html")
        band = home[home.index('id="analysis"'):]
        band = band[:band.index('aria-labelledby="record-and-analysis"')]
        self.assertIn("Briefs in development", band)
        self.assertNotIn("Read this Brief", band)


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
                                     "From the former series The PLA Watch "
                                     "· published under China Mil Watch")
                else:
                    self.assertTrue(row["provenance"].startswith(
                        "From the former series The PLA Watch "
                        "· published by Indo-Pacific Record"))

    def test_no_14_keeps_its_stored_identity_and_claims_no_approval(self):
        row = next(r for r in self.collection.rows
                   if r["entry"]["issue"] == 14)
        self.assertEqual(row["kind"], "issue")
        self.assertEqual(row["provenance"],
                         "From the former series The PLA Watch "
                         "· published by Indo-Pacific Record "
                         "· Retrospective edition")
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

    def test_the_fixture_is_refused_by_the_build_with_and_without_an_origin(self):
        # The public renderer is `build()` with an origin and no opt-in.
        for kw in ({}, {"site_origin": TEST_ORIGIN, "allow_test_origin": True}):
            with self.subTest(kw=sorted(kw)):
                with self.assertRaises(bc.CollectionError) as cm:
                    build(self.root / "refused-2",
                          briefs_dir=brief_fixtures.FIXTURE_DIR, **kw)
                self.assertIn("synthetic rendering fixture", str(cm.exception))
                self.assertFalse((self.root / "refused-2" / "briefs").exists())

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

    # The public copy, with no brief published.

    @staticmethod
    def flat(html):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))

    def test_with_earlier_issues_and_no_native_brief_analysis_is_not_empty(self):
        # The earlier issues are published Briefs. The zero-state is for a
        # collection with nothing in it, so it must not appear here.
        text = self.flat(self.page("plain", "analysis.html"))
        self.assertNotIn("Briefs in development", text)
        self.assertNotIn("in development, and no Brief has been published", text)
        self.assertIn("Latest Brief", text)
        for claim in ("Weekly, ongoing", "Closed", "Continuing",
                      "No new issue is published"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, text)
        html = self.page("plain", "analysis.html")
        collections = html[html.index('<h3 id="collections">Collections</h3>'):
                           html.index('<h3 id="series">Series</h3>')]
        n = len(gp.load_editions(REPO_ROOT))
        self.assertIn("Published", collections)
        self.assertNotIn("In development", collections)
        self.assertIn('<td data-label="Briefs" class="num">%d</td>' % n,
                      collections)
        # One collection row, not one per name it was published under.
        self.assertEqual(collections.count("<tr>") - 1, 1)

    def test_analysis_keeps_every_desk_row_and_adds_collections_apart(self):
        html = self.page("plain", "analysis.html")
        start = html.index('<h3 id="series">Series</h3>')
        series = html[start:html.index("</section>", start)]
        self.assertLess(html.index('<h3 id="collections">Collections</h3>'), start)
        self.assertNotIn('<h3 id="collections">', series)
        for desk in load_registry():
            with self.subTest(desk=desk.slug):
                self.assertIn('<a href="%s">%s</a>' % (desk.route, desk.name),
                              series)
        self.assertEqual(series.count("<tr>") - 1, len(load_registry()))

    def test_the_newest_earlier_issue_leads_analysis_as_the_latest_brief(self):
        # With no native brief the newest item of the one collection is the
        # newest earlier issue, and it leads: No. 14 is the latest Brief.
        html = self.page("plain", "analysis.html")
        head = html[html.index('class="band briefs-head"'):
                    html.index('id="briefs-published"')]
        lead = gp.load_editions(REPO_ROOT)[0]
        self.assertIn('id="briefs-lead-title"', head)
        self.assertNotIn('id="briefs-development"', html)
        self.assertIn("Latest Brief · No. %d" % lead["issue"], head)
        self.assertIn('href="%s"' % lead["url"], head)
        self.assertIn("Read this Brief", head)
        # Where it was first published is a secondary line, not the heading.
        self.assertIn("From the former series The PLA Watch", head)
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", head, re.S).group(1)
        self.assertEqual(h1.strip(), "Indo-Pacific Record Briefs")

    def test_analysis_has_no_separate_archive_of_the_earlier_issues(self):
        for name in ("plain", "fixture"):
            with self.subTest(build=name):
                html = self.page(name, "analysis.html")
                text = self.flat(html)
                for marker in ('id="legacy-archive"', 'class="archive-zone"',
                               'id="every-issue"', "feature--archive"):
                    self.assertNotIn(marker, html)
                for phrase in ("Legacy archive", "Historical PLA Watch",
                               "Previous publication", "The series page",
                               "Analysis archive"):
                    self.assertNotIn(phrase, text)
                self.assertEqual(html.count("<h1"), 1)

    def test_every_earlier_issue_is_in_the_one_catalog(self):
        html = self.page("plain", "analysis.html")
        catalog = html[html.index('id="briefs-published"'):
                       html.index('id="briefs-method"')]
        editions = gp.load_editions(REPO_ROOT)
        self.assertGreaterEqual(len(editions), 13)
        for e in editions:
            with self.subTest(issue=e["issue"]):
                self.assertEqual(catalog.count('href="%s"' % e["url"]), 1)
                self.assertIn("No. %d" % e["issue"], catalog)
                self.assertIn(e["title"], catalog.replace("&#39;", "'"))
        # One list: a single ordered list of every row, no second ledger.
        self.assertEqual(catalog.count("<ol "), 1)
        self.assertEqual(catalog.count('class="issue-ledger-row"'),
                         len(editions))
        self.assertIn("%d published Briefs, newest first" % len(editions),
                      self.flat(catalog))

    def test_the_catalog_is_newest_first_and_carries_each_issues_provenance(self):
        html = self.page("plain", "analysis.html")
        catalog = html[html.index('id="briefs-published"'):
                       html.index('id="briefs-method"')]
        numbers = [int(n) for n in re.findall(r'class="issue-no">No\. (\d+)<',
                                              catalog)]
        self.assertEqual(numbers, sorted(numbers, reverse=True))
        self.assertEqual(numbers, [e["issue"]
                                   for e in gp.load_editions(REPO_ROOT)])
        for e in gp.load_editions(REPO_ROOT):
            expected = bc.provenance(e)
            self.assertTrue(expected.startswith("From the former series "))
            self.assertIn(expected, catalog)

    def test_the_operational_tables_stay_below_the_catalog_and_the_key(self):
        html = self.page("plain", "analysis.html")
        order = [html.index(marker) for marker in
                 ('id="briefs-lead-title"', 'id="briefs-published"',
                  'id="briefs-method"', 'id="collections-and-desks"')]
        self.assertEqual(order, sorted(order))

    @staticmethod
    def home_band(html):
        band = html[html.index('id="analysis"'):]
        return band[:band.index('aria-labelledby="record-and-analysis"')]

    def test_the_home_band_shows_the_newest_unified_brief_not_a_zero_state(self):
        # Earlier issues are published Briefs, so with no native brief the band
        # leads with the newest of them and never says "in development".
        band = self.home_band(self.page("plain", "index.html"))
        lead = gp.load_editions(REPO_ROOT)[0]
        self.assertNotIn("Briefs in development", band)
        self.assertIn("Indo-Pacific Record Briefs, No. %d" % lead["issue"], band)
        self.assertIn('href="%s"' % lead["url"], band)
        self.assertIn("Read this Brief", band)
        self.assertIn("From the former series The PLA Watch", band)
        for claim in ('class="band-archive"', "Legacy archive",
                      "Browse the archive", "<svg", 'class="plate',
                      "Read this edition", 'href="pla-watch.html"'):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, band)

    def test_a_brief_leads_the_home_band_and_nothing_stands_beside_it(self):
        band = self.home_band(self.page("fixture", "index.html"))
        link = 'href="briefs/%s.html"' % SLUG
        self.assertIn(link, band)
        self.assertIn("Read this Brief", band)
        self.assertNotIn("Briefs in development", band)
        self.assertNotIn("the-pla-watch/posts/", band)
        self.assertNotIn('class="band-archive"', band)

    def test_a_brief_leads_analysis_then_the_catalog_holds_it_with_the_issues(self):
        html = self.page("fixture", "analysis.html")
        link = 'href="briefs/%s.html"' % SLUG
        order = [html.index(marker) for marker in
                 ('id="briefs-lead-title"', 'id="briefs-published"',
                  'id="briefs-method"', 'id="collections-and-desks"')]
        self.assertEqual(order, sorted(order))
        self.assertLess(html.index(link), html.index('id="briefs-published"'))
        catalog = html[html.index('id="briefs-published"'):
                       html.index('id="briefs-method"')]
        # The fixture (9001) is first, then every earlier issue, in one list.
        self.assertEqual(catalog.count(link), 1)
        self.assertLess(catalog.index(link), catalog.index("the-pla-watch/posts/"))
        editions = gp.load_editions(REPO_ROOT)
        for e in editions:
            self.assertEqual(catalog.count('href="%s"' % e["url"]), 1)
        self.assertEqual(catalog.count('class="issue-ledger-row"'),
                         len(editions) + 1)
        head = html[html.index('class="band briefs-head"'):
                    html.index('id="briefs-published"')]
        self.assertNotIn("the-pla-watch/posts/", head)

    def test_no_page_claims_a_brief_is_being_written_or_published(self):
        for route in ("about.html", "analysis.html", "pla-watch.html",
                      "index.html"):
            with self.subTest(route=route):
                text = self.flat(self.page("plain", route))
                for claim in ("He writes Indo-Pacific Record Briefs",
                              "writes Indo-Pacific Record Briefs",
                              "Briefs is continuing"):
                    self.assertNotIn(claim, text)

    def test_the_about_bio_describes_the_founder_and_claims_no_brief(self):
        text = self.flat(self.page("plain", "about.html"))
        self.assertIn("He founded Indo-Pacific Record, writes source-linked "
                      "security and policy analysis, and maintains the "
                      "project’s collection pipeline.", text)
        self.assertNotIn("He writes The PLA Watch", text)
        bio = text[text.index("Benjamin Yang studies"):]
        bio = bio[:bio.index("pipeline.") + len("pipeline.")]
        for word in ("Brief", "brief", "PLA Watch"):
            self.assertNotIn(word, bio)

    def test_the_old_series_route_is_a_compatibility_bridge_only(self):
        # `pla-watch.html` stays because inbound links to it are established
        # and its citation anchors are cited. It is not a second collection: it
        # says the issues are now Briefs, sends readers to Analysis, and lists
        # no issue of its own.
        html = self.page("plain", "pla-watch.html")
        text = self.flat(html)
        self.assertIn("The PLA Watch is now part of Indo-Pacific Record Briefs",
                      text)
        self.assertIn('href="analysis.html"', html)
        self.assertIn("Read the Briefs", html)
        self.assertNotIn('<table', html)
        for e in gp.load_editions(REPO_ROOT):
            self.assertNotIn('href="%s"' % e["url"], html)
        for claim in ("Analysis archive", "This page is an archive of those issues",
                      "The series continues", "Continuing", "in development",
                      "Earlier Briefs"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, text)

    def test_the_compatibility_route_keeps_every_citation_anchor(self):
        html = self.page("plain", "pla-watch.html")
        for e in gp.load_editions(REPO_ROOT):
            with self.subTest(slug=e["slug"]):
                self.assertIn('id="cite-edition-%s"' % e["slug"], html)
        # Collapsed by default: it reads as a bridge, not a list.
        self.assertIn('<details class="ed-cite cite-all">', html)
        self.assertNotIn("<details class=\"ed-cite cite-all\" open", html)

    def test_no_page_links_to_the_old_series_route(self):
        # One analysis destination: the compatibility route is linked from no
        # navigation, footer or page body. It only resolves.
        for route in ("index.html", "analysis.html", "archive.html",
                      "desks.html", "china.html", "about.html",
                      "coverage.html", "methodology.html", "sources.html"):
            with self.subTest(route=route):
                html = self.page("plain", route)
                self.assertNotIn('href="pla-watch.html"', html)

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


class TestUnapprovedBriefsStayOutOfPublicOutput(_Tmp):
    """Built the way production builds (a site origin), a brief that is not
    approved and numbered adds nothing: not a page, a row, a feed, a sitemap
    entry or a byte to any other page."""

    ORIGIN = dict(site_origin=TEST_ORIGIN, allow_test_origin=True)

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="briefs-unapproved-"))
        build(cls.root / "plain", briefs_dir=cls.root / "no-briefs",
              **cls.ORIGIN)
        cls.plain = tree(cls.root / "plain")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def draft(self, **over):
        d = real_brief(fixture_sidecar())
        d.update(editorial_status="draft", issue_number=None)
        d.pop("approval")
        d.update(over)
        return d

    def built(self, name, sidecar):
        briefs = self.root / (name + "-src")
        self.write_brief(briefs, "candidate", sidecar)
        return build(self.root / name, briefs_dir=briefs, **self.ORIGIN)

    def test_an_unnumbered_draft_leaves_the_public_output_unchanged(self):
        self.built("draft", self.draft())
        self.assertEqual(tree(self.root / "draft"), self.plain)
        out = self.root / "draft"
        self.assertFalse((out / "briefs").exists())
        self.assertFalse((out / "briefs.css").exists())
        self.assertNotIn("briefs/", (out / "sitemap.xml").read_text(encoding="utf-8"))

    def test_a_draft_that_carries_a_number_is_still_withheld(self):
        self.built("numbered-draft", self.draft(issue_number=15))
        self.assertEqual(tree(self.root / "numbered-draft"), self.plain)

    def test_an_approved_brief_with_no_number_stops_the_build(self):
        unnumbered = real_brief(fixture_sidecar())
        unnumbered["issue_number"] = None
        with self.assertRaises(bc.CollectionError) as cm:
            self.built("unnumbered", unnumbered)
        self.assertIn("carries its issue number", str(cm.exception))
        self.assertFalse((self.root / "unnumbered" / "briefs").exists())

    def test_an_approved_numbered_brief_stops_the_build_while_no_14_is_unreconciled(self):
        with self.assertRaises(bc.CollectionError) as cm:
            self.built("numbered", real_brief(fixture_sidecar()))
        self.assertIn("unreconciled", str(cm.exception))
        self.assertFalse((self.root / "numbered" / "briefs").exists())


if __name__ == "__main__":
    unittest.main()
