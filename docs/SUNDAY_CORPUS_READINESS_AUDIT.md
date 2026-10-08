# Sunday Briefs production-corpus readiness — read-only

This is an independent, metadata-only source-coverage diagnostic for the Sunday unified thematic Brief. It **does not** generate a manuscript, use Anthropic, send an email, retrieve new issuer documents, or change the production database. It can run while [Sunday manuscript PR #237](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/237) has long-running full CI without restarting it.

## Why

A working Sunday writer can still fail operationally if there are no substantive, full-text records across at least two production-backed desks, the full Saturday reporting week has not yet elapsed, or Sunday's successful production database update has not been recorded. The existing integration properly refuses to run on stale dates, but an editor benefits from knowing this **before** spending on a model or attempting SMTP.

The normal daily source run commits the New York-local success marker at `.github/state/last_daily_run_date.txt`; its existence and correct **Sunday** date are necessary for a current full-week brief but do not prove exhaustive ministry publication coverage.

## What is actually checked

`scripts/sunday_corpus_readiness.py` uses the existing production desk registry and `scripts.reconcile_db.read_only` (which copies the tracked SQLite and any WAL sidecars into temporary storage, leaving the original intact) to select original records within a precisely bounded Sunday-to-Saturday publication window. No HTML, original-language body, translation, article URL or private manuscript is included in the report.

The report counts, **for each eligible production desk**, stored records, offered unscreened/selected records, and records with at least 250 characters of saved original/translated text. Records deliberately screened `not_selected` do not count as model candidates. Mere publisher headlines and source IDs without actual text do not count as model-usable evidence.

Its model-attempt verdict is a **necessary preflight only**:

- The reporting source `as_of` must reach the full Saturday. Thursday or Friday is `reporting_week_not_complete`.
- The New York-local review date must reach **Sunday**, not Saturday.
- The tracked daily successful-update marker must equal that **same Sunday**, not yesterday or an arbitrary past date.
- At least two distinct production-backed desks must each have usable original/translated text. This is not proof of a coherent shared theme, truthful citations or source completeness.

If any condition is absent, the report says `hold_before_model_or_email` and lists specific unmet gates. If all are present, it may say `candidate_for_no_send_model_preview_not_approved`. It **never** marks the manuscript reviewed, external Japan/Vietnam research verified, publication approved or Dylan's email authorized.

## GitHub Actions usage

A pull request runs the isolated 12-test contract suite and checks the actual current tracked database. It derives the current New York-local reporting Saturday and source-as-of date; on weekdays it correctly produces a **partial-week** status rather than asserting premature Sunday readiness. Future manual runs on `main` produce the corresponding updated metadata report. Only an unapproved JSON metadata artifact is retained for 30 days. GitHub token is read-only; no source originals or unpublished manuscripts are uploaded.

This PR can merge independently of #237 and does not touch any shared writer, source manifest, Friday retired email workflow, country desk, SQLite, output or delivery variable.

## Relationship to Japan and Vietnam

The Sunday manuscript may consider **bounded, typed, unapproved official-source research**, independently of this production-corpus check. Such items are not production records and cannot fix the preflight's two-production-desk requirement or invent a country-desk collection day. The current five-item Japan/Vietnam research packet is only for the week ending October 10, 2026; the permanent source feeder remains tracked in [Issue #200](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/200).

**For October 11:** full-week production success, a working Sunday model draft and private owner review are separate gates. The preflight passing cannot activate Dylan delivery or overrule human source review.
