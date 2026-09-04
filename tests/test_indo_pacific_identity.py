"""
Brand identity contract for the Indo-Pacific Record candidate.

Two failures are in scope, and they pull in opposite directions.

The first is a rebrand that does not happen: China Mil Watch surviving as the
masthead of a product that now declares four desks, so the page promises a
region and signs a country. The second is a rebrand that erases: historical
issues quietly restamped with a name they never carried, commit messages
scrubbed, transition documents rewritten. The first is a broken promise; the
second is falsifying a publication record, which is worse.

So the guards here are directional, never a repository-wide string ban. The
predecessor name is forbidden in the candidate's chrome — masthead, document
title, footer — and required where the archive is described. Documentation,
commit history, the deployed predecessor site and the transition map are all
outside the scope of a check on rendered candidate pages, and deliberately so.

Nothing here builds production or touches the tracked database.
"""

from __future__ import annotations

import importlib.util
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

#: The candidate's public identity, as owner-directed.
TITLE = "Indo-Pacific Record"
TAGLINE = ("Official defense and security texts, preserved as published and "
           "analyzed in context.")

#: Retired names. `PREDECESSOR` is historical fact and is allowed in archival
#: context; `WORKING_NAME` was never public and is allowed nowhere on a page.
PREDECESSOR = "China Mil Watch"
PREDECESSOR_SERIES = "The PLA Watch"
WORKING_NAME = "The Declared Record"

#: Pages that describe the archive, and may therefore name the predecessor.
#: Everything else may not. The list is explicit so widening it is a decision.
ARCHIVAL_PAGES = ("about.html", "pla-watch.html", "analysis.html",
                  "china.html", "index.html")


def load_render():
    spec = importlib.util.spec_from_file_location(
        "site_render", REPO_ROOT / "site" / "render.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class IdentityCase(unittest.TestCase):
    """One build under the real public title."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="identity-"))
        cls.out = cls.tmp / "build"
        gp.build(cls.out, TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, name: str) -> str:
        return (self.out / name).read_text(encoding="utf-8")

    def pages(self):
        return {str(p.relative_to(self.out)): p.read_text(encoding="utf-8")
                for p in sorted(self.out.rglob("*.html"))}

    @staticmethod
    def chrome(html: str) -> str:
        """Masthead, document title and footer — the publication's signature."""
        parts = [html.split("<title>", 1)[1].split("</title>", 1)[0]]
        parts.append(html.split("<header", 1)[1].split("</header>", 1)[0])
        parts.append(html.split("<footer", 1)[1].split("</footer>", 1)[0])
        return "\n".join(parts)


class TestTheMastheadIsTheNewIdentity(IdentityCase):

    def test_the_home_page_wordmark_is_the_h1(self):
        html = self.page("index.html")
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        self.assertIsNotNone(h1)
        self.assertIn(TITLE, h1.group(1))

    def test_every_page_carries_the_wordmark_and_the_tagline(self):
        for name, html in self.pages().items():
            with self.subTest(page=name):
                self.assertIn(TITLE, html)
                self.assertIn(TAGLINE, html)

    def test_every_page_title_names_the_publication(self):
        for name, html in self.pages().items():
            title = html.split("<title>", 1)[1].split("</title>", 1)[0]
            with self.subTest(page=name):
                self.assertIn(TITLE, title)

    def test_every_page_has_exactly_one_h1(self):
        for name, html in self.pages().items():
            with self.subTest(page=name):
                self.assertEqual(len(re.findall(r"<h1[ >]", html)), 1)

    def test_the_description_metadata_is_the_tagline(self):
        for name, html in self.pages().items():
            with self.subTest(page=name):
                self.assertIn('<meta name="description" content="%s">'
                              % TAGLINE, html)

    def test_the_build_mode_is_recorded_in_metadata(self):
        for name, html in self.pages().items():
            with self.subTest(page=name):
                self.assertIn('name="generator" content="%s — %s build"'
                              % (TITLE, gp.BUILD_MODE), html)

    def test_the_mark_is_shipped_and_referenced_as_the_icon(self):
        self.assertTrue((self.out / "mark.svg").is_file())
        for name, html in self.pages().items():
            with self.subTest(page=name):
                self.assertRegex(
                    html, r'<link rel="icon" type="image/svg\+xml" '
                          r'href="(\.\./)?mark\.svg">')

    def test_the_mark_is_decorative_and_the_wordmark_is_the_name(self):
        """
        The mark in the masthead is announced to nobody, so a screen reader
        reads the wordmark once rather than a graphic and a heading. The
        standalone file, used as a favicon, carries its own accessible title
        instead.

        The masthead mark became an <img> when the compass replaced the
        generic document glyph: the canonical artwork is owner-supplied raster
        and is not redrawn as inline vector. The property being asserted is
        unchanged — decorative in the page, named in the icon file.
        """
        html = self.page("index.html")
        mark = re.search(r'<img[^>]+class="brand-mark"[^>]*>', html)
        self.assertIsNotNone(mark, "no masthead mark rendered")
        mark = mark.group(0)
        self.assertIn('alt=""', mark)
        self.assertIn('aria-hidden="true"', mark)
        standalone = (self.out / "mark.svg").read_text(encoding="utf-8")
        self.assertIn("<title>%s</title>" % TITLE, standalone)

    def test_the_mark_carries_no_military_symbolism(self):
        svg = (self.out / "mark.svg").read_text(encoding="utf-8").lower()
        for banned in ("star", "crosshair", "reticle", "radar", "wing",
                       "insignia", "sword", "shield"):
            with self.subTest(motif=banned):
                self.assertNotIn(banned, svg)

    def test_the_primary_navigation_is_the_regional_information_model(self):
        nav = self.page("index.html").split('aria-label="Primary"', 1)[1]
        nav = nav.split("</nav>", 1)[0]
        labels = re.findall(r">([A-Za-z ]+)</a>", nav)
        self.assertEqual(labels, ["Record", "Desks", "Sources", "Analysis",
                                  "Coverage", "Methodology", "About"])


class TestRetiredNamesStayRetired(IdentityCase):

    def test_the_working_name_appears_on_no_page(self):
        """
        "The Declared Record" was a prototype codename. It was never adopted
        and never published, so unlike the predecessor it has no archival
        claim on any surface.
        """
        for name, html in self.pages().items():
            with self.subTest(page=name):
                self.assertNotIn(WORKING_NAME, html)

    def test_the_predecessor_never_appears_in_chrome(self):
        for name, html in self.pages().items():
            with self.subTest(page=name):
                self.assertNotIn(PREDECESSOR, self.chrome(html))

    def test_the_predecessor_appears_only_where_the_archive_is_described(self):
        for name, html in self.pages().items():
            if PREDECESSOR not in html:
                continue
            with self.subTest(page=name):
                self.assertIn(
                    name, ARCHIVAL_PAGES,
                    "%s names the predecessor outside archival context" % name)

    def test_the_predecessor_is_named_where_the_change_is_explained(self):
        """
        The other half of the rule. A rebrand that never mentions what it
        replaced leaves a reader unable to connect a citation to its source.
        """
        about = self.page("about.html")
        self.assertIn(PREDECESSOR, about)
        self.assertIn("The umbrella name changed because the scope did", about)
        series = self.page("pla-watch.html")
        self.assertIn(PREDECESSOR, series)
        self.assertIn(PREDECESSOR_SERIES, series)

    def test_the_predecessor_is_never_described_as_the_current_product(self):
        for name, html in self.pages().items():
            flat = re.sub(r"\s+", " ", html)
            with self.subTest(page=name):
                for claim in ("%s preserves" % PREDECESSOR,
                              "%s is an" % PREDECESSOR,
                              "%s collects" % PREDECESSOR,
                              "Welcome to %s" % PREDECESSOR):
                    self.assertNotIn(claim, flat)

    def test_the_pla_watch_series_is_not_retired_only_relabelled(self):
        """The series continues; only the masthead above it changed."""
        html = self.page("pla-watch.html")
        self.assertIn("not a discontinued one", html)


class TestTheGuardIsNotARepositoryWideStringBan(unittest.TestCase):
    """
    The historical record has to stay legible, so the checks above are scoped
    to rendered candidate pages. These assert the things a naive ban would have
    destroyed are all still present.
    """

    def test_the_governing_documents_still_name_the_predecessor(self):
        contract = (REPO_ROOT / "docs"
                    / "INDO_PACIFIC_RECORD_EVOLUTION.md").read_text("utf-8")
        self.assertIn(PREDECESSOR, contract)
        self.assertIn(WORKING_NAME, contract)

    def test_the_transition_map_still_names_the_predecessor_routes(self):
        raw = (REPO_ROOT / "site"
               / "url_transition_map.json").read_text("utf-8")
        self.assertIn("/the-pla-watch/", raw)
        self.assertIn("predecessor", raw)

    def test_the_published_editions_are_not_rewritten(self):
        """
        The deployed pages keep the masthead they were published under. This
        branch does not touch them, and nothing in the candidate does either.
        """
        posts = REPO_ROOT / "output" / "the-pla-watch" / "posts"
        if not posts.is_dir():
            self.skipTest("no output/ in this tree")
        rendered = sorted(posts.glob("*.html"))
        self.assertGreaterEqual(len(rendered), 13)
        carrying = [p for p in rendered
                    if PREDECESSOR in p.read_text(encoding="utf-8")]
        self.assertEqual(len(carrying), len(rendered),
                         "a published edition lost its original masthead")

    def test_the_site_mode_seam_defaults_to_the_launched_mode(self):
        r = load_render()
        self.assertEqual(r.DEFAULT_SITE_MODE, r.INDO_PACIFIC_RECORD)
        self.assertEqual(r.INDO_PACIFIC_RECORD_TITLE, TITLE)


if __name__ == "__main__":
    unittest.main()
