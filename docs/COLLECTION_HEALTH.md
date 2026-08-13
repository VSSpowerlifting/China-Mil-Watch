# Collection health

## The problem this addresses

A green run was evidence of nothing. Five scheduled runs a day report success by
design (one real, four scheduling-guard no-ops), and the aggregate `scrape_runs`
row could not distinguish "MOD China published nothing" from "MOD China could
not be reached". PLA Daily supplies ~87% of the corpus, so the totals never
moved when a smaller source died — MOD China was silent from 2026-07-10 for four
weeks without a single failed run.

## Reports

```bash
.venv/bin/python scripts/source_health_report.py
.venv/bin/python scripts/source_health_report.py --json report.json
```

Read-only, no network, no model calls. The pipeline also logs the human report
inline at the end of collection.

Neither report is a public surface. They contain no secrets and no stack traces
by construction, but the public coverage statement is written by a human.

### Current output (2026-08-13)

```
SOURCE             DESK   TIER  ORIG     ARTICLES  LAST ARTICLE SILENCE        CONFIG
china_mil_online   china  B     mirror        315  2026-08-12   within_cadence (1d) ok
global_times_mil   china  D     original       90  2026-08-12   within_cadence (1d) ok
mod_china          china  A     original       11  2026-07-10   overdue (34d)  ok
pla_daily          china  B     original     2766  2026-08-12   within_cadence (1d) ok
xinhua_mil         china  C     syndicat        0  never        unknown (?d)   not_implemented
```

Both known problems are now visible without anyone going looking: MOD China
overdue against its own 21-day threshold, and Xinhua reported as
`not_implemented` rather than as a healthy source that published nothing.

## Definitions

**Discovered** — candidate references the listing produced.
**Fetched** — references retrieved successfully.
**Extracted** — captures the parser turned into documents.
**Duplicates** — extracted documents already stored (URL or content hash).
**New** — documents stored for the first time this run.
**Relevance rejected** — stored but failed the keyword gate.

**Silence** is measured against the source's own `silence_threshold_days`, taken
from the manifest and measured from the source's own listings — never from our
collection, which is the thing under test.

- `within_cadence` — quiet, but not unusually so.
- `overdue` — silent past its own threshold. Investigate; do not assume dead.
- `unknown` — never delivered, or no date to measure from.

**Not implemented** is not silence and not failure. It means a configured source
has no working collection path. It never degrades a run and is never hidden.

## Per-source results

`source_run_results`, one row per (run, source), written by
`storage.db.record_source_run_result()`. `is_failure` is stored rather than
derived so a later change to the status vocabulary cannot retroactively rewrite
what an old run reported.

Rows cascade when their run is deleted. Articles deliberately do **not** cascade:
a run holding published articles cannot be deleted at all, because article ids
are live `output/article/<id>.html` URLs.

**Reconciliation.** `scripts/reconcile_db.py` merges these rows from both
sides. Local rows whose run was renumbered follow the remap; the natural key is
`(scrape_run_id, source_slug)` after remapping, and on a true conflict the
published/origin row wins. Source identity is the **slug**, which is stored
directly — numeric `sources.id` values are never compared across two
independently evolved databases.

A row whose run lineage cannot be proven **aborts the merge**. It is never
dropped, and never attached to a run that merely shares its numeric id. The
merged table is then compared against an exactly computed expected map, so a
missing, extra or altered observation fails rather than passing unnoticed. Gates
also fail if the table is absent — a missing table is never treated as an empty
one.

**Limitation.** History starts at the first run after migration 0004 — the
report says so rather than implying a longer record than exists.

## Reading a degraded run

`degraded` now has two independent causes:

1. **Analysis** — an account-level API block mid-run (the existing 2026-08-09
   behaviour, unchanged).
2. **Collection** — at least one collectible source failed.

Both write `scrape_runs.status = 'degraded'`; the per-source rows and the run's
`errors` say which. A run that collected nothing at all from every collectible
source is `failed`, not `degraded`.

## What is still missing

- No coverage-completeness metric. `coverage_metrics` is Phase 3.
- No alerting. The report is pull-only; the existing `check_source_liveness.py`
  health gate is untouched and still the notifying mechanism.
- No per-desk or per-source collection budget. Not needed with one desk;
  required before a second is activated, so one high-volume country cannot
  consume the run.
