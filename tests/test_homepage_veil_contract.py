"""Photograph-led opening contrast at actual glyph pixels.

October refinement replaces the retired Ocean Signal lobe geometry. Preserve
the existing screenshot-difference method and WCAG floors for the new photo.
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
CSS = REPO_ROOT / "site" / "preview" / "home.css"
DERIV = REPO_ROOT / "site" / "assets" / "editorial" / "derivatives"
NARROWEST_VEIL_BOX_ASPECT = 2.442
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
class TestTextOverTheVeilIsMeasuredAtItsGlyphs(VeilCase):
    """
    The measurement that nearly did not happen. Every run below sits over the
    photograph at one width or the other.
    """

    #: selector -> the floor it must clear. `.claim` is display type and takes
    #: the large-text floor; everything else takes body.
    RUNS = {".claim": AA_LARGE, ".pacific-dek": AA_BODY,
            ".pacific-intro": AA_BODY, ".photo-credit": AA_BODY,
            ".nav-desktop>a": AA_BODY}

    #: Below this many differing pixels the mask did not find a glyph, which
    #: means the probe measured nothing and must not report a pass.
    MIN_GLYPH_PIXELS = 200

    def glyph_contrast(self, page, selector):
        """Worst contrast over the pixels this run's glyphs actually cover."""
        page.locator(selector).first.scroll_into_view_if_needed()
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
        for width in (375, 1280, 1920):
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
                    if selector.startswith(".nav-desktop") and width < 900: continue
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
                            "%s at %d measures %.2f:1 over the source photo "
                            "(floor %.1f, %d glyph pixels)."
                            % (selector, width, result["worst"], floor,
                               result["pixels"]))
            finally:
                context.close()
if __name__ == "__main__":
    unittest.main()
