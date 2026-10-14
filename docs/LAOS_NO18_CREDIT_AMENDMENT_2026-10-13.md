# Laos Brief No. 18 — October 13, 2026 credit amendment

## Scope and owner authorization

The owner reviewed the proposed co-author cards and byline in the editorial conversation and explicitly authorized the attribution changes (“yes thats authorization”). The exact changes and provenance were publicly documented in [the PR #514 amendment note](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/514#issuecomment-6153456275).

This is an **attribution/biographical-metadata correction to an already published Brief**, not a new investigation or a fresh grant of source reuse rights. Benjamin Yang remains the lead author and the publication's Founder & Director of Research and Editorial. Dylan Tanzi is now a co-author of this Brief and retains the IPR position Lead Research Analyst. The byline becomes **Benjamin Yang and Dylan Tanzi**. Evergreen biographies and contact links change accordingly.

## Immutable original approval preserved

- Original approval: [PR #485 owner final acceptance](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/485#issuecomment-6138538619)
- Original source-rights exception: [PR #485 owner policy ruling](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/485#issuecomment-6138481576)
- Original full editorial fingerprint: `ec3da971c0c9ab0ec21e2688b971d419c4a5650a690e49bad380c56763a0e500`
- New metadata-inclusive fingerprint: `3ff586938e7680a014a7b6b6c60449327c9d07dcb12b2f6845fc0d3749a44c57`
- Unchanged approved source manuscript SHA-256: `43ec5cc44ba724401235d976c73af6485566026d24114146878e0152cce3d0c1`
- Unchanged: original **11 article paragraphs**, **seven publisher references**, source-link associations and rights limitations, Brief number **18**, October 4–10 reporting window, original approval date and publisher identity.

The source-linked validator binds the **whole sidecar**, including credits, to the exact approved version. The credit correction therefore updates the metadata-inclusive fingerprint in the `editorial_review` and `policy_ruling` receipts, and points their current exact-version reference to the later owner-authorization note above. This is **not** a claim that the original source review was repeated. The original review and rights evidence remain linked here rather than being silently rewritten out of history.

## Follow-through gate

Before treating the correction as released, verify that article paragraphs, source URLs, original language, license/rights basis, and historical files remain byte-identical; regenerate output and validate the rendered cards, byline, feed, citation, Analysis and homepage surfaces; run applicable tests and exact-head CI; only then merge and deploy. Independently verify live output, taking the documented Pages race (#346) into account.

## Longer-term engineering improvement

Split **manuscript/source-rights** attestation from **editorial metadata** attestation, rather than making routine biographies/credit fixes invalidate substantive source approvals. Retain an explicit editor authorization for actual authorship changes; reserve full evidence and rights review for changes to the research or licensing basis. This amendment documents a scoped exception using existing controls; it does not relax the source-rights policy or bypass CI.
