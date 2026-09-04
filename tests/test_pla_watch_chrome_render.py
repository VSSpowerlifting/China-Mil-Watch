"""
The PLA Watch identity boundary, asserted through the real render path.

Why this module exists
----------------------
The 2026-09-04 audit found the deployed weekly series serving the predecessor's
name in its navigation, its masthead tag, its favicon and its social card —
while the source templates had already been corrected. The templates were
right; the published tree was seven days stale.

`tests/test_public_chrome_is_truthful.py` could not catch it. That module
builds a fresh tree with `generate_preview.build()`, which renders the record
site and never emits `the-pla-watch/` at all. The weekly pages come from
`scripts/rerender_pla_watch.py`, and nothing rendered them under test.

So this module renders through the actual weekly path — `make_pw_env()`, the
real `pla-watch-*.html` templates, and `_build_post_context()` over the real
committed sidecars — into a temporary directory. It asserts the boundary that
`core/edition_identity.py` defines, from both sides.

The boundary
------------
An edition is a dated artifact. Editions 1-13 were published by China Mil
Watch and keep that name in their own byline, author title and citation:
re-rendering one must reproduce the page that was published, not restate it
under whatever the project is called today.

The site around them is not dated. Navigation, the masthead tag, the parent
publication, the favicon and the social card are properties of the site, and
the site is Indo-Pacific Record — always, including on a page that lists
historical editions.

Both halves are asserted. A change that scrubs the predecessor from edition
bylines fails here just as loudly as one that leaves it in the chrome.

Nothing here writes into `output/`.
"""

from __future__ import annotations

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

PREDECESSOR = "China Mil Watch"
CURRENT = "Indo-Pacific Record"
SERIES = "The PLA Watch"

#: `core.edition_identity.LAST_HISTORICAL_ISSUE`, restated so a change to the
#: constant has to be a deliberate change to this contract too.
LAST_HISTORICAL_ISSUE = 13

POSTS_DIR = REPO_ROOT / "output" / "the-pla-watch" / "posts"


def load_sidecars() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(POSTS_DIR.glob("*.json"))]


class WeeklyRenderCase(unittest.TestCase):
    """
    Renders the weekly series the way the weekly renderer does, into a
    scratch directory. Skips rather than fails where the environment cannot
    import the renderer's dependencies, so an offline suite stays honest
    about what it did not check.
    """

    @classmethod
    def setUpClass(cls):
        if not POSTS_DIR.is_dir() or not any(POSTS_DIR.glob("*.json")):
            raise unittest.SkipTest("no published sidecars to render")
        try:
            from scripts.pw_env import make_pw_env
            import scripts.rerender_pla_watch as rr
        except Exception as exc:                        # pragma: no cover
            raise unittest.SkipTest("weekly renderer unavailable: %s" % exc)

        cls.rr = rr
        cls.tmp = Path(tempfile.mkdtemp(prefix="pw-chrome-"))
        env = make_pw_env()
        post_tmpl = env.get_template("pla-watch-post.html")
        index_tmpl = env.get_template("pla-watch-index.html")
        archive_tmpl = env.get_template("pla-watch-archive.html")

        sidecars = load_sidecars()
        rr.validate_sidecar_identities(sidecars)
        by_date = sorted(sidecars, key=lambda s: s.get("date", ""))

        cls.posts = {}
        for i, sidecar in enumerate(by_date):
            ctx = rr._build_post_context(sidecar)
            ctx["prev_post"] = by_date[i - 1] if i > 0 else None
            ctx["next_post"] = by_date[i + 1] if i + 1 < len(by_date) else None
            cls.posts[sidecar["date"]] = {
                "html": post_tmpl.render(**ctx),
                "issue": sidecar.get("issue_number"),
                "sidecar": sidecar,
            }

        newest_first = sorted(sidecars, key=lambda s: s.get("date", ""),
                              reverse=True)
        origin = rr.SITE_ORIGIN
        cls.index_html = index_tmpl.render(
            latest_post=newest_first[0],
            archive_posts=newest_first[1:], root_path="../",
            page_url="%s/the-pla-watch/" % origin, latest_veil=None)
        cls.archive_html = archive_tmpl.render(
            posts=newest_first, root_path="../",
            page_url="%s/the-pla-watch/archive.html" % origin)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def chrome(html: str) -> str:
        """Header and nav only — never the edition's own body."""
        return "\n".join(re.findall(
            r"<(?:header|nav)\b[\s\S]*?</(?:header|nav)>", html, re.I))

    @staticmethod
    def head(html: str) -> str:
        return html.split("</head>", 1)[0]

    def site_pages(self):
        return {"index.html": self.index_html,
                "archive.html": self.archive_html}


class TestCurrentSiteChromeIsIndoPacificRecord(WeeklyRenderCase):

    def test_the_series_landing_chrome_names_the_current_publication(self):
        for name, html in self.site_pages().items():
            with self.subTest(page=name):
                self.assertIn(CURRENT, self.chrome(html))

    def test_no_site_chrome_carries_the_predecessor(self):
        """
        The masthead tag, the back-link and the nav belong to the site, not to
        any edition. This is the guard the deployed tree failed.
        """
        for name, html in self.site_pages().items():
            with self.subTest(page=name):
                self.assertNotIn(PREDECESSOR, self.chrome(html))

    def test_no_post_navigation_carries_the_predecessor(self):
        """
        Navigation only — deliberately not the whole header.

        `pla-watch-base.html` states the publishing identity of the page the
        masthead sits on, so on an edition page the masthead tag is that
        edition's publisher and reads "A weekly publication of China Mil
        Watch" for issues 1-13. That is the historical contract, not
        staleness, and a header-wide ban would force it to be broken.

        The nav is a different object: it belongs to the site, and the site
        is always Indo-Pacific Record.
        """
        for date, post in self.posts.items():
            nav = re.search(r"<nav\b[\s\S]*?</nav>", post["html"], re.I)
            with self.subTest(edition=date):
                self.assertIsNotNone(nav)
                self.assertNotIn(PREDECESSOR, nav.group(0))

    def test_the_back_link_points_at_the_current_publication(self):
        for date, post in self.posts.items():
            with self.subTest(edition=date):
                back = re.search(r'class="pw-nav-back"[^>]*>([^<]+)<',
                                 post["html"])
                self.assertIsNotNone(back, "no back-link rendered")
                self.assertIn(CURRENT, back.group(1))

    def test_a_historical_editions_masthead_tag_names_its_own_publisher(self):
        """
        The positive half. An edition page must say who published *it*, and
        for issues 1-13 that is the predecessor. This is the assertion that
        stops a future identity sweep from restating thirteen published
        artifacts under a name they never carried.
        """
        historical = {d: p for d, p in self.posts.items()
                      if p["issue"] and p["issue"] <= LAST_HISTORICAL_ISSUE}
        self.assertGreater(len(historical), 0)
        for date, post in historical.items():
            tag = re.search(r'class="pw-tag"[^>]*>([^<]+)<', post["html"])
            with self.subTest(edition=date, issue=post["issue"]):
                self.assertIsNotNone(tag, "no masthead tag rendered")
                self.assertIn(PREDECESSOR, tag.group(1))

    def test_the_series_name_is_never_treated_as_renamed(self):
        for name, html in self.site_pages().items():
            with self.subTest(page=name):
                self.assertIn(SERIES, html)


class TestCurrentIconAndSocialAssetsAreUsed(WeeklyRenderCase):
    """
    The weekly pages sit one and two levels below the site root and reference
    the root asset set. Those references must be the current ones.
    """

    def all_rendered(self):
        pages = dict(self.site_pages())
        pages.update({d: p["html"] for d, p in self.posts.items()})
        return pages

    def test_no_page_references_the_predecessor_eagle(self):
        for name, html in self.all_rendered().items():
            with self.subTest(page=name):
                self.assertNotIn("logo-icon.png", html)
                self.assertNotIn("logo-wordmark.png", html)

    def test_the_icon_is_the_current_mark(self):
        for name, html in self.all_rendered().items():
            with self.subTest(page=name):
                self.assertRegex(
                    self.head(html),
                    r'<link rel="icon"[^>]+href="(?:\.\./)+mark\.svg"')

    def test_the_touch_icon_is_the_current_mark(self):
        for name, html in self.all_rendered().items():
            with self.subTest(page=name):
                self.assertRegex(
                    self.head(html),
                    r'<link rel="apple-touch-icon"'
                    r'[^>]+href="(?:\.\./)+apple-touch-icon\.png"')

    def test_the_site_social_card_is_not_the_retired_homepage_screenshot(self):
        """
        `og-image.png` is a screenshot of the predecessor's front page, dated
        24 August 2026. It is not a current identity asset.
        """
        for name, html in self.site_pages().items():
            with self.subTest(page=name):
                self.assertNotIn("og-image.png", self.head(html))

    def test_no_page_hard_codes_the_retired_domain(self):
        for name, html in self.all_rendered().items():
            with self.subTest(page=name):
                self.assertNotIn("chinamilwatch.org", html)

    def test_the_series_pages_offer_a_skip_link(self):
        for name, html in self.all_rendered().items():
            with self.subTest(page=name):
                self.assertIn('href="#', html)
                self.assertRegex(html, r'class="[^"]*skip')


class TestHistoricalEditionIdentityIsPreserved(WeeklyRenderCase):
    """
    The inverse guard, and the more important one. Editions 1-13 were really
    published under the predecessor's name; a test suite that made them
    disappear would be falsifying a publication record.
    """

    def historical(self):
        return {d: p for d, p in self.posts.items()
                if p["issue"] and p["issue"] <= LAST_HISTORICAL_ISSUE}

    def test_there_are_historical_editions_to_protect(self):
        self.assertGreater(len(self.historical()), 0)

    def test_every_historical_edition_keeps_its_publisher(self):
        for date, post in self.historical().items():
            with self.subTest(edition=date, issue=post["issue"]):
                self.assertIn(PREDECESSOR, post["html"])

    def test_the_historical_byline_is_not_restated_under_the_new_name(self):
        for date, post in self.historical().items():
            with self.subTest(edition=date, issue=post["issue"]):
                title = re.search(r'class="author-block-title"[^>]*>([^<]+)<',
                                  post["html"])
                if title is None:
                    continue
                self.assertIn(PREDECESSOR, title.group(1))

    def test_the_edition_identity_module_still_draws_the_boundary(self):
        from core.edition_identity import (LAST_HISTORICAL_ISSUE as boundary,
                                           resolve_identity)
        self.assertEqual(boundary, LAST_HISTORICAL_ISSUE)
        historical = resolve_identity({"issue_number": boundary})
        current = resolve_identity({"issue_number": boundary + 1})
        self.assertEqual(historical["publication"], PREDECESSOR)
        self.assertEqual(current["publication"], CURRENT)


if __name__ == "__main__":
    unittest.main()
