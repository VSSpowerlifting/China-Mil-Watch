# Frontend Phase 4A — light Desks map: implementation review

**Status:** review candidate, not published or visually certified. PR #504; parent #498. Baseline: owner-approved Phase 0 `docs/FRONTEND_REFINEMENT_PHASE0_2026-10-10.md` (B9 / requirements 8–9). This Phase 0 owner direction supersedes the dark geographic chart in the previously approved sitewide landing; a `DECISION_LOG.md` review entry remains to be appended after PR readiness (a large-file GitHub write returned a rule-validation timeout).

## Source and status invariants

- The map uses the existing Natural Earth 1:50m geometry and Miller projection, from `scripts/desk_map.py` and `desks/geography.json`. No boundaries, original institutional-seat coordinates or corpus facts were changed.
- Every placed country uses the registry's current collection state. Filling a country does **not** imply that private shadow originals are admitted. The U.S. Indo-Pacific reference desk has a **Hawaii institution seat but no U.S. country fill**, preserving the sovereign/operational distinction.
- Indonesia remains an unplaced status-only public entry in the ordinary desk list. We refuse to infer its location or production status from shadow data.
- Full-colour flags (including Korean and Philippine) are vendored 4×3 assets from flag-icons v7.3.2 under the already existing MIT `site/assets/flags/LICENSE`. Flags denote identity, never collection status.
- The UI uses existing `--lift-1` / `--lift-2` tokens through page-local `relief.css`, not a new shadow family. `desk-map.js` is unchanged.
- The current P4A work changes no production DB, source entries, collector, admission gates, sidecars or generated `output/`.

## Layout decision: seven placed desks instead of five

The Phase 0 photographic study used five placed desks and showed cards surrounding the map at 900–1280px. The live registry has **seven placed** desks; direct reuse risks collision. P4A therefore keeps the light map and fully visible card register at ordinary sizes, deferring absolute anchored cards to widths of at least 1480px (subject to the browser B10 gate).

A conservative 1280px-wide map-box calculation (paper plate **232×265px**, larger than the Phase 0 card study) detected an overlap between Japan and Korea in their inherited positions. Adjusting the **Korea card display** from an east-pointing leader to an above-seat leader at 126.98° E, 43° N clears Japan without moving Seoul's actual seat. Static rectangle pairs now have zero positive-area overlaps. This is **not a substitute** for browser-measured text rectangles, leader/label checks or the actual zoom/mobile layout.

## Remaining gates before approval

1. Exact-head PR CI and a scratch site render, including parsing of the Desks Jinja template, existing source/corpus boundary tests, and the full offline suite.
2. Browser verification at **320, 375, 768, 900, 1100, 1280, 1480 and 1600 px**. Reject any clipped plate, colliding map label or card, missing hit target, inaccessible keyboard route or zoom overflow. Check JS disabled, reduced motion, forced colours and print.
3. Confirm no extra page or corpus changes in a clean scratch build; preserve all country status notes and publisher-link boundaries.
4. Owner visual approval of the final screenshot set. Separately implement P4B scope panels with full source limitations and permitted run-health binding.
5. Merge only after review; public release has an independent gate. **No output render, Pages deployment or source promotion from this PR.**
