from playwright.sync_api import sync_playwright
from pathlib import Path
import json
checks=[]
with sync_playwright() as p:
 b=p.chromium.launch();c=b.new_context(viewport={'width':1440,'height':1000},permissions=['clipboard-read','clipboard-write']);page=c.new_page()
 page.goto('http://127.0.0.1:8787/desks.html')
 page.locator('.dm-country[data-desk="china"] use').click()
 checks.append({'name':'actual country pointer click','passed':page.locator('[data-select-desk="china"]').get_attribute('aria-pressed')=='true'})
 page.locator('.dm-anchor[data-desk="japan"] .dm-dot').click()
 checks.append({'name':'actual seat pointer click','passed':page.locator('[data-select-desk="japan"]').get_attribute('aria-pressed')=='true'})
 page.goto('http://127.0.0.1:8787/record/3924.html#record-citation')
 page.locator('[data-copy="cite-as-held"]').click();page.wait_for_timeout(100)
 expected=page.locator('#cite-as-held').text_content().strip();actual=page.evaluate('navigator.clipboard.readText()')
 checks.append({'name':'citation copy preserves exact rendered text','passed':actual==expected})
 page.goto('http://127.0.0.1:8787/methodology.html');page.evaluate('document.documentElement.classList.add("no-anim")')
 checks.append({'name':'no-anim contour static','passed':page.locator('.page-head').evaluate('e=>getComputedStyle(e,"::after").animationName')=='none'})
 b.close()
Path('/private/tmp/ipr-expressive-extra-interactions.json').write_text(json.dumps(checks,indent=2)+'\n')
print(checks)
assert all(x['passed'] for x in checks)
