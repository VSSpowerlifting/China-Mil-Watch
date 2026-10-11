import sys, json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width':420,'height':120})
    pg.goto('http://127.0.0.1:8792/archive.html')
    pg.evaluate("""()=>{document.body.innerHTML='';
      const mk=(label,m)=>{const d=document.createElement('div');d.dataset.l=label;
        d.style.cssText='display:inline-block;width:80px;height:80px;margin:6px;background:#06c;'+(m?'-webkit-mask:url('+m+') center/contain no-repeat;mask:url('+m+') center/contain no-repeat':'');
        document.body.appendChild(d)};
      mk('no-mask (control)','');
      mk('symbol fragment','assets/geo/emblems.svg#china');
      mk('standalone file','assets/desk-marks/china.svg');
    }""")
    pg.wait_for_timeout(600)
    # sample the centre pixel colour of each box via screenshot clip
    pg.screenshot(path=sys.argv[1])
    b.close()
