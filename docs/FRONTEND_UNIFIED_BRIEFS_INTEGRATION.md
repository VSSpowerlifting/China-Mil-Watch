# October 9 frontend visual integration after unified Briefs

This independent review candidate is built from `main` after #287's
single-publication historical Briefs merge and the #309–#315 operational
safeguards. It is a **replacement candidate** for #314, not a merge of
#314's stale feature branch into the default branch.

## Provenance-preserving integration

- Use the approved #314 first-seen frontend feature blobs for source CSS,
  static decorative materials, renderer and approved native output.
- Retain main's current analysis, retry, source-gap, configuration and
  collection files, rather than replacing them with copies from #314's
  older base. No task models, costs or caps change.
- Retain #287's current historical renderer, source sidecars, existing
  author/veil/source citations, site routes and canonical titles.
- Every historical output HTML body comes from #287's latest approved
  page, with **only** a two-level `../../enrichment.css` link and
  `data-surface="brief" data-route="analysis.html"` on the body. The
  historical publication content, original attribution, URL and feed
  are not regenerated from the old PLA Watch shell.
- Integrate `base.html` by preserving `root_path` handling and the
  hidden-empty-freshness rule, while carrying the terrain macro, scoped
  CSS, surface attributes, and interactive frontend behavior from #314.
- Retain existing legacy browser-test coverage, but repair the fixture to
  serve actual checked-in historical WOFF2 and CSS assets; preserve the
  warm-vs-blocked font test instead of ignoring it.
- Include owner-created material provenance receipts and artwork
  unchanged; no source photos or flags are invented.
- Preserve `pla_watch.db`, article JSON, canonical feed, issue author
  links and original source trails.

## Required review gates

1. Exact-head focused tests prove all fourteen historical pages match
   the current historical Jinja renderer **byte-for-byte** and retain
   published identity, citations, media and the new CSS assets.
2. Offline browser, reduced-motion, no-JS, keyboard, all publication
   families, historic material/pixel/receipt and full suite success.
3. Full output validator and tracked database/published-output
   immutability during CI, independent of expected committed page changes.
4. Human visual review of desktop/mobile/no-script and historical
   Briefs before any owner-approved merge/deploy.

The full previous #314 CI success applies only to its earlier head
and **is not the release gate for this reconciled candidate**.
