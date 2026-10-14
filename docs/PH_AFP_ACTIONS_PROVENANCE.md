# AFP shadow — independent GitHub Actions run reconciliation

**Purpose:** Give the AFP seven-day collection audit (#183) a separate, inspectable check of actual GitHub Actions positive schedule-run outcomes. This gate neither replaces original-source human review (#178/#185) nor declares the Philippines Desk qualified. It does not collect Philippine pages or modify a database, shadow branch, production manifest, output or AI-writer input.

## Historical positive runs independently inspected October 8, 2026

| Logical date | State-branch run ID | GitHub run | Workflow event | Result | GitHub head SHA / AFP collector SHA |
|---|---|---|---|---|---|
| 2026-10-07 | 37631681338-1 | https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37631681338 | schedule | completed/success | 5ccc20ff94131f63d639aed840633776b829ef60 |
| 2026-10-08 | 37788547061-1 | https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37788547061 | schedule | completed/success | 5066f45e78ab6316034d74154d943aca9cf17f7d |

Both belong to GitHub workflow ID 376813005, **Philippines AFP Shadow Collection**. Their ledger records independently report 13 and five new articles. These are TWO supported dates; October 13 is the earliest seventh scheduled logical date. This lookup does not certify that every failed run/attempt was enumerated.

## October 14, 2026: first seven-day positive-run reconciliation

The separate source branch `shadow/ph-afp` now contains eight individually inspected, successful **scheduled logical-date ledgers** for October 7–14. I compared each exact stored `run_id` to the corresponding **live GitHub Actions run metadata** on October 14. All eight runs were `event=schedule`, `status=completed`, `conclusion=success`, `run_attempt=1`, `head_branch=main`, and workflow ID `376813005` (`Philippines AFP Shadow Collection`). **Every** run's GitHub `head_sha` matched the source ledger's `collector_commit` exactly, and the API `created_at` date matched the ledger's reporting date.

| Logical date | Run ID (attempt 1) | Collector SHA (prefix) | New | Duplicate | Final corpus |
| --- | --- | --- | ---: | ---: | ---: |
| Oct 7 | [37631681338](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37631681338) | `5ccc20ff` | 13 | 0 | 13 |
| Oct 8 | [37788547061](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37788547061) | `5066f45e` | 5 | 13 | 18 |
| Oct 9 | [37938647189](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37938647189) | `0e1b6b75` | 0 | 18 | 18 |
| Oct 10 | [38054020491](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38054020491) | `f25378fb` | 0 | 16 | 18 |
| Oct 11 | [38143215597](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38143215597) | `39b40bb7` | 0 | 16 | 18 |
| Oct 12 | [38274471323](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38274471323) | `25e6024d` | 0 | 14 | 18 |
| Oct 13 | [38414155939](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38414155939) | `22627423` | 0 | 14 | 18 |
| Oct 14 | [38562843186](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38562843186) | `bd727f74` | 4 | 14 | **22** |

**Positive machine evidence:** All eight ledgers report healthy `ok`/`ok_all_duplicates` status, `robots_status=allowed`, `listing_status=ok`, and exactly **zero fetch, extraction, access and redirect failures**. The first seven **distinct consecutive logical dates** (Oct 7–13) therefore have their corresponding positive scheduled Actions runs and source ledger receipts independently matched. Oct 14 adds a clean eighth observed logical-date receipt and four original-text captures. The ledger's `shadow_day` is based on elapsed 24-hour periods (and even repeats 1 or 6 across different dates); it is **not** the qualifying-days denominator.

**Limits that must remain explicit:**

- This was an **eight-positive-run spot reconciliation**, not the formal seven-day verifier on a frozen, authenticated source Git commit and SQLite/capture set. The full `scripts.audit_ph_afp_seven_day` and `scripts.audit_ph_afp_actions_provenance` commands still need execution against a pinned source branch and complete correctly scoped Actions export. The eight successful runs do **not** prove there were no other failed, canceled or rerun attempts.
- No original AFP text, listing body, images or private reviewer notes were copied into this document. Neither GitHub's successful conclusion nor the ledger proves human source fidelity or authorized reuse.
- The **Oct 7 Day-0 cohort contains 13 originals** (the original Day-0 queue covers all), Oct 8 added 5, and Oct 14 added 4. Under the existing per-insertion sampling rule, the minimum source-review workload is five for Oct 7, five for Oct 8, and all four for Oct 14, but **no such reviews are represented as completed**. Human review of the full original Day-0 set may be preferable; 5 is only the documented minimum for >5 new records. The exact original IDs for Oct 14 require source-branch per-run packet generation, not deduction from counts.
- The isolated Philippine National Security Council collector is a separate source with its own quiet and active slots. Neither NSC success nor its reported absence of new publications substitutes for AFP review, and this report is not evidence that the Philippines institutions were publicly silent.
- **No Philippine production admission or weekly AI eligibility is granted**, and no source-use, rights, human original-language review or publication gate is changed.

**Next operational action:** Pin the latest `shadow/ph-afp` commit; execute the full seven-day ledger/capture audit and Actions attempt census; prepare the Oct 14 per-run review packet under an access-controlled workspace; route unsigned originals to a genuine reviewer. Do not invent signoffs or change the production registry based on this snapshot.

## Produce a reproducible export locally

Explicitly fetch the isolated AFP state branch into an authorized local checkout and record a literal historical 40-character commit. Authenticate GitHub CLI with Actions read access. Collect ALL AFP workflow events in the intended UTC window, not only successful scheduled runs (filtering those would conceal negatives). Save the original API export to a private local path.

    gh api --paginate --slurp -X GET \
      'repos/VSSpowerlifting/China-Mil-Watch/actions/workflows/ph_afp_shadow.yml/runs?created=2026-10-07..2026-10-13&per_page=100' \
      > /secure/ph-afp-actions-pages.json

    python3 -m scripts.audit_ph_afp_actions_provenance \
      --state-repo /path/to/repository-containing-shadow-state-history \
      --state-commit LITERAL_40_CHARACTER_GIT_COMMIT \
      --as-of 2026-10-08 \
      --actions-export /secure/ph-afp-actions-pages.json \
      > /secure/ph-afp-actions-reconciliation.json

The tool accepts one GitHub REST response or the array of pages produced by --paginate --slurp. All pages must share the same total_count; unique IDs must equal the total. Missing pages, duplicate IDs or changing totals fail closed. Retain the API export and the time it was captured for an independent human to compare online.

The verifier binds each eligible pinned ledger to the GitHub run ID *and attempt*, the configured workflow ID/name, scheduling event, main branch, exact collector SHA, completed successful conclusion and same-day UTC creation. It refuses to silently count a wrong-day run, a manual dispatch, an altered SHA, or a failed/missing action. Extra scheduled runs absent from the successful durable ledger appear in a separate list for investigation.

## Standing limits

- Operator-supplied JSON can be modified or queried with incomplete filters. Matching an API total_count does not independently authenticate the export's query scope or its historical responses.
- The workflow-runs endpoint does not establish the complete history of failed and rerun attempts; separately inspect individual run attempts, jobs and saved artifacts.
- Even seven matching positive runs do not establish human source-review completion, original-source accuracy, independent corroboration, source indexing/reuse rights or editorial approval.
- The report **always** denies production eligibility and weekly AI-writer eligibility. It authorizes no database, rendered output or state write. Do not substitute Philippine NSC runs, silently approve AFP originals or feed shadow records to the model.

Verification: python3 -m unittest tests.test_ph_afp_actions_provenance -v. Run full CI and DB/output preservation before merging. This is independently scoped and does not depend on unfinished AFP admission-preflight PR #213.
