"""Measure migrated text roles against actual inherited/composited backgrounds."""
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright
from capture import ROUTES, EVIDENCE
sys.path.insert(0, str(EVIDENCE.parents[2]))
from tests.test_palette_and_accessibility import contrast


def main():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory='/tmp'))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    results=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for width in (375,1280):
            page=browser.new_page(viewport={'width':width,'height':900}, reduced_motion='reduce')
            page.add_init_script("sessionStorage.setItem('ipr-intro','1')")
            for route,(suffix,path) in ROUTES.items():
                page.goto(f'http://127.0.0.1:{server.server_port}/ipr-coastal-after{suffix}/{path}',wait_until='networkidle')
                page.evaluate('document.fonts.ready')
                pairs=page.evaluate('''() => {
                  let rgb=s=>s.match(/[0-9.]+/g).map(Number);
                  let hex=a=>'#'+a.slice(0,3).map(n=>Math.round(n).toString(16).padStart(2,'0')).join('');
                  let migrated=['#23665b','#446c79','#92d5cc','#aacfd0'];
                  return [...document.querySelectorAll('*')].flatMap(el=>{
                    let s=getComputedStyle(el),r=el.getBoundingClientRect(), fg=hex(rgb(s.color));
                    if(!migrated.includes(fg)||!r.width||!r.height||s.visibility==='hidden'||
                       ![...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())) return [];
                    let ancestors=[], node=el, bg=[255,255,255];
                    while(node){ancestors.unshift(getComputedStyle(node).backgroundColor);node=node.parentElement}
                    for(let color of ancestors){let c=rgb(color), alpha=c[3]??1;bg=bg.map((n,i)=>c[i]*alpha+n*(1-alpha))}
                    return [{selector:el.tagName.toLowerCase()+'.'+el.className,fg,bg:hex(bg),
                             fontSize:parseFloat(s.fontSize),fontWeight:parseFloat(s.fontWeight)}];
                  });
                }''')
                for pair in pairs:
                    pair['ratio']=contrast(pair['fg'],pair['bg'])
                    pair['required']=3 if pair['fontSize']>=24 or (pair['fontSize']>=18.66 and pair['fontWeight']>=700) else 4.5
                    results.append(dict(route=route,width=width,**pair))
            page.close()
        browser.close()
    server.shutdown()
    (EVIDENCE/'rendered-contrast.json').write_text(json.dumps(results,indent=2))
    failures=[r for r in results if r['ratio']<r['required']]
    print(f'{len(results)} migrated rendered text consumers measured; {len(failures)} contrast failures')
    if failures: print(json.dumps(failures,indent=2))
    assert not failures


if __name__=='__main__': main()
