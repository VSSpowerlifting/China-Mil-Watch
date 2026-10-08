# Philippines AFP — seven-day scheduled shadow evidence audit

**Status:** read-only reviewer infrastructure. This tool neither starts the collector nor establishes institutional coverage, archive rights, editorial review completion or production readiness. It computes a **ledger-supported machine evidence gate**, not a success claim about externally unverified GitHub Actions events.

The Philippines AFP collector is scheduled at **06:40 UTC**, has a 14-day source window and a hard 100-item cap. Its first confirmed complete scheduled shadow run was **October 7, 2026**, run `37631681338-1`. That run created day zero and archived 13 full-text documents. The completed Day-0 review-queue infrastructure merged in PR #178, but no person is represented as having reviewed those bodies.

## Why this gate exists

A `shadow_day` counter is elapsed time since the initial clock, **not** a proof that every intervening scheduled date succeeded. Furthermore, the public `shadow/ph-afp` state branch holds only commits that passed verification and were published; failures may exist only in GitHub Actions logs and artifacts. Counting seven successful-looking ledger files, or seeing `shadow_day >= 7`, is insufficient.

Seven consecutive **scheduled logical dates** are necessary for the first AFP reliability checkpoint. Each day must have exactly one unambiguous qualifying completed ledger with original request evidence, listing completeness, source policy, collection-status fidelity and capture-state integrity. All human source-integrity signoffs and Actions run provenance are **separate, mandatory reviews**.

## Running an immutable offline audit

Use an ordinary Git checkout of the repository that **already contains** the explicitly fetched `shadow/ph-afp` state history. Record the exact full commit SHA first. The command takes only a *literal full 40-character Git SHA*, never `HEAD`, `main`, or a moving `shadow/ph-afp` ref:

    python3 scripts/audit_ph_afp_seven_day.py \
      --state-repo /path/to/repository-with-afp-state-objects \
      --state-commit <exact-40-character-state-commit> \
      --as-of 2026-10-08 > /tmp/ph-afp-seven-day-evidence.json

The initial seven-day window is **October 7–13, 2026**, inclusive. Specify an explicit later `--start-date YYYY-MM-DD` if investigating an alternative *consecutive* seven-day period. The required `--as-of` is a UTC date used only to distinguish future slots from already-due slots; this tool does not silently consult the machine's local clock or assign collection times.

The program performs **zero network calls**, **zero edits**, **zero ledger publication** and **zero production database interactions**. A temporary immutable SQLite copy is discarded. Git object access is fail-closed if the historical object was never fetched, the commit is not a literal SHA, the path is missing, or the stored Git blob fails its digest check.

## What is measured

Each of the seven date slots is clearly reported as:

- `ledger_success_unverified_actions`: exactly one eligible claimed scheduled event, healthy complete collection, allowed source access, fully reconciled listing, zero failures, exact source receipts, with **GitHub Actions event/outage evidence still unverified**
- `missing_scheduled_ledger`: no qualifying source-date ledger is present in this pinned state commit
- `future_not_due`: the target date falls after the explicit `--as-of` date; this is **not** failure
- `invalid_ledger_evidence`: a required success/identity/window/receipt rule failed
- `ambiguous_multiple_scheduled_ledgers`: duplicate scheduled ledgers for one logical date, requiring investigation before any count

A quiet window with verified reconciliation and `ok_no_publications` counts at the ledger level; no source publication is invented. Manual `workflow_dispatch`, rehearsals, successful partial collections, failed attempts, missing source receipts, altered policy/listing payloads and multi-attempt ambiguity do **not** count.

The gate also reads only the latest committed SQLite snapshot, verifies integrity, validates original saved API response SHA-256 hashes, matches each stored body to its preserved extracted-text SHA-256, and requires that the last ledger's corpus count/hash match that snapshot. Historical intermediate rows are **not** falsely claimed to have been rechecked against their day-of-run bytes; the separate append-only publication checks govern that. Audit results show the minimum **required number** of manual reviews for each supported slot (all new records if five or fewer, otherwise at least five), **not** that any review has happened.

## Required actions before a reviewer can recommend graduation

1. Inspect the exact **GitHub Actions run and attempt** for each scheduled date. Match workflow name, trigger/event, logical slot resolution, collector SHA, resulting Git state commit and completed job steps. Inspect **failed and canceled runs**, which can be absent from the state branch. A corresponding state ledger alone cannot authenticate the trigger.
2. Review retained request receipts, original policy/listing payloads, any challenge or refusal evidence, and full rendered/logical dates. Confirm that source access did not degrade over seven consecutive days.
3. Review actual AFP archived full-body source text, at least the number reported by the tool (five new records per insertion batch larger than five, otherwise every new record). Reviewers must attribute identity and record actual fidelity findings. PR #178's unsigned full-13 Day-0 queue supports this, but merging #178 alone does not meet this checkpoint.
4. Independently review publisher-date precision, AFP institutional scope, NSC supplemental reliability, gaps at DND/Philippine Coast Guard, pre-activation historical coverage and source reuse/republishing rights.
5. Record an **explicit human owner decision** separately. The script intentionally emits `human_review_completed_or_verified: false`, `github_actions_event_and_failure_artifacts_independently_verified: false`, `philippines_desk_qualified: false`, and `production_admission_authorized: false` **even after seven mechanically supported ledger slots**.

Do not update production registry, `desks/`, `pla_watch.db`, `output/`, task classifications or a publication pipeline on the basis of this scorecard.

## Testing

    python3 -m unittest tests.test_ph_afp_seven_day -v

The tests use only synthetic ledgers, disposable SQLite archives and temporary Git commits. They cover missing dates, future dates, quiet windows, duplicate or manual slots, refusals, incomplete listings, changed request evidence, broken body/capture hashes, and moving-ref refusal. **These tests are not real AFP source reviews.**

This is a separate source-readiness component from PR #99 (NSC parser refusal guard), #177 (blinded HADR review logistics) and #178 (AFP Day-0 human review). No source schedule or source adapter behavior is modified here.
