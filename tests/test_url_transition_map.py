"""
Historical URL continuity.

China Mil Watch stops being the active identity. Its addresses do not stop
being addresses. Some of them are cited — in the weekly editions, and by
anyone who has linked to a record — and a citation that stops resolving is the
one failure this project cannot argue its way out of, because the whole claim
is that it preserves a record.

So `site/url_transition_map.json` is a promise, and these tests are what make
it checkable: every route the deployed tree currently serves has a written
disposition, every redirect lands somewhere real in one hop, nothing loops,
nothing mass-redirects distinct records to a home page, and no historical page
is dressed up as having been published under a name it never carried.

The launch executed this map on 2026-08-27. What the predecessor published is
now a historical fact rather than a live directory, so completeness is checked
against `site/predecessor_routes.txt` — frozen from the last predecessor
deployment — and the emitted side is checked against a real build. Reading
`output/` for the first question would compare the map against the site it
transitions *to*.
"""

from __future__ import annotations

import importlib.util
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

TRACKED_DB = REPO_ROOT / "pla_watch.db"
PRODUCTION_OUT = REPO_ROOT / "output"
MAP_PATH = REPO_ROOT / "site" / "url_transition_map.json"


def load_transition():
    spec = importlib.util.spec_from_file_location(
        "transition", REPO_ROOT / "site" / "transition.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["transition"] = mod
    spec.loader.exec_module(mod)
    return mod


class MapCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.t = load_transition()
        cls.map = cls.t.load_map()


class TestTheMapIsComplete(MapCase):

    def test_every_published_route_has_a_disposition(self):
        """
        A route the predecessor served and nobody wrote down is exactly the one
        that breaks. The record of what it served is frozen, so this stays
        answerable now that the tree that proved it has been replaced.
        """
        published = set(self.t.predecessor_routes())
        declared = {r.old for r in self.map}
        missing = sorted(published - declared)
        self.assertEqual(missing, [],
                         "published routes with no recorded disposition")

    def test_the_map_declares_no_route_that_does_not_exist(self):
        published = set(self.t.predecessor_routes())
        declared = {r.old for r in self.map}
        self.assertEqual(sorted(declared - published), [],
                         "the map describes routes the predecessor never served")

    def test_the_frozen_record_matches_the_last_predecessor_deployment(self):
        """
        Twenty-five route patterns, which is the whole of what China Mil Watch
        ever served. A file that can be edited without anything noticing is not
        a record.
        """
        published = self.t.predecessor_routes()
        self.assertEqual(len(published), 25)
        for required in ("/", "/article/{id}.html", "/signals.html",
                         "/the-pla-watch/posts/{date}.html",
                         "/the-pla-watch/feed.xml"):
            with self.subTest(route=required):
                self.assertIn(required, published)

    def test_every_disposition_is_defined_in_the_map_itself(self):
        for route in self.map:
            with self.subTest(route=route.old):
                self.assertIn(route.disposition, self.map.dispositions)

    def test_every_route_carries_a_reason(self):
        """A disposition with no note is a decision nobody can review."""
        for route in self.map:
            with self.subTest(route=route.old):
                self.assertTrue(route.note.strip(),
                                "%s has no note" % route.old)

    def test_the_map_is_valid_json_with_no_duplicate_routes(self):
        raw = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        olds = [r["old"] for r in raw["routes"]]
        self.assertEqual(len(olds), len(set(olds)))


class TestRedirectsResolveAndDoNotLoop(MapCase):

    def test_no_route_loops(self):
        for route in self.map:
            with self.subTest(route=route.old):
                self.map.resolve(route.old)

    def test_every_redirect_lands_in_one_hop(self):
        """
        A chain costs a round trip per hop and is one edit away from a loop.
        Every moved address names its final destination directly.
        """
        for route in self.map.redirects:
            with self.subTest(route=route.old):
                self.assertEqual(self.map.hops(route.old), 1)

    def test_a_redirect_target_is_never_itself_redirected(self):
        for route in self.map.redirects:
            target = self.map.get(route.new)
            with self.subTest(route=route.old):
                if target is not None:
                    self.assertFalse(target.redirect)

    def test_a_route_that_does_not_move_does_not_redirect(self):
        for route in self.map:
            with self.subTest(route=route.old):
                if not route.moves:
                    self.assertFalse(route.redirect)

    def test_a_moved_route_always_redirects(self):
        for route in self.map:
            with self.subTest(route=route.old):
                if route.moves:
                    self.assertTrue(
                        route.redirect,
                        "%s moves to %s with no redirect" % (route.old,
                                                             route.new))

    def test_no_rule_sends_distinct_records_to_one_page(self):
        """
        The cheap way to make old links 'work' is to point them all at the home
        page. It destroys every citation while reporting success, so it is
        forbidden outright: a pattern route must carry its placeholder through
        to its destination.
        """
        for route in self.map.redirects:
            with self.subTest(route=route.old):
                self.assertNotIn(route.new, ("/", "/index.html"),
                                 "%s is mass-redirected to the home page"
                                 % route.old)
                if route.pattern:
                    placeholders = re.findall(r"\{[a-z_]+\}", route.old)
                    for placeholder in placeholders:
                        self.assertIn(
                            placeholder, route.new,
                            "%s collapses many addresses into one"
                            % route.old)


class TestEvidenceRoutesAreNeverRetired(MapCase):

    def test_record_and_edition_routes_are_marked_as_evidence(self):
        for old in ("/article/{id}.html",
                    "/the-pla-watch/posts/{date}.html",
                    "/the-pla-watch/posts/{date}.json",
                    "/the-pla-watch/archive.html"):
            with self.subTest(route=old):
                route = self.map.get(old)
                self.assertIsNotNone(route)
                self.assertTrue(route.evidence)

    def test_no_evidence_route_is_left_to_an_owner_decision(self):
        """
        `owner_decision` means 'may be retired later'. Nothing cited may sit in
        that category — the question is already answered.
        """
        for route in self.map.evidence_routes:
            with self.subTest(route=route.old):
                self.assertNotEqual(route.disposition, "owner_decision")

    def test_every_published_edition_route_still_exists_today(self):
        posts = PRODUCTION_OUT / "the-pla-watch" / "posts"
        if not posts.is_dir():
            self.skipTest("no output/ in this tree")
        editions = sorted(p.stem for p in posts.glob("*.html"))
        self.assertGreaterEqual(len(editions), 13)
        for slug in editions:
            with self.subTest(edition=slug):
                self.assertTrue((posts / (slug + ".html")).is_file())
                self.assertTrue((posts / (slug + ".json")).is_file())


class TestLegacyLabelling(MapCase):

    def test_every_predecessor_page_is_labelled_legacy(self):
        for route in self.map:
            with self.subTest(route=route.old):
                if route.old.startswith("/the-pla-watch/") and route.old.endswith(
                        (".html", "/")):
                    self.assertTrue(
                        route.legacy_label,
                        "%s is a predecessor page and must be labelled as one"
                        % route.old)

    def test_nothing_outside_the_predecessor_series_is_labelled_legacy(self):
        for route in self.map:
            with self.subTest(route=route.old):
                if route.legacy_label:
                    self.assertTrue(route.old.startswith("/the-pla-watch/"))

    def test_a_preserved_route_keeps_its_own_canonical(self):
        for route in self.map:
            with self.subTest(route=route.old):
                if route.disposition == "preserve" and route.canonical:
                    self.assertEqual(self.map.resolve(route.canonical),
                                     route.canonical)

    def test_a_moved_route_points_its_canonical_at_the_destination(self):
        for route in self.map.redirects:
            with self.subTest(route=route.old):
                self.assertEqual(route.canonical, route.new)


class TestTheCandidateHonoursTheMap(unittest.TestCase):
    """One real build, checked against the promise."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.t = load_transition()
        cls.map = cls.t.load_map()
        cls.tmp = Path(tempfile.mkdtemp(prefix="transition-"))
        cls.out = cls.tmp / "build"
        cls.result = gp.build(cls.out, "Test Title", TRACKED_DB,
                              snapshot=gp.snapshot_from_corpus(TRACKED_DB),
                              legacy_routes=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_preserved_route_is_emitted_by_the_build(self):
        """
        Only the routes the candidate is responsible for. Assets, the feed and
        the predecessor series are carried forward by the deployment, not
        regenerated here, and the candidate is forbidden from writing into the
        predecessor namespace at all.
        """
        owned = ("/index.html", "/archive.html", "/methodology.html")
        for old in owned:
            route = self.map.get(old)
            with self.subTest(route=old):
                self.assertIsNotNone(route)
                self.assertEqual(route.disposition, "preserve")
                self.assertTrue((self.out / route.new.lstrip("/")).is_file())

    def test_every_legacy_record_route_resolves_to_a_real_record(self):
        """
        One stub per address that was public, not one per record. The legacy
        renderer built `/article/` from the analyzed articles, so that is the
        set of addresses that can be cited, and the set the compatibility
        namespace has to cover — no more.
        """
        stubs = sorted((self.out / "article").glob("*.html"))
        self.assertEqual(len(stubs), self.result["legacy_redirects"])
        self.assertLessEqual(len(stubs), self.result["records"])
        for stub in stubs:
            html = stub.read_text(encoding="utf-8")
            match = re.search(r'href="\.\./record/(\d+)\.html"', html)
            with self.subTest(stub=stub.name):
                self.assertIsNotNone(match)
                self.assertTrue(
                    (self.out / "record" / (match.group(1) + ".html")).is_file())

    def test_a_legacy_record_route_keeps_its_own_id(self):
        """The map says {id} -> {id}. A stub pointing at a different record
        would silently rewrite a citation."""
        for stub in sorted((self.out / "article").glob("*.html"))[:200]:
            html = stub.read_text(encoding="utf-8")
            with self.subTest(stub=stub.name):
                self.assertIn('href="../record/%s.html"' % stub.stem, html)

    def test_a_legacy_record_route_carries_a_canonical_to_its_destination(self):
        for stub in sorted((self.out / "article").glob("*.html"))[:50]:
            html = stub.read_text(encoding="utf-8")
            with self.subTest(stub=stub.name):
                self.assertIn('<link rel="canonical" href="../record/%s.html">'
                              % stub.stem, html)

    def test_a_legacy_record_route_does_not_compete_for_indexing(self):
        for stub in sorted((self.out / "article").glob("*.html"))[:50]:
            with self.subTest(stub=stub.name):
                self.assertIn('content="noindex"',
                              stub.read_text(encoding="utf-8"))

    def test_the_build_never_writes_into_the_predecessor_namespace(self):
        self.assertFalse((self.out / "the-pla-watch").exists())

    def test_the_legacy_series_page_does_not_backdate_the_rebrand(self):
        """
        The editions were published under China Mil Watch. The page says so.
        A page that presented them as Indo-Pacific Record issues would be
        falsifying a publication record to tidy up a rename.
        """
        html = self.map and (self.out / "pla-watch.html").read_text(
            encoding="utf-8")
        self.assertIn("China Mil Watch", html)
        self.assertIn("preserved as published", html.lower())
        self.assertIn("because it did not", html)

    def test_every_new_route_the_map_advertises_is_actually_built(self):
        for advertised in self.map.new_routes:
            with self.subTest(route=advertised):
                if "{" in advertised:
                    prefix = advertised.split("{", 1)[0].lstrip("/")
                    matches = list(self.out.glob(prefix + "*"))
                    self.assertTrue(matches, "no page matches %s" % advertised)
                else:
                    self.assertTrue(
                        (self.out / advertised.lstrip("/")).is_file(),
                        "%s is advertised but not built" % advertised)


if __name__ == "__main__":
    unittest.main()
