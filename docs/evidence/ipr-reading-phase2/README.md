# Briefs Phase 2 — complete reading review

Baseline main: `f469801b9c1ddb21e01188b4bfddf4ffa0c913ae` after #570.
Real Chromium 147.0.7727.15; self-hosted fonts loaded; screenshots at DPR 1,
900px viewport height with reduced motion consistently in both phases.
No AI images, HTML mockups, cropped substitutes for full pages, or new editorial
material. [Design decisions and limits](../../BRIEFS_READING_DESIGN_PHASE2_2026-10-14.md).

**Start with the [navigable visual index](index.html).** Full images open at their
native dimensions. Review the entire article, including the long prose between
headings. Owner acceptance remains outstanding.

## Full-page before and after: No. 18

| Viewport | Baseline | Candidate |
| --- | --- | --- |
| 1440 × 900 | [Complete before](laos-before-1440-full.jpg) | [Complete after](laos-after-1440-full.jpg) |
| 1280 × 900 | [Complete before](laos-before-1280-full.jpg) | [Complete after](laos-after-1280-full.jpg) |
| 375 × 900 | [Complete before](laos-before-375-full.jpg) | [Complete after](laos-after-375-full.jpg) |

## Equivalent reading locations

Positions use the same semantic anchor and 112px top offset, or 25/50/75% of
structured prose height. References and closing matter are excluded from that
progress denominator. Viewport-height screenshots supplement full pages.

| Location | Desktop 1440: before → after | Mobile 375: before → after |
| --- | --- | --- |
| Finding / navigation | [before](laos-before-1440-finding.jpg) → [after](laos-after-1440-finding.jpg) | [before](laos-before-375-finding.jpg) → [after](laos-after-375-finding.jpg) |
| First approved section | [before](laos-before-1440-first-section.jpg) → [after](laos-after-1440-first-section.jpg) | [before](laos-before-375-first-section.jpg) → [after](laos-after-375-first-section.jpg) |
| 25% of prose | [before](laos-before-1440-depth-25.jpg) → [after](laos-after-1440-depth-25.jpg) | [before](laos-before-375-depth-25.jpg) → [after](laos-after-375-depth-25.jpg) |
| 50% of prose | [before](laos-before-1440-depth-50.jpg) → [after](laos-after-1440-depth-50.jpg) | [before](laos-before-375-depth-50.jpg) → [after](laos-after-375-depth-50.jpg) |
| 75% of prose | [before](laos-before-1440-depth-75.jpg) → [after](laos-after-1440-depth-75.jpg) | [before](laos-before-375-depth-75.jpg) → [after](laos-after-375-depth-75.jpg) |
| Publisher references | [before](laos-before-1440-references.jpg) → [after](laos-after-1440-references.jpg) | [before](laos-before-375-references.jpg) → [after](laos-after-375-references.jpg) |
| Citation / closing | [before](laos-before-1440-citation.jpg) → [after](laos-after-1440-citation.jpg) | [before](laos-before-375-citation.jpg) → [after](laos-after-375-citation.jpg) |

## Two rendered directions

| Direction | Entire article | Reading detail |
| --- | --- | --- |
| A: open journal, selected and refined | [Full page](exploration-a-laos-1440-full.jpg) | [Section transition](exploration-a-laos-1440-middle.jpg) |
| B: floating headings and composed references, rejected | [Full page](exploration-b-laos-1440-full.jpg) | [Variable line-length detail](exploration-b-laos-1440-middle.jpg) |

[Trial A CSS](exploration-a.css), [trial B CSS](exploration-b.css),
[initial trial geometry](exploration-measurements.json). These are local browser
prototypes applied to the unchanged baseline; only the selected system in
`site/preview/briefs.css` ships. B's irregular line starts and crowded source
columns cost too much reading stability. The selected open page has less
compositional novelty and clearer sustained paragraph flow.

## Other complete reading experiences

| Brief / private fixture | Desktop 1440 | Mobile 375 |
| --- | --- | --- |
| No. 17 — Trident Resolve | [Full page](trident-after-1440-full.jpg) | [Full page](trident-after-375-full.jpg) |
| No. 14 — historical with coverage and original author | [Full page](fourteen-after-1440-full.jpg) | [Full page](fourteen-after-375-full.jpg) |
| No. 1 — oldest publication format | [Full page](pilot-after-1440-full.jpg) | [Full page](pilot-after-375-full.jpg) |
| No. 12 — asset denial, no admitted photograph | [Full page](no-photo-12-after-1440-full.jpg) | All-width browser matrix |
| No. 10 — rights hold retained | [Full page](rights-hold-10-after-1440-full.jpg) | All-width browser matrix |
| Future: granted photograph | [Full page](fixture-journal-photograph-1440-full.jpg) | [Full page](fixture-journal-photograph-375-full.jpg) |
| Future: no photograph | [Full page](fixture-journal-no-photograph-1440-full.jpg) | [Full page](fixture-journal-no-photograph-375-full.jpg) |
| Future: long title and cross-desk prose | [Full page](fixture-journal-long-cross-desk-1440-full.jpg) | [Full page](fixture-journal-long-cross-desk-375-full.jpg) |
| Future: comparatively short, sparse anatomy | [Full page](fixture-journal-short-1440-full.jpg) | [Full page](fixture-journal-short-375-full.jpg) |
| Future: source-linked, exact manuscript | [Full page](fixture-journal-source-linked-1440-full.jpg) | [Full page](fixture-journal-source-linked-375-full.jpg) |

No new evidence component is selected for publication. Existing native
[Signal](trident-signal.jpg) and [source trail](trident-sources.jpg), and the
approved Laos finding/references above, show retained evidence distinctions.
Optional excerpt and photographic placement boundaries are explained in the
design document. Private fixtures remain visibly synthetic/unapproved and are
never part of output, a sitemap or a public issue number.

## Measurements and verification

| Measurement | Baseline | Candidate |
| --- | --- | --- |
| Desktop main track | 704px | 784px |
| Actual usable desktop prose | 630px | 743.77px (+18.1%) |
| Desktop internal side padding | 36px each, plus 1px borders | 0; no borders |
| Desktop nav | 272px panel | 232px open column |
| Gap at 1280 / 1440 | 76.8 / 86.4px | 51.2 / 56px |
| Desktop body / line-height | 19 / 35.15px | 19 / 33.25px |
| Computed prose measure | 62.61ch | 73.91ch (74ch cap) |
| Actual complete line mean / max, including links | 65.17 / 74 characters | 76.47 / 86 characters |
| 375px usable prose / line-height | 331 / 32.4px | 331 / 32.4px |
| 768px usable prose | 643.13px | 691.19px |
| Laos total page height at 1440 | 9,866px | 9,153px |
| Maximum article HTML + recursive CSS | 95,871 bytes | 95,938 bytes |
| Maximum executable JS | 5,336 bytes | 5,336 bytes |

- **511 checks, zero failures:** all eighteen routes and five future fixtures;
  320/375/768/1280/1440, JS/no-JS, reduced motion, forced colors, anchors,
  keyboard focus, print and 200% text/layout/actual browser zoom.
  [Browser receipt](browser-receipts.json).
- **Final print/citation and geometry checks:** the print-only refinement restores
  Source Serif 4 for the finding and a white print ground. Screen geometry is
  rechecked against the captured candidate at all five widths; all eighteen
  print layouts and actual citation clipboard copying in Nos. 17/18 are tested.
  [Final receipt](closing-receipts.json).
- **Actual 200% browser zoom:** Chromium setting in a disposable profile;
  `innerWidth=640`, `devicePixelRatio=2`, `visualViewport.scale=1` from a 1280px
  window. [Viewport capture](laos-browser-200-percent.png).
- **Fallback review:** [forced colors](laos-forced-colors.png),
  [print screenshot](laos-print.png), [complete print PDF](laos-print.pdf).
- **Contrast:** 128 computed text/surface samples, 4.90:1–12.72:1;
  [receipt](contrast-receipts.json). Prose itself is 12.72:1 on clean ivory.
- **Preservation:** all eighteen article HTML files byte-identical to current main;
  [geometry and preservation receipt](reading-receipts.json). [Protected-file receipt](integrity-receipts.json) verifies exact baseline hashes.
  No content, image, admission, approval or database delta. The only generated change is CSS.
- **Budgets:** 22,031-byte article CSS (gzip 5,148), unchanged 120KB/10KB gates;
  [all eighteen page deliveries](delivery-receipts.json).
- **Focused tests:** 103 tests passed in the final focused set, including the unified-output
  contracts; the initial 100-test set also passed.
- **Output validator:** passed before and after regeneration with exactly ten
  governed warnings. No validator or allow-list was relaxed.
- **Complete offline suite and exact-head CI:** final results and run links are
  reported in the PR description/checks. The local full suite was running when
  this visual packet was assembled; this document does not certify a pending
  run. CI must be evaluated on the final PR head.

## Reproduce

Use the repository's installed Python dependencies and real Chromium. This
session used the existing external Python 3.9 runtime because this worktree
has no `.venv`; no runtime path or external dependency is added to the product.
Build the baseline at the exact SHA above, then the candidate through the same
`scripts/build_frontend_review.py --out <new-private-directory>` command.
Export fixtures with `tests.brief_journal_fixtures.build_private_fixtures`.

```sh
python scripts/verify_brief_journal.py --root <candidate> --baseline <baseline> --fixtures <fixtures> --out <matrix-receipts>
python scripts/verify_brief_reading_design.py --root <candidate> --baseline <baseline> --fixtures <fixtures> --out docs/evidence/ipr-reading-phase2
python -m unittest tests.test_brief_unified_reading tests.test_brief_journal_future tests.test_brief_presentation tests.test_brief_presentation_integration tests.test_historical_brief_shell tests.test_brief_cover tests.test_brief_photography tests.test_briefs_output_scope
python -m unittest discover -s tests -t . -v
python scripts/validate_output.py
python scripts/guard_briefs_render_scope.py
```

Retained trial CSS is read by the capture script. Private trees are immutable
while being checked. For a print-only refinement use `--closing-only`, which
also requires exact screen-geometry agreement with the full capture receipt.
No hand editing of public or private article HTML is involved.

[Exact changed-file inventory](changed-files.txt). The HTML index and screenshots
are review artifacts, not new site pages. Nothing here grants publication,
merge or deployment approval.
