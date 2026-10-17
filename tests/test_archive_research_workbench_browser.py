"""Real Chromium interactions against the private loopback build, never output/."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from playwright.sync_api import sync_playwright

from research.archive_workbench.build import ROOT, build
from research.archive_workbench.corpus import SCHEMA
from research.archive_workbench.serve import server
from tests.test_archive_research_workbench import fixture


class WorkbenchBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/'build').mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='workbench-browser-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.path, cls.metrics = build(Path(cls.temp.name)/'preview')
        cls.http = server(cls.path,0)
        cls.thread = threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.http.server_close)
        cls.addClassCleanup(cls.http.shutdown)
        cls.url = 'http://127.0.0.1:%d/' % cls.http.server_port
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as error:
            raise unittest.SkipTest('Chromium unavailable: '+str(error)[:150])
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':1280,'height':1000},
            permissions=['clipboard-read','clipboard-write'],accept_downloads=True)
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors, self.network = [], []
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.on('console',lambda m:self.errors.append(m.text) if m.type=='error' else None)
        self.page.on('request',lambda r:self.network.append(r.url))

    def ready(self, suffix=''):
        self.page.goto(self.url+suffix)
        self.page.wait_for_function("() => /[0-9]+ results?/.test(document.querySelector('#count').textContent)")

    def test_search_filter_sort_open_copy_export_reload_back_forward(self):
        p = self.page
        self.ready()
        p.get_by_label('Search archive',exact=True).fill('maritime')
        p.get_by_role('button',name='Search',exact=True).click()
        self.assertIn('q=maritime',p.url)
        self.assertEqual(p.locator('#count').inner_text(),'33 results')
        p.locator('#desk').select_option('singapore')
        filtered_count = p.locator('#count').inner_text()
        self.assertNotEqual(filtered_count,'33 results')
        p.locator('#sort').select_option('oldest')
        self.assertTrue(all('singapore' in item for item in p.locator('.result .metadata').all_text_contents()[::2]))
        first = p.locator('.result').first
        first.locator('input[type=checkbox]').check()
        first.locator('input[type=checkbox]').check()  # Duplicate attempt is idempotent.
        self.assertEqual(p.locator('#selection-count').inner_text(),'1 selected')
        first.locator('summary').click()
        citation = first.locator('.citation').inner_text()
        first.get_by_role('button',name='Copy citation',exact=True).click()
        p.wait_for_function("() => document.querySelector('.result details [role=status]').textContent==='Citation copied.'")
        self.assertEqual(p.evaluate('navigator.clipboard.readText()'),citation)
        canonical = first.get_by_role('link',name='Open IPR record').get_attribute('href')
        self.context.route('https://indopacificrecord.org/**',lambda route:route.fulfill(status=200,body='<title>Canonical destination fixture</title>'))
        with p.expect_popup() as opened:
            first.get_by_role('link',name='Open IPR record').click()
        opened.value.wait_for_load_state()
        self.assertEqual(opened.value.url,canonical)
        opened.value.close()
        with p.expect_download() as download:
            p.get_by_role('button',name='Export CSV',exact=True).click()
        raw = Path(download.value.path()).read_text(encoding='utf-8-sig')
        self.assertIn('As held.',raw); self.assertNotIn('text_original',raw)
        with p.expect_download() as download:
            p.get_by_role('button',name='Export JSON',exact=True).click()
        saved = json.loads(Path(download.value.path()).read_text())
        self.assertEqual(len(saved['records']),1)
        selected = saved['records'][0]['id']
        p.reload(); p.wait_for_function("() => /[0-9]+ results?/.test(document.querySelector('#count').textContent)")
        self.assertEqual(p.locator('#selection-count').inner_text(),'1 selected')
        self.assertEqual(p.locator('#sort').input_value(),'oldest')
        self.assertTrue(p.locator('input[data-record-id="'+selected+'"]').is_checked())
        p.go_back(); self.assertEqual(p.locator('#sort').input_value(),'relevance')
        p.go_back(); self.assertEqual(p.locator('#desk').input_value(),'')
        p.go_forward(); self.assertEqual(p.locator('#desk').input_value(),'singapore')
        # Runtime search/filter/export performs no unexpected network requests.
        self.assertTrue(all(url.startswith(self.url) for url in self.network),self.network)
        self.assertEqual(self.errors,[])

    def test_keyboard_focus_narrow_layout_reduced_motion_and_announcements(self):
        p = self.page; self.context.set_default_timeout(5000)
        p.set_viewport_size({'width':375,'height':900}); p.emulate_media(reduced_motion='reduce')
        self.ready()
        p.keyboard.press('Tab')
        self.assertEqual(p.locator(':focus').inner_text(),'Skip to search')
        p.keyboard.press('Enter')
        self.assertEqual(p.locator(':focus').get_attribute('id'),'query')
        outline = p.locator('#query').evaluate('(e)=>getComputedStyle(e).outlineWidth')
        self.assertEqual(outline,'3px')
        p.keyboard.type('nonexistent-token'); p.keyboard.press('Enter')
        self.assertEqual(p.locator('#count').inner_text(),'0 results')
        self.assertTrue(p.locator('#empty').is_visible())
        self.assertEqual(p.locator('#count').get_attribute('aria-live'),'polite')
        self.assertEqual(p.locator('#count').get_attribute('aria-atomic'),'true')
        self.assertTrue(p.get_by_role('button',name='Remove Search filter').is_visible())
        for width in (320,375,768,1280):
            p.set_viewport_size({'width':width,'height':900})
            self.assertTrue(p.evaluate('document.documentElement.scrollWidth<=innerWidth'),width)
        p.locator('#reset').click()
        self.assertEqual(p.locator('#query').input_value(),'')
        p.go_back(); self.assertEqual(p.locator('#query').input_value(),'nonexistent-token')
        self.assertEqual(self.errors,[])

    def test_untrusted_html_script_links_exports_and_unknown_fields_stay_inert(self):
        rows = fixture()['records']
        evil = '<img src=x onerror="window.__payload=1"><script>window.__payload=2</script>'
        rows[0] = dict(rows[0], title=evil, summary='=HYPERLINK("https://example.org")',
                       secret='private field', ipr_url='javascript:window.__payload=3')
        rows[1]['title'] = '+SUM(1,2)'
        p = self.page
        p.route('**/index.json',lambda route:route.fulfill(content_type='application/json',body=json.dumps({'schema':SCHEMA,'records':rows})))
        manifest = json.loads((self.path/'manifest.json').read_text());manifest['included']=len(rows)
        p.route('**/manifest.json',lambda route:route.fulfill(content_type='application/json',body=json.dumps(manifest)))
        self.ready('?q=onerror')
        self.assertEqual(p.locator('#count').inner_text(),'1 result')
        self.assertIn('<script>',p.locator('.result h3').inner_text())
        self.assertEqual(p.locator('.result img,.result script').count(),0)
        self.assertIsNone(p.evaluate('window.__payload'))
        self.assertEqual(p.locator('.result a').count(),0)
        p.locator('.result input').check()
        with p.expect_download() as download:p.locator('#export-csv').click()
        csv = Path(download.value.path()).read_text(encoding='utf-8-sig')
        self.assertIn("'=HYPERLINK",csv);self.assertNotIn('private field',csv)
        p.locator('#query').fill('metadata-only');p.locator('.primary').click()
        self.assertEqual(p.locator('#count').inner_text(),'1 result')
        self.assertIn('Publication date not recorded',p.locator('.result').inner_text())
        self.assertNotIn('Secret needle',p.locator('.result').inner_text())
        self.assertEqual(self.errors,[])

    def test_large_malformed_shared_queries_fail_gracefully(self):
        from urllib.parse import urlencode
        p=self.page
        for query in ({'q':'x'*513},{'q':'"unclosed'},{'source':'x'*600},{'from':'2026-02-30'},{'sort':'unknown'}):
            p.goto(self.url+'?'+urlencode(query));p.locator('#error').wait_for(state='visible')
            self.assertEqual(p.locator('#results .result').count(),0)
            p.locator('#reset').click()
            self.assertIn('results',p.locator('#count').inner_text())
        self.assertEqual(self.errors,[])

    def test_private_headers_host_guard_noindex_and_no_directory_listing(self):
        with urlopen(self.url) as r:
            self.assertEqual(r.headers['X-Robots-Tag'],'noindex, nofollow, noarchive')
            self.assertIn("connect-src 'self'",r.headers['Content-Security-Policy'])
            self.assertEqual(r.headers['Cache-Control'],'no-store')
            self.assertIn(b'content="noindex',r.read())
        for path in ('.ipr-private-preview','assets/'):
            with self.assertRaises(HTTPError):urlopen(self.url+path)
        with self.assertRaises(HTTPError):urlopen(Request(self.url,headers={'Host':'untrusted.example'}))
        with urlopen(self.url+'robots.txt') as r:self.assertIn(b'Disallow: /',r.read())
        self.assertFalse((self.path/'sitemap.xml').exists())

    def test_real_font_files_load_and_render_instead_of_system_fallbacks(self):
        p = self.page
        responses = []
        p.on('response', lambda r: responses.append((r.url, r.status)) if '/assets/fonts/' in r.url else None)
        self.ready('?q=maritime')
        p.wait_for_function("() => document.fonts.status === 'loaded'")
        for file in ('instrument-serif-1.woff2', 'inter-0.woff2', 'source-serif-4-1.woff2'):
            self.assertIn((self.url + 'assets/fonts/' + file, 200), responses)
            self.assertEqual((self.path / 'assets/fonts' / file).read_bytes(), (ROOT / 'site/assets/fonts' / file).read_bytes())
        expected = {'h1':('Instrument Serif', 'InstrumentSerif'), '.result h3':('Source Serif 4', 'SourceSerif4'),
                    '#desk':('Inter', 'Inter-Regular'), '.metadata':('Inter', 'Inter-Regular')}
        cdp = self.context.new_cdp_session(p)
        cdp.send('DOM.enable'); cdp.send('CSS.enable')
        document = cdp.send('DOM.getDocument')['root']['nodeId']
        for selector, (family, postscript) in expected.items():
            computed = p.locator(selector).first.evaluate('(e) => ({family:getComputedStyle(e).fontFamily,weight:getComputedStyle(e).fontWeight})')
            self.assertIn(family, computed['family'])
            self.assertEqual(computed['weight'], '400')
            ident = cdp.send('DOM.querySelector', {'nodeId':document, 'selector':selector})['nodeId']
            fonts = cdp.send('CSS.getPlatformFontsForNode', {'nodeId':ident})['fonts']
            self.assertTrue(any(f['isCustomFont'] and postscript in f['postScriptName'] and f['glyphCount'] > 0 for f in fonts), (selector, fonts))
        for selector in ('#query', '#source', '#issuer', '#from', '#to', '#sort', '.primary'):
            computed = p.locator(selector).evaluate('(e) => ({family:getComputedStyle(e).fontFamily,weight:getComputedStyle(e).fontWeight})')
            self.assertIn('Inter', computed['family']); self.assertEqual(computed['weight'], '400')
        self.assertEqual(self.errors, [])

    def test_more_filters_keyboard_url_restore_removal_and_mobile_layout(self):
        p = self.page
        self.ready('?q=maritime')
        disclosure = p.locator('#more-filters > summary')
        self.assertFalse(p.locator('#source').is_visible())
        self.assertTrue(p.locator('#desk').is_visible()); self.assertTrue(p.locator('#record_type').is_visible())
        disclosure.focus(); p.keyboard.press('Enter')
        self.assertTrue(p.locator('#source').is_visible())
        p.locator('#source').select_option('MINDEF Singapore — official releases')
        p.locator('#from').fill('2026-10-01'); p.locator('#from').dispatch_event('change')
        p.locator('#to').fill('2026-10-15'); p.locator('#to').dispatch_event('change')
        self.assertEqual(p.locator('#more-filter-count').inner_text().strip(), '(3)')
        self.assertIn('source’s publication date', p.locator('#date-help').inner_text())
        self.assertIn('recorded IPR publication dates', p.locator('#date-help').inner_text())
        p.reload(); p.wait_for_function("() => document.querySelector('#count').textContent.includes('results')")
        self.assertTrue(p.locator('#source').is_visible())
        self.assertEqual(p.locator('#from').input_value(), '2026-10-01')
        for width in (320, 375, 768, 1280):
            p.set_viewport_size({'width':width, 'height':900})
            self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth'), width)
        disclosure.click()
        self.assertFalse(p.locator('#source').is_visible())
        remove = p.get_by_role('button', name='Remove Source filter', exact=True)
        self.assertTrue(remove.is_visible()); remove.click()
        self.assertEqual(p.locator(':focus').inner_text(), 'More filters (2)')
        self.assertNotIn('source=', p.url)
        p.go_back(); self.assertEqual(p.locator('#source').input_value(), 'MINDEF Singapore — official releases')
        self.assertTrue(p.locator('#source').is_visible())
        p.locator('#reset').click(); self.assertFalse(p.locator('#source').is_visible())
        self.assertEqual(p.locator('#query').input_value(), '')
        self.assertEqual(self.errors, [])

    def test_full_provenance_citations_exports_and_specific_holds_survive_quieter_rows(self):
        p = self.page
        self.ready('?q=maritime')
        first = p.locator('.result').first
        ident = first.get_attribute('data-record-id')
        records = json.loads((self.path/'index.json').read_text())['records']
        r = next(r for r in records if r['id'] == ident)
        self.assertIn('not human-reviewed', first.locator('.processing').inner_text())
        self.assertFalse(first.locator('.provenance-notes').is_visible())
        first.locator('summary').click()
        self.assertIn(r['processing'], first.locator('.provenance-notes').inner_text())
        self.assertIn(r['date_kind'], first.locator('.provenance-notes').inner_text())
        self.assertEqual(first.locator('.citation').inner_text(), r['citation'])
        first.locator('input[type=checkbox]').check()
        with p.expect_download() as download: p.locator('#export-json').click()
        selected = json.loads(Path(download.value.path()).read_text())['records']
        self.assertEqual(selected, [r])
        p.locator('#query').fill('156785161'); p.locator('.primary').click()
        self.assertTrue(p.locator('.result .hold').is_visible())
        self.assertIn('unresolved excavation-year discrepancy', p.locator('.hold').inner_text())
        self.assertFalse(p.locator('.result .provenance-notes').is_visible())
        self.assertEqual(self.errors, [])


    def test_mobile_research_disclosure_empty_keyboard_semantics_and_desktop(self):
        p = self.page
        p.set_viewport_size({'width':375, 'height':900})
        self.ready('?q=maritime')
        disclosure = p.locator('#research-disclosure')
        summary = p.locator('.research-summary')
        self.assertEqual(summary.inner_text(), 'Research list · 0')
        self.assertEqual(p.locator('#selection-count').get_attribute('aria-live'), 'off')
        self.assertEqual(p.locator('#research-notice').get_attribute('aria-live'), 'polite')
        self.assertFalse(disclosure.evaluate('(e) => e.open'))
        self.assertFalse(p.locator('#export-csv').is_visible())
        self.assertLess(p.locator('#research-list').bounding_box()['height'], 50)
        self.assertLess(p.locator('.result h3').first.bounding_box()['y'], 850)
        cdp = self.context.new_cdp_session(p)
        def expanded():
            nodes = cdp.send('Accessibility.getFullAXTree')['nodes']
            node = next(n for n in nodes if n.get('role',{}).get('value') == 'DisclosureTriangle'
                        and n.get('name',{}).get('value','').startswith('Research list'))
            return next(v['value']['value'] for v in node['properties'] if v['name'] == 'expanded')
        self.assertFalse(expanded())
        summary.focus(); p.keyboard.press('Enter')
        self.assertTrue(expanded()); self.assertTrue(p.locator('#export-csv').is_visible())
        self.assertFalse(p.locator('#export-csv').is_enabled())
        p.keyboard.press('Space'); self.assertFalse(expanded())
        for width in (320, 375, 680, 1280):
            p.set_viewport_size({'width':width, 'height':900})
            if width <= 680:
                summary.click()
            self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth'), width)
        self.assertTrue(disclosure.evaluate('(e) => e.open'))
        self.assertFalse(summary.is_visible())
        self.assertEqual(p.locator('#selection-count').get_attribute('aria-live'), 'polite')
        self.assertTrue(p.get_by_role('heading', name='Your research list').is_visible())
        self.assertTrue(p.locator('#export-csv').is_visible())
        self.assertEqual(self.errors, [])

    def test_mobile_selection_discovery_without_focus_or_scroll_and_restoration(self):
        p = self.page
        p.set_viewport_size({'width':375, 'height':900})
        self.ready('?q=maritime')
        checkbox = p.locator('.result input').first
        ident = checkbox.get_attribute('data-record-id')
        summary = p.locator('.research-summary')
        disclosure = p.locator('#research-disclosure')
        checkbox.focus()
        before = checkbox.bounding_box()['y']; scroll = p.evaluate('scrollY')
        p.keyboard.press('Space')
        self.assertTrue(checkbox.is_checked())
        self.assertEqual(p.locator(':focus').get_attribute('data-record-id'), ident)
        self.assertEqual(p.evaluate('scrollY'), scroll)
        self.assertAlmostEqual(checkbox.bounding_box()['y'], before, delta=1)
        self.assertFalse(disclosure.evaluate('(e) => e.open'))
        self.assertEqual(p.locator('#research-mobile-count').inner_text(), '1')
        self.assertTrue(p.locator('#research-export-hint').is_visible())
        self.assertIn('citations are beside each result', p.locator('#research-notice').text_content())
        self.assertTrue(p.locator('.result summary').first.is_visible())
        p.keyboard.press('Space')
        self.assertEqual(p.locator('#research-mobile-count').inner_text(), '0')
        self.assertFalse(p.locator('#research-export-hint').is_visible())
        self.assertFalse(disclosure.evaluate('(e) => e.open'))
        p.keyboard.press('Space'); p.reload()
        p.wait_for_function("() => document.querySelector('#research-mobile-count').textContent === '1'")
        self.assertFalse(disclosure.evaluate('(e) => e.open'))
        self.assertTrue(p.locator('input[data-record-id="'+ident+'"]').is_checked())
        self.assertTrue(p.locator('#research-export-hint').is_visible())
        summary.focus(); p.keyboard.press('Enter')
        self.assertTrue(p.locator('#export-csv').is_enabled())
        self.assertTrue(p.locator('#export-json').is_enabled())
        self.assertTrue(p.locator('#selected-list').is_visible())
        for width in (320,375,680):
            p.set_viewport_size({'width':width, 'height':900})
            self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth'), width)
        p.locator('#clear-selection').click()
        self.assertEqual(p.locator('#research-mobile-count').inner_text(), '0')
        self.assertTrue(disclosure.evaluate('(e) => e.open'))
        self.assertEqual(p.locator(':focus').get_attribute('id'), 'selection-count')
        self.assertFalse(p.locator('#export-csv').is_enabled())
        summary.focus(); p.keyboard.press('Space')
        self.assertFalse(disclosure.evaluate('(e) => e.open'))
        p.reload(); p.wait_for_function("() => document.querySelector('#count').textContent.includes('results')")
        self.assertEqual(summary.inner_text(), 'Research list · 0')
        self.assertFalse(disclosure.evaluate('(e) => e.open'))
        self.assertEqual(self.errors, [])
