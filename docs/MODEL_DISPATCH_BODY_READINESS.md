# Daily analysis: stored backlog versus body-ready model dispatch

The canonical read-only queue audit counts records stored in eligible
Daily buckets. The Daily runtime, with the proposed blank-body input
guard in PR #299, should send **only records with a real, nonblank
original body** to paid model analysis. These are different quantities.

The existing `scripts/audit_analysis_backlog_triage.py` now reports:

- `stored_daily_queue_eligible`: **all records in the Daily storage
  buckets**, including records whose original prose is absent.
- `stored_daily_model_dispatch_body_ready`: Daily-eligible records
  whose stored `text_original` is a Python `str` with at least one
  nonwhitespace character, matching #299's input predicate.
- `stored_daily_model_dispatch_body_withheld`: Daily-eligible records
  whose stored bodies are NULL, non-string or empty under
  `str.strip()`, requiring recovery/operator review before paid
  dispatch. **Body withheld is not a terminal content verdict.**

Those last two totals must exactly sum to the first. The same counts
reconcile independently by source and desk.

The previous `review_lanes` and `metadata_flags.daily_missing_body`
remain **unchanged**. They use SQLite's historical ASCII whitespace
trim, which does **not** necessarily match Python's Unicode-aware
`str.strip()`; a record consisting of non-ASCII spaces can be
model-withheld even though the older review lane says body-present.
The audit intentionally does **not** rewrite old evidence or
pretend those flags are identical. Its new predicate reads text on
a scratch SQLite connection but never emits it in JSON.

Usage:

```sh
python scripts/audit_analysis_backlog_triage.py --db pla_watch.db \
  > /private/tmp/ipr-backlog-body-readiness.json
```

The status is a **snapshot of stored input**. It is not a preview of
what tomorrow's scraper will collect, of the next run's scheduling
decisions, whether an article will pass relevance, or whether the
provider succeeds. It is *not* proof that the separate PR #299 is
already merged/deployed. No cap or reserve change is authorized by
this report.

A record with no extractable body must stay in the source archive
with a human-reviewable recovery path. This audit does not access
publisher sites, classify absent text as `no_usable_prose`, resume
records, invoke model tasks, estimate billing, modify the production
database, publish the site or send Briefs.

Fields `model_dispatch_preview_not_future_run_workload=true`,
`model_dispatch_preview_not_spending_approval=true`,
`model_spend_authorized=false`, `model_calls=0`, `writes=0`
mark those boundaries explicitly.

To release, require exact-head focused CI plus full repository
offline/Chromium/render and archive-preservation checks. Existing
Operations Center consumers should display the **stored** count
unless separately updated and tested to distinguish the new fields.
