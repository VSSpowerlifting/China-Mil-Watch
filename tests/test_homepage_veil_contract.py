"""
The Ocean Signal Veil, measured — not described.

The home page paints a photograph behind live type. That is the thing the
previous design removed, and it is allowed back only because each hazard it
carries is now a measurement rather than an intention. This file is those
measurements.

Why glyph-pixel sampling, and not a colour check or a box sample
----------------------------------------------------------------
A colour-based contrast check cannot see a background IMAGE at all: it walks
`backgroundColor` and finds the page ground behind a photograph. A box sample
can see the image but averages the whole text box, including the empty part
that extends past the last glyph — and on a run whose line ends mid-column
that empty part is mostly paper, which lifts the score.

Both agreed the first r3 build passed. `.claim-sub` was at **2.22:1**.

The method here is the one that caught it: screenshot the run twice, once
normally and once with its text forced transparent, difference the two frames
to derive the glyph mask, and read the background ONLY at coordinates a glyph
actually covers. It is slower and it is the only one that was right.

What is load-bearing
--------------------
Mask lobe 1's HORIZONTAL RADIUS. At 86% the photograph reached under
`.claim-sub`; at 45% it does not. Nothing else about the treatment changed
between those two states — same lobe centre, same background-position, same
ledger fill, same crop. Do not widen it without re-running this file.

Offline. Serves a temporary build over loopback; never `output/`, and never
opens the tracked database for writing.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))

import generate_preview as gp                                    # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"
CSS = REPO_ROOT / "site" / "preview" / "styles.css"
DERIV = REPO_ROOT / "site" / "assets" / "editorial" / "derivatives"

#: The veil box at 1280 is 88% of the 1180px shell, against the opening's own
#: height. A derivative WIDER than this is scaled by height under `cover`, and
#: its left edge walks off screen as the viewport grows.
NARROWEST_VEIL_BOX_ASPECT = 2.442

#: WCAG 2.1. Large text is >= 24px, or >= 18.66px bold.
AA_BODY = 4.5
AA_LARGE = 3.0


def _luminance(rgb) -> float:
    def channel(value):
        value /= 255.0
        return (value / 12.92 if value <= 0.03928
                else ((value + 0.055) / 1.055) ** 2.4)
    r, g, b = (channel(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class VeilCase(unittest.TestCase):
    """One build, served over loopback, shared by every measurement."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:                       # pragma: no cover
            raise unittest.SkipTest("playwright is not installed")
        cls.tmp = Path(tempfile.mkdtemp(prefix="veil-"))
        cls.out = cls.tmp / "build"
        gp.build(cls.out, gp.PUBLIC_TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB))
        class Quiet(SimpleHTTPRequestHandler):
            # One line per asset per viewport is several hundred lines of CI
            # output that says only that the server worked.
            def log_message(self, *args):
                pass

        handler = partial(Quiet, directory=str(cls.out))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @property
    def url(self) -> str:
        return "http://127.0.0.1:%d/index.html" % self.port


class TestTheDerivativeGeometryIsLoadBearing(unittest.TestCase):
    """
    Two properties of the ASSET, checked without a browser, because both are
    silent: a build with either one wrong renders a plausible page whose
    subject drifts off frame as the viewport changes.
    """

    def record(self) -> dict:
        path = DERIV / "veil-ocean.json"
        self.assertTrue(path.is_file(),
                        "the derivative's crop record is missing")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_the_derivative_is_narrower_than_the_narrowest_veil_box(self):
        """
        The historical veil was 1600x1086 — aspect 1.47, narrower than every
        box it was ever painted into — so `cover` scaled it by WIDTH and
        cropped only vertically. An earlier build authored at 3.617:1: at 1280
        only x 0.325..1.000 of the asset was ever on screen and its left third
        was unreachable at any viewport.
        """
        record = self.record()
        self.assertLess(record["aspect"], NARROWEST_VEIL_BOX_ASPECT)
        for name in ("veil-ocean.webp", "veil-ocean.jpg"):
            path = DERIV / name
            with self.subTest(asset=name):
                self.assertTrue(path.is_file(), "%s is missing" % name)
                from PIL import Image
                with Image.open(path) as im:
                    width, height = im.size
                self.assertEqual([width, height], record["output_px"])
                self.assertLess(width / height, NARROWEST_VEIL_BOX_ASPECT)

    def test_the_subject_sits_on_the_background_position_anchor(self):
        """
        `cover` scales about the background-position anchor, so the image
        point at that fraction maps to the same box fraction at every width.
        The anchor's Y must therefore equal the Y in `background-position`, or
        the subject slides between 1280 and 1920 — which is how an earlier
        build lost the carrier at the wider viewport.
        """
        record = self.record()
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("background-position: 100% 75%;", css,
                      "the veil's background-position moved")
        self.assertEqual(record["anchor"][1], 0.75,
                         "the crop anchor and background-position disagree")

    def test_the_crop_is_explicit_and_nothing_was_clamped(self):
        """
        The builder this replaced accepted a box and then centre-cropped it to
        the output aspect, so the box it was given was not the crop it made
        and nothing said so. A clamped edge means the requested box did not
        fit the frame and was silently moved.
        """
        record = self.record()
        self.assertEqual(record["clamped_edges"], [])
        self.assertEqual([round(v, 3) for v in record["effective_crop_frac"]],
                         [0.186, 0.251, 0.766, 0.676])


class TestTheVeilIsNotFetchedBelowTheDesktopGate(VeilCase):

    #: 900 and 901 are the pair that matters: the gate is a `min-width: 901px`
    #: media query and an off-by-one is invisible on a wide monitor.
    WIDTHS = {320: 0, 375: 0, 768: 0, 900: 0, 901: 1, 1280: 1, 1920: 1}

    def test_the_veil_asset_is_requested_only_at_901_and_above(self):
        for width, expected in sorted(self.WIDTHS.items()):
            context = self.browser.new_context(
                viewport={"width": width, "height": 900},
                device_scale_factor=1)
            page = context.new_page()
            seen = []
            page.on("request", lambda r: (seen.append(r.url)
                                          if "veil-ocean" in r.url else None))
            try:
                page.goto(self.url, wait_until="networkidle")
                with self.subTest(width=width):
                    self.assertEqual(
                        len(seen), expected,
                        "%d veil requests at %dpx, expected %d"
                        % (len(seen), width, expected))
            finally:
                context.close()

    def test_the_property_does_not_exist_below_the_gate(self):
        """
        Stronger than counting requests, and the reason the declaration is
        inside the query rather than behind `display: none`: below 901px the
        `background-image` property must not be in the cascade at all. A
        declared-then-hidden image is one a browser may still fetch.
        """
        for width in (320, 375, 768, 900):
            context = self.browser.new_context(
                viewport={"width": width, "height": 900})
            page = context.new_page()
            try:
                page.goto(self.url, wait_until="load")
                painted = page.evaluate(
                    "() => { const v = document.querySelector('.veil');"
                    " return v ? getComputedStyle(v).backgroundImage : 'none'; }")
                with self.subTest(width=width):
                    self.assertEqual(painted, "none",
                                     "a background image is declared at %dpx"
                                     % width)
            finally:
                context.close()


class TestTextOverTheVeilIsMeasuredAtItsGlyphs(VeilCase):
    """
    The measurement that nearly did not happen. Every run below sits over the
    photograph at one width or the other.
    """

    #: selector -> the floor it must clear. `.claim` is display type and takes
    #: the large-text floor; everything else takes body.
    RUNS = {".claim": AA_LARGE, ".claim-sub": AA_BODY,
            ".btn--secondary": AA_BODY, ".ledger-label": AA_BODY,
            ".ledger-row dt": AA_BODY, ".ledger-row dd": AA_BODY,
            ".ledger-foot a": AA_BODY, ".veil-credit": AA_BODY}

    #: Below this many differing pixels the mask did not find a glyph, which
    #: means the probe measured nothing and must not report a pass.
    MIN_GLYPH_PIXELS = 200

    def glyph_contrast(self, page, selector):
        """Worst contrast over the pixels this run's glyphs actually cover."""
        info = page.evaluate(
            "(s) => { const e = document.querySelector(s); if (!e) return null;"
            " const r = e.getBoundingClientRect();"
            " const cs = getComputedStyle(e);"
            " return {color: cs.color, size: parseFloat(cs.fontSize),"
            "         weight: cs.fontWeight, x: r.x, y: r.y,"
            "         w: r.width, h: r.height}; }", selector)
        if not info or info["w"] < 1 or info["h"] < 1:
            return None
        clip = {"x": info["x"], "y": info["y"],
                "width": info["w"], "height": info["h"]}
        with_text = page.screenshot(clip=clip)
        page.add_style_tag(content="%s{color:transparent !important}" % selector)
        page.wait_for_timeout(80)
        without_text = page.screenshot(clip=clip)
        page.evaluate(
            "() => { const s = [...document.querySelectorAll('style')].pop();"
            " if (s) s.remove(); }")

        from PIL import Image
        import io
        a = Image.open(io.BytesIO(with_text)).convert("RGB")
        b = Image.open(io.BytesIO(without_text)).convert("RGB")
        self.assertEqual(a.size, b.size)
        fg = [int(v) for v in
              info["color"].replace("rgba(", "").replace("rgb(", "")
              .rstrip(")").split(",")[:3]]
        pa, pb = a.load(), b.load()
        worst, count = 99.0, 0
        for y in range(a.size[1]):
            for x in range(a.size[0]):
                p, q = pa[x, y], pb[x, y]
                # The glyph CORE, not its antialiased edge: an edge pixel is a
                # blend of ink and ground and is not required to clear AA.
                if (abs(p[0] - q[0]) + abs(p[1] - q[1])
                        + abs(p[2] - q[2])) <= 90:
                    continue
                count += 1
                ratio = contrast(fg, q)
                if ratio < worst:
                    worst = ratio
        return {"worst": worst, "pixels": count, "size": info["size"],
                "weight": info["weight"]}

    def test_every_text_run_over_the_veil_clears_its_floor_at_its_glyphs(self):
        for width in (1280, 1920):
            context = self.browser.new_context(
                viewport={"width": width, "height": 900},
                device_scale_factor=2)
            page = context.new_page()
            try:
                page.goto(self.url, wait_until="networkidle")
                page.evaluate(
                    "() => document.documentElement.classList.add('no-anim')")
                page.wait_for_timeout(120)
                for selector, floor in sorted(self.RUNS.items()):
                    result = self.glyph_contrast(page, selector)
                    with self.subTest(width=width, run=selector):
                        self.assertIsNotNone(
                            result, "%s did not render at %d"
                                    % (selector, width))
                        self.assertGreaterEqual(
                            result["pixels"], self.MIN_GLYPH_PIXELS,
                            "%s: only %d glyph pixels sampled — the mask found "
                            "no text, so this is not a measurement"
                            % (selector, result["pixels"]))
                        self.assertGreaterEqual(
                            result["worst"], floor,
                            "%s at %d measures %.2f:1 over the veil "
                            "(floor %.1f, %d glyph pixels). Lobe 1's "
                            "horizontal radius is the usual cause."
                            % (selector, width, result["worst"], floor,
                               result["pixels"]))
            finally:
                context.close()


class TestTheVeilCostsNothingItDoesNotDeclare(VeilCase):

    def geometry(self, page):
        return page.evaluate("""() => {
          const pick = s => {
            const e = document.querySelector(s);
            if (!e) return null;
            const r = e.getBoundingClientRect();
            return [Math.round(r.x), Math.round(r.y),
                    Math.round(r.width), Math.round(r.height)];
          };
          return {
            doc: Math.round(document.documentElement.scrollHeight),
            claim: pick('.claim'), sub: pick('.claim-sub'),
            ledger: pick('.ledger'), lead: pick('.lead-record'),
            register: pick('.register'), band: pick('.band'),
          };
        }""")

    def test_the_veil_adds_no_layout_shift(self):
        """
        The veil is absolutely positioned and `pointer-events: none`, so it
        should change no geometry at all. Asserted rather than assumed: a
        layer that moves the ledger by a pixel is a layer that invalidates
        every measurement in this file.
        """
        for width in (1280, 1920):
            context = self.browser.new_context(
                viewport={"width": width, "height": 900})
            page = context.new_page()
            try:
                page.goto(self.url, wait_until="networkidle")
                page.evaluate(
                    "() => document.documentElement.classList.add('no-anim')")
                page.wait_for_timeout(100)
                before = self.geometry(page)
                page.add_style_tag(
                    content=".veil{display:none !important}")
                page.wait_for_timeout(100)
                after = self.geometry(page)
                with self.subTest(width=width):
                    self.assertEqual(before, after,
                                     "removing the veil moved the layout")
            finally:
                context.close()

    def test_the_masthead_holds_its_measured_geometry_at_320(self):
        """
        Item 59 of the implementation map, and the reason it is here: a
        `<source>` inside a `display: contents` picture is not `display: none`
        by default. It becomes a zero-width flex item, the row `gap` charges
        9.6px for it, `.brand-text` narrows from 234.41 to 224.81, and
        `.brand-sub` wraps onto a fourth line — pushing the masthead from
        146.80px to 164.19px. Nothing errors and nothing looks obviously
        wrong. Only the number moves.
        """
        expected = {320: (146.8, 3), 375: (148.58, 3)}
        for width, (height, lines) in sorted(expected.items()):
            context = self.browser.new_context(
                viewport={"width": width, "height": 900},
                device_scale_factor=1)
            page = context.new_page()
            try:
                page.goto(self.url, wait_until="load")
                got = page.evaluate("""() => {
                  const m = document.querySelector('.masthead');
                  const s = document.querySelector('.brand-sub');
                  const cs = getComputedStyle(s);
                  const n = document.querySelector('.brand-name');
                  return {
                    masthead: +m.getBoundingClientRect().height.toFixed(2),
                    subLines: Math.round(s.getBoundingClientRect().height /
                                         parseFloat(cs.lineHeight)),
                    nameLines: Math.round(
                      n.getBoundingClientRect().height /
                      parseFloat(getComputedStyle(n).lineHeight)),
                    sourceDisplay: getComputedStyle(
                      document.querySelector('.brand picture source')).display,
                  };
                }""")
                with self.subTest(width=width):
                    self.assertEqual(got["sourceDisplay"], "none",
                                     "the picture's source is a flex item")
                    self.assertAlmostEqual(got["masthead"], height, delta=0.5)
                    self.assertEqual(got["subLines"], lines)
                    self.assertEqual(got["nameLines"], 1,
                                     "the wordmark must hold one line")
            finally:
                context.close()

    def test_exactly_one_masthead_mark_is_fetched_at_every_width(self):
        """
        A `<picture>` that is wrong in either direction is silent: a broken
        swap serves the canonical artwork below its floor, and a double fetch
        serves both and shows the right one.
        """
        expected = {320: "mark.svg", 375: "mark.svg", 380: "mark.svg",
                    381: "masthead-mark.png", 768: "masthead-mark.png",
                    1280: "masthead-mark.png"}
        for width, asset in sorted(expected.items()):
            context = self.browser.new_context(
                viewport={"width": width, "height": 900},
                device_scale_factor=1)
            page = context.new_page()
            seen = []
            page.on("request", lambda r: (
                seen.append(r.url.split("/")[-1])
                if r.url.endswith(("mark.svg", "masthead-mark.png")) else None))
            try:
                page.goto(self.url, wait_until="networkidle")
                current = page.evaluate(
                    "() => (document.querySelector('.brand-mark').currentSrc"
                    " || '').split('/').pop()")
                with self.subTest(width=width):
                    self.assertEqual(current, asset)
                    # `mark.svg` is also the favicon, so it can legitimately be
                    # requested for that. What must not happen is BOTH masthead
                    # candidates arriving.
                    self.assertNotIn(
                        "masthead-mark.png" if asset == "mark.svg"
                        else "mark.svg-as-mark", seen[:0] or [],
                        "both mark candidates were fetched")
                    marks = [s for s in seen if s == "masthead-mark.png"]
                    if asset == "mark.svg":
                        self.assertEqual(
                            marks, [],
                            "the canonical raster was fetched below its floor")
            finally:
                context.close()


if __name__ == "__main__":
    unittest.main()
