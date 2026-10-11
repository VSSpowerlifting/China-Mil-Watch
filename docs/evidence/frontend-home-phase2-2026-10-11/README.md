# Phase 2 evidence: homepage relief (2026-10-11)

This phase covers **the homepage only**. It links the Phase 1 relief primitives into `site/preview/templates/home.html` and into no other template.
- **Authority:** the owner's Phase 2 home kickoff and the lean execution addendum (2026-10-11).
- **Base:** `main` at `39b40bb7adbd998dc60e0cae886582fa37f7b43b`. It was later rebased onto the then-current `origin/main`, and the PR records the final head.
- **Not authorized:** merge or deploy. Independent review is required.
- **Unchanged:** nothing under `output/`, the database, sidecars, the collector, publication text or translation data changes.

## What changed

| Path | Change |
|---|---|
| `site/preview/templates/home.html` | **Imports and stylesheet.** Imports `_relief.html` and links `relief.css` before `home.css`.<br>**Finder.** Gains `rl-finder`, and its input and button gain `.tactile`.<br>**Record cards.** The latest-4 list uses a home-only `home_card` macro. It has the `record_row` fields and order, plus the source-stated `<time>` and the desk emblem. `record_row` is untouched.<br>**Analysis band.** Gains `rl-analysis`, the lead Brief's own desk emblems, and the Singapore Strait figure **only when the lead Brief's `desks` include `singapore`**.<br>**Desk list.** Each `desks if d.record_count` card begins with that desk's silhouette (`aria-hidden`). The heading carries no emblems. |
| `site/preview/home.css` | Adds 42 lines of page layout for the relief surfaces. It adds no `box-shadow`, and its lift comes only from `relief.css`.<br>**Review revision.** Record geography plates are 96 px on desktop, 64 px at ≤600 px and 52 px at ≤380 px.<br>Both analysis planes are lighter navy paper with a hairline edge and a hard offset under-plate drawn by `::before` (no shadow). Crimson tops the Brief plane only.<br>A static border spine runs from the desks heading through the scope link and coverage note to a rule, with a short drop to each desk card's silhouette. It maps to `CanvasText` in forced colours.<br>Adds the reduced-motion press fix, `[data-surface] .home-page :is(.btn,button):not(:disabled):active{transform:none}`. |
| `site/preview/generate_preview.py` | **Production build.** Copies `relief.css` plus `RELIEF_PRODUCTION_ASSETS = (assets/geo/emblems.svg, assets/geo/strait.svg)` byte-for-byte. Exposes the receipt's symbol boxes to templates.<br>**Excluded from production.** Flags, glyphs, `region.svg`, the receipt and `gallery-relief.html`. These remain `--gallery`-only. |
| `tests/test_relief_primitives.py` | **Isolation test updated, not deleted.** The Phase 1 isolation test becomes a positive, page-scoped allowlist: `home.html` may reference only `relief.css`, `_relief.html`, `rl-finder`, `rl-card` and `rl-analysis`, and only the `emblem` and `strait` macros.<br>**Unchanged guards.** Stylesheets and both base templates stay out, and the B1 six-surface shadow audit is unchanged.<br>**New tests.** Production-asset tests check byte identity, sprite allowlist, `<use>` resolution, link order and `aria-hidden`. They also check that the timeline branch survives beside the strait. A strait-scope test shows that a China-only lead Brief gets no strait. The Phase 1 gallery build tests are kept. The file now has 28 tests. |

Zero JavaScript was added: page scripts remain `intro.js` and `shell.js` at 31,792 B, byte-identical.

## Route, content, rights and asset ledger

- **Routes:** the delivery verifier checked 7,520 routes on both builds with 0 failures.
  - Only `index.html` changed its budget row (`receipts/delivery-summary.json`).
  - In the production manifest diff, only `index.html` and `home.css` changed.
  - Three files were added: `relief.css`, `assets/geo/emblems.svg` and `assets/geo/strait.svg`.
- **Records:** the integrity verifier checked all 5,065 records with 0 failures (`receipts/after-integrity.json`).
- **Homepage content parity.** The following are identical before and after (`receipts/*-checks.json`):
  - the latest-4 record ids, titles and order
  - "A record to explore"
  - the form: `archive.html`, GET `q`
  - the title-only caption
  - the Brief/timeline branch
  - the desk names, counts and coverage note
  - the hero and photograph credits
  - the script list
- **Image rights:** the naval hero credit (U.S. Navy, public domain) and the Maritime Cooperation photo credit with "Source and credit / Context, not evidence" are unchanged.
  - The new geometry is Natural Earth (public domain) via world-atlas 2.0.2 (ISC), per `site/assets/geo/geo.receipt.json`.
  - The strait caption states that the figure is decorative and not a navigation or boundary chart.
- **Desks:** emblems appear only for desks with public records in the snapshot. No shadow, research or blocked desk is shown as collecting.

| Asset | Bytes | SHA-256 (first 12) |
|---|---|---|
| `relief.css` | 4,031 | `66568ea0d45d` |
| `assets/geo/emblems.svg` | 15,306 | `a22b88871fbf` |
| `assets/geo/strait.svg` | 20,170 | `f1a4ff03d0ec` |

## Budget (`index.html`, delivery verifier)

| Measure | Baseline | Candidate | Cap |
|---|---|---|---|
| HTML (`index.html`) | 14,840 | 17,017 | — |
| `home.css` | 14,921 | 19,810 | — |
| HTML + CSS | 67,795 | 78,892 | 300,000 delivery / 120,000 integrity |
| JS | 11,940 | 11,940 | 12,000 |
| SVG sprites fetched via `<use>` | 0 | 35,476 | not counted by `asset_bytes` (2,618,405 both) |

## Browser evidence

The tool is `tools/home_evidence.py`, which uses Playwright Chromium from `.venv`. It runs 32 checks against the scratch builds (`--snapshot-from-corpus --legacy-routes`).
- **Baseline:** 2 failures, both pre-existing.
  - Desk links in `row-side` are 19 px tall, below the 24 px target.
  - The reduced-motion press still translates 2 px (`matrix(1,0,0,1,0,2)`).
- **Candidate:** 0 failures.
  - Press under `reduce` is `none`; under `no-preference` it still moves 2 px.
  - The hero credit is not occluded.
  - Contrast on new text runs from 5.15 to 13.73.
  - `html.no-anim` runs no relief animation.
  - Forced colours, print, keyboard focus, no-JS and 200% zoom are all exercised.

The `81.cn` record photographs are masked in every shot. The magenta masks are an evidence-only screenshot overlay and are not part of the page.

**Review revision.** The shots were retaken at the revised head with the same 32 checks and 0 failures.
- **320 px:** page `scrollWidth` is 320, and record plates are 52 px. The plates' only overhang is the decorative under-plate offset, with no text overflow.
- **Content parity with the first candidate:** every check field is identical except desk-link heights, which are taller because each card now holds a silhouette.

| Section | Before | After |
|---|---|---|
| Finder 375/768/1280 | `shots/before-finder-*.jpg` | `shots/after-finder-*.jpg` |
| Records 320/375/768/1280 | `shots/before-records-*.jpg` | `shots/after-records-*.jpg` |
| Analysis 320/375/768/1280 | `shots/before-analysis-*.jpg` | `shots/after-analysis-*.jpg` |
| Photo Brief 375/768/1280 | `shots/before-photo-brief-*.jpg` | `shots/after-photo-brief-*.jpg` |
| Desks 320/375/768/1280 | `shots/before-desks-*.jpg` | `shots/after-desks-*.jpg` |
| Full page 375/1280 | `shots/before-full-*.jpg` | `shots/after-full-*.jpg` |
| Focus (input, button) | `shots/before-focus-*.jpg` | `shots/after-focus-*.jpg` |
| Forced colours | `shots/before-forced-colors-1280.jpg` | `shots/after-forced-colors-{375,1280}.jpg` |
| No-JS / reduced motion / 200% zoom | — | `shots/after-nojs-375.jpg`, `shots/after-zoom200-full.jpg` |

## Verifiers that are not green

- **`verify_expressive_frontend.py`:** 17 of 234 checks fail on candidate-vs-baseline. The identical 17 also fail on baseline-vs-baseline (`receipts/expressive-summary.json`).
  - All 17 are 404s on legacy `the-pla-watch/` routes, which the scratch preview build does not emit.
  - These are **errors matched to the baseline**, not passes.
- **The full `unittest discover`:** fails on baseline main with 6 failures and 42 errors. These are sandbox and worktree guards (`test_state_is_refused_inside_worktree…`, evidence-store `unsafe_store_root`, and similar).
  - The candidate has 1 failure and 21 errors. Both sets are classified in `receipts/unittest-summary.txt`.

## Deviations and risks

- **Strait figure is conditional.**
  - It appears only for a lead Brief whose desks include Singapore.
  - Otherwise the band shows just the Brief's own desk emblems, and with no lead it shows nothing.
  - No fixed relief appears on unrelated content.
- **Analysis-band emblems are the lead Brief's own `desks`**, the countries it analyses, not a coverage claim. A Brief listing a non-collecting desk would show that desk's emblem there; today's lead lists China and Singapore.
- **`rl-settles` dropped** from the second analysis plane. The timeline/Briefs column keeps its existing layout.
- **Desk-list cards carry their own silhouette.** It is inside the existing link, so link targets, names, counts and the coverage note are unchanged. Desks without public records get no card and no silhouette.
- **Overlap with open PRs.** PRs #314 and #323 touch `home.html`, `generate_preview.py` and `base.html`. None of their changes are included here, and a later rebase of either will conflict.
- **Untested browsers.** Only Chromium was exercised. Safari, Firefox and real assistive technology were not.
