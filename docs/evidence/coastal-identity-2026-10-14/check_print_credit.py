"""Measure homepage print credit overflow on exact-base/candidate local renders."""
import argparse
import functools
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--render-prefix',default='ipr-coastal')
    args=parser.parse_args()
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory='/tmp'))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    results=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for width in (375,1280):
            for phase in ('before','after'):
                page=browser.new_page(viewport={'width':width,'height':900},reduced_motion='reduce')
                page.add_init_script("sessionStorage.setItem('ipr-intro','1')")
                page.goto(f'http://127.0.0.1:{server.server_port}/{args.render_prefix}-{phase}/index.html',wait_until='networkidle')
                page.evaluate('document.fonts.ready');page.emulate_media(media='print')
                facts=page.locator('.photo-credit').evaluate('''el=>{
                  const a=el.querySelector('a'),s=getComputedStyle(el),pseudo=getComputedStyle(a,'::after'),r=el.getBoundingClientRect();
                  const finder=document.querySelector('.home-finder'),fr=finder.getBoundingClientRect();
                  const hits=[.1,.5,.9].map(f=>({x:r.x+r.width*f,y:r.bottom-8,top:document.elementFromPoint(r.x+r.width*f,r.bottom-8)?.className}));
                  return {creditTop:r.top,creditBottom:r.bottom,creditHeight:r.height,finderTop:fr.top,overlapPixels:Math.max(0,r.bottom-fr.top),lowerLineHitTests:hits,creditWidth:r.width,creditRight:r.right,clientWidth:el.clientWidth,scrollWidth:el.scrollWidth,
                    pageWidth:innerWidth,pageScrollWidth:document.documentElement.scrollWidth,
                    overflowWrap:s.overflowWrap,whiteSpace:s.whiteSpace,
                    pseudoContent:pseudo.content,pseudoOverflowWrap:pseudo.overflowWrap,pseudoWhiteSpace:pseudo.whiteSpace,
                    pseudoDisplay:pseudo.display,anchorDisplay:getComputedStyle(a).display,
                    href:a.getAttribute('href'),text:el.textContent.trim()};
                }''')
                facts['credit_overflow']=facts['scrollWidth']>facts['clientWidth']
                results.append(dict(phase=phase,width=width,**facts));page.close()
        browser.close()
    server.shutdown()
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(results,indent=2))
    for item in results:print(item['phase'],item['width'],'credit',item['clientWidth'],item['scrollWidth'],'pseudo',item['pseudoOverflowWrap'],item['pseudoWhiteSpace'])


if __name__=='__main__':main()
