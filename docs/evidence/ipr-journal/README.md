# Brief journal — browser and preservation evidence

14 October 2026 owner-review candidate. Real Chromium 147.0.7727.15 renders;
these are screenshots of implemented pages, not illustrations or mockups.
Design/architecture/release scope:
[specification](../../BRIEFS_JOURNAL_DESIGN_SYSTEM_2026-10-14.md).

## Results

- **511 browser checks pass, zero failures.** Eighteen published article routes
  at 320/375/768/1280/1440 with JavaScript, no JavaScript, reduced motion and
  forced colors; print, native fragments, keyboard focus, 200% text enlargement,
  desktop CSS layout enlargement and real Chromium desktop zoom. Five future
  variants are checked at all five widths. Raw facts:
  [browser receipt](browser-receipts.json).
- **114 retained files are unchanged.** Thirty-one protected DB/canonical /
  presentation/material files, plus 83 retained editorial images/metadata,
  fonts, feeds and sitemap files. All eighteen articles retain
  canonical prose/source/citation/author text and links, image paths/alt text,
  provenance and metadata against main `889ef3ed67`:
  [integrity receipt](integrity-receipts.json).
- **Contrast clears AA.** Measured prose, quotation, labels, navigation,
  reference metadata, trace and author text range from 6.8:1 to 12.72:1:
  [contrast receipt](contrast-receipts.json). This measures computed foreground /
  underlying surface colors; the faint decoration was separately inspected.
- **Delivery stays within budget.** Maximum article HTML plus recursively
  linked CSS: 95,871 bytes; maximum executable JS: 5,336 bytes. No external
  dependency. Article CSS gzip increases 920 bytes; disclosure JS gzip decreases
  12 bytes (source grows 14 bytes). No new fonts or documentary assets:
  [performance receipt](performance-receipts.json).
- **Output validator:** passes with ten existing governed warnings. Scope guard
  permits exactly the shared CSS/JS and eighteen article pages changed here;
  no other output delta remains. Sixteen local image files were independently
  decoded. All fourteen closed historical author disclosures are visible in
  Chromium print.

## Published article comparisons

Positions are the same semantic reading locations, at 375 × 900 and
1280 × 900. They are region screenshots so type and navigation are legible.
The pilot contains no Signal; its actual Coverage Snapshot is captured instead.

| Page / location | Desktop before → after | Mobile before → after |
| --- | --- | --- |
| No. 18 central finding / navigation | [before](laos-before-desktop.png) → [after](laos-after-desktop.png) | [before](laos-before-mobile.png) → [after](laos-after-mobile.png) |
| No. 18 mid-article reading | [before](laos-mid-before-desktop.png) → [after](laos-mid-after-desktop.png) | [before](laos-mid-before-mobile.png) → [after](laos-mid-after-mobile.png) |
| No. 18 publisher references | [before](laos-references-before-desktop.png) → [after](laos-references-after-desktop.png) | [before](laos-references-before-mobile.png) → [after](laos-references-after-mobile.png) |
| No. 17 Signal / development / navigation | [before](trident-before-desktop.png) → [after](trident-after-desktop.png) | [before](trident-before-mobile.png) → [after](trident-after-mobile.png) |
| No. 15 native Signal / sections | [before](native-before-desktop.png) → [after](native-after-desktop.png) | [before](native-before-mobile.png) → [after](native-after-mobile.png) |
| No. 15 source trail | [before](native-sources-before-desktop.png) → [after](native-sources-after-desktop.png) | [before](native-sources-before-mobile.png) → [after](native-sources-after-mobile.png) |
| No. 18 documentary hero | [before](laos-hero-before-desktop.png) → [after](laos-hero-after-desktop.png) | [before](laos-hero-before-mobile.png) → [after](laos-hero-after-mobile.png) |
| No. 14 historical Signal / coverage | [before](fourteen-before-desktop.png) → [after](fourteen-after-desktop.png) | [before](fourteen-before-mobile.png) → [after](fourteen-after-mobile.png) |
| No. 1 pilot coverage / opening | [before](pilot-before-desktop.png) → [after](pilot-after-desktop.png) | [before](pilot-before-mobile.png) → [after](pilot-after-mobile.png) |

These final comparisons use reconciled current-main output as the before
baseline. Older historical output contains stale utility media/navigation
labels; the governed renderer supplies its already-defined media-kind, plate
fallback and adjacent-issue presentation. Canonical article/source/author /
citation selectors and image src/alt remain exact.

The screenshots were inspected for typography, paper restraint, navigation,
prose measure, long labels, reference hierarchy and compact mobile behavior.

## Future publication inheritance

Each test article is conspicuously private/synthetic, contains no real new
published issue number, and uses the actual build/template/stylesheet path.
The source-linked case is an unnumbered draft copied from exact approved text;
its presentation review receipt is simulated only. A fixture photograph is
scratch-only and passes the existing media hash gate. These fixtures confer
no rights, editorial approval or public admission.

| Variation | Desktop | Mobile |
| --- | --- | --- |
| Normal Brief with granted photograph | [1280](fixture-journal-photograph-1280.png) | [375](fixture-journal-photograph-375.png) |
| No photograph / plate fallback | [1280](fixture-journal-no-photograph-1280.png) | [375](fixture-journal-no-photograph-375.png) |
| Long cross-desk / long title | [1280](fixture-journal-long-cross-desk-1280.png) | [375](fixture-journal-long-cross-desk-375.png) |
| Short / optional components absent | [1280](fixture-journal-short-1280.png) | [375](fixture-journal-short-375.png) |
| Reviewed source-linked presentation | [1280](fixture-journal-source-linked-1280.png) | [375](fixture-journal-source-linked-375.png) |

## Fallback evidence and limits

[Forced colors](laos-forced-colors.png), [print screenshot](laos-print.png),
[actual A4 print PDF](laos-print.pdf), and
[real 200% desktop browser zoom](laos-browser-200-percent.png).
The browser setting is changed through Chromium's own settings in a disposable
profile. Its measured layout viewport is 640 CSS px inside a 1280px window,
devicePixelRatio 2 and pinch scale 1. No user browser profile is changed.

This gate uses Chromium, not a claim of WebKit/Firefox or a screen-reader
session. Semantic landmarks, one H1, unique IDs, fragment targets and native
keyboard disclosures are checked; accessible labels remain in real markup.
Closed historical print disclosures are explicitly revealed by shared CSS.
No-JS source/evidence links continue to work. At 200% computed text size the
375px and 1280px layouts retain no horizontal overflow. CSS layout zoom is
checked at desktop; doubling a 375px viewport would test 187.5 CSS px, below
the requested 320px floor, rather than an additional supported breakpoint.

Harness corrections are retained here so failed attempts are not called green:
the first capture assumed a nonexistent pilot Signal; a concurrent render was
followed by a missing DOM node during another sweep, so the final gate serves
an immutable generated tree; unloaded lazy footer logos were initially counted
as broken images; and CSS zoom below the supported floor was removed from the
required matrix. Real local image files were independently decoded, eager
images still must load, and actual browser zoom remains required. The final
511-check receipt above is the corrected complete run, not a partial rerun.
The later shared-script compaction is verified by
[90 layout/resize checks plus Escape](compact-script-receipts.json).
Its behavior is unchanged; homepage/archive script budgets are also checked.
Final visual inspection also caught premature photograph painting and a blank
Chromium surface screenshot at actual browser zoom. Capture now waits for fonts,
image decoding and painting; the zoom image uses Chromium's viewport compositor
capture. The measured zoom/reflow checks are unchanged.

## Test and release handoff

Focused stages: 105 native/presentation/collection/frontend tests passed;
the corrected historical/scope/inheritance stage passed 40 tests; the separate
future/presentation/cover stage passed 39 tests. The obsolete inline-style
historical expectation and its former pre-3C transform were removed only after
the governed rerender; current pages now require exact byte equality, alongside
unchanged prose, image/source/credit and citation assertions.

The separate release/media contract stage passes 143 tests. The all-route
delivery stage passes four tests, including every generated route. Initial
full-run findings included the obsolete inline-CSS test and a real hub script
budget overrun, both corrected without raising budgets or weakening media
gates. A concurrent 40-test browser stage timed out after a disclosure click;
the complete corrected stage subsequently passed all 40 tests. The first local
full run also failed 21 custody fixtures because macOS's default temporary
path traverses the `/var` symlink. Using canonical `TMPDIR=/private/tmp` makes
those 21 tests pass without changing the custody guard. The initial full run
was interrupted after diagnosis and is not counted as green; the complete
suite was restarted with the canonical temporary path. That completed attempt
ran 6,257 tests with six errors: one delivery read overlapped a render, one
repository-root rejection saw local virtualenv symlinks first, and four errors
involved the missing existing python-docx requirement. That dependency is now
installed, the runtime is outside the checkout, and rendering is kept separate
from the frozen full run. Affected environment/Word/isolation contracts pass
as a complete 44-test stage. The reconciled article/media/presentation/workflow
stage passes 102 tests, and the refreshed complete browser stage passes all
511 checks. No partial or failed full run is called green.
The new PR-only current-output replay mode and unchanged manual-publication
boundary pass a separate 70-test workflow/contract stage. CI requires an
idempotent committed render; manual release still refuses empty deltas.

The full offline command is `.venv/bin/python -m unittest discover -s tests -t . -v`.
The review PR records its final full result and the authoritative successful
GitHub Actions offline-checks run for the exact current head. A draft/skipped
check is not acceptance. The renderer and validator commands remain those in
the specification; publication needs later owner approval.

Graphify's repository-required refresh completed locally: 18,014 nodes,
37,258 edges, 901 communities. Its ignored graph/report cache is not shipped;
the visual export was skipped by its 5,000-node size limit. Architecture facts
here come from the actual renderer/template audit, not inferred graph edges.
