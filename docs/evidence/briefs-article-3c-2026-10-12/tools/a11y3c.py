"""Phase 3C a11y checks. usage: a11y3c.py <root> <outdir> <route>...
keyboard: Tab until each issue-nav link has focus; record outline/visibility.
forced: clip nav + figure under forced-colors.
zoom: 1280 at 200% == 640 CSS px viewport, deviceScaleFactor 2; overflow check.
print: emulate print; nav hidden, figure + caption still present.
"""
import sys, asyncio
from pathlib import Path
from playwright.async_api import async_playwright

root, out, routes = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)


async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for route in routes:
            n = route.replace("/", "_").replace(".html", "")
            url = (root / route).as_uri()
            # keyboard
            pg = await b.new_page(viewport={"width": 1280, "height": 900})
            await pg.goto(url)
            want = await pg.locator(".brief-issue-nav a").count()
            seen = []
            for _ in range(400):
                await pg.keyboard.press("Tab")
                info = await pg.evaluate("""() => { const a = document.activeElement;
                  if (!a || !a.closest('.brief-issue-nav')) return null;
                  const s = getComputedStyle(a); const r = a.getBoundingClientRect();
                  return {cls: a.className, ow: s.outlineWidth, os: s.outlineStyle,
                          inView: r.top >= 0 && r.bottom <= innerHeight}; }""")
                if info and info["cls"] not in [s["cls"] for s in seen]:
                    seen.append(info)
                    await pg.screenshot(path=str(out / f"{n}-focus-{len(seen)}.png"))
                if len(seen) == want:
                    break
            print(route, "keyboard", f"{len(seen)}/{want}",
                  [(s["cls"].split("-")[-1], s["os"], s["ow"], s["inView"]) for s in seen])
            await pg.close()
            # forced colors
            pg = await b.new_page(viewport={"width": 1280, "height": 900})
            await pg.emulate_media(forced_colors="active")
            await pg.goto(url); await pg.wait_for_timeout(200)
            for i, sel in enumerate(["figure[data-article-media]", ".brief-issue-nav"]):
                el = pg.locator(sel).first
                if await el.count():
                    await el.screenshot(path=str(out / f"{n}-forced-{i}.png"))
            await pg.close()
            # 200% zoom
            ctx = await b.new_context(viewport={"width": 640, "height": 450}, device_scale_factor=2)
            pg = await ctx.new_page(); await pg.goto(url); await pg.wait_for_timeout(200)
            sw = await pg.evaluate("document.documentElement.scrollWidth")
            nav = pg.locator(".brief-issue-nav").first
            if await nav.count():
                await nav.screenshot(path=str(out / f"{n}-zoom200-nav.png"))
            print(route, "zoom200", "scrollWidth", sw, "OVERFLOW" if sw > 640 else "ok")
            await ctx.close()
            # print
            pg = await b.new_page(viewport={"width": 1280, "height": 900})
            await pg.emulate_media(media="print")
            await pg.goto(url)
            res = await pg.evaluate("""() => {
              const nav = document.querySelector('.brief-issue-nav');
              const fig = document.querySelector('figure[data-article-media] figcaption');
              return {nav: nav ? getComputedStyle(nav).display : 'absent',
                      caption: fig ? getComputedStyle(fig).display : 'absent'}; }""")
            await pg.pdf(path=str(out / f"{n}.pdf"))
            print(route, "print", res)
            await pg.close()
        await b.close()

asyncio.run(run())
