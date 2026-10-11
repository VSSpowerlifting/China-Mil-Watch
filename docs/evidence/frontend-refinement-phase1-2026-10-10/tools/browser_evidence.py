"""Phase 1 gallery browser evidence: screenshots + behavioural checks on the Relief section."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
results, shots = [], []


def check(name, ok, detail=None):
    results.append(dict(name=name, passed=bool(ok), detail=detail))


SECTION = """() => {const a=document.querySelector('#g-relief').getBoundingClientRect().top+scrollY;
  const b=document.querySelector('.g-rl-glyphs').getBoundingClientRect().bottom+scrollY; return [a,b]}"""


def watch(pg, errs):
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.on("requestfailed", lambda r: errs.append("FAIL " + r.url))
    pg.on("response", lambda r: r.status >= 400 and errs.append("%d %s" % (r.status, r.url)))


def section_shot(pg, name, w):
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.wait_for_timeout(250)
    a, b = pg.evaluate(SECTION)
    path = OUT / ("%s.png" % name)
    pg.screenshot(path=str(path), full_page=True,
                  clip={"x": 0, "y": a - 20, "width": w, "height": b - a + 40})
    shots.append(path.name)


def el_shot(pg, selector, name, pad=14):
    box = pg.locator(selector).first.evaluate(
        "e=>{const r=e.getBoundingClientRect();return [r.left,r.top+scrollY,r.width,r.height]}")
    path = OUT / ("%s.png" % name)
    pg.screenshot(path=str(path), full_page=True,
                  clip={"x": max(box[0] - pad, 0), "y": box[1] - pad, "width": box[2] + 2 * pad, "height": box[3] + 2 * pad})
    shots.append(path.name)


with sync_playwright() as p:
    browser = p.chromium.launch()

    # 1. Finished state at three widths (reduced motion: nothing mid-animation).
    for w in (375, 768, 1280):
        ctx = browser.new_context(viewport=dict(width=w, height=900), reduced_motion="reduce")
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        pg.goto(URL, wait_until="networkidle")
        section_shot(pg, "relief-%d" % w, w)
        check("%dpx: no horizontal overflow" % w, not pg.evaluate("document.documentElement.scrollWidth>innerWidth+1"),
              pg.evaluate("[document.documentElement.scrollWidth, innerWidth]"))
        check("%dpx: no console errors or failed requests" % w, not errs, errs)
        ctx.close()

    # 2. Normal motion: motion assigned, hover lifts, press sinks.
    ctx = browser.new_context(viewport=dict(width=1280, height=900))
    pg = ctx.new_page(); errs = []; watch(pg, errs)
    pg.goto(URL, wait_until="networkidle")
    check("scroll-driven draw assigned on emblems", pg.locator(".rl-emblem.rl-draws").first.evaluate(
        "e=>getComputedStyle(e).animationName") == "rl-draw")
    check("analysis copy settles", pg.locator(".rl-settles").first.evaluate("e=>getComputedStyle(e).animationName") == "rl-settle")
    card = pg.locator(".g-rl-card").first
    card.scroll_into_view_if_needed(); card.hover(); pg.wait_for_timeout(400)
    t = card.evaluate("e=>getComputedStyle(e).transform")
    lift = card.evaluate("e=>getComputedStyle(e,'::after').opacity")
    check("hover: card rises and gains lift 2", t != "none" and lift == "1", dict(transform=t, after_opacity=lift))
    el_shot(pg, ".g-rl-card", "card-hover-1280")
    brief = pg.locator(".g-rl-brief")
    brief.scroll_into_view_if_needed(); brief.hover(); pg.wait_for_timeout(400)
    check("hover: brief print plate scales", pg.locator(".rl-print>svg").evaluate("e=>getComputedStyle(e).transform") != "none")
    el_shot(pg, ".g-rl-brief", "brief-hover-1280")
    btn = pg.locator(".g-rl-finder .btn--primary")
    btn.scroll_into_view_if_needed(); btn.hover(); pg.wait_for_timeout(250)
    rest = btn.evaluate("e=>getComputedStyle(e).backgroundColor")
    pg.mouse.down(); pg.wait_for_timeout(250)
    pressed = btn.evaluate("e=>[getComputedStyle(e).transform,getComputedStyle(e).backgroundColor,getComputedStyle(e).boxShadow]")
    sink = float(pressed[0].rstrip(")").split(",")[-1]) if pressed[0].startswith("matrix(") else 0
    # The production surfaces.css press (translateY(2px) on [data-surface]
    # buttons) outranks relief.css's 1px; the check asserts the shared intent.
    check("press: control sinks, darkens, no inset shadow",
          sink > 0 and pressed[1] != rest and pressed[2] == "none",
          dict(transform=pressed[0], sink_px=sink, rest_bg=rest, pressed_bg=pressed[1], box_shadow=pressed[2]))
    el_shot(pg, ".g-rl-finder", "finder-press-1280")
    pg.mouse.up()
    check("normal motion: no console errors", not errs, errs)
    ctx.close()

    # 3. Reduced motion: no transforms, no animation; lift still shows on hover.
    ctx = browser.new_context(viewport=dict(width=1280, height=900), reduced_motion="reduce")
    pg = ctx.new_page()
    pg.goto(URL, wait_until="networkidle")
    check("reduced motion: no scroll animation", pg.locator(".rl-draws").first.evaluate("e=>getComputedStyle(e).animationName") == "none")
    card = pg.locator(".g-rl-card").first
    card.scroll_into_view_if_needed(); card.hover(); pg.wait_for_timeout(300)
    check("reduced motion: hover lift without movement",
          card.evaluate("e=>getComputedStyle(e).transform") == "none" and card.evaluate("e=>getComputedStyle(e,'::after').opacity") == "1")
    ctx.close()

    # 4. Keyboard: focus ring on every tactile control and card link.
    ctx = browser.new_context(viewport=dict(width=1280, height=900), reduced_motion="reduce")
    pg = ctx.new_page()
    pg.goto(URL, wait_until="networkidle")
    pg.locator("#g-rl-q").focus()
    rings = []
    for i in range(9):
        info = pg.evaluate("""()=>{const e=document.activeElement;const s=getComputedStyle(e);
          return [e.tagName+(e.className?'.'+String(e.className).split(' ').join('.'):''),s.outlineStyle,s.outlineWidth,
                  e.closest('.rl-card,.rl-plate')?getComputedStyle(e.closest('.rl-card,.rl-plate'),'::after').opacity:null]}""")
        rings.append(info)
        if i == 2:
            el_shot(pg, ".g-rl-finder", "finder-focus-1280")
        if info[3] == "1" and not any(n.startswith("focus-card") for n in shots):
            pg.evaluate("document.activeElement.closest('.rl-card,.rl-plate').scrollIntoView({block:'center'})")
            el_shot(pg, ".rl-card:focus-within, .rl-plate:focus-within", "focus-card-1280")
        pg.keyboard.press("Tab")
    tactile = [r for r in rings if "tactile" in r[0]]
    check("keyboard: every tactile control shows a 2px outline", tactile and all(r[1] == "solid" and r[2] == "2px" for r in tactile), rings)
    check("keyboard: a focused card link raises its card's lift", any(r[3] == "1" for r in rings), rings)
    ctx.close()

    # 5. Forced colours: borders, no lifts, art hidden, text intact.
    for w in (375, 1280):
        ctx = browser.new_context(viewport=dict(width=w, height=900), forced_colors="active", reduced_motion="reduce")
        pg = ctx.new_page()
        pg.goto(URL, wait_until="networkidle")
        section_shot(pg, "relief-forced-colors-%d" % w, w)
        sh = pg.evaluate("[...document.querySelectorAll('.rl-finder,.rl-card,.rl-analysis,.rl-brief,.rl-plate,.rl-scope')].map(e=>getComputedStyle(e).boxShadow)")
        check("forced colours %dpx: no lift" % w, all(s == "none" for s in sh), sorted(set(sh)))
        check("forced colours %dpx: illustrations hidden, flags and text kept" % w,
              pg.locator(".rl-emblem").first.evaluate("e=>getComputedStyle(e).display") == "none"
              and pg.locator(".rl-flag").first.is_visible() and pg.locator("#g-rl-analysis-h").is_visible())
        ctx.close()

    # 6. No JavaScript: finished state, no motion, no overflow.
    for w in (375, 1280):
        ctx = browser.new_context(viewport=dict(width=w, height=900), java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(URL, wait_until="networkidle")
        section_shot(pg, "relief-no-js-%d" % w, w)
        check("no JS %dpx: no scroll animation" % w, pg.locator(".rl-draws").first.evaluate("e=>getComputedStyle(e).animationName") == "none")
        ctx.close()

    # 7. Accessibility and image audit of the section.
    ctx = browser.new_context(viewport=dict(width=1280, height=900))
    pg = ctx.new_page(); reqs = []
    pg.on("request", lambda r: reqs.append(r.url))
    pg.goto(URL, wait_until="networkidle")
    audit = pg.evaluate("""()=>{const s=document.querySelector('#g-relief');const end=document.querySelector('.g-rl-glyphs');
      const inside=e=>(s.compareDocumentPosition(e)&Node.DOCUMENT_POSITION_FOLLOWING)&&(end.compareDocumentPosition(e)&Node.DOCUMENT_POSITION_PRECEDING||end.contains(e));
      const svgs=[...document.querySelectorAll('svg.rl-emblem,svg.rl-strait,svg.rl-region,svg.rl-glyph')];
      const imgs=[...document.querySelectorAll('img')].filter(inside);
      const bgs=[...document.querySelectorAll('*')].filter(inside).map(e=>getComputedStyle(e).backgroundImage).filter(v=>v!=='none');
      const btns=[...document.querySelectorAll('.tactile')].map(e=>e.tagName==='INPUT'?(e.labels[0]||{}).textContent:e.textContent.trim());
      return {svgs:svgs.length,hidden:svgs.filter(e=>e.getAttribute('aria-hidden')==='true'&&e.getAttribute('focusable')==='false').length,
              imgs:imgs.map(i=>[i.getAttribute('src'),i.getAttribute('alt')]),bgs,controls:btns}}""")
    check("every relief SVG is aria-hidden and unfocusable", audit["svgs"] and audit["hidden"] == audit["svgs"], audit["svgs"])
    check("only flag images in the section, each alt=\"\"",
          all(src.startswith("assets/flags/") and alt == "" for src, alt in audit["imgs"]), audit["imgs"])
    check("no background photographs in the section", not audit["bgs"], audit["bgs"])
    check("every control has an accessible name", all((c or "").strip() for c in audit["controls"]), audit["controls"])
    check("no request to 81.cn from the gallery", not [u for u in reqs if "81.cn" in u])
    sizes = pg.evaluate("""()=>performance.getEntriesByType('resource').filter(r=>/relief\\.css|assets\\/(geo|flags|glyphs)\\//.test(r.name))
        .map(r=>[r.name.split('/').slice(-2).join('/'),r.encodedBodySize])""")
    ctx.close()
    browser.close()

receipt = dict(url=URL, checks=len(results), failures=[r for r in results if not r["passed"]],
               results=results, screenshots=shots, relief_resources=sizes,
               limitations=["Chromium only; Safari, Firefox and real assistive technology not exercised",
                            "Screenshots crop the Relief section; other gallery sections are out of Phase 1 scope"])
(OUT / "browser-checks.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({k: v for k, v in receipt.items() if k not in ("results",)}, indent=2))
