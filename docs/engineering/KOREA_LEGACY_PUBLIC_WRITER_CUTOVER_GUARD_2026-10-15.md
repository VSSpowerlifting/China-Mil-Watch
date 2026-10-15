# Korea writer cutover — legacy public writer interruption guard

**Owner review only, October 15, 2026.** This engineering change adds fail-closed checks to the *existing* [combined Indonesia–Korea workflow](../../.github/workflows/indonesia_korea_shadow.yml). The active mode remains **legacy public shadow**. The separate private Git evidence vault exists, but no Korean HWPX originals have been transferred or restored there; #520 remains open. This PR does not deploy or activate a private Korea writer.

## Current behavior (unchanged in the approved policy state)

The original scheduled workflow still selects Indonesia at **17:17 UTC** and Korea at **17:47 UTC**, runs the source collector, and commits to each separate current public orphan branch. The new Korea-only guard reads [the checked-in pinned policy](../../config/korea_shadow_writer_policy.json) twice:

1. **Before checkout/source access:** verify Korea is still explicitly in `legacy_public_shadow`, with correct branch, exact original day-zero timestamp and seed run, and **all private/cutover/production flags false**. Any missing, extra, modified or malformed field stops the job *before* touching sources or candidate state.
2. **Immediately before Git staging and public push:** re-run the same check. Even if another workflow step or later refactor attempted a private/dual-writer policy, the old branch writer must fail closed rather than writing government originals to the old public ref.

The guard accepts only those pinned legacy-state fields and two named checkpoints; it is intentionally **not capable of approving private operation or production admission**. A legitimate future migration must explicitly change this policy and implement an independently protected private writer with its own proof and owner authorization. Merely changing `mode` to `private` now causes the legacy collector to halt; there is no automatic fallback to its old public branch.

For Indonesia, selection, schedule, writer, artifact retention, source importer and credentials remain identical. There is no Indonesia policy read or new guard execution in the live workflow. Existing Korea metadata-only Actions artifact settings and all ledger/source-review/publication/AI/email holds remain intact.

## Requirements before a future controlled switch

- Verify the real destination `VSSpowerlifting/ipr-source-evidence-private` is private **and** its collaborators, fork policy, secret usage and backup/restore procedure have been approved; [vault #1](https://github.com/VSSpowerlifting/ipr-source-evidence-private/issues/1) remains open.
- Obtain independent source-specific retention/rights approval for the original HWPX and any embedded media; KOGL text-only marks do not automatically authorize entire HWPX transfer or public release.
- Complete approved hash-preserving archive copy, verify *all* captured bytes and Git ancestry via [#616](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/616) (merged), reconcile historical failed-run originals via [#619](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/619), and test an **independently encrypted backup restore**. The October 12 historical scheduled failure remains failed.
- Prepare a **separate, explicitly owner-approved, exact-head full CI** cutover PR that provisions a private-only Korea writer, proves no overlapping writers, disables the Korea legacy job without touching Indonesia, preserves clock/ledgers, prevents original data in public Actions or logs, and verifies new genuine scheduled private-store collections.
- Obtain separate reviewer/rights/owner admission for Sunday editorial input; publication, AI model use and email remain excluded from this storage-mode policy.

## Verification

[Dedicated offline workflow](../../.github/workflows/korea_legacy_writer_contracts.yml) runs only synthetic assertions: a default successful legacy mode, every attempted private/dual transition rejected at *both* checkpoints, clock/seed changes held, ambiguous/malformed schema held, non-boolean authorization values rejected, safe CLI failure receipts and static inspection of the workflow's two gates and unchanged Indonesia schedule. The full repository offline suite is a **separate exact-head requirement**.

**Release note:** Because this proposal touches a live scheduled GitHub workflow, do not merge it solely from a focused green test. Require owner review of the two guard insertion points and a full green exact-head suite. Merging with the existing pinned legacy policy should preserve the current behavior, but it does **not make archival custody private**. Never substitute this guard for the separately approved cutover.
