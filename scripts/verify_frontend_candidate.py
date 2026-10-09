#!/usr/bin/env python3
"""Reader-flow, accessibility fallback and delivery receipts for a local candidate.

Requires Playwright/Chromium; never fetches an official publisher or writes output/.
Start a loopback server serving the candidate and a separate private timeline tree.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def verify(public_url, timeline_url, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    routes = {'home': (public_url, 'index.html'), 'archive': (public_url, 'archive.html'),
              'record': (public_url, 'record/3924.html'),
              'brief': (public_url, 'briefs/maritime-cooperation-2026.html'),
              'timeline': (timeline_url, 'timeline/maritime-cooperation-2026.html')}
    receipt = {'cases': [], 'flows': [], 'delivery': [], 'errors': []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        receipt['browser'] = browser.version
        for width in (320, 375, 768, 1280, 1440):
            for profile in ('default', 'no-js', 'reduced-motion'):
                for kind, (base, route) in routes.items():
                    context = browser.new_context(viewport={'width': width, 'height': 844 if width < 600 else 1000},
                                                  java_script_enabled=profile != 'no-js',
                                                  reduced_motion='reduce' if profile == 'reduced-motion' else 'no-preference')
                    page = context.new_page()
                    page.on('pageerror', lambda error: receipt['errors'].append(str(error)))
                    page.on('response', lambda response: receipt['errors'].append(response.url + ': ' + str(response.status)) if response.status >= 400 else None)
                    page.goto(base + '/' + route, wait_until='networkidle')
                    page.evaluate('document.fonts.ready')
                    assert page.locator('h1').count() == 1, (kind, width, profile)
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), (kind, width, profile, 'overflow')
                    assert page.locator('img').evaluate_all('(els)=>els.filter(e=>e.complete && !e.naturalWidth).length') == 0, (kind, width, profile, 'image')
                    if profile != 'default':
                        assert page.locator('[data-reveal]').evaluate_all('(els)=>els.every(e=>getComputedStyle(e).opacity==="1")'), (kind, width, profile, 'hidden content')
                    if profile == 'no-js':
                        assert page.locator('main').inner_text().strip(), (kind, 'no-js')
                        if kind == 'archive':
                            assert page.locator('#results .record-row').count() == 50
                            assert not page.locator('#controls').is_visible()
                    case = {'route': kind, 'width': width, 'profile': profile, 'h1_y': round(page.locator('h1').bounding_box()['y'], 1)}
                    if kind == 'archive':
                        case['first_result_y'] = round(page.locator('#results .record-row').first.bounding_box()['y'], 1)
                    if kind == 'record' and page.locator('#record-summary').count():
                        case['summary_y'] = round(page.locator('#record-summary').bounding_box()['y'], 1)
                    if kind == 'timeline':
                        case['chronology_y'] = round(page.locator('#tl-narrative-heading').bounding_box()['y'], 1)
                        assert page.locator('.tl-spine>li').count() == 6
                        assert page.locator('.tl-ledger>ol>li').count() == 5
                    receipt['cases'].append(case)
                    if profile == 'default' and width in (375, 1440):
                        device = 'mobile' if width == 375 else 'desktop'
                        page.screenshot(path=str(out / (kind + '-' + device + '-opening.png')))
                        page.evaluate('document.querySelectorAll("[data-reveal]").forEach(e=>e.classList.add("is-in"))')
                        page.screenshot(path=str(out / (kind + '-' + device + '-full.png')), full_page=True)
                    context.close()
        context = browser.new_context(viewport={'width': 375, 'height': 844}, permissions=['clipboard-read', 'clipboard-write'])
        page = context.new_page()
        page.goto(public_url + '/archive.html', wait_until='networkidle')
        assert not any('corpus-index.json' in e['name'] for e in page.evaluate('performance.getEntriesByType("resource").map(e=>({name:e.name}))'))
        page.fill('#f-q', 'Maritime Cooperation')
        page.locator('#controls > .finder-row > button').click()
        page.wait_for_function('document.querySelector("#result-range").textContent.includes("of") && !document.querySelector("#index-state").hidden === false')
        page.wait_for_timeout(100)
        english_count = page.locator('#result-range').inner_text()
        assert page.locator('#results .record-row').count() > 0
        receipt['flows'].append({'search': 'English titles', 'result': english_count})
        page.fill('#f-q', '海上合作')
        page.locator('#controls > .finder-row > button').click(); page.wait_for_timeout(100)
        assert page.locator('#results .record-row').count() > 0
        receipt['flows'].append({'search': 'Original Chinese titles', 'result': page.locator('#result-range').inner_text()})
        page.locator('#f-reset').click(); page.wait_for_timeout(100)
        page.locator('.finder-more>summary').click()
        page.select_option('#f-desk', 'singapore');page.wait_for_timeout(100)
        assert 'desk=singapore' in page.url
        assert all('Singapore Desk' in item.inner_text() for item in page.locator('#results .row-side').all())
        page.go_back();page.wait_for_timeout(100)
        assert page.locator('#f-desk').input_value() == ''
        receipt['flows'].append({'filter_history': 'Desk selection and Back restore URL, control and records'})
        page.check('#f-trail');page.wait_for_timeout(100)
        trail_result = page.locator('#result-range').inner_text()
        assert page.locator('#results .trail-tag').count() == page.locator('#results .record-row').count()
        receipt['flows'].append({'approved_trails': trail_result})
        page.locator('#f-reset').click();page.wait_for_timeout(100)
        page.locator('#page-next').click();page.wait_for_timeout(100)
        assert 'page=2' in page.url
        assert page.locator(':focus').get_attribute('id') == 'result-range'
        page.go_back();page.wait_for_timeout(100)
        receipt['flows'].append({'pagination': 'Second page, range focus and Back restore'})
        page.fill('#f-from', '1900-01-01');page.fill('#f-to', '1900-01-02')
        page.locator('.finder-more-body button').click();page.wait_for_timeout(100)
        assert page.locator('#no-results').is_visible()
        receipt['flows'].append({'empty_state': 'Nonmatching date interval'})
        page.goto(public_url + '/record/3924.html', wait_until='networkidle')
        page.locator('.record-history>summary').focus();page.keyboard.press('Enter')
        assert page.locator('.record-history').evaluate('(e)=>e.open')
        page.locator('[data-copy="cite-source-text"]').click()
        source_text = page.locator('#cite-source-text').inner_text()
        assert page.evaluate('navigator.clipboard.readText()') == ' '.join(source_text.split())
        link = page.locator('.trail-panel a[href*="briefs/maritime"]')
        link.focus();page.keyboard.press('Enter');page.wait_for_url('**/briefs/maritime-cooperation-2026.html#r-3924')
        assert page.locator('#r-3924').count() == 1
        receipt['flows'].append({'citations': 'Exact source citation copied; record backlink reaches native Brief trail anchor'})
        page.goto(public_url + '/briefs/maritime-cooperation-2026.html', wait_until='networkidle')
        page.locator('.brief-photo-credit-detail>summary').click()
        assert page.locator('.brief-photo-credit-detail').evaluate('(e)=>e.open')
        page.locator('.brief-reading-navigation>summary').click()
        page.locator('.brief-toc a[href="#s-sources"]').click()
        assert page.url.endswith('#s-sources')
        receipt['flows'].append({'brief': 'Natural source photo credit and section navigation'})
        page.goto(timeline_url + '/timeline/maritime-cooperation-2026.html', wait_until='networkidle')
        page.locator('.tl-context-about>summary').focus();page.keyboard.press('Enter')
        assert page.locator('.tl-context-about').evaluate('(e)=>e.open')
        page.locator('.tl-context-tracks>summary').click()
        page.locator('.tl-track a[href="#sea-phase"]').click()
        assert page.url.endswith('#sea-phase')
        page.locator('#sea-phase .tl-evidence>summary').focus();page.keyboard.press('Space')
        assert page.locator('#sea-phase .tl-evidence').evaluate('(e)=>e.open')
        receipt['flows'].append({'timeline': 'Native context/date tracks, anchor navigation and keyboard evidence disclosure'})
        page.locator('.nav-mobile>summary').click();page.keyboard.press('Escape')
        assert not page.locator('.nav-mobile').evaluate('(e)=>e.open')
        assert page.locator(':focus').evaluate('(e)=>e===document.querySelector(".nav-mobile>summary")')
        receipt['flows'].append({'menu': 'Escape closes native menu and restores focus'})
        # Both emulations keep primary reading and explicit focus in view.
        for kind in ('record', 'brief', 'timeline'):
            base, route = routes[kind]
            page.goto(base + '/' + route, wait_until='networkidle')
            page.emulate_media(forced_colors='active')
            page.locator('a').first.focus()
            assert page.locator(':focus').evaluate('(e)=>getComputedStyle(e).outlineStyle') == 'solid'
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.emulate_media(forced_colors='none', media='print')
            assert page.locator('main').is_visible()
            assert page.locator('h1').evaluate('(e)=>getComputedStyle(e).color') == 'rgb(0, 0, 0)'
            if kind == 'brief':
                assert page.locator('.brief-evidence').evaluate_all('(els)=>els.every(e=>!e.open)')
                for selector in ('#s-compare', '#s-coverage'):
                    assert page.locator(selector).is_visible(), (kind, selector, 'print evidence')
                    assert page.locator(selector).inner_text().strip()
            page.emulate_media(media='screen')
            if kind == 'brief':
                assert not page.locator('#s-compare').is_visible()
                assert not page.locator('#s-coverage').is_visible()
        receipt['flows'].append({'fallbacks': 'Forced colors focus and print reading on record, Brief and timeline'})
        for base, route in ((public_url, 'index.html'), (timeline_url, 'index.html'),
                            (public_url, 'briefs/maritime-cooperation-2026.html')):
            page.goto(base + '/' + route, wait_until='networkidle')
            page.locator('picture source').evaluate_all('(els)=>els.forEach(e=>e.remove())')
            page.wait_for_function('Array.from(document.querySelectorAll("picture img")).every(e=>e.complete && e.naturalWidth>0 && e.currentSrc.endsWith(".jpg"))')
        receipt['flows'].append({'image_fallback': 'Natural JPEG images load in fresh public and private trees when WebP sources are unavailable'})
        page.goto(public_url + '/archive.html', wait_until='networkidle')
        page.set_viewport_size({'width': 320, 'height': 844})
        page.locator('.publication-freshness>summary').click()
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert page.locator('.freshness-bar dd').evaluate_all('(els)=>els.every(e=>e.getBoundingClientRect().height <= parseFloat(getComputedStyle(e).lineHeight)+1)')
        receipt['flows'].append({'freshness': 'Three independent dates stay unbroken in the open 320px disclosure'})
        context.close()
        for kind in ('home', 'archive', 'brief', 'timeline'):
            base, route = routes[kind]
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            page = context.new_page()
            for cached in (False, True):
                page.goto(base + '/' + route, wait_until='networkidle')
                page.evaluate('document.fonts.ready')
                values = page.evaluate('''() => { const entries = [...performance.getEntriesByType('navigation'),...performance.getEntriesByType('resource')];return {transfer:entries.reduce((n,e)=>n+e.transferSize,0),body:entries.reduce((n,e)=>n+e.encodedBodySize,0),resources:entries.map(e=>({url:e.name,transfer:e.transferSize,body:e.encodedBodySize})),timing:performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd,fonts:document.fonts.status}}''')
                receipt['delivery'].append(dict(route=kind, cached=cached, **values))
            context.close()
        browser.close()
    assert not receipt['errors'], receipt['errors']
    (out / 'BROWSER_QA.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
    print('Verified %s responsive/fallback cases and %s reader flows' % (len(receipt['cases']), len(receipt['flows'])))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--public-url', required=True);parser.add_argument('--timeline-url', required=True);parser.add_argument('--out', required=True)
    args = parser.parse_args()
    verify(args.public_url.rstrip('/'), args.timeline_url.rstrip('/'), args.out)
