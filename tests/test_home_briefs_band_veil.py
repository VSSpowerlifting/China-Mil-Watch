"""
The Briefs-band Signal Veil, held to what it promised.

The home page's "Latest analysis" band is Night Desk ground with a 46rem
column on it; the veil is a pure-gradient atmosphere painted into the band's
empty right side (`site/preview/styles.css`, "BRIEFS-BAND SIGNAL VEIL"). It may
never become a layout, a raster, or a thing that gets between a reader and the
type. Those are the properties asserted here:

  * it is two pseudo-elements and nothing else: no template change, no
    `url()`, no `<svg>` (the home band must still draw no plate);
  * it is inert, behind the content, and inside the band's own box, so it
    cannot overflow the page, cover a link, or take a click;
  * from 720px it exists in full and below that it is the quiet corner (no
    mesh layer); print and forced colours drop it;
  * every text run in the band still clears WCAG AA at the pixels its glyphs
    actually cover, at the widths where the veil is strongest and weakest.
    The measurement is the Ocean Signal Veil's own (glyph-pixel sampling, see
    `tests/test_homepage_veil_contract.py`), reused rather than reinvented.

Offline. Serves a temporary build over loopback; never `output/`.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests import test_homepage_veil_contract as contract         # noqa: E402
from tests.test_homepage_veil_contract import (                   # noqa: E402
    AA_BODY, AA_LARGE, CSS, VeilCase,
)

BAND = '.band[aria-labelledby="analysis"]'


def veil_css() -> str:
    css = CSS.read_text(encoding="utf-8")
    start = css.rindex("/*", 0, css.index("BRIEFS-BAND SIGNAL VEIL"))
    block = css[start:css.index(".issue-ledger--briefs", start)]
    return re.sub(r"/\*.*?\*/", "", block, flags=re.S)


class TestTheVeilIsOnlyGradientsOnPseudoElements(unittest.TestCase):

    def test_it_paints_no_image_and_selects_only_the_home_band(self):
        block = veil_css()
        self.assertNotIn("url(", block, "the veil must stay pure gradients")
        for selector in re.findall(r"^([^{}@\n][^{}]*)\{", block, flags=re.M):
            for part in selector.split(","):
                with self.subTest(selector=part.strip()):
                    self.assertTrue(part.strip().startswith(BAND))

    def test_it_is_inert_and_behind_the_content(self):
        block = veil_css()
        self.assertIn("pointer-events: none", block)
        self.assertIn("z-index: -1", block)
        self.assertIn("isolation: isolate", block)

    def test_print_and_forced_colours_drop_it(self):
        block = veil_css()
        self.assertRegex(block, r"@media print, \(forced-colors: active\)"
                                r"\s*\{[^}]*display: none")


class TestTheBandVeilInTheBrowser(VeilCase):
    """One build serves every browser check; each is its own method."""

    WIDTHS = (375, 390, 430, 719, 720, 768, 900, 1024, 1280, 1440)

    def band_state(self, page):
        return page.evaluate("""() => {
          const band = document.querySelector('.band[aria-labelledby="analysis"]');
          const box = band.getBoundingClientRect();
          const read = pseudo => {
            const cs = getComputedStyle(band, pseudo);
            return {display: cs.display, events: cs.pointerEvents,
                    z: cs.zIndex, position: cs.position,
                    width: parseFloat(cs.width)};
          };
          return {
            scroll: document.documentElement.scrollWidth,
            inner: window.innerWidth,
            band: box.width,
            before: read('::before'), after: read('::after'),
            svgs: band.querySelectorAll('svg').length,
          };
        }""")

    def test_no_overflow_always_inert_and_inside_the_band(self):
        for width in self.WIDTHS:
            context = self.browser.new_context(
                viewport={"width": width, "height": 900})
            page = context.new_page()
            try:
                page.goto(self.url, wait_until="load")
                state = self.band_state(page)
                with self.subTest(width=width):
                    self.assertLessEqual(state["scroll"], state["inner"],
                                         "the page scrolls sideways")
                    self.assertEqual(state["svgs"], 0)
                    for layer in ("before", "after"):
                        if state[layer]["display"] == "none":
                            continue
                        self.assertEqual(state[layer]["events"], "none")
                        self.assertEqual(state[layer]["z"], "-1")
                        self.assertEqual(state[layer]["position"], "absolute")
                        self.assertLessEqual(state[layer]["width"],
                                             state["band"] + 0.5)
            finally:
                context.close()

    def test_the_full_veil_starts_at_720_and_the_mesh_goes_below_it(self):
        for width, mesh in ((719, False), (720, True), (375, False),
                            (1440, True)):
            context = self.browser.new_context(
                viewport={"width": width, "height": 900})
            page = context.new_page()
            try:
                page.goto(self.url, wait_until="load")
                state = self.band_state(page)
                with self.subTest(width=width):
                    self.assertEqual(state["after"]["display"] != "none", mesh)
                    self.assertNotEqual(state["before"]["display"], "none")
            finally:
                context.close()

    def test_the_cta_and_the_section_link_are_still_what_is_under_the_pointer(self):
        for width in self.WIDTHS:
            context = self.browser.new_context(
                viewport={"width": width, "height": 900})
            page = context.new_page()
            try:
                page.goto(self.url, wait_until="load")
                page.evaluate(
                    "() => document.documentElement.classList.add('no-anim')")
                hit = page.evaluate("""() => {
                  const band = document.querySelector('.band[aria-labelledby="analysis"]');
                  return ['.section-more a', '.btn--primary'].map(s => {
                    const el = band.querySelector(s);
                    el.scrollIntoView({block: 'center'});
                    const r = el.getBoundingClientRect();
                    const top = document.elementFromPoint(
                      r.x + r.width / 2, r.y + r.height / 2);
                    return top === el || el.contains(top);
                  });
                }""")
                with self.subTest(width=width):
                    self.assertEqual(hit, [True, True])
            finally:
                context.close()


    # --- text over the veil, measured at the glyphs --------------------------

    _measured = contract.TestTextOverTheVeilIsMeasuredAtItsGlyphs
    glyph_contrast = _measured.glyph_contrast
    MIN_GLYPH_PIXELS = _measured.MIN_GLYPH_PIXELS

    RUNS = {
        BAND + " .section-more a": AA_BODY,
        BAND + " .section-kicker": AA_BODY,
        BAND + " .briefs-label": AA_BODY,
        BAND + " .feature--briefs h3 a": AA_LARGE,
        BAND + " .feature--briefs .dek": AA_BODY,
        BAND + " .feature--briefs .byline": AA_BODY,
        BAND + " .feature--briefs .legacy-note": AA_BODY,
    }

    #: `.byline` and `.briefs-label` have no measure of their own and the byline
    #: lists the lead's desks, so a lead with several desks runs toward the
    #: column's 46rem, over the veil's left edge. The veil starts 34rem in; this
    #: is the stress that proves it does not matter.
    LONG = {
        BAND + " .briefs-label":
            "Indo-Pacific Record Briefs, No. 14 · week ending 15 August 2026"
            " · China Desk, Singapore Desk and Japan Desk",
        BAND + " .feature--briefs .byline":
            "Benjamin Yang, Creator and Editor · China Desk, Singapore Desk,"
            " Japan Desk and Taiwan Desk",
    }

    def measure(self, width, long_text=False):
        context = self.browser.new_context(
            viewport={"width": width, "height": 900}, device_scale_factor=2)
        page = context.new_page()
        try:
            page.goto(self.url, wait_until="networkidle")
            page.evaluate(
                "() => document.documentElement.classList.add('no-anim')")
            if long_text:
                for selector, text in self.LONG.items():
                    page.evaluate(
                        "([s, t]) => { document.querySelector(s)"
                        ".textContent = t; }", [selector, text])
            for selector, floor in sorted(self.RUNS.items()):
                if long_text and selector not in self.LONG:
                    continue
                page.evaluate(
                    "s => document.querySelector(s)"
                    ".scrollIntoView({block: 'center'})", selector)
                page.wait_for_timeout(80)
                result = self.glyph_contrast(page, selector)
                with self.subTest(width=width, run=selector, long=long_text):
                    if result is None:
                        self.skipTest("%s absent at %d (the band's "
                                      "in-development state)"
                                      % (selector, width))
                    self.assertGreaterEqual(
                        result["pixels"], self.MIN_GLYPH_PIXELS,
                        "%s: the probe found no glyphs" % selector)
                    self.assertGreaterEqual(
                        result["worst"], floor,
                        "%s at %d measures %.2f:1 over the veil "
                        "(floor %.1f)" % (selector, width,
                                          result["worst"], floor))
        finally:
            context.close()

    def test_every_run_clears_its_floor_at_its_glyphs(self):
        for width in self.WIDTHS:
            self.measure(width)

    def test_a_long_byline_and_label_still_clear_it_where_the_veil_reaches_furthest(self):
        for width in (720, 768, 1024, 1280):
            self.measure(width, long_text=True)


if __name__ == "__main__":
    unittest.main()
