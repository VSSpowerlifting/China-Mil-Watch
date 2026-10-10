# Owner-approved frontend landing — 10 October 2026

The owner visually approved the existing 9ade candidate and authorized commit,
source-driven output regeneration, a final-head checked PR and merge. No design
refinement is included. The portable review export remains locally available.

## Base and overlap reconciliation

The approved detached candidate began at `0487bfc0480bd94a9d4471f927c449c506f07cbf`.
Its actual initial inventory was 29 source/handoff files plus 71 evidence files,
not the checkpoint's 18-file subset. All 29 source snapshots matched the approved
portable export before committing. Source/evidence commit is `07b5672b2`.

Current main `f25378fba` adds only the generated MINDEF source-text audit (#331):
its script, tests and findings are preserved by merging main into this branch.
The release owns `codex/ipr-approved-sitewide-frontend-20261010`; it does not
modify another task's branch or select an older frontend as the baseline.

PR #314 (`a5c1e7e81`) and its reconciled successor #323 (`cb70da7f50944d50b058cd205c5f9c08d09729e5`)
remain open and unmerged. Their older enrichment CSS, shell markup, native Brief
hero changes and extra shared scripting are superseded by the visually approved
source candidate. They are not cherry-picked or merged. Their operational and
historical baseline requirements are already represented by current main and
preserved here. The previously reused navy tile/builder/receipt remain the exact
approved source assets. #323's extra font kit, workflows and legacy-shell tests
belong to its different candidate and are not represented as checks on this
release. The current repository's complete PR offline gate must pass on this
release's own final head before merge.

## Regeneration and preservation

The production command was `site/render.py`, followed by
`scripts/rerender_pla_watch.py --no-covers`, using the existing read-only virtual
environment interpreter. Output is a separate commit. No generated file was
hand-edited; no evidence, database, sidecar or publication status was changed.

Every existing file of the approved private build matches regenerated output
byte-for-byte except `sitemap.xml`. The normal production publish path includes
the 17 historical URLs in the sitemap and orders the homepage first. It also
writes the compatibility redirect `signals.html` → `methodology.html`, omitted
by the fresh private render. This exactly explains 7,462 production routes versus
7,461 private routes; no editorial route was removed. The redirect and publish
mapping remain unchanged from main. All approved HTML, CSS, JS, image/font assets
and canonical public data match the approved candidate. Forty-three pinned
protected files remain byte-identical: database, native Briefs and timeline
sidecars, desk registry/geography, selected identity, historical sidecars/feed.
The timeline remains draft, with no new public timeline route or link.

## Fresh checks

Receipts are in `evidence/frontend-landing-2026-10-10/`:

- All 7,462 routes: zero governed HTML/CSS/JS budget failures.
- Full 5,020-record evidence integrity: zero failures.
- Deploy validator: pass, the same ten governed warnings.
- 234 Chromium + 98 Firefox/WebKit + four native pointer/clipboard/static-state
  checks repeated against regenerated output: all 336 pass.
- Approved build parity and protected fingerprints: pass.

The earlier integrated run reported 5,280 tests, zero failures/errors and one
existing skip. That is historical candidate evidence, not final-head CI. Final
PR CI is required before merge, including all offline tests, the output validator
and tracked database/output immutability checks. A passing shallow CI may disclose
Git-history-dependent replay skips; these must be reported separately from the
executed checks. Real Safari/iOS/touch hardware, real screen-reader sessions and
deployed/CDN behavior remain outside the completed local checks.

No separate deployment workflow is dispatched. After merge, deployment status
is reported from existing Actions evidence only. The original handoff records
actual design resources and the offline screenshot gallery; no new design
resource or third-party runtime was introduced in this landing phase.
