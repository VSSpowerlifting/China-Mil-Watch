"""
Whether the built tree may be indexed, and what it tells crawlers.

Three things were missing from the Indo-Pacific Record candidate that the
legacy site has always shipped: `robots.txt`, `sitemap.xml`, and a canonical on
content pages. A fourth was present and would have been worse — `base.html`
puts `noindex, nofollow` on every page, which is correct for a preview and
catastrophic for a launch. Publishing that tree would have told every crawler
to ignore the entire publication.

The contract these tests pin is one switch, safe by default:

    no --site-origin  ->  candidate: noindex everywhere, no sitemap
    --site-origin X   ->  launch:    indexable, canonical to X, sitemap at X

You cannot get an indexable tree by forgetting a flag — only by naming where
the site will live. That matters because the domain is an owner decision that
has not been made, and inventing a placeholder would ship a real-looking URL.
"""
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

ORIGIN = "https://example.invalid"


def _build(tmp, origin=None):
    #: `.invalid` is reserved by RFC 2606 and can never resolve, so a test tree
    #: built under it cannot be mistaken for a publishable one. The build
    #: refuses such an origin unless asked explicitly — which is the point.
    return gp.build(Path(tmp), gp.PUBLIC_TITLE, gp.TRACKED_DB,
                    snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB),
                    legacy_routes=True, site_origin=origin,
                    allow_test_origin=True)


class BuiltTreeCase(unittest.TestCase):
    origin = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="idx-")
        cls.result = _build(cls.tmp, cls.origin)
        cls.root = Path(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def pages(self, stubs=False):
        for p in sorted(self.root.rglob("*.html")):
            is_stub = p.relative_to(self.root).as_posix().startswith("article/")
            if is_stub == stubs:
                yield p


class TestTheCandidateBuildRefusesToBeIndexed(BuiltTreeCase):
    origin = None

    def test_every_content_page_is_noindex(self):
        pages = list(self.pages())
        self.assertTrue(pages)
        for p in pages:
            with self.subTest(page=p.relative_to(self.root).as_posix()):
                self.assertIn('content="noindex', p.read_text(encoding="utf-8"))

    def test_no_sitemap_is_written(self):
        self.assertFalse((self.root / "sitemap.xml").exists(),
                         "a sitemap needs absolute URLs; without an origin one "
                         "could only be written by inventing a domain")
        self.assertEqual(self.result["sitemap_urls"], 0)

    def test_robots_txt_is_still_written(self):
        """Valid crawl directives do not need a domain; only the Sitemap line does."""
        robots = (self.root / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("User-agent: *", robots)
        self.assertNotIn("Sitemap:", robots)

    def test_the_result_reports_no_origin(self):
        self.assertIsNone(self.result["site_origin"])
        self.assertEqual(self.result["indexable_pages"], 0)

    def test_no_placeholder_domain_appears_anywhere(self):
        """The failure mode this guards is a fake domain shipping as a real URL."""
        for p in list(self.pages()) + [self.root / "robots.txt"]:
            text = p.read_text(encoding="utf-8")
            for fake in ("example.com", "example.org", "yourdomain",
                         "TODO", "PLACEHOLDER", "changeme"):
                with self.subTest(page=p.name, fake=fake):
                    self.assertNotIn(fake, text)


class TestSupplyingAnOriginProducesALaunchableTree(BuiltTreeCase):
    origin = ORIGIN

    def test_no_content_page_is_noindex_any_more(self):
        for p in self.pages():
            with self.subTest(page=p.relative_to(self.root).as_posix()):
                self.assertNotIn('content="noindex', p.read_text(encoding="utf-8"))

    def test_every_content_page_carries_a_canonical(self):
        for p in self.pages():
            with self.subTest(page=p.relative_to(self.root).as_posix()):
                self.assertIn('rel="canonical"', p.read_text(encoding="utf-8"))

    def test_each_canonical_matches_that_page_s_own_route(self):
        for p in self.pages():
            rel = p.relative_to(self.root).as_posix()
            expected = ORIGIN + "/" + gp.canonical_route(rel)
            found = re.search(r'<link rel="canonical" href="([^"]+)"',
                              p.read_text(encoding="utf-8"))
            with self.subTest(page=rel):
                self.assertIsNotNone(found)
                self.assertEqual(found.group(1), expected)

    def test_the_home_canonical_is_the_bare_origin(self):
        home = (self.root / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="%s/"' % ORIGIN, home)

    def test_robots_points_at_the_sitemap(self):
        robots = (self.root / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Sitemap: %s/sitemap.xml" % ORIGIN, robots)

    def test_the_sitemap_lists_every_content_page_and_the_root(self):
        sitemap = (self.root / "sitemap.xml").read_text(encoding="utf-8")
        locs = set(re.findall(r"<loc>([^<]+)</loc>", sitemap))
        expected = {ORIGIN + "/"}
        for p in self.pages():
            rel = p.relative_to(self.root).as_posix()
            expected.add(ORIGIN + "/" + gp.canonical_route(rel))
        self.assertEqual(locs, expected)

    def test_the_sitemap_lists_no_redirect_stub(self):
        """
        Listing a `noindex` redirect invites a crawler to index the redirect
        instead of the record it points at.
        """
        sitemap = (self.root / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("/article/", sitemap)

    def test_the_sitemap_is_well_formed(self):
        import xml.etree.ElementTree as ET
        ET.parse(self.root / "sitemap.xml")     # raises if malformed

    def test_the_redirect_stubs_stay_noindex(self):
        stubs = list(self.pages(stubs=True))
        self.assertTrue(stubs)
        for p in stubs:
            with self.subTest(stub=p.name):
                self.assertIn("noindex", p.read_text(encoding="utf-8"))

    def test_the_stub_canonical_still_points_at_its_record(self):
        stub = (self.root / "article" / "1000.html").read_text(encoding="utf-8")
        self.assertIn('rel="canonical" href="../record/1000.html"', stub)


class TestTheBuilderAndTheTemplateCannotDrift(unittest.TestCase):
    """
    The builder lifts `noindex` by string replacement. If `base.html` reworded
    the tag, the replacement would silently match nothing and every page would
    ship noindex on a real launch — the exact failure this work removed.
    """

    def test_the_template_emits_exactly_the_tag_the_builder_looks_for(self):
        template = (ROOT / "site" / "preview" / "templates"
                    / "base.html").read_text(encoding="utf-8")
        self.assertIn(gp.NOINDEX_TAG, template)

    def test_the_tag_appears_once_per_page(self):
        template = (ROOT / "site" / "preview" / "templates"
                    / "base.html").read_text(encoding="utf-8")
        self.assertEqual(template.count(gp.NOINDEX_TAG), 1)


if __name__ == "__main__":
    unittest.main()


class TestAnUnusableOriginStopsTheBuild(unittest.TestCase):
    """
    Every other part of the origin switch is permissive: omit it and you get a
    candidate. But a *supplied* origin is written into every canonical and every
    sitemap entry, where a malformed or stand-in value does not fail loudly — it
    ships, and the published site tells crawlers its canonical home is somewhere
    that does not exist. So supplying one fails closed.
    """

    def refuse(self, origin, **kw):
        with self.assertRaises(gp.UnusableSiteOrigin):
            gp.validate_site_origin(origin, **kw)

    def test_a_placeholder_host_is_refused(self):
        for host in ("https://example.com", "https://example.org",
                     "https://yourdomain.com", "https://localhost"):
            with self.subTest(host=host):
                self.refuse(host)

    def test_a_reserved_suffix_is_refused(self):
        for host in ("https://foo.invalid", "https://foo.test",
                     "https://foo.example", "https://foo.local"):
            with self.subTest(host=host):
                self.refuse(host)

    def test_a_non_http_scheme_is_refused(self):
        for origin in ("ftp://x.org", "file:///tmp", "x.org", "//x.org"):
            with self.subTest(origin=origin):
                self.refuse(origin)

    def test_a_host_without_a_dot_is_refused(self):
        self.refuse("https://nodot")

    def test_an_origin_carrying_a_path_or_query_is_refused(self):
        for origin in ("https://x.org/path", "https://x.org?a=1",
                       "https://x.org#f"):
            with self.subTest(origin=origin):
                self.refuse(origin)

    def test_empty_and_missing_origins_are_refused(self):
        for origin in ("", "   ", None):
            with self.subTest(origin=origin):
                self.refuse(origin)

    def test_a_real_looking_origin_is_accepted_and_normalised(self):
        self.assertEqual(
            gp.validate_site_origin("https://indopacificrecord.org/"),
            "https://indopacificrecord.org")

    def test_the_escape_hatch_is_explicit_and_never_implicit(self):
        """A reserved origin passes only when asked for by name."""
        self.refuse("https://foo.invalid")
        self.assertEqual(
            gp.validate_site_origin("https://foo.invalid",
                                    allow_test_origin=True),
            "https://foo.invalid")

    def test_the_build_itself_refuses_an_unusable_origin(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(gp.UnusableSiteOrigin):
                gp.build(Path(tmp), gp.PUBLIC_TITLE, gp.TRACKED_DB,
                         snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB),
                         site_origin="https://example.com")

    def test_omitting_the_origin_is_still_permitted(self):
        """The candidate path must not be made to require a domain."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result = gp.build(Path(tmp), gp.PUBLIC_TITLE, gp.TRACKED_DB,
                              snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB))
            self.assertIsNone(result["site_origin"])


class TestLegacyModeIsUntouched(unittest.TestCase):
    """
    The origin switch lives entirely in the Indo-Pacific Record renderer.
    Legacy renders through site/generator.py, which this work does not touch —
    and which is now the rollback path, so leaving it alone matters more after
    the launch than it did before.
    """

    def test_the_legacy_generator_is_not_modified_by_this_work(self):
        gen = (ROOT / "site" / "generator.py").read_text(encoding="utf-8")
        for name in ("site_origin", "allow_test_origin", "validate_site_origin"):
            with self.subTest(name=name):
                self.assertNotIn(name, gen)

    def test_the_default_site_mode_is_the_launched_mode(self):
        """
        Launched 2026-08-27. This pin held the switch shut while the candidate
        was dormant; it now holds it open, so that a careless revert of the one
        constant is a test failure rather than a silent unpublication.
        """
        render = (ROOT / "site" / "render.py").read_text(encoding="utf-8")
        self.assertIn("DEFAULT_SITE_MODE = INDO_PACIFIC_RECORD", render)
        self.assertNotIn("DEFAULT_SITE_MODE = LEGACY", render)

    def test_the_legacy_generator_still_writes_its_own_robots_and_sitemap(self):
        gen = (ROOT / "site" / "generator.py").read_text(encoding="utf-8")
        self.assertIn("_generate_robots_txt", gen)
        self.assertIn("_generate_sitemap_xml", gen)
