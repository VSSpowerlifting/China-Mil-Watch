#!/usr/bin/env python3
"""Offline publication parity and broad browser review of the public frontend.

Uses complete renderer/carry-forward trees. Never renders, contacts editorial
publishers, or writes output/. Captures are browser images, never concepts.
The existing verify_frontend_candidate.py remains the deeper finder/citation
reader-flow check; this extends coverage to every public page family.
"""
import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WIDTHS = (375, 768, 1440)
PROFILES = ('default', 'no-js', 'script-failure', 'reduced-motion',
            'no-anim', 'forced-colors', 'print')


class PublicationBody(HTMLParser):
    """Meaning-bearing body only; decorative subtrees do not carry evidence."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.stack = []
        self.hidden = 0
        self.text, self.links, self.ids = [], [], []
        self.stylesheets = []
        self.script_count = 0
        self.redirect = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and 'stylesheet' in attrs.get('rel', '').split():
            self.stylesheets.append(attrs.get('href', ''))
        if tag == 'script':
            self.script_count += 1
        if tag == 'meta' and attrs.get('http-equiv', '').lower() == 'refresh':
            match = re.search(r'url\s*=\s*(.+)', attrs.get('content', ''), re.I)
            if match:
                self.redirect = match[1].strip().strip('"\'')
        if tag == 'body':
            self.in_body = True
            return
        if not self.in_body:
            return
        hide = tag in ('script', 'style') or attrs.get('aria-hidden') == 'true'
        if tag not in self.VOID:
            self.stack.append((tag, hide))
            self.hidden += int(hide)
        if self.hidden or hide:
            return
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])

    def handle_endtag(self, tag):
        if tag == 'body':
            self.in_body = False
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                self.hidden -= sum(int(hide) for _, hide in self.stack[i:])
                del self.stack[i:]
                break

    def handle_data(self, value):
        if self.in_body and not self.hidden:
            self.text.append(value)

    def contract(self):
        return {'text': ' '.join(' '.join(self.text).split()),
                'links': self.links, 'ids': self.ids}


def read_body(path):
    parsed = PublicationBody()
    parsed.feed(Path(path).read_text(encoding='utf-8'))
    return parsed


def compare_publication(candidate, baseline, require_enrichment=True):
    """Fail on missing routes, altered publication text, links or anchors."""
    candidate, baseline = Path(candidate), Path(baseline)
    actual = {p.relative_to(candidate).as_posix() for p in candidate.rglob('*.html')}
    expected = {p.relative_to(baseline).as_posix() for p in baseline.rglob('*.html')}
    failures = []
    if actual != expected:
        failures.append({'missing_routes': sorted(expected - actual),
                         'unexpected_routes': sorted(actual - expected)})
    links = anchors = redirected = static_weeks = 0
    for route in sorted(actual & expected):
        current, old = read_body(candidate / route), read_body(baseline / route)
        differences = [key for key, value in old.contract().items()
                       if current.contract()[key] != value]
        if differences:
            failures.append({'route': route, 'changed': differences})
        if current.redirect != old.redirect:
            failures.append({'route': route, 'changed': ['redirect']})
        links += len(current.links)
        anchors += len(current.ids)
        redirected += bool(current.redirect)
        if route.startswith('week-'):
            static_weeks += 1
            if current.script_count:
                failures.append({'route': route, 'changed': ['script-free week']})
        if require_enrichment and not current.redirect:
            # #287 moved published posts into the unified IPR Briefs shell.
            # Historical index, archive, and terms still use the predecessor skin.
            predecessor_surface = (route.startswith('the-pla-watch/')
                                   and not route.startswith('the-pla-watch/posts/'))
            sheet = 'historical-enrichment.css' if predecessor_surface else 'enrichment.css'
            if not any(Path(urlsplit(url).path).name == sheet
                       for url in current.stylesheets):
                failures.append({'route': route, 'changed': ['missing enrichment stylesheet']})
    if 'timelines.html' in actual or any(route.startswith('timeline/') for route in actual):
        failures.append({'changed': ['unpublished timeline exposed']})
    return {'routes_checked': len(actual & expected), 'links_checked': links,
            'anchors_checked': anchors, 'redirects_checked': redirected,
            'script_free_weeks': static_weeks, 'failures': failures}


def representative_routes(root):
    """Select actual files; never invent an edition, source or record."""
    root = Path(root)
    routes = {}
    for label, route in [('home', 'index.html'), ('archive', 'archive.html'),
                         ('catalog', 'analysis.html'), ('desks-map', 'desks.html'),
                         ('desk-china', 'china.html'), ('desk-singapore', 'singapore.html'),
                         ('desk-held', 'us-indopacific.html'), ('desk-research', 'vietnam.html'),
                         ('about', 'about.html'), ('methodology', 'methodology.html'),
                         ('coverage', 'coverage.html'), ('sources', 'sources.html'),
                         ('corpus-guide', 'corpus-guide.html'), ('corpus', 'corpus.html'),
                         ('compatibility-bridge', 'pla-watch.html'), ('redirect-signals', 'signals.html')]:
        if (root / route).is_file():
            routes[label] = route
    records = list((root / 'record').glob('*.html'))
    if records:
        selected = root / 'record/3924.html'
        routes['record-paired'] = (selected if selected.is_file() else records[0]).relative_to(root).as_posix()
        routes['record-largest'] = max(records, key=lambda p: p.stat().st_size).relative_to(root).as_posix()
        for path in sorted(records, key=lambda p: p.stat().st_size):
            text = path.read_text(encoding='utf-8')
            if re.search(r'<h1[^>]*\blang=', text) and 'record-title-pair' not in text:
                routes['record-original-only'] = path.relative_to(root).as_posix()
                break
    for path in sorted((root / 'briefs').glob('*.html')):
        routes['brief-' + path.stem] = path.relative_to(root).as_posix()
    for label, desired in [('source-live', 'pla_daily.html'), ('source-shadow', 'jp_mod_news_ja.html')]:
        path = root / 'source' / desired
        if path.is_file():
            routes[label] = path.relative_to(root).as_posix()
    weeks = sorted(root.glob('week-*.html'))
    if weeks:
        routes['week'] = max(weeks, key=lambda p: p.stat().st_size).relative_to(root).as_posix()
        numbered = [p for p in weeks if re.fullmatch(r'week-\d{4}-\d{2}-\d{2}-\d+\.html', p.name)]
        if numbered:
            routes['week-pagination'] = numbered[0].relative_to(root).as_posix()
    posts = sorted((root / 'the-pla-watch/posts').glob('*.html'))
    if posts:
        routes['historical-oldest'] = posts[0].relative_to(root).as_posix()
        routes['historical-largest'] = max(posts, key=lambda p: p.stat().st_size).relative_to(root).as_posix()
        routes['historical-latest'] = posts[-1].relative_to(root).as_posix()
    for name in ('index', 'archive', 'terms'):
        route = 'the-pla-watch/' + name + '.html'
        if (root / route).is_file():
            routes['historical-' + name] = route
    redirects = sorted((root / 'article').glob('*.html'))
    if redirects:
        routes['redirect-article'] = redirects[0].relative_to(root).as_posix()
    return routes


def delivery_inventory(root):
    from scripts.verify_frontend_delivery import verify
    result = verify(root)
    assert not result['failures'], result['failures'][:10]
    return {key: value for key, value in result.items() if key != 'routes'}


def full_capture(page, path):
    """Observe actual entrance reveals and lazy images before a full capture."""
    position = page.evaluate('({x:scrollX,y:scrollY})')
    step=max(200,page.evaluate('innerHeight')*.8)
    height=page.evaluate('document.documentElement.scrollHeight')
    for y in range(0,int(height),int(step)):
        page.evaluate('(y)=>scrollTo(0,y)',y)
        page.wait_for_timeout(80)
    for img in page.locator('img').all():
        if img.is_visible():
            img.scroll_into_view_if_needed()
            page.wait_for_function('''(e)=>{const src=e.currentSrc,stable=e.dataset.captureSrc===src;e.dataset.captureSrc=src;return stable && e.complete && e.naturalWidth>0}''',arg=img.element_handle(),polling='raf')
            img.evaluate('(e)=>e.decode()')
    settle_document_animations(page)
    page.evaluate('(p)=>scrollTo(p.x,p.y)', position)
    page.screenshot(path=str(path), full_page=True, type='jpeg', quality=85)


def external_font_delivery(browser, url, route, out):
    """Measure real remote font requests separately from the offline matrix."""
    context=browser.new_context(viewport={'width':1440,'height':1000})
    page=context.new_page();session=context.new_cdp_session(page)
    session.send('Network.enable')
    requests={}
    def received(event):
        response=event['response']
        host=urlsplit(response['url']).hostname or ''
        if host in ('fonts.googleapis.com','fonts.gstatic.com'):
            requests[event['requestId']]={'url':response['url'],'status':response['status'],
                                         'type':event['type'],'from_disk_cache':response.get('fromDiskCache',False)}
    def finished(event):
        if event['requestId'] in requests:
            requests[event['requestId']]['encoded_transfer_bytes']=event['encodedDataLength']
    session.on('Network.responseReceived',received)
    session.on('Network.loadingFinished',finished)
    failures=[]
    page.on('requestfailed',lambda request:failures.append({'url':request.url,'failure':request.failure}) if (urlsplit(request.url).hostname or '') in ('fonts.googleapis.com','fonts.gstatic.com') else None)
    page.goto(urljoin(url.rstrip('/')+'/',route),wait_until='networkidle')
    page.evaluate('document.fonts.ready')
    page.screenshot(path=str(Path(out)/'historical-external-fonts-desktop.png'))
    result={'route':route,'mode':'Network font probe: local fonts enabled and Google font requests allowed',
            'requests':list(requests.values()),'failures':failures,
            'remote_encoded_transfer_bytes':sum(r.get('encoded_transfer_bytes',0) for r in requests.values()),
            'local_fonts':page.evaluate('performance.getEntriesByType("resource").filter(e=>/\\.woff2?(?:$|\\?)/.test(e.name)).map(e=>({url:e.name,transfer:e.transferSize,body:e.encodedBodySize}))'),
            'faces':page.evaluate('Array.from(document.fonts).map(f=>({family:f.family,status:f.status,weight:f.weight}))')}
    context.close()
    return result


def settle_document_animations(page,timeout=6):
    """Direct evaluation remains usable under the script-failure CSP."""
    deadline=time.monotonic()+timeout
    predicate='()=>document.getAnimations().every(a=>a.timeline!==document.timeline || a.effect.getComputedTiming().iterations===Infinity || a.playState!=="running")'
    while not page.evaluate(predicate):
        assert time.monotonic()<deadline,'Document-time animations did not settle'
        page.wait_for_timeout(50)


def focus_contrast(page, target, ground):
    target.focus();page.keyboard.press('Tab');page.keyboard.press('Shift+Tab')
    assert target.evaluate('(e)=>e.matches(":focus-visible")')
    values=target.evaluate('''(e,selector)=>{const s=getComputedStyle(e),b=getComputedStyle(document.querySelector(selector));return {outline:s.outlineColor,outline_width:parseFloat(s.outlineWidth),style:s.outlineStyle,background:b.backgroundColor}}''',ground)
    def luminance(color):
        channels=[float(value)/255 for value in re.findall(r'[\d.]+',color)[:3]]
        channels=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in channels]
        return sum(c*w for c,w in zip(channels,(.2126,.7152,.0722)))
    a,b=luminance(values['outline']),luminance(values['background'])
    values['contrast']=round((max(a,b)+.05)/(min(a,b)+.05),3)
    assert values['outline_width']>=2 and values['style']=='solid' and values['contrast']>=3,values
    return values


def browser_review(url, root, out, baseline_url=None, released_url=None, widths=WIDTHS, private_url=None):
    from playwright.sync_api import sync_playwright
    root, out = Path(root), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    routes = representative_routes(root)
    receipt = {'captures': 'Actual Chromium implementation images', 'routes': routes,
               'cases': [], 'flows': [], 'errors': [], 'delivery': []}
    def progress():
        (out/'BROWSER_PROGRESS.json').write_text(json.dumps(receipt,indent=2)+'\n')
    progress()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        receipt['browser'] = browser.version
        for width in widths:
            for profile in PROFILES:
                context = browser.new_context(viewport={'width': width, 'height': 844 if width < 600 else 1000},
                                              java_script_enabled=profile != 'no-js',
                                              reduced_motion='reduce' if profile == 'reduced-motion' else 'no-preference')
                if profile == 'no-anim':
                    context.add_init_script('document.addEventListener("DOMContentLoaded",()=>document.documentElement.classList.add("no-anim"))')
                if profile == 'script-failure':
                    context.route('**/*.js', lambda request: request.abort())
                    def block_page_scripts(request):
                        response = request.fetch()
                        headers = dict(response.headers)
                        headers['content-security-policy'] = "script-src 'none'"
                        request.fulfill(response=response, headers=headers)
                    context.route('**/*.html', block_page_scripts)
                # Preserve historic Google fonts as an explicitly disclosed
                # dependency while keeping the review offline/deterministic.
                context.route('https://fonts.googleapis.com/**', lambda request: request.abort())
                context.route('https://fonts.gstatic.com/**', lambda request: request.abort())
                page = context.new_page()
                page.on('pageerror', lambda error: receipt['errors'].append(str(error)))
                page.on('response', lambda response: receipt['errors'].append(str(response.status) + ' ' + response.url) if response.status >= 400 else None)
                if profile == 'forced-colors':
                    page.emulate_media(forced_colors='active')
                if profile == 'print':
                    page.emulate_media(media='print')
                for label, route in routes.items():
                    page.goto(urljoin(url.rstrip('/') + '/', route), wait_until='networkidle')
                    page.evaluate('document.fonts.ready')
                    if profile in ('default', 'script-failure'):
                        # The legacy reading-progress ScrollTimeline tracks
                        # the reader and never settles in document time.
                        settle_document_animations(page)
                    if label.startswith('historical-'):
                        assert page.evaluate('()=>document.getAnimations().filter(a=>a.timeline===document.timeline).every(a=>a.effect.getComputedTiming().iterations!==Infinity)'),(route,width,profile,'autonomous infinite historical motion')
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), (route, width, profile, 'overflow')
                    assert page.locator('h1').count() == 1, (route, width, profile, 'h1')
                    assert page.locator('h1').is_visible(), (route, width, profile, 'hidden heading')
                    assert page.locator('main').inner_text().strip(), (route, width, profile, 'empty reading')
                    assert page.locator('img').evaluate_all('(els)=>els.every(e=>!e.complete || e.naturalWidth>0)'), (route, width, profile, 'broken image')
                    assert page.locator('.terrain-stage').evaluate_all('(els)=>els.every(e=>e.getAttribute("aria-hidden")==="true" && getComputedStyle(e).pointerEvents==="none")'), (route, width, profile, 'decoration intercepts input')
                    if profile in ('no-js', 'reduced-motion', 'no-anim', 'script-failure'):
                        assert page.locator('[data-reveal]:not([aria-hidden="true"])').evaluate_all('(els)=>els.every(e=>parseFloat(getComputedStyle(e).opacity)>0.99)'), (route, width, profile, 'hidden content')
                    if profile in ('reduced-motion', 'no-anim'):
                        assert page.locator('.terrain-lines').evaluate_all('(els)=>els.every(e=>getComputedStyle(e).animationName==="none")'), (route, width, profile, 'art motion')
                    if profile in ('print', 'forced-colors'):
                        assert page.locator('.terrain-stage').evaluate_all('(els)=>els.every(e=>getComputedStyle(e).display==="none")'), (route, width, profile, 'printed decoration')
                    if profile == 'print':
                        assert page.locator('h1').evaluate('(e)=>getComputedStyle(e).color') == 'rgb(0, 0, 0)', (route,width,'print heading contrast')
                    if profile == 'no-js' and label == 'archive':
                        assert page.locator('#results .record-row').count() == 50
                        assert not page.locator('#controls').is_visible()
                    case = {'route': route, 'family': label, 'width': width, 'profile': profile,
                            'h1_y': round(page.locator('h1').bounding_box()['y'], 1), 'url': page.url}
                    receipt['cases'].append(case)
                    progress()
                    if profile == 'default' and not label.startswith('redirect-'):
                        device = 'mobile' if width == 375 else 'tablet' if width == 768 else 'desktop'
                        page.screenshot(path=str(out / (label + '-' + device + '.png')))
                        if width in (375, 1440) and label in ('home', 'archive', 'catalog', 'desks-map', 'historical-largest', 'brief-maritime-cooperation-2026'):
                            full_capture(page,out / (label + '-' + device + '-full.jpg'))
                    if profile != 'print' and not label.startswith('redirect-'):
                        menu = page.locator('.shell-menu>summary')
                        visible = next((item for item in menu.all() if item.is_visible()), None)
                        if visible:
                            visible.focus(); page.keyboard.press('Enter')
                            assert visible.evaluate('(e)=>e.parentElement.open'), (route, width, profile, 'menu')
                            page.keyboard.press('Escape')
                            if profile not in ('no-js', 'script-failure') and not route.startswith('week-'):
                                assert visible.evaluate('(e)=>!e.parentElement.open && e===document.activeElement'), (route, width, profile, 'menu Escape/focus')
                            else:
                                if visible.evaluate('(e)=>e.parentElement.open'):
                                    page.keyboard.press('Enter')
                context.close()
                print('Reviewed %s/%s: %s representative routes' % (width,profile,len(routes)),flush=True)
                progress()
        context = browser.new_context(viewport={'width':375,'height':844}, permissions=['clipboard-read', 'clipboard-write'])
        page = context.new_page()
        for label in ('home', 'about', 'corpus', 'historical-index'):
            if label not in routes:
                continue
            page.goto(urljoin(url.rstrip('/') + '/', routes[label]), wait_until='networkidle')
            page.keyboard.press('Tab')
            focused = page.locator(':focus')
            assert 'skip' in (focused.get_attribute('class') or ''), (label, 'skip focus')
            page.keyboard.press('Enter')
            assert urlsplit(page.url).fragment, (label, 'skip anchor')
            receipt['flows'].append({'skip_link': routes[label]})
        for width in widths:
            page.set_viewport_size({'width':width,'height':844 if width<600 else 1000})
            page.goto(urljoin(url.rstrip('/')+'/',routes['home']),wait_until='networkidle')
            menu=next(item for item in page.locator('.shell-menu>summary').all() if item.is_visible())
            for name,target,ground in [('menu',menu,'.pacific-opening'),
                    ('hero',page.locator('.pacific-opening .btn').first,'.pacific-opening'),
                    ('coast',page.locator('.home-coast-band .btn').first,'.home-coast-band')]:
                values=focus_contrast(page,target,ground)
                receipt['flows'].append({'dark_focus':name,'width':width,**values})
                page.screenshot(path=str(out/('home-%s-focus-%s.png'%(name,width))))
            page.goto(urljoin(url.rstrip('/')+'/',routes['archive']),wait_until='networkidle')
            disclosure=page.locator('.finder-more>summary')
            disclosure.focus();page.keyboard.press('Enter')
            assert disclosure.evaluate('(e)=>e.parentElement.open')
            page.locator('#f-desk').focus()
            assert page.locator(':focus').evaluate('(e)=>getComputedStyle(e).outlineStyle') == 'solid'
            page.screenshot(path=str(out/('archive-expanded-filters-%s.png'%width)))
            receipt['flows'].append({'expanded_filters':width})
        page.set_viewport_size({'width':375,'height':844})
        for label, route in routes.items():
            if not label.startswith(('brief-', 'historical-')):
                continue
            page.goto(urljoin(url.rstrip('/') + '/', route), wait_until='networkidle')
            links = page.locator('main a[href^="#"]')
            navigation = page.locator('.brief-reading-navigation>summary')
            if navigation.count() and not navigation.evaluate('(e)=>e.parentElement.open'):
                navigation.focus(); page.keyboard.press('Enter')
            link = next((item for item in links.all() if item.is_visible()), None)
            if link:
                target = link.get_attribute('href')[1:]
                assert page.locator('[id="' + target + '"]').count(), (route, target)
                link.focus(); page.keyboard.press('Enter')
                assert unquote(urlsplit(page.url).fragment) == target
                receipt['flows'].append({'section_anchor': route, 'target': target})
        if 'record-paired' in routes:
            page.goto(urljoin(url.rstrip('/') + '/',routes['record-paired']),wait_until='networkidle')
            button=page.locator('[data-copy="cite-source-text"]')
            if button.count():
                button.click()
                expected=' '.join(page.locator('#cite-source-text').inner_text().split())
                assert page.evaluate('navigator.clipboard.readText()') == expected
                receipt['flows'].append({'copy_source_citation':routes['record-paired']})
                page.screenshot(path=str(out/'record-citation-mobile.png'))
            history=page.locator('.record-history>summary')
            if history.count():
                history.focus();page.keyboard.press('Enter')
                assert history.evaluate('(e)=>e.parentElement.open')
                receipt['flows'].append({'keyboard_record_history':routes['record-paired']})
                page.screenshot(path=str(out/'record-history-mobile.png'))
        if 'historical-largest' in routes:
            page.goto(urljoin(url.rstrip('/') + '/',routes['historical-largest']),wait_until='networkidle')
            button=page.locator('#pw-cite-copy')
            if button.count():
                expected=page.locator('#pw-cite').text_content().strip()
                button.click()
                assert page.evaluate('navigator.clipboard.readText()') == expected
                receipt['flows'].append({'copy_historical_citation':routes['historical-largest']})
                page.screenshot(path=str(out/'historical-citation-mobile.png'))
        if 'desks-map' in routes:
            page.goto(urljoin(url.rstrip('/') + '/',routes['desks-map']),wait_until='networkidle')
            link=page.locator('.deskmap-plate .deskmap-enter a').first
            destination=link.get_attribute('href')
            link.focus()
            page.screenshot(path=str(out/'desks-map-focus-mobile.png'))
            page.keyboard.press('Enter')
            page.wait_for_url('**/'+destination)
            assert page.locator('h1').count()==1
            receipt['flows'].append({'keyboard_desk_map_destination':destination})
        context.close()
        if private_url:
            context=browser.new_context(viewport={'width':1440,'height':1000})
            page=context.new_page()
            private_route='timeline/maritime-cooperation-2026.html'
            page.goto(urljoin(private_url.rstrip('/')+'/',private_route),wait_until='networkidle')
            assert page.locator('.tl-context-tracks').evaluate('(e)=>e.open'), 'private desktop date tracks'
            summary=page.locator('.nav-more>summary')
            summary.focus();page.keyboard.press('Enter')
            assert summary.evaluate('(e)=>e.parentElement.open')
            page.keyboard.press('Escape')
            assert summary.evaluate('(e)=>!e.parentElement.open && e===document.activeElement')
            receipt['private_review']={'route':private_route,'desktop_date_tracks_open':True,'menu_escape_restores_focus':True,'published':False}
            page.screenshot(path=str(out/'private-timeline-desktop.png'))
            context.close()
        for label in ('home', 'archive', 'catalog', 'record-largest', 'historical-largest'):
            if label not in routes:
                continue
            for name, base in [('candidate',url), ('current-main',baseline_url), ('released',released_url)]:
                if not base:
                    continue
                context = browser.new_context(viewport={'width':1440,'height':1000})
                context.route('https://fonts.googleapis.com/**', lambda request: request.abort())
                context.route('https://fonts.gstatic.com/**', lambda request: request.abort())
                page = context.new_page()
                for cached in (False, True):
                    page.goto(urljoin(base.rstrip('/') + '/', routes[label]), wait_until='networkidle')
                    page.evaluate('document.fonts.ready')
                    values = page.evaluate('''()=>({resources:[...performance.getEntriesByType('navigation'),...performance.getEntriesByType('resource')].map(e=>({url:e.name,transfer:e.transferSize,body:e.encodedBodySize})),dom_ready:performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd})''')
                    receipt['delivery'].append(dict(route=routes[label],tree=name,cached=cached,**values))
                if name != 'candidate':
                    page.screenshot(path=str(out / (name + '-' + label + '-desktop.png')))
                    for width in widths:
                        if width == 1440:
                            continue
                        page.set_viewport_size({'width':width,'height':844 if width<600 else 1000})
                        page.goto(urljoin(base.rstrip('/')+'/',routes[label]),wait_until='networkidle')
                        page.evaluate('document.fonts.ready')
                        device='mobile' if width==375 else 'tablet'
                        page.screenshot(path=str(out/(name+'-'+label+'-'+device+'.png')))
                context.close()
        if 'historical-largest' in routes:
            receipt['external_font_delivery']=external_font_delivery(browser,url,routes['historical-largest'],out)
        browser.close()
    assert not receipt['errors'], receipt['errors'][:20]
    receipt['external_font_mode'] = 'Matrix blocks Google font endpoints; local font requests remain enabled. Separate network probe reports actual loaded faces and any remote delivery.'
    progress()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True); parser.add_argument('--baseline', required=True)
    parser.add_argument('--url'); parser.add_argument('--baseline-url'); parser.add_argument('--released-url');parser.add_argument('--private-url')
    parser.add_argument('--out', required=True); parser.add_argument('--static-only', action='store_true')
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    parity = compare_publication(args.root, args.baseline)
    (out / 'PUBLICATION_PARITY.json').write_text(json.dumps(parity,indent=2)+'\n')
    assert not parity['failures'], parity['failures'][:30]
    inventory = delivery_inventory(args.root)
    (out / 'DELIVERY_SUMMARY.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print('Publication parity and delivery passed for %s public routes' % parity['routes_checked'],flush=True)
    if not args.static_only:
        if not args.url:
            parser.error('--url is required unless --static-only')
        browser = browser_review(args.url,args.root,out,args.baseline_url,args.released_url,private_url=args.private_url)
        (out / 'BROWSER_QA.json').write_text(json.dumps(browser,indent=2)+'\n')
        print('Verified %s browser cases across %s representatives' % (len(browser['cases']),len(browser['routes'])))
    print('Compared %s public routes, %s links and %s anchors; complete delivery gate passes' % (parity['routes_checked'],parity['links_checked'],parity['anchors_checked']))


if __name__ == '__main__':
    main()
