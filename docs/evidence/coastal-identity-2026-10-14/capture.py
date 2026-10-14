"""Capture isolated renders with real local fonts; does not write publication output.
Run with the project Python after rendering /tmp/ipr-coastal-{before,after}
and their private -review and -fixture companions (see README).
"""
import functools
import http.server
import json
import hashlib
from pathlib import Path
import threading

from PIL import Image
from playwright.sync_api import sync_playwright

EVIDENCE = Path(__file__).resolve().parent
ROUTES = {
    'home': ('', 'index.html'),
    'analysis': ('', 'analysis.html'),
    'laos': ('', 'briefs/what-is-being-built-in-laos.html'),
    'historical': ('', 'the-pla-watch/posts/2026-08-15.html'),
    'native': ('', 'briefs/maritime-cooperation-2026.html'),
    'record': ('', 'record/1.html'),
    'laos-v2-private': ('-review', 'briefs/what-is-being-built-in-laos.html'),
    'evidence-fixture': ('-fixture', 'index.html'),
}


def main():
    shots = EVIDENCE / 'shots'; shots.mkdir(exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory='/tmp')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    receipts = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for phase in ('before', 'after'):
            for width in (375, 768, 1280):
                context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
                context.add_init_script("sessionStorage.setItem('ipr-intro','1')")
                for name, (suffix, route) in ROUTES.items():
                    page = context.new_page()
                    url = f'http://127.0.0.1:{server.server_port}/ipr-coastal-{phase}{suffix}/{route}'
                    response = page.goto(url, wait_until='networkidle')
                    page.evaluate('document.fonts.ready')
                    page.evaluate('''async () => {for (const i of document.images) i.loading='eager'; await Promise.all([...document.images].map(i=>i.decode().catch(()=>{})))}''')
                    page.locator('footer').count() and page.locator('footer').last.scroll_into_view_if_needed()
                    page.evaluate('window.scrollTo(0,0)')
                    page.wait_for_timeout(150)
                    info = page.evaluate('''() => ({overflow:document.documentElement.scrollWidth > innerWidth,
                      fonts:document.fonts.status, h1:document.querySelectorAll('h1').length,
                      missingImages:[...document.images].filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src),
                      text:document.body.innerText,
                      links:[...document.querySelectorAll('a')].map(a=>[a.textContent,a.getAttribute('href')]),
                      geometry:[...document.querySelectorAll('main,header,h1,h2,nav,img')].map(el=>{let r=el.getBoundingClientRect();return [el.tagName,...[r.x,r.y,r.width,r.height].map(n=>Math.round(n*100)/100)]}),
                      images:[...document.images].map(i=>[i.getAttribute('src'),i.getAttribute('alt'),i.getAttribute('srcset')])})''')
                    stem = f'{phase}-{name}-{width}'
                    png = shots / (stem+'.png'); page.screenshot(path=str(png), full_page=True, timeout=60000)
                    with Image.open(png) as im:
                        im.save(shots/(stem+'.jpg'), 'JPEG', quality=88, optimize=True)
                    png.unlink()
                    for key in ('text','links','images','geometry'):
                        info[key] = hashlib.sha256(json.dumps(info[key],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                    receipts.append(dict(phase=phase, route=name, width=width, status=response.status, **info))
                    if phase=='after' and width in (375,1280):
                        page.keyboard.press('Tab')
                        page.screenshot(path=str(shots/(stem+'-focus.png')))
                        for mode in ('forced', 'print'):
                            page.emulate_media(media='print' if mode=='print' else 'screen', forced_colors='active' if mode=='forced' else 'none')
                            page.screenshot(path=str(shots/(stem+'-'+mode+'.png')))
                    page.close()
                context.close()
        browser.close()
    server.shutdown()
    for png in shots.glob('*.png'):
        if any(png.stem.endswith('-'+mode) for mode in ('focus','print','forced')):
            with Image.open(png) as im:
                im.save(png.with_suffix('.webp'), 'WEBP', lossless=True)
        png.unlink()
    for old in shots.glob('*.webp'):
        if old.with_suffix('.jpg').exists(): old.unlink()
    (EVIDENCE/'browser-receipts.json').write_text(json.dumps(receipts, ensure_ascii=False, indent=2))
    comparisons=[]
    for after in [r for r in receipts if r['phase']=='after']:
        before=next(r for r in receipts if r['phase']=='before' and r['route']==after['route'] and r['width']==after['width'])
        comparisons.append({'route':after['route'],'width':after['width'],
                            **{k:before[k]==after[k] for k in ('text','links','images','geometry')}})
    (EVIDENCE/'parity.json').write_text(json.dumps(comparisons, indent=2))
    assert all(r['status']==200 and not r['overflow'] and not r['missingImages'] for r in receipts)
    assert all(all(r[k] for k in ('text','links','images','geometry')) for r in comparisons)
    print(f'{len(receipts)} route/viewport captures; content, links and images unchanged')


def supplemental():
    """Close views of changed cues and a visibly focused control on navy."""
    server = http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory='/tmp'))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    checks=[]
    targets=(('home-dark-focus','home','.home-selected a'),
             ('home-editorial','home','.home-latest-analysis'),
             ('native-signal','native','.brief-signal'),
             ('v2-finding','laos-v2-private','.brief-reading-finding'),
             ('record-custody','record','.custody'))
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for width in (375,1280):
            page=browser.new_page(viewport={'width':width,'height':900},reduced_motion='reduce')
            page.add_init_script("sessionStorage.setItem('ipr-intro','1')")
            for name,route,selector in targets:
                suffix,path=ROUTES[route]
                page.goto(f'http://127.0.0.1:{server.server_port}/ipr-coastal-after{suffix}/{path}',wait_until='networkidle')
                page.evaluate('document.fonts.ready')
                node=page.locator(selector).first
                if not node.is_visible():
                    checks.append({'component':name,'width':width,'captured':False,'reason':'Existing compact layout hides this component'})
                    continue
                node.scroll_into_view_if_needed()
                if name=='home-dark-focus':
                    page.keyboard.press('Tab'); node.focus()
                    assert node.evaluate('(el)=>el.matches(":focus-visible")')
                    assert node.evaluate('(el)=>getComputedStyle(el).outlineColor')=='rgb(146, 213, 204)'
                    png=EVIDENCE/'shots'/f'after-{name}-{width}.png'
                    page.screenshot(path=str(png))
                else:
                    png=EVIDENCE/'shots'/f'after-{name}-{width}.png'
                    node.screenshot(path=str(png))
                with Image.open(png) as im: im.save(png.with_suffix('.webp'),'WEBP',lossless=True)
                png.unlink()
                checks.append({'component':name,'width':width,'captured':True})
            page.close()
        browser.close()
    server.shutdown()
    (EVIDENCE/'supplemental.json').write_text(json.dumps(checks,indent=2))


def refresh_modes():
    """Refresh media-specific evidence after a print-only refinement."""
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory='/tmp'))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for width in (375,1280):
            page=browser.new_page(viewport={'width':width,'height':900},reduced_motion='reduce')
            page.add_init_script("sessionStorage.setItem('ipr-intro','1')")
            for route,(suffix,path) in ROUTES.items():
                page.emulate_media(media='screen',forced_colors='none')
                page.goto(f'http://127.0.0.1:{server.server_port}/ipr-coastal-after{suffix}/{path}',wait_until='networkidle')
                page.evaluate('document.fonts.ready')
                page.keyboard.press('Tab')
                for mode in ('focus','forced','print'):
                    page.emulate_media(media='print' if mode=='print' else 'screen',forced_colors='active' if mode=='forced' else 'none')
                    png=EVIDENCE/'shots'/f'after-{route}-{width}-{mode}.png'
                    page.screenshot(path=str(png),timeout=60000)
                    with Image.open(png) as im:im.save(png.with_suffix('.webp'),'WEBP',lossless=True)
                    png.unlink()
            page.close()
        browser.close()
    server.shutdown()


if __name__ == '__main__':
    main()
    supplemental()
