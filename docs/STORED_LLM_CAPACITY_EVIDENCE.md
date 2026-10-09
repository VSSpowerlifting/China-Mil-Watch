# Stored model-usage evidence for backlog capacity decisions

This report uses the existing append-only
`.github/state/llm_usage.jsonl` operational telemetry to assess
**what the pipeline recorded using its current configuration**, not
to propose or implement an automatic cap increase.

## Run (read-only)

```sh
python scripts/audit_stored_llm_capacity.py \
  --usage-jsonl .github/state/llm_usage.jsonl \
  > /tmp/ipr-usage-capacity-evidence.json
```

No network request, model call, collector dispatch, database change,
file write by the script, publication, or editorial delivery occurs.
The report identifies the exact JSONL input with SHA-256, verifies its
bytes remain unchanged, reconciles every task-level count with its
corresponding run totals, refuses duplicate dates, and checks estimated
task costs against the corresponding run costs and per-analyzed cost.
Models missing pricing are identified as **incomplete cost coverage**,
not counted as free. History with malformed, truncated, contradictory
or duplicate-day receipts is refused rather than silently repaired.

The script outputs **aggregate, model/task and run-date metadata only**,
not article IDs, text, URLs, model prompts, credentials, invoices or
original ledger line bodies.

## What the October 2–8 tracked usage data can establish

Six model-usage receipts exist for October 2, 3, 4, 5, 6 and 8. There
is **no October 7 record** in this tracked usage history; this says
nothing on its own about whether October 7 collection or model calls
happened. Original Actions evidence for October 7 must be reviewed
separately, and cancelled attempts may have consumed compute or money
without leaving a complete usage record.

Run-level `articles_queued` measures tasks **selected under the daily
cap**, not the number that will pass relevance, be fully analyzed or
exit the persistent queue. `articles_fully_analyzed` excludes
relevance-rejected records: **55 queued with 25 fully analyzed does not
mean 30 failed**. Similarly, task `failed_calls` counts attempts,
not affected unique records or additional billable articles.

The `estimated_cost_usd` field is calculated from the repository's
price table (`pricing_checked` in each receipt); it is **not** an
Anthropic invoice. A null per-analyzed cost when zero are fully analyzed
does not mean that no tokens were used. Any unpriced model prevents
a complete cost estimate.

## Limits and decisions

The report explicitly **does not** prove historical job authenticity
beyond the stored file, billing accuracy, or which exact article
IDs a model processed. For the original October 6/8 Daily run log
evidence see Issue #268. The independent two-SQLite reconciliation in
PR #291 compares stored backlog movement, not priced LLM invocations.
Do not invent an exact one-to-one mapping between these datasets.

Deciding whether to change `DAILY_ANALYSIS_CAP=55` or the
`BACKLOG_RESERVE_FRACTION=0.30` requires an owner-reviewed combined
finding covering fresh record intake, held-out desk exclusions, queue
dispositions, failure causes, cost and editorial value. **This tool
neither recommends an automatic numerical increase nor changes the
environment, schedules, pipeline or budget.**

Trust flags remain false: `analysis_cap_change_authorized`,
`model_spend_authorized`, `run_authenticity_beyond_pinned_input_proven`,
`matching_actions_jobs_authenticated`, and `publication_authorized`.
Local computation always records `model_calls=0` and `writes=0`.

## CI

The dedicated workflow verifies synthetic malformed/duplicate JSONL,
call/task accounting, prices, missing date distinction, no-write hashing,
and a real tracked six-run telemetry smoke. It explicitly verifies
`pla_watch.db`, the tracked usage file and public output are unmodified.
Require its exact-head success **and** full offline repository/Chromium/
render/preservation checks before owner merge.
