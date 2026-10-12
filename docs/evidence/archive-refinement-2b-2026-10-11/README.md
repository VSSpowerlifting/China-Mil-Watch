# Archive refinement, Phase 2b — evidence (2026-10-11)

Base: `origin/main` = `c9b2c38068995635c6ca143c56bf49b35c2e8022` (PR #391 merge).
Branch: `claude/archive-visual-refinement-2b-1ca784`. Presentation only: no record
data, title, source, sort, filter, index, route, DB, sidecar or `output/` change.

## What changed

| File | Change |
|---|---|
| `site/preview/templates/archive.html` | links `relief.css` before `archive.css`; `#controls` gains `rl-finder` |
| `site/preview/archive.css` | per-desk marker rules on `.row-side a`; hidden in forced colours and print |
| `site/assets/desk-marks/{china,japan,singapore,vietnam}.svg` + receipt | static outlines, 9,767 B total |
| `scripts/build_desk_marks.py` | deterministic generator; reads committed `emblems.svg` |
| `site/preview/generate_preview.py` | `ARCHIVE_MARK_ASSETS` allowlist and its copy loop |
| `tests/test_archive_desk_marks.py` (new), `tests/test_relief_primitives.py` | isolation allowlists widened to `archive.html`; new mark tests |
| `PROJECT_STATE.md`, `DECISION_LOG.md` | records |

Untouched: `browse.js` (9,847 B, byte-identical), `_records.html`, `relief.css`,
`base.html`, every other page.

## Why separate glyph files

Probe `tools/probe_mask.py`, shot `shots/mask-probe-control-symbol-file.png`
(Chromium, three boxes on one page): the unmasked control fills; the
`emblems.svg#china` symbol fragment draws nothing; the standalone
`desk-marks/china.svg` draws the silhouette.

## Gates

| Gate | Result |
|---|---|
| Before/after at 320, 375, 768, 1280 | `shots/{before,after}-{top,rows}-{320,375,768,1280}.png` |
| Finder raised, modest | the homepage's `--lift-3` finder token, hairline border kept; `after-top-*` |
| Marker on every eligible row, all states | `receipts/behave-after.json`: 50/50 on initial, search, Singapore filter, sort, page 2, back, forward; before: 0 |
| Text, rows, counts unchanged | `behave-before.json` vs `behave-after.json`: row count, `#results` text length and first-row text identical in all seven states |
| Singapore | marker via browse.js desk filter; `singapore.svg` 200 |
| Japan, Vietnam, unmapped desk | synthetic rows (`after-synthetic-640.png`): both marked, Philippines none |
| No console errors, failed assets | 0 console errors, 0 responses >= 400; mask fetches 200 |
| Overflow | 0 px at 320, 375, 768, 1280 and at 640 CSS px (200% zoom) |
| JavaScript off | 50 server rows render, finder keeps `hidden` and stays invisible (`after-nojs-real-1280.png`, `receipts/nojs-and-index-error.json`) |
| browse.js blocked | JS on, `browse.js` aborted: 50 server rows marked, finder stays `hidden` (`after-browsejs-blocked-1280.png`) |
| Index error behaviour | `corpus-index.json` aborted, then a search: before and after identical (`#browse` hidden, error notice shown, the 50 rows kept, one console error from the aborted fetch itself); `*-index-error-1280.png` |
| Reduced motion | no motion added; the marker is static |
| Forced colours | finder `box-shadow:none`, marker `display:none` (`after-forced-colors-*`) |
| Print | finder hidden (existing rule), marker `display:none` |
| Keyboard | Tab reaches `#f-q`; 2 px outline unchanged |
| B1 restriction | `archive.css` has no `box-shadow`, `--lift-` or drop shadow (tested) |
| Validator | `validate_output.py`: passed, 10 warnings (baseline) |
| Delivery budget | 0 failures over 7,589 routes. archive.html HTML+CSS 134,055 → 139,634 B (cap 300,000); JS 9,847 B (cap 10,000), unchanged |
| Integrity | `verify_frontend_integrity.py` passed before and after (5,097 record bodies) |
| Route tree | full-tree diff, before vs after: 7,682 → 7,686 files; added the 4 marks; changed `archive.css`, `archive.html`; nothing else |

`asset_bytes` rises 9,767 B because the budget tool counts every `url()` in
`archive.css`; a browser fetches a mark only when a row for that desk is
rendered on the page (today China, 3,950 B, and Singapore, 707 B).

## Caveats

- Screenshots are Chromium only (Playwright); no Safari or Firefox pass.
- With JavaScript off, computed styles cannot be queried, so the marker is
  confirmed from `after-nojs-real-1280.png`; computed-style proof is from the
  browse.js-blocked run.
- Japan and Vietnam have no records yet, so their markers are verified on
  synthetic rows only.
- The scratch builds used `--snapshot-from-corpus`; `output/` was never
  regenerated.
