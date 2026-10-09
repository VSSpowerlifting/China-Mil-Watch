# Frontend implementation review — 9 October 2026

Implementation candidate for the owner-requested production instruction in
`IPR_Frontend_Production_Checkpoint.md`. Review this PR before merge. No merge,
deployment, collection run or editorial release is part of this handoff.

## Sources and scope

Initial production base: `2524d11c2f12ae29ff1f05da3f6dd6ca26ef7359`.
Current main `0e1b6b753cba66067391d886da31499b9d072206` was integrated
before the final full-suite run; its concurrent operations/editorial tooling is
preserved and has no frontend or corpus changes.
The reviewed visual source is local design checkpoint
`8cb2f23f450785db8044606ec9bbba1d284287fd`, whose immutable implementation
reference is `cdae0862a96e9e6739d08f03b05dcd2fd181b266` in
`design/frontend-2026-10-08/`. Its refinement bundle supplied the visual target;
its frozen 4,930-record snapshot and HTML-transforming builder are not shipped.
Original MNTN/Area/third-concept files were unavailable; exact fidelity to those
unseen references is not claimed.

PR #181 was inspected open at head
`657e9f2644b50a4c9d98d68455124784e59f22b4`. Its governed timeline prerequisite
was applied to the current main base in separate commit `b80b3e4`; current
Vietnam/source changes remain intact. The frontend change includes that
prerequisite rather than depending on an unmerged branch at runtime.
The Maritime Cooperation timeline remains an unpublished draft with unchanged
SHA-256 `0e922865856addb24786b088ee925c35ebab3809659fb252462a66090c9da332`.
Ordinary production builds emit no timeline route, library, tab or backlinks
while there is no separately approved timeline. Private review remains noindex,
without canonicals, feed or sitemap, and is refused by the deployment validator.

## Result

The selected lowercase `ipr` identity, Instrument Serif display type, Inter UI
and Source Serif 4 reading text are integrated into the production Jinja/view
model system. Home leads with realistic Pacific photography and record search;
the archive keeps its newest 50 server-rendered records, lazy title index,
filters, history and pagination; record pages lead with their title and source;
Briefs use the unchanged natural-color source frame; timeline reading begins
before the long context and date tracks, now native disclosures.
Supporting routes share the same shell. Published historical weekly pages and
the rollback renderer keep their original identity and markup.

Counts and public desk membership come from the current governed 8 October
snapshot (4,980 records). Native approved Brief trails now contribute exact-URL
record backlinks and archive `trail_ids` together. Drafts and external evidence
remain outside that membership. An unscreened machine state no longer asserts
that no human judgment exists when an approved Brief cites the record.

Shared CSS and route CSS replace the prototype overrides. The dependency gate
counts every linked local sheet, recursive import and executable script/module,
including inline scripts; missing dependencies fail. Timeline detail and library
retain the 120,000-byte HTML/CSS and 10,000-byte JS gates. Archive retains its
300,000-byte allowance. The existing optional home arrival intro retains its
separate 12,000-byte aggregate script cap; other routes retain 10,000 bytes.

Photographs use full-frame responsive WebP derivatives with JPEG fallback,
explicit dimensions and lazy loading below the fold. Original assets, credits,
license metadata and editorial sidecars are unchanged. Source and output hashes
are recorded in `site/assets/frontend/DELIVERY.json`; the photo view model and
validator bind delivered bytes to that source. The selected logo's supplied
source/derivative receipt is preserved under `site/assets/identity/selected-ipr/`.
Self-hosted Latin WOFF2 faces, source URLs, hashes and OFL licenses are under
`site/assets/fonts/`; CJK uses system fonts. The share card uses the selected
identity. No runtime request to Google Fonts is required.

## Verification and evidence

The review evidence and final measurements are in
[frontend-production-2026-10-09](frontend-production-2026-10-09/).
The final complete offline suite ran 4,874 tests in 849.487 seconds and passed.
Its one existing skip is the frozen prototype release-readiness metadata check
(declared 26 August/3,574 records versus current 8 October/4,980). The production
candidate uses the current explicit governed snapshot; no browser classes were
skipped. Command and results are in `TESTS.json` in the evidence directory.

The browser receipt covers 75 cases (five routes × five widths × default,
no-JS and reduced motion) and 13 reader flows: English/Chinese title search,
desk filtering and Back, approved trails, pagination/focus/history, empty
results, source-citation copy, native Brief anchors, Brief credit/navigation,
timeline keyboard evidence/tracks, menu Escape/focus, forced colors, printed closed Brief evidence and natural JPEG fallback delivery
in fresh public/private render trees, plus unbroken freshness dates at 320px.
Separate tests retain the screenshot-difference glyph contrast method and its
4.5:1 body / 3:1 large-type floors. Reading scrims were strengthened where the
new photograph's bright details failed those measurements.

The integrity receipt checks all record headlines, original titles, stored
bodies, summaries, source URLs, dates, provenance and citation payloads in their
own rendered elements. It compares the exact six-field archive index rows and
checks approved native relations and previously existing compatibility routes.
Complete local CSS/JS delivery was also measured for every one of the 5,122
changed HTML routes: all fit their applicable budgets. The largest record is
110,284 bytes; the archive and Desks directory use the 300,000-byte index
allowance. No canonical DB, Brief JSON, historical sidecar, desk registry, shadow record,
collector or workflow is changed by the frontend implementation.

ResourceTiming receipts measure actual cold/cached local navigation, loaded
font/image/CSS/JS bytes and document timing. They are loopback Chromium results;
they do not establish production network latency, CDN compression or deployed
cache headers. Cached local navigations report zero transferred bytes.
No deployment or public-page verification is claimed.

Old September assertions for compass chrome, masked Ocean Signal geometry,
numbered/register ordering and a six-analyzed-record homepage were superseded
by the explicitly reviewed October direction. Their evidence and language
contracts, source immutability, accessibility floors and publication gates are
retained or retargeted. Tests are not skipped to bypass the new design.

## Reproduce

Use the repository's normal `.venv`; this Mac used the existing read-only
runtime at `/Users/benjaminyang/pla-watch/.venv/bin/python` because this managed
worktree had no environment. No production dependency or framework was added.

```sh
.venv/bin/python site/render.py
.venv/bin/python scripts/validate_output.py
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python site/render.py --review-timeline timelines/maritime-cooperation-2026.json --out /tmp/ipr-timeline-review
.venv/bin/python scripts/verify_frontend_integrity.py --public output --private /tmp/ipr-timeline-review --receipt /tmp/ipr-integrity.json
# Serve output and the separate private tree over loopback, then:
.venv/bin/python scripts/verify_frontend_candidate.py --public-url http://127.0.0.1:8765 --timeline-url http://127.0.0.1:8766 --out preview/frontend-verification
```

`site/render.py --out` alone is a fresh renderer tree; a full candidate also
needs the normal `publish()` exchange's carried historical/data assets.
The tracked candidate here is produced only by the normal default production
renderer, never by hand editing output. Source and generated output changes
are separate commits. Optional asset rebuild commands are
`build_frontend_assets.py` (Pillow), `build_frontend_fonts.py` (FontTools/Brotli,
networked upstream sources) and `build_frontend_social_card.py` (Playwright).
Rebuilding fonts may receive newer upstream bytes; review receipts and licenses.

Remaining action: owner implementation review and separate decisions on merge
and deployment. The timeline's exact editorial content needs its own approval
before it can be published.
