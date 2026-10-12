#!/usr/bin/env python3
"""Browser/integrity review for the production Briefs catalog.

Serve released, current-main baseline and candidate trees on loopback. Captures
are actual Chromium images, never concepts; no editorial source is requested.

Phase 3B turned the ledger rows into media cards. The publication contract is
unchanged and still compared exactly: the baseline body text, links and ids
must equal the candidate's once the *additive* catalogue nodes are removed, and
those nodes are themselves audited (one media block and one credit block per
card, one key). Nothing the baseline said may move, and nothing is stripped
that is not on that list.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


# Catalogue nodes the redesign adds. Everything else must equal the baseline.
ADDITIVE = ('[data-catalogue-media]', '.brief-credit', '.brief-key')
# Anything a catalogue request may never touch: article source images, veils,
# and 81.cn / PLA Daily imagery (Phase 0 B2).
FORBIDDEN_REQUEST = re.compile(r'-source-image|-veil|veil-ocean|81\.cn|81cn', re.I)
ROOT = Path(__file__).resolve().parent.parent


def body_contract(path, strip_additive=False):
    soup = BeautifulSoup(Path(path).read_text(), 'html.parser')
    additive = {sel: len(soup.select(sel)) for sel in ADDITIVE}
    if strip_additive:
        for node in soup.select(', '.join(ADDITIVE)):
            node.decompose()
    for node in soup.select('script, style, [aria-hidden="true"]'):
        node.decompose()
    out = {'text': ' '.join(soup.body.get_text(' ', strip=True).split()),
           'links': [a.get('href') for a in soup.body.select('a[href]')],
           'ids': [node['id'] for node in soup.select('[id]')]}
    return (out, additive) if strip_additive else out


def media_links(path):
    """Links that live only inside the additive nodes (credit and source links)."""
    soup = BeautifulSoup(Path(path).read_text(), 'html.parser')
    return [a.get('href') for sel in ('.brief-credit',) for n in soup.select(sel)
            for a in n.select('a[href]')]


def verify(url, baseline_url, released_url, root, baseline, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    expected = body_contract(Path(baseline) / 'analysis.html')
    actual, additive = body_contract(Path(root) / 'analysis.html', strip_additive=True)
    assert actual == expected, 'Catalog publication text, links or anchors changed'
    n_cards = len(BeautifulSoup((Path(baseline) / 'analysis.html').read_text(), 'html.parser').select('.issue-ledger-row'))
    assert additive == {'[data-catalogue-media]': n_cards, '.brief-credit': n_cards, '.brief-key': 1}, additive
    sys.path.insert(0, str(ROOT))
    admitted = {e['issue'] for e in json.loads((ROOT / 'site/assets/catalogue/admissions.json').read_text())['entries']
                if e['status'] == 'admitted'}
    for href in actual['links']:
        parts = urlsplit(href)
        if not parts.scheme and not parts.netloc and parts.path:
            assert (Path(root) / parts.path).is_file(), href
    assert len(actual['ids']) == len(set(actual['ids']))
    receipt = {'publication_links_preserved': len(actual['links']), 'exact_body_contract': True,
               'additive_nodes': additive, 'cards': [], 'forbidden_requests': [],
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
                page.on('request', lambda r: receipt['forbidden_requests'].append(r.url) if FORBIDDEN_REQUEST.search(r.url) else None)
                if profile == 'script-failure': page.route('**/*.js', lambda r: r.abort())
                if profile == 'no-anim': page.add_init_script('document.addEventListener("DOMContentLoaded",()=>document.documentElement.classList.add("no-anim"))')
                if profile == 'forced-colors': page.emulate_media(forced_colors='active')
                if profile == 'print': page.emulate_media(media='print')
                page.goto(url + '/analysis.html', wait_until='networkidle'); page.evaluate('document.fonts.ready')
                assert page.locator('h1').count() == 1
                assert page.locator('.brief-card').count() == n_cards
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
                # Media: every card carries its tag; no frame is ever empty. A
                # plate's art is hidden in forced colours and print, where its
                # text tag stands in; a photograph's frame stays.
                plates = page.locator('.brief-card[data-media="plate"] .rl-print')
                assert plates.count() == n_cards - len(admitted)
                if profile in ('forced-colors', 'print'):
                    assert plates.evaluate_all('(els)=>els.every(e=>getComputedStyle(e).display==="none")'), (width, profile, 'plate frame')
                assert page.locator('.brief-tag').evaluate_all('(els)=>els.every(e=>e.getBoundingClientRect().width>0)'), (width, profile, 'tag')
                # No horizontal bleed from any card, and a card's frame is 3:2.
                assert page.locator('.brief-card').evaluate_all('(els)=>els.every(e=>e.getBoundingClientRect().right<=innerWidth+.5&&e.scrollWidth<=e.clientWidth+1)'), (width, profile, 'card overflow')
                if profile in ('default', 'reduced-motion'):
                    ratios = page.locator('.brief-card .rl-print').evaluate_all('(els)=>els.map(e=>{const r=e.getBoundingClientRect();return r.width/r.height})')
                    assert all(abs(r - 1.5) < .02 for r in ratios), (width, profile, ratios)
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
        link = page.locator('.brief-card h3 a').first;link.focus()
        # The card shows the focus ring and the approved Brief lift; the link's
        # own outline is replaced by the card's, never both.
        assert link.evaluate('(e)=>getComputedStyle(e.closest(".brief-card")).outlineStyle') == 'solid'
        assert link.evaluate('(e)=>getComputedStyle(e).outlineStyle') == 'none'
        page.wait_for_function('parseFloat(getComputedStyle(document.querySelector(".brief-card"),"::after").opacity) >= 1')
        page.screenshot(path=str(out / 'briefs-mobile-focus.png'))
        page.keyboard.press('Enter');page.wait_for_url('**/briefs/trident-resolve-regional-scale-specific-chinese-tasks.html')
        assert page.locator('h1').count() == 1
        receipt['flows'].append('Keyboard skip, Browse anchor, visible card focus and native Brief navigation')
        # Mouse hover raises the one approved Brief lift and moves nothing else.
        page.goto(url + '/analysis.html',wait_until='networkidle')
        page.set_viewport_size({'width':1440,'height':1000})
        link=page.locator('.brief-card h3 a').first;link.scroll_into_view_if_needed();link.hover();page.wait_for_timeout(320)
        assert link.evaluate('(e)=>getComputedStyle(e.closest(".brief-card"),"::after").opacity') == '1'
        receipt['flows'].append('Hover raises the approved Brief lift')
        # One link per card answers to the headline; credit links stay clickable above it.
        n_links = page.locator('.brief-card').evaluate_all('(els)=>els.map(e=>e.querySelectorAll(".issue-ledger-copy a").length)')
        assert all(n == 1 for n in n_links), n_links
        receipt['flows'].append('One primary link per card; stretched target stays below the credit links')
        # Runtime preference changes release the finished art too.
        page.emulate_media(reduced_motion='reduce')
        assert page.locator('.terrain-lines').first.evaluate('(e)=>getComputedStyle(e).transform') == 'none'
        receipt['flows'].append('Live reduced-motion preference leaves finished artwork')
        context.close()
        # Media audit: every card's media, label, credit and licence as rendered.
        context = browser.new_context(viewport={'width':1280,'height':1000})
        page = context.new_page()
        page.on('request', lambda r: receipt['forbidden_requests'].append(r.url) if FORBIDDEN_REQUEST.search(r.url) else None)
        page.goto(url + '/analysis.html', wait_until='networkidle')
        for i in range(n_cards):
            card = page.locator('.brief-card').nth(i); card.scroll_into_view_if_needed()
            img = card.locator('.rl-print img')
            if img.count():
                page.wait_for_function('(e)=>e.complete&&e.naturalWidth>0', arg=img.first.element_handle())
        page.wait_for_timeout(150)
        cards = page.evaluate('''()=>[...document.querySelectorAll('.brief-card')].map(c=>{
          const img=c.querySelector('.rl-print img'),a=c.querySelector('h3 a');
          return {issue:c.querySelector('.issue-no').textContent.trim(),title:a.textContent.trim(),href:a.getAttribute('href'),
            media:c.dataset.media,tag:c.querySelector('.brief-tag').textContent.trim(),
            img:img?{src:img.getAttribute('src'),alt:img.alt,w:img.naturalWidth,h:img.naturalHeight,lazy:img.loading}:null,
            plate_svg:!!c.querySelector('.rl-print svg.rl-region'),
            credit:c.querySelector('.brief-credit').innerText.replace(/\\s+/g,' ').trim(),
            credit_links:[...c.querySelectorAll('.brief-credit a')].map(x=>({href:x.getAttribute('href'),rel:x.rel,text:x.textContent.trim()}))}})''')
        assert len(cards) == n_cards
        for c in cards:
            n = int(re.sub(r'\D', '', c['issue']))
            if n in admitted:
                assert c['media'] == 'photograph' and c['tag'] == 'Photograph' and c['img'], c
                assert c['img']['src'].startswith('assets/catalogue/media/') and not FORBIDDEN_REQUEST.search(c['img']['src']), c
                assert (c['img']['w'], c['img']['h']) == (720, 480) and c['img']['alt'], c
                assert c['img']['lazy'] == 'lazy', c
                assert 'Visual context, not evidence.' in c['credit'] and 'Toned, cropped and resized by IPR.' in c['credit'], c
                assert c['credit_links'] and all(l['href'].startswith('https://') and 'noopener' in l['rel'] for l in c['credit_links']), c
            else:
                assert c['media'] == 'plate' and c['tag'] == 'Editorial plate' and c['plate_svg'] and not c['img'], c
                assert c['credit'] == 'No source photograph. Outlines from Natural Earth.', c
                assert not c['credit_links'], c
        receipt['cards'] = cards
        assert [int(re.sub(r'\D', '', c['issue'])) for c in cards] == sorted((int(re.sub(r'\D', '', c['issue'])) for c in cards), reverse=True)
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
    assert not receipt['forbidden_requests'], sorted(set(receipt['forbidden_requests']))
    (out / 'BROWSER_QA.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Verified %s catalog cases, %s flows and %s unchanged publication links' % (len(receipt['cases']),len(receipt['flows']),receipt['publication_links_preserved']))
    return receipt


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    for name in ('url','baseline-url','released-url','root','baseline','out'): parser.add_argument('--'+name,required=True)
    args=parser.parse_args();verify(args.url,args.baseline_url,args.released_url,args.root,args.baseline,args.out)
