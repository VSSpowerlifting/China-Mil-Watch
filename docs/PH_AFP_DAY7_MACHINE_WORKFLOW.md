# Philippine AFP — manual Day-7 machine receipt

**Status:** reviewer-facing workflow proposal only. This is not a human source-review record, reuse-rights assessment, desk graduation, editor-email permission or weekly model authorization. No original article body is added to `main` or to the uploaded artifact.

## Purpose

The AFP seven-day machine auditors already exist, but previously required an operator to combine a live immutable `shadow/ph-afp` checkout, full GitHub Actions export and two local commands. `.github/workflows/ph_afp_day7_machine_receipt_manual.yml` packages those operations behind a **manual-only read-only** GitHub Actions workflow, with no schedule and `contents: read, actions: read` permissions.

This follows the [October 7–14 positive-run cross-check](PH_AFP_ACTIONS_PROVENANCE.md) without rewriting that dated evidence. The earliest seven consecutive AFP logical dates are October 7–13, 2026.

## How to inspect (after reviewed merge)

Select **Actions → Philippines AFP pinned Day-7 machine evidence (manual) → Run workflow**, ref `main`. Leave `as_of` as the explicit UTC review cutoff (`2026-10-14` for the inaugural review), or name a valid later cutoff up to the current UTC date. The workflow rejects an earlier-than-Oct-13 or future date. A reviewer may repeat it after more data arrives, but the seven-day window remains exactly October 7–13 unless this workflow is deliberately revised.

It independently executes:

1. Source-audit and Actions-provenance synthetic contracts.
2. Read-only clone of `shadow/ph-afp` into GitHub's temporary runner directory, refusing branch misidentity and any path besides `state`, pinning the **literal current 40-character commit SHA**, and running `audit_ph_afp_seven_day.py` against that frozen state and original preserved SQLite/capture hashes.
3. Full paginated GitHub Actions workflow-runs API export for `ph_afp_shadow.yml` over October 7 through the chosen cutoff. The query deliberately does **not** pre-filter to successful or scheduled runs. It invokes `audit_ph_afp_actions_provenance.py` on the entire API export, then removes the raw export before upload. This is **positive-run matching**, not exhaustive per-attempt failure/cancellation authentication.
4. A machine-only verdict. Seven matched positive runs alone are not enough for a positive receipt if the supplied workflow-run export also shows **an unmatched scheduled run created during October 7–13**. Such runs require an explicit `review_hold`, regardless of whether the additional run succeeded, failed, or was cancelled; an unmatched schedule with an unparseable creation date is also held. The machine receipt includes the **count** of these visible ambiguous runs and the separate Actions assessment retains their metadata. A valid scheduled October 14 run is outside this fixed seven-day window and is disclosed without automatically blocking it.
5. Only when all seven positive source/Actions matches exist **and** no extra in-window scheduled run is visible in the supplied export may the verdict be `positive_seven_slots_machine_only`. It still sets every human, source-rights, AI, email, admission and publication authorization field to **false**. Any insufficient or ambiguous machine evidence produces `review_hold`.
5. A private 30-day retained **metadata-only** artifact: exact pinned state SHA, ledger assessment, Actions-positive matching assessment and final machine verdict. The original AFP database, captured original texts, attachments, source-response bytes, raw Actions export and tokens are **never uploaded**.

This workflow does not itself certify that an Actions export came from every relevant run attempt, that the publisher material is accurate, that a rights agreement applies, or that a human reviewer completed any original-source inspection. Those are independent gates.

## Next meaningful work after machine success

The human source-fidelity package remains unsigned. AFP's original first batch has 13 captured originals, Oct 8 added five, and Oct 14 added four. Per-run reviewer packets must be generated and assessed against the actual archived API originals, with exact commit and reviewer evidence. The API `noindex, nofollow` observation and any text/image reuse limitations require a separate disposition. NSC remains an independent supporting source, not an AFP substitute.

**Stop condition:** machine assessment completed and held for human review. Never update `desks/`, production registries, `pla_watch.db`, `output/`, source admission switches or the Sunday manuscript feeder simply because the report is green. A genuine human owner/source decision and an independently reviewed release remain necessary.

## Offline verification

`python -m unittest tests.test_ph_afp_day7_machine_workflow tests.test_ph_afp_seven_day tests.test_ph_afp_actions_provenance -v`

Require exact-head CI, zero database/output differences, and owner review before merge. No workflow dispatch is part of this PR.
