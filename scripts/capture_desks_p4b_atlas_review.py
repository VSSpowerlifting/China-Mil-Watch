"""Read-only Phase 4B Source Atlas browser screenshots and verification.

No production output, DB modification, external service or deployment.
This runs on a temporary PR merge that includes the Source Atlas frontend.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as gp  # noqa: E402

OUT = ROOT / "phase4b-atlas-visual-receipt"
DESKS = ("china", "singapore", "japan", "korea",
         "philippines", "vietnam", "indonesia", "us-indopacific")
SAMPLE_DESKS = ("china", "vietnam", "indonesia", "us-indopacific")


def main() -> int:
    OUT.mkdir(exist_ok=True)
    failures, receipts = [], []
    with tempfile.TemporaryDirectory(prefix="ipr-p4b-visual-") as temp:
        destination = Path(temp) / "site"
        gp.build(destination, "Indo-Pacific Record", ROOT / "pla_watch.db",
                 snapshot=gp.snapshot_from_corpus(ROOT / "pla_watch.db"))
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                for width in (375, 768, 1280, 1600):
                    page = browser.new_page(
                        viewport={"width": width, "height": 900},
                        reduced_motion="reduce",
                    )
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto((destination / "desks.html").as_uri(), wait_until="load")
                    panels = page.locator("article.sa-panel")
                    slugs = panels.evaluate_all(
                        "(elements) => elements.map(e => e.id.replace(/^atlas-/, ''))"
                    )
                    doc_width = page.evaluate("document.documentElement.scrollWidth")
                    visible = [
                        slug for slug in DESKS
                        if page.locator("#atlas-" + slug).is_visible()
                    ]
                    failures.extend([f"{width}: panel order incorrect"]
                                    if slugs != list(DESKS) else [])
                    if doc_width > width + 1:
                        failures.append(f"{width}: horizontal overflow {doc_width}")
                    if len(visible) != 8:
                        failures.append(f"{width}: only {len(visible)} visible panels")
                    if errors:
                        failures.append(f"{width}: page errors: {errors}")
                    receipts.append({"width": width, "panels": slugs,
                                     "visible": visible, "documentWidth": doc_width,
                                     "pageErrors": errors})
                    if width in (375, 1280):
                        for slug in SAMPLE_DESKS:
                            page.locator("#atlas-" + slug).screenshot(
                                path=str(OUT / f"atlas-{slug}-{width}.png"))
                        page.locator(".sa-intro").screenshot(
                            path=str(OUT / f"atlas-intro-{width}.png"))
                    page.close()
                nojs = browser.new_context(
                    viewport={"width": 375, "height": 812},
                    java_script_enabled=False,
                    reduced_motion="reduce",
                )
                nojs_page = nojs.new_page()
                nojs_page.goto((destination / "desks.html").as_uri(), wait_until="load")
                count = nojs_page.locator("article.sa-panel").count()
                if count != 8:
                    failures.append(f"no-JS mode has {count} panels, expected eight")
                nojs_page.locator("#atlas-indonesia").screenshot(
                    path=str(OUT / "atlas-indonesia-375-nojs.png"))
                receipts.append({"mode": "no-js", "panelCount": count})
                nojs.close()

                contrast = browser.new_page(
                    viewport={"width": 375, "height": 812},
                    forced_colors="active",
                    reduced_motion="reduce",
                )
                contrast.goto((destination / "desks.html").as_uri(),
                              wait_until="load")
                contrast.locator("#atlas-indonesia").screenshot(
                    path=str(OUT / "atlas-indonesia-375-forced-colors.png"))
                if contrast.locator("article.sa-panel").count() != 8:
                    failures.append("forced colours: missing Atlas panels")
                contrast.close()
            finally:
                browser.close()
    (OUT / "measurements.json").write_text(
        json.dumps({"receipts": receipts, "failures": failures},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"receipts": len(receipts), "failures": failures},
                     indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
