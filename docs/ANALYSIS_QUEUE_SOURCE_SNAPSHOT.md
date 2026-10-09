# Source-attributed analysis queue snapshot — read-only

Addresses the remaining [Daily throughput investigation #268](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/268) without raising model spend, running collection, opening the database for writing or pretending a past workflow log reflects the current stored queue.

## Run on a **pinned database checkout**

```sh
python scripts/audit_analysis_queue_by_source.py \
  --db pla_watch.db > /tmp/ipr-source-analysis-queue.json
```

The command uses `scripts.reconcile_db.read_only`: a scratch copy of SQLite plus any WAL/SHM sidecars, so no SQLite journal or checkpoint is written beside `pla_watch.db`. It reports only aggregate **counts by original source slug and declared desk**, not article text, titles or URLs. It records SHA-256 of the input DB (plus existing sidecars) and UTC audit time, **refusing to produce a report if those input bytes change during the audit**. This is not an external attestation of the file's origin or an immutable Git commit. Pin a Git commit and source separately in research notes when comparing snapshots.

## Definitions match the production pipeline

| Bucket | SQL and routing meaning |
|---|---|
| `daily_pending_analysis` | `passed_relevance=1`, `analyzed_at IS NULL`, state not paused/terminal; only desks where `profile_for_desk(desk_id).daily_queue` is true |
| `daily_unscored_live` / `archive` | `passed_relevance IS NULL`, not paused/terminal, eligible for the daily queue; split by configured `LIVE_BACKLOG_DAYS` cutoff against the audit timestamp |
| `daily_unscored_undated` | Eligible unscored with no stored scrape date; never automatically called recent |
| `held_unscored` / `held_pending_analysis` | The same stored pending categories, but at a desk held out from the China-model daily queue, including Singapore; not counted as daily-model debt |
| `paused` | Explicit processing retry budget pause. Human-review candidate, not an automatically retriable Daily task |
| `terminal` | A provenance-retained content disposition, not something to keep sending to the model |
| `completed_analysis` | `analyzed_at` set and state not already paused/terminal |
| `relevance_rejected` | Stored `passed_relevance=0`; not actionable analysis backlog |
| `unknown_state` | An unexpected future/malformed processing state kept visible, not silently treated as eligible |

`stored_daily_queue_eligible` = unscored live + archive + undated + pending for eligible desks only. `stored_held_out_of_daily` is separate. They are **not the full archive size, the next run's queue or the 55-article current Daily cap.** The next run may collect new records, alter profiles, encounter an API outage or exhaust reserved backlog capacity. This snapshot cannot measure fresh articles *not yet stored*. Do not treat `stored_daily_queue_eligible` as a guaranteed spend, backlog clearance time or Sunday Brief readiness.

The `processing_state` handling matches `storage.db.get_articles_pending_analysis`, `get_articles_unscored`, and `pipeline.py` routing. A missing/undeclared desk follows the pipeline's China-profile fallback but retains an explicit source/desk attribution sentinel so that the dashboard does **not** imply a genuinely reviewed China source.

## Evidence and safety

The output contract is `ipr-analysis-queue-by-source/1` and always declares `historical_run_completeness_established=false`, `next_run_new_articles_known=false`, `future_queue_cap_outcome_known=false`, `live_production_state_authenticated=false`, `collection_executed_authenticated=false`, `model_spend_authorized=false`, `source_rights_cleared=false`, `publication_authorized=false`, `editor_delivery_authorized=false`, `model_calls=0` and `writes=0`.

The audit does not perform API calls or use environment secrets. It refuses missing/incompatible tables, invalid scrape timestamps and impossible relevance verdicts; unknown processing states are explicitly counted for human review instead of silently admitted.

## CI and acceptance

The dedicated CI runs 21 synthetic tests for all buckets, source and desk attribution, precise live cutoff, cross-source count conservation, malformed schema, SQLite scratch-copy read, missing file, a subprocess CLI invocation and no model/DB mutations. A separate smoke step runs the CLI against the **actual tracked production SQLite** and validates all bucket sums and zero authorization flags, and logs aggregate counts only (never article text, titles or URLs), without contacting GitHub or a publisher.

Merge only after exact-head focused tests **and** the repository's full offline/Chromium/render/DB-output-preservation suite pass. This milestone is independent of the currently running Unified Operations Center PR #275; a later optional integration may add its verified counts as a **separately scoped, explicitly labeled** section, never a surrogate for official source health.

**No change to `DAILY_ANALYSIS_CAP`, model cost, collection frequency, user permissions, shadow admission, model prompts, publishing or editorial delivery.**
