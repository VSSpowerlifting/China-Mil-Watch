# Production Daily: offline Actions execution and backlog receipts

**Status:** Internal investigation tool for [Operations Center Issue #268](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/268) and [Phase 2 Issue #250](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/250). This does **not** connect to GitHub, authenticate a run export, query the production database, call a model, or publish. It interprets evidence provided by an operator.

## Why this is needed

A successful GitHub Actions conclusion has at least two distinct meanings in the production Daily workflow: the scheduling guard may report `should_run=false` because that New York day already ran successfully, or the guarded workflow may execute the pipeline, output validator, database/output commit, deployment, successful-run marker and health gate. A workflow ending green does not alone distinguish these.

A cancelled run is **not** proof no work took place. The October 7 Daily run listing shows five cancellations, but a cancellation may occur before or after any collection step. The current workflow's `cancel-in-progress=false` is also not evidence identifying who or what cancelled any particular run.

The analysis queue must be monitored separately from source collection. Job logs from [the actual October 6 production run](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37511704148) report 331 queued (18 new + 313 backlog) and 276 after cap 55. Logs from [the actual October 8 production run](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37827949547) report 324 queued (42 new + 282 backlog), 266 backlog after cap 55, 46 newly stored documents and 3 newly queued items deferred. Stored articles and LLM-eligible queue items are **not interchangeable**. A subsequent [green scheduling-guard skip](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37836092547) is not a second collection.

## How to run, offline

```sh
python scripts/audit_daily_run_receipts.py /tmp/ipr-reviewed-daily-actions.json > /tmp/ipr-daily-candidates.json
python -m unittest tests.test_daily_run_receipts -v
```

Supply a JSON object with exactly:

- `schema: "ipr-daily-actions-receipts/1"`
- `as_of_utc`: explicit zero-offset UTC timestamp later than the last supplied Actions run's `updated_at`
- `runs`: an array of 0–200 *reviewed* completed GitHub Actions attempts, which may be incomplete.

Each run must identify `run_id` (positive integer), `attempt` (positive integer), `workflow: "Daily PLA Watch Update"`, `event` (`schedule` or `workflow_dispatch`), `status: "completed"`, `conclusion` (success, failure, cancelled, timed_out), `created_at`, `updated_at`, `guard`, `steps` and `analysis`.

`guard` has `step_result` (success/failure/skipped/cancelled/unknown) and `should_run` (true, false or null). Set `should_run` only when the guard step and its log support that decision.

`steps` has **exactly** six keys, each valued success/failure/skipped/cancelled/unknown, matching the current Daily workflow's step names: `Run pipeline`, `Validate rendered output`, `Commit updated database and site output`, `Deploy to GitHub Pages`, `Record successful run`, `Health gate`. Use `unknown` rather than inventing a status if metadata is missing.

`analysis` may be null; where separately verified pipeline log lines supply all seven fields, it may have nonnegative integer `new_articles_stored`, `queue_total`, `queue_new`, `queue_backlog`, `daily_analysis_cap`, `backlog_after_cap`, and `deferred_new`. The tool refuses inconsistent queue totals, impossible post-cap sizes and metrics attached to an unexecuted pipeline. It **does not** claim to authenticate these log excerpts.

## How to interpret results

- `collection_validation_deploy_candidate`: guard explicitly ran; all six key execution and publish stages are reported successful; successful workflow. Requires independent run/job/log verification before considering it proven.
- `green_scheduling_guard_skip_candidate`: successful guard with explicit `should_run=false`, and all six execution/publish steps skipped. **Never count as another collection**.
- `cancelled_pipeline_step_skipped_candidate`: a *supplied job* reported guard `should_run=true` but skipped the pipeline and all six inspected production/deployment stages before cancellation (the October 7 Playwright stall illustrates this). This is still **not authenticated** proof about all possible jobs or collections.
- `cancelled_execution_extent_unknown` or `timed_out_execution_extent_unknown`: there is insufficient supplied step evidence to know whether the pipeline executed, why the run stopped or whether another job/attempt existed.
- `pipeline_failed_attempt`, `post_deploy_health_gate_failed`, `failed_workflow_execution_requires_review`: distinguish a failed pipeline from a health notification after an actual deployment.
- `green_workflow_work_not_established`: success is not enough to establish that every required collection/publish step ran.

Outputs include a separate count of provided statuses for runs grouped by **Actions creation date in New York**, with UTC date also retained on individual runs. This is **not** the nominal expected workflow slot date, and no attempt is made to infer dates missing from an incomplete export. Backlog snapshots are historical, operator-supplied measurements; **none** establishes the current queue size.

Every output declares: source/authentication/production/queue/editor/publisher-silence/rights claims **false**. No e-mails, source promotions, automation or DB writes. Never increase `DAILY_ANALYSIS_CAP` on the basis of this output alone; confirm model capacity, cost and operational impact first.

## Merge/test gate

The dedicated CI runs 27 synthetic contracts and verifies that the tracked production database and `output/` remain unchanged. The repository's full PR offline checks (Chromium, test suite, output validator and preservation) must also pass against current `main` before this component can merge. This issue-level milestone deliberately does not modify the pre-merge Operations Center UI or any collection workflow; a later gated integration may present authenticated receipts once available.
