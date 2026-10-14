# Coastal identity — full-site release preview and handoff

> **Release status, 14 October 2026:** Coastal identity PR #566 is merged,
> and the normal daily production run #38606036281 already rendered, validated,
> committed and deployed the palette. All five active source, generated and
> published stylesheets were independently confirmed byte-identical; public
> homepage, Analysis, No. 18 Laos, record and historical Brief output likewise
> match GitHub Pages. **Do not trigger this preview to publish that completed
> release.** The process below is retained as a guarded option for *future*
> cosmetic output releases, not an outstanding task. Manual-preview PR #573
> corrected escaped Actions expressions; draft PR #574 adds optional fidelity
> checks. Neither workflow is a substitute for the daily publisher.

This is a **review-only** mechanism. Source changes in palette PR #566 do not
become live on merge: GitHub Pages deploys the committed generated `output/`,
not the CSS/templates under `site/preview/`. The existing Briefs release
guard cannot approve sitewide modifications; do not broaden it to make this pass.

## Preflight, after PR #566 merges

Obtain the exact latest reviewed `main` SHA. On the main branch, run the
manual GitHub Action **IPR sitewide cosmetic release — preview only** and enter
it as `reviewed_main_sha`. The job fails if main has moved.

The job checks out that exact main revision with read-only credentials, checks
the database baseline, installs existing render dependencies, executes the
existing `scripts.run_briefs_render_release --scope report-only` for historical
and IPR rendering, and inventories every tracked/staged/untracked/ignored output
change. No source acquisition, model invocation, git push, commit, or deployment
step is included.

The inventory classifies root CSS paths as `css-review`, known generated
homepage/Analysis/record/Brief markup as `html-manual-review`, and unknown
routes, new media, data, feeds, historical canonical JSON, assets, or symlinks
as `blocked-noncosmetic`. It also fails if the database changes, a WAL/SHM
sidecar appears, or any file outside `output/` changes.

The sitewide receipt also attests SHA-256 parity between every changed
coastal stylesheet and its corresponding first-party source. For changed
HTML pages, it compares the newly generated document against committed
`HEAD` via the stdlib HTML parser; textual content, byline/citation links,
photograph references and alt text, metadata and inline scripts must remain
identical. CSS presentation-only changes are permitted for review. Newly
generated HTML routes have no baseline and are blocked in a cosmetic release.
These checks do not establish visual suitability or waive manuscript review.

Even a successful run is **not a release approval**. Review all reported
HTML changes and historical/canonical content, verify article paragraphs,
approved presentation/author cards, links, image attributions, desk status,
feed/sitemap parity and licensed media. A blocked change may require a
separate scoped release; never suppress the guard to achieve green CI.

## Only after owner approval

Prepare a **separate** generated-output PR from the latest main, using the
approved production renderer, preserving carried historical assets. Review its
exact diff, run `scripts/validate_output.py` and exact-head CI, and merge
only after independent approval. Then run the existing manual
`Deploy Rendered Output` workflow from latest main and inspect the live
homepage, Analysis, representative source record, native/historical Brief and
approved Laos No. 18.

No automatic output commit or Pages deployment is authorized by this preview
workflow. The manual daily pipeline is **not** the palette release tool—it
also collects/analyzes and may mutate the database.
