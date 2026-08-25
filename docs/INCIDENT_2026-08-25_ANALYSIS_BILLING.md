# Incident 2026-08-25 — analysis blocked by an account usage limit

**Layered verdict.** Collection succeeded. Storage succeeded. Analysis did not
run at all. Nothing was published, and nothing was lost. The block is an
account-level condition that no code in this repository can clear.

---

## 1. What actually happened

Scheduled run **533** (`32853064669`), head `da42b911`, 2026-08-25 13:23–13:31 UTC.

Steps 1–13 passed, including the offline suite and the tracked-database
cleanliness gate. Step 14, `Run pipeline`, failed. Everything after it either
salvaged state or was skipped:

| Step | Outcome | Consequence |
|---|---|---|
| Run pipeline | **failure** (exit 2) | analysis aborted |
| Validate rendered output | skipped | — |
| Persist scraped articles | success | commit `3f79ba1` — database only |
| Commit billing-failure marker | success | commit `4207eac` — marker only |
| Commit database and site output | skipped | `output/` not regenerated |
| Deploy to GitHub Pages | skipped | Pages frozen at the 2026-08-24 build |
| Record successful run | skipped | **`last_daily_run_date.txt` stayed 2026-08-24** |

### The failing call

Collection finished normally, then the first of 55 queued analysis calls
returned:

```text
POST https://api.anthropic.com/v1/messages  ->  HTTP 400
invalid_request_error: "You have reached your specified API usage limits.
                        You will regain access on 2026-09-01 at 00:00 UTC."
```

`analysis/analyzer._classify_status_error` matched
`reached your specified api usage limits` in `_FATAL_MESSAGE_MARKERS` and
raised `FatalAPIError`. `pipeline.py` aborted the queue at 1/55 rather than
making 54 further doomed calls, wrote the marker, and exited 2.

**This is not credit exhaustion.** The account has not run out of money; it has
reached a *configured* usage limit with a stated reset. The project has seen
both, and they need different actions:

| Date | Message | Fix |
|---|---|---|
| 2026-07-30 | configured usage limit | raise the limit, or wait for the monthly reset |
| 2026-08-07 | `credit balance is too low` | add credit in the Console |
| **2026-08-25** | **configured usage limit, resets 2026-09-01 00:00 UTC** | **raise the limit, or wait for 2026-09-01** |

The state file is named `last_billing_failure_date.txt` because it is one
bucket for every account-level block. The filename is not the diagnosis.

---

## 2. What the run did and did not achieve

| Layer | Result |
|---|---|
| Collection | **complete** — aggregate `completed`, 4 sources ok, 1 documented stub, 0 failures |
| Storage | **complete** — 35 records stored (ids 3506–3540), 3499 → 3534 |
| Analysis | **none** — 0 of 55 attempted calls succeeded |
| Rendering | **not attempted** — the validate/commit/deploy steps were skipped |
| Publication | **not attempted** — Pages still serves the 2026-08-24 build |

Run 121 is recorded `status='failed'` with the API error stored in
`scrape_runs.errors`. Nothing rewrote it as a success.

### Nothing was written half-way

* 0 of the 35 new records carry any analysis field.
* 0 pre-existing records were modified. Analyzed count is 1,335 before and
  after; category links 2,551 before and after.
* `PRAGMA integrity_check` = `ok`, 0 foreign-key violations,
  `verify_db_current.py` = `fully_current`.
* `output/article/` holds 1,335 pages and the corpus holds 1,335 analyzed
  records. The site renders only analyzed articles, so a run that analyzed
  nothing had nothing to publish — `output/` is not stale, it is complete for
  the set it describes.

One collection defect, unrelated to the block: record **3537**
(`81.cn/yw_208727/16481250.html`) stored with a 0-character body. Same class as
the known id 2678. It was keyword-rejected, so it will not be analyzed, but the
capture failed silently.

---

## 3. Recovery — automatic, and proved

Recovery does not depend on anyone re-running anything, because the analysis
queue is selected by **record state**, never by which run inserted a record:

* `get_articles_unscored()` → every row with `passed_relevance IS NULL`
* `get_articles_pending_analysis()` → every row scored but not analyzed

The backlog receives a reserved share of the daily cap
(`BACKLOG_RESERVE_FRACTION`, 30% of 55 → 17 slots minimum), and unscreened rows
scraped within `LIVE_BACKLOG_DAYS` are drained **before** the archive, so the
records from this outage go to the front rather than behind ~769 older ones.

Simulated locally against a copy of the post-incident database, with the
provider mocked and the network denied — the 30 unscreened records from run 121
(ids 3506–3535):

| Scenario | Result |
|---|---|
| Block persists, next run | 0 analyzed, 0 stored partially, exit 2, marker rewritten. Nothing lost. |
| Limit lifted, next run | **all 30 analyzed in one run**, `unscreened 30 → 0` |
| Retry run twice | second run re-analyzes none of them; no duplicate records, runs or category links |
| Fresh collection + this backlog | 12 new stored *and* all 30 recovered in the same run |
| Block after 10 analyses, then lifted | 7 recovered on day 1, remaining 23 on day 2 |

Collection failing does not block analysis recovery either: in one simulation
every source failed and the backlog still drained 55 records.

### The guard blocks one day, not the outage

`last_billing_failure_date.txt = 2026-08-25` makes the remaining cron windows on
**2026-08-25 only** skip their paid retries — confirmed by runs 534–537, which
report "success" having run nothing but checkout and the guard. The success
marker was never written, so 2026-08-25 is not recorded as a completed day, and
2026-08-26 runs normally.

**Until the limit is lifted**, each daily run will: collect and store normally,
attempt one analysis call, fail, rewrite the marker, exit 2, and skip publishing.
Collection is preserved every day. Analysis stalls.

At ~30 records/day the unscreened backlog grows from 799 to roughly 980 by
2026-09-01. After that, at cap 55 with the 30% reserve, it drains ~25/day
against ~30/day inflow — roughly 40 collecting days to clear, or far fewer with
`DAILY_ANALYSIS_CAP` raised for a few runs.

---

## 4. Owner action

Nothing in this repository can clear an account-level limit.

1. **Anthropic Console → usage limits.** Raise or remove the configured monthly
   API usage limit for the key the workflow uses. Adding credit will *not* help:
   the account is limit-blocked, not balance-blocked.
2. Alternatively, do nothing and wait for **2026-09-01 00:00 UTC**, when the
   limit resets by itself.

After either, recovery is automatic on the next scheduled run. To recover the
same day instead, run the workflow manually — `workflow_dispatch` skips the
billing guard by design:

```bash
gh workflow run daily_update.yml
```

To drain the accumulated backlog faster than the daily cap, one scoped run:

```bash
DAILY_ANALYSIS_CAP=200 .venv/bin/python pipeline.py
```

For a specific edition window, prefer the scoped backfill, which prices the run
first and requires the estimate to be acknowledged:

```bash
.venv/bin/python scripts/backfill_unscored.py --since 2026-08-23 --until 2026-08-29 --confirm-spend
```

Expected paid scope on the first recovered run: at most `DAILY_ANALYSIS_CAP`
articles. Already-analyzed records are never re-queued, so a retry costs nothing
for work already paid for.

---

## 5. Editions

**Edition No. 14 (week ending 2026-08-15) is not affected by this incident.**
That window holds 229 records across 7 dates: 137 analyzed, 92 screened out,
**0 unscreened, 0 incomplete**. Its data was complete before the block and is
complete now. No. 15 (w/e 2026-08-22) is likewise fully screened.

What blocks No. 14 is the same limit: `scripts/generate_pla_watch.py` calls the
API itself. It will fail while the account is limit-blocked, and will work as
soon as it is not.

**One gap worth knowing about before generating a later edition.**
`generate_pla_watch.py` selects `analyzed_at IS NOT NULL` and neither counts nor
warns about unscreened records in the window. For the week ending 2026-08-29 it
would currently see 39 of 105 records and say nothing about the other 30 being
unassessed. That is safe for No. 14 and No. 15, and it is a real hazard for an
edition generated over a window the backlog has not reached yet. Check the
window before generating:

```sql
SELECT COUNT(*) FROM articles
 WHERE published_date BETWEEN :start AND :end AND passed_relevance IS NULL;
```

Adding a gate to the generator is a behaviour change and was deliberately not
made as part of this incident response.

---

## 6. Latent risk recorded, not fixed

`_write_billing_failure_marker()` writes `date.today()` — the runner's **UTC**
date — while the workflow guard compares against **America/New_York**. Its
docstring claims it writes the NY date. Every configured cron window is
08:23–10:23 EDT, where the two agree, so this cannot misfire today. A cron moved
past 20:00 EDT would write tomorrow's marker for today's failure and suppress a
day that never failed. `tests/test_analysis_recovery_contract.py` fails if any
cron window ever lands on a different date in the two zones.
