"""Generate actual Phase 4A Desks screenshots and DOM receipts, off production.

Run on a PR head after Playwright Chromium is installed. The candidate builder
writes only to a fresh disposable directory, preserving output/ and the DB.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site" / "preview"))

import generate_preview as gp  # noqa: E402
from tests.test_desks_phase4_browser import PROBE, WIDTHS

OUT = ROOT / "phase4a-visual-receipt"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    failures = []
    receipts = []
    with tempfile.TemporaryDirectory(prefix="ipr-p4a-visual-") as temp:
        destination = Path(temp) / "build"
        gp.build(
            destination,
            "Indo-Pacific Record",
            ROOT / "pla_watch.db",
            snapshot=gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
        )
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                for width in WIDTHS:
                    page = browser.new_page(
                        viewport={"width": width, "height": 900},
                        reduced_motion="reduce",
                    )
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto((destination / "desks.html").as_uri(), wait_until="load")
                    result = page.evaluate(PROBE)
                    result["page_errors"] = errors
                    result["flag_images"] = page.locator(".deskmap-flag-tab img").evaluate_all(
                        "(nodes) => nodes.map(n => ({src:n.getAttribute('src'), "
                        "complete:n.complete, naturalWidth:n.naturalWidth}))"
                    )
                    if len(result["flag_images"]) != 8 or any(
                        not im["complete"] or im["naturalWidth"] == 0
                        for im in result["flag_images"]
                    ):
                        failures.append(f"{width}: missing or broken public flag SVG")
                    receipts.append(result)
                    if result["cards"] != 7 or result["unplaced"] != 1:
                        failures.append(f"{width}: incomplete 7+1 desk roster")
                    for key in ("overlaps", "labelHits", "outside", "page_errors"):
                        if result[key]:
                            failures.append(f"{width}: {key}: {result[key]}")
                    if result["docWidth"] > width + 1:
                        failures.append(f"{width}: horizontal overflow {result['docWidth']}")
                    if width in (375, 900, 1280, 1600):
                        page.locator("figure.deskmap").screenshot(
                            path=str(OUT / f"desks-{width}.png")
                        )
                    if width == 1600:
                        page.locator('[data-select-desk="singapore"]').click()
                        page.locator("figure.deskmap").screenshot(
                            path=str(OUT / "desks-singapore-selected-1600.png")
                        )
                    page.close()

                context = browser.new_context(
                    viewport={"width": 375, "height": 812},
                    java_script_enabled=False,
                    reduced_motion="reduce",
                )
                nojs = context.new_page()
                nojs.goto((destination / "desks.html").as_uri(), wait_until="load")
                count = nojs.locator(".deskmap-plate").count()
                receipts.append({"mode": "no-js", "plate_count": count})
                nojs.locator("figure.deskmap").screenshot(
                    path=str(OUT / "desks-nojs-375.png")
                )
                if count != 8:
                    failures.append("no-JS mode failed eight-desk fallback")
                context.close()

                forced = browser.new_page(
                    viewport={"width": 375, "height": 812},
                    forced_colors="active",
                    reduced_motion="reduce",
                )
                forced.goto((destination / "desks.html").as_uri(), wait_until="load")
                sample = forced.evaluate("""() => {
                    const fill = sel => getComputedStyle(document.querySelector(sel)).fill;
                    const reset = getComputedStyle(document.querySelector('.deskmap-reset'));
                    return {
                        canvas:fill('.dm-sea'),
                        live:fill('.dm-country.is-live use'),
                        quiet:fill('.dm-country.is-quiet use'),
                        buttonText:reset.color,
                        buttonBackground:reset.backgroundColor
                    };
                }""")
                receipts.append({"mode":"forced-colors", "sample":sample})
                if sample["canvas"] != sample["live"] or sample["canvas"] != sample["quiet"]:
                    failures.append("forced colours: country fills obscure the map")
                if sample["buttonText"] == sample["buttonBackground"]:
                    failures.append("forced colours: selected desk button text invisible")
                forced.locator("figure.deskmap").screenshot(
                    path=str(OUT / "desks-forced-colors-375.png")
                )
                forced.close()
            finally:
                browser.close()

    (OUT / "measurements.json").write_text(
        json.dumps(
            {"viewport_receipts": receipts, "failures": failures},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"viewports": len(WIDTHS), "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
