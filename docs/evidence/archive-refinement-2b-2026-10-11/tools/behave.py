import sys, json
from playwright.sync_api import sync_playwright
port=int(sys.argv[1]); BASE='http://127.0.0.1:%d/archive.html'%port
PROBE="""()=>{const rows=[...document.querySelectorAll('#results .record-row')];
 const marked=rows.filter(r=>{const a=r.querySelector('.row-side a'); if(!a) return false;
   const cs=getComputedStyle(a,'::before'); return cs.maskImage!=='none' && parseFloat(cs.width)>0 && cs.content!=='none';});
 const noLink=rows.filter(r=>!r.querySelector('.row-side a')).length;
 return {rows:rows.length, marked:marked.length, noDeskLink:noLink, text:document.querySelector('#results').innerText.length,
   first:(rows[0]||{}).innerText||''}}"""
res={}
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={'width':1280,'height':900}); pg=ctx.new_page()
    errs=[]; pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
    bad=[]; pg.on('response',lambda r: bad.append('%s %s'%(r.status,r.url)) if r.status>=400 else None)
    marks=[]; pg.on('response',lambda r: marks.append(r.url.split('/')[-1]+' '+str(r.status)) if 'desk-marks' in r.url else None)
    pg.goto(BASE); pg.wait_for_selector('#controls:not([hidden])'); pg.wait_for_timeout(400)
    res['initial']=pg.evaluate(PROBE)
    pg.fill('#f-q','国防'); pg.press('#f-q','Enter'); pg.wait_for_timeout(500); res['search']=pg.evaluate(PROBE)
    pg.fill('#f-q',''); pg.press('#f-q','Enter'); pg.wait_for_timeout(400)
    pg.click('.finder-more > summary'); pg.wait_for_timeout(200)
    opts=pg.eval_on_selector_all('#f-desk option','os=>os.map(o=>[o.value,o.textContent.trim()])'); res['desk_options']=opts
    sg=[o for o in opts if 'singapore' in (o[0]+o[1]).lower()]
    if sg:
        pg.select_option('#f-desk',sg[0][0]); pg.wait_for_timeout(500); res['filter_singapore']=pg.evaluate(PROBE)
        pg.select_option('#f-desk',''); pg.wait_for_timeout(400)
    pg.select_option('#f-sort', index=1); pg.wait_for_timeout(500); res['sort']=pg.evaluate(PROBE)
    pg.click('#page-next'); pg.wait_for_timeout(500); res['page2']=pg.evaluate(PROBE)
    pg.go_back(); pg.wait_for_timeout(500); res['back']=pg.evaluate(PROBE)
    pg.go_forward(); pg.wait_for_timeout(500); res['forward']=pg.evaluate(PROBE)
    res['errors']=errs; res['bad']=bad; res['mask_fetches']=sorted(set(marks))
    b.close()
print(json.dumps({k:(v if k!='initial' else {kk:vv for kk,vv in v.items()}) for k,v in res.items()},ensure_ascii=False,indent=1)[:4500])
