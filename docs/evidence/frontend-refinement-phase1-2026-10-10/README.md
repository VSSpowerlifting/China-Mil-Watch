# Phase 1 evidence: shared relief, motion and geo primitives (2026-10-10)

The ticket is `docs/FRONTEND_REFINEMENT_PHASE0_2026-10-10.md` §13, built under
the owner rulings recorded in `DECISION_LOG.md` (2026-10-10 B1, B9, B3/B4, B2
and B5). Phase 1 is **infrastructure only**. It redesigns no live page and
changes no production output, and nothing it adds is linked from a production
template. The screenshots are review material, not visual sign-off.

- **Base:** `main` at `51769ae3e82e038be1853fa15a55dc2840941fc7`
- **Branch:** `claude/ipr-phase1-frontend-9316d6`

## What was built

| Path | What it is |
|---|---|
| `site/preview/relief.css` | 4,031 B (cap 4,096). Three lift tokens on the six B1 surfaces only. `.tactile` rest, hover, focus-visible and press states. `rl-draw` / `rl-rise` / `rl-settle` motion, gated three ways. Forced-colours and print overrides. |
| `site/preview/templates/_relief.html` | Macros `emblem`, `strait`, `region_plate`, `flag`, `glyph`, `glyph_for`. Every SVG is `aria-hidden="true" focusable="false"` and uses an external `<use href>`. Every flag `<img>` has `alt=""` beside its text label. |
| `scripts/build_geo_assets.py` | A deterministic Natural Earth builder that reuses `scripts/desk_map.py`'s decoder, simplifier and Miller projection. Inputs are passed as arguments and never fetched. |
| `site/assets/geo/{emblems,strait,region}.svg` and `geo.receipt.json` | The generated sprites, plus a receipt of input SHA-256s, parameters, output hashes and licence. The receipt records no time. |
| `site/assets/flags/{cn,sg,jp,vn,us}.svg` and `LICENSE` | flag-icons 7.3.2, MIT, © 2013 Panayiotis Lipiridis. The licence travels with the files. |
| `site/assets/glyphs/sources.svg` | Six source-family glyphs drawn for IPR: newspaper, ministry, agency, journal, portal and feed. They are generic forms, never a seal, crest, flag, masthead or logo. |
| `site/preview/templates/gallery-relief.html` | An unpublished specimen page rendered only with `--gallery`, using real corpus data. It holds the raised finder, record cards with emblems, desk plates with flags, the scope panel, a Brief print card on an Editorial plate, the analysis plane and the glyph legend. `gallery.html` gains only a link to it. |
| `tests/test_relief_primitives.py` | 20 tests, listed under Tests below. |

## Deviations from the §13 wording

All of these are recorded in `DECISION_LOG.md` (2026-10-11):

- **Three sprites instead of one `emblems.svg`.**
  - The files are `emblems.svg` (15.3 KB), `strait.svg` (20.2 KB) and `region.svg` (49.8 KB), so a page fetches only the geometry it shows.
  - The receipt is `geo.receipt.json`.
- **No separate `water_lines(symbol)` macro.** Water lines are baked into each emblem symbol and coloured through `--rl-w1`…`--rl-w5`, which cross into the `<use>` tree where page class selectors cannot reach. `--rl-draw` drives the draw motion.
- **`flag()` and `emblem()` take a desk slug, not an ISO code.** The US Indo-Pacific desk maps to the US flag and to a **Hawaii** emblem, never the sovereign US outline.
- **The relief specimens live on `gallery-relief.html`, not inside `gallery.html`.**
  - With them inline, `gallery.html` measured 123,320 B of HTML + CSS against the verifier's 120,000 B cap for a non-index page.
  - The cap was not raised. The specimens moved to their own page instead.
- **The press state darkens; it does not cast an inset shadow.**
  - Production `surfaces.css:20` already sinks every `[data-surface]` button 2 px on `:active`, and that rule outranks a 1 px relief rule. The dead 1 px rule was removed.
  - That production press ignores `prefers-reduced-motion`. This is pre-existing behaviour, noted and not changed here (out of scope).

## Gates (§13) and results

| Gate | Result | Receipt |
|---|---|---|
| Production build byte-identical to the fresh-main baseline | **Identical.** 7,608 files, the same manifest hash, including `index.html`, `archive.html`, `desks.html` and every `briefs/` page | `receipts/prod-identity.txt` |
| Gallery build drift | Adds exactly `gallery-relief.html`, `relief.css`, five flags + `LICENSE`, three geo sprites and `glyphs/sources.svg`. `gallery.html` +60 B (the nav link). Nothing else changes. | `receipts/gallery-vs-baseline.diff` |
| `validate_output.py` | Passed, with the same 10 governed warnings as baseline, line for line | below |
| `verify_frontend_delivery.py` (gallery build) | 7,522 routes (baseline 7,521, +`gallery-relief.html`), **0 failures** | `receipts/delivery-summary.json` |
| `verify_frontend_integrity.py --public` | rc 0. All 5,065 record bodies, titles, source URLs, dates and compatibility routes verified | — |
| `verify_expressive_frontend.py --before main --after candidate` | 234 checks, **0 failures**, 52 screenshots | `receipts/expressive-browser-checks.json` |
| Focused tests: `test_relief_primitives`, `test_preview_prototype`, `test_desk_map` | 512 tests **OK** (1 skipped), rc 0. Baseline was 492, and the 20 new relief tests make 512 | — |
| Full suite (`unittest discover`) | 5,638 tests, which is baseline 5,618 plus 20, with 21 errors and 1 skip. The errors are exactly the baseline's 21 `test_evidence_store` `unsafe_store_root` sandbox errors, matched by test ID. The baseline's one flaky veil `ConnectionResetError` did not recur. There are no failures and no new errors. | — |
| Gallery browser evidence at 375 / 768 / 1280, plus reduced motion, forced colours and no-JS | 27 checks, **0 failures**, 12 captures | `receipts/browser-checks.json`, `shots/` |

The expressive verifier's screenshots are **not committed**: its route set
includes Brief pages that show 81.cn imagery. Only the receipt is kept, with
local URLs replaced by placeholders.

### Validator warnings

These are unchanged from baseline:

- three weekly-sidecar date and significance warnings (2026-05-09, -16, -23) and the pilot span
- three missing LinkedIn files
- one 2026-07-18 → 08-01 cadence gap

## Geometry, licences and budgets

**Geometry:**

- `receipts/geometry-vs-phase0.json`: every built desk emblem, the strait and the regional plate has **byte-identical path data and seats** to the Phase 0 study (`studies/emblems.json`, `studies/plates.json`).
- Emblem viewBoxes gain a 9-unit margin so the outer water line is not clipped.
- Phase 0's `hainan` study was not built: it is not in the §13 asset list.

**Inputs:**

- world-atlas 2.0.2 (ISC), from Natural Earth (public domain).
- Input SHA-256s are in `site/assets/geo/geo.receipt.json` and match Phase 0's.
- Rebuilding twice gives identical bytes (tested).

**Flags:**

- The five files are byte-identical to the Phase 0 `studies/flags.json` copies of flag-icons 7.3.2.
- `site/assets/flags/LICENSE` is byte-identical to `studies/LICENSE-flag-icons.txt`.
- Flag red is not the crimson analysis signal. Desk status is always separate text.

**Glyphs:** IPR-drawn, with no third-party source.

**Measured transfer** on `gallery-relief.html`, from the browser:

| Resource | Size |
|---|---|
| `relief.css` | 4,031 B |
| `emblems.svg` | 15,306 B |
| `strait.svg` | 20,170 B |
| `region.svg` | 49,760 B |
| `sources.svg` | 2,181 B |
| flags | 470–889 B each |

The page's HTML + CSS is 91,580 B against the 120,000 B cap.

## Browser checks (`receipts/browser-checks.json`)

Chromium via Playwright, against a disposable `--gallery` build of this commit.

- **Overflow and errors:** no horizontal overflow, console errors or failed requests at 375, 768 or 1280.
- **Normal motion:**
  - the scroll-driven draw is assigned to the emblems, and the analysis copy settles
  - card hover rises and gains lift 2
  - the Brief print plate scales
  - press sinks the control (2 px, inherited) and darkens it, with no box shadow
- **Reduced motion:** no animation and no transforms. The lift still appears on hover.
- **Keyboard:** every `.tactile` control shows a solid 2 px outline. A focused card link raises its card's lift through `:focus-within`.
- **Forced colours (375, 1280):**
  - no lifts
  - geographic art hidden
  - flags and text kept
  - borders carry the structure
- **No JS (375, 1280):** the finished state, with no animation.
  - The captures are byte-identical to the reduced-motion captures, by design.
- **Accessibility and rights:**
  - every relief SVG is `aria-hidden` and unfocusable
  - the only `<img>`s are flags, each with `alt=""`
  - there are no background photographs
  - every control has an accessible name
  - **no request to 81.cn**
- **Limitations:** Chromium only. Safari, Firefox and real assistive technology were not exercised.

## Reproduce

```bash
# from the repo root, with the repo .venv
python scripts/build_geo_assets.py <countries-50m.json> <countries-10m.json>   # rebuilds site/assets/geo/
cd site/preview && python generate_preview.py --out <scratch>/gallery --snapshot-from-corpus --legacy-routes --gallery
python -m http.server 8781 --directory <scratch>/gallery &
python -I docs/evidence/frontend-refinement-phase1-2026-10-10/tools/browser_evidence.py http://127.0.0.1:8781/gallery-relief.html <scratch>/shots
```

The tool writes PNG captures and a receipt that records the served URL.

The committed copies were post-processed for size and privacy:

- PNGs became JPEG q82 with `sips` (7.3 MB to 4.9 MB).
- `browser-checks.json` lists the `.jpg` names.
- Its local URL is replaced with a placeholder.

No check result was edited. `expressive-browser-checks.json` received the same URL substitution only.

**Production identity:**

- The comparison uses `site/render.py`'s own build function, `generate_preview.build(..., legacy_routes=True)` (`site/render.py:306`), with `gallery` left at its default `False`.
- The new geo, flag and glyph assets and `relief.css` are copied only inside that function's `if gallery:` block.
- Production's own asset copy allowlists `fonts`, `identity/selected-ipr` and `frontend`, so the new folders never reach `output/`.

1. Build without `--gallery` on `main` and on this branch.
2. Hash both with `find . -type f | LC_ALL=C sort | xargs shasum -a 256`.
3. Compare the two manifests.

## Rights audit

- Every capture in `shots/` was viewed before commit.
- They show only the Relief specimen page: Natural Earth outlines, flag-icons flags, IPR glyphs and corpus text.
- There are **no photographs**: no Brief photography and no 81.cn / PLA Daily imagery.
- Per B2 = B and B5 = B, Phase 1 touches no Brief image, catalogue or No. 12 surface.
- Text receipts carry no local paths or secrets.
