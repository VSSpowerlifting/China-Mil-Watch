# BIS official-link production readback — independent evidence stage

This workflow is a read-only follow-up to held production release PR #711.
A successful release workflow is a signal to investigate, not itself proof
that a public visitor can see matching metadata. The readback workflow requires
a successful genuine workflow_run event of the exact named BIS release job.

It reads the current main SQLite production database, generated U.S. Desk HTML,
the exact file checked out from the gh-pages Git branch, and the public HTTPS
response from indopacificrecord.org. It requires:

- at least one BIS official metadata row in the authenticated typed table;
- exact BIS identity, canonical first-party URL, posting date, neutral label and
  safe outbound link semantics on the published page;
- ten or more USCC and Treasury links and nine PACOM static links, with
  PACOM access blocked and DVIDS collection paused;
- byte-identical main U.S. page, gh-pages Git U.S. page and actual HTTPS page,
  after a bounded six-request propagation window;
- no source bodies, original publisher titles or translations;
- no database, source Git, main or Pages mutation by this verifier.

The on-PR job uses only synthetic SQLite and HTML and **cannot** count a real
scheduled source observation, source qualification, Pages deployment or
attested original publisher document. The genuine run cannot execute until
the BIS metadata release job is merged and completes after a verified
scheduled BIS collector event. The website readback may fail if CDN
propagation exceeds its bounded window; such a failure is a truthful HOLD,
not a license to overwrite Pages or fake observed coverage.

The publisher homepage digest was collected but the complete original page
was not retained for independent rehashing. Even a successful HTTPS metadata
readback is **not** a BIS original-body archive, reuse permission, substantive
editorial approval, or comprehensive institutional history.
