# Stored analysis backlog: review-only mechanical triage

**Purpose:** Develop an evidence-based review inventory for the stored backlog without
automatically deciding which sources deserve editorial analysis, executing a
model, or increasing the Daily cap. This is a standalone follow-on to merged
[#280](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/280).
It does not depend on or modify the still-running #282 Operations Center branch.

## Run

```sh
python scripts/audit_analysis_backlog_triage.py --db pla_watch.db \
  > /tmp/ipr-stored-backlog-triage.json
```

The command uses `reconcile_db.read_only` to inspect a scratch copy of the
SQLite database and compares all counts with `audit_analysis_queue_by_source`
from **the same scratch connection**. It fingerprints the original SQLite and
any present WAL/SHM sidecars before and after reading, refusing a changed input.
The output is **aggregate source-level counts** and at most 20 identifier-only
review samples per lane; no title, URL, body, summary, prompt, or API credential.

## Review lanes, not automatic execution order

| Lane | Meaning |
|---|---|
| `ready_recent_unscored` | Daily-eligible, not relevance-scored, inside the configured 14-day **scrape** recency window; nonblank stored body |
| `ready_pending_analysis` | Daily-eligible, already passed relevance, awaiting full analysis; nonblank body, regardless of scrape age |
| `ready_archive_unscored` | Daily-eligible, unscored, older than the scrape recency window; nonblank body |
| `ready_undated_unscored` | Daily-eligible unscored with missing stored scrape time; nonblank body |
| `missing_body_daily` | Daily-eligible, but stored body blank; **extraction/adapter review is needed**, not a permanent content verdict |
| `held_desk_separate_review` | Singapore or another desk intentionally kept out of China's Daily model queue |
| `paused_manual_review` | Retry budget paused processing; only separately authorized human review may resume |
| `unknown_state_review` | Unrecognized processing state, not eligible for automatic analysis |

Rows already analyzed, relevance-rejected or terminal are not backlog triage
candidates. The script also reports **previously failed attempt counters**,
missing stored publication dates, and daily-eligible records without a declared
desk. These are metadata observations; `body_nonblank=true` does **not** prove
successful extraction, content rights, relevance, significance, or publication
readiness. No source is editorially ranked by its metadata alone.

**Trust and cost boundary:** the stored 277 eligible, 69 desk-held and 12 paused
values observed October 9 must not be treated as live production counts. The
number of selected tasks in a future run, success rate, API cost, and editorial
value are unknown. The triage marks all model-spend, publication, editorial
delivery and live-state authorizations false and does not alter the existing
`DAILY_ANALYSIS_CAP=55` or `BACKLOG_RESERVE_FRACTION=0.3`.

## Verification

Dedicated no-network CI exercises synthetic exact cutoff, desk exclusion,
missing body, pending analysis, paused state, retry metadata, exact source
reconciliation, sample-size limits, no text/body/URL leak, original DB no-write
hashing and a real tracked-DB smoke. The exact-head full repository offline,
Chromium, render and database/output-preservation suite must pass before
owner merge. No automatic deployment, backlog processing or editorial handoff.
