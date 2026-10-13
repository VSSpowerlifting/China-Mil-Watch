"""Author block list styling on native No. 15. usage: authorcheck.py <site_root>..."""
import sys, asyncio
from pathlib import Path
from playwright.async_api import async_playwright
async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for root in sys.argv[1:]:
            pg = await b.new_page(viewport={"width":1280,"height":900})
            await pg.goto((Path(root).resolve()/"briefs/maritime-cooperation-2026.html").as_uri())
            r = await pg.evaluate("""() => { const a=[...document.querySelectorAll('a')].find(x=>x.textContent.trim()==='LinkedIn');
              const ul=a&&a.closest('ul'); return ul?{cls:ul.className, ls:getComputedStyle(ul).listStyleType, parent:ul.parentElement.className}:null }""")
            print(root.split('/')[-1], r)
        await b.close()
asyncio.run(run())
