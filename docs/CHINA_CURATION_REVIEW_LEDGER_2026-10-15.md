# China curation: machine-checkable editorial review ledger (15 October 2026)

**Status:** review-intake prototype; **no public editorial selection or publication**.
The actual corpus remains unchanged. This work prepares Phase 2 of
[issue #605](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/605),
alongside the source-screening and duplicate audits in PRs #603 and #612.
Historical Global Times extraction pollution is issue #613.

## The principle

A curator must be able to distinguish:

1. The **entire preserved corpus** — every stable ID, recorded title, original
   text, publication URL, date, processing outcome, citation and source trail.
2. The **review ledger** — sparse and versioned human disposition proposals,
   with explicit evidence, reason, and review stage.
3. The **future curated discovery view** — a *separate*, owner-approved and
   tested UI/product choice; never created directly from a machine flag,
   headline, score, repeated title, or this ledger alone.

A record **not listed in the review ledger is NOT an editorial rejection**.
It remains preserved, accessible in the full corpus, and awaits disposition.
When daily collection adds new records, review labels are not inherited by
the new records or inferred from the last approved batch.

## Decisions and stages

| Disposition | Meaning | Historical record |
|---|---|---|
| `retain_primary` | High-value original/official declaration or substantive development worth discovery prominence | Preserved |
| `retain_context` | Useful contextual, chronological or cross-desk evidence | Preserved |
| `group_secondary` | Secondary publication to a reviewed representative; provenance remains distinct | Preserved, never redirected away |
| `exclude_discovery` | Low priority for *primary curated discovery*; NOT a deletion | Preserved, searchable through full corpus |
| `hold_quality` | Contaminated or insufficient text, issuer, timing, provenance or other unresolved defect | Preserved with review hold |

The three stages are `triage`, `source_checked`, and
`owner_approved`. Only a `source_checked` record with an independent
evidence URL, named reviewer, dated and substantive checking note, identified
issuer (or explicit `unknown`) and quality assessment can proceed to
`owner_approved`. The approval stage also requires a **separate** named and
dated owner receipt; a `hold_quality` or contaminated/unknown capture cannot
be approved.

The validator checks the presence and consistency of **claimed** evidence
receipts; it does not contact the URL, independently confirm a claim, validate
the reviewer identity, or substitute for an owner's actual approval. A
malicious or inaccurate JSON entry does not become editorial fact just
because a validator returned exit code zero.

## What is already entered

`research/china/archive-curation-triage-2026-10-15.json` contains **seven**
concrete **triage-only** records: #2849, #2391 (prospective primary retained
declarations), #943, #2294 (context candidates), and #2180, #946, #2265
(quality holds). Every source check and owner approval is `null`; no
decision is publication-enabled. These are provisional hypotheses tied to
the October 14 stored-record source, original title, and date.

We intentionally do NOT pre-create thousands of `exclude_discovery` decisions
from a model label. That would wrongly turn automated screening and human
review omissions into purported editorial exclusions.

### Validation

```bash
python3 -m unittest tests.test_china_curation_review_ledger
python3 scripts/validate_china_curation_review.py \
  --index output/corpus-index.json \
  --ledger research/china/archive-curation-triage-2026-10-15.json
```

The CLI prints aggregate audit information only and **writes nothing**.
There are no network requests, LLM calls, database connections, migrations,
render calls, CSV exports, background jobs, or output updates.

It rejects duplicate IDs; wrong source, original-title or date; non-China
records; lost source-trail IDs; malformed evidence; invented approval stages;
owner-approved quality holds; unreviewed representative relationships; and
snapshots older or smaller than the ledger baseline. The baseline is not
silently refreshed. Later snapshots with additional records are **allowed**
and reported as advanced; those arrivals remain unreviewed until explicitly
added.

### Review protocol (next steps, not automatically executed)

1. **Source custody:** Compare original-language publisher capture,
   normalized republisher attribution, title, publication/event date,
   completeness and quote integrity; record the separate issuing institution.
2. **Evidence adjudication:** Describe what the item proves about official
   messaging, not that the publisher's assertions are independently true.
   Review the prior record and any linked Brief trail.
3. **Cross-publisher relationship:** Compare same-day titles *and actual
   bodies*. Recurring patrol headlines weeks apart are separate events;
   syndicated copies retain their own URLs.
4. **Selection decision:** Record one disposition and a specific reason,
   distinguish missing data from low editorial relevance, and give quality
   defects explicit holds.
5. **Second review:** Spot-check both proposed retains and excluded controls,
   especially original-language sources and events screened out by machine.
6. **Owner checkpoint:** Show the evidence and proposed reader-visible counts,
   then obtain explicit approval for the reviewed set. A source-level
   verification note is NOT that approval.
7. **Release candidate:** Only under a separate approved implementation,
   derive *curated* archive/home/finder from a frozen approved manifest while
   keeping a full-corpus route and every published record/legacy link. Retain
   the difference between collected, screened, verified and selected counts.
8. **Daily update:** Newly collected China records remain in the full corpus
   and an editorial pending queue; current publication selections are not
   automatically extended by a similarity match, title flag or model score.

**Stop point:** This PR ends at a demonstrably safe review schema, a seven-case
research example and contract tests. It does not render pages, edit the
database, change the collection pipeline, touch published Briefs, merge,
or deploy. Final release requires separate editorial and production approval.
