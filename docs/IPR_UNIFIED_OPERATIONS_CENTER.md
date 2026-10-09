# Unified Operations Center — production, shadow and Daily evidence

**Private, local and read-only.** This is a single operator-facing report composed from the existing source-health dashboard, the static shadow source/workflow map, optional vetted logical-slot candidate reports, and optional **operator-supplied** Daily Actions receipts. It does not deploy a public page or automatically query GitHub, read a shadow state branch, run a collector, publish, call an LLM, write the database or send an editorial packet.

## One command for a full local snapshot

With the repository checked out and standard dependencies installed:

```sh
python scripts/operations_center_unified.py \
  --html /tmp/ipr-unified-operations.html \
  --json /tmp/ipr-unified-operations.json
```

The command reads the existing production SQLite database *read-only* through `scripts.source_health_report.build_report`; then calls `scripts.audit_shadow_workflow_bindings.validate(ROOT)` **directly on the actual repository configuration**. It joins all `shadow/*/manifest.json` declarations through the existing `operations_center_shadow_overlay.attach` contract. A static declaration says which workflow and branch are configured, **not** which job ran or whether collection succeeded.

The existing `scripts/operations_center.py` CLI and `scripts/operations_center_shadow_overlay.py` CLI remain supported unchanged.

## Optional Daily Actions metadata

To add real (but **unsigned and not authenticated after export**) Actions metadata from a particular **UTC run-creation day**, explicitly run the separate read-only GitHub API capture command:

```sh
python scripts/capture_daily_actions_receipts.py --created-utc-day 2026-10-07 \
  > /tmp/ipr-daily-raw-2026-10-07.json

python scripts/operations_center_unified.py \
  --daily-receipts /tmp/ipr-daily-raw-2026-10-07.json \
  --as-of 2026-10-09 \
  --html /tmp/ipr-unified-with-daily.html \
  --json /tmp/ipr-unified-with-daily.json
```

The unified CLI makes no network request by default. An operator can explicitly request a bounded GitHub Actions metadata GET through `--fetch-daily-utc-day YYYY-MM-DD` **instead of** `--daily-receipts`; these input modes are mutually exclusive. Either path passes the raw receipt through the **actual** `audit_daily_run_receipts.interpret` contract, rejecting malformed, contradictory, missing-field, duplicate-attempt and future-as-of-display records. It refuses a pre-rendered audit summary where a raw receipt is required.

Its new **Daily Actions evidence candidates** section shows per-run New York creation date, GitHub conclusion, *candidate* interpretation, guard decision if actually supplied, and separately sourced historical stored-article/backlog figures **only if those figures were supplied in the canonical receipt**. A green workflow whose guard stdout has not been reviewed is **not** called a successful collection. A cancelled job with no step evidence remains unknown. An empty report does not prove there were no runs or government publications.

The GitHub metadata capture client itself always sets `guard.should_run=null` and `analysis=null`; it cannot infer those from step metadata. The caller must obtain and review the corresponding original job logs to supply those fields in a separate **explicitly operator-edited** canonical receipt, never as an automatic fabricated observation.

## Optional source-slot candidate reports

```sh
python scripts/operations_center_unified.py \
  --slot-report /tmp/ipr-id-kemhan-slot-candidates.json \
  --html /tmp/ipr-unified-slots.html \
  --json /tmp/ipr-unified-slots.json
```

The separately vetted `ipr-shadow-slot-candidates/1` reports remain source-scoped and unauthenticated; the existing overlay checks source slug, state branch, cron and counts. A missing candidate report means **not supplied**, not missed government publication. Nothing is promoted to production or sent to the Sunday AI writer.

## Boundaries, outputs and merge gates

The unified JSON adds `daily_actions_evidence.schema=ipr-unified-daily-evidence/1` only when a receipt is explicitly supplied. Every positive status remains a **candidate**. The output carries `input_origin_authenticated=false`, `collector_work_certified=false`, `complete_run_history_established=false`, `current_analysis_queue_verified=false`, `publisher_silence_established=false`, `publication_authorized=false`, `source_promotion_authorized=false` and `editor_delivery_authorized=false`. The original source health report remains the **sole authority for production source counts and health**. Neither Daily receipts nor shadow candidate reports may alter it.

Both HTML and JSON destination paths must be **new**, distinct and **outside the repository**, including outside its tracked `output/` tree. The tool never overwrites existing reports; only the specified external output files are created.

Twenty tests cover unchanged Phase 1 HTML when Daily evidence is absent, real native shadow-manifest joins, independent overlay coexistence, skipped workflows, cancellations, historical backlog, malformed receipt refusal, HTML escaping, a CLI report to a temporary directory, and an end-to-end synthetic GitHub metadata capture → Daily classifier → Operations Center path proving that a green run with unknown guard cannot become an authenticated collection. Dedicated CI checks the new contracts and existing production/shadow/Daily tests without collector or GitHub calls and proves no tracked database/output writes; the full PR offline Chromium, repository tests, rendered output validation and preservation gates must also pass before the owner merges.

**Limits:** static files and historical metadata are not a real-time dashboard or source-use rights evaluation. This reporting milestone is not permission to schedule shadow jobs, expand model spend, release a manuscript, or email Dylan.
