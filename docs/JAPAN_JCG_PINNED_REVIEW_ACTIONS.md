# Japan Coast Guard — manual pinned review Actions

**Read-only; no source approval or automatic production eligibility.**

This is a companion to `docs/JAPAN_JCG_FIRST_SHADOW_RUNBOOK.md`. The first Coast Guard shadow collection is installed on `main` through [PR #212](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/212). It is **manual-only** and uses the separate `shadow/japan-jcg` state branch.

## Step 1 — first genuine collection (owner-only)

Go to **GitHub → Actions → Japan Coast Guard — Manual Isolated Shadow Pilot**. Run the workflow on `main` with an explicit UTC logical `target_date` (initially `2026-10-08` if reviewing that reporting date). Inspect the job's conclusion, its recorded `health` and its `result` **separately**. A workflow that is green does not itself mean the source qualifies for production.

Only an accepted run publishes immutable original-body captures, database state and ledger under `shadow/japan-jcg`. Its new state commit must be read from the actual Git branch after the workflow completes. **Do not invent or copy a commit from the collector source branch.** A partial/failed attempt is not a successful shadow day.

## Step 2 — pin and inspect without local commands

After the first persistent state commit exists, go to **GitHub → Actions → Japan Coast Guard — Pinned Shadow Review (Read Only)** and select `main`. Enter:

- `state_commit`: exact, full 40-character lowercase SHA of the commit on `shadow/japan-jcg`, obtained from the branch/history.
- `as_of`: intended UTC review cutoff, in `YYYY-MM-DD` format. For the initial `2026-10-08` run, use `2026-10-08`.

The review workflow validates the fields, clones **only** the named state branch read-only, and uses `scripts/review_desk_shadow.py --state-repo ... --state-commit ...`. The existing formal reviewer proves that the supplied commit is an ancestor of `shadow/japan-jcg`, contains only allowlisted state files, and carries ledger/capture/record hashes that still match. It reports original-date and institutional-scope exceptions.

The Actions artifact contains **only** `receipt.json`, `formal/report.json` and `formal/report.md`; original source text, `records.jsonl`, HTML and binary captures are deliberately not uploaded by this workflow. A separate authorized source reviewer can retrieve the originals from the pinned state branch when comparing publisher webpages and attachment PDFs.

**A machine-clear result is not a human approval.** Every receipt explicitly records `human_review_completed: false`, `promotion_authorized: false` and `editorial_release_authorized: false`. Existing Day 7/14/30 human checkpoints and 30 healthy collecting days remain mandatory. PDF-linked content remains uncollected by the HTML adapter; see [JCG PDF-completeness PR #217](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/217) for the separate original-document research findings.

## Failure conditions and honest claims

- Missing `shadow/japan-jcg`, missing exact SHA, wrong/forged commit ancestry or unexpected files: **the formal review fails**. Do not convert a mutable state checkout or a guessed SHA into a review receipt.
- Incorrect dates, changed captures, missing successful daily ledgers or stale/unexplained HTML date attributes: machine findings or explicit human-review holds, not automatic approval.
- A failed formal integrity check can still produce read-only reports for diagnosis, but the workflow remains red and cannot authorize source promotion.
- No workflow here writes back to `shadow/japan-jcg`, production SQLite, output, registry or the AI writer. Only the separate, explicitly owner-triggered collection workflow may write the isolated state.
