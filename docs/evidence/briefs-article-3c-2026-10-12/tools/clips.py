"""Element clips. usage: clips.py <root> <outdir> <width> <route> <selector>[,<selector>...]"""
import sys, asyncio
from pathlib import Path
from playwright.async_api import async_playwright
root, out, w, route, sels = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5].split(",")
out.mkdir(parents=True, exist_ok=True)
async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": w, "height": 900})
        await pg.goto((root / route).as_uri()); await pg.wait_for_timeout(250)
        for i, s in enumerate(sels):
            el = pg.locator(s).first
            if not await el.count(): print("missing", s); continue
            n = route.replace("/", "_").replace(".html", "")
            await el.screenshot(path=str(out / f"{n}-{w}-{i}.png")); print("ok", s)
        await b.close()
asyncio.run(run())
