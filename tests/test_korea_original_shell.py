"""
A registered Korean original is an ordinary page of the publication.

On 2026-10-16 the first owner-released Korean original reached main as a bare
HTML document: no masthead, no skip link, no icon set, its own description and
a hand-written canonical. Sixteen site-wide identity, indexability and chrome
tests failed on that one page, and because the daily workflow runs the offline
suite before it collects, collection stopped.

Nothing in the owner rulings exempts original-text pages from the shared shell
(DECISION_LOG 2026-10-09, "One IPR article experience"), so the page now
renders through `korea-original.html` over `base.html`. What these tests pin is
the seam: the shell owns the frame, the registry module owns the escaped body,
and the body reaches the built page byte-for-byte.
"""
import html
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as gp                                    # noqa: E402
from core.korea_published_originals import (                     # noqa: E402
    original_page_title, read_release_index, render_original_body,
)

ORIGIN = "https://indopacificrecord.org"


class BuiltOriginals(unittest.TestCase):
    origin = None

    @classmethod
    def setUpClass(cls):
        if not gp.TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.rows = read_release_index()
        if not cls.rows:
            raise unittest.SkipTest("no Korean original is registered")
        cls.tmp = Path(tempfile.mkdtemp(prefix="korea-shell-"))
        gp.build(cls.tmp, gp.PUBLIC_TITLE, gp.TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB),
                 legacy_routes=True, site_origin=cls.origin)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, row):
        return (self.tmp / row["route"]).read_text(encoding="utf-8")


class TestTheShellFramesTheRegisteredBody(BuiltOriginals):
    origin = ORIGIN

    def test_every_registered_original_is_written_and_nothing_else(self):
        built = {p.relative_to(self.tmp).as_posix()
                 for p in (self.tmp / "korea-originals").glob("*")}
        self.assertEqual(built, {row["route"] for row in self.rows})

    def test_the_escaped_body_appears_exactly_once(self):
        for row in self.rows:
            with self.subTest(route=row["route"]):
                self.assertEqual(
                    self.page(row).count(render_original_body(row)), 1)

    def test_the_korean_text_is_the_registered_text(self):
        for row in self.rows:
            pre = re.search(r'<pre lang="ko"[^>]*>(.*?)</pre>',
                            self.page(row), re.S)
            with self.subTest(route=row["route"]):
                self.assertIsNotNone(pre)
                self.assertEqual(html.unescape(pre.group(1)),
                                 row["text_original"])
                self.assertIn(row["original_text_sha256"], self.page(row))

    def test_the_page_carries_the_shared_shell(self):
        for row in self.rows:
            page = self.page(row)
            with self.subTest(route=row["route"]):
                self.assertIn('<html lang="en"', page)
                self.assertIn('class="skip" href="#main"', page)
                self.assertIn('<header class="masthead">', page)
                self.assertIn('<footer class="site">', page)
                self.assertEqual(page.count("<h1"), 1)
                self.assertIn("<title>%s — %s</title>"
                              % (original_page_title(row), gp.PUBLIC_TITLE),
                              page)

    def test_the_canonical_is_the_page_s_own_public_address(self):
        for row in self.rows:
            expected = ORIGIN + "/" + row["route"]
            page = self.page(row)
            with self.subTest(route=row["route"]):
                self.assertEqual(page.count('rel="canonical"'), 1)
                self.assertIn('<link rel="canonical" href="%s">' % expected,
                              page)
                self.assertIn('<meta property="og:url" content="%s">'
                              % expected, page)
                self.assertNotIn("noindex", page)

    def test_the_release_workflow_s_own_page_guards_still_hold(self):
        """`korea_standing_original_text_production.yml` refuses a page with a
        script or an HWPX reference; the shell must not introduce either."""
        for row in self.rows:
            page = self.page(row)
            with self.subTest(route=row["route"]):
                self.assertNotIn("<script", page)
                self.assertNotIn(".hwpx", page)


class TestWithoutAnOriginTheOriginalIsNoindex(BuiltOriginals):
    origin = None

    def test_the_candidate_page_is_noindex_and_has_no_canonical(self):
        for row in self.rows:
            page = self.page(row)
            with self.subTest(route=row["route"]):
                self.assertIn(gp.NOINDEX_TAG, page)
                self.assertNotIn('rel="canonical"', page)


if __name__ == "__main__":
    unittest.main()
