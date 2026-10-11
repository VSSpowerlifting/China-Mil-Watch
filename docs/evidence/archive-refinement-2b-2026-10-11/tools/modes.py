import sys, json
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:8793/archive.html'
R={}
M="""()=>{const a=document.querySelector('#results .record-row .row-side a');const cs=getComputedStyle(a,'::before');
 const f=document.querySelector('#controls')||document.querySelector('.finder');const fs=getComputedStyle(f);
 return {markDisplay:cs.display,mask:cs.maskImage,w:cs.width,content:cs.content,finderShadow:fs.boxShadow,finderHidden:f.hidden,finderDisplay:fs.display}}"""
with sync_playwright() as p:
    b=p.chromium.launch()
    # no JS
    c=b.new_context(java_script_enabled=False,viewport={'width':1280,'height':900}); pg=c.new_page(); pg.goto(BASE); pg.wait_for_timeout(300)
    R['nojs']=pg.evaluate_handle if False else None
    c.close()
    c=b.new_context(java_script_enabled=True,viewport={'width':1280,'height':900}); pg=c.new_page()
    pg.route('**/browse.js',lambda r:r.abort()); pg.goto(BASE); pg.wait_for_timeout(500)   # JS present but browse.js blocked == honest no-JS fallback
    R['no-browse-js']=pg.evaluate(M)
    R['no-browse-js']['rows']=pg.locator('#results .record-row').count()
    R['no-browse-js']['finder_visible']=pg.locator('#controls').is_visible()
    pg.screenshot(path=sys.argv[1]+'/shots/after-nojs-1280.png',full_page=False)
    c.close()
    for name,kw in (('reduced-motion',dict(reduced_motion='reduce')),('forced-colors',dict(forced_colors='active'))):
        c=b.new_context(viewport={'width':1280,'height':900},**kw); pg=c.new_page(); pg.goto(BASE); pg.wait_for_selector('#controls:not([hidden])'); pg.wait_for_timeout(300)
        R[name]=pg.evaluate(M); pg.screenshot(path=sys.argv[1]+'/shots/after-%s-1280.png'%name)
        if name=='forced-colors': pg.locator('#results').scroll_into_view_if_needed(); pg.screenshot(path=sys.argv[1]+'/shots/after-forced-colors-rows-1280.png')
        c.close()
    c=b.new_context(viewport={'width':1280,'height':900}); pg=c.new_page(); pg.goto(BASE); pg.wait_for_selector('#controls:not([hidden])')
    pg.emulate_media(media='print'); R['print']=pg.evaluate(M)
    pg.emulate_media(media='screen')
    # keyboard focus: tab to the search field, check the outline and that the lifted finder keeps it
    pg.keyboard.press('Tab')
    for i in range(12):
        pg.keyboard.press('Tab')
        if pg.evaluate("document.activeElement&&document.activeElement.id")=='f-q': break
    R['focus']=pg.evaluate("(()=>{const e=document.activeElement;const s=getComputedStyle(e);return {id:e.id,outline:s.outlineStyle+' '+s.outlineWidth,borderColor:s.borderColor}})()")
    c.close()
    # 200% zoom == 640 CSS px wide at 1280 device px; plus synthetic japan/vietnam rows
    c=b.new_context(viewport={'width':640,'height':450},device_scale_factor=2); pg=c.new_page(); pg.goto(BASE); pg.wait_for_selector('#controls:not([hidden])')
    R['zoom200']={'overflow':pg.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth')}
    pg.evaluate("""()=>{const ul=document.querySelector('#results .record-row').parentNode;
      for(const s of ['japan','vietnam','singapore','china','philippines']){const li=document.createElement('li');li.className='record-row';li.innerHTML='<div><h3><a href="#">'+s+'</a></h3></div><p class="row-side"><span class="row-who">Synthetic</span><a href="'+s+'.html">'+s+' Desk</a></p>';ul.prepend(li);}}""")
    R['synthetic']=pg.evaluate("""()=>[...document.querySelectorAll('#results .record-row .row-side a')].slice(0,5).map(a=>[a.getAttribute('href'),getComputedStyle(a,'::before').maskImage.slice(0,60),getComputedStyle(a,'::before').width])""")
    pg.wait_for_timeout(300); pg.locator('#results .record-row').first.scroll_into_view_if_needed()
    pg.screenshot(path=sys.argv[1]+'/shots/after-synthetic-640.png')
    c.close(); b.close()
print(json.dumps(R,indent=1,ensure_ascii=False))
