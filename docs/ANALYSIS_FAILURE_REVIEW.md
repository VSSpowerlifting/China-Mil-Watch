# Stored analysis failure-cause receipt — strictly read-only

This is a diagnostic companion to [Issue #268](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/268) and the merged source-attributed queue audit #280. It helps a human identify where to inspect extraction, retry behavior or contradictory processing metadata. **It does not certify causation, value, model readiness, or authorization to retry a record.**

## Usage

```sh
python scripts/audit_analysis_failure_causes.py --db pla_watch.db \
  > /tmp/ipr-analysis-failure-causes.json
```

The script invokes the **existing #280 categorizer on the same scratch SQLite connection** used for this report. It counts only records currently stored as eligible for China's Daily model queue, and separately preserves paused and terminal distinctions. It emits aggregate counts **by source and desk** of blank stored bodies, prior attempt counts, overlapping cases and missing publication dates, plus recorded reason codes. It flags contradictory processing metadata (such as a processed article with failed relevance, a terminal record with a retryable reason, or a paused record with a non-pause reason) **without rewriting that metadata or changing existing pipeline eligibility**.

The output includes only aggregate metadata and at most 12 article-ID review receipts per review flag. It does not include titles, URLs, article text, translated material, summaries, credentials or an API token. It checks the original SQLite DB and available WAL/SHM sidecar SHA-256 fingerprints both before and after a read-only scratch-copy audit. The hashes are a **local identity only**, not proof of an authenticated live production state.

## Interpretation

- Blank body: **potential extraction/adapter problem**, not a verified empty publisher article or an automatic permanent disposition. Check the original source and the adapter before spending model tokens.
  The receipt splits blank-body records by **stored scrape age** against the configured 14-day UTC live window, with missing dates separate. This prevents an older stored extraction failure from automatically being misrepresented as a defect in the current adapter. Global Times already has September 16, 2026 flow-template extraction regression fixtures; source-level blank counts alone cannot establish that repair has regressed.
- Prior failures: **recorded attempt history**, not proof that retries will be unsuccessful. Inspect `processing_reason` to distinguish `transient_failure`, `analysis_failed`, `analysis_incomplete` and `empty_body_unconfirmed`.
- Overlap: count records with *both* blank body and prior failure explicitly. **Do not add the two marginal counts and call them distinct affected articles.**
- Contradictory states: a human review flag. Legacy records or incomplete metadata may explain some; the audit does not auto-correct or retroactively reclassify them.
- Paused/terminal: separate from the Daily-eligible backlog. Only a reviewed action may resume paused records; deterministic terminal records are not automatically resumed.

The script explicitly returns `model_spend_authorized=false`, `retry_authorized=false`, `publication_authorized=false`, `root_causes_established=false`, `model_calls=0` and `writes=0`. A read-only diagnostic is not a scheduled model run or publisher silence assertion.

Dedicated PR CI must exercise synthetic reason/state fixtures, full source accounting, real tracked-database smoke, output text non-disclosure and original database/output byte preservation. The full PR offline/Chromium/render checks are additional required merge gates.
