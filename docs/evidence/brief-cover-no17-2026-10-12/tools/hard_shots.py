"""No. 17 cover QA: screenshots and checks for one rendered site.

usage: hard_shots.py <site-dir-name> <out-dir> [<before-site-dir-name>]
Serves from http://127.0.0.1:8791/ (the scratchpad root).
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

SITE, OUT = sys.argv[1], Path(sys.argv[2])
BEFORE = sys.argv[3] if len(sys.argv) > 3 else None
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8791/"
ART = "briefs/trident-resolve-regional-scale-specific-chinese-tasks.html"
CARD = '.brief-card:has(a[href*="trident-resolve"])'
report = {}


def card_height(pg, site):
    pg.goto(BASE + site + "/analysis.html"); pg.wait_for_timeout(400)
    return pg.locator(CARD).first.evaluate("e => Math.round(e.getBoundingClientRect().height)")


with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (1280, 375):
        r = {}
        pg = b.new_page(viewport={"width": w, "height": 900}, reduced_motion="reduce")
        errs = []
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        if BEFORE:
            r["card_height_before"] = card_height(pg, BEFORE)
        r["card_height"] = card_height(pg, SITE)
        card = pg.locator(CARD).first
        card.scroll_into_view_if_needed(); pg.wait_for_timeout(200)
        card.screenshot(path=str(OUT / f"B-card-{w}.png"))
        lead = pg.locator(".briefs-lead-photo").first
        if lead.count():
            lead.scroll_into_view_if_needed(); lead.screenshot(path=str(OUT / f"B-lead-{w}.png"))
        r["analysis"] = pg.evaluate("""() => ({
          scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
          broken: [...document.images].filter(x => x.complete && !x.naturalWidth).length,
          cardImg: (document.querySelector('%s img')||{}).currentSrc?.split('/').pop(),
          notice: [...document.querySelectorAll('%s .brief-credit p')].some(p => /does not imply or constitute DoW endorsement/.test(p.textContent)
                   && getComputedStyle(p).display !== 'none' && getComputedStyle(p).visibility !== 'hidden'),
          creditFont: getComputedStyle(document.querySelector('%s .brief-credit')).fontSize})""" % (CARD, CARD, CARD))
        # Keyboard: tab through the No. 17 card's links; each must be visible on focus.
        links = card.locator("a")
        focus = []
        for i in range(links.count()):
            a = links.nth(i)
            a.focus()
            focus.append(a.evaluate("""a => { const s = getComputedStyle(a);
              return {text: a.textContent.trim().slice(0, 40), focused: document.activeElement === a,
                      outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 || s.boxShadow !== 'none' || s.textDecorationLine.includes('underline')}; }"""))
        r["card_focus"] = focus
        pg.goto(BASE + SITE + "/" + ART); pg.wait_for_timeout(500)
        pg.locator(".brief-hero").screenshot(path=str(OUT / f"B-article-{w}.png"))
        r["article"] = pg.evaluate("""() => { const i = document.querySelector('.brief-cover img');
          const f = document.querySelector('.brief-cover-frame');
          const before = f && getComputedStyle(f, '::before').backgroundImage;
          const after = f && getComputedStyle(f, '::after').backgroundImage;
          return {current: i && i.currentSrc.split('/').pop(), loaded: i && i.naturalWidth,
                  gradient_css: [before, after].some(x => x && x.includes('gradient')),
                  scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
                  broken: [...document.images].filter(x => x.complete && !x.naturalWidth).length}; }""")
        r["console_errors"] = errs
        pg.close()
        # Forced colours and print.
        pg = b.new_page(viewport={"width": w, "height": 900}, forced_colors="active", reduced_motion="reduce")
        pg.goto(BASE + SITE + "/analysis.html"); pg.wait_for_timeout(400)
        c = pg.locator(CARD).first; c.scroll_into_view_if_needed()
        c.screenshot(path=str(OUT / f"B-card-forced-{w}.png"))
        pg.goto(BASE + SITE + "/" + ART); pg.wait_for_timeout(400)
        pg.locator(".brief-hero").screenshot(path=str(OUT / f"B-article-forced-{w}.png"))
        r["forced_gradient_display"] = pg.evaluate("getComputedStyle(document.querySelector('.brief-cover-frame'), '::after').display")
        pg.close()
        if w == 1280:
            pg = b.new_page(viewport={"width": w, "height": 900})
            pg.emulate_media(media="print")
            pg.goto(BASE + SITE + "/" + ART); pg.wait_for_timeout(400)
            r["print_article"] = pg.evaluate("""() => { const f = document.querySelector('.brief-cover');
              const cr = document.querySelector('.brief-cover-credit');
              return {figure_shown: !!f && getComputedStyle(f).display !== 'none',
                      credit_shown: !!cr && getComputedStyle(cr).display !== 'none',
                      notice: !!cr && /DoW endorsement/.test(cr.textContent),
                      gradient_display: getComputedStyle(document.querySelector('.brief-cover-frame'), '::after').display}; }""")
            pg.goto(BASE + SITE + "/analysis.html"); pg.wait_for_timeout(400)
            r["print_card"] = pg.locator(CARD).first.evaluate("""e => {
              const cr = e.querySelector('.brief-credit');
              return {credit_shown: !!cr && getComputedStyle(cr).display !== 'none',
                      notice: !!cr && /DoW endorsement/.test(cr.textContent)}; }""")
            pg.close()
        report[w] = r
    b.close()
print(json.dumps(report, indent=1))
