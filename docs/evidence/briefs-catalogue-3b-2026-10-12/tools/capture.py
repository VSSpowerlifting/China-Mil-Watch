#!/usr/bin/env python3
"""Serve a built tree on loopback and capture analysis.html (read-only).

usage: capture.py TREE LABEL OUTDIR [--widths 320,375,768,1280] [--modes default,...]
Full-page PNGs at each width; records scrollWidth, console errors, failed
requests and every image request so the caller can audit them.
"""
import argparse, functools, http.server, json, socketserver, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

MODES = {
    "default": dict(),
    "no-js": dict(java_script_enabled=False),
    "reduced-motion": dict(reduced_motion="reduce"),
    "forced-colors": dict(forced_colors="active"),
    "dark": dict(color_scheme="dark"),
}

def serve(tree):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tree))
    handler.log_message = lambda *a, **k: None
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tree"); ap.add_argument("label"); ap.add_argument("out")
    ap.add_argument("--widths", default="320,375,768,1280")
    ap.add_argument("--modes", default="default")
    ap.add_argument("--page", default="analysis.html")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    srv, base = serve(Path(a.tree))
    report = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for mode in a.modes.split(","):
            for w in [int(x) for x in a.widths.split(",")]:
                ctx = b.new_context(viewport={"width": w, "height": 900}, **MODES[mode])
                page = ctx.new_page()
                errs, images = [], []
                page.on("pageerror", lambda e: errs.append(str(e)))
                page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
                page.on("response", lambda r: (errs.append("%s %s" % (r.status, r.url)) if r.status >= 400 else None,
                                                images.append(r.url) if r.request.resource_type == "image" else None))
                page.goto(base + "/" + a.page, wait_until="networkidle")
                page.evaluate("document.fonts.ready")
                # Reveal-on-scroll art finishes by scrolling once; then return to the top.
                h = page.evaluate("document.documentElement.scrollHeight")
                for y in range(0, h, 700): page.evaluate("window.scrollTo(0,%d)" % y); page.wait_for_timeout(60)
                page.evaluate("window.scrollTo(0,0)"); page.wait_for_timeout(250)
                name = "%s-%s-%d.png" % (a.label, mode, w)
                page.screenshot(path=str(out / name), full_page=True)
                report.append(dict(mode=mode, width=w, shot=name, scrollWidth=page.evaluate("document.documentElement.scrollWidth"),
                                   innerWidth=w, errors=errs, images=sorted(set(images))))
                ctx.close()
        b.close()
    srv.shutdown()
    (out / ("capture-%s.json" % a.label)).write_text(json.dumps(report, indent=1))
    for r in report: print(r["mode"], r["width"], "overflow" if r["scrollWidth"] > r["innerWidth"] else "ok", "errors:", len(r["errors"]))

if __name__ == "__main__": main()
