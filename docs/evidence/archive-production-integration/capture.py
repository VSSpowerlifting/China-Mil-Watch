"""Reproduce desktop/mobile review evidence from an isolated current render.

Run from the repository root with its Python/Playwright environment. No tracked
output, canonical database, publication register or workflow is written.
"""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tests.test_archive_integration_browser import ArchiveIntegrationBrowser as Build
from core.frontend_budget import measure_page

DEST = Path(__file__).resolve().parent
Build.setUpClass()
try:
    report = measure_page(Build.site / 'archive.html', Build.site)
    report['html_bytes'] = (Build.site / 'archive.html').stat().st_size
    report['javascript_gzip_bytes_separately_encoded'] = sum(len(gzip.compress((Build.site / p).read_bytes(), mtime=0)) for p in report['js'])
    report['index_raw_bytes'] = (Build.site / 'archive-research-index.json').stat().st_size
    report['index_gzip_bytes'] = len(gzip.compress((Build.site / 'archive-research-index.json').read_bytes(), mtime=0))
    report['included'] = len(Build.index['records'])
    report['archive_projection_sha256'] = Build.index['archive_sha256']
    report['record_digest'] = Build.index['digest']
    report['archive_html_sha256'] = hashlib.sha256((Build.site / 'archive.html').read_bytes()).hexdigest()
    for name,width,height in [('desktop',1280,1200),('mobile',375,900)]:
        context=Build.browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce')
        page=context.new_page(); errors=[]; requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda message:errors.append(message.text) if message.type in ('error','warning') else None)
        page.on('request',lambda r:requests.append(r.url))
        page.goto(Build.origin+'/archive.html?scope=published&record_type=human_analysis&keywords=Laos',wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        row=page.locator('#results .record-row').first
        row.locator('input').check(); row.locator('summary').click()
        page.evaluate('scrollTo(0,0)')
        page.screenshot(path=str(DEST/(name+'.jpg')),quality=82,type='jpeg')
        initial_disclosure = page.locator('#research-list').evaluate('e=>e.open')
        page.locator('#research-list').scroll_into_view_if_needed()
        page.screenshot(path=str(DEST/(name+'-compact.jpg')),quality=82,type='jpeg')
        if name == 'mobile':
            page.locator('#research-list > summary').click()
        page.locator('#research-list').scroll_into_view_if_needed()
        page.screenshot(path=str(DEST/(name+'-list.jpg')),quality=82,type='jpeg')
        row.locator('.archive-citation').scroll_into_view_if_needed()
        page.screenshot(path=str(DEST/(name+'-citation.jpg')),quality=82,type='jpeg')
        cdp=context.new_cdp_session(page); cdp.send('DOM.enable'); cdp.send('CSS.enable')
        document=cdp.send('DOM.getDocument')['root']['nodeId']
        fonts={}
        for label,selector in [('title','#results h3 a'),('control','label[for="f-q"]')]:
            node=cdp.send('DOM.querySelector',{'nodeId':document,'selector':selector})['nodeId']
            fonts[label]=cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
            assert any(font['isCustomFont'] and font['glyphCount']>0 for font in fonts[label]),fonts
        report[name]={'actual_glyph_fonts':fonts,'console_errors':errors,'unexpected_requests':[u for u in requests if not u.startswith(Build.origin)],
                      'scroll_width':page.evaluate('document.documentElement.scrollWidth'),
                      'research_list_expanded':initial_disclosure,
                      'title_font':row.locator('h3').evaluate('e=>getComputedStyle(e).fontFamily'),
                      'control_font':page.locator('#f-q').evaluate('e=>getComputedStyle(e).fontFamily')}
        context.close()
    (DEST/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('assets','css','js')},indent=2))
finally:
    Build.tearDownClass()
