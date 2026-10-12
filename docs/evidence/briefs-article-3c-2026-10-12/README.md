# Phase 3C evidence — opened Brief articles

2026-10-12. Baseline: main `18b57684e6` (Phase 3B, PR #418 merged). Every render below is disposable. `site/render.py --out <scratch>` drives the three native Briefs. `tools/render_historical.py` drives the 14 earlier issues: it calls `scripts/historical_brief_render.py` with the same date-sorted `prev_post`/`next_post` wiring as `scripts/rerender_pla_watch.py`. Tracked `output/`, `pla_watch.db` and the canonical sidecars were not written. `receipts/verifiers.txt` ends with the DB checksum and an empty `git status -- output/ pla_watch.db`. The verifiers were run on an *overlay*: a copy of tracked `output/` with the after renders laid on top, which is the state after the owner's rerender. Not merged, not deployed. Contract: `docs/engineering/BRIEFS_ARTICLE_PHASE3C_2026-10-12.md`. The PR names the frozen head the receipts belong to.

## What to look at

| Question | File |
|---|---|
| Which treatment each of the 17 articles gets | `receipts/media-kinds.json` |
| What changed in the rendered HTML, route by route | `receipts/render-diff.txt` (which files), `receipts/invariants-summary.txt` and `receipts/invariants-delta.json` (which fields) |
| Photograph caption, before and after | `shots/caption-no08-photograph-{375,1280}-{before,after}.jpg`, `shots/caption-no09-photograph-*` |
| Signal Veil caption, before and after | `shots/caption-no02-signal-veil-{375,1280}-{before,after}.jpg` |
| Previous / next Brief | `shots/nav-no02-*`, `shots/nav-no08-*`, `shots/nav-no09-*` (before/after); `shots/nav-no15-native-*-after.jpg` (new on native pages) |
| Hero-to-reading transition at 320/375/768/1280 | `shots/transition-{no02-signal-veil,no08-photograph,no12-held,no14-text-led,no15-native,no17-native}-*-after.jpg`; before: `transition-no08-*-before`, `transition-no15-*-before` |
| Native author block | `shots/author-no15-native-{375,1280}-{before,after}.jpg` |
| Keyboard focus on the new nav | `shots/keyboard-focus-no08-prev-1280.jpg`, `shots/keyboard-focus-no15-next-1280.jpg` |
| Forced colours, no-JS, reduced motion | `shots/forced-colors-*`, `shots/nojs-*`, `shots/reduced-motion-*` |
| 200% zoom | `shots/zoom200-no08-nav.jpg`, `shots/zoom200-no15-nav.jpg` |
| Print | `print/no08-photograph-print.pdf`, `print/no15-native-print.pdf` |
| Whole pages | `shots/fullpage-no08-photograph-1280-after-50pct.jpg`, `shots/fullpage-no15-native-375-after.jpg` |
| Browser contract runs (all 17 routes × 4 widths, modes, keyboard, zoom, print, fragment navigation) | `receipts/browser-qa.txt` |
| Budgets | `receipts/budget.txt`; `receipts/verifiers.json` (delivery verifier, per article) |
| Validator, delivery, integrity, DB, `output/` | `receipts/verifiers.txt` |
| Tests | `receipts/tests.txt` |
| Capture and measurement tools | `tools/` |

Screenshots were captured as PNG in Chromium (Playwright, `file://`) and stored as JPEG to keep the folder small. Run the tools with the repository's `.venv` python. `tools/budget.py` imports `core.frontend_budget` from the repository root.

## Results

- **Media.** Seven Signal Veils (Nos. 2, 3, 5, 6, 7, 11, 13) gain a leading "Signal Veil" label. The rest of the caption is the pre-3C text, word for word, and the stored `credit` of a source veil is never read.
- **Photographs.** Two photographs (No. 8 and No. 9) now carry:
  - the manifest's full credit in place of the abbreviated id;
  - the licence, linked to its deed where the manifest records one (No. 8, CC BY 4.0);
  - "via Wikimedia Commons", linked to the file page;
  - "Toned, cropped and resized by IPR." and "Visual context, not evidence."
- **Unchanged figures and text-led pages.** Nos. 1, 10, 12 and 15 keep their figure markup byte for byte. Nos. 4, 14, 16 and 17 have no figure and still have none. "Downloaded from PLA Daily" appears on no route, before or after.
- **Invariants.** On all 17 routes the following fields are equal before and after:
  - title and meta (canonical, Open Graph, description);
  - h1, heading order and ids;
  - article paragraphs and language spans;
  - images;
  - the citation, provenance line and byline;
  - the model-flagged count.

  Only `hrefs` (17), `figcaptions` (9) and `external_hrefs` (1, No. 8's licence) differ, each as predicted before editing. `receipts/invariants-summary.txt` explains every delta.
- **Navigation.** The 14 earlier issues keep their prev/next targets; the links gain labels and readable titles. The 3 native Briefs gain the same nav, in collection order. No. 15's "Previous Brief" link goes to No. 14's historical route.
- **Browser.**
  - All 17 routes at 320, 375, 768 and 1280 px: no horizontal overflow, console error or failed request.
  - The same holds for new historical pages served with the old `briefs.css` (mixed state), and for the no-JS, reduced-motion and forced-colours runs.
  - Every nav link is reachable by Tab with a 2 px solid outline.
  - 200% zoom keeps `scrollWidth` at 640.
  - Print hides the nav and keeps the photograph caption.
  - In Chromium, Firefox and WebKit, a fragment URL or a TOC click opens the collapsed `#s-compare` and `#s-coverage` sections with the heading in view.
- **Budgets.**
  - HTML+CSS per article: 75,930–86,310 B historical, 78,484–79,091 B native, all under the 120,000 B cap.
  - JS: unchanged (372 B historical, 5,322 B native; cap 10,000 B).
  - Delivery verifier: 0 failures on 7,609 routes, both overlay and tracked `output/`.
- **Integrity verifier.** All 5,097 record bodies, titles, source URLs, dates and compatibility routes verified on the overlay.
- **Validator.** Tracked `output/` passes with the baseline 10 governed warnings. The overlay passes with 7: the three LinkedIn warnings depend on location and cannot fire outside the repository (`receipts/verifiers.txt`).
- **Tests.**
  - Focused suites (`test_article_media`, `test_historical_brief_shell`, `test_briefs_collection`): 117 tests, OK.
  - Full suite: 5,966 tests, 0 failures. The 25 errors are local-environment errors in suites that import none of the changed modules: no `python-docx`, and `unsafe_store_root` for the macOS temp directory.

## Limits

- **Browsers.** Chromium for the screenshots and mode runs; Firefox and WebKit only for fragment navigation. Forced colours are Playwright's emulation. No screen-reader run.
- **Captures** were taken on `file://` renders, not a deployed site.
- **Native keyboard check.** The `inView=False` result on the native keyboard runs is subpixel: the focused link's bottom edge is 0.016 px and 0.125 px past a 900 px viewport (`browser-qa.txt`, focusgap section).
- **Image rights.** Nothing here re-examines image rights. The open items are in the engineering contract.
