# Bounded multi-day Daily Actions metadata capture

The archive’s Daily workflow has five scheduled retry slots each day, and the Operations Center sometimes needs to compare multiple historical days of guard skips, cancellations or reported collection execution. The original metadata importer `scripts/capture_daily_actions_receipts.py` captures exactly **one UTC run-creation day**. This follow-up combines **one to seven** such days into a single canonical, raw, operator-supplied Daily evidence file without changing the importer or the classifier.

## Example — one conservative historical report

```sh
python scripts/capture_daily_actions_window.py \
  --from-utc-day 2026-10-03 \
  --through-utc-day 2026-10-09 \
  > /tmp/ipr-seven-day-actions.json

python scripts/audit_daily_run_receipts.py \
  /tmp/ipr-seven-day-actions.json > /tmp/ipr-seven-day-audit.json
```

After [PR #275](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/275) is merged, that same raw file can be supplied to its unified local Operations Center:

```sh
python scripts/operations_center_unified.py \
  --daily-receipts /tmp/ipr-seven-day-actions.json \
  --html /tmp/ipr-ops-seven-day.html \
  --json /tmp/ipr-ops-seven-day.json
```

All outputs are operator-chosen **outside the repository**; this CLI itself only prints JSON to stdout. **No scheduled monitor is installed.** Invoking it explicitly accesses GitHub's Actions API in **GET-only** mode using the already-reviewed `capture_daily_actions_receipts.capture` transport. An optional preconfigured `GITHUB_TOKEN` can avoid anonymous rate limits; no account credential is written to output. It never triggers a Daily run, a publisher fetch, a model call, an email or a shadow desk.

## Guardrails

- **Range:** inclusive UTC run-creation dates, 1–7 days, not New York display dates and not nominal logical target dates. Dates must be valid, ordered and not in the future.
- **Boundedness:** each daily importer enforces its fixed-host request timeout, response cap, exact workflow identity, single reviewed job shape, and refusal of ambiguous reruns. The combined report is capped at **200 Actions attempts**. Refuse, do not truncate.
- **Completeness:** one failed GitHub API response, unknown/in-progress run, incomplete pagination, changed as-of, duplicate attempt, cross-day attribution, malformed receipt or other inconsistency **fails the entire export** rather than silently returning a six-day report labeled seven days.
- **Input provenance:** no requested date is proof of complete historical Actions coverage. Even if all seven API fetches succeed, the downloaded JSON remains **unsigned, operator-controlled metadata**.
- **Truth:** `guard.should_run` is never guessed from job step conclusions and `analysis` never receives made-up stored-article/queue/backlog metrics. Cancellations with missing job history stay unknown. Green wrappers never prove an actual collector execution.
- **Authority:** `supplied_actions_export_authenticated=false`, `complete_actions_history_established=false`, `production_health_certified=false`, `archive_capture_verified=false`, `analysis_queue_current_state_verified=false`, `publication_authorized=false`, `editor_delivery_authorized=false`, and `no_publications_inferred=false` remain invariant through the existing offline classifier.

## Tests and review

The focused no-network suite uses synthetic injected UTC-day fetchers and verifies ordered composition, a missing middle day, maximum seven days and 200 attempts, invalid/future dates, duplicate attempts, inconsistent as-of timestamps, cross-day attribution and absence of fabricated source authority. It also tests direct CLI help without network. Focused CI verifies byte-for-byte preservation of the tracked production SQLite database and `output/`; the exact-head complete repository suite still needs to pass Chromium launch, offline tests, rendered-output validation and DB/output checks.

This work is independent of the unmerged unified Operations Center and its optional one-day UI fetch. It can be reviewed and merged as a data-export tool without activating a live dashboard. For this reason its PR should remain based on current `main`, not on feature PR #275 or #276.
