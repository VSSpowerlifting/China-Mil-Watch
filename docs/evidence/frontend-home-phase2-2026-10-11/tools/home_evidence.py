"""Phase 2 homepage evidence: per-section captures and behavioural checks.

usage: python -I home_evidence.py <base-url> <out-dir> <label>
<base-url> serves a scratch build (…/index.html). Writes <label>-*.png and
<label>-checks.json. Brief photographs credited to 81.cn / PLA Daily are
masked in every capture (rights: not republished in evidence).
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE, OUT, LABEL = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
URL = BASE + "/index.html"
SECTIONS = {"finder": ".home-finder", "records": ".home-register", "analysis": "#analysis",
            "photo-brief": ".home-brief", "desks": ".home-desks"}
MASK = ".home-brief-photo img"
results, shots = [], []


def check(name, ok, detail=None):
    results.append(dict(name=name, passed=bool(ok), detail=detail))


def page_for(b, w, h=900, **kw):
    ctx = b.new_context(viewport={"width": w, "height": h}, **kw)
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.on("requestfailed", lambda r: errs.append("FAIL " + r.url))
    pg.on("response", lambda r: r.status >= 400 and errs.append("%d %s" % (r.status, r.url)))
    reqs = []
    pg.on("request", lambda r: reqs.append(r.url))
    pg.goto(URL, wait_until="networkidle")
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.wait_for_timeout(300)
    pg.evaluate("window.scrollTo(0, 0)")
    pg.wait_for_timeout(150)
    return ctx, pg, errs, reqs


def shot(pg, name, selector=None, pad=24, w=None):
    masks = [pg.locator(MASK)]
    path = OUT / ("%s-%s.png" % (LABEL, name))
    if selector is None:
        pg.screenshot(path=str(path), full_page=True, mask=masks)
    else:
        loc = pg.locator(selector).first
        if not loc.count():
            return
        loc.scroll_into_view_if_needed()
        pg.wait_for_timeout(200)
        x, y, bw, bh = loc.evaluate(
            "e=>{const r=e.getBoundingClientRect();return [r.left,r.top+scrollY,r.width,r.height]}")
        if selector == ".home-finder":  # include the hero's lower edge the sheet overlaps
            y, bh = y - 180, bh + 180
        pg.screenshot(path=str(path), full_page=True, mask=masks,
                      clip={"x": 0, "y": max(0, y - pad), "width": w, "height": bh + 2 * pad})
    shots.append(path.name)


def state(pg):
    return pg.evaluate("""() => {
      const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)];
      const f=q('.home-search');
      return {
        recent: qa('.home-recent h3 a').map(a=>a.getAttribute('href')),
        selected: q('.home-selected h3 a')?.getAttribute('href'),
        selected_id: q('.home-selected h3')?.id,
        selected_original_lang: q('.home-selected-original')?.lang,
        form: f && {action:f.getAttribute('action'), method:f.getAttribute('method'),
                    inputs: qa('.home-search input').map(i=>[i.name,i.id,i.type])},
        search_caption: q('.home-search-caption p')?.textContent.trim(),
        analysis_branch: q('#analysis')?.innerText.includes('Follow the dates') ? 'timeline' : 'briefs',
        analysis_text: q('#analysis')?.innerText.replace(/\\s+/g,' ').trim(),
        desks: qa('.home-desk-list a').map(a=>[a.getAttribute('href'), a.innerText.replace(/\\s+/g,' ').trim()]),
        desk_note: q('.home-coverage-note')?.textContent.replace(/\\s+/g,' ').trim(),
        credits: qa('.photo-credit, .home-brief-photo p').map(p=>p.textContent.replace(/\\s+/g,' ').trim()),
        scripts: qa('script[src]').map(s=>s.getAttribute('src')),
        styles: qa('link[rel=stylesheet]').map(s=>s.getAttribute('href')),
      }}""")


with sync_playwright() as p:
    b = p.chromium.launch()
    data = {}
    for w in (320, 375, 768, 1280, 1440):
        ctx, pg, errs, reqs = page_for(b, w)
        overflow = pg.evaluate("document.documentElement.scrollWidth - innerWidth")
        check("no horizontal overflow @%d" % w, overflow <= 0, overflow)
        check("no console errors / failed requests @%d" % w, not errs, errs)
        check("no request to 81.cn @%d" % w, not [u for u in reqs if "81.cn" in u])
        if w == 1280:
            data = state(pg)
            data["requests"] = sorted({u.replace(BASE, "") for u in reqs if u.startswith(BASE)})
        if w in (375, 768, 1280):
            shot(pg, "full-%d" % w)
            for name, sel in SECTIONS.items():
                shot(pg, "%s-%d" % (name, w), sel, w=w)
        ctx.close()

    # Keyboard: tab to the search field and the button; focus must be visible.
    ctx, pg, errs, _ = page_for(b, 1280)
    pg.locator("#home-q").focus()
    pg.keyboard.press("Shift+Tab"); pg.keyboard.press("Tab")
    focus = pg.evaluate("""() => {const e=document.activeElement, s=getComputedStyle(e);
        return [e.id, s.outlineStyle, s.outlineWidth, s.boxShadow]}""")
    check("search input keyboard focus visible", focus[0] == "home-q" and (focus[1] != "none" or focus[3] != "none"), focus)
    shot(pg, "focus-input-1280", ".home-finder", w=1280)
    pg.keyboard.press("Tab")
    bfocus = pg.evaluate("""() => {const e=document.activeElement, s=getComputedStyle(e);
        return [e.tagName, e.textContent.trim(), s.outlineStyle, s.outlineWidth]}""")
    check("search button keyboard focus visible", bfocus[0] == "BUTTON" and bfocus[2] != "none", bfocus)
    shot(pg, "focus-button-1280", ".home-finder", w=1280)
    btn = pg.locator(".home-search button").first.bounding_box()
    check("search button touch target >= 44px", btn["height"] >= 44 and btn["width"] >= 44, btn)
    inp = pg.locator("#home-q").bounding_box()
    check("search input touch target >= 44px", inp["height"] >= 44, inp)
    links = pg.evaluate("""() => [...document.querySelectorAll('.home-recent a, .home-desk-list a')]
        .map(a=>{const r=a.getBoundingClientRect();return [a.textContent.trim().slice(0,30), Math.round(r.height)]})""")
    data["link_heights_1280"] = links
    check("record and desk link targets >= 24px (WCAG 2.5.8)", all(h >= 24 for _, h in links), links)
    # The hero photo credit must stay on top: the raised finder may not cover it.
    credit = pg.evaluate("""() => {const a=document.querySelector('.photo-credit a'); a.scrollIntoView({block:'center'});
        const r=a.getBoundingClientRect(), e=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
        return e===a || a.contains(e)}""")
    check("hero photo credit link not occluded", credit, credit)
    # Text contrast of the new card and band text against their computed grounds.
    contrast = pg.evaluate("""() => {
      const rgb=s=>s.match(/[\\d.]+/g).slice(0,3).map(Number), lum=c=>{c=c.map(v=>{v/=255;return v<=.03928?v/12.92:((v+.055)/1.055)**2.4});return .2126*c[0]+.7152*c[1]+.0722*c[2]};
      const bg=e=>{for(;e;e=e.parentElement){const b=getComputedStyle(e).backgroundColor;if(b&&!/rgba\\(.*, 0\\)|transparent/.test(b))return b}return 'rgb(255,255,255)'};
      const ratio=e=>{const a=lum(rgb(getComputedStyle(e).color)),b=lum(rgb(bg(e)));return +((Math.max(a,b)+.05)/(Math.min(a,b)+.05)).toFixed(2)};
      const out={};for(const s of ['.home-card-date','.home-recent .row-side','.home-recent h3 a','.home-analysis-geo figcaption','.home-latest-analysis .meta','.home-desk-list a span'])
        {const e=document.querySelector(s); if(e) out[s]=ratio(e)} return out}""")
    data["contrast_1280"] = contrast
    check("new text contrast >= 4.5:1", all(v >= 4.5 for v in contrast.values()), contrast)
    # Search submits the GET form to archive.html?q=
    pg.fill("#home-q", "exercise")
    with pg.expect_navigation():
        pg.keyboard.press("Enter")
    check("search submits GET archive.html?q=", "archive.html?q=exercise" in pg.url, pg.url.replace(BASE, ""))
    ctx.close()

    # Press under reduced motion: no movement on the home search button.
    for motion in ("reduce", "no-preference"):
        ctx, pg, errs, _ = page_for(b, 1280, reduced_motion=motion)
        pg.locator(".home-search button").scroll_into_view_if_needed()
        bb = pg.locator(".home-search button").bounding_box()
        pg.mouse.move(bb["x"] + 5, bb["y"] + 5); pg.mouse.down()
        pg.wait_for_timeout(250)
        t = pg.evaluate("getComputedStyle(document.querySelector('.home-search button')).transform")
        pg.mouse.move(2, 2); pg.mouse.up()  # release off the button: no submit
        data["press_transform_" + motion] = t
        if motion == "reduce":
            check("reduced motion: pressed search button does not move", t in ("none", "matrix(1, 0, 0, 1, 0, 0)"), t)
            anims = pg.evaluate("document.getAnimations().length")
            check("reduced motion: no running animations", anims == 0, anims)
            shot(pg, "reduced-motion-1280")
        ctx.close()

    # No JS: finished state, nothing hidden.
    for w in (375, 1280):
        ctx, pg, errs, _ = page_for(b, w, java_script_enabled=False)
        hidden = pg.evaluate("""() => [...document.querySelectorAll('.home-finder, .home-register, #analysis, .home-desks, .home-recent li, .home-desk-list a')]
            .filter(e=>{const s=getComputedStyle(e); return s.visibility=='hidden' || +s.opacity < 0.99}).length""")
        check("no-JS: every homepage section visible @%d" % w, hidden == 0, hidden)
        shot(pg, "nojs-%d" % w)
        ctx.close()

    # The intro's skip switch (html.no-anim): nothing animates, nothing hidden.
    ctx, pg, errs, _ = page_for(b, 1280)
    pg.evaluate("document.documentElement.classList.add('no-anim')")
    pg.wait_for_timeout(200)
    st = pg.evaluate("""() => [document.querySelectorAll('.rl-draws').length,
        [...document.querySelectorAll('.rl-draws')].filter(e=>getComputedStyle(e).animationName!='none').length]""")
    check("html.no-anim: relief art not animated", st[1] == 0, st)
    ctx.close()

    # Forced colours.
    for w in (375, 1280):
        ctx, pg, errs, _ = page_for(b, w, forced_colors="active")
        shadows = pg.evaluate("""() => [...document.querySelectorAll('main *')].filter(e=>getComputedStyle(e).boxShadow!='none').length""")
        check("forced colours: no box shadows @%d" % w, shadows == 0, shadows)
        shot(pg, "forced-colors-%d" % w)
        ctx.close()

    # 200% zoom: a 1280 window at 200% is a 640 CSS-px viewport at DPR 2.
    ctx, pg, errs, _ = page_for(b, 640, h=450, device_scale_factor=2)
    overflow = pg.evaluate("document.documentElement.scrollWidth - innerWidth")
    check("200% zoom: no horizontal overflow", overflow <= 0, overflow)
    shot(pg, "zoom200-full")
    ctx.close()

    # Print.
    ctx, pg, errs, _ = page_for(b, 1280)
    pg.emulate_media(media="print")
    shadows = pg.evaluate("""() => [...document.querySelectorAll('main *')].filter(e=>getComputedStyle(e).boxShadow!='none').length""")
    check("print: no box shadows", shadows == 0, shadows)
    ctx.close()
    b.close()

json.dump({"url": "<served scratch build>/index.html", "label": LABEL, "state": data,
           "checks": results, "failures": [r for r in results if not r["passed"]], "shots": shots},
          open(OUT / ("%s-checks.json" % LABEL), "w"), indent=1, ensure_ascii=False)
print("%d checks, %d failures, %d shots" % (len(results), sum(not r["passed"] for r in results), len(shots)))
for r in results:
    if not r["passed"]:
        print("FAIL", r["name"], r["detail"])
