import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright
SP = Path(sys.argv[1]); OUT = SP / "cover-shots"
ART = "briefs/trident-resolve-regional-scale-specific-chinese-tasks.html"
report = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for v in "B":
        root = SP / ("cover-" + v)
        for w in (1280, 375):
            pg = b.new_page(viewport={"width": w, "height": 900}, reduced_motion="reduce")
            errs = []; pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
            pg.goto(f"http://127.0.0.1:8791/cover-{v}/analysis.html"); pg.wait_for_timeout(600)
            card = pg.locator('.brief-card:has(a[href*="trident-resolve"])').first
            card.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
            card.screenshot(path=str(OUT / f"{v}-card-{w}.png"))
            lead = pg.locator(".briefs-lead-photo").first
            if lead.count():
                lead.scroll_into_view_if_needed(); lead.screenshot(path=str(OUT / f"{v}-lead-{w}.png"))
            sw = pg.evaluate("document.documentElement.scrollWidth")
            pg.goto(f"http://127.0.0.1:8791/cover-{v}/{ART}"); pg.wait_for_timeout(600)
            hero = pg.locator(".brief-hero")
            hero.screenshot(path=str(OUT / f"{v}-article-{w}.png"))
            info = pg.evaluate("""() => { const i = document.querySelector('.brief-cover img');
              return {loaded: i && i.complete && i.naturalWidth, current: i && i.currentSrc.split('/').pop(),
                      scrollW: document.documentElement.scrollWidth,
                      broken: [...document.images].filter(x => x.complete && !x.naturalWidth).length}; }""")
            report[f"{v}-{w}"] = {**info, "analysis_scrollW": sw, "console_errors": errs}
            pg.close()
    b.close()
print(json.dumps(report, indent=1))
