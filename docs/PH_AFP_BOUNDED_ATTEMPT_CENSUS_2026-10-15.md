# Philippines AFP — bounded per-attempt Actions verification (October 15, 2026)

## Status and purpose

This is a **manual-only extension** of the existing October 7–13 Day-7 audit. It is not an executed audit receipt, original-language human review, reuse-rights finding, source promotion, Sunday-model grant, editor-email authorization, or publication.

The existing manual Day-7 workflow reconciles seven successful shadow ledgers with GitHub's current workflow-run records. A current GitHub run object reports its latest attempt. It cannot alone establish that historical rerun attempts and their failed jobs have been inspected. The supplementary Python auditor now asks GitHub for **each numbered attempt and every job page of every run ID visible in that exact workflow-run export**.

### Exact workflow

After reviewed merge and green exact-head PR CI, an operator may choose **Actions → Philippines AFP pinned Day-7 machine evidence (manual) → Run workflow**, branch main, explicit as_of=2026-10-14 (or a later valid UTC cutoff). This workflow:

1. Verifies the exact frozen shadow/ph-afp SQLite, ledger and source-capture commitments without changing them.
2. Downloads the complete bounded ph_afp_shadow.yml GitHub workflow-runs list for October 7 through the UTC cutoff, **without filtering event or conclusion**; checks seven date-specific ledger/Actions matches and rejects unmatched in-window scheduled run IDs.
3. **Independently fetches every attempt** numbered 1..run_attempt for each visible run, including unsuccessful and manual runs, and all associated job pages through GitHub's read-only REST API. Requires exact run ID, workflow ID, source SHA, attempt number, date, event, branch, job ownership and pagination. Each of the seven positive first attempts must have completed successful jobs. A missing historical attempt, failed positive-day job, unexpected schedule or inconsistent API response stops the manual run.
4. Only after all checks pass, creates a **metadata-only** bounded attempt/jobs receipt and machine verdict. Removes the raw workflow-run export from runner temporary storage, including on failure, before metadata-only artifact upload.

No historic job logs, original publisher responses, government article text, photographs, workflow tokens or raw API dump enter the uploaded receipt. No GitHub write permissions, production DB/manifest changes, source collector changes, model calls, SMTP or deployment are made.

### What a green result means — and does *not* mean

A positive result means all **currently visible** runs returned by the bounded GitHub workflow-runs query had all their numbered attempts and jobs examined, and the seven fixed October 7–13 positives were successful scheduled first attempts with job evidence. A GitHub query is not a cryptographically complete history of deleted runs, expired artifacts or past logs. Those limitations remain reported as **false**; the cross-desk private evidence vault/independent backup program is a separate dependency.

The actual first formal manual audit still needs to be dispatched and its resulting run URL, pinned state SHA, job outcome, artifact expiry and verdict inspected. **Do not report a machine pass based on synthetic CI alone.** If the run is red, do not silence it by excluding attempts, changing the fixed review dates, weakening identity checks or copying originals into main.

### Human review after technical reconciliation

The AFP source review remains **unsigned**. The preserved 22 originals consist of 13 October 7 inserts, five October 8 inserts and four October 14 inserts. Generate and check original-version-bound review packets for each actual insertion batch using the existing per-run review and review-docket scripts. Compare the archived publisher source bytes, identity, event dates, quotations and AFP vs NSC attribution. A source reviewer must record an actual version-bound decision and the separate rights/noindex/media disposition. A green Day-7 machine receipt **does not** sign or validate any of these decisions.

### Synthetic verification

Run the four focused test modules: test_ph_afp_seven_day, test_ph_afp_actions_provenance, test_ph_afp_attempt_history, and test_ph_afp_day7_machine_workflow.

Require repository-wide exact-head CI, an isolated changed-file review, and unchanged tracked production DB/site output before merge. The add-on's maximum 150 visible runs / 20 attempts per run / 1,000 jobs per attempt is a refusal bound, **not** permission to truncate a larger API census. If exceeded, stop and scope a reviewed verifier change; never silently skip data.
