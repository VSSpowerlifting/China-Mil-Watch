#!/usr/bin/env python3
"""Full-page reading-design comparisons and measured geometry; local trees only.

Complements verify_brief_journal.py's all-issue accessibility matrix. Never
changes manuscripts, manifests, output, browser profiles or publication state.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_brief_journal import REPRESENTATIVES, WIDTHS, server


METRICS = r'''() => {
 const q=s=>document.querySelector(s), rect=n=>n.getBoundingClientRect();
 const prose=[...document.querySelectorAll('.brief-reading-section>p')];
 const n=prose[0] || q('.brief-section>p'), c=getComputedStyle(n);
 const main=q('.brief-main'), nav=q('.brief-reading-navigation');
 // Character ranges count rendered characters on each real line, including links.
 const lines=[];
 for (const p of prose) {
   const rows=new Map(), walker=document.createTreeWalker(p,NodeFilter.SHOW_TEXT);
   let node;
   while(node=walker.nextNode()) for(let i=0;i<node.length;i++) {
     const range=document.createRange();range.setStart(node,i);range.setEnd(node,i+1);
     const r=range.getBoundingClientRect();
     if(r.width>0) {const y=Math.round(r.y);rows.set(y,(rows.get(y)||0)+1);}
   }
   lines.push([...rows.values()]);
 }
 const flat=lines.flat(), complete=lines.flatMap(p=>p.slice(0,-1));
 const probe=document.createElement('span');probe.style.font=c.font;
 probe.textContent='0';document.body.append(probe);const ch=rect(probe).width;probe.remove();
 const wrap=main.closest('.wrap'), wc=getComputedStyle(wrap);
 const rgb=s=>(s.match(/[\d.]+/g)||[]).map(Number);
 const lum=s=>{const [r,g,b]=rgb(s).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return .2126*r+.7152*g+.0722*b};
 let ground=n;
 while(ground.parentElement && rgb(getComputedStyle(ground).backgroundColor)[3]===0) ground=ground.parentElement;
 const bg=getComputedStyle(ground).backgroundColor, l1=lum(c.color),l2=lum(bg);
 return {viewport:innerWidth,main:rect(main).width,prose:rect(n).width,
   main_padding:getComputedStyle(main).padding,nav:rect(nav).width,
   gap:getComputedStyle(q('.brief-layout')).columnGap,font:c.fontSize,
   line_height:c.lineHeight,measure_ch:rect(n).width/ch,
   main_border:getComputedStyle(main).borderInlineWidth,
   main_background:getComputedStyle(main).backgroundColor,
   wrap_background:wc.backgroundColor,effective_background:bg,wrap_border:wc.borderInlineWidth,
   text_contrast:(Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05),
   height:document.documentElement.scrollHeight,article_height:rect(main).height,
   prose_lines:flat.length,characters_per_line_max:Math.max(0,...flat),
   complete_line_mean:complete.reduce((a,b)=>a+b,0)/(complete.length||1),
   overflow:document.documentElement.scrollWidth>innerWidth+1};
}'''


def ready(page):
    page.evaluate('''async () => {
      await document.fonts.ready;
      // Decode also lazily admitted in-article images before full-page captures.
      await Promise.all([...document.images].map(async i=>{
        i.loading='eager'; await i.decode();
      }));
      await Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{})));
    }''')


def screenshot(page, path):
    ready(page)
    page.screenshot(path=str(path), full_page=path.stem.endswith('-full'),
                    type='jpeg', quality=75, animations='disabled')


def capture_reading(root, baseline, fixtures, out):
    from playwright.sync_api import sync_playwright
    from tests.test_brief_unified_reading import PAGES
    out.mkdir(parents=True, exist_ok=True)
    failures, measurements, preserved = [], [], []
    # CSS-only delivery must leave every byte of all 18 approved HTML pages intact.
    for path in PAGES:
        route = path.relative_to(ROOT / 'output')
        equal = (root/route).read_bytes() == (baseline/route).read_bytes()
        preserved.append({'route':str(route),'exact_html_equal':equal})
        if not equal:
            failures.append({'route':str(route),'changed_html':True})
    with server(baseline) as before, server(root) as after, server(fixtures) as future, sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width':1440,'height':900}, reduced_motion='reduce')
        for phase, base in (('before',before),('after',after)):
            for width in WIDTHS:
                page.set_viewport_size({'width':width,'height':900})
                page.goto(base+REPRESENTATIVES['laos'][0],wait_until='networkidle')
                ready(page)
                metrics=page.evaluate(METRICS)
                measurements.append(dict(phase=phase,**metrics))
                if metrics['overflow'] or metrics['text_contrast'] < 4.5:
                    failures.append(dict(phase=phase,**metrics))
                if phase=='after' and width>=1280:
                    if not (metrics['prose']>=730 and metrics['prose']<=metrics['main']
                            and metrics['nav']<=248 and metrics['measure_ch']<=74.1):
                        failures.append(dict(phase=phase,**metrics))
                if width not in (375,1280,1440):
                    continue
                screenshot(page,out/f'laos-{phase}-{width}-full.jpg')
                if width == 1280:
                    continue
                for part,selector in (
                    ('finding','#reading-finding'),('first-section','.brief-reading-section'),
                    ('references','#s-publishers'),('citation','#s-cite')):
                    page.locator(selector).first.evaluate('(n)=>scrollTo(0,n.getBoundingClientRect().top+scrollY-112)')
                    screenshot(page,out/f'laos-{phase}-{width}-{part}.jpg')
                # Comparable reading progress: 25/50/75% of the prose, excluding
                # source lists and closing matter. Each viewport uses the same anchor rule.
                for depth in (.25,.5,.75):
                    page.evaluate('''fraction=>{const r=document.querySelector('.brief-structured').getBoundingClientRect();scrollTo(0,scrollY+r.top+r.height*fraction-112)}''',depth)
                    screenshot(page,out/f'laos-{phase}-{width}-depth-{int(depth*100)}.jpg')
        for direction in ('exploration-a','exploration-b'):
            page.set_viewport_size({'width':1440,'height':900})
            page.goto(before+REPRESENTATIVES['laos'][0],wait_until='networkidle')
            page.add_style_tag(content=(out/(direction+'.css')).read_text())
            screenshot(page,out/(direction+'-laos-1440-full.jpg'))
            page.locator('#reading-aviation').evaluate('(n)=>scrollTo(0,n.getBoundingClientRect().top+scrollY-140)')
            screenshot(page,out/(direction+'-laos-1440-middle.jpg'))
        # Full experiences rather than only isolated objects, including no-photo
        # No. 12 (asset denial), short/pilot No. 1 and the rights-held No. 10.
        for name in ('trident','fourteen','pilot'):
            for width in (375,1440):
                page.set_viewport_size({'width':width,'height':900})
                page.goto(after+REPRESENTATIVES[name][0],wait_until='networkidle')
                screenshot(page,out/f'{name}-after-{width}-full.jpg')
        for name,route in (('no-photo-12','the-pla-watch/posts/2026-08-01.html'),
                           ('rights-hold-10','the-pla-watch/posts/2026-07-11.html')):
            page.set_viewport_size({'width':1440,'height':900})
            page.goto(after+route,wait_until='networkidle')
            screenshot(page,out/f'{name}-after-1440-full.jpg')
        for fixture in sorted((fixtures/'briefs').glob('*.html')):
            for width in (375,1440):
                page.set_viewport_size({'width':width,'height':900})
                page.goto(future+str(fixture.relative_to(fixtures)),wait_until='networkidle')
                screenshot(page,out/f'{fixture.stem}-{width}-full.jpg')
        # Native evidence/source components already admitted in No. 17.
        page.set_viewport_size({'width':1440,'height':900})
        page.goto(after+REPRESENTATIVES['trident'][0],wait_until='networkidle')
        for part,selector in (('signal','.brief-signal'),('sources','#s-sources')):
            page.locator(selector).first.evaluate('(n)=>scrollTo(0,n.getBoundingClientRect().top+scrollY-112)')
            screenshot(page,out/f'trident-{part}.jpg')
        browser.close()
    report={'measurements':measurements,'preserved':preserved,'failures':failures,
            'screenshots':'Chromium 900px viewport height; DPR 1; self-hosted fonts loaded; reduced motion in both phases',
            'depth_rule':'Fraction of structured prose height, excluding publisher references and closing matter'}
    (out/'reading-receipts.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return bool(failures)


def verify_closing(root, out):
    """Final print correction and real citation copying on the retained scripts."""
    from playwright.sync_api import sync_playwright
    from tests.test_brief_unified_reading import PAGES
    checks, failures = [], []
    with server(root) as url, sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(permissions=['clipboard-read','clipboard-write'],
                                      viewport={'width':1280,'height':900})
        page = context.new_page()
        earlier=json.loads((out/'reading-receipts.json').read_text())
        for width in WIDTHS:
            page.set_viewport_size({'width':width,'height':900})
            page.goto(url+REPRESENTATIVES['laos'][0],wait_until='networkidle')
            ready(page)
            actual=page.evaluate(METRICS)
            expected=next(m for m in earlier['measurements'] if m['phase']=='after' and m['viewport']==width)
            stable=all(actual[k]==expected[k] for k in ('main','prose','nav','gap','font','line_height','height'))
            if not stable:
                failures.append({'screen_geometry_changed':width,'actual':actual})
            checks.append({'width':width,'mode':'final-screen-geometry','unchanged':stable})
        page.set_viewport_size({'width':1280,'height':900})
        for path in PAGES:
            route=str(path.relative_to(ROOT/'output'))
            page.goto(url+route,wait_until='networkidle')
            page.emulate_media(media='print')
            ready(page)
            data=page.evaluate('''()=>({
                navigation_hidden:getComputedStyle(document.querySelector('.brief-reading-navigation')).display==='none',
                backgrounds:[...document.querySelectorAll('.brief-main,.brief-signal,.brief-reading-finding,.brief-trail,.brief-citation-section')].map(n=>getComputedStyle(n).backgroundImage),
                wrap_background:getComputedStyle(document.querySelector('.brief-main').closest('.wrap')).backgroundColor,
                finding_font:document.querySelector('.brief-reading-finding blockquote p')?getComputedStyle(document.querySelector('.brief-reading-finding blockquote p')).fontFamily:null
            })''')
            if not data['navigation_hidden'] or any(b!='none' for b in data['backgrounds']) or data['wrap_background']!='rgb(255, 255, 255)':
                failures.append(dict(route=route,**data))
            checks.append(dict(route=route,mode='print',**data))
            if route==REPRESENTATIVES['laos'][0]:
                if 'Source Serif' not in data['finding_font']:
                    failures.append({'route':route,'incorrect_print_finding':data})
                page.locator('#reading-finding').evaluate('(n)=>scrollTo(0,n.getBoundingClientRect().top+scrollY-140)')
                page.screenshot(path=str(out/'laos-print.png'))
                page.pdf(path=str(out/'laos-print.pdf'),format='A4',print_background=False)
            page.emulate_media(media='screen')
        for name in ('laos','trident'):
            page.goto(url+REPRESENTATIVES[name][0],wait_until='networkidle')
            button=page.locator('button[data-copy]').first
            target=button.get_attribute('data-copy')
            expected=' '.join(page.locator('#'+target).text_content().split())
            button.click()
            page.wait_for_function("navigator.clipboard.readText().then(s=>s===document.querySelector('[data-copy]').closest('.ed-cite').querySelector('[id]').textContent.replace(/\\s+/g,' ').trim())")
            copied=page.evaluate('navigator.clipboard.readText()')
            if copied!=expected:
                failures.append({'citation_copy':name})
            checks.append({'route':REPRESENTATIVES[name][0],'mode':'citation-copy','exact_visible_text':copied==expected})
        browser.close()
    report={'checks':checks,'failures':failures}
    (out/'closing-receipts.json').write_text(json.dumps(report,indent=2)+'\n')
    print('%d final print/citation checks; %d failures'%(len(checks),len(failures)))
    return bool(failures)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','baseline','fixtures','out'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--closing-only',action='store_true')
    args=parser.parse_args()
    if args.closing_only:
        raise SystemExit(verify_closing(args.root,args.out))
    raise SystemExit(capture_reading(args.root,args.baseline,args.fixtures,args.out) or verify_closing(args.root,args.out))
