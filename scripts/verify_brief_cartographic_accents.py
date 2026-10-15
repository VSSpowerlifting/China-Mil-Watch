#!/usr/bin/env python3
"""Review paint-only Brief accents against an immutable local Phase 2 tree.

Checks every published article's text geometry and accent/text separation at
five widths, plus future fixtures, print, forced colors and citation copying.
Screenshots use real Chromium and unchanged article HTML; never publishes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_brief_journal import PAGES, REPRESENTATIVES, WIDTHS, server
from scripts.verify_brief_reading_design import ready

INSPECT = r'''() => {
 const main=document.querySelector('.brief-main'), text=[];
 const walker=document.createTreeWalker(main,NodeFilter.SHOW_TEXT);
 let node;
 while(node=walker.nextNode()) if(node.textContent.trim() && node.parentElement.checkVisibility()) {
   const range=document.createRange();range.selectNodeContents(node);
   for(const r of range.getClientRects()) if(r.width&&r.height) text.push(r);
 }
 const overlap=(a,b)=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;
 const accents=[...main.querySelectorAll('.brief-section')].flatMap(n=>{
   const s=getComputedStyle(n,'::after');
   if(s.content==='none'||s.display==='none') return [];
   const r=n.getBoundingClientRect(), x=r.right-parseFloat(s.right)-parseFloat(s.width),
     y=r.top+parseFloat(getComputedStyle(n).borderTopWidth)+parseFloat(s.top);
   const box={left:x,right:x+parseFloat(s.width),top:y,bottom:y+parseFloat(s.height)};
   return [{id:n.id,box,intersections:text.filter(t=>overlap(box,t)).length,
     pointer_events:s.pointerEvents,has_profile:s.backgroundImage.startsWith('url(\"data:image/svg+xml,'),
     inside_viewport:box.left>=0&&box.right<=innerWidth}];
 });
 const geometry=[...document.querySelectorAll('.brief-main,.brief-reading-navigation,.brief-main p,.brief-main h2,.brief-main h3,.brief-main a,.brief-main img,.brief-main button')].map(n=>{
   const r=n.getBoundingClientRect(),s=getComputedStyle(n);
   return [n.tagName,n.id,r.x,r.y+scrollY,r.width,r.height,s.font,s.margin,s.padding,s.color,s.backgroundColor];
 });
 return {geometry,height:document.documentElement.scrollHeight,accents,
   overflow:document.documentElement.scrollWidth>innerWidth+1};
}'''


def shot(page, out, name, anchor=None):
    ready(page)
    if anchor:
        page.locator(anchor).first.evaluate('(n)=>scrollTo(0,n.getBoundingClientRect().top+scrollY-340)')
    page.evaluate('async()=>{await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))}')
    page.screenshot(path=str(out/(name+'.jpg')),full_page=not anchor,
                    type='jpeg',quality=86 if anchor else 78,animations='disabled')


def capture_review(page, current, previous, out):
    for phase,url in (('before',previous),('after',current)):
        for width in (1440,375):
            page.set_viewport_size({'width':width,'height':900})
            page.goto(url+REPRESENTATIVES['laos'][0],wait_until='networkidle')
            shot(page,out,f'laos-{phase}-{width}-full')
            if phase=='after':
                shot(page,out,f'laos-section-{width}','#reading-identity')
                shot(page,out,f'laos-sources-{width}','#s-publishers')
    for name,route in [('trident',REPRESENTATIVES['trident'][0]),('historical',REPRESENTATIVES['fourteen'][0]),('no-photo','briefs/xiangshan-security-frames-defense-ties.html')]:
        for width in (1440,375):
            page.set_viewport_size({'width':width,'height':900});page.goto(current+route,wait_until='networkidle')
            if name=='no-photo':
                assert page.locator('.brief-hero img').count()==0
            shot(page,out,f'{name}-after-{width}-full')
    for direction in 'abc':
        for name,anchor in [('laos','#reading-identity'),('trident','#s-why')]:
            page.set_viewport_size({'width':1440,'height':900});page.goto(previous+REPRESENTATIVES[name][0],wait_until='networkidle')
            page.add_style_tag(content=(out/f'direction-{direction}.css').read_text())
            shot(page,out,f'direction-{direction}-{name}-full')
            shot(page,out,f'direction-{direction}-{name}-section',anchor)


def verify(root, baseline, fixtures, out):
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True,exist_ok=True)
    checks, failures, preservation = [], [], []
    for p in PAGES:
        route=str(p.relative_to(ROOT/'output'))
        before=(baseline/route).read_bytes();after=(root/route).read_bytes()
        preservation.append({'route':route,'sha256':hashlib.sha256(after).hexdigest(),'unchanged':before==after})
    if not all(x['unchanged'] for x in preservation):
        raise ValueError('Article HTML differs from the approved baseline')
    with server(root) as current, server(baseline) as previous, server(fixtures) as future, sync_playwright() as pw:
        browser=pw.chromium.launch()
        context=browser.new_context(reduced_motion='reduce',permissions=['clipboard-read','clipboard-write'])
        page=context.new_page()
        for width in WIDTHS:
            page.set_viewport_size({'width':width,'height':900})
            for p in PAGES:
                route=str(p.relative_to(ROOT/'output'))
                data=[]
                for url in (previous,current):
                    page.goto(url+route,wait_until='networkidle');ready(page)
                    data.append(page.evaluate(INSPECT))
                a,b=data
                stable=a['geometry']==b['geometry'] and a['height']==b['height']
                safe=all(n['intersections']==0 and n['inside_viewport'] and n['pointer_events']=='none' and n['has_profile'] for n in b['accents'])
                record={'route':route,'width':width,'mode':'geometry-and-clearance','geometry_unchanged':stable,
                        'height':b['height'],'accents':b['accents'],'overflow':b['overflow']}
                checks.append(record)
                if not stable or not safe or b['overflow'] or not b['accents']: failures.append(record)
        # Open evidence disclosures so their visible text is also protected.
        for width in (375,1280):
            page.set_viewport_size({'width':width,'height':900})
            for p in PAGES:
                route=str(p.relative_to(ROOT/'output'));data=[]
                for url in (previous,current):
                    page.goto(url+route,wait_until='networkidle')
                    page.locator('.brief-main details').evaluate_all('(ns)=>ns.forEach(n=>n.open=true)')
                    ready(page);data.append(page.evaluate(INSPECT))
                a,b=data;stable=a['geometry']==b['geometry'] and a['height']==b['height']
                safe=all(not n['intersections'] and n['inside_viewport'] for n in b['accents'])
                record={'route':route,'width':width,'mode':'open-disclosures','geometry_unchanged':stable,'clear_of_text':safe}
                checks.append(record)
                if not stable or not safe or b['overflow']:failures.append(record)
        page.set_viewport_size({'width':1440,'height':900})
        for mode in ('print','forced-colors'):
            page.emulate_media(media='print' if mode=='print' else 'screen',forced_colors='active' if mode=='forced-colors' else 'none')
            for p in PAGES:
                route=str(p.relative_to(ROOT/'output'));page.goto(current+route);ready(page)
                data=page.evaluate(INSPECT)
                record={'route':route,'mode':mode,'accents_hidden':not data['accents']}
                checks.append(record)
                if not record['accents_hidden']:failures.append(record)
            page.emulate_media(media='screen',forced_colors='none')
        # Existing fixture HTML stays unchanged; intercept only its shared CSS.
        context.route('**/briefs.css',lambda route:route.fulfill(path=str(root/'briefs.css'),content_type='text/css'))
        for width in WIDTHS:
            page.set_viewport_size({'width':width,'height':900})
            for p in sorted((fixtures/'briefs').glob('*.html')):
                page.goto(future+str(p.relative_to(fixtures)),wait_until='networkidle');ready(page)
                data=page.evaluate(INSPECT)
                record={'route':p.name,'width':width,'mode':'future-clearance','accents':data['accents'],'overflow':data['overflow']}
                checks.append(record)
                if data['overflow'] or any(n['intersections'] or not n['inside_viewport'] for n in data['accents']):failures.append(record)
        context.unroute('**/briefs.css')
        for name in ('laos','trident'):
            page.goto(current+REPRESENTATIVES[name][0],wait_until='networkidle');ready(page)
            button=page.locator('button[data-copy]').first
            target=button.get_attribute('data-copy');expected=' '.join(page.locator('#'+target).text_content().split())
            button.click();page.wait_for_function('(text)=>navigator.clipboard.readText().then(s=>s===text)',arg=expected)
            checks.append({'mode':'citation-copy','route':name,'exact_text_copied':True})
        capture_review(page,current,previous,out)
        report={'chromium':browser.version,'baseline':'d5c3ca5169bf10eb7685897c234b06452c3592e5',
                'checks':len(checks),'receipts':checks,'preservation':preservation,'failures':failures}
        browser.close()
    (out/'accent-receipts.json').write_text(json.dumps(report,indent=2)+'\n')
    print('%d checks; %d failures'%(len(checks),len(failures)))
    return bool(failures)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('root','baseline','fixtures','out'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(verify(args.root,args.baseline,args.fixtures,args.out))
