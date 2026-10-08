# Japan Coast Guard — shadow qualification evidence status

**Purpose:** a repeatable, read-only progress report showing which UTC days were actually collected, which collection attempts failed, and whether Day +7 / +14 / +30 checkpoints are **due**. It never decides whether Japan can become a production or weekly AI-writer desk.

## Evidence, not elapsed-time promotion

JCG's first persistent shadow state was created by [run 37828199188](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37828199188) with original state commit `81558026117067cbcf54bd7a7859a2d9db168a0c`, containing three English HTML-body records and a genuine October 8, 2026 Day 0 ledger. The source remains Japan **Coast Guard**, not Japan MOD, and excludes attached PDFs.

The status tool reads the **actual pinned shadow state tree**, validates the Day 0 clock and run ID, checks SHA-256 continuity between successive ledger database states, verifies that every referenced publisher HTTP capture still hashes to its recorded digest, and confirms the final database matches the last ledger. It then calculates a per-date table for every UTC day from the true Day 0 through the explicit cutoff.

It **does not infer collecting days from article publication dates** and never treats a review, parser test, historical upload or GitHub Actions success alone as a collecting-day ledger. A legitimate original listing with zero new publications can count if collection actually completed healthily with no failed source access. Multiple attempts for a single logical day and failed requests remain anomalies requiring documented disposition even if a later replay succeeds.

The contemplated two-release September historical backfill in [PR #230](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/230) would be marked `operation=jcg_2026_09_historical_backfill`, `counts_as_qualifying_shadow_day=false`, and `shadow_day=null`: these entries are counted as **historical content imports**, not as new collection days. Any attempt to relabel a backfill as a collecting day or break the state-hash chain causes the report to refuse the snapshot.

## Outputs and use

The tool is `scripts/jcg_shadow_qualification_status.py`. The [read-only Actions workflow](../.github/workflows/jcg_shadow_qualification_report.yml) uses the verified Day 0 snapshot for its PR acceptance test. After merge, an owner may also run it manually from Actions with **exact** `shadow/japan-jcg` commit SHA and a desired as-of UTC date.

The workflow clones only the branch that stores shadow state, proves the SHA is a branch ancestor, checks out that exact commit, and runs unit tests plus the reporter. Only **metadata JSON** is uploaded (never original HTML/PDFs, extracted article text, SQLite database or captures).

The report includes:

- frozen state commit, original day-zero run and database digest;
- total stored records and ledger entries;
- true successful collecting days, first-gap consecutive streak, missing/unhealthy days, historical content-import runs and unresolved anomalies;
- Day +7, +14 and +30 checkpoint dates and machine-only verdicts: `not_due`, `evidence_gaps_or_anomalies_require_disposition`, or `human_checkpoint_required_not_approved`.

No value in the machine output can sign off content rights or editorial review. All fields for `human_checkpoint_reviews_completed`, `source_rights_human_review_completed`, `source_pdf_completeness_human_review_completed`, `owner_promotion_authorized`, `production_eligible` and `weekly_writer_eligible` remain **false**.

## Cautions

A gap is a gap. Do not change an older immutable ledger or invent a successful historical collecting day to make a checkpoint green. Scheduling requires the separate owner-controlled `JCG_SHADOW_DAILY_ENABLED=true` repository variable; installing this workflow does not set it.

The existing formal reviewer (source hashes, original publication dates, scope, publisher template defect) and independent Day +7 / +14 / +30 **human reviews**, rights review, companion PDF adjudication, 30 consecutive days and owner decision log remain governing prerequisites under `docs/DESK_STRENGTH_CRITERIA.md`. This read-only status check is supporting evidence only.
