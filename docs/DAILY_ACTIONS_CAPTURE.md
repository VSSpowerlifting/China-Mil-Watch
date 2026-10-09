# Daily Actions receipt capture — metadata-only, read-only

**Stage:** Supports [Operations Center reliability investigation #268](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/268). This is a **nested PR** on top of [Daily receipt classifier #269](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/269), not a deployed monitor. Do not merge into main until #269's independent full suite passes and is merged.

## Purpose

Operators previously had to manually copy metadata into the `ipr-daily-actions-receipts/1` offline classifier input. `scripts/capture_daily_actions_receipts.py` retrieves the **exact UTC creation-day's** Daily Actions run metadata and its job/step conclusions over the public GitHub REST API, with an optional `GITHUB_TOKEN` for rate limits.

```sh
python scripts/capture_daily_actions_receipts.py --created-utc-day 2026-10-07 \
  > /tmp/ipr-actions-2026-10-07.json

python scripts/audit_daily_run_receipts.py \
  /tmp/ipr-actions-2026-10-07.json > /tmp/ipr-daily-candidates.json
```

**Exactly one host and repository** are embedded: `https://api.github.com/repos/VSSpowerlifting/China-Mil-Watch`. The exporter uses only `GET` with 20-second request timeouts. It does not execute or dispatch a workflow, call OpenAI/Anthropic, collect official records, modify production state, or send editor mail. It uses an inclusive `created=YYYY-MM-DD` **UTC** filter, never inferring New York calendar days or logical scheduled target dates from that field.

It refuses an API export if results are partial, exceed 200 runs, change pagination counts across pages, contain duplicates, carry unknown workflow/event/status, have inconsistent timestamps, or if a Daily run now has multiple jobs rather than the reviewed single `update` job. It refuses incomplete/running runs instead of treating a partially completed day as an empty one.

## Strict trust boundary

GitHub's job API exposes the `Scheduling guard` step **result** but not the text printed to its stdout. Accordingly the exporter **ALWAYS writes `guard.should_run=null`**. Its six required downstream step statuses are `success`, `failure`, `skipped`, `cancelled`, or `unknown` if absent. A run with no job entry is **unknown**, not assumed to have skipped the collector.

The API does **not** contain pipeline counts of newly archived articles, LLM-eligible queue items, backlog or spending. The exporter **ALWAYS writes `analysis=null`**, even for a completely green pipeline. An operator must separately examine the pinned run's job logs and, if desired, supply verified log interpretations using the offline schema. No log facts are manufactured or scraped by this exporter.

A fetched file is **not a signed attestation**. Although the tool fetches official GitHub API metadata via HTTPS at execution time, the resulting JSON can be edited afterward and has no independently verified signature. The downstream classifier still correctly emits `supplied_actions_export_authenticated=false`, `production_health_certified=false`, `analysis_queue_current_state_verified=false`, `archive_capture_verified=false`, `no_publications_inferred=false`, and `publication_authorized=false`.

Crucially, since `guard.should_run=null`, a green run with every required step present and marked successful still yields `green_workflow_work_not_established` until the actual guard output has been reviewed. This conservatism is intentional. A queued/cancelled job is not proof a source publisher fell silent or that a historic Daily date had zero publications.

## Testing and merge

```sh
python -m unittest tests.test_capture_daily_actions_receipts -v
python -m unittest tests.test_daily_run_receipts -v
```

Focused CI tests 24 synthetic API importer cases plus the upstream offline-classifier contract and confirms the tracked production SQLite database and `output/` are byte-unchanged. It performs **no real network API calls**, ensuring failures are deterministic and cannot affect production availability. The full repository PR offline/Chromium/render validation suite is still required on final main before merge.

**Next phase, out of scope:** authenticated Actions receipt handling with pinned job log retrieval and provenance linking, canonical production throughput metrics and first-party UI integration. Those require explicit trust contracts, bounded access and owner-reviewed promotion; nothing here automatically validates source publication or sends editorial material.
