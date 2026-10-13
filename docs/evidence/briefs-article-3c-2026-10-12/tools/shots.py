"""Capture article routes. usage: shots.py <root> <outdir> <widths,csv> <route> [<route>...]
env: FULL=1 full page (default), VIEW=1 viewport only, MOTION=reduce, FORCED=active, JS=0"""
import os, sys, asyncio
from pathlib import Path
from playwright.async_api import async_playwright
root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]); widths = [int(w) for w in sys.argv[3].split(",")]
routes = sys.argv[4:]; out.mkdir(parents=True, exist_ok=True)
async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w in widths:
            ctx = await b.new_context(viewport={"width": w, "height": 900}, device_scale_factor=1,
                                      reduced_motion=os.environ.get("MOTION", "no-preference"),
                                      forced_colors=os.environ.get("FORCED", "none"),
                                      java_script_enabled=os.environ.get("JS", "1") == "1")
            pg = await ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("requestfailed", lambda r: errs.append("FAILED " + r.url))
            for r in routes:
                await pg.goto((root / r).as_uri()); await pg.wait_for_timeout(250)
                sw = await pg.evaluate("document.documentElement.scrollWidth")
                name = r.replace("/", "_").replace(".html", "")
                await pg.screenshot(path=str(out / f"{name}-{w}.png"), full_page=os.environ.get("VIEW") != "1")
                print(f"{r} @{w}: scrollWidth={sw}{' OVERFLOW' if sw > w else ''}")
            if errs: print("  errors:", errs[:8])
            await ctx.close()
        await b.close()
asyncio.run(run())
