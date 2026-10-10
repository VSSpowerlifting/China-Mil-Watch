#!/usr/bin/env python3
"""Capture reproducible human-review evidence from already-rendered IPR pages.

Read-only: serves the checked-in HTML on loopback, never rebuilds the site,
reads no secrets, runs no collector/models, and saves images outside output/.
Passing browser assertions do not constitute human visual approval.
"""

import argparse
import functools
import hashlib
import http.server
import json
import threading
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def route_inventory(root):
    """Identify exact existing routes; a missing required family is a failure."""
    required = {
        "home": "index.html",
        "records": "archive.html",
        "briefs-catalog": "analysis.html",
        "desks": "desks.html",
        "about": "about.html",
        "record": "record/1.html",
        "historical-index": "the-pla-watch/index.html",
        "historical-terms": "the-pla-watch/terms.html",
    }
    routes = dict(required)
    briefs = sorted((root / "briefs").glob("*.html"))
    history = sorted((root / "the-pla-watch/posts").glob("*.html"))
    if not briefs or len(history) != 14:
        raise RuntimeError("Expected at least one native Brief and exactly 14 historical Briefs")
    routes["native-brief"] = briefs[0].relative_to(root).as_posix()
    for label, index in (("historical-first", 0), ("historical-middle", len(history) // 2), ("historical-last", -1)):
        routes[label] = history[index].relative_to(root).as_posix()
    missing = [route for route in routes.values() if not (root / route).is_file()]
    if missing:
        raise RuntimeError("Required rendered site routes missing: " + ", ".join(missing))
    return routes


def capture(root, dest):
    routes = route_inventory(root)
    dest.mkdir(parents=True, exist_ok=True)
    records = []
    problems = []
    handler = functools.partial(QuietHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = "http://127.0.0.1:%d/" % server.server_port
    cases = [(label, path, "desktop", 1440, True, False) for label, path in routes.items()]
    cases += [(label, path, "mobile", 390, True, False) for label, path in routes.items()]
    for label in ("home", "records", "briefs-catalog", "native-brief", "historical-last"):
        cases.append((label, routes[label], "no-js-mobile", 390, False, False))
        cases.append((label, routes[label], "reduced-motion-mobile", 390, True, True))
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for label, route, mode, width, js, reduced in cases:
                record = {"label": label, "route": route, "mode": mode, "width": width}
                context = browser.new_context(
                    viewport={"width": width, "height": 900 if width > 600 else 844},
                    device_scale_factor=1,
                    java_script_enabled=js,
                    reduced_motion="reduce" if reduced else "no-preference",
                )
                context.route("https://fonts.googleapis.com/**", lambda request: request.abort())
                context.route("https://fonts.gstatic.com/**", lambda request: request.abort())
                page = context.new_page()
                page_errors = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                try:
                    url = origin + quote(route, safe="/-._~")
                    response = page.goto(url, wait_until="networkidle", timeout=30000)
                    if response is None or response.status >= 400:
                        raise AssertionError("HTTP error: %s" % (response.status if response else "none"))
                    if page.locator("h1").count() != 1 or not page.locator("h1").first.is_visible():
                        raise AssertionError("Missing/duplicate/invisible primary heading")
                    if page.locator("main").count() != 1:
                        raise AssertionError("Missing or duplicated main landmark")
                    overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                    if overflow:
                        raise AssertionError("Horizontal overflow")
                    filename = "%s--%s.png" % (label, mode)
                    image = dest / filename
                    page.screenshot(path=str(image), full_page=True, animations="disabled", timeout=45000)
                    record["file"] = filename
                    record["sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
                    record["bytes"] = image.stat().st_size
                    record["javascript"] = js
                    record["reduced_motion"] = reduced
                    if page_errors:
                        raise AssertionError("Browser script errors: " + repr(page_errors[:3]))
                    record["status"] = "captured"
                except Exception as exc:
                    record["status"] = "failed"
                    record["error"] = str(exc)
                    problems.append(record)
                finally:
                    records.append(record)
                    context.close()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        (dest / "REVIEW_MANIFEST.json").write_text(
            json.dumps({"purpose": "Human visual review, not release approval",
                        "routes": routes, "cases": records, "failures": problems}, indent=2) + "\n",
            encoding="utf-8",
        )
    if problems:
        raise RuntimeError("%d/%d visual-capture smoke cases failed; review manifest" % (len(problems), len(cases)))
    print("Captured %d read-only visual-review screenshots across %d real routes" % (len(records), len(routes)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    dest = args.out.resolve()
    if not (root / "index.html").is_file():
        parser.error("--root must be an existing rendered output directory")
    if dest == root or root in dest.parents:
        parser.error("--out must be outside the rendered site directory")
    capture(root, dest)


if __name__ == "__main__":
    main()
