# Phase 3B evidence — Briefs catalogue

2026-10-12. Candidate built from main `22293e92bc` plus this branch. Not merged, not deployed; `output/` was not regenerated. Design and engineering contract: `docs/engineering/BRIEFS_CATALOGUE_PHASE3B_2026-10-12.md`.

## What to look at

| Question | File |
|---|---|
| What changed visually, at four widths | `shots/before-default-{320,375,768,1280}.jpg`, `shots/after-default-{320,375,768,1280}.jpg` (full page) |
| Forced colours | `shots/after-forced-colors-{320,375,768,1280}.jpg` |
| No-JS / reduced motion | Byte-identical to default at every width: `receipts/mode-equivalence.json` |
| 17/17 card audit (decision beside render) | `receipts/catalogue-17-card-audit.json` |
| Licence / creator verification of the three originals | `receipts/commons-imageinfo-raw.json` (raw Commons API response, with its limits) |
| Browser contract run (42 cases, 4 flows) | `receipts/browser-qa.json` |
| Budgets | `receipts/analysis-budget.json`, `receipts/frontend-delivery-candidate.json` |
| Output / record integrity | `receipts/frontend-integrity-candidate.json` |
| Capture tool | `tools/capture.py` |

## Results

- **Cards:** 17 of 17 rendered, newest first, numbered 17 → 1. 3 photographs (Nos. 8, 9, 10), 14 Editorial plates. No. 1 `held`, No. 12 `denied`.
- **Publication contract:** after removing only the additive nodes (17 media blocks, 17 credit blocks, 1 key), body text, 59 links and ids equal current main exactly (`scripts/verify_briefs_catalog.py`). Historical `rel="noopener"` live-archive links, "From the former series The PLA Watch" lines and "The PLA Watch:" title prefixes are present as before.
- **Forbidden requests:** zero requests for `*-source-image*`, `*-veil*`, `81.cn` or `81cn` across 42 browser cases plus the media audit.
- **Layout:** no horizontal overflow at 320, 375, 768, 960, 1280 or 1440 in any profile; every media frame measures 3:2; photographs load at 720×480 with explicit dimensions and `loading="lazy"`.
- **Modes:** default, no-JS, script-failure, reduced-motion, no-anim, forced-colors and print profiles pass; keyboard journey (skip link → Browse anchor → card focus ring and lift → Brief navigation) and mouse hover lift pass. CLS ≤ 0.025 at 375 and 1440, equal to current main.
- **Budgets:** `analysis.html` HTML+CSS 119,633 B (cap 300,000 B; main 101,878 B). JS 3,118 B (cap 10,000 B; unchanged). Delivery verifier: 0 failures on 7,589 routes (legacy-routes build). Integrity verifier: all 5,097 record bodies, titles, URLs, dates and compatibility routes verified.
- **Validator:** `scripts/validate_output.py output` passes with the baseline 10 governed warnings (`output/` untouched).
- **Tests:** new `tests/test_catalogue_media.py` (25). Re-run after the change and passing: `test_relief_primitives`, `test_briefs_collection`, `test_historical_source_veil_provenance`, `test_archive_desk_marks` (120); `test_preview_prototype`, `test_site_mode_contract`, `test_identity_assets`, `test_pla_watch_authoring_identity`, `test_historical_brief_shell` (673, 1 skipped); `test_cover_origin_rebasing`, `test_ipr_briefs`. The full suite was not run.

## Limits

- **Image rights.** The Commons receipt verifies licence, creator and description of each Commons *original*. It does not prove the re-encoded local derivatives come from it, and no publisher-site retrieval or independent photo-origin investigation was made. No. 10's public-domain status rests on Commons' "PD US Government" categorisation and the CRS report's own statement. Admissions are an engineering review pending independent confirmation, not an owner ruling.
- **Delivery accounting.** The delivery verifier's asset list does not count `assets/geo/region.svg` (referenced through `<use>`). Real local delivery for the page is about 50 KB higher than `asset_bytes` reports.
- **Browsers.** Chromium 147 only; forced colours are Playwright's emulation. No Safari, Firefox or screen-reader run. The card focus ring uses `:has()`; without it the link keeps its own outline.
- **Not exercised.** The hero lead photograph branch (no native lead has a cover), the draft-review and synthetic-fixture branches beyond their unit/regression tests.
- **Captures** were taken against the built tree served on loopback, not a deployed site.

## Reproduce

```bash
.venv/bin/python site/preview/generate_preview.py --out /tmp/cand --snapshot-from-corpus --legacy-routes
.venv/bin/python scripts/build_catalogue_media.py --check
.venv/bin/python docs/evidence/briefs-catalogue-3b-2026-10-12/tools/capture.py /tmp/cand after OUT --widths 320,375,768,1280 --modes default,forced-colors
.venv/bin/python scripts/verify_briefs_catalog.py --url … --baseline-url … --released-url … --root /tmp/cand --baseline <main build> --out OUT
```
