"""Real Chromium proof of focus/full archive navigation, with preserved URLs.

Required browser test (never SkipTest): the archive is generated from the
real read-only DB into ephemeral tmp and served on localhost. No deploy.
"""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "site" / "preview"
sys.path.insert(0, str(PREVIEW))
import generate_preview as gp  # noqa: E402


class _QuietStatic(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


class ChinaFocusRealBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = Path(tempfile.mkdtemp(prefix="ipr-china-scope-browser-"))
        cls.build = cls.temp / "site"
        cls.server = None
        cls.playwright = None
        cls.browser = None
        try:
            gp.build(cls.build, gp.PUBLIC_TITLE, ROOT / "pla_watch.db",
                     snapshot=gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
                     legacy_routes=True)
            cls.index = json.loads(
                (cls.build / "corpus-index.json").read_text(encoding="utf-8"))
            handler = functools.partial(_QuietStatic, directory=str(cls.build))
            cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            cls.thread = threading.Thread(
                target=cls.server.serve_forever, daemon=True)
            cls.thread.start()
            cls.origin = "http://127.0.0.1:%d" % cls.server.server_port
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.browser:
            cls.browser.close()
        if cls.playwright:
            cls.playwright.stop()
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()
            cls.thread.join(5)
        shutil.rmtree(cls.temp, ignore_errors=True)

    def test_mobile_and_desktop_scope_switch_and_deeplink(self):
        index = self.index
        self.assertEqual(len(index["records"]), index["snapshot"]["records"])
        self.assertTrue(len(index["focus_ids"]) < len(index["records"]))
        self.assertEqual(index["focus_policy"],
                         "automated_research_focus_not_human_curated")
        self.assertEqual(len(index["focus_ids"]), len(set(index["focus_ids"])))
        originals = {x[0] for x in index["records"]}
        self.assertTrue(set(index["trail_ids"]) <= originals)
        self.assertTrue(set(index["focus_ids"]) <= originals)
        self.assertEqual({2391, 2849} & set(index["focus_ids"]), {2391, 2849})
        self.assertFalse({2265, 2881} & set(index["focus_ids"]))

        for width in (375, 1280):
            with self.subTest(width=width):
                ctx = self.browser.new_context(
                    viewport={"width": width, "height": 900})
                try:
                    page = ctx.new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    response = page.goto(self.origin + "/archive.html",
                                         wait_until="networkidle")
                    self.assertEqual(response.status, 200)
                    self.assertEqual(
                        page.locator("#f-scope").input_value(), "focus")
                    self.assertIn("not individually fact-checked or editor-approved",
                                  page.locator("body").inner_text())
                    self.assertIn(
                        "research-focus records",
                        page.locator("#result-range").inner_text())
                    page.locator("#f-scope").select_option("all")
                    page.wait_for_function(
                        """expected => document.querySelector('#result-range')
                          .textContent.includes('of ' + expected.toLocaleString('en-US') +
                          ' preserved records')""",
                        arg=len(index["records"]))
                    self.assertEqual(
                        page.locator("#f-scope").input_value(), "all")
                    self.assertIn("scope=all", page.url)
                    self.assertEqual(page.locator("#index-error:visible").count(), 0)
                    # Previously downranked Chinese ministry report remains
                    # available through ordinary full-archive title searching.
                    page.locator("#f-q").fill("黄岩")
                    page.wait_for_function(
                        """() => document.querySelector('#result-range').textContent
                          .includes('matching filters')""")
                    self.assertGreater(page.locator("#results li.record-row").count(), 0)
                    page.go_back(wait_until="networkidle")
                    page.wait_for_function(
                        """() => document.querySelector('#f-scope').value === 'focus'""")
                    page.goto(self.origin + "/archive.html?scope=all",
                              wait_until="networkidle")
                    self.assertEqual(page.locator("#f-scope").input_value(), "all")
                    page.wait_for_function(
                        """() => document.querySelector('#result-range')
                          .textContent.includes('preserved records')""")
                    self.assertEqual(errors, [])
                    self.assertLessEqual(page.evaluate(
                        "document.documentElement.scrollWidth"), width)
                finally:
                    ctx.close()

    def test_no_javascript_fallback_has_unbroken_full_corpus_path(self):
        ctx = self.browser.new_context(java_script_enabled=False,
                                       viewport={"width": 375, "height": 900})
        try:
            p = ctx.new_page()
            resp = p.goto(self.origin + "/archive.html")
            self.assertEqual(resp.status, 200)
            self.assertIn("research focus", p.locator("body").inner_text().lower())
            self.assertEqual(p.locator("li.record-row").count(), 50)
            p.locator('a[href="corpus.html"]').first.click()
            self.assertTrue(p.url.endswith("corpus.html"))
            # corpus.html is the complete week index, not an exhaustive
            # inline record list. Follow the real no-script route to a week.
            p.locator('a[href^="week-"]').first.click()
            self.assertGreater(p.locator('a[href^="record/"]').count(), 0)
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
