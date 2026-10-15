# IPR Briefs — cartographic accent pass

Design baseline: approved PR #588 head
`d5c3ca5169bf10eb7685897c234b06452c3592e5`. This pass updates the same PR.
The approved Phase 2 proportions, typography, open ivory surface and source
styling are retained. These captures are local Chromium renders, not production
verification or evidence graphics. No merge or deployment is authorized.

Start with the [visual review index](index.html). Full images open at native
resolution. The before images are the approved Phase 2 design, rather than
its earlier main-branch baseline.

## Selected treatment

**A — angular open profile.** Two fine, unfilled paths in muted turquoise and
slate sit at the right of existing whitespace before alternate section openings.
A wider decorative field marks the transition to sources. The profile is abstract:
it represents no location, elevation, distance, event, military activity or
measurement. It has no axes, labels, markers or data binding.

The small asymmetry gives the page a recognizable editorial signature without
adding another component to read. Unlike the existing closed contour fields,
the new motif consists of open horizontal cross-sections. The source transition
is its most complete expression. Finding and Signal areas retain their approved
treatment; citation boxes and author matter acquire no further ornament.

The ornament occupies existing section gaps, outside all rendered text. It is
not beneath a paragraph or heading, and does not consume layout space. At desktop
it is 184 × 28px (240 × 28px at sources); at mobile it reduces to 112 × 18px
(160 × 20px at sources). Print and forced colors hide it. Empty CSS pseudo-elements
supply no accessible text, accept no pointer events, and introduce no focus target,
request, asset file, script, animation or font.

## Three actual rendered directions

| Direction | Laos: complete / detail | Trident: complete / detail | Decision |
| --- | --- | --- | --- |
| A — angular open profile | [full](direction-a-laos-full.jpg) / [detail](direction-a-laos-section.jpg) | [full](direction-a-trident-full.jpg) / [detail](direction-a-trident-section.jpg) | Selected: distinct from existing contours; irregular without chart-like steps. |
| B — stepped shelf | [full](direction-b-laos-full.jpg) / [detail](direction-b-laos-section.jpg) | [full](direction-b-trident-full.jpg) / [detail](direction-b-trident-section.jpg) | Rejected: orthogonal steps suggest a chart or operational interface. |
| C — soft double ridge | [full](direction-c-laos-full.jpg) / [detail](direction-c-laos-section.jpg) | [full](direction-c-trident-full.jpg) / [detail](direction-c-trident-section.jpg) | Rejected: too close to the existing smooth contour vocabulary. |

All three use identical placement, dimensions and opacity. Their retained
[CSS A](direction-a.css), [CSS B](direction-b.css), [CSS C](direction-c.css)
are review prototypes applied to the approved baseline in Chromium. Only A is
included in the shared production `site/preview/briefs.css`.

## Required before/after and compatibility views

| Page | Desktop 1440px | Mobile 375px |
| --- | --- | --- |
| Laos — approved Phase 2 before | [full page](laos-before-1440-full.jpg) | [full page](laos-before-375-full.jpg) |
| Laos — selected after | [full page](laos-after-1440-full.jpg) | [full page](laos-after-375-full.jpg) |
| Trident Resolve — native, after | [full page](trident-after-1440-full.jpg) | [full page](trident-after-375-full.jpg) |
| No. 14 — historical, after | [full page](historical-after-1440-full.jpg) | [full page](historical-after-375-full.jpg) |
| No. 16 — no photograph, after | [full page](no-photo-after-1440-full.jpg) | [full page](no-photo-after-375-full.jpg) |
| Laos — section-transition clearance | [close-up](laos-section-1440.jpg) | [close-up](laos-section-375.jpg) |
| Laos — source-transition clearance | [close-up](laos-sources-1440.jpg) | [close-up](laos-sources-375.jpg) |

## Verification

**189 checks passed, zero failures**, including 90 exact geometry/clearance
comparisons, 36 comparisons with disclosures open, 36 print/forced-color checks,
25 future-fixture checks and two real citation clipboard copies. Results are
recorded in [accent receipts](accent-receipts.json). A [negative control](negative-controls.json)
deliberately moved ornament over prose: the check detected 12 text intersections
versus zero in the selected treatment. **117 focused tests passed** in 104.874s.
The initial focused run overlapped production rendering and failed one delivery
check while a copied icon was temporarily absent. The complete 117-test set was
rerun after rendering, with no missing dependency or failure. No guard was changed.

The initial clearance pass counted rectangles inside closed disclosures as visible
text. The corrected check filters actual visibility and separately opens disclosures
to verify their content too.

The reproducible check compares every paragraph, heading, link, image, button, main column and
navigation rectangle and their font, margin, padding and colors against the
approved baseline at 320, 375, 768, 1280 and 1440px. It also compares page height.
Every decorative pseudo-element's bounding box is tested against every rendered
text-node line rectangle, with viewport containment and pointer transparency.
Five existing private future fixtures use the same candidate CSS; none is
published or assigned a new issue number.

[Protected-file and delivery receipts](integrity-delivery-receipts.json) compare
all eighteen HTML pages and the existing 114-file protected inventory with the
exact approved Git baseline, and measure all eighteen article deliveries. Maximum HTML+CSS is 97,523 bytes; executable
JavaScript remains 5,336 bytes. The shared CSS is 23,616 bytes (+1,585).
The sole generated delta is `output/briefs.css`, produced by `site/render.py`.
No template, manuscript, sidecar, presentation manifest, approval, image admission,
rights/custody record, database, feed, sitemap, source trail or safeguard changes.

**511 additional browser checks passed**, zero failures: all eighteen issues and
five future fixtures, JS/no-JS, reduced motion, forced colors, keyboard focus,
anchors, print, 200% text/layout and real Chromium 200% zoom. See the
[full matrix receipt](browser-matrix-receipts.json). The output validator passed
before and after rendering with exactly ten governed warnings; the scope guard
permits only the generated CSS delta. Final-head CI results are reported in the PR
description. Existing 120KB HTML+CSS and 10KB JS
budgets and the ten-warning validator baseline are unchanged. The PR checks
remain authoritative for their exact head; this document grants no release approval.

## Reproduce

Use the repository's Python/Playwright dependencies and installed Chromium.
Build an immutable private tree at the exact baseline above with
`scripts/build_frontend_review.py --out <baseline>`. Restore the candidate source,
then render `<candidate>` through the same command. Export existing private
fixtures with `tests.brief_journal_fixtures.build_private_fixtures`.

```sh
python scripts/verify_brief_cartographic_accents.py --root <candidate> --baseline <baseline> --fixtures <fixtures> --out docs/evidence/ipr-cartographic-accents
python scripts/verify_brief_journal.py --root <candidate> --baseline <baseline> --fixtures <fixtures-with-candidate-css> --out <temporary-matrix-receipts>
python -m unittest tests.test_brief_unified_reading tests.test_brief_journal_future tests.test_brief_presentation tests.test_brief_presentation_integration tests.test_historical_brief_shell tests.test_brief_cover tests.test_brief_photography tests.test_briefs_output_scope tests.test_briefs_render_release_contract tests.test_briefs_enrichment
python scripts/validate_output.py
python scripts/guard_briefs_render_scope.py
```

The accent verifier intercepts only the private fixtures' CSS request; it never
modifies fixture HTML. This session reused the existing external Python 3.9
runtime because this worktree has no `.venv`; no runtime dependency is added.

[Exact follow-up changed-file inventory](changed-files.txt).
