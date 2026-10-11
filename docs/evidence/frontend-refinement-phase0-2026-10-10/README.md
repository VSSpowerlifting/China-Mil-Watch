# Phase 0 evidence: frontend expressive refinement (2026-10-10)

This folder holds disposable studies and receipts. It is **not production code**, and nothing here is linked from the site.

The governing write-up is `docs/FRONTEND_REFINEMENT_PHASE0_2026-10-10.md`.

| Folder | Contents |
|---|---|
| `shots/` | 1280 / 900 / 375 JPG captures, before (`*-base-*`, `home-before-*`) and after (`*-study-*`, `home-after-*`), with variants `home-stack-*` (B1b) and `home-forced-*` (forced colors) |
| `studies/` | CSS and JS overlays scoped to `html.study`, injected at review time into a served `output/` build. Also the study data: `emblems.json`, `plates.json`, `flags.json`, `desk-sources.json`, glyph SVGs. `old-map.css` is the pre-`07b5672b2b` light map (R7). |
| `tools/` | `capture.py` (Playwright capture), `emblems.py` / `plates.py` (Natural Earth builders), `glyphs.py`, `veil_coverage.py` (read-only audit), `evidence.py` |
| `plans/` | Capture plans, with paths relative to this folder |
| `reports/` | Capture reports (`errors: []`) and the validator baseline receipt |

**How to reproduce:**

- **Captures:** start the Browser-pane server `pla-watch-site` (port 8765, serving `output/`), then run `tools/capture.py` from this folder with the repo `.venv` Python.
- **Veil audit:** `python -I tools/veil_coverage.py <repo-root>`. It only reads.
- **Emblems and plates:** `python -I tools/emblems.py <repo> <countries-50m.json> <countries-10m.json> <out.json>` and `python -I tools/plates.py <repo> <countries-50m.json> <out.json>`. The inputs are world-atlas 2.0.2 (ISC; Natural Earth, public domain):
  - `countries-50m.json`: SHA-256 `04342cdc1e3016bcd7db1630de95684d67b79fe3c8c460321e87aef469502394`
  - `countries-10m.json`: SHA-256 `3bc6f1d367a9bcec479841bae0e76092f512838411d0cef124e92eec4db45f79`

  The rebuild is deterministic, and the 1:50m rebuild matches the committed `site/preview/templates/_desk_map_geo.svg`.

**Rights:**

- PLA Daily / 81.cn imagery is **excluded** from this folder. The Brief catalogue captures use a withheld placeholder, and the 375 px home band captures are cropped above the Maritime Cooperation photograph.
- The flag SVGs inside `studies/flags.json` are from flag-icons 7.3.2 (MIT, © 2013 Panayiotis Lipiridis). The licence text is in `studies/LICENSE-flag-icons.txt` and must travel with any copy.
- The source-family glyphs were drawn for IPR.

**Superseded study behaviour (owner rulings, 2026-10-10):**

- `studies/overlay-briefs.js` has a default mode that places 81.cn veils on Briefs catalogue cards. B2 = B rejects that: only the `html.study-no81` mode (withheld placeholder, Editorial plates) reflects the approved direction. The committed catalogue-list captures were taken in `study-no81` mode; the hero captures show no catalogue images.
- The same overlay holds No. 12 on a plate "for a credit check". B5 = B supersedes that hold: the existing No. 12 image stays where it already appears, still unresolved for attribution and rights, and is not added to new surfaces.
- These are design choices, not visual sign-off. The screenshots still need independent review.

**Public-repo audit (2026-10-10):** every capture, including the bottoms of the tall 375 px shots, was viewed before commit. No PLA Daily / 81.cn photograph appears. Visible photographs are the public-domain U.S. Navy hero and the curated Nos. 8 (Japan MOD, CC BY 4.0), 9 (NASA, public domain) and 10 (CRS, public domain), with credits shown. Text files carry no local paths, secrets or embedded images.
