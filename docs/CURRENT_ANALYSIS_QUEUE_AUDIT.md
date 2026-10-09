# Current analysis queue: read-only source-attributed audit

Addresses the **current database counting** requirement in [issue #268](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/268), separately from the historical GitHub Actions attempt/step logs and from the Operations Center's source-health overlays.

## Run locally

```sh
python -m scripts.audit_current_analysis_queue \
  --db pla_watch.db \
  --out /tmp/ipr-current-analysis-queue.json
```

The output must be a **new file outside the repository**. The CLI uses the existing SQLite scratch-copy read-only helper (including WAL/SHM sidecars when present) and creates the private JSON with exclusive 0600 permissions. It does not modify `pla_watch.db`, output files, analysis retry states, queue priorities, any Actions workflow, or collector/publisher state.

All article dispositions are counted once and grouped by their actual stored **source slug and desk assignment**:

- `pending_relevance`: unscored, non-held record; part of automatic pipeline candidates.
- `pending_analysis`: passed relevance, unanalyzed, not held; part of automatic candidates.
- `paused_manual_review`: retry budget exhausted; explicitly **not** automatically queued.
- `terminal_content`: content is not automatically retryable; **not** automatically queued.
- `screened_out`: failed relevance check without analysis; not automatically queued.
- `analyzed`: passed and successfully timestamped as analyzed; not in the queue.
- `inconsistent_state`: unexpectedly marked states, e.g. analyzed while paused, or an invalid relevance code. Counts are surfaced rather than quietly counted as success.

The `automatic_queue_candidates` number matches the broad **relevance/state filters** in `storage.db.get_articles_unscored()` and `get_articles_pending_analysis()`; it is NOT a promise that this many records will be processed in the next run. Per-desk routing, available API credits, selection logic, retry outcomes and the 55-item Daily analysis cap still govern actual throughput. `held_out_of_automatic_queue` separates paused and terminal records; those are not buried in the pending backlog.

`queue_state_digest_sha256` covers ordered article IDs, source affiliations and queue dispositions from **one copied SQLite view**. It is not a cryptographic signature of the complete original database or a proof of GitHub Actions run history. Its purpose is to distinguish two states when comparing *reports*, not to infer publisher silence or model costs. The report does not include URLs, article titles, article bodies, generated summaries, model keys, or email addresses.

## Operational use

1. Run after obtaining a current, intact production database checkout. Label the archive commit and observation time **separately** in your operations notes; the report itself does not authenticate that the checkout is current.
2. Inspect `automatic_queue_candidates`, `paused_manual_review`, `terminal_content` and `inconsistent_state` separately. Sort source groups to distinguish a source-specific bottleneck from overall backlog.
3. Do not compare the number against historical Daily figures (e.g. the October 6 / October 8 run logs) without pinning both underlying database snapshots and accounting for new intake, analyzed records and changes to relevance or paused disposition.
4. Review actual model cost telemetry, failure rate and intake before proposing any cap or prioritization change. **No cap, schedule, API budget, priority, production desk or editor workflow is altered here.**

The output's collection/model/publication authority flags are always false. It supplies useful internal observability but is not source-health, government-inactivity, Sunday corpus-readiness, or human editorial permission evidence.
