# Vietnam source-history intake: authenticated Actions to existing reconciler

Phase 0B engineering, October 10, 2026. Tracking: issues #250 and #373. **No source qualification, license, production admission, Day 7 review or publisher network activity is authorized.**

## Why this change is narrow

The repository ALREADY contains scripts/vietnam_ministry_attempt_reconciliation.py, its negative tests and docs/VIETNAM_MINISTRY_ACTIONS_ATTEMPT_RECONCILIATION_2026-10-08.md. That reconciler protects October 7's failed first bootstrap attempt, each family's *different* historical Day 0 target, missing ledgers, partial pushes, failed/recovered slots, wrong source and incomplete expected dates.

The bridge reads real GitHub Actions and pinned Git state into that **existing unchanged reconciliation contract**. It is not a new qualification standard or duplicate reconciler.

## Trust and access

Trusted operator, Python 3.9+, secure local GITHUB_TOKEN with read-only Actions and Contents permissions, plus explicit --approve-github-read:

    python -m scripts.bridge_vietnam_actions_reconciliation --through 2026-10-10 --approve-github-read

Output is metadata-only JSON. Store privately outside the repository if retained. Never put the token or raw publisher source text in logs, issues, PRs, artifact uploads or model prompts.

The API reads only the fixed owner/repository and source-bound orphan branches; it does NOT access any ministry site. It verifies the complete response-page count for a bounded workflow run list; fetches every actual numbered attempt including failed attempts; derives each scheduled logical day from actual UTC start and the declared source cron; and records unknown manual recovery target dates rather than inventing them. The historical Day 0 attempt is represented as a manual run with three **separate** source targets, never one falsely shared date.

It pins and rechecks each source state branch HEAD, reads **every** published ledger JSON and the Day 0 clock from that immutable commit, verifies returned Git blob SHA-1, checks source family/clock, extracts **only** metadata and hands the resulting packet directly to the existing reconciler.

Bounds: review starts October 7 and extends no more than 45 days; up to 120 workflow runs, eight numbered attempts per run, four pages of 30, 60 ledgers per source, size-limited GitHub JSON, no retries. Missing index pages, denied access, moving branches or version inconsistencies fail closed rather than appearing as publisher silence.

## What a result means

A complete GitHub API page listing **does not** prove GitHub never omitted a run, nor that every failed run artifact has been examined. The existing reconciler's conservative status fields remain false for exhaustive history, Git ancestry verification, checkpoint signature, source rights and production. The bridge independently retains per-family source anomaly counts so that the two known MOIT robots MIME findings remain review holds even after a green collector run.

The original October 7 failed Day 0 first attempt remains visible as a warning even if its second attempt successfully published state. Scheduled omissions, failed workflows that wrote no ledger, partial three-family publication and unknown manual recovery target dates remain visible. No country-level or source-family health-green claim is automatically emitted.

## Checks and follow-on

    python -m unittest tests.test_vietnam_authenticated_attempt_bridge -v
    python -m unittest tests.test_vietnam_ministry_attempt_reconciliation -v
    python -m unittest tests.test_vietnam_run_state_attestation -v

All PR checks are offline with fake GitHub envelopes and real existing reconciliation rules. The next actual source-integrity milestone is the October 14 Day 7 observation and human review, only after the genuine scheduled run and separately verified evidence packets. Original-language checking, publisher rights, retention, external model transmission, public display and source/desk promotion remain separate owner decisions.

This PR contains no collector, state, desk registry, production data, editor delivery or deployment changes.
