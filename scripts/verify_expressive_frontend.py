#!/usr/bin/env python3
"""Browser evidence for the source-only expressive frontend candidate.

Serve the before/after disposable builds first. Screenshots use the deliberately
finished reduced-motion state; behavioral checks also exercise normal motion.
No output/, sidecars, database, source photographs or editorial state is written.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROUTES = [
    ('home', 'index.html', 650),
    ('home-lower', 'index.html', 1720),
    ('archive', 'archive.html', 0),
    ('record', 'record/3924.html', 0),
    ('catalog', 'analysis.html', 0),
    ('brief', 'briefs/maritime-cooperation-2026.html', 0),
    ('brief-reading', 'briefs/maritime-cooperation-2026.html', 980),
    ('desks', 'desks.html', 140),
    ('desk', 'china.html', 0),
    ('utility', 'methodology.html', 0),
    ('historical', 'the-pla-watch/posts/2026-08-08.html', 0),
    ('glossary', 'the-pla-watch/terms.html', 0),
    ('source', 'source/pla_daily.html', 0),
]
EXTRA = ['coverage.html', 'sources.html', 'about.html', 'corpus-guide.html',
         'corpus.html', 'japan.html', 'vietnam.html', 'singapore.html',
         'us-indopacific.html', 'the-pla-watch/index.html',
         'the-pla-watch/archive.html', 'week-2026-06-08.html']


def verify(before, after, destination):
    out = Path(destination).resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = []

    def check(name, ok, detail=None):
        results.append(dict(name=name, passed=bool(ok), detail=detail))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        errors, missing = [], []
        context = browser.new_context(reduced_motion='reduce')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: missing.append(response.url)
                if response.status >= 400 and response.url.startswith(after) else None)
        routes = list(dict.fromkeys([r[1] for r in ROUTES] + EXTRA))
        for width in (1440, 768, 375, 320):
            page.set_viewport_size(dict(width=width, height=1000 if width>700 else 900))
            for route in routes:
                response = page.goto(after+'/'+route)
                page.evaluate('document.fonts.ready')
                page.wait_for_timeout(60)
                overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                check(f'{width}px {route}: route and width', response.status==200 and not overflow,
                      {'status': response.status, 'overflow': overflow})
                check(f'{width}px {route}: single heading', page.locator('h1').count()==1)
        check('sampled routes: JavaScript errors', not errors, errors)
        check('sampled routes: local resource responses', not missing, sorted(set(missing)))
        # Capture paired static states with the same dimensions and scroll.
        for width, label in ((1440, 'desktop'), (375, 'mobile')):
            page.set_viewport_size(dict(width=width, height=1000 if width==1440 else 900))
            for name, route, scroll in ROUTES:
                for state, origin in (('before',before), ('after',after)):
                    page.goto(origin+'/'+route)
                    page.evaluate('document.fonts.ready')
                    if name=='desks' and state=='after':
                        page.locator('[data-select-desk="singapore"]').click()
                    # On phones the photograph ends earlier; show the finder
                    # and lower register instead of overshooting those sections.
                    offset = 530 if width==375 and name=='home' else scroll
                    page.evaluate('(y)=>scrollTo(0,y)', offset)
                    page.wait_for_timeout(70)
                    page.screenshot(path=str(out/f'{name}-{label}-{state}.jpg'),
                                    type='jpeg', quality=82)
        # Home photographic opening has the identical composition and credit.
        hero = []
        page.set_viewport_size(dict(width=1440,height=1000))
        for origin in (before,after):
            page.goto(origin+'/index.html')
            page.evaluate('document.fonts.ready')
            hero.append(page.locator('.pacific-opening').evaluate('''e=>({
                text:e.innerText, height:e.getBoundingClientRect().height,
                photo:e.querySelector('img').getAttribute('src'),
                title:e.querySelector('h1').getBoundingClientRect().toJSON()})'''))
        check('home photographic composition, title and credit unchanged', hero[0]==hero[1], hero)
        # Native controls: selection persists through focus/scroll, reset and
        # country + actual seat selection share the same state.
        page.goto(after+'/desks.html')
        for slug in ('china','singapore','japan','vietnam','us-indopacific'):
            button = page.locator(f'[data-select-desk="{slug}"]')
            button.click()
            check('map '+slug+': linked selected states',
                  button.get_attribute('aria-pressed')=='true'
                  and page.locator(f'.deskmap-plate[data-desk="{slug}"].is-selected').count()==1
                  and page.locator(f'.dm-anchor[data-desk="{slug}"].is-selected').count()==1
                  and page.locator(f'[data-context-desk="{slug}"]').is_visible())
            check('map '+slug+': announced status and recorded count',
                  'Records:' in page.locator('.deskmap [role=status]').inner_text())
        page.locator('[data-select-desk="china"]').focus()
        page.keyboard.press('ArrowRight')
        check('map arrow keys move to next native button',
              page.evaluate('document.activeElement.dataset.selectDesk')=='singapore')
        page.keyboard.press('Space')
        check('map Space selects focused desk',page.locator('[data-select-desk="singapore"]').get_attribute('aria-pressed')=='true')
        page.keyboard.press('Escape')
        check('map Escape resets and focuses All desks',page.locator('.deskmap-reset').evaluate('e=>e===document.activeElement') and not page.locator('.deskmap .is-selected').count())
        page.locator('.dm-country[data-desk="china"]').dispatch_event('click')
        check('real country click selects entry',page.locator('[data-select-desk="china"]').get_attribute('aria-pressed')=='true')
        page.locator('.dm-anchor[data-desk="japan"]').dispatch_event('click')
        check('real seat click selects entry',page.locator('[data-select-desk="japan"]').get_attribute('aria-pressed')=='true')
        page.locator('.deskmap-reset').click()
        check('All desks resets chart and scope',not page.locator('.deskmap .is-selected').count() and page.locator('.deskmap-context-default').is_visible())
        page.goto(after+'/desks.html#desk-vietnam')
        check('existing desk hash initializes selection',page.locator('[data-select-desk="vietnam"]').get_attribute('aria-pressed')=='true')
        page.set_viewport_size(dict(width=375,height=900))
        check('phone coordinate ticks omitted', not page.locator('.dm-scale').is_visible())
        hit=page.locator('.dm-hit').first.bounding_box()
        check('phone seat hit targets at least 44px', hit and hit['width']>=44, hit)
        page.emulate_media(forced_colors='active')
        page.locator('[data-select-desk="china"]').click()
        check('forced colors preserves selected control and entry',page.locator('[data-select-desk="china"]').is_visible() and page.locator('.deskmap-plate.is-selected').is_visible())
        page.emulate_media(forced_colors='none')
        # Search, evidence disclosures, citation, mobile navigation.
        page.goto(after+'/archive.html')
        page.locator('#f-q').fill('Maritime Cooperation')
        page.locator('#f-q').press('Enter')
        page.wait_for_timeout(500)
        check('archive title search returns records',page.locator('#results .record-row').count()>0 and 'q=' in page.url)
        page.locator('#f-reset').click()
        check('archive reset restores newest records',not page.locator('#f-reset').is_visible() and page.locator('#results .record-row').count()==50)
        page.goto(after+'/record/3924.html')
        page.locator('a[href="#record-citation"]').first.click()
        check('record citation anchor works',page.url.endswith('#record-citation'))
        page.goto(after+'/briefs/maritime-cooperation-2026.html')
        evidence=page.locator('.brief-evidence').first
        evidence.locator('summary').click()
        check('Brief evidence disclosure opens',evidence.get_attribute('open') is not None)
        page.locator('.nav-mobile summary').click()
        check('mobile native Menu opens',page.locator('.nav-mobile').get_attribute('open') is not None)
        page.keyboard.press('Escape')
        check('mobile Escape closes Menu',page.locator('.nav-mobile').get_attribute('open') is None)
        page.emulate_media(media='print')
        check('print keeps prose and removes contour overlay',page.locator('.brief-main').is_visible() and page.locator('.brief-hero').evaluate('e=>getComputedStyle(e,"::after").display')=='none')
        # Every fallback retains canonical text/links. Native shell needs no JS.
        fallback=browser.new_context(java_script_enabled=False, viewport=dict(width=375,height=900), reduced_motion='reduce')
        fp=fallback.new_page()
        for route in ('index.html','archive.html','desks.html','record/3924.html','briefs/maritime-cooperation-2026.html','the-pla-watch/posts/2026-08-08.html'):
            fp.goto(after+'/'+route)
            check('no JavaScript '+route+': reading and width',fp.locator('h1').is_visible() and not fp.evaluate('document.documentElement.scrollWidth>innerWidth+1'))
        fp.goto(after+'/desks.html')
        check('no JavaScript map register and entry links',fp.locator('.deskmap-enter a').count()==5 and not fp.locator('.deskmap-controls').is_visible())
        fallback.close()
        # Normal motion is perceptible but finite, and never gates content.
        motion=browser.new_context(viewport=dict(width=1440,height=1000))
        mp=motion.new_page()
        mp.goto(after+'/methodology.html')
        check('contour scroll entrance is assigned',mp.locator('.page-head').evaluate('e=>getComputedStyle(e,"::after").animationName')=='profile-settle')
        mp.goto(after+'/desks.html')
        mp.locator('[data-select-desk="china"]').hover()
        mp.mouse.down()
        mp.wait_for_timeout(180)
        check('control press provides movement',mp.locator('[data-select-desk="china"]').evaluate('e=>getComputedStyle(e).transform')!='none')
        mp.mouse.up()
        for width in (320,480,600,768):
            mp.set_viewport_size(dict(width=width,height=900))
            for route in ('index.html','methodology.html'):
                mp.goto(after+'/'+route)
                check(f'normal motion {width}px {route}: width',not mp.evaluate('document.documentElement.scrollWidth>innerWidth'))
        mp.emulate_media(reduced_motion='reduce')
        mp.goto(after+'/desks.html')
        check('reduced motion removes control transition',mp.locator('[data-select-desk="china"]').evaluate('e=>getComputedStyle(e).transitionDuration')=='0s')
        mp.goto(after+'/methodology.html')
        check('reduced motion contour is static',mp.locator('.page-head').evaluate('e=>getComputedStyle(e,"::after").animationName')=='none')
        fonts=browser.new_context(viewport=dict(width=375,height=900))
        fonts.route('**/*.woff2', lambda route: route.abort())
        fp=fonts.new_page();blocked=[]
        fp.on('requestfailed',lambda request:blocked.append(request.url) if request.url.endswith('.woff2') else None)
        fp.goto(after+'/source/pla_daily.html')
        fp.wait_for_timeout(100)
        check('blocked fonts preserve reading and width',blocked and fp.locator('h1').is_visible() and not fp.evaluate('document.documentElement.scrollWidth>innerWidth+1'),blocked)
        fonts.close()
        browser.close()
    receipt=dict(checks=len(results),failures=[r for r in results if not r['passed']],results=results,
                 screenshots=len(ROUTES)*4,before=before,after=after,
                 limitations=['Chromium browser checks; real assistive technology and Safari/Firefox not exercised'])
    (out/'browser-checks.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='results'},indent=2))
    return not receipt['failures']


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--before',default='http://127.0.0.1:8786')
    parser.add_argument('--after',default='http://127.0.0.1:8787')
    parser.add_argument('--evidence',required=True)
    args=parser.parse_args()
    raise SystemExit(0 if verify(args.before,args.after,args.evidence) else 1)
