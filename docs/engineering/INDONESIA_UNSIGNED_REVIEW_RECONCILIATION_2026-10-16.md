# Indonesia reviewer decisions — offline, unsigned reconciliation

This adds a **separate** private review integrity check stacked on [#756](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/756). It does not modify the #756 branch or its in-progress checks.

## What to reconcile

Source: the genuine pinned 31-original Indonesia workflow receipt, run
`38952228512`, source commit
`0595c6677be24f8f0f33aecb28eec0050e36e8f9`.
The frozen genuine `original_version_manifest.json` has SHA-256
`6dd3b25ad4c69983e6faf555605bd8fce967c0af5cdba35dd3638c0591b514ad`.
The new module **pins this digest in code**, rather than trusting a checksum
provided alongside a changed reviewer worksheet. A new source-version review
cohort requires a reviewed code/update, not silent reuse of old approvals.

Human reviewers can *privately* work from
`review_decisions_UNSIGNED.csv` downloaded from the existing Actions artifact.
It has 31 rows; each immutable source identity/URL/date/disposition/version
digest is non-editable for validation. A reviewer may enter actual name and
UTC review timestamp, specify Indonesian original-language/date/factual checks
as `yes`, `no`, or `unclear`, and describe source-specific link/body/
translation/media use as `allow`, `deny`, or `unclear`. Every edited row
requires a genuine factual reviewer note. These are **unverified assertions**
until separately authenticated against a named reviewer and actual evidence.

## Offline invocation

Only from a private location containing the downloaded two metadata-only files:

```bash
python -m scripts.reconcile_indonesia_unsigned_reviews \
  --manifest /private/indonesia/original_version_manifest.json \
  --worksheet /private/indonesia/review_decisions_UNSIGNED.csv
```

The command prints only aggregate coverage and machine-authentication **false**
flags; it never prints names, reviewer notes, source URLs or original bodies.
It rejects altered versions/URLs/dates, duplicate or missing identities,
incomplete decision fields, invalid dates, fabricated authoritative manifest
digests and any attempt to grant rights to the documented geography-
contradictory Yonif 880 source. This is a locally executed verification step,
not a GitHub Actions step that uploads completed private reviewer data.

## Limits

The source version hashes are anchored to the real Oct 14 original Git
snapshot but this reconciliation script does **not** independently reload
original bytes or reverify publisher transport. Even 30 filled positive rows
would remain **unverified claims**. It cannot authenticate human identity,
review proof, licensing, seven genuine collection slots, rejected Actions
attempts or final editorial/publication decisions.

No importer, `pla_watch.db`, `output/`, `gh-pages`, registry, source shadow
Git or regional renderer is changed. No signature is invented, and the
known 31st geographic hold remains mandatory. The separate source-release
writer from #749 remains HOLD-only until independently trusted human+
Actions evidence exists. This tool is not the trusted validator callback.
