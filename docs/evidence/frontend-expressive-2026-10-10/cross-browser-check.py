from playwright.sync_api import sync_playwright
from pathlib import Path
import json
routes=['index.html','archive.html','analysis.html','desks.html','china.html','record/3924.html','briefs/maritime-cooperation-2026.html','methodology.html','source/pla_daily.html','the-pla-watch/posts/2026-08-08.html','the-pla-watch/terms.html']
checks=[];errors=[]
with sync_playwright() as p:
 for engine in ('firefox','webkit'):
  try:b=getattr(p,engine).launch()
  except Exception as e:errors.append({'engine':engine,'error':str(e)});continue
  c=b.new_context(viewport={'width':1440,'height':1000});page=c.new_page()
  for width in (1440,768,375,320):
   page.set_viewport_size({'width':width,'height':900})
   for route in routes:
    response=page.goto('http://127.0.0.1:8787/'+route);page.evaluate('document.fonts.ready')
    checks.append({'name':engine+' '+str(width)+' '+route,'passed':response.status==200 and not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')})
  page.set_viewport_size({'width':375,'height':900});page.goto('http://127.0.0.1:8787/desks.html')
  page.locator('[data-select-desk="japan"]').click()
  checks.append({'name':engine+' selected state','passed':page.locator('.deskmap-plate[data-desk="japan"].is-selected').is_visible() and page.locator('[data-select-desk="japan"]').get_attribute('aria-pressed')=='true'})
  page.locator('[data-select-desk="china"]').focus();page.keyboard.press('ArrowRight');page.keyboard.press('Space')
  checks.append({'name':engine+' native keyboard selection','passed':page.locator('[data-select-desk="singapore"]').get_attribute('aria-pressed')=='true'})
  page.keyboard.press('Escape')
  checks.append({'name':engine+' Escape reset','passed':not page.locator('.deskmap .is-selected').count()})
  hit=page.locator('.dm-hit').first.bounding_box()
  checks.append({'name':engine+' mobile marker target','passed':hit['width']>=44,'detail':hit})
  page.goto('http://127.0.0.1:8787/methodology.html')
  page.emulate_media(reduced_motion='reduce')
  checks.append({'name':engine+' reduced motion static','passed':page.locator('.page-head').evaluate('e=>getComputedStyle(e,"::after").animationName')=='none'})
  b.close()
r={'checks':len(checks),'failures':[c for c in checks if not c['passed']],'engine_errors':errors,'results':checks,'limitations':['Playwright Firefox/WebKit; real Safari app, iOS hardware and assistive technology not exercised']}
Path('/private/tmp/ipr-expressive-cross-browser.json').write_text(json.dumps(r,indent=2)+'\n')
print({k:v for k,v in r.items() if k!='results'})
