# Unified Operations Center — explicit opt-in Daily Actions fetch

The explicit opt-in Actions lookup from [PR #276](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/276) was integrated into the feature branch before [PR #275](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/275) merged into `main`. The unified Operations Center remains offline **by default**; this convenience path permits an operator to request the already merged, bounded, GET-only GitHub Actions metadata importer.

## Default remains offline

```sh
python scripts/operations_center_unified.py \
  --json /tmp/ipr-unified-default.json \
  --html /tmp/ipr-unified-default.html
```

**No network requests** are made by that command; it reads the checked-out repository's existing production SQLite database, static shadow declarations and daily marker without changing them. The default display date follows **America/New_York** rather than the runner machine's local timezone or UTC, matching the Daily scheduling guard. A deliberate `--as-of YYYY-MM-DD` overrides the display date without time-traveling the tracked database. UTC run-created dates in `--fetch-daily-utc-day` remain UTC and are explicitly separate.

## Explicit opt-in to real Actions metadata

```sh
python scripts/operations_center_unified.py \
  --fetch-daily-utc-day 2026-10-07 \
  --as-of 2026-10-09 \
  --json /tmp/ipr-unified-with-actions.json \
  --html /tmp/ipr-unified-with-actions.html
```

This performs the same **bounded, read-only GET** against GitHub Actions API used by `scripts/capture_daily_actions_receipts.py`, with a fixed GitHub API host, no redirects, a limited UTC-created-day run history, no run dispatch, and an optional locally configured `GITHUB_TOKEN` for rate limiting. It passes the returned **raw, unsigned metadata** directly through `audit_daily_run_receipts.interpret` and the original Operations Center validation. It never downloads or interprets job logs, claims an editorial right, changes collectors, or sends an email.

The two evidence options are **mutually exclusive**: choose either `--daily-receipts PATH` (operator-supplied JSON, always offline) or `--fetch-daily-utc-day YYYY-MM-DD` (explicit GitHub API GET), not both.

### What the fetched result does NOT establish

The official GitHub jobs API **does not show the scheduling guard's stdout decision**, the stored article count, or the analysis queue. The importer still sets `guard.should_run=null` and `analysis=null`, and it refuses rerun attempts greater than one absent attempt-scoped job provenance. A green Actions job remains `green_workflow_work_not_established` until additional operator-reviewed evidence establishes its guard decision. Cancelled runs with missing job records remain unknown.

Every unified response continues to declare `input_origin_authenticated=false`, `collector_work_certified=false`, `current_analysis_queue_verified=false`, `publisher_silence_established=false`, `source_promotion_authorized=false`, `publication_authorized=false`, and `editor_delivery_authorized=false`. The fetched metadata has no content-authenticating signature after export. It is not a real-time or complete source-publication monitor.

Both requested local files must be **new, distinct and outside the repository**. A failed fetch or malformed receipt refuses the report and does not write either output. A later local file-write error attempts to roll back only the newly created report files (checking original file identity before unlinking), rather than leaving a misleading orphaned JSON file. This is not a transaction against concurrent readers or a promise of atomic two-file publication.

## Verification and integration history

Focused tests verify New York day rollover and DST, the network-free default, explicit invocation of the correct UTC creation date, actual API-metadata-to-classifier-to-dashboard path without fabricated collection claims, offline file mode, mutually exclusive evidence options, future-date rejection and failure without output. CI runs them plus the parent unified suite, then asserts byte-identical tracked production database and published output. The integrated #275 head passed Chromium launch, the full offline repository suite, rendered output validation and tracked database/output preservation before owner merge.

**Integration:** #276 was merged into #275's feature branch, and #275 subsequently merged into `main`. Neither change activated a scheduled monitor or public Operations Center page.
