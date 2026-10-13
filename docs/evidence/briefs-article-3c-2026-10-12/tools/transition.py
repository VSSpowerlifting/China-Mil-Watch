"""Viewport shot at the hero/reading transition. usage: transition.py <root> <outdir> <widths> <route>..."""
import sys, asyncio
from pathlib import Path
from playwright.async_api import async_playwright
root, out, widths, routes = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), [int(w) for w in sys.argv[3].split(",")], sys.argv[4:]
out.mkdir(parents=True, exist_ok=True)
async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w in widths:
            pg = await b.new_page(viewport={"width": w, "height": 800})
            for r in routes:
                await pg.goto((root / r).as_uri()); await pg.wait_for_timeout(200)
                await pg.evaluate("window.scrollTo(0, document.querySelector('.brief-hero').getBoundingClientRect().bottom + scrollY - 300)")
                await pg.wait_for_timeout(100)
                n = r.replace('/', '_').replace('.html', '')
                await pg.screenshot(path=str(out / f"{n}-{w}-transition.png"))
                sw = await pg.evaluate("document.documentElement.scrollWidth"); print(r, w, "scrollWidth", sw)
            await pg.close()
        await b.close()
asyncio.run(run())
