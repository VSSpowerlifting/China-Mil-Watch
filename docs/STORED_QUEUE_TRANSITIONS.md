# Two-snapshot stored queue change audit

**Purpose:** Convert Issue #268's backlog-throughput question into reproducible
evidence *without* approving an LLM budget increase or mistaking a lower
backlog count for successful model work. This is independent of #283, #286
and #289, which inspect a **single** tracked SQLite state.

## Inputs / command

A human must provide **two actual SQLite files**, copied or archived at
different points in time. GitHub Actions does not automatically persist
historical production databases for this tool and does not fetch them.

```sh
python scripts/audit_stored_queue_transitions.py \
  --before-db /private/snapshots/ipr-before.db \
  --after-db /private/snapshots/ipr-after.db \
  --at-utc 2026-10-09T12:00:00Z \
  > /private/reports/ipr-stored-transition.json
```

The command is **read-only** and entirely offline. It validates #280's
canonical queue categorization against each full database, pins the original
DB and present WAL/SHM hashes before and after scratch-copy inspection, and
requires distinct, nonidentical input files. Both sides use the **same UTC
cutoff**, to avoid fabricating transitions solely because time advanced.

The audit compares article IDs between files **only when the stored canonical
URL matches for that ID** (compared by in-memory SHA-256, without outputting
the URL). A reused ID for a different publisher URL fails closed rather than
pretending to be the same document. The output reports:

- Total Daily-eligible and separately held-out stored records on both sides.
- Added, removed and shared article IDs, including source/desk reassignments
  that need operator scrutiny.
- For shared records, exact queue-bucket transitions and Daily-eligibility
  entrances/exits.
- The **fully reconciled accounting equation**:

  `new Daily backlog − old Daily backlog =
  new eligible IDs − removed eligible IDs + shared IDs entering − shared IDs leaving`

- Source-level beginning and ending Daily-eligible counts, local input hashes
  and at most 12 article IDs in each identity-change sample.

The audit does not include article titles, URLs or body text. It cannot
authenticate whether either snapshot is actually production, whether one
descends from the other, whether record removals were justified, or whether a
move to `completed_analysis` reflects a successfully executed model run
versus a manual data mutation. **A processing-state transition is not proof
of billed model calls, expense, editorial value, source rights, website
publication or a successful Daily workflow.** Those require exact original
Actions/log receipts and source review.

## Operational interpretation

A fall in stored backlog may reflect completed processing, relevance
rejections, pauses, terminal classifications, source/desk scope changes,
or even deleted records; the report preserves these distinctions. Similarly,
a queue increase can be caused by newly stored articles, a manual resume,
or desk reclassification, not necessarily an unexpectedly high intake day.
Do not extrapolate this one comparison to a forecast.

To assess `DAILY_ANALYSIS_CAP=55` or the 30% backlog reserve, collect at
least several consistently timed snapshots, reconcile each with original
Daily run logs, and distinguish successful dispositions from unprocessed
attempts and guard skips. Seek explicit approval before any new spend.

The report carries `snapshot_ancestry_authenticated=false`,
`historical_model_execution_authenticated=false`,
`successful_analysis_jobs_inferred=false`,
`cost_or_budget_established=false`,
`model_spend_authorized=false`, `publication_authorized=false`
and `model_calls=network_requests=writes=0`.

The dedicated CI uses two synthetic SQLite fixtures to validate the
accounting under additions, deletions, unchanged IDs, desk reassignment,
paused resumes, relevance decisions, and completed-analysis state changes.
It also proves the two original DBs and site output remain byte-identical.
It **does not manufacture or upload a historical production snapshot**.
Full repository offline/Chromium/render/no-write CI must pass before merge.
