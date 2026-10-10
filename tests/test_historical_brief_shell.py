"""Current-shell consolidation must preserve real historical edition evidence."""
import copy
import hashlib
import json
import functools
import http.server
import shutil
import socketserver
import tempfile
import threading
from pathlib import Path
import unittest

from bs4 import BeautifulSoup

from scripts.historical_brief_render import render_historical_brief, SECTIONS
from scripts.pw_env import inline_markup, make_pw_env
from scripts.rerender_pla_watch import _build_post_context

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "output/the-pla-watch/posts"


class HistoricalBriefShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts = []
        cls.files = list(POSTS.glob("*.json")) + [ROOT / "pla_watch.db"]
        cls.fingerprints = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in cls.files}
        sides = sorted((json.loads(p.read_text()) for p in POSTS.glob("*.json")),
                       key=lambda s: s["date"])
        for i, side in enumerate(sides):
            ctx = _build_post_context(side)
            ctx["prev_post"] = sides[i - 1] if i else None
            ctx["next_post"] = sides[i + 1] if i + 1 < len(sides) else None
            before = copy.deepcopy(ctx)
            page = render_historical_brief(ctx)
            if ctx != before:
                raise AssertionError("renderer mutated historical context")
            cls.posts.append((ctx, page, BeautifulSoup(page, "html.parser")))

    def test_every_real_issue_is_exercised(self):
        self.assertEqual(len(self.posts), len(list(POSTS.glob("*.json"))))
        self.assertGreaterEqual(len(self.posts), 14)

    def test_current_shell_and_collection_on_every_direct_article(self):
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                chrome = str(soup.header) + str(soup.footer)
                self.assertIn('aria-label="Indo-Pacific Record home"', chrome)
                self.assertNotIn("China Mil Watch", chrome)
                self.assertNotIn("The PLA Watch", chrome)
                self.assertEqual(soup.select_one('.brief-eyebrow').get_text(strip=True),
                                 "Indo-Pacific Record Briefs")
                self.assertEqual(soup.select_one('meta[property="og:site_name"]')["content"],
                                 "Indo-Pacific Record")
                self.assertFalse(soup.select('meta[name="robots"][content*="noindex"]'))
                self.assertEqual(soup.select_one('link[rel="canonical"]')["href"], ctx["page_url"])

    def test_all_stored_body_paragraphs_remain_identical(self):
        fields = list(SECTIONS) + [
            ("what_im_watching_next", "s-watching", ""),
            ("term_to_know_explanation", "s-term", ""),
        ]
        for ctx, page, soup in self.posts:
            for key, anchor, _ in fields:
                if not ctx.get(key):
                    continue
                with self.subTest(issue=ctx["issue_number"], field=key):
                    actual = [p.get_text() for p in soup.select(f"#{anchor}>p")
                              if "term-word" not in p.get("class", [])]
                    expected = [BeautifulSoup(str(inline_markup(p.strip())), "html.parser").get_text()
                                for p in ctx[key].split("\n\n") if p.strip()]
                    self.assertEqual(actual, expected)

    def test_current_ipr_title_and_social_sharing_preserve_original_citation(self):
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                expected = soup.select_one("#brief-title").get_text() + " — Indo-Pacific Record"
                self.assertEqual(soup.title.get_text(), expected)
                self.assertEqual(soup.select_one('meta[property="og:title"]')["content"], expected)
                self.assertEqual(soup.select_one('meta[name="twitter:title"]')["content"], expected)
                self.assertFalse(expected.startswith("The PLA Watch: "))

    def test_original_citation_is_exactly_the_existing_citation(self):
        old = make_pw_env().get_template("pla-watch-post.html")
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                before = BeautifulSoup(old.render(**ctx), "html.parser").select_one('#pw-cite')
                self.assertEqual(soup.select_one('#pw-cite').get_text(), before.get_text())
                self.assertIn(ctx["publication"], soup.select_one('.historical-provenance').get_text())

    def test_every_source_title_original_url_outlet_date_and_flag_survives(self):
        for ctx, page, soup in self.posts:
            items = soup.select('.historical-source-list>li')
            self.assertEqual(len(items), len(ctx["articles"]))
            for source, item in zip(ctx["articles"], items):
                self.assertEqual(item.a["href"], source["url"])
                self.assertEqual(item.a.get_text(), source["title"])
                original = item.select_one('.source-card-original')
                self.assertEqual(original.get_text() if original else "", source.get("title_zh", ""))
                self.assertIn(source["source"], item.get_text())
                if source.get("date"):
                    self.assertEqual(item.time["datetime"], source["date"])
                self.assertEqual("Model-flagged" in item.get_text(), source["is_significant"])

    def test_historical_author_information_is_labelled_and_unmodified(self):
        for ctx, page, soup in self.posts:
            author = soup.select_one('details.historical-author')
            self.assertEqual(author.summary.get_text(), "Author information at original publication")
            self.assertEqual(author.select_one('.author-block-name').get_text(), ctx["author_name"])
            self.assertEqual(author.select_one('.author-block-title').get_text(), ctx["author_title"])
            self.assertEqual(author.select_one('.author-block-bio').get_text(), ctx["author_bio"])
            self.assertNotIn("China Mil Watch", soup.select_one('.brief-byline').get_text())

    def test_signal_veils_and_credit_survive_all_real_issues(self):
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                original = ctx.get("pw_veil")
                figures = soup.select("figure.historical-veil")
                if not original:
                    self.assertEqual(figures, [])
                    continue
                self.assertEqual(len(figures), 1)
                figure = figures[0]
                self.assertEqual(figure["data-editorial-id"], original["id"])
                self.assertEqual(figure["aria-label"], "Historical visual context, not evidence")
                self.assertEqual(figure.img["src"], original["duo"])
                self.assertEqual(figure.img["alt"], original["alt"])
                self.assertIn(original["mask_focus"], figure.img["style"])
                self.assertEqual(figure.a["href"], original["source_page"])
                self.assertIn(original["source_id"], figure.get_text())
                self.assertIn(original.get("subject") or "", figure.get_text())
                self.assertIn("Context, not evidence", figure.get_text())
                self.assertFalse(soup.select(".brief-opening-photo"),
                    "Resolved Signal Veil replaces in-page cover, not duplicates it")

    def test_replaced_cover_photographs_keep_original_source_credit(self):
        for ctx, page, soup in self.posts:
            if not (ctx.get("pw_veil") and ctx.get("cover_media_item")):
                continue
            with self.subTest(issue=ctx["issue_number"]):
                note = next((p for p in soup.select("#s-snapshot .historical-source-meta")
                             if "Edition cover (link-preview image)" in p.get_text()), None)
                self.assertIsNotNone(note)
                cover = ctx["cover_media_item"]
                self.assertEqual(note.a["href"],
                                 cover.get("source_page") or cover.get("source_url"))
                self.assertIn("visual context only", note.get_text())
                self.assertFalse(soup.select(".brief-opening-photo"))

    def test_signal_veil_without_cover_uses_photo_grid(self):
        context = next(copy.deepcopy(ctx) for ctx, _, _ in self.posts
                       if ctx.get("pw_veil"))
        context["cover_media_item"] = None
        page = render_historical_brief(context)
        soup = BeautifulSoup(page, "html.parser")
        self.assertIn("brief-hero--photo",
                      soup.select_one(".brief-hero").get("class", []))
        self.assertIsNotNone(soup.select_one(
            ".brief-hero-inner > figure.historical-veil"))
        self.assertIn(".historical-veil{grid-area:photo",
                      soup.select_one("style").get_text())
        self.assertEqual(soup.select_one("figure.historical-veil img")["src"],
                         context["pw_veil"]["duo"])

    def test_original_author_links_preserved_and_unsafe_hrefs_rejected(self):
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                anchors = soup.select("details.historical-author .historical-author-links a")
                actual = {a.get_text(): a["href"] for a in anchors}
                self.assertEqual(actual, ctx.get("author_links") or {})
        ctx = copy.deepcopy(self.posts[0][0])
        ctx["author_links"] = {
            "Unsafe": "javascript:alert(1)",
            "Unsafe data": "data:text/html,bad",
            "Unsafe relative": "../../secrets",
            "Valid": "https://example.org/profile",
        }
        rendered = BeautifulSoup(render_historical_brief(ctx), "html.parser")
        self.assertEqual(
            [(a.get_text(), a["href"]) for a in rendered.select(".historical-author-links a")],
            [("Valid", "https://example.org/profile")],
        )

    def test_checked_in_pages_equal_current_sidecar_render(self):
        for ctx, rendered, _ in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                published = POSTS / (ctx["date"] + ".html")
                self.assertEqual(published.read_text(encoding="utf-8"), rendered)

    def test_links_and_assets_use_the_correct_two_level_root(self):
        for ctx, page, soup in self.posts:
            self.assertEqual(soup.select_one('.brand')["href"], '../../index.html')
            self.assertIn('../../analysis.html', [a["href"] for a in soup.header.select('a[href]')])
            self.assertEqual([s["href"] for s in soup.select('link[rel="stylesheet"]')],
                             ['../../fonts.css', '../../styles.css', '../../enrichment.css', '../../briefs.css'])
            self.assertEqual(soup.select_one('script[src]')["src"], '../../shell.js')
            self.assertFalse(soup.select('.publication-freshness'))
            for neighbor in (ctx["prev_post"], ctx["next_post"]):
                if neighbor:
                    self.assertIn(neighbor["date"] + '.html',
                                  [a["href"] for a in soup.select('.historical-issue-nav a')])

    def test_no_invented_dates_source_fields_or_unsafe_markup(self):
        ctx = copy.deepcopy(self.posts[0][0])
        ctx['opening_note'] = '<script>alert(1)</script> <strong>Kept</strong>'
        soup = BeautifulSoup(render_historical_brief(ctx), 'html.parser')
        self.assertFalse(soup.select('#s-opening script'))
        self.assertEqual(soup.select_one('#s-opening strong').get_text(), 'Kept')

    def test_render_is_deterministic_and_canonical_bytes_do_not_change(self):
        ctx, first, _ = self.posts[0]
        self.assertEqual(render_historical_brief(ctx), first)
        self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.files},
                         self.fingerprints)


class HistoricalBriefBrowserTests(unittest.TestCase):
    """Actual current-shell pages: old template browser tests remain rollback QA."""
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.tmp = tempfile.TemporaryDirectory(prefix='ipr-historical-browser-')
        cls.root = Path(cls.tmp.name)
        for name in ('fonts.css', 'styles.css', 'enrichment.css', 'briefs.css', 'shell.js'):
            shutil.copy2(ROOT / 'output' / name, cls.root / name)
        shutil.copytree(ROOT / 'output/assets', cls.root / 'assets')
        for name in ('media', 'covers'):
            shutil.copytree(ROOT / 'output/the-pla-watch' / name,
                            cls.root / 'the-pla-watch' / name)
        posts = cls.root / 'the-pla-watch/posts'
        posts.mkdir()
        cls.routes = []
        for source in sorted(POSTS.glob('*.json')):
            context = _build_post_context(json.loads(source.read_text()))
            route = 'the-pla-watch/posts/' + source.stem + '.html'
            (cls.root / route).write_text(render_historical_brief(context))
            cls.routes.append(route)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        cls.server = socketserver.TCPServer(('127.0.0.1', 0),
            functools.partial(Quiet, directory=str(cls.root)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def visit(self, page, route):
        page.goto(f'http://127.0.0.1:{self.server.server_address[1]}/{route}')
        page.evaluate('document.fonts.ready')

    def test_all_historical_articles_fit_mobile_tablet_and_desktop(self):
        for width in (320, 375, 768, 1280):
            page = self.browser.new_page(viewport={'width': width, 'height': 900})
            failures = []
            page.on('pageerror', lambda e: failures.append(str(e)))
            for route in self.routes:
                with self.subTest(width=width, route=route):
                    self.visit(page, route)
                    dimensions = page.evaluate('({viewport:innerWidth,width:document.documentElement.scrollWidth})')
                    self.assertLessEqual(dimensions['width'], dimensions['viewport'])
                    self.assertEqual(page.locator('h1').count(), 1)
                    self.assertTrue(page.locator('#pw-cite').is_visible())
                    self.assertFalse(failures)
            page.close()

    def test_no_javascript_and_reduced_motion_keep_sources_and_navigation(self):
        for options in ({'java_script_enabled': False}, {'reduced_motion': 'reduce'}):
            context = self.browser.new_context(viewport={'width':375,'height':900}, **options)
            page = context.new_page()
            for route in self.routes:
                with self.subTest(mode=options, route=route):
                    self.visit(page, route)
                    self.assertTrue(page.locator('#s-sources').is_visible())
                    self.assertTrue(page.locator('#pw-cite').is_visible())
                    page.locator('.brief-reading-navigation>summary').click()
                    self.assertTrue(page.locator('.brief-toc a').first.is_visible())
                    page.locator('.historical-author>summary').click()
                    self.assertTrue(page.locator('.author-block-bio').is_visible())
            context.close()

    def test_keyboard_menu_escape_and_skip_link(self):
        page = self.browser.new_page(viewport={'width':375,'height':900})
        self.visit(page, self.routes[0])
        page.keyboard.press('Tab')
        self.assertEqual(page.evaluate('document.activeElement.className'), 'skip')
        page.keyboard.press('Enter')
        self.assertTrue(page.url.endswith('#main'))
        page.keyboard.press('Tab')
        self.assertTrue(page.evaluate('document.activeElement.closest("main")!==null'))
        menu = page.locator('.nav-mobile>summary')
        menu.focus()
        page.keyboard.press('Enter')
        self.assertTrue(page.locator('.nav-mobile').evaluate('(e)=>e.open'))
        page.keyboard.press('Escape')
        self.assertFalse(page.locator('.nav-mobile').evaluate('(e)=>e.open'))
        page.close()

    def test_historical_image_credits_are_readable_on_dark_hero(self):
        from scripts.verify_enrichment_frontend import color_contrast
        page = self.browser.new_page()
        for route in self.routes:
            self.visit(page, route)
            for caption in page.locator('.historical-veil figcaption').all():
                colors = caption.evaluate('(e)=>[getComputedStyle(e).color,getComputedStyle(e.closest(".brief-hero")).backgroundColor]')
                self.assertGreaterEqual(color_contrast(*colors), 4.5, (route, colors))
                for link in caption.locator('a').all():
                    foreground = link.evaluate('(e)=>getComputedStyle(e).color')
                    self.assertGreaterEqual(color_contrast(foreground, colors[1]), 4.5, route)
        page.close()

    def test_local_styles_fonts_scripts_and_photos_resolve(self):
        page = self.browser.new_page()
        failed = []
        page.on('response', lambda response: failed.append(response.url)
                if response.status >= 400 else None)
        for route in self.routes:
            self.visit(page, route)
            self.assertEqual(page.locator('img').evaluate_all(
                '(images)=>images.filter(i=>i.loading!=="lazy" && (!i.complete || !i.naturalWidth)).length'), 0)
        self.assertEqual(failed, [])
        page.close()


if __name__ == '__main__':
    unittest.main()
