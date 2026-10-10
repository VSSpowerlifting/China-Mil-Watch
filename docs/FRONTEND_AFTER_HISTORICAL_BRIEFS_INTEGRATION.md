# Integration candidate: public surface #314 after historical Briefs #287

This integration branch was built from current `main` **after #287 and #315 merged**, not by replacing the current repository with old frontend files. It carries the owned decorative CSS, local fonts, visual assets, renderer and generated non-historical pages from #314, while preserving today's operations/relevance/collection fixes.

## Conflict resolution and provenance

The October 9 three-way object tree audit located **17 distinct same-path conflicting blobs** between the original frontend base and current main: `analysis/analyzer.py`, 14 historical HTML files, `site/preview/templates/base.html`, and `tests/test_pla_watch_reading_ergonomics.py`.

- Current `main` wins for `analysis/analyzer.py`, `config.py`, `pipeline.py` and all new source receipt/retry/tool workflow tests. We do **not** remove current-main files missing from #314's older branch.
- All 14 current IPR-shell historical article pages were retained exactly from merged #287 at the initial transplant. Their sidecar JSONs, feed, author/source links, Signal Veil evidence, image receipts and route identities are unchanged.
- `base.html` starts with #287's root-aware `root_path` override, adds #314's owned terrain/visual `data-surface` / `data-route` and `enrichment.css`, all using **`{{ root }}`**. Historical render already passes `brief={}`; it therefore automatically receives the scoped `data-surface="brief"`.
- The reading-ergonomics suite retains #287's tests and the #316 local CSS/WOFF2 fixture and fallback-font interceptions. Both source-domain wrapping and genuine fallback verification remain mandatory.
- Other #314 sources/assets and generated pages were transplanted by existing Git object IDs, not lossy text reconstruction. Do not merge the old #314 branch over this candidate.

## HTML-only re-render

Run `python scripts/render_historical_frontend_integration.py --write`
to deterministically update **only** the 14 historical HTML files from original
JSON sidecars and the merged #287 renderer. The script fails closed unless
there are exactly fourteen valid, nonempty source sidecars and expected
original provenance, source-trail, and new root-aware stylesheet references.

`--check` compares all 14 files byte-for-byte to current Jinja rendering.
No model provider calls, scraping, cover derivation, asset editing, SQLite writes
or publication are involved.

The temporary integration-branch-only CI render job regenerates and commits
only these 14 HTML paths, after independently enforcing that `pla_watch.db`,
published sidecar JSON, feed, and tracked source files were not edited.
This never writes to `main` or triggers a deployment.

## Release gates

This is a **draft integration candidate**, not approval to deploy. Exact-head
full offline, browser, site-render and archive-preservation CI must pass
after the regenerated historical HTML commit. Independently review mobile/
desktop visuals and preservation of all 14 original issue identities,
attributions, source trails and existing URL identities. Merge **one**
consolidated frontend candidate to main, not both #314 and this branch.

If the site generator produces additional differences, reconcile against the
current main source of truth; no full archive backfill or DB reprocessing.
