# IPR Briefs — the cartographic research journal

Owner-review candidate, 14 October 2026. This implements the supplied master
task; it grants no editorial approval, merge, deployment or publication.

## Baseline and audit

The assigned clean worktree was detached at `216dfbb8ba`. Origin is
`VSSpowerlifting/China-Mil-Watch`. Initial main was `0ff01ac9ef`; PR #567 was
open at `3c4b79ffbb`, and Pages was `5b11822585`. The branch incorporated that
dependency without changing its branch. During implementation #567 merged as
`3799e78a83`, with successful offline CI `38593731223`; this branch advanced
to that verified main. There were no pre-existing local changes. PR #566's
separate coastal identity candidate is not incorporated here. Any later
integration must reconcile its palette with this scoped article treatment.

Available tools: Git/GitHub CLI, Python 3.9.6, Playwright and real Chromium
147.0.7727.15, frontend-design skill, read-only parallel audits. No new plugin,
font, frontend dependency or account permission was installed. The absent
`graphify-out/GRAPH_REPORT.md` and worktree-mismatched TokenSave index were not
used as architecture evidence. The local virtual environment reuses installed
packages through an ignored `.pth` file; it is not part of the deliverable.

The existing three body adapters already converge on the current IPR shell:

| Article family | Source and render path | Boundary retained |
| --- | --- | --- |
| Earlier issues 1–14 | canonical historical sidecars → `rerender_pla_watch.py` → `historical_brief_render.py` → `historical-brief.html` | original URLs, publication attribution, citations, manuscript, source trails and author information |
| Native Briefs 15–17 and future Sunday issues | `author_brief.py` / Sunday draft work → reviewed canonical Brief → `brief_collection.brief_view` → production renderer → `brief.html` | fixed standing anatomy, per-desk evidence, readiness and human approval |
| Source-linked Brief 18 and future authorized manuscripts | exact paragraph runs → `brief.html` / `_brief_reading.html`; independently approved `brief-presentation-v1` manifest | exact manuscript fingerprint, five approved Laos headings, central finding, source associations and independent presentation approval |

The historical renderer formerly embedded a second copy of media/navigation
CSS and article-specific presentation rules. These copies competed with the
shared stylesheet and made future visual fixes harder to propagate. Both
historical and native templates repeated the disclosure/navigation scaffold.
Native optional comparisons/coverage could leave empty disclosures. The
sidebar breakpoint (901px) disagreed with JavaScript's wide default (1100px).

## Design specification and implementation

Keep the existing Instrument Serif / Source Serif 4 / Inter stack, self-hosted
fonts, documentary photography and navy `#142E38` hero. Prose reads on clean
`#F3F2EC` paper with ink `#1D2D31`; the new scoped object paper is `#E7EEEA`,
source paper `#EDF0E9` and fine rules `#B4C8C2`. Turquoise `#176C6C` identifies
article structure. Machine-output and real warning colors retain their meaning.

The common `site/preview/briefs.css` owns the reading surface, generous section
spacing, engraved rules, callouts, evidence, source references, author identity,
citation, adjacent issues and all responsive/print/forced-color treatments.
The `--brief-*` tokens are scoped to the article, not the rest of the site.
Historical presentation now lives in a documented adapter block in that same
sheet. No issue-specific stylesheet or JavaScript branch was introduced.

- **Clean reading:** a lightly ruled paper folio inside textured margins;
  prose measure remains below 68 characters. No contour sits beneath prose.
- **Signature objects:** the finding is a sea-glass folio with a restrained
  corner contour, exact quotation and separate source trace. Signal shares
  its material and teal rule, with a lighter, compact label treatment.
- **Section rhythm:** existing headings receive measured space and fine rules;
  existing follow-up sections use a stronger closing rule. No headings,
  numbering, excerpts or fixed-paragraph interruptions are manufactured.
- **Navigation:** `_brief_navigation.html` supplies one semantic native
  disclosure; each body adapter supplies its own approved labels and targets.
  Desktop is sticky; tablet/mobile use a compact disclosure. The shared
  `shell.js` now applies the 901px reading breakpoint and responds to resize.
  No scroll spy was added: native fragments and explicit target/focus feedback
  serve navigation without a second scroll-position state or observer.
- **Closing matter:** source/publisher references, author information, citation
  and adjacent articles have distinct materials and spacing. Original author
  roles, institutional descriptions and historical identity remain verbatim.
- **Optional content:** comparison and coverage disclosures render only when
  their underlying content exists. All approved current articles retain their
  complete text and links; this removes empty controls in sparse future cases.
- **Fallbacks:** small-screen objects fit the reading column; print suppresses
  decoration/navigation and reveals evidence/author disclosure content;
  forced colors uses system colors; no-JS anchors remain native.

Reused assets are `chart-paper.png`, `navy-paper.png`, `chart-shelf.svg` and
`contours-paper.svg`. Existing `ASSET_RECEIPT.json`, `NAVY_RECEIPT.json` and
`PROFILE_RECEIPT.json` remain unchanged. Their curves are abstract decoration,
not geography, elevation or evidence. No new material/media asset was created;
the added PNG/PDF files are browser review evidence only. Existing photographic
pixels, crop settings, credit and licence metadata are unchanged, including
the No. 10 rights hold and No. 12 denial.

## Automatic future inheritance

The production build copies the single stylesheet and renders every admitted
Brief through the same shell, body adapter and navigation macro. The Sunday
pipeline needs no frontend change: editorial review/admission precedes the
same canonical collection/render path. No. 19 or No. 25 inherits the layout
when its own editorial approval is recorded. Missing Signal, term, contributor,
comparison, coverage or photography does not require copied CSS.

`tests/brief_journal_fixtures.py` exports five explicitly private variants via
the actual `generate_preview.build` path, with existing synthetic support and
a narrowly mocked test-only collection seam for an unnumbered source-linked
draft. Exports refuse the repository, its children, ancestors and existing
destinations. Nothing creates a production approval or public issue number.
The scratch photograph uses retained admitted pixels and the real manifest /
derivative hash gate. The source-linked fixture copies exact approved text and
uses a visibly simulated, validated presentation receipt. Default public draft
withholding, synthetic refusal and site-origin exclusion are separately tested.

The five variants are: a normal Brief with a granted photograph, an image-free
Brief with the actual plate fallback, a long cross-desk Brief with a long English
title, a short Brief without optional components, and a source-linked manuscript
with reviewed reading structure. Tampered media, manuscript and presentation
receipts fail the unchanged contracts.

Actual schema limits: native Briefs use fixed standing sections; arbitrary
manuscript-specific headings require the separately governed source-linked
presentation format. Presentation-v1 does not admit arbitrary figures: it can
place an already granted article photograph. An unsupported new desk still
needs registry/evidence admission; visual inheritance does not grant live
status, a source exception or a desk promotion.

## Performance, preservation and verification

Detailed receipts and real browser comparisons are in
[`evidence/ipr-journal`](evidence/ipr-journal/README.md).
Shared article CSS grows from 16,454 to 21,964 bytes (gzip 4,089 → 5,009).
Disclosure JS grows from 372 to 386 bytes (gzip 264 → 252). Historical HTML
loses its duplicated inline stylesheet. The largest of the eighteen article
HTML plus recursive linked CSS deliveries is 94,800 bytes; maximum executable
JS is 5,336 bytes. Both remain inside the existing 120KB / 10KB gates. There
are no external dependencies or new font/media assets. Finding pages reuse the
existing 3,031-byte contour SVG, an additional local request when uncached. These are delivery
measurements, not a claim of faster loading.

Preservation receipts compare 31 protected database/canonical/manuscript /
presentation/material files, and all eighteen articles' complete text/link
semantics, bylines, hero captions, provenance and metadata. All match the
baseline. Historical tests now compare exact regenerated bytes; obsolete
pre-3C normalization was removed. Media/rights and presentation gates were not
weakened. Output validation retains exactly ten governed warnings.

Reproduce with the established runtime:

```sh
.venv/bin/python -m unittest tests.test_brief_journal_future tests.test_brief_presentation tests.test_brief_presentation_integration tests.test_historical_brief_shell tests.test_brief_unified_reading tests.test_brief_cover tests.test_brief_photography tests.test_briefs_output_scope
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python scripts/validate_output.py
.venv/bin/python scripts/guard_briefs_render_scope.py
```

For browser QA, first build a complete private baseline/candidate with
`scripts/build_frontend_review.py --out <new outside-repository directory>`.
Export the five variants using `build_private_fixtures(new_private_path)`.
Then run `scripts/verify_brief_journal.py --root <immutable candidate>
--baseline <baseline> --fixtures <private fixtures> --out <evidence directory>`.
It checks all eighteen routes at 320/375/768/1280/1440, no-JS, reduced-motion,
forced-colors, fragment targets, keyboard focus, print, text/layout enlargement,
and real 200% browser zoom in an isolated Chromium profile.

## Controlled release scope

Review source, tests and evidence before publication. The generated delta is
the shared `briefs.css`, `shell.js`, four native pages and fourteen historical
article pages. The exact output guard adds only Laos and `shell.js` to the
existing explicit Brief release scope. A full renderer also picked up unrelated
Japan/U.S. desk source/output differences and historical source-image copies;
those generated spillovers were returned to HEAD through the existing scope
restoration helper, from the verified initially clean tree.

The PR render-contract job uses `--scope strict --verify-current`: it requires
the committed Brief output to match the governed replay after unrelated spill
is restored. Any scoped difference fails. Manual preview/publication does not
use that flag; the existing strict release command still refuses an empty
publication delta. This distinction supports review of already-regenerated
pages without weakening a publication gate. Two invariant tests cover both
modes and the PR-only workflow boundary.

No database, canonical JSON, approval, feed, sitemap, image, catalogue, public
desk, collection automation or deployment workflow changes belong to this
release. Before later owner-authorized landing/publication, recheck approved
head, complete offline CI, current main and Pages SHA; reconcile concurrent
frontend changes, verify this minimal file set, and use the existing guarded,
non-force deployment process. This task stops at a reviewable PR.
