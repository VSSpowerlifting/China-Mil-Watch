import functools, http.server, socketserver, sys, threading, json
from pathlib import Path
from playwright.sync_api import sync_playwright
root = Path(sys.argv[1]); shots = Path(sys.argv[2]); shots.mkdir(exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(root)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}/"
routes = sorted("the-pla-watch/posts/" + p.name for p in (root/"the-pla-watch/posts").glob("*.html")) + \
         sorted("briefs/" + p.name for p in (root/"briefs").glob("*.html") if p.name != "index.html")
problems, summary = [], {}
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for w in (320, 375, 768, 1280):
        page = b.new_page(viewport={"width": w, "height": 900})
        errs, bad = [], []
        page.on("console", lambda m: m.type == "error" and errs.append(m.text))
        page.on("response", lambda r: r.status >= 400 and bad.append(r.url))
        for r in routes:
            page.goto(base + r); page.evaluate("document.fonts.ready")
            info = page.evaluate("""() => {
              const f = document.querySelector('.brief-hero figure');
              const k = f ? (f.dataset.articleMedia || f.className) : null;
              const pl = document.querySelector('.article-plate-art');
              const imgs = [...document.querySelectorAll('img')].filter(i => i.complete && i.naturalWidth === 0 && i.loading !== 'lazy').map(i => i.src);
              const nav = [...document.querySelectorAll('.brief-issue-nav a')].map(a => a.getAttribute('href'));
              return {k, overflow: document.documentElement.scrollWidth - innerWidth,
                      plateH: pl ? pl.getBoundingClientRect().height : null,
                      figW: f ? f.getBoundingClientRect().width : null, imgs, nav,
                      cap: f && f.querySelector('figcaption') ? f.querySelector('figcaption').innerText : null};
            }""")
            summary.setdefault(r, {})[w] = info
            if info["overflow"] > 0: problems.append((w, r, "overflow", info["overflow"]))
            if not info["k"]: problems.append((w, r, "no hero figure"))
            if info["imgs"]: problems.append((w, r, "broken", info["imgs"]))
            if info["plateH"] is not None and info["plateH"] < 150: problems.append((w, r, "plate short", info["plateH"]))
            if w in (375, 1280) and r.split("/")[-1] in ("2026-05-30.html", "2026-08-15.html", "trident-resolve-regional-scale-specific-chinese-tasks.html", "2026-06-27.html"):
                page.screenshot(path=str(shots / f"{w}-{r.split('/')[-1][:-5]}.png"), full_page=False)
        problems += [(w, "console", e) for e in errs] + [(w, "http", u) for u in set(bad)]
        page.close()
    # forced colors + print on a historical plate page
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.emulate_media(forced_colors="active"); page.goto(base + "the-pla-watch/posts/2026-08-15.html")
    fc = page.evaluate("getComputedStyle(document.querySelector('.article-plate-art')).display")
    page.screenshot(path=str(shots / "forced-2026-08-15.png"))
    page.emulate_media(forced_colors="none", media="print")
    pr = page.evaluate("getComputedStyle(document.querySelector('.article-plate')).display")
    rm = page.evaluate("[...document.querySelectorAll('.brief-hero figcaption [lang]')].map(e=>e.lang+':'+e.textContent)")
    page.goto(base + "the-pla-watch/posts/2026-06-27.html")
    ja = page.evaluate("[...document.querySelectorAll('.brief-hero figcaption [lang]')].map(e=>e.lang+':'+e.textContent)")
    b.close()
kinds = {r: v[1280]["k"] for r, v in summary.items()}
print(json.dumps(kinds, indent=0)); print("forced display:", fc, "print display:", pr, "No.8 lang:", ja)
print("nav 14:", summary["the-pla-watch/posts/2026-08-15.html"][1280]["nav"])
print("nav 15:", summary["briefs/maritime-cooperation-2026.html"][1280]["nav"])
print("PROBLEMS", len(problems)); [print(p) for p in problems[:30]]
srv.shutdown()
