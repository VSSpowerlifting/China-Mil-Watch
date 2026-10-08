# AFP shadow — independent GitHub Actions run reconciliation

**Purpose:** Give the AFP seven-day collection audit (#183) a separate, inspectable check of actual GitHub Actions positive schedule-run outcomes. This gate neither replaces original-source human review (#178/#185) nor declares the Philippines Desk qualified. It does not collect Philippine pages or modify a database, shadow branch, production manifest, output or AI-writer input.

## Historical positive runs independently inspected October 8, 2026

| Logical date | State-branch run ID | GitHub run | Workflow event | Result | GitHub head SHA / AFP collector SHA |
|---|---|---|---|---|---|
| 2026-10-07 | 37631681338-1 | https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37631681338 | schedule | completed/success | 5ccc20ff94131f63d639aed840633776b829ef60 |
| 2026-10-08 | 37788547061-1 | https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37788547061 | schedule | completed/success | 5066f45e78ab6316034d74154d943aca9cf17f7d |

Both belong to GitHub workflow ID 376813005, **Philippines AFP Shadow Collection**. Their ledger records independently report 13 and five new articles. These are TWO supported dates; October 13 is the earliest seventh scheduled logical date. This lookup does not certify that every failed run/attempt was enumerated.

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
