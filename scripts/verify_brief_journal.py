#!/usr/bin/env python3
"""Browser receipts for every Brief; serves local trees, never publishes them."""
import argparse
import base64
from contextlib import contextmanager
import functools
import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_brief_unified_reading import PAGES

WIDTHS = (320, 375, 768, 1280, 1440)
REPRESENTATIVES = {
    'laos': ('briefs/what-is-being-built-in-laos.html', '#reading-finding'),
    'trident': ('briefs/trident-resolve-regional-scale-specific-chinese-tasks.html', '.brief-signal'),
    'native': ('briefs/maritime-cooperation-2026.html', '.brief-signal'),
    'fourteen': ('the-pla-watch/posts/2026-08-15.html', '.brief-signal'),
    'pilot': ('the-pla-watch/posts/2026-05-09.html', '#s-snapshot'),
}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@contextmanager
def server(root):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:%d/' % httpd.server_port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def inspect(page):
    return page.evaluate('''() => {
      const ids=[...document.querySelectorAll('[id]')].map(n=>n.id);
      const toc=[...document.querySelectorAll('.brief-toc a[href^="#"]')];
      return {
        overflow:document.documentElement.scrollWidth>innerWidth+1,
        h1:document.querySelectorAll('h1').length,
        duplicate_ids:ids.filter((id,i)=>ids.indexOf(id)!==i),
        broken_targets:toc.filter(a=>!document.getElementById(a.hash.slice(1))).map(a=>a.hash),
        images:[...document.querySelectorAll('img')].filter(i=>i.loading!=='lazy'&&(!i.complete||!i.naturalWidth)).map(i=>i.src),
        deferred_images:[...document.querySelectorAll('img[loading="lazy"]')].filter(i=>!i.naturalWidth).length,
        reading_background:getComputedStyle(document.querySelector('.brief-main')).backgroundColor,
        toc_open:document.querySelector('.brief-reading-navigation').open
      };
    }''')


def position(page, selector):
    page.locator(selector).first.evaluate('(n)=>scrollTo(0,n.getBoundingClientRect().top+scrollY-140)')


def capture(page, path):
    """Wait for fonts, image decoding and a painted frame before review capture."""
    page.wait_for_load_state('networkidle')
    page.evaluate('''async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].filter(i=>i.loading!=='lazy')
        .map(i=>i.decode()));
      await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      await Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{})));
    }''')
    page.screenshot(path=str(path))


def verify(root, baseline, out, fixture_root=None):
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True, exist_ok=True)
    routes = [str(p.relative_to(ROOT / 'output')) for p in PAGES]
    receipts, failures = [], []
    with server(root) as url, sync_playwright() as pw:
        browser = pw.chromium.launch()
        version = browser.version
        for profile, options in (
            ('default', {}), ('no-js', {'java_script_enabled': False}),
            ('reduced-motion', {'reduced_motion': 'reduce'}),
            ('forced-colors', {'forced_colors': 'active'}),
        ):
            print('Checking ' + profile, flush=True)
            context = browser.new_context(**options)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            for width in WIDTHS:
                page.set_viewport_size({'width': width, 'height': 900})
                for route in routes:
                    errors.clear()
                    response = page.goto(url + route, wait_until='networkidle')
                    data = inspect(page)
                    data.update(profile=profile, width=width, route=route,
                                status=response.status, errors=list(errors))
                    if (data['overflow'] or data['h1'] != 1 or data['duplicate_ids']
                            or data['broken_targets'] or data['images'] or errors or response.status != 200):
                        failures.append(data)
                    receipts.append(data)
                    # Real fragment navigation also exercises targets inside closed details.
                    for anchor in (page.locator('.brief-toc a').all() if width in (375, 1280) else []):
                        target = anchor.get_attribute('href')
                        page.goto(url + route + target, wait_until='domcontentloaded')
                        node = page.locator(target)
                        if not node.is_visible():
                            failures.append({'route': route, 'width': width, 'profile': profile,
                                             'hidden_fragment_target': target})
                    if profile == 'reduced-motion':
                        moving = page.evaluate("() => document.getAnimations().filter(a=>a.playState==='running').length")
                        if moving:
                            failures.append({'route': route, 'profile': profile, 'running_animations': moving})
            context.close()

        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        for route in routes:
            page.goto(url + route)
            page.emulate_media(media='print')
            data = inspect(page)
            nav_hidden = not page.locator('.brief-reading-navigation').is_visible()
            backgrounds = page.locator('.brief-main,.brief-signal,.brief-reading-finding,.brief-trail,.brief-citation-section').evaluate_all(
                "ns=>ns.map(n=>({color:getComputedStyle(n).backgroundColor,image:getComputedStyle(n).backgroundImage}))")
            if not nav_hidden or any(b['image'] != 'none' for b in backgrounds):
                failures.append({'route': route, 'profile': 'print', 'backgrounds': backgrounds})
            receipts.append(dict(data, route=route, profile='print', nav_hidden=nav_hidden))
            page.emulate_media(media='screen')

        # Keyboard activation and focus are checked without mouse clicks.
        for width in (375, 1280):
            for route in routes:
                page.set_viewport_size({'width': width, 'height': 900})
                page.goto(url + route)
                summary = page.locator('.brief-reading-navigation>summary')
                summary.focus()
                if not page.locator('.brief-reading-navigation').evaluate('(n)=>n.open'):
                    page.keyboard.press('Enter')
                first = page.locator('.brief-toc a').first
                first.focus()
                outline = first.evaluate('(n)=>getComputedStyle(n).outlineStyle')
                href = first.get_attribute('href')
                page.keyboard.press('Enter')
                target = page.locator(href)
                top = target.bounding_box()['y']
                if outline == 'none' or not target.is_visible() or top < 0 or top > 250:
                    failures.append({'route': route, 'width': width, 'profile': 'keyboard',
                                     'outline': outline, 'target_top': top})
                receipts.append({'route': route, 'width': width, 'profile': 'keyboard',
                                 'outline': outline, 'target_top': top})

        # Enlarge the actual computed text, including the existing px typography.
        for mode, script in (
            ('text-200-percent', """[...document.querySelectorAll('body *')]
                .map(n=>[n,parseFloat(getComputedStyle(n).fontSize)])
                .forEach(([n,size])=>n.style.fontSize=(2*size)+'px')"""),
            ('css-layout-200-percent', "document.documentElement.style.zoom='2'"),
        ):
            for width in (375, 1280):
                # CSS zoom at 375px would test 187.5 CSS px, below the 320px
                # supported reflow floor. Real browser zoom is verified below.
                if mode == 'css-layout-200-percent' and width == 375:
                    continue
                page.set_viewport_size({'width': width, 'height': 900})
                for route in routes:
                    page.goto(url + route)
                    page.evaluate(script)
                    data = inspect(page)
                    if data['overflow']:
                        failures.append(dict(data, route=route, profile=mode, width=width))
                    receipts.append(dict(data, route=route, profile=mode, width=width))

        # Region screenshots make actual type, source matter and navigation reviewable.
        with server(baseline) as before_url:
            for phase, base in (('before', before_url), ('after', url)):
                for width, device in ((375, 'mobile'), (1280, 'desktop')):
                    page.set_viewport_size({'width': width, 'height': 900})
                    for name, (route, selector) in REPRESENTATIVES.items():
                        page.goto(base + route)
                        position(page, selector)
                        capture(page, out / ('%s-%s-%s.png' % (name, phase, device)))
                    route = REPRESENTATIVES['laos'][0]
                    for part, selector in (('mid', '#reading-aviation'), ('references', '#s-publishers')):
                        page.goto(base + route)
                        position(page, selector)
                        capture(page, out / ('laos-%s-%s-%s.png' % (part, phase, device)))
                    page.goto(base + REPRESENTATIVES['native'][0])
                    position(page, '#s-sources')
                    capture(page, out / ('native-sources-%s-%s.png' % (phase, device)))
                    page.goto(base + REPRESENTATIVES['laos'][0])
                    capture(page, out / ('laos-hero-%s-%s.png' % (phase, device)))

        page.set_viewport_size({'width': 1280, 'height': 900})
        page.goto(url + REPRESENTATIVES['laos'][0])
        position(page, '#reading-finding')
        page.emulate_media(forced_colors='active')
        capture(page, out / 'laos-forced-colors.png')
        page.emulate_media(forced_colors='none', media='print')
        capture(page, out / 'laos-print.png')
        page.pdf(path=str(out / 'laos-print.pdf'), format='A4', print_background=False)
        page.emulate_media(media='screen')

        if fixture_root:
            with server(fixture_root) as fixtures_url:
                fixture_pages = sorted((fixture_root / 'briefs').glob('*.html'))
                for width in WIDTHS:
                    page.set_viewport_size({'width': width, 'height': 900})
                    for fixture in fixture_pages:
                        route = str(fixture.relative_to(fixture_root))
                        page.goto(fixtures_url + route, wait_until='networkidle')
                        data = inspect(page)
                        if data['overflow'] or data['broken_targets'] or data['images']:
                            failures.append(dict(data, route=route, profile='future', width=width))
                        receipts.append(dict(data, route=route, profile='future', width=width))
                        if width in (375, 1280):
                            position(page, '.brief-main')
                            capture(page, out / ('%s-%d.png' % (fixture.stem, width)))
        browser.close()
        # Use Chromium's own setting in an isolated, disposable profile. This is
        # actual desktop browser zoom, not device scale or visual/pinch zoom.
        with tempfile.TemporaryDirectory(prefix='ipr-journal-browser-zoom-') as profile:
            zoom = pw.chromium.launch_persistent_context(profile, channel='chromium',
                                                        viewport={'width': 1280, 'height': 900})
            page = zoom.new_page()
            page.goto('chrome://settings/appearance')
            page.locator('#zoomLevel').select_option('2')
            for route in routes:
                page.goto(url + route, wait_until='networkidle')
                data = inspect(page)
                metrics = page.evaluate('({inner:innerWidth,dpr:devicePixelRatio,pinch:visualViewport.scale})')
                if data['overflow'] or metrics != {'inner': 640, 'dpr': 2, 'pinch': 1}:
                    failures.append(dict(data, route=route, profile='browser-200-percent', metrics=metrics))
                receipts.append(dict(data, route=route, profile='browser-200-percent', metrics=metrics))
                if route == REPRESENTATIVES['laos'][0]:
                    position(page, '#reading-finding')
                    # Chromium's surface capture misplaces content at actual
                    # browser zoom. Capture the browser viewport compositor.
                    shot = zoom.new_cdp_session(page).send('Page.captureScreenshot',
                        {'captureBeyondViewport': False, 'fromSurface': False})
                    (out / 'laos-browser-200-percent.png').write_bytes(base64.b64decode(shot['data']))
            zoom.close()
    report = {'chromium': version, 'widths': WIDTHS, 'routes': len(routes),
              'checks': len(receipts), 'receipts': receipts, 'failures': failures,
              'zoom_scope': '200% computed text, CSS layout, and real Chromium desktop zoom'}
    (out / 'browser-receipts.json').write_text(json.dumps(report, indent=2) + '\n')
    print('%d checks; %d failures; Chromium %s' % (len(receipts), len(failures), version))
    return 1 if failures else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--fixtures', type=Path)
    args = parser.parse_args()
    raise SystemExit(verify(args.root, args.baseline, args.out, args.fixtures))
