import sys, json
from playwright.sync_api import sync_playwright
out={}
with sync_playwright() as p:
    b=p.chromium.launch()
    # 1. real JavaScript-off, rows region, after build only
    c=b.new_context(java_script_enabled=False,viewport={'width':1280,'height':900}); pg=c.new_page()
    pg.goto('http://127.0.0.1:8793/archive.html'); pg.wait_for_timeout(500)
    pg.evaluate_handle  # (not callable with JS off; screenshot only)
    box=pg.locator('#results .record-row').first.bounding_box()
    pg.mouse.wheel(0,max(0,box['y']-120)); pg.wait_for_timeout(200)
    pg.screenshot(path=sys.argv[1]+'/after-nojs-real-1280.png')
    out['nojs_rows']=pg.locator('#results .record-row').count()
    out['nojs_finder_hidden_attr']=pg.locator('#controls').get_attribute('hidden') is not None
    out['nojs_finder_visible']=pg.locator('#controls').is_visible()
    c.close()
    # 2. index error: corpus-index.json aborted, before vs after
    for name,port in (('before',8792),('after',8793)):
        c=b.new_context(viewport={'width':1280,'height':900}); pg=c.new_page()
        errs=[]; pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
        pg.route('**/corpus-index.json*',lambda r:r.abort())
        pg.goto('http://127.0.0.1:%d/archive.html'%port); pg.fill('#f-q','navy'); pg.press('#f-q','Enter'); pg.wait_for_timeout(1500)
        out['index_error_'+name]=pg.evaluate("""()=>{const q=s=>document.querySelector(s);
          const vis=e=>e&&!e.hidden&&getComputedStyle(e).display!=='none';
          return {browseHidden:q('#browse').hidden, formHidden:q('#controls').hidden,
                  failText:[...document.querySelectorAll('#browse *, #results *, .index-state')].filter(e=>e.classList.contains('index-state--error')||e.classList.contains('index-state')).map(e=>[e.className,e.hidden,(e.innerText||'').trim()]),
                  rows:document.querySelectorAll('#results .record-row').length,
                  statusText:(q('.finder-status')||{}).innerText||''}}""")
        out['index_error_'+name]['console_errors']=len(errs)
        pg.screenshot(path=sys.argv[1]+'/%s-index-error-1280.png'%name)
        c.close()
    b.close()
print(json.dumps(out,indent=1,ensure_ascii=False))
