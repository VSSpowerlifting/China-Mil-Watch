"""Focused issue-nav link rect vs the viewport after Tab focus scroll. usage: focusgap.py <root> <route>..."""
import sys, asyncio
from pathlib import Path
from playwright.async_api import async_playwright
async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for route in sys.argv[2:]:
            pg = await b.new_page(viewport={"width": 1280, "height": 900})
            await pg.goto((Path(sys.argv[1]).resolve() / route).as_uri())
            for _ in range(400):
                await pg.keyboard.press("Tab")
                r = await pg.evaluate("""() => { const a = document.activeElement;
                  if (!a || !a.closest('.brief-issue-nav')) return null; const r = a.getBoundingClientRect();
                  return {cls: a.className, top: r.top, bottom: r.bottom, ih: innerHeight, sy: scrollY, max: document.documentElement.scrollHeight - innerHeight}; }""")
                if r: print(route, r); break
            await pg.close()
        await b.close()
asyncio.run(run())
