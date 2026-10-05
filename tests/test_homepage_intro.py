"""
The homepage opening title (`site/preview/intro.js`), held to its contract.

The intro is allowed only because it can never stand between a reader and the
site. These tests are that claim, measured in a browser: it plays once, it
leaves nothing behind on any exit, and it does not start at all for a reader
who came for something specific.

Two runtime gates are adjusted per test. `intro.js` declines automated
browsers (`navigator.webdriver`), which is what keeps every other browser test
of the homepage meaningful, and it declines software WebGL
(`failIfMajorPerformanceCaveat`), which is all a headless runner has. `HUMAN`
undoes both, so the paths below actually run; `test_automation_is_declined`
checks the first gate without it, so it is tested too rather than assumed.

Offline. Serves a temporary build over loopback; never `output/`, and never
opens the tracked database for writing.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import threading
import time
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
INTRO = REPO_ROOT / "site" / "preview" / "intro.js"

HUMAN = """
Object.defineProperty(Navigator.prototype, 'webdriver', {get: () => false});
const gc = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function (type, opts) {
  if (opts) { opts = Object.assign({}, opts); delete opts.failIfMajorPerformanceCaveat; }
  return gc.call(this, type, opts);
};
// Which exit ran: dismiss() fades the overlay (`is-out`) first, while the
// cap, an error and context loss tear it down at once.
new MutationObserver(() => {
  const el = document.querySelector('div.ipr-intro');
  if (el) { window.__seen = true; if (el.classList.contains('is-out')) window.__faded = true; }
}).observe(document, {subtree: true, childList: true, attributes: true, attributeFilter: ['class']});
"""

#: Everything the intro may change, read back in one call. `clean` is the
#: whole post-condition of every exit path.
STATE = """() => {
  const html = document.documentElement;
  const styles = [...document.querySelectorAll('style')]
    .filter(s => s.textContent.includes('ipr-intro')).length;
  return {
    overlay: !!document.querySelector('.ipr-intro'),
    classes: [...html.classList].filter(c => c.startsWith('ipr-intro')),
    overflow: getComputedStyle(html).overflow,
    hidden: getComputedStyle(document.body).visibility,
    inert: document.querySelectorAll('[inert]').length,
    styles,
    overflowX: html.scrollWidth > html.clientWidth,
  };
}"""

GONE = "() => !document.querySelector('.ipr-intro')"
FADED = "!!window.__faded"


class IntroCase(unittest.TestCase):
    """One build, served over loopback, shared by every scenario."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:                       # pragma: no cover
            raise unittest.SkipTest("playwright is not installed")
        cls.tmp = Path(tempfile.mkdtemp(prefix="intro-"))
        cls.out = cls.tmp / "build"
        gp.build(cls.out, gp.PUBLIC_TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB))

        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(Quiet, directory=str(cls.out)))
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(
                args=["--enable-unsafe-swiftshader"])
        except Exception as exc:                  # pragma: no cover
            cls.pw.stop()
            raise unittest.SkipTest("chromium not available (%s)"
                                    % type(exc).__name__)
        probe = cls.browser.new_page()
        webgl = probe.evaluate(
            "!!document.createElement('canvas').getContext('webgl')")
        probe.close()
        if not webgl:                             # pragma: no cover
            # Without WebGL the intro declines to start, and every "it
            # plays" assertion below would pass without testing anything.
            cls.tearDownClass()
            raise unittest.SkipTest("no WebGL in this chromium")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "browser", None):
            cls.browser.close()
            cls.browser = None
            cls.pw.stop()
        if getattr(cls, "server", None):
            cls.server.shutdown()
            cls.server.server_close()
            cls.server = None
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def url(self, path="index.html") -> str:
        return "http://127.0.0.1:%d/%s" % (self.port, path)

    def page(self, width=480, height=640, human=True, extra="", **kwargs):
        # Small and 1x by default: the shader runs on the CPU here.
        context = self.browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1, **kwargs)
        self.addCleanup(context.close)
        if human:
            context.add_init_script(HUMAN + extra)
        elif extra:
            context.add_init_script(extra)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.errors = errors
        return page

    def assert_clean(self, page):
        state = page.evaluate(STATE)
        self.assertEqual(state, {
            "overlay": False, "classes": [], "overflow": "visible",
            "hidden": "visible", "inert": 0, "styles": 0, "overflowX": False,
        })

    def assert_never_started(self, page, path="index.html"):
        page.goto(self.url(path), wait_until="load")
        page.wait_for_timeout(150)
        self.assert_clean(page)

    def start(self, page, path="index.html"):
        page.goto(self.url(path), wait_until="domcontentloaded")
        page.wait_for_selector("div.ipr-intro", state="attached", timeout=3000)


class TestTheIntroPlaysOnceAndLeavesNothing(IntroCase):

    def test_first_visit_plays_then_restores_the_page(self):
        page = self.page()
        self.start(page)
        during = page.evaluate("""() => ({
          classes: [...document.documentElement.classList],
          overflow: getComputedStyle(document.documentElement).overflow,
          mainInert: document.querySelector('main').inert,
          title: document.querySelector('.ipr-intro-title').textContent,
          sub: document.querySelector('.ipr-intro-sub').textContent,
          skip: document.querySelector('.ipr-intro-skip').textContent,
          canvas: !!document.querySelector('.ipr-intro canvas'),
          h1s: document.querySelectorAll('h1').length,
        })""")
        self.assertIn("ipr-intro", during["classes"])
        self.assertEqual(during["overflow"], "hidden")
        self.assertTrue(during["mainInert"])
        # Live text, not pixels; the page keeps its single h1.
        self.assertEqual(during["title"], "Indo-Pacific Record")
        self.assertEqual(during["sub"], "Defense records. Regional context.")
        self.assertEqual(during["skip"], "Skip intro")
        self.assertTrue(during["canvas"])
        self.assertEqual(during["h1s"], 1)
        # It ends by itself, by the timeline's dissolve and not the 5s cap.
        page.wait_for_function(GONE, timeout=6000)
        self.assertTrue(page.evaluate(FADED))
        self.assert_clean(page)
        self.assertEqual(page.errors, [])

    def test_it_does_not_replay_in_the_same_tab(self):
        page = self.page()
        self.start(page)
        page.wait_for_function(GONE, timeout=6000)
        self.assert_never_started(page)
        page.reload(wait_until="load")
        page.wait_for_timeout(150)
        self.assert_clean(page)
        page.goto(self.url("archive.html"), wait_until="load")
        page.go_back(wait_until="load")
        page.wait_for_timeout(150)
        self.assert_clean(page)

    def test_leaving_mid_intro_and_returning_finds_the_page(self):
        page = self.page()
        self.start(page)
        page.goto(self.url("archive.html"), wait_until="load")
        page.go_back(wait_until="load")
        page.wait_for_timeout(150)
        self.assert_clean(page)


class TestEveryWayOut(IntroCase):

    def test_skip_by_keyboard_returns_focus_to_the_top_of_the_page(self):
        page = self.page()
        self.start(page)
        page.keyboard.press("Tab")
        self.assertEqual(page.evaluate("document.activeElement.className"),
                         "ipr-intro-skip")
        page.keyboard.press("Enter")
        page.wait_for_function(GONE, timeout=1500)
        self.assertTrue(page.evaluate(FADED))
        self.assert_clean(page)
        self.assertEqual(page.evaluate("document.activeElement.className"),
                         "skip")

    def test_skip_by_pointer_does_not_move_focus_into_the_page(self):
        page = self.page()
        self.start(page)
        page.click(".ipr-intro-skip")
        page.wait_for_function(GONE, timeout=1500)
        self.assertTrue(page.evaluate(FADED))
        self.assert_clean(page)
        self.assertEqual(page.evaluate("document.activeElement.tagName"),
                         "BODY")

    def test_escape_dismisses(self):
        page = self.page()
        self.start(page)
        page.keyboard.press("Escape")
        page.wait_for_function(GONE, timeout=1500)
        self.assertTrue(page.evaluate(FADED))
        self.assert_clean(page)

    def test_the_page_is_not_reachable_until_it_ends(self):
        page = self.page()
        self.start(page)
        for _ in range(4):
            page.keyboard.press("Tab")
            self.assertTrue(page.evaluate(
                "!!document.activeElement.closest('.ipr-intro')"
                " || document.activeElement === document.body"))
        hit = page.evaluate("""() => {
          const a = document.querySelector('.claim-cta a').getBoundingClientRect();
          const el = document.elementFromPoint(a.x + 4, a.y + 4);
          return !!el.closest('.ipr-intro'); }""")
        self.assertTrue(hit)


class TestADestinationIsNeverDelayed(IntroCase):

    def test_hash_and_query_bypass(self):
        for path in ("index.html#main", "index.html?from=feed", "?q=1"):
            with self.subTest(path=path):
                self.assert_never_started(self.page(), path)

    def test_other_pages_do_not_carry_it(self):
        pages = sorted(p.relative_to(self.out).as_posix()
                       for p in self.out.rglob("*.html")
                       if "intro.js" in p.read_text(encoding="utf-8"))
        self.assertEqual(pages, ["index.html"])
        for path in ("archive.html", "analysis.html", "china.html",
                     "methodology.html"):
            with self.subTest(path=path):
                self.assert_never_started(self.page(), path)

    def test_a_same_site_arrival_bypasses(self):
        page = self.page()
        page.goto(self.url("about.html"), wait_until="load")
        page.click(".brand")
        page.wait_for_load_state("load")
        page.wait_for_timeout(150)
        self.assertTrue(page.url.endswith("index.html"))
        self.assert_clean(page)

    def test_reduced_motion_bypasses(self):
        self.assert_never_started(self.page(reduced_motion="reduce"))

    def test_automation_is_declined(self):
        self.assert_never_started(self.page(human=False))


class TestFailureNeverTraps(IntroCase):

    FAILURES = {
        "no webgl": "HTMLCanvasElement.prototype.getContext = () => null;",
        "storage denied": """Object.defineProperty(window, 'sessionStorage',
            {get() { throw new DOMException('denied', 'SecurityError'); }});""",
        "storage full": """Storage.prototype.setItem = function () {
            throw new DOMException('full', 'QuotaExceededError'); };""",
    }

    def test_an_unavailable_dependency_means_no_intro(self):
        for name, script in self.FAILURES.items():
            with self.subTest(failure=name):
                self.assert_never_started(self.page(extra=script))

    def test_an_error_mid_intro_tears_it_down_at_once(self):
        # The test throws on demand, once the overlay is up, from the frame
        # loop's next requestAnimationFrame.
        page = self.page(extra="""const raf = window.requestAnimationFrame;
            window.requestAnimationFrame = function (f) {
              if (window.__boom) throw new Error('boom');
              return raf.call(window, f); };""")
        self.start(page)
        page.evaluate("window.__boom = true")
        page.wait_for_function(GONE, timeout=1500)
        self.assertFalse(page.evaluate(FADED), "ended by the timeline, not the error")
        self.assert_clean(page)

    def test_a_lost_context_ends_it_at_once(self):
        page = self.page()
        self.start(page)
        page.evaluate("""() => document.querySelector('.ipr-intro canvas')
            .getContext('webgl').getExtension('WEBGL_lose_context').loseContext()""")
        page.wait_for_function(GONE, timeout=1500)
        self.assertFalse(page.evaluate(FADED), "ended by the timeline, not the loss")
        self.assert_clean(page)

    def test_fonts_that_never_load_do_not_hold_the_copy(self):
        page = self.page(extra="if (document.fonts) document.fonts.load = () => new Promise(() => {});")
        self.start(page)
        page.wait_for_selector("div.ipr-intro.is-text", state="attached", timeout=1500)
        page.wait_for_function(GONE, timeout=6000)
        self.assertTrue(page.evaluate(FADED))
        self.assert_clean(page)

    def test_a_slow_page_gets_no_intro(self):
        # It waits for nothing the page loads: a document still parsing after
        # 1.5s (here, held by the next head script) is shown without one.
        page = self.page()
        page.route("**/reveal.js", lambda route: (time.sleep(2.2), route.continue_()))
        page.goto(self.url(), wait_until="load")
        self.assertFalse(page.evaluate("!!window.__seen"))
        self.assert_clean(page)


class TestTheCompositionFits(IntroCase):

    def test_copy_and_skip_stay_inside_the_viewport(self):
        for width, height in ((320, 568), (375, 812), (812, 375), (1280, 800)):
            with self.subTest(viewport="%dx%d" % (width, height)):
                page = self.page(width, height)
                self.start(page)
                boxes = page.evaluate("""() => Object.fromEntries(
                  ['.ipr-intro-title', '.ipr-intro-sub', '.ipr-intro-skip'].map(s => {
                    const r = document.querySelector(s).getBoundingClientRect();
                    return [s, [r.left, r.top, r.right, r.bottom]]; }))""")
                for selector, (left, top, right, bottom) in boxes.items():
                    self.assertGreaterEqual(left, 16, selector)
                    self.assertGreaterEqual(top, 16, selector)
                    self.assertLessEqual(right, width - 16, selector)
                    self.assertLessEqual(bottom, height - 16, selector)
                skip = boxes[".ipr-intro-skip"]
                title = boxes[".ipr-intro-title"]
                self.assertLess(skip[3], title[1], "Skip overlaps the title")
                self.assertGreaterEqual(skip[3] - skip[1], 44, "touch target")
                self.assertFalse(page.evaluate(
                    "document.documentElement.scrollWidth"
                    " > document.documentElement.clientWidth"))


    def test_it_recomposes_when_the_viewport_turns(self):
        page = self.page(812, 375)
        self.start(page)
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(100)
        state = page.evaluate("""() => {
          const t = document.querySelector('.ipr-intro-title').getBoundingClientRect();
          const k = document.querySelector('.ipr-intro-skip').getBoundingClientRect();
          const c = document.querySelector('.ipr-intro canvas');
          return {right: t.right, skipBottom: k.bottom, top: t.top,
                  canvas: [c.clientWidth, c.clientHeight]}; }""")
        self.assertLessEqual(state["right"], 375 - 16)
        self.assertLess(state["skipBottom"], state["top"])
        self.assertEqual(state["canvas"], [375, 812])


class TestBudget(unittest.TestCase):

    def test_intro_script_stays_within_its_budget(self):
        # VISUAL_AND_MOTION_SYSTEM §1.1. Homepage only, cached after the
        # first visit; no other page fetches it.
        self.assertLessEqual(INTRO.stat().st_size, 12_000)


if __name__ == "__main__":
    unittest.main()
