# Phase 3B evidence — Briefs catalogue

2026-10-12. Revised after the independent review of PR #418 (reviewed head `acf5c92404`). Candidate = branch synced with main `dd79144399`. The browser, budget, delivery and integrity receipts and the captures were produced on the tree synced at `4717c8e38a`; the final sync brought in #426 (Philippines desk entrypoints), which touches none of this page's files, and `receipts/route-parity.json` was re-measured against `dd79144399`. Not merged, not deployed; `output/` was not regenerated. Design and engineering contract: `docs/engineering/BRIEFS_CATALOGUE_PHASE3B_2026-10-12.md`. The frozen head the receipts belong to is named in the PR.

## Review response

| # | Review item | Where it is addressed |
|---|---|---|
| 1 | No. 10 held; two photographs, fifteen plates | `site/assets/catalogue/admissions.json`; `receipts/catalogue-17-card-audit.json` (2 photographs, 15 plates); No. 10's derivative removed |
| 2 | Hero credit parity and a hero test | `site/preview/templates/_catalogue_credit.html` (`photo_credit`, used by card and hero); `tests/test_catalogue_media.py::HeroPhotographTests` |
| 3 | Source-hash and origin continuity at build time | `core/catalogue_media.py::_check`; negative tests in `ResolverRuleTests` |
| 4 | Red `offline-checks` contract | `tests/test_extraction_interface.py` (`strip_trigger_path_filters`) |
| 5 | Sync main; re-measure parity against it | `receipts/route-parity.json` (baseline = fresh build of main `dd79144399`) |
| 6 | Report the `region.svg` weight | `receipts/analysis-budget.json` (`actual_page_weight_bytes`) |

## What to look at

| Question | File |
|---|---|
| What changed visually, at four widths | `shots/before-default-{320,375,768,1280}.jpg`, `shots/after-default-{320,375,768,1280}.jpg` (full page) |
| Forced colours | `shots/after-forced-colors-{320,375,768,1280}.jpg` |
| No-JS / reduced motion | Byte-identical to default at every width: `receipts/mode-equivalence.json` |
| 17/17 card audit (decision beside render) | `receipts/catalogue-17-card-audit.json` |
| Licence / creator check of the Commons originals | `receipts/commons-imageinfo-raw.json` (raw API response; still holds No. 10's original for the record) |
| Browser contract run | `receipts/browser-qa.json` |
| Budgets | `receipts/analysis-budget.json`, `receipts/frontend-delivery-candidate.json` |
| Output / record integrity | `receipts/frontend-integrity-candidate.json` |
| Route parity against current main | `receipts/route-parity.json` |
| Capture tool | `tools/capture.py` |

The `before-*` captures are the unchanged `analysis.html` of main; the later main commits (#410, #413–#423) do not touch the page, `briefs-catalog.css` or any shared asset (see route parity).

## Results

- **Cards:** 17 of 17 rendered, newest first, numbered 17 → 1. 2 photographs (Nos. 8, 9) and 15 Editorial plates. Nos. 1 and 10 `held`, No. 12 `denied`. The browser's rendered media kind equals the resolver's decision for every card.
- **Publication contract:** after removing only the additive nodes (media blocks, credit blocks, the key), body text, 59 links and ids equal current main exactly (`scripts/verify_briefs_catalog.py`, 42 cases, 4 flows). Historical `rel="noopener"` links, "From the former series The PLA Watch" lines and "The PLA Watch:" prefixes are present as before.
- **Forbidden requests:** zero requests for `*-source-image*`, `*-veil*`, `81.cn` or `81cn`.
- **Layout and modes:** no overflow at the verifier's widths; 3:2 frames; default, no-JS, script-failure, reduced-motion, forced-colors and print profiles pass; keyboard journey and hover lift pass.
- **Route parity (candidate build vs fresh main build, same flags):** the published file list gains exactly `assets/geo/region.svg` and the two admitted JPEGs and loses nothing; the only changed bytes are `analysis.html` and `briefs-catalog.css`. `assets/catalogue/admissions.json` and No. 10's derivative are not published. `briefs-catalog.css` and `page-briefs` are used only by `analysis.html`; the rules removed earlier have no other consumer, and `historical-utility.html` takes its ledger styles from the untouched `support.css`.
- **Budgets:** `analysis.html` HTML+CSS 119,440 B (cap 300,000 B; main 101,878 B). JS 3,118 B (cap 10,000 B; unchanged). Corrected page weight including `region.svg`: 223,153 B with both photographs (`analysis-budget.json`). Delivery verifier: 0 failures on 7,589 routes (legacy-routes build). Integrity verifier: all 5,097 record bodies, titles, URLs, dates and compatibility routes verified.
- **Validator:** `scripts/validate_output.py output` passes with the baseline 10 governed warnings (`output/` untouched).
- **Tests (local, macOS, Python 3.9):** full discovered suite, 5,830 tests: 5 failures, 25 errors, 1 skipped, none in this branch's files.
  - **Contract fixed here:** `test_extraction_interface` (24) passes, including the new negative cases for the trigger-path exemption.
  - **Baseline Korea-registry failures, reproduced on a clean `origin/main` checkout and not changed here:** `test_briefs_collection…test_analysis_keeps_every_desk_row_and_adds_collections_apart` (2 reports), `test_preview_prototype…test_non_collecting_desks_are_labelled_and_carry_no_record_count` (korea), `test_indonesia_korea_shadow…test_both_manifests_are_absent_from_production_discovery_and_registry`, `test_desk_capability_execution_plan…test_every_task_is_a_plan_not_a_fake_review`. Each asserts the pre-#415 roster or a row/page for a desk the registry now declares internal-only. They are Korea-governance decisions, so no fictional Korea row or test weakening is added here.
  - **Local-environment only:** `python-docx` is not installed in the local venv (`test_sunday_editor_docx`, `test_sunday_editor_word_return`, and two Sunday owner-release tests; `requirements.txt` has it for CI), and `test_evidence_store` refuses the macOS temp root (21 errors; files untouched by this branch).
  - **Catalogue/relief/production:** `test_catalogue_media` (resolver, committed record, source continuity, hero path), `test_relief_primitives`, `test_briefs_collection` (other tests), `test_frontend_production` pass.

## Limits

- **Image rights.** The Commons receipt verifies licence, creator and description of each Commons *original*. It does not prove the re-encoded local derivatives come from it, and no publisher-site retrieval or independent photo-origin investigation was made. Nos. 8 and 9 were approved by the independent review; No. 10 is held.
- **Delivery accounting.** The delivery verifier's asset list does not count `assets/geo/region.svg` (referenced through `<use>`); `analysis-budget.json` carries the corrected figure and the shared checker is unchanged.
- **Browsers.** Chromium only; forced colours are Playwright's emulation. No Safari, Firefox or screen-reader run. The card focus ring uses `:has()`; without it the link keeps its own outline.
- **Determinism.** The two JPEGs were encoded with Pillow 11.3.0 (`built_with` in the admissions record). JPEG bytes are only guaranteed for that encoder; `requirements.txt` has `Pillow>=10.0.0`, unpinned. The byte-equality test therefore runs only when the installed Pillow equals the recorded version; production is protected by the resolver's SHA-256 checks.
- **Hero.** No real native lead has a cover, so the hero photograph path is exercised only by the synthetic admitted-lead build test, not by the live data.
- **Not exercised.** The draft-review and synthetic-fixture branches beyond their unit/regression tests. `scripts/verify_expressive_frontend.py` is a manual evidence script, not a CI gate, and was not run.
- **Captures** were taken against built trees served on loopback, not a deployed site.

## Reproduce

```bash
.venv/bin/python site/preview/generate_preview.py --out /tmp/cand --snapshot-from-corpus
.venv/bin/python scripts/build_catalogue_media.py --check
.venv/bin/python docs/evidence/briefs-catalogue-3b-2026-10-12/tools/capture.py /tmp/cand after OUT --widths 320,375,768,1280 --modes default,forced-colors
.venv/bin/python scripts/verify_briefs_catalog.py --url … --baseline-url … --released-url … --root /tmp/cand --baseline <main build> --out OUT
```
