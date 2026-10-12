import sys, json
from playwright.sync_api import sync_playwright
S=sys.argv[1]; which=sys.argv[2]; port={'before':8792,'after':8793}[which]
out={}
with sync_playwright() as p:
    b=p.chromium.launch()
    for w in (320,375,768,1280):
        pg=b.new_page(viewport={'width':w,'height':900})
        errs=[]; pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
        fails=[]; pg.on('requestfailed',lambda r: fails.append(r.url)); pg.on('response',lambda r: fails.append('%s %s'%(r.status,r.url)) if r.status>=400 else None)
        pg.goto('http://127.0.0.1:%d/archive.html'%port); pg.wait_for_selector('#controls:not([hidden])'); pg.wait_for_timeout(500)
        pg.screenshot(path='%s/shots/%s-top-%d.png'%(S,which,w))
        pg.locator('#results').first.scroll_into_view_if_needed()
        el=pg.locator('#results .record-row').first
        el.scroll_into_view_if_needed(); pg.wait_for_timeout(200)
        pg.screenshot(path='%s/shots/%s-rows-%d.png'%(S,which,w))
        out[w]={'overflow':pg.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth'),'errors':errs,'failed':fails}
        pg.close()
    b.close()
print(json.dumps(out,indent=1))
