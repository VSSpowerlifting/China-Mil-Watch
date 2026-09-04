"""
Identity asset contract for the Indo-Pacific Record.

The audit of 2026-09-04 found the publication's identity wrong or missing on
every surface it owns: a generic document glyph in the masthead of 3,950
pages, no Open Graph metadata anywhere on the record site, and a 1.0 MB
predecessor eagle still serving as the icon for the weekly series. This module
is the guard against each of those returning.

Three rules shape what is asserted here.

The canonical mark is a fixed input, not an output. `ipr-compass-logo.png` is
owner-supplied and its bytes are pinned by digest. Everything else under
`site/assets/identity/` is a derivative produced from it by
`scripts/build_identity_assets.py`, and a derivative that has drifted from its
recorded dimensions is a build nobody can reproduce.

Size is a correctness property, not a preference. The audit measured the
canonical artwork's ring strokes at 4 px against a 500 px field, which is
below one device pixel at every masthead size. The floor that follows — 48 CSS
px for the canonical mark, a separate simplified derivative below 32 px — is
enforced here so a future change cannot quietly reintroduce a mark that
renders as a grey smudge.

The predecessor is forbidden in current chrome and required in the archive.
That directional rule is `test_indo_pacific_identity`'s and is not restated;
what this module adds is the asset half of it — no page of current Indo-Pacific
Record chrome may reference the predecessor's eagle or its retired homepage
screenshot, whatever the surrounding prose says.

Nothing here builds production or touches the tracked database.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import struct
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
IDENTITY_DIR = REPO_ROOT / "site" / "assets" / "identity"

TITLE = "Indo-Pacific Record"
SITE_ORIGIN = "https://indopacificrecord.org"
RETIRED_DOMAIN = "chinamilwatch.org"

#: The owner-supplied mark. Pinned by digest because every other asset in this
#: directory is derived from it: if this changes, the derivatives are stale and
#: the size evidence in the audit no longer describes what ships.
CANONICAL_NAME = "ipr-compass-logo.png"
CANONICAL_SHA256 = (
    "7e3f3b606c5d7dcb0bda82d84f888ce2afd903b8229a621b72d66e670645762f")

#: Derivative -> (width, height). Names are explicit on purpose: a reader who
#: finds one of these in a build directory should not have to open it to learn
#: what it is for.
DERIVATIVES = {
    "ipr-compass-masthead-112.png": (112, 112),
    "ipr-compass-icon-16.png": (16, 16),
    "ipr-compass-icon-32.png": (32, 32),
    "ipr-compass-touch-180.png": (180, 180),
    "ipr-social-card-1200x630.png": (1200, 630),
}

#: The simplified mark, authorised because the canonical artwork's 4 px rings
#: are sub-pixel below 32 px. It is a separate file and never overwrites the
#: canonical source.
SMALL_MARK = "ipr-compass-mark-small.svg"

#: Predecessor assets. Still carried in `output/` for the pages that have not
#: been re-rendered yet, and therefore still resolvable — but never referenced
#: by current Indo-Pacific Record chrome.
LEGACY_ASSETS = ("logo-icon.png", "logo-wordmark.png", "og-image.png")

#: A favicon is fetched on every cold page load. The predecessor shipped a
#: 1,028,724-byte PNG as one; this is the ceiling that forbids a repeat.
ICON_BYTE_CEILING = 32 * 1024
SOCIAL_CARD_BYTE_CEILING = 300 * 1024


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    """Width and height from the IHDR chunk, without a decode dependency."""
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s is not a PNG" % path.name)
    return struct.unpack(">II", raw[16:24])


class TestTheCanonicalMarkIsUnaltered(unittest.TestCase):
    """
    The canonical file is an input. These assertions are about preservation,
    not about design: a derivative may be regenerated at will, but the source
    it was derived from has one permitted set of bytes.
    """

    def test_the_canonical_mark_is_committed(self):
        self.assertTrue((IDENTITY_DIR / CANONICAL_NAME).is_file(),
                        "canonical mark missing from site/assets/identity/")

    def test_the_canonical_mark_matches_the_owner_supplied_digest(self):
        self.assertEqual(sha256_of(IDENTITY_DIR / CANONICAL_NAME),
                         CANONICAL_SHA256)

    def test_the_canonical_mark_keeps_its_supplied_geometry(self):
        self.assertEqual(png_size(IDENTITY_DIR / CANONICAL_NAME), (500, 500))

    def test_the_canonical_mark_is_documented_as_canonical(self):
        """
        A directory of eight PNGs with no statement of which one is the source
        is a directory in which the wrong file eventually gets edited.
        """
        doc = (IDENTITY_DIR / "IDENTITY_ASSETS.md").read_text(encoding="utf-8")
        self.assertIn(CANONICAL_NAME, doc)
        self.assertIn(CANONICAL_SHA256, doc)
        self.assertRegex(doc, r"(?i)canonical")
        for name in DERIVATIVES:
            with self.subTest(asset=name):
                self.assertIn(name, doc)


class TestTheDerivativesAreTruthful(unittest.TestCase):

    def test_every_derivative_exists_at_its_recorded_size(self):
        for name, expected in DERIVATIVES.items():
            with self.subTest(asset=name):
                path = IDENTITY_DIR / name
                self.assertTrue(path.is_file(), "%s missing" % name)
                self.assertEqual(png_size(path), expected)

    def test_the_simplified_mark_is_a_separate_file(self):
        self.assertTrue((IDENTITY_DIR / SMALL_MARK).is_file())
        self.assertNotEqual(sha256_of(IDENTITY_DIR / SMALL_MARK),
                            sha256_of(IDENTITY_DIR / CANONICAL_NAME))

    def test_the_simplified_mark_keeps_the_brand_colours(self):
        """
        Recognisably the same compass: the derivative may drop the second ring
        and the diagonal ticks, but not the palette the canonical mark is
        drawn in.
        """
        svg = (IDENTITY_DIR / SMALL_MARK).read_text(encoding="utf-8").upper()
        for colour in ("#4DAD99", "#255E7A"):
            with self.subTest(colour=colour):
                self.assertIn(colour, svg)

    def test_no_icon_is_large_enough_to_be_a_page_weight_problem(self):
        for name in ("ipr-compass-icon-16.png", "ipr-compass-icon-32.png",
                     "ipr-compass-touch-180.png", SMALL_MARK):
            with self.subTest(asset=name):
                size = (IDENTITY_DIR / name).stat().st_size
                self.assertLess(size, ICON_BYTE_CEILING,
                                "%s is %d bytes" % (name, size))

    def test_the_social_card_stays_inside_the_documented_budget(self):
        size = (IDENTITY_DIR / "ipr-social-card-1200x630.png").stat().st_size
        self.assertLess(size, SOCIAL_CARD_BYTE_CEILING)

    def test_the_builder_is_committed_so_derivatives_can_be_reproduced(self):
        self.assertTrue(
            (REPO_ROOT / "scripts" / "build_identity_assets.py").is_file())


class IdentityBuildCase(unittest.TestCase):
    """One candidate build, with an origin, so metadata can be checked."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="identity-assets-"))
        cls.out = cls.tmp / "build"
        gp.build(cls.out, TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB),
                 site_origin=SITE_ORIGIN)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, name: str) -> str:
        return (self.out / name).read_text(encoding="utf-8")

    def pages(self):
        """Every rendered page. Used only by aggregate checks."""
        return {str(p.relative_to(self.out)): p.read_text(encoding="utf-8")
                for p in sorted(self.out.rglob("*.html"))}

    def sample(self):
        """
        One page per template shape, plus one from each nested namespace.

        The build emits 5,409 pages from sixteen templates. Asserting a head
        or masthead property on every one of them turns a single regression
        into thousands of identical subTest failures, which is noise a
        reviewer has to page through rather than signal. The aggregate checks
        below still read every page; this is for the per-page assertions.
        """
        names = ["index.html", "archive.html", "coverage.html", "desks.html",
                 "china.html", "analysis.html", "methodology.html",
                 "about.html", "sources.html", "corpus.html",
                 "corpus-guide.html", "pla-watch.html"]
        chosen = {n: (self.out / n).read_text(encoding="utf-8")
                  for n in names if (self.out / n).is_file()}
        for folder in ("record", "article", "source"):
            first = next(iter(sorted((self.out / folder).glob("*.html"))), None)
            if first is not None:
                chosen[str(first.relative_to(self.out))] = \
                    first.read_text(encoding="utf-8")
        week = next(iter(sorted(self.out.glob("week-*.html"))), None)
        if week is not None:
            chosen[week.name] = week.read_text(encoding="utf-8")
        return chosen

    @staticmethod
    def head(html: str) -> str:
        return html.split("</head>", 1)[0]

    @staticmethod
    def masthead(html: str) -> str:
        return html.split("<header", 1)[1].split("</header>", 1)[0]


class TestTheBuildShipsTheIdentityAssets(IdentityBuildCase):

    def test_the_icon_routes_are_written(self):
        for route in ("mark.svg", "icon-16.png", "icon-32.png",
                      "apple-touch-icon.png", "masthead-mark.png",
                      "social-card.png"):
            with self.subTest(route=route):
                self.assertTrue((self.out / route).is_file(),
                                "%s not emitted by the build" % route)

    def test_the_emitted_masthead_asset_is_the_canonical_compass(self):
        """
        Not the 500 px source — a delivery derivative — but derived from it,
        so the two cannot drift.
        """
        self.assertEqual(
            sha256_of(self.out / "masthead-mark.png"),
            sha256_of(IDENTITY_DIR / "ipr-compass-masthead-112.png"))

    def test_the_emitted_favicon_is_the_simplified_mark(self):
        self.assertEqual(sha256_of(self.out / "mark.svg"),
                         sha256_of(IDENTITY_DIR / SMALL_MARK))

    def test_the_build_carries_no_predecessor_asset(self):
        for name in LEGACY_ASSETS:
            with self.subTest(asset=name):
                self.assertFalse((self.out / name).exists(),
                                 "%s written into a current build" % name)


class TestTheMastheadCarriesTheCompass(IdentityBuildCase):

    def test_every_masthead_shows_the_compass_mark(self):
        for name, html in self.sample().items():
            with self.subTest(page=name):
                mast = self.masthead(html)
                self.assertRegex(
                    mast,
                    r'<img[^>]+class="brand-mark"[^>]+'
                    r'src="(\.\./)?masthead-mark\.png"')

    def test_the_generic_document_glyph_is_gone(self):
        """
        The retired mark was three ruled paths in a rounded rect. Its class
        names are the reliable fingerprint; the geometry could be re-typed.
        """
        offenders = [n for n, h in self.pages().items()
                     if any(t in h for t in
                            ("mark-field", "mark-rules", "mark-tide"))]
        self.assertEqual(offenders[:5], [])

    def test_the_mark_is_decorative_and_the_wordmark_is_the_name(self):
        """
        Unchanged in substance from the SVG it replaces: a screen reader
        announces the publication once, from the wordmark, not twice.
        """
        mast = self.masthead(self.page("index.html"))
        img = re.search(r'<img[^>]+class="brand-mark"[^>]*>', mast).group(0)
        self.assertIn('alt=""', img)
        self.assertIn('aria-hidden="true"', img)

    def test_the_home_link_still_has_an_accessible_name(self):
        for name, html in self.sample().items():
            with self.subTest(page=name):
                brand = re.search(r'<a class="brand"[\s\S]*?</a>',
                                  self.masthead(html)).group(0)
                self.assertIn(TITLE, brand)

    def test_the_mark_is_delivered_with_explicit_dimensions(self):
        """No image on this site may cause layout shift."""
        for name, html in self.sample().items():
            with self.subTest(page=name):
                img = re.search(r'<img[^>]+class="brand-mark"[^>]*>',
                                self.masthead(html)).group(0)
                self.assertRegex(img, r'\bwidth="\d+"')
                self.assertRegex(img, r'\bheight="\d+"')

    def test_the_mark_is_never_rendered_below_its_measured_floor(self):
        """
        The audit measured 48 CSS px as the size below which the compass stops
        reading as a compass. The stylesheet may not go under it.
        """
        css = (REPO_ROOT / "site" / "preview" / "styles.css").read_text("utf-8")
        block = re.findall(r"\.brand-mark\s*\{[^}]*\}", css)
        self.assertTrue(block, ".brand-mark rule not found")
        for rule in block:
            for value in re.findall(r"(?:width|height)\s*:\s*([\d.]+)px", rule):
                with self.subTest(rule=rule.strip()[:60]):
                    self.assertGreaterEqual(float(value), 48.0)


class TestTheLegacyRollbackMastheadIsUntouched(unittest.TestCase):
    """
    `site/templates/base.html` belongs to the rollback renderer. Its China Mil
    Watch identity is deliberate historical behaviour, and this tranche has no
    business in it. The guard is directional: it asserts the legacy template
    still names the predecessor, so a well-meaning sweep cannot "fix" it.
    """

    def setUp(self):
        self.legacy = (REPO_ROOT / "site" / "templates" / "base.html"
                       ).read_text(encoding="utf-8")

    def test_the_rollback_masthead_still_carries_its_own_identity(self):
        self.assertIn("China Mil Watch", self.legacy)

    def test_the_rollback_masthead_keeps_its_own_icon_reference(self):
        self.assertIn("logo-icon.png", self.legacy)

    def test_the_rollback_renderer_is_not_the_production_renderer(self):
        """
        Guards the audit's S9 finding: the module docstring once said the
        default was legacy while the constant said otherwise.
        """
        render = (REPO_ROOT / "site" / "render.py").read_text(encoding="utf-8")
        self.assertRegex(render,
                         r"DEFAULT_SITE_MODE\s*=\s*INDO_PACIFIC_RECORD")


class TestTheCurrentMetadataIdentity(IdentityBuildCase):

    def test_every_page_declares_the_icon_set(self):
        for name, html in self.pages().items():
            head = self.head(html)
            up = "../" if "/" in name else ""
            with self.subTest(page=name):
                self.assertIn(
                    '<link rel="icon" type="image/svg+xml" href="%smark.svg">'
                    % up, head)
                self.assertIn(
                    '<link rel="apple-touch-icon" href="%sapple-touch-icon.png">'
                    % up, head)

    def test_every_page_declares_a_theme_colour_matching_the_masthead(self):
        for name, html in self.sample().items():
            with self.subTest(page=name):
                self.assertRegex(
                    self.head(html),
                    r'<meta name="theme-color" content="#0A1A22">')

    def test_every_page_carries_open_graph_identity(self):
        for name, html in self.sample().items():
            head = self.head(html)
            with self.subTest(page=name):
                for prop in ("og:title", "og:description", "og:image",
                             "og:url", "og:type", "og:site_name"):
                    self.assertIn('property="%s"' % prop, head, prop)

    def test_every_page_carries_a_twitter_card(self):
        for name, html in self.sample().items():
            head = self.head(html)
            with self.subTest(page=name):
                self.assertIn('name="twitter:card"', head)
                self.assertIn("summary_large_image", head)

    def test_social_metadata_uses_absolute_current_domain_urls(self):
        for name, html in self.sample().items():
            head = self.head(html)
            with self.subTest(page=name):
                for prop in ("og:image", "og:url"):
                    value = re.search(
                        r'property="%s"\s+content="([^"]+)"' % prop,
                        head).group(1)
                    self.assertTrue(value.startswith(SITE_ORIGIN + "/"),
                                    "%s = %s" % (prop, value))

    def test_no_page_hard_codes_the_retired_domain(self):
        offenders = [n for n, h in self.pages().items()
                     if RETIRED_DOMAIN in h]
        self.assertEqual(offenders[:5], [])

    def test_the_og_url_is_the_page_and_matches_its_canonical(self):
        """
        A social card that points every page at the home page is worse than
        no card: it makes a shared record page unciteable.
        """
        for name, html in self.pages().items():
            head = self.head(html)
            canonical = re.search(r'<link rel="canonical" href="([^"]+)"', head)
            if not canonical:
                continue
            og_url = re.search(r'property="og:url"\s+content="([^"]+)"',
                               head).group(1)
            with self.subTest(page=name):
                self.assertEqual(og_url, canonical.group(1))

    def test_page_descriptions_are_governed_not_invented(self):
        """
        The renderer has no per-record description, so it uses the tagline
        rather than synthesising prose about a document it has not read.
        """
        for name, html in self.pages().items():
            head = self.head(html)
            meta = re.search(r'<meta name="description" content="([^"]+)"',
                             head).group(1)
            og = re.search(r'property="og:description"\s+content="([^"]+)"',
                           head).group(1)
            with self.subTest(page=name):
                self.assertEqual(meta, og)


class TestNestedRoutesResolve(IdentityBuildCase):
    """
    Record, article and source pages sit one directory down. Every asset
    reference on them is relative, so a missing `../` is a broken icon on
    5,306 of 5,409 pages and on none of the ones a spot check would open.
    """

    def nested_pages(self):
        return {n: h for n, h in self.pages().items() if "/" in n}

    def nested_sample(self):
        return {n: h for n, h in self.sample().items() if "/" in n}

    def test_there_are_nested_pages_to_check(self):
        self.assertGreater(len(self.nested_pages()), 0)

    def test_every_local_asset_reference_resolves_on_disk(self):
        pattern = re.compile(r'(?:href|src)="([^"#?]+)"')
        missing = []
        for name, html in self.sample().items():
            base = (self.out / name).parent
            for ref in pattern.findall(self.head(html) +
                                       self.masthead(html)):
                if ref.startswith(("http://", "https://", "mailto:", "data:",
                                   "//", "#")):
                    continue
                if not (base / ref).resolve().is_file():
                    missing.append("%s -> %s" % (name, ref))
        self.assertEqual(missing[:10], [])

    def test_nested_icon_references_climb_exactly_one_level(self):
        for name, html in self.nested_sample().items():
            with self.subTest(page=name):
                self.assertIn('href="../mark.svg"', self.head(html))
                self.assertIn('src="../masthead-mark.png"',
                              self.masthead(html))


class TestTheCollectionStateRail(IdentityBuildCase):
    """
    Direction A's rail, brought into the Dossier masthead. It reports only
    figures the template already holds, and it keeps the distinction the
    freshness dates exist to make: collection and analysis are separate
    states with separate dates.
    """

    def test_the_rail_states_the_corpus_scale(self):
        html = self.page("index.html")
        rail = html.split('class="freshness-bar', 1)[1].split("</dl>", 1)[0]
        self.assertIn("Records held", rail)
        self.assertIn("Of those, analyzed", rail)

    def test_collection_and_analysis_stay_distinguishable(self):
        for name, html in self.pages().items():
            if 'class="freshness-bar' not in html:
                continue
            with self.subTest(page=name):
                self.assertIn("Records last collected", html)
                self.assertIn("Analysis last produced", html)

    def test_the_rail_uses_description_list_markup(self):
        html = self.page("index.html")
        rail = html.split('class="freshness-bar', 1)[1].split("</dl>", 1)[0]
        self.assertIn("<dt>", rail)
        self.assertIn("<dd>", rail)

    def test_the_rail_reports_no_figure_the_corpus_cannot_support(self):
        """
        A zero here would read as "collection failed". The renderer prints a
        real count or says the value is not measured; it never prints 0 as a
        stand-in for unknown.
        """
        html = self.page("index.html")
        rail = html.split('class="freshness-bar', 1)[1].split("</dl>", 1)[0]
        self.assertNotRegex(rail, r"<dd>\s*0\s*</dd>")


class TestNoRegressionInTheQualityFloor(IdentityBuildCase):
    """
    The audit measured these clean. A tranche that fixes identity and breaks
    one of them has not made the site better.
    """

    def test_every_image_declares_width_and_height(self):
        offenders = []
        for name, html in self.pages().items():
            for img in re.findall(r"<img[^>]*>", html):
                if not (re.search(r'\bwidth="\d+"', img)
                        and re.search(r'\bheight="\d+"', img)):
                    offenders.append("%s: %s" % (name, img[:70]))
        self.assertEqual(offenders[:5], [])

    def test_every_image_declares_alt_text(self):
        offenders = [
            "%s: %s" % (name, img[:70])
            for name, html in self.pages().items()
            for img in re.findall(r"<img[^>]*>", html)
            if "alt=" not in img
        ]
        self.assertEqual(offenders[:5], [])

    def test_the_skip_link_survives(self):
        offenders = [n for n, h in self.pages().items()
                     if 'href="#main"' not in h]
        self.assertEqual(offenders[:5], [])

    def test_focus_visible_styling_survives(self):
        css = (REPO_ROOT / "site" / "preview" / "styles.css").read_text("utf-8")
        self.assertIn(":focus-visible", css)
        self.assertNotRegex(css, r"outline:\s*(none|0)\s*;")

    def test_reduced_motion_handling_survives(self):
        css = (REPO_ROOT / "site" / "preview" / "styles.css").read_text("utf-8")
        self.assertIn("prefers-reduced-motion", css)

    def test_no_transition_shorthand_animates_everything(self):
        css = (REPO_ROOT / "site" / "preview" / "styles.css").read_text("utf-8")
        self.assertNotRegex(css, r"transition:\s*all\b")

    def test_the_mobile_disclosure_navigation_survives(self):
        html = self.page("index.html")
        self.assertIn("nav-toggle", html)
        self.assertIn("<summary", html)


class TestTheSimplifiedMarkStaysWithinDoctrine(IdentityBuildCase):
    """
    `test_indo_pacific_identity` bans a list of military motifs from the
    shipped mark by scanning its source text. A compass rose passes that scan
    only if it is described in the vocabulary of navigation.
    """

    BANNED = ("crosshair", "reticle", "radar", "wing", "insignia", "sword",
              "shield", "star")

    def test_the_shipped_mark_names_no_military_motif(self):
        svg = (self.out / "mark.svg").read_text(encoding="utf-8").lower()
        for motif in self.BANNED:
            with self.subTest(motif=motif):
                self.assertNotIn(motif, svg)

    def test_the_shipped_mark_carries_its_own_accessible_name(self):
        svg = (self.out / "mark.svg").read_text(encoding="utf-8")
        self.assertIn("<title>%s</title>" % TITLE, svg)


if __name__ == "__main__":
    unittest.main()
