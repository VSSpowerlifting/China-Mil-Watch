# Unscored Daily retries must retain their attempt counts

## Confirmed production symptom, October 9, 2026

Original Actions pipeline logs for October 6 ([run #37511704148](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37511704148)), October 8 ([run #37827949547](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37827949547)) and October 9 ([run #37973189996](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37973189996)) all report `Analysis failed entirely` for the exact same stored **article IDs 1077 and 1635**. The analyzer reports malformed JSON during relevance scoring; the errors are not content or source-use verdicts.

The existing pipeline recorded processing history only from
`pending_rows` (already relevance-passed, awaiting full analysis).
An article whose relevance call failed stayed in the *unscored*
backlog (`passed_relevance IS NULL`), and its recorded
`processing_attempts` was **not loaded back into** `attempts_before`
on its next appearance. `_record_failure` consequently classified
each attempted recurrence with `attempts_before=None` rather than
the previous recorded count. Repetition therefore could never reach
the intended reversible five-attempt review pause.

## Exact code change

The pure `pipeline.prior_processing_attempts()` helper collects
**stored** `processing_attempts` from both `pending_rows` and
`unscored_rows`, after desk/inserted-ID routing and before model
dispatch. Only records with already-present counters enter the map.
Newly scraped records remain free of invented historical attempts.

After a future observed analysis-format failure, the existing
`processing_state.classify` function increments the correct
stored history and records one of:

- `retriable` for an observed analysis failure below the five-attempt
  threshold;
- `paused` after the fifth observed nontransient failure, **reversible
  by explicit human resume**;
- **never** `terminal` from the counter alone.

The original `TRANSIENT` policy remains unchanged: transient API
outages do not auto-pause records even after repeated attempts.
Records with blank original bodies are still withheld before model
dispatch by merged PR #299, without incrementing counters or
claiming publisher silence. This PR does **not** retrospectively
increment or pause either identified recurring record: that would
invent unrecorded attempts and mutate historical production data.
If their stored count is currently one, the next actual failed
attempt becomes two, not five. Operator review can occur earlier
by separate action.

## Verification and bounds

Synthetic scratch-SQLite tests use the *real* storage retrieval and
processing-failure persistence APIs. They exercise repeated unscored
failures, fifth-attempt pause, human resume/reset, unchanged pending
lane, and the exemption for transient failures. The focused workflow
also checks the tracked production database using
`scripts.reconcile_db.read_only` copies, reporting only article IDs
and attempt metadata, without article text, network calls or writes.

No scraping, API/model calls, cap modification, paid retry, editor
delivery, publication, historic counter backfill or source-rights
decision is involved. Full repository offline/Chromium/render/
database-preservation CI and clean GitHub mergeability are required
on the **exact** PR head before owner squash merge.

## Open investigation

October 9 still showed one PLA Daily `no-text` classification among
27 parsed records despite overall source collection success. It is
not evidence that this particular record entered the paid model
queue (that run withheld **zero newly scraped blank-body model
candidates**). Identify its exact publisher record and review
the extraction verdict separately; do not conflate it with the
two recurring body-present relevance-format failures.
