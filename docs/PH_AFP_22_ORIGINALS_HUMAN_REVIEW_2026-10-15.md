# Philippines AFP: first 22 preserved originals — consolidated unsigned review

**October 15, 2026.** This handoff creates one reviewer-friendly metadata roster for the existing 13+5+4 original AFP records, not a new collector, human signoff, copyright grant or production admission.

## Original evidence pinned by capture run

| Original inserted | Logical date | Scheduled run / attempt | Immutable state SHA |
| ---: | --- | --- | --- |
| 13 | 2026-10-07 | 37631681338-1 | `492001f34ba6176169b6acc96a237f05592a3395` |
| 5 | 2026-10-08 | 37788547061-1 | `c668790ce3be88b08b3300b945bad58589b3a5b1` |
| 4 | 2026-10-14 | 38562843186-1 | `4dd40b9655ec53fe4fae829eb12ba21032946b25` |

The three commits are in the existing `shadow/ph-afp` branch. Each contains original evidence and the exact per-run ledger. The workflow refuses a missing/nonancestor commit or a non-state-only Git root. It builds the roster with the existing source-capture/DB/ledger-bound `scripts.prepare_ph_afp_run_review` and `scripts.prepare_ph_afp_review_docket` routines, not speculative text or new publisher fetches.

## How the owner initiates the genuine review roster

After reviewed merge and CI, select **Actions → AFP first 22 originals — unsigned consolidated human review docket → Run workflow**, ref `main`. Inspect the run's metadata-only artifact `ph-afp-22-unsigned-review-<run_id>` and ensure exactly 22 distinct original IDs, three pinned batch identities, no unavailable bodies, and every review status `not_started`.

**The roster contains only** original publisher title, first-party link, publication date, source ID, SHA-256 identity digests, source-capture versions and pending flags. The captured body, original API JSON, photographs and attachments stay inside the temporary runner. Public or private upload of raw original bodies is not part of this workflow. The uploaded metadata roster is retained for seven days.

A real reviewer must still use the owner-controlled private per-run packet tooling to read the **actual preserved original** for all 22 cases and record for each: issuer and date, original-text fidelity, claim modality, correct quotation/attribution, duplicates or republished claims, independent corroboration when warranted, and rights/noindex/image-use restrictions. Reviewer identity and version-specific decisions must be independently attested; an unsigned `not_started` docket is not a vote.

## Public feasibility sequence

1. Complete the Day-7 Actions attempt/job audit after PR #633 exact-head CI and reviewed merge, then separately dispatch its manual evidence workflow.
2. Use this docket as a 22-item *human-review* workload register. Preserve all rejected or disputed original captures in restricted evidence custody; do not silently delete them.
3. Keep a separate rights decision for metadata links, short independently authored commentary, full original body storage, images, and model use; inspect publisher-specific `X-Robots-Tag` and terms.
4. Preserve the Day-14 and Day-30 **future** collecting-day checkpoints and independent human decisions. For the October 7 Day 0, November 5 is the **earliest possible** 30th date, not an assurance of continuity.
5. Only a separate, explicitly approved production-release PR may change the registry, archive DB, published website, Sunday writing or editorial email. Link-only public reference material remains a different, narrower question.

No reviewer signoff, rights approval, production eligibility, public release, email or model call occurs here.

## Offline verification

On the PR head, run `python -m unittest tests.test_ph_afp_review_docket tests.test_ph_afp_run_review tests.test_ph_afp_all22_review_docket_workflow -q` and repository-wide tests. Confirm `pla_watch.db` and `output/` remain byte-identical to the PR base. The genuine manual workflow has **not** been executed merely because PR CI is green.
