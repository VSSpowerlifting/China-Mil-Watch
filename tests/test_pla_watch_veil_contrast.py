"""
Reading contrast inside the Signal Veil band — measured on composited pixels.

Why this module exists
----------------------
`test_pla_watch_reading_ergonomics.py` lifted `--color-text-muted` and closed
the token-ground defects, and it says in its own docstring what it could not
reach: on an edition carrying a Signal Veil the hero renders inside
`.nd-veil-band`, so the byline and the hero metadata sit over a photograph
rather than over `--color-bg`. No colour can fix that, because the ground is
an image.

The 2026-09-07 exploration measured the real scale of it. Eleven of fourteen
editions render `.nd-veil-band` — Nos. 2, 3, 5, 6, 7, 8, 9, 10, 11, 12 and 13;
only Nos. 1, 4 and 14 do not. Across those eleven at 375/768/1280 the merged
templates failed 265 of 832 text runs, the worst at **1.00:1** — the desktop
source bracket on No. 2, which is not merely low contrast but invisible.

Three failures had distinct causes, and all three are contracted here:

1.  The type sits in the band's lower zone (byline from ~60% of band height,
    metadata from ~70%, tick label ending at ~96%) while the mask puts the
    photograph in exactly that zone on mobile. Direction C answers it with a
    deck anchored to `.hero-meta` itself, so the boundary lands on the rule
    that block already draws whatever the headline does.

2.  `.pw-badge--significant` and `--pilot` carry *translucent* fills, so a
    bright frame shows straight through the chip. They are given the page
    ground underneath and keep their exact tint on top.

3.  The 701–900px range had no protection at all: the mobile mask stops at
    700px, so the desktop mask ran across the full narrow band and every run
    sat on photography. It is invisible at 375 and at 1280.

Method, and what it does not claim
----------------------------------
WCAG assumes a uniform background. Over photography there is none, so a single
ratio does not exist. Each page is rendered twice — once normally, once with
every glyph transparent while every box, border, background and overlay stays
intact. Differencing gives a glyph-coverage mask; pixels at >= 55% of a run's
peak difference are its *core* (the solid stroke). Each core pixel's backdrop
is read from the glyph-free render and compared against the computed colour.
The asserted figure is the 2nd percentile, not the mean.

Deliberately not counted: text shadow. The backdrop pass strips it, so no
shadow can inflate a score. A shadow is not a WCAG contrast mechanism.

Raster tolerance. These assertions sample real pixels, so they are not exact
across rasterisers. They are written as *floors with headroom* rather than as
screenshot equality: the design target is 4.8:1, the governed floor is 4.65:1
(0.15 for glyph-core selection shifting between font stacks and hinting), and
AA's own 4.5:1 is asserted separately and unconditionally. Measured worst on
the implementation is 4.84:1, so the floor sits ~0.19 below the real value.
Where the offline suite has no network the fonts fall back, glyph cores move,
and that headroom is what absorbs it.

Nothing here writes into `output/`, and nothing here touches `pla_watch.db`.
Images are read from the published tree read-only, so the real curated and
source veils are measured rather than a stand-in.
"""

from __future__ import annotations

import functools
import http.server
import json
import re
import shutil
import socketserver
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TEMPLATES = REPO_ROOT / "site" / "templates"
POST_TEMPLATE = TEMPLATES / "pla-watch-post.html"
BASE_TEMPLATE = TEMPLATES / "pla-watch-base.html"
OUTPUT_PW = REPO_ROOT / "output" / "the-pla-watch"
POSTS_DIR = OUTPUT_PW / "posts"

WIDTHS = (375, 768, 1280)

# Design target 4.8; governed floor 4.65 leaves 0.15 for rasteriser variation.
CONTRAST_TARGET = 4.8
CONTRAST_FLOOR = 4.65
AA_NORMAL = 4.5
AA_LARGE = 3.0
GLYPH_CORE = 0.55


# ── colour maths ────────────────────────────────────────────────────────────

def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    return 0.2126 * _lin(rgb[0]) + 0.7152 * _lin(rgb[1]) + 0.0722 * _lin(rgb[2])


def contrast_of(l1: float, l2: float) -> float:
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def parse_rgb(text: str):
    nums = re.findall(r"[\d.]+", text or "")
    if len(nums) < 3:
        return (0, 0, 0)
    return (float(nums[0]), float(nums[1]), float(nums[2]))


def hex_to_rgb(value: str):
    value = value.strip().lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


# ── template source helpers ─────────────────────────────────────────────────

def _style_source(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"<style[^>]*>(.*?)</style>", text, re.S)
    if blocks:
        return "\n".join(blocks)
    return text


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


def root_tokens() -> dict:
    css = strip_comments(_style_source(BASE_TEMPLATE))
    block = re.search(r":root\s*\{(.*?)\}", css, re.S)
    tokens = {}
    for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block.group(1)):
        tokens[name] = value.strip()
    return tokens


def veil_block() -> str:
    """
    The Signal Veil reading-contrast section of the post template, taken from
    the opening of its banner comment so `strip_comments` can remove the whole
    rationale. Starting mid-comment would leave the prose to be parsed as
    selectors.
    """
    css = _style_source(POST_TEMPLATE)
    marker = css.find("Signal Veil reading contrast")
    if marker == -1:
        return ""
    start = css.rfind("/*", 0, marker)
    if start == -1:
        start = marker
    end = css.find("/* ── Cover attribution", marker)
    return css[start:end if end != -1 else len(css)]


def scrim_rules() -> list:
    """Bodies of every `.nd-veil-band::after` rule, at every breakpoint."""
    return re.findall(r"\.nd-veil-band::after\s*\{(.*?)\}",
                      strip_comments(veil_block()), re.S)


# ── fixtures ────────────────────────────────────────────────────────────────

class VeilSurfaces(unittest.TestCase):
    """
    Renders the weekly posts the way the weekly renderer does, into a tree
    shaped like `output/` so the real veil images resolve, and serves it.
    """

    @classmethod
    def setUpClass(cls):
        if not POSTS_DIR.is_dir() or not any(POSTS_DIR.glob("*.json")):
            raise unittest.SkipTest("no published sidecars to render")
        try:
            from scripts.pw_env import make_pw_env
            import scripts.rerender_pla_watch as rr
        except Exception as exc:                             # pragma: no cover
            raise unittest.SkipTest("weekly renderer unavailable: %s" % exc)

        cls.tmp = Path(tempfile.mkdtemp(prefix="pw-veil-"))
        posts_out = cls.tmp / "the-pla-watch" / "posts"
        posts_out.mkdir(parents=True, exist_ok=True)

        # Read-only borrows of the published media so the measured veils are
        # the real curated and source photographs, not a stand-in.
        for src, dest in ((OUTPUT_PW / "media", cls.tmp / "the-pla-watch" / "media"),
                          (REPO_ROOT / "output" / "assets", cls.tmp / "assets")):
            if src.is_dir() and not dest.exists():
                dest.symlink_to(src, target_is_directory=True)

        env = make_pw_env()
        post_tmpl = env.get_template("pla-watch-post.html")
        sidecars = [json.loads(p.read_text(encoding="utf-8"))
                    for p in sorted(POSTS_DIR.glob("*.json"))]
        by_date = sorted(sidecars, key=lambda s: s.get("date", ""))

        cls.posts, cls.veil_dates, cls.plain_dates = {}, [], []
        for i, sidecar in enumerate(by_date):
            ctx = rr._build_post_context(sidecar)
            ctx["prev_post"] = by_date[i - 1] if i > 0 else None
            ctx["next_post"] = by_date[i + 1] if i + 1 < len(by_date) else None
            html = post_tmpl.render(**ctx)
            date = sidecar["date"]
            cls.posts[date] = {"html": html, "sidecar": sidecar,
                               "issue": sidecar.get("issue_number")}
            (posts_out / ("%s.html" % date)).write_text(html, encoding="utf-8")
            # The band is emitted only when the edition resolves a veil, so
            # the markup is the authority on which editions are in scope.
            # Matching the class name alone would hit the inlined stylesheet
            # on every page, veil or not.
            (cls.veil_dates if '<section class="nd-veil-band">' in html
             else cls.plain_dates).append(date)

        if not cls.veil_dates:                               # pragma: no cover
            raise unittest.SkipTest("no edition renders a Signal Veil")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def issue_of(self, date):
        return "No. %s" % (self.posts[date]["issue"] or "?")


class BrowserVeilCase(VeilSurfaces):
    """Serves the rendered tree on loopback and measures it in chromium."""

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:                                  # pragma: no cover
            raise unittest.SkipTest("playwright not installed")
        try:
            import PIL  # noqa: F401
        except ImportError:                                  # pragma: no cover
            raise unittest.SkipTest("pillow not installed")
        super().setUpClass()

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        handler = functools.partial(Quiet, directory=str(cls.tmp))
        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls._pw = sync_playwright().start()
        try:
            cls.browser = cls._pw.chromium.launch()
        except Exception as exc:                             # pragma: no cover
            cls._pw.stop()
            cls.httpd.shutdown()
            cls.httpd.server_close()
            raise unittest.SkipTest(
                "chromium not available (%s); run `playwright install chromium`"
                % type(exc).__name__)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
            cls._pw.stop()
            cls.httpd.shutdown()
            cls.httpd.server_close()
        super().tearDownClass()

    def url(self, date):
        return "http://127.0.0.1:%d/the-pla-watch/posts/%s.html" % (self.port, date)

    def page(self, date, width, scale=1, reduced="reduce"):
        ctx = self.browser.new_context(
            viewport={"width": width, "height": 900},
            device_scale_factor=scale, reduced_motion=reduced)
        page = ctx.new_page()
        page.goto(self.url(date), wait_until="load")
        try:
            page.wait_for_function("document.fonts.status === 'loaded'", timeout=6000)
        except Exception:
            pass
        page.wait_for_timeout(200)
        return ctx, page

    def evaluate(self, date, width, script, scale=1):
        ctx, page = self.page(date, width, scale)
        try:
            return page.evaluate(script)
        finally:
            ctx.close()


# ── the measurement itself ──────────────────────────────────────────────────

COLLECT_RUNS_JS = r"""
() => {
  const band = document.querySelector('section.nd-veil-band');
  if (!band) return null;
  const runs = [];
  const walker = document.createTreeWalker(band, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim()) continue;
    const el = node.parentElement;
    if (!el) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const rects = [...range.getClientRects()].filter(r => r.width > 1 && r.height > 1);
    if (!rects.length) continue;
    const size = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight) || 400;
    runs.push({
      label: (el.className && typeof el.className === 'string'
              ? el.className : el.tagName).split(' ')[0],
      text: node.textContent.trim().slice(0, 48),
      color: cs.color,
      sizePx: size,
      isLarge: size >= 24 || (size >= 18.66 && weight >= 700),
      rects: rects.map(r => ({x: r.x, y: r.y, w: r.width, h: r.height})),
    });
  }
  const b = band.getBoundingClientRect();
  return {runs, band: {x: b.x, y: b.y, w: b.width, h: b.height}};
}
"""

HIDE_GLYPHS_CSS = """
section.nd-veil-band, section.nd-veil-band * {
  color: transparent !important;
  text-shadow: none !important;
  -webkit-text-stroke: 0 !important;
  text-decoration-color: transparent !important;
}
"""


class ContrastMixin:
    """Samples the composited backdrop behind every glyph core in the band."""

    SCALE = 2

    def band_contrasts(self, date, width):
        from PIL import Image
        import io

        ctx, page = self.page(date, width, scale=self.SCALE)
        try:
            info = page.evaluate(COLLECT_RUNS_JS)
            if info is None:
                return None
            band = info["band"]
            clip = {"x": max(0.0, band["x"]), "y": max(0.0, band["y"]),
                    "width": min(band["w"], float(width)), "height": band["h"]}
            shot_text = page.screenshot(clip=clip, full_page=True)
            page.add_style_tag(content=HIDE_GLYPHS_CSS)
            page.wait_for_timeout(120)
            shot_bg = page.screenshot(clip=clip, full_page=True)
        finally:
            ctx.close()

        im_t = Image.open(io.BytesIO(shot_text)).convert("RGB")
        im_b = Image.open(io.BytesIO(shot_bg)).convert("RGB")
        px_t, px_b = im_t.load(), im_b.load()
        W, H = im_t.size
        ox, oy, s = clip["x"], clip["y"], self.SCALE

        measured = []
        for run in info["runs"]:
            text_lum = luminance(parse_rgb(run["color"]))
            diffs = []
            for r in run["rects"]:
                x0 = max(0, int(round((r["x"] - ox) * s)))
                x1 = min(W, int(round((r["x"] - ox + r["w"]) * s)))
                y0 = max(0, int(round((r["y"] - oy) * s)))
                y1 = min(H, int(round((r["y"] - oy + r["h"]) * s)))
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        a, b = px_t[x, y], px_b[x, y]
                        d = max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))
                        if d > 4:
                            diffs.append((d, b))
            if not diffs:
                continue
            peak = max(d for d, _ in diffs)
            core = [b for d, b in diffs if d >= GLYPH_CORE * peak]
            if len(core) < 12:
                core = [b for d, b in diffs if d >= 0.35 * peak]
            if len(core) < 4:
                continue
            ratios = sorted(contrast_of(text_lum, luminance(b)) for b in core)
            p2 = ratios[min(len(ratios) - 1, int(0.02 * (len(ratios) - 1)))]
            measured.append({"label": run["label"], "text": run["text"],
                             "isLarge": run["isLarge"], "sizePx": run["sizePx"],
                             "ratio": p2, "color": run["color"]})
        return measured


# ── 1. the scrim exists, and cannot reach past the veil band ────────────────

class TestScrimIsPresentAndScoped(unittest.TestCase):

    def setUp(self):
        self.block = veil_block()
        self.assertTrue(
            self.block,
            "the post template has no Signal Veil reading-contrast section")

    def test_band_carries_a_non_interactive_overlay(self):
        rule = re.search(r"\.nd-veil-band::after\s*\{(.*?)\}", self.block, re.S)
        self.assertIsNotNone(rule, ".nd-veil-band::after is not declared")
        body = rule.group(1)
        self.assertIn("pointer-events", body)
        self.assertRegex(body, r"pointer-events\s*:\s*none",
                         "the overlay must never take pointer events")

    def test_record_deck_is_anchored_to_the_metadata_block(self):
        # Anchored to .hero-meta rather than to a percentage of band height:
        # the byline starts anywhere from 60% to 71% of the band depending on
        # how the headline wraps, so a fixed percentage would cut into it.
        self.assertRegex(
            self.block, r"\.nd-veil-band\s+\.hero-meta::before\s*\{",
            "the deck must be anchored to .hero-meta, not to the band")
        rule = re.search(r"\.nd-veil-band\s+\.hero-meta::before\s*\{(.*?)\}",
                         self.block, re.S).group(1)
        self.assertRegex(rule, r"pointer-events\s*:\s*none")
        self.assertRegex(rule, r"z-index\s*:\s*-1",
                         "the deck must paint behind the metadata it backs")

    def test_every_new_selector_is_scoped_to_the_veil_band(self):
        stripped = strip_comments(self.block)
        selectors = []
        for chunk in re.findall(r"([^{}]+)\{", stripped):
            for sel in chunk.split(","):
                sel = sel.strip()
                if not sel or sel.startswith("@") or sel.startswith("/"):
                    continue
                selectors.append(sel)
        unscoped = [s for s in selectors if not s.startswith(".nd-veil-band")]
        self.assertEqual(
            [], unscoped,
            "these would reach editions with no Signal Veil: %s" % unscoped)

    def test_scrim_colour_is_the_page_ground(self):
        # The scrim is the publication's own ground at partial alpha. If
        # --color-bg is ever retuned the scrim must move with it, so the
        # channels are asserted equal rather than left to drift.
        ground = hex_to_rgb(root_tokens()["--color-bg"])
        rules = scrim_rules()
        self.assertTrue(rules, "no .nd-veil-band::after rule found")
        channels = set()
        for body in rules:
            channels.update(re.findall(
                r"rgba\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,", body))
        self.assertTrue(channels, "no scrim colour found")
        for triple in channels:
            self.assertEqual(
                tuple(int(v) for v in triple), ground,
                "scrim rgba%s is not --color-bg %s" % (triple, ground))

    def test_scrim_introduces_no_asset_font_or_motion(self):
        stripped = strip_comments(self.block)
        for forbidden, why in ((r"url\(", "no external or generated asset"),
                               (r"@font-face", "no new font"),
                               (r"animation\s*:", "no motion"),
                               (r"transition\s*:", "no motion"),
                               (r"backdrop-filter", "no glass-card blur"),
                               (r"filter\s*:\s*blur", "no glass-card blur")):
            self.assertNotRegex(stripped, forbidden,
                                "%s belongs in this band" % why)

    def test_the_gap_between_the_two_masks_is_covered(self):
        # The mobile mask stops at 700px and the desktop mask begins its own
        # geometry at 901px. Between them the desktop mask ran across the full
        # narrow band with nothing protecting the type. That range is the
        # worst in the set and is invisible at 375 and at 1280.
        self.assertRegex(
            strip_comments(self.block),
            r"@media\s*\(min-width:\s*701px\)\s*and\s*\(max-width:\s*900px\)",
            "the 701-900px range needs its own scrim geometry")


# ── 2. badges stop being see-through ────────────────────────────────────────

class TestBadgeChipsAreOpaqueOverPhotography(unittest.TestCase):

    def test_badge_fills_sit_on_the_page_ground(self):
        block = strip_comments(veil_block())
        rule = re.search(r"\.nd-veil-band\s+\.pw-badge\s*\{(.*?)\}", block, re.S)
        self.assertIsNotNone(
            rule, "badge chips are translucent by construction and must be "
                  "given the page ground inside the veil band")
        self.assertRegex(rule.group(1),
                         r"background-color\s*:\s*var\(--color-bg\)")

    def test_badge_tints_are_reapplied_unchanged(self):
        # The chip must look identical on navy: same rgba, now layered over
        # the ground instead of over whatever frame is behind it.
        base = strip_comments(_style_source(BASE_TEMPLATE))
        block = strip_comments(veil_block())
        for variant in ("significant", "pilot"):
            original = re.search(
                r"\.pw-badge--%s\s*\{(.*?)\}" % variant, base, re.S)
            self.assertIsNotNone(original)
            tint = re.search(r"background\s*:\s*(rgba\([^)]*\))",
                             original.group(1))
            self.assertIsNotNone(tint, "%s has no rgba fill" % variant)
            wanted = re.sub(r"\s+", "", tint.group(1))
            found = re.search(
                r"\.nd-veil-band\s+\.pw-badge--%s\s*\{(.*?)\}" % variant,
                block, re.S)
            self.assertIsNotNone(found, "%s is not re-grounded" % variant)
            self.assertIn(wanted, re.sub(r"\s+", "", found.group(1)),
                          "%s must keep its exact tint" % variant)

    def test_opacity_is_never_used_inside_the_band(self):
        # An early draft dimmed .hero-edition with opacity, which
        # re-composited the now-opaque badge against the photograph and undid
        # the fix above. Colour only, never opacity, inside this band.
        block = strip_comments(veil_block())
        self.assertNotRegex(
            block, r"(^|[;{\s])opacity\s*:",
            "opacity re-composites the opaque badge chips against the "
            "photograph; use colour instead")


# ── 3. the measured contract ────────────────────────────────────────────────

class TestVeilTextMeetsAA(BrowserVeilCase, ContrastMixin):
    """
    Every text run inside every Signal Veil band, at all three primary
    widths, measured against the pixels actually behind its glyphs.
    """

    def test_every_veil_edition_clears_the_governed_floor(self):
        failures, worst = [], (99.0, None)
        for date in self.veil_dates:
            for width in WIDTHS:
                runs = self.band_contrasts(date, width)
                self.assertIsNotNone(
                    runs, "%s renders no veil band at %dpx" % (date, width))
                for run in runs:
                    hard = AA_LARGE if run["isLarge"] else AA_NORMAL
                    floor = AA_LARGE if run["isLarge"] else CONTRAST_FLOOR
                    if run["ratio"] < floor:
                        failures.append(
                            "%s %s @%dpx  .%s  %.2f:1 (needs %.2f, AA %.2f) "
                            "%.1fpx %s  %r" % (
                                self.issue_of(date), date, width, run["label"],
                                run["ratio"], floor, hard, run["sizePx"],
                                run["color"], run["text"]))
                    if not run["isLarge"] and run["ratio"] < worst[0]:
                        worst = (run["ratio"], failures[-1] if failures else None)
        self.assertEqual(
            [], failures,
            "%d run(s) below the governed floor (target %.1f, floor %.2f):\n  %s"
            % (len(failures), CONTRAST_TARGET, CONTRAST_FLOOR,
               "\n  ".join(failures[:24])))

    def test_the_expected_editions_are_in_scope(self):
        # The brief assumed one veil edition. Eleven render the band; if that
        # set changes, this contract should be re-derived rather than quietly
        # covering fewer pages.
        self.assertGreaterEqual(
            len(self.veil_dates), 11,
            "expected at least 11 editions rendering .nd-veil-band, found %d: %s"
            % (len(self.veil_dates), self.veil_dates))
        self.assertTrue(self.plain_dates,
                        "expected at least one edition with no Signal Veil")


# ── 4. nothing moves, nothing is repositioned ───────────────────────────────

GEOMETRY_JS = r"""
() => {
  const box = s => { const e = document.querySelector(s); if (!e) return null;
    const r = e.getBoundingClientRect();
    return [+r.x.toFixed(2), +r.y.toFixed(2), +r.width.toFixed(2), +r.height.toFixed(2)]; };
  const veil = document.querySelector('.nd-veil');
  const cs = veil ? getComputedStyle(veil) : null;
  return {
    boxes: {
      band: box('section.nd-veil-band'), inner: box('.nd-band-inner'),
      title: box('.hero-title'), dek: box('.hero-dek'),
      byline: box('.byline'), bylineTitle: box('.byline-title'),
      meta: box('.hero-meta'), edition: box('.hero-edition'),
      srcInline: box('.nd-src-inline'), tickLabel: box('.nd-tickrow-label'),
    },
    veil: cs ? {
      maskImage: cs.maskImage || cs.webkitMaskImage,
      backgroundPosition: cs.backgroundPosition,
      backgroundImage: cs.backgroundImage,
      backgroundSize: cs.backgroundSize,
      width: cs.width,
    } : null,
    overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  };
}
"""

# Neutralises exactly the new rules, so the comparison is against this
# template with the treatment off rather than against a stale checkout.
DISABLE_TREATMENT_CSS = """
section.nd-veil-band::after { content: none !important; }
section.nd-veil-band .hero-meta::before { content: none !important; }
section.nd-veil-band .hero-meta { position: static !important; }
"""


class TestTreatmentMovesNothing(BrowserVeilCase):

    def _geometry(self, date, width, disabled):
        ctx, page = self.page(date, width)
        try:
            if disabled:
                page.add_style_tag(content=DISABLE_TREATMENT_CSS)
                page.wait_for_timeout(80)
            return page.evaluate(GEOMETRY_JS)
        finally:
            ctx.close()

    def test_no_box_moves_and_no_page_overflows(self):
        drifted = []
        for date in self.veil_dates:
            for width in WIDTHS:
                on = self._geometry(date, width, disabled=False)
                off = self._geometry(date, width, disabled=True)
                self.assertFalse(
                    on["overflowX"],
                    "%s at %dpx overflows horizontally" % (date, width))
                for name, box in on["boxes"].items():
                    if box is None or off["boxes"][name] is None:
                        continue
                    for axis, a, b in zip("xywh", box, off["boxes"][name]):
                        if abs(a - b) > 0.01:
                            drifted.append("%s @%dpx %s.%s %.2f -> %.2f"
                                           % (date, width, name, axis, b, a))
        self.assertEqual([], drifted,
                         "the treatment must not move anything:\n  %s"
                         % "\n  ".join(drifted[:20]))

    def test_the_photograph_is_not_repositioned(self):
        # Direction B was rejected partly because it re-aimed the mask. The
        # curated crop and its focal point are governed by the 2026-08-12
        # traceability ruling, so the veil's own geometry must be untouched.
        for date in self.veil_dates:
            for width in WIDTHS:
                on = self._geometry(date, width, disabled=False)
                off = self._geometry(date, width, disabled=True)
                self.assertEqual(
                    off["veil"], on["veil"],
                    "%s at %dpx: the veil's own mask, position or size moved"
                    % (date, width))


# ── 5. non-veil editions are untouched ──────────────────────────────────────

class TestNonVeilEditionsAreUntouched(BrowserVeilCase):

    def test_plain_editions_render_no_band_and_no_deck(self):
        for date in self.plain_dates:
            html = self.posts[date]["html"]
            self.assertNotIn('<section class="nd-veil-band">', html,
                             "%s should render no Signal Veil band" % date)
            for width in WIDTHS:
                painted = self.evaluate(date, width, r"""
                  () => {
                    const m = document.querySelector('.hero-meta');
                    if (!m) return null;
                    const before = getComputedStyle(m, '::before');
                    return {content: before.content,
                            position: getComputedStyle(m).position};
                  }
                """)
                self.assertIsNotNone(painted, "%s has no .hero-meta" % date)
                self.assertEqual(
                    "none", painted["content"],
                    "%s at %dpx paints a record deck outside a veil band"
                    % (date, width))
                self.assertEqual(
                    "static", painted["position"],
                    "%s at %dpx had its metadata block repositioned"
                    % (date, width))


# ── 6. stacking, hit testing and the companion bracket fix ──────────────────

class TestOverlayStackingAndPointerEvents(BrowserVeilCase):

    def test_metadata_text_sits_above_the_deck(self):
        for date in self.veil_dates[:4]:
            for width in WIDTHS:
                hit = self.evaluate(date, width, r"""
                  () => {
                    const num = document.querySelector('.hero-meta .num');
                    if (!num) return 'no metadata';
                    const r = num.getBoundingClientRect();
                    const el = document.elementFromPoint(r.x + r.width/2,
                                                         r.y + r.height/2);
                    return el === num || num.contains(el) || el.contains(num)
                      ? 'above' : 'covered by ' + el.className;
                  }
                """)
                self.assertEqual("above", hit,
                                 "%s at %dpx: %s" % (date, width, hit))

    def test_nothing_in_the_band_intercepts_pointer_events(self):
        for date in self.veil_dates[:4]:
            for width in WIDTHS:
                bad = self.evaluate(date, width, r"""
                  () => {
                    const band = document.querySelector('.nd-veil-band');
                    const r = band.getBoundingClientRect(); const bad = [];
                    for (let i = 1; i < 10; i++)
                      for (let j = 1; j < 10; j++) {
                        const x = r.x + r.width * i / 10;
                        const y = r.y + r.height * j / 10;
                        if (y < 0 || y > innerHeight) continue;
                        const el = document.elementFromPoint(x, y);
                        if (el && getComputedStyle(el).pointerEvents === 'none')
                          bad.push(String(el.className) + '@' + i + ',' + j);
                      }
                    return bad;
                  }
                """)
                self.assertEqual([], bad,
                                 "%s at %dpx: inert element took the hit: %s"
                                 % (date, width, bad))

    def test_the_veil_never_takes_pointer_events(self):
        for date in self.veil_dates[:4]:
            value = self.evaluate(date, 1280, """
              () => getComputedStyle(document.querySelector('.nd-veil')).pointerEvents
            """)
            self.assertEqual("none", value, "%s: the veil became clickable" % date)


# ── 7. print, reduced motion, identity ──────────────────────────────────────

class TestVeilBandDegradesHonestly(BrowserVeilCase):

    def test_print_drops_the_veil_and_its_scrim(self):
        for date in self.veil_dates[:4]:
            ctx, page = self.page(date, 1280)
            try:
                page.emulate_media(media="print")
                page.wait_for_timeout(100)
                state = page.evaluate(r"""
                  () => {
                    const band = document.querySelector('.nd-veil-band');
                    const veil = document.querySelector('.nd-veil');
                    const meta = document.querySelector('.hero-meta');
                    return {
                      overlay: getComputedStyle(band, '::after').content,
                      deck: getComputedStyle(meta, '::before').content,
                      veil: getComputedStyle(veil).display,
                    };
                  }
                """)
            finally:
                ctx.close()
            self.assertEqual("none", state["veil"], "%s: veil prints" % date)
            self.assertEqual("none", state["overlay"],
                             "%s: the scrim prints as a dark block" % date)
            self.assertEqual("none", state["deck"],
                             "%s: the deck prints as a dark block" % date)

    def test_the_treatment_adds_no_motion(self):
        for date in self.veil_dates[:4]:
            state = self.evaluate(date, 1280, r"""
              () => {
                const band = document.querySelector('.nd-veil-band');
                const meta = document.querySelector('.hero-meta');
                const a = getComputedStyle(band, '::after');
                const b = getComputedStyle(meta, '::before');
                return {aAnim: a.animationName, aTrans: a.transitionProperty,
                        bAnim: b.animationName, bTrans: b.transitionProperty};
              }
            """)
            self.assertEqual("none", state["aAnim"], "%s: scrim animates" % date)
            self.assertEqual("none", state["bAnim"], "%s: deck animates" % date)
            self.assertIn(state["aTrans"], ("none", "all"),
                          "%s: scrim declares a transition" % date)

    def test_identity_and_disclosure_survive_the_treatment(self):
        from core.edition_identity import AUTHOR_NAME
        for date in self.veil_dates:
            html = self.posts[date]["html"]
            self.assertIn('class="byline-name"', html,
                          "%s lost its byline" % date)
            self.assertIn(AUTHOR_NAME, html, "%s lost the author name" % date)
            self.assertIn('class="pw-nameplate"', html,
                          "%s lost the nameplate" % date)
            sidecar = self.posts[date]["sidecar"]
            if sidecar.get("publication_timing") == "retrospective":
                self.assertIn("pw-badge--retrospective", html,
                              "%s lost its retrospective disclosure" % date)

    def test_the_skip_link_still_works_on_a_veil_edition(self):
        for date in self.veil_dates[:4]:
            state = self.evaluate(date, 375, r"""
              () => {
                const s = document.querySelector('.pw-skip');
                if (!s) return null;
                s.focus();
                const r = s.getBoundingClientRect();
                return {focused: document.activeElement === s,
                        visible: r.width > 0 && r.height > 0 && r.bottom > 0,
                        target: !!document.querySelector(s.getAttribute('href'))};
              }
            """)
            self.assertIsNotNone(state, "%s has no skip link" % date)
            self.assertTrue(state["focused"], "%s: skip link took no focus" % date)
            self.assertTrue(state["visible"], "%s: skip link stays hidden" % date)
            self.assertTrue(state["target"], "%s: skip link points nowhere" % date)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main(verbosity=2)
