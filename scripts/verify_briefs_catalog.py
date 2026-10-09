#!/usr/bin/env python3
"""Browser/integrity review for the production Briefs catalog pilot.

Serve released, current-main baseline and candidate trees on loopback. Captures
are actual Chromium images, never concepts; no editorial source is requested.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def body_contract(path):
    soup = BeautifulSoup(Path(path).read_text(), 'html.parser')
    for node in soup.select('script, style, [aria-hidden="true"]'):
        node.decompose()
    return {'text': ' '.join(soup.body.get_text(' ', strip=True).split()),
            'links': [a.get('href') for a in soup.body.select('a[href]')],
            'ids': [node['id'] for node in soup.select('[id]')]}


def verify(url, baseline_url, released_url, root, baseline, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    expected = body_contract(Path(baseline) / 'analysis.html')
    actual = body_contract(Path(root) / 'analysis.html')
    assert actual == expected, 'Catalog publication text, links or anchors changed'
    for href in actual['links']:
        parts = urlsplit(href)
        if not parts.scheme and not parts.netloc and parts.path:
            assert (Path(root) / parts.path).is_file(), href
    assert len(actual['ids']) == len(set(actual['ids']))
    receipt = {'publication_links_preserved': len(actual['links']), 'exact_body_contract': True,
               'cases': [], 'flows': [], 'errors': [], 'delivery': [], 'concept_images': False}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); receipt['browser'] = browser.version
        for width in (320, 375, 768, 960, 1280, 1440):
            for profile in ('default', 'no-js', 'script-failure', 'reduced-motion', 'no-anim', 'forced-colors', 'print'):
                context = browser.new_context(viewport={'width': width, 'height': 844 if width < 600 else 1000},
                                              java_script_enabled=profile != 'no-js',
                                              reduced_motion='reduce' if profile == 'reduced-motion' else 'no-preference')
                page = context.new_page()
                page.on('pageerror', lambda e: receipt['errors'].append(str(e)))
                page.on('response', lambda r: receipt['errors'].append(str(r.status) + ' ' + r.url) if r.status >= 400 else None)
                if profile == 'script-failure': page.route('**/*.js', lambda r: r.abort())
                if profile == 'no-anim': page.add_init_script('document.addEventListener("DOMContentLoaded",()=>document.documentElement.classList.add("no-anim"))')
                if profile == 'forced-colors': page.emulate_media(forced_colors='active')
                if profile == 'print': page.emulate_media(media='print')
                page.goto(url + '/analysis.html', wait_until='networkidle'); page.evaluate('document.fonts.ready')
                assert page.locator('h1').count() == 1
                assert page.locator('.issue-ledger-row').count() == len(BeautifulSoup((Path(baseline) / 'analysis.html').read_text(), 'html.parser').select('.issue-ledger-row'))
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), (width, profile, 'overflow')
                assert page.locator('.briefs-masthead').is_visible() and page.locator('.briefs-lead').is_visible()
                assert page.locator('.terrain-stage').evaluate_all('(els)=>els.every(e=>e.getAttribute("aria-hidden")==="true" && getComputedStyle(e).pointerEvents==="none")')
                if profile in ('no-js', 'script-failure', 'reduced-motion', 'no-anim'):
                    assert float(page.locator('.terrain-lines').first.evaluate('(e)=>getComputedStyle(e).opacity')) >= .75, (width, profile, 'finished artwork')
                    assert page.locator('.terrain-lines').first.evaluate('(e)=>getComputedStyle(e).transform') == 'none'
                if profile in ('forced-colors', 'print'):
                    assert not page.locator('.terrain-stage').first.is_visible()
                    assert page.locator('body').evaluate('(e)=>getComputedStyle(e).backgroundImage') == 'none'
                if profile == 'print':
                    assert page.locator('h1').evaluate('(e)=>getComputedStyle(e).color') == 'rgb(0, 0, 0)'
                if profile == 'default' and width in (375, 768, 1440):
                    device = {375:'mobile',768:'tablet',1440:'desktop'}[width]
                    page.screenshot(path=str(out / ('briefs-' + device + '.png')))
                    page.screenshot(path=str(out / ('briefs-' + device + '-full.jpg')), full_page=True, type='jpeg', quality=85)
                summary = page.locator('.nav-mobile>summary' if width <= 900 else '.nav-more>summary')
                if profile != 'print':
                    summary.focus();page.keyboard.press('Enter')
                    assert summary.evaluate('(e)=>e.parentElement.open'), (width, profile, 'menu open')
                    page.keyboard.press('Escape')
                    if profile not in ('script-failure', 'no-js'):
                        assert not summary.evaluate('(e)=>e.parentElement.open')
                        assert summary.evaluate('(e)=>e===document.activeElement')
                    else:
                        page.keyboard.press('Enter')  # Native close if shell is unavailable.
                case = {'width': width, 'profile': profile, 'title_box': page.locator('h1').bounding_box()}
                receipt['cases'].append(case)
                context.close()
        # Keyboard journey: skip, native menu, catalog anchor, row focus, Brief.
        context = browser.new_context(viewport={'width':375,'height':844})
        page = context.new_page();page.goto(url + '/analysis.html', wait_until='networkidle')
        page.keyboard.press('Tab');assert page.locator(':focus').get_attribute('class') == 'skip'
        page.keyboard.press('Enter');assert page.url.endswith('#main')
        page.locator('.briefs-browse a').first.focus();page.keyboard.press('Enter')
        assert page.url.endswith('#briefs-published')
        assert page.locator('#briefs-published').bounding_box()['y'] >= 0
        link = page.locator('.issue-ledger-row h3 a').first;link.focus()
        assert link.evaluate('(e)=>getComputedStyle(e).outlineStyle') == 'solid'
        page.wait_for_function('parseFloat(getComputedStyle(document.querySelector(".issue-ledger-row"),"::before").opacity) >= .8')
        page.screenshot(path=str(out / 'briefs-mobile-focus.png'))
        page.keyboard.press('Enter');page.wait_for_url('**/briefs/trident-resolve-regional-scale-specific-chinese-tasks.html')
        assert page.locator('h1').count() == 1
        receipt['flows'].append('Keyboard skip, Browse anchor, visible row focus and native Brief navigation')
        # Mouse hover tint is instant/stable after a short opacity response.
        page.goto(url + '/analysis.html',wait_until='networkidle')
        page.set_viewport_size({'width':1440,'height':1000})
        link=page.locator('.issue-ledger-row h3 a').first;link.hover();page.wait_for_timeout(180)
        assert link.evaluate('(e)=>getComputedStyle(e.closest(".issue-ledger-row"),"::before").opacity') == '0.85'
        receipt['flows'].append('Hover surface tint with unchanged row layout')
        # Runtime preference changes release the finished art too.
        page.emulate_media(reduced_motion='reduce')
        assert page.locator('.terrain-lines').first.evaluate('(e)=>getComputedStyle(e).transform') == 'none'
        receipt['flows'].append('Live reduced-motion preference leaves finished artwork')
        context.close()
        # Cold and cached requests, CLS and paint timings are lab observations.
        for label, base in [('candidate', url), ('current-main', baseline_url), ('released', released_url)]:
            for width in (375, 1440):
                context=browser.new_context(viewport={'width':width,'height':1000})
                page=context.new_page()
                page.add_init_script('window.__shifts=[];new PerformanceObserver(l=>l.getEntries().forEach(e=>{if(!e.hadRecentInput)window.__shifts.push(e.value)})).observe({type:"layout-shift",buffered:true})')
                for cached in (False, True):
                    page.goto(base + '/analysis.html',wait_until='networkidle');page.evaluate('document.fonts.ready')
                    values=page.evaluate('''()=>({cls:window.__shifts.reduce((a,b)=>a+b,0),paints:performance.getEntriesByType('paint').map(e=>({name:e.name,start:e.startTime})),resources:[...performance.getEntriesByType('navigation'),...performance.getEntriesByType('resource')].map(e=>({url:e.name,transfer:e.transferSize,body:e.encodedBodySize,duration:e.duration}))})''')
                    # Measure the existing swap-font arrival as well as the
                    # pilot; do not mistake a lab font shift for art motion.
                    assert values['cls'] <= .1, (label, width, values['cls'])
                    receipt['delivery'].append(dict(route=label,width=width,cached=cached,**values))
                context.close()
        for label, base in [('released',released_url),('current-main',baseline_url)]:
            for width in (375,768,1440):
                page=browser.new_page(viewport={'width':width,'height':844 if width<600 else 1000})
                page.goto(base+'/analysis.html',wait_until='networkidle');page.evaluate('document.fonts.ready')
                page.screenshot(path=str(out/('%s-%s.png'%(label,width))))
                page.close()
        browser.close()
    assert not receipt['errors'], receipt['errors']
    (out / 'BROWSER_QA.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Verified %s catalog cases, %s flows and %s unchanged publication links' % (len(receipt['cases']),len(receipt['flows']),receipt['publication_links_preserved']))
    return receipt


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    for name in ('url','baseline-url','released-url','root','baseline','out'): parser.add_argument('--'+name,required=True)
    args=parser.parse_args();verify(args.url,args.baseline_url,args.released_url,args.root,args.baseline,args.out)
