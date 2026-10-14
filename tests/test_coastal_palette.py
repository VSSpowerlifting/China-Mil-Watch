"""Coastal semantic roles, first-party paint guard and real-browser contrast.
The guard examines styles and SVG paint, never manuscript text, photos, flags
or archival source documents. Production output and editorial records are read-only.
"""
import colorsys
import json
import re
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from tests.test_palette_and_accessibility import contrast, tokens

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / 'site/preview'
WARNING_PAINT = {'#87511a', '#d9be9c', '#93621d'}


def retired_paint(style):
    style = re.sub(r'/\*.*?\*/', '', style, flags=re.S)
    def rgb_hex(match):
        channels = [float(n) for n in re.findall(r'[0-9.]+', match.group())][:3]
        return '#' + ''.join('%02x' % max(0, min(255, round(n))) for n in channels)
    def hsl_hex(match):
        hue, saturation, lightness = [float(n) for n in re.findall(r'[0-9.]+', match.group())][:3]
        channels = colorsys.hls_to_rgb((hue % 360)/360, lightness/100, saturation/100)
        return '#' + ''.join('%02x' % round(n*255) for n in channels)
    style = re.sub(r'hsla?\(\s*[0-9.]+(?:deg)?[ ,]+[0-9.]+%[ ,]+[0-9.]+%[^)]*\)', hsl_hex, style)
    style = re.sub(r'rgba?\([^)]*\)', rgb_hex, style)
    found = []
    for match in re.finditer(r'#[0-9a-fA-F]{3,8}\b|\b(?:red|crimson|pink|salmon|tomato|firebrick|maroon|coral|purple)\b', style):
        value = match.group().lower()
        if not value.startswith('#'):
            found.append(value); continue
        if value in WARNING_PAINT:
            continue
        digits = value[1:]
        if len(digits) in (3, 4): digits = ''.join(c * 2 for c in digits)
        if len(digits) not in (6, 8): continue
        rgb = [int(digits[i:i+2], 16)/255 for i in (0, 2, 4)]
        hue, light, saturation = colorsys.rgb_to_hls(*rgb)
        # Red through rust, and pink/purple: exempt desaturated warm neutrals.
        if saturation > .2 and (hue < .10 or hue > .75):
            found.append(value)
    return found


class CoastalPalette(unittest.TestCase):
    def test_active_first_party_styles_and_inline_paint_use_coastal_colors(self):
        for path in PREVIEW.glob('*.css'):
            with self.subTest(path=path.name):
                self.assertEqual(retired_paint(path.read_text()), [])
        for path in (PREVIEW / 'templates').glob('*.html'):
            html = path.read_text()
            paint = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', html, re.S))
            paint += '\n'.join(re.findall(r'\b(?:fill|stroke|style)=["\']([^"\']*)', html))
            with self.subTest(path=path.name):
                self.assertEqual(retired_paint(paint), [])

    def test_guard_rejects_reintroduced_red_and_ignores_source_text(self):
        for value in ('#B3132B', '#D4845F', '#F07A8A', 'crimson', '#f88', 'rgb(179, 19, 43)', 'rgba(212, 132, 95, .5)', 'hsl(0 100% 50%)'):
            self.assertTrue(retired_paint('color:'+value))
        self.assertEqual(retired_paint('/* archival source says crimson */ color:#C6B79B'), [])

    def test_edition_plate_keeps_machine_tick_height_and_semantic_roles(self):
        env = Environment(loader=FileSystemLoader(PREVIEW/'templates'))
        plate = {'ticks':[False, True], 'issue':1, 'series_name':'Fixture', 'week_ending':'2026-05-09'}
        html = env.get_template('_plate.html').module.edition_plate(plate,'fixture','Fixture')
        self.assertIn('fill="var(--editorial-on-dark)"', html)
        self.assertRegex(html, r'height="30" fill="var\(--machine-on-dark\)" class="tick tick--flagged"')
        self.assertRegex(html, r'height="18" fill="#5C6570" class="tick"')
        self.assertIn('aria-labelledby="fixture"', html)

    def test_semantic_names_replace_retired_names_without_aliases(self):
        names = tokens()
        self.assertFalse(any(n.startswith(('--crimson','--signal')) for n in names))
        for role in ('editorial', 'machine'):
            self.assertIn('--'+role+'-ink', names)
            self.assertIn('--'+role+'-on-dark', names)


    def test_approved_laos_public_markup_uses_structured_reading_with_coastal_css(self):
        """After approved PR #565, guard the public v2 article against palette drift.

        This checks the tracked public HTML's manuscript/presentation contract
        against the proposed palette source. It does NOT claim generated output
        CSS is updated before the separate render-only release.
        """
        from core.brief_presentation import presentation_html_errors
        from core.brief_source_linked import manuscript_html_errors

        slug = 'what-is-being-built-in-laos'
        manifest = json.loads((ROOT / 'briefs/presentation' / (slug + '.json')).read_text())
        if manifest['status'] != 'approved':
            self.skipTest('Laos presentation was not yet approved at this branch base')
        article = json.loads((ROOT / 'briefs' / (slug + '.json')).read_text())
        public_path = ROOT / 'output/briefs' / (slug + '.html')
        html = public_path.read_text()
        self.assertIn('brief-layout--structured', html)
        self.assertIn('class="brief-reading-finding"', html)
        self.assertEqual(manuscript_html_errors(article, html), [])
        self.assertEqual(presentation_html_errors(manifest, html), [])
        css = (PREVIEW / 'briefs.css').read_text()
        # The unified Briefs reading system (PR #567) deliberately keeps
        # turquoise for its Signal/finding components. Semantic jade still
        # marks human analysis on the other public surfaces.
        self.assertIn('var(--accent)', css)
        self.assertIn('var(--accent-ink)', css)
        self.assertNotIn('var(--crimson', css)


class BrowserRoles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as exc:
            cls.pw.stop()
            raise unittest.SkipTest('Chromium unavailable: '+str(exc))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def test_rendered_labels_states_shapes_focus_and_system_colors(self):
        css = '\n'.join((PREVIEW/n).read_text() for n in ('styles.css','home.css','record.css','briefs.css'))
        page = self.browser.new_page()
        try:
            page.set_content('<style>'+css+'</style><main><a id="paper" href="#dark">Paper link</a>'
                '<p class="evidence evidence--record">Source record</p>'
                '<p id="machine" class="evidence evidence--model">Machine output</p>'
                '<p id="human" class="evidence evidence--analysis">Human analysis</p>'
                '<p class="state state--analyzed">Analyzed</p>'
                '<p class="trail-tag">In an analysis source trail</p>'
                '<p class="desk-state desk-state--live">Live collecting</p>'
                '<p class="desk-state desk-state--access_blocked">Access blocked</p>'
                '<aside class="brief-reading-finding"><h2>Central finding</h2></aside>'
                '<section class="band"><a id="dark" href="#paper">Dark link</a>'
                '<p id="dark-machine" class="evidence evidence--model">Machine output</p>'
                '<p id="dark-human" class="evidence evidence--analysis">Human analysis</p></section>'
                '<section class="home-coast-band"><p id="home-human" class="evidence evidence--analysis">Human-controlled analysis</p></section>'
                '<header class="brief-hero"><h1>Brief title</h1></header><section class="pacific-opening"><h1>Home title</h1><a class="btn" href="#paper">Print action</a></section>'
                '<ul class="custody"><li class="is-machine"><b>Machine reading</b></li>'
                '<li class="is-analysis"><b>Analysis</b></li></ul></main>')
            def rgb(value):
                channels = [int(x) for x in re.findall(r'\d+',value)[:3]]
                return '#'+''.join('%02x'%v for v in channels)
            for selector, ground in [('#machine','bg'),('#human','bg'),('.state--analyzed','machine-tint'),
                    ('.trail-tag','accent-tint'),('.desk-state--live','bg'),('.desk-state--access_blocked','bg'),
                    ('#dark-machine','band'),('#dark-human','band'),('.brief-reading-finding h2','bg')]:
                actual=page.locator(selector).evaluate('(el)=>getComputedStyle(el).color')
                self.assertGreaterEqual(contrast(rgb(actual),tokens()['--'+ground]),4.5,selector)
            for selector, expected in [('#machine','dotted'),('#human','none')]:
                self.assertEqual(page.locator(selector).evaluate('(el)=>getComputedStyle(el,"::before").borderTopStyle'),expected)
            for selector in ('#dark-human', '#home-human'):
                color=page.locator(selector).evaluate('(el)=>getComputedStyle(el,"::before").backgroundColor')
                self.assertGreaterEqual(contrast(rgb(color),tokens()['--band']),3,selector)
            shapes = [page.locator('.custody .'+name).evaluate('(el)=>{let s=getComputedStyle(el,"::before");return [s.width,s.height,s.borderRadius]}') for name in ('is-machine','is-analysis')]
            self.assertNotEqual(*shapes)
            page.keyboard.press('Tab')
            self.assertTrue(page.locator('#paper').evaluate('(el)=>el.matches(":focus-visible")'))
            for selector, ground in [('#paper','bg'),('#dark','band')]:
                page.locator(selector).focus()
                outline=page.locator(selector).evaluate('(el)=>{let s=getComputedStyle(el);return [s.outlineStyle,s.outlineColor]}')
                self.assertEqual(outline[0],'solid')
                self.assertGreaterEqual(contrast(rgb(outline[1]),tokens()['--'+ground]),3)
            for mode in ('print','forced'):
                page.emulate_media(media='print' if mode=='print' else 'screen',forced_colors='active' if mode=='forced' else 'none')
                self.assertIn('Human analysis',page.inner_text('body'))
                self.assertIn('Machine output',page.inner_text('body'))
                if mode=='print':
                    for selector in ('.brief-hero', '.pacific-opening'):
                        self.assertEqual(rgb(page.locator(selector).evaluate('(el)=>getComputedStyle(el).backgroundColor')),'#ffffff')
                    self.assertEqual(rgb(page.locator('.btn').evaluate('(el)=>getComputedStyle(el).color')),'#000000')
                    marker=page.locator('#dark-machine').evaluate('(el)=>getComputedStyle(el,"::before").borderTopColor')
                    self.assertEqual(rgb(marker),'#000000')
                    marker=page.locator('#home-human').evaluate('(el)=>getComputedStyle(el,"::before").backgroundColor')
                    self.assertEqual(rgb(marker),'#000000')
                if mode=='forced':
                    page.locator('#paper').focus()
                    self.assertNotEqual(page.locator('#paper').evaluate('(el)=>getComputedStyle(el).outlineStyle'),'none')
        finally:
            page.close()
