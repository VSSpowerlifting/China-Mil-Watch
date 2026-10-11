# Phase 0 execution | Vietnam scheduled run and immutable source state

Prepared October 10, 2026. Scope: **source-family operational observation only**, not a collection authorization or desk qualification.

This is the first bounded engineering implementation from issue #373 and #250. It reuses the existing source manifest/workflow binding audit, the shared logical date resolver, and each pre-existing Vietnam orphan state branch. It neither duplicates the collector nor adds a registry, status flag, public route or new scheduled job.

## Exactly three existing source families

- vn_mps_foreign_affairs_vi — shadow/vietnam-mps-foreign-affairs
- vn_moit_energy_vi — shadow/vietnam-moit-energy
- vn_moit_foundational_industry_vi — shadow/vietnam-moit-foundational-industry

The actual configuration audit identifies the workflow file, the logical cron and each state branch. The complete declaration inventory still has **16** source families, including manual/research-only lanes, but this first attestor examines only three existing scheduled Vietnam ministry lanes. Never market it as a universal all-desk health scanner.

## Operator-only GitHub read (no publisher network)

From a trusted private checkout, only after deliberately allowing repository metadata GETs:

    python -m scripts.attest_vietnam_run_state --as-of 2026-10-10 --approve-github-read

The operator may redirect the resulting **source-metadata-only** JSON to a protected location outside the repository. An optional locally provided GITHUB_TOKEN supports REST permissions and rate limits. No token, original publisher article, archive database, media or capture is printed or retained.

The script reads only the fixed GitHub repository over HTTPS. Per source, it checks the actual branch ref twice (detecting a moving HEAD); the state/ledger directory from the first pinned SHA; the latest immutable ledger and source-specific clock with Git blob SHA verification; and the **precise** Actions run ID/attempt referenced in that ledger. It verifies successful scheduled event, correct bound workflow path, UTC start, exact nominal logical collection day, source slug, clock, bounded collection status and source anomalies. The normal cap is 18 GETs across the three families. Any refusal, bad JSON, wrong branch/workflow, changed HEAD, run mismatch or invalid blob aborts the affirmative report. No publisher request, re-run, workflow dispatch, new remote state or collector code is involved.

The explicit --as-of date **limits the latest observed state** and rejects the future; this tool does not search historical commits. For a Day 7/14/30 checkpoint, use the formal reviewer against the *exact historical commit* from that day, not this latest-ledger attestor.

## What a reported success means

verified_run_and_state_observation means the latest pinned source ledger and one completed GitHub Actions attempt genuinely agree about source family, workflow, run, logical day and result **for that observation**. It is not a claim that every expected daily job ran, that all article versions were reviewed or that the publisher was fully covered.

needs_review means the observed source ledger has a declared anomaly (including the existing MOIT robots MIME findings) or that the three-source cohort cannot be matched cleanly. Zero publications in a bounded listing never proves ministry-wide silence.

Every result independently keeps false: complete historical Actions attempt audit, full chained state continuity, original-language human source verification, publisher rights review, private AI/publication permission, signed 7/14/30 checkpoint and production/promotion approval. A green CI badge cannot set those fields.

## Next Stage 0B — complete logical-slot evidence

The next separate PR under issue #250 should enumerate **all actual GitHub workflow attempts**, including failures and cancellations which never wrote a ledger, and reconcile them with every pinned source-family slot in a bounded interval. Detect delayed nominal dates, missing ledgers, partial three-branch pushes, duplicate logical days, failed attempts followed by manual recovery and Git SHA drift. The existing operations overlay is currently candidate-only; do not turn it into green desk health until source-specific original/API/state provenance is independently demonstrated.

## Exact offline safety proof

    python -m unittest tests.test_vietnam_run_state_attestation -v

Offline tests use fake GitHub REST envelopes without network: correct current source bindings, valid same-run cohort, source anomalies, altered blob SHA, wrong issuer, moved HEAD, wrong logical day, wrong workflow/event/attempt, bad source clock, missing UTC, fake future date and refused CLI access without explicit network permission.

This code does **not** change production records, source manifests, clock/review evidence, private article contents, main database, website, deployment, country desk status or editor correspondence. Vietnam remains a research desk.
