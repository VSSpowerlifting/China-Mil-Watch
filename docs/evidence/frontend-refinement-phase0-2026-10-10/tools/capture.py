"""Phase 0 study capture (disposable). Loads a page from the local preview
server, optionally injects a study overlay (CSS + JS + JSON data), and saves
element screenshots. Nothing is written outside --out.

usage: python capture.py PLAN.json
PLAN = {"base": "http://localhost:8765/", "out": "...", "data": {...},
        "shots": [{"page": "index.html", "width": 1280, "css": [...], "js": [...],
                   "classes": ["study"], "media": {"reduced_motion": "reduce"},
                   "items": [{"name": "x", "sel": ".home-finder", "pad": [t,r,b,l],
                              "clip_to": null, "full": false}]}]}
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(plan["out"])
out.mkdir(parents=True, exist_ok=True)
data = plan.get("data", {})
for key, path in plan.get("data_files", {}).items():
    data[key] = json.loads(Path(path).read_text(encoding="utf-8"))
report = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for shot in plan["shots"]:
        media = shot.get("media", {})
        ctx = browser.new_context(
            viewport={"width": shot["width"], "height": shot.get("height", 900)},
            device_scale_factor=shot.get("dpr", 1),
            reduced_motion=media.get("reduced_motion", "reduce"),
            forced_colors=media.get("forced_colors", "none"),
        )
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(plan["base"] + shot["page"], wait_until="networkidle")
        page.evaluate("d => { window.STUDY = d; }", data)
        for cls in shot.get("classes", []):
            page.evaluate("c => document.documentElement.classList.add(c)", cls)
        css_bytes = 0
        for css in shot.get("css", []):
            text = Path(css).read_text(encoding="utf-8")
            css_bytes += len(text.encode())
            page.add_style_tag(content=text)
        js_bytes = 0
        for js in shot.get("js", []):
            text = Path(js).read_text(encoding="utf-8")
            js_bytes += len(text.encode())
            page.add_script_tag(content=text)
        page.wait_for_timeout(shot.get("settle", 400))
        for item in shot["items"]:
            name = "%s-%d.png" % (item["name"], shot["width"])
            target = out / name
            if item.get("full"):
                page.screenshot(path=str(target), full_page=True)
            else:
                loc = page.locator(item["sel"]).first
                loc.scroll_into_view_if_needed()
                page.wait_for_timeout(150)
                box = loc.bounding_box()
                if not box:
                    report.append({"shot": name, "error": "no box for " + item["sel"]})
                    continue
                t, r, b, l = item.get("pad", [0, 0, 0, 0])
                y0 = box["y"] + page.evaluate("scrollY") - t
                clip = {"x": max(0, box["x"] - l), "y": max(0, y0),
                        "width": min(shot["width"], box["width"] + l + r),
                        "height": box["height"] + t + b}
                if item.get("max_h"):
                    clip["height"] = min(clip["height"], item["max_h"])
                page.screenshot(path=str(target), clip=clip, full_page=True)
            report.append({"shot": name, "css_bytes": css_bytes, "js_bytes": js_bytes,
                           "errors": errors[:]})
        if shot.get("probe"):
            report.append({"probe": shot["page"], "width": shot["width"],
                           "result": page.evaluate(shot["probe"])})
        ctx.close()
    browser.close()

(out / ("report-%s.json" % plan.get("tag", "run"))).write_text(json.dumps(report, indent=1), encoding="utf-8")
print(json.dumps(report, indent=1)[:3000])
