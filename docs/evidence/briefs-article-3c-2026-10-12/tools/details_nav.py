"""Fragment + TOC navigation into collapsed <details> (chromium, firefox, webkit). usage: details_nav.py <native_brief.html>"""
import sys, asyncio
from pathlib import Path
from playwright.async_api import async_playwright
page_path = Path(sys.argv[1]).resolve()
async def run():
    async with async_playwright() as p:
        for name in ("chromium", "firefox", "webkit"):
            b = await getattr(p, name).launch()
            pg = await b.new_page(viewport={"width": 1280, "height": 900})
            res = []
            for frag in ("s-compare", "s-coverage"):
                await pg.goto(page_path.as_uri())
                await pg.goto(page_path.as_uri() + "#" + frag)
                await pg.wait_for_timeout(300)
                direct = await pg.evaluate(f"document.getElementById('{frag}').closest('details').open")
                await pg.goto(page_path.as_uri())
                await pg.click(f".brief-toc a[href='#{frag}']")
                await pg.wait_for_timeout(300)
                click = await pg.evaluate(f"document.getElementById('{frag}').closest('details').open")
                vis = await pg.evaluate(f"(()=>{{const r=document.getElementById('h-{frag[2:]}').getBoundingClientRect();return r.height>0 && r.top>=0 && r.top<innerHeight}})()")
                res.append((frag, "url-load open=%s" % direct, "toc-click open=%s" % click, "heading in view=%s" % vis))
            print(name, res)
            await b.close()
asyncio.run(run())
