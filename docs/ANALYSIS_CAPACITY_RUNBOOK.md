# Analysis capacity — private implementation candidate

This feature plans stored work and optionally admits requests against a per-run
estimated USD envelope. It does not authorize collection, spending, publication,
deployment, desk admission, model/limit changes or a new schedule. Defaults remain
cap 55, reserve 0.3, live window 14 days, existing models and output ceilings.
Independent review and an explicit single-run spending decision precede activation.

## Ownership and contract

Base: `59bb2eb0e8708dc51e063f81dbf325a8be31177d`, fresh main on 2026-10-11;
selected clean worktree, branch `codex/ipr-analysis-capacity-20261011`.
The current graph index was stale and belonged to another worktree; targeted
file reads governed implementation. #268's October 10 maintenance checkpoint
distinguishes merged fixes from outstanding live verification. Its old cap and
cost counts are not this archive's queue.

| Stage | Integrated seam and acceptance |
|---|---|
| S0 | Current rules, archive hashes, #268 checkpoint and open PR ownership pinned once |
| S1 | `core.analysis_plan` shared by Daily and private previews; differential legacy selection fixtures |
| S2 | `analysis.admission` at the analyzer's sole raw/tool/stream dispatch boundary; mock failure/concurrency matrix |
| S3 | Actual `pipeline.run`, analyzer, scratch SQLite DAO, native scrape-run ID, telemetry and private journal |
| S4 | Existing Operations Center, allowlisted JSON, fictional equal-cap/envelope replay, desktop/mobile browser checks |
| S5 | Full offline/validator/preservation gate, private reports and one draft PR; no activation |

Custody #342/C1/C2 retains database binding, durable identities and recovery.
The C1 private `DatabaseContext` remains dry-run-only in Daily. This candidate
does not integrate or absorb #360–#367's fictional custody/spend-journal stack.
Scratch tests use the established isolated DAO path. `get_analysis_inventory`
is an additive query on a caller-selected connection, not a storage redesign.
Desk, frontend (#391), Brief and #389 chronology/prompt work remain independent;
prompts, custody schemas and their branches are untouched.

## Planning and private inspection — no calls

Use new destinations outside the repository. Reports are mode 0600, refuse
overwrites and protected/repository paths, and contain no bodies, source titles,
URLs, prompts, translations, model output or credentials. SQLite reads use the
existing scratch-copy helper; file/main/WAL/SHM hashes pin input bytes before and
after reading. Snapshot plans have zero invented new arrivals.

```sh
.venv/bin/python scripts/analysis_capacity.py plan \
  --at 2026-10-11T00:00:00+00:00 --budget-usd 24 \
  --json /tmp/ipr-analysis-plan.json
.venv/bin/python scripts/analysis_capacity.py replay \
  --json /tmp/ipr-analysis-replay.json
.venv/bin/python scripts/operations_center_unified.py --as-of 2026-10-11 \
  --analysis-plan --analysis-budget-usd 24 \
  --analysis-replay /tmp/ipr-analysis-replay.json \
  --html /tmp/ipr-analysis-ops.html --json /tmp/ipr-analysis-ops.json
```

These example dates/envelopes are reproducibility inputs, not an approved amount.
The view preserves collector/scheduling/analysis/output/deployment distinctions.
Unsigned local identities and supplied run evidence never authenticate live
collection or billing. Existing Actions evidence retains its own authentication
limits; no new links are manufactured from plan/execution IDs.

Compatibility ordering: insertion order for this run's new records; pending by
ID; live unscored by ID before archive unscored by ID. The UTC cutoff compares
stored `scraped_at` day prefixes, exactly as before. Backlog slots use Python
`round(cap * reserve)`, minimum one when backlog exists, bounded by backlog
length. Unused new capacity spills to backlog. Desk holds, Unicode-whitespace
bodies, paused/terminal, completed/rejected and unknown processing states never
consume a selected slot. Unknown states are explicitly held; missing/duplicate
identities refuse the plan. A null desk retains the existing legacy China-profile
fallback. All SQL stays in the DAO.

The single age-aware alternative changes only backlog order: stored scrape
timestamp, then ID, missing timestamps last. It leaves the new allocation and
envelope equal and may displace publication-window/pending work with older
archive work. Scrape waiting time is not publication age or editorial value.
Code, complete in-memory inputs, processing history, runtime task settings,
policy/time and pinned prices bind the plan. Daily rereads and revalidates before
dispatch. A stored preview is not authorization for a later post-collection run.

## Admission and failure semantics

Strict money uses decimal arithmetic and canonical USD strings; it consumes the
same responses as best-effort telemetry without using telemetry to authorize
dispatch or rewriting its ledger. Reservations use the one price table plus
model limits in `analysis/pricing.py`. The full context ceiling bounds total
input including system/tool overhead; all input is reserved at the 5-minute
cache-write rate, plus unchanged output ceilings. No optimistic cache discount,
character/token heuristic, count endpoint or paid access probe is used.

Default models reserve **USD 12.005 per article** before relevance (0.2525
relevance + 4.23 translation + 3.765 summary + 3.7575 categories). This is a
worst-case exposure estimate, not the expected article price. It can materially
reduce throughput under a low envelope. Valid usage releases excess capacity;
relevance rejection releases all downstream reservations. The model ceilings and
rates are pinned to [Sonnet 4.6](https://platform.claude.com/docs/en/models/sonnet-4-6/overview)
and [Haiku 4.5](https://platform.claude.com/docs/en/models/haiku-4-5/overview),
checked 2026-10-11; historical telemetry retains its 2026-10-01 pricing date.

Each article's four stages are funded atomically under one lock. Summary/category
consume distinct reservations, and both futures resolve even after errors.
Unknown models, invalid limits/prices, custom endpoints/query/header overrides,
non-text inputs, server tools and unsupported cache TTLs refuse strict dispatch.
SDK automatic retries are explicitly disabled with `with_options(max_retries=0)`;
the default path retains its existing retry settings. SDK 0.100.0 and 0.125.0
were inspected/exercised; a real SDK mock transport proves one 429 attempt.

Admission denial is a deferral and changes no retry counters or relevance
verdicts. Denied calls are absent from usage telemetry. Parse/tool semantic
errors, empty output and truncation keep spent token receipts. HTTP/transport/
stream failures and missing/invalid usage retain the whole uncertain exposure
and block new dispatch. An observed bound breach keeps its actual estimated
cost and blocks requests, even when that reveals an over-envelope run.

For new admissions: known estimated spend + unresolved exposure + outstanding
reservations <= envelope. This is not an invoice/account/daily/cross-run cap.
There is no exactly-once billing claim, stage caching or automatic replay of an
ambiguous call. The owner-only journal fsyncs each write-ahead observation before
dispatch. Required receipt I/O failure stops dispatch; partial final lines and
interrupted runs remain incomplete. An attempted flag records dispatch intent,
not proof the provider received or billed it. A later invocation is a new
allowance and must not automatically resume an uncertain prior run.

The guarded API is `pipeline.run(..., budget_usd="…", receipt_sink=journal)`;
CLI equivalents are `--analysis-budget-usd` with `--analysis-run-receipt` and
optional `--analysis-policy age-aware`. These actual execution controls require
separate activation authority; **do not run them as part of this handoff**.
`generate_output=False` is an explicit scratch-test seam; normal defaults retain
rendering. No production workflow enables the controls.

## Evidence, replay and verification

Run outcomes form a partition: unattempted, budget-deferred, relevance-rejected,
fully-analyzed, incomplete, unknown. Admitted/attempted are overlapping lifecycle
flags, never summed as that partition. Calls reconcile known vs unresolved cost;
completed run status requires no unresolved/pending exposure or incomplete work.
Native scrape-run completion and deployment remain separate observations.
For a private journal view, replace `--analysis-plan` with
`--analysis-run /tmp/<new-run>.jsonl`; supplied evidence remains unsigned.

Replay contains identical fictional two-source arrivals for three days, cap four,
USD 24 envelope per day, and declared synthetic 1000-input/100-output token
receipts; every third record is modeled as relevance-rejected. Both policies use
the real planner/controller. It reports new/backlog allocation, waiting days,
source/desk admission counts and costs. It is a modeled comparison, not historical
per-record execution or a causal/quality improvement. Tracked aggregate usage
receipts are never divided into invented record prices. Actual analyzer/DAO
execution is separately proved by the scratch integration tests.

```sh
.venv/bin/python -m unittest tests.test_analysis_planning \
  tests.test_analysis_admission tests.integration.test_analysis_capacity \
  tests.test_analysis_capacity_reports -v
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python scripts/validate_output.py
```

The dedicated analysis-capacity PR workflow runs the full offline suite, browser
launch, output validation and DB/history/output preservation even while draft.
The ordinary PR gate keeps its existing draft policy. Local/CI results and exact
candidate heads are recorded in the PR and `PROJECT_STATE.md`; a required failure
leaves the PR draft. Real archive and public output are never regenerated here.
