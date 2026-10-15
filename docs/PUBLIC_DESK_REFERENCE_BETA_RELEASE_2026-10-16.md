# Accelerated public source-reference beta — target October 16–17, 2026

**Scope:** Reader-facing reference navigation for already-declared Philippines and Vietnam desks. This is **not an accelerated admission of AFP, NSC, MPS, MOIT, VGP or other original publisher content into the production corpus**, and does not waive source-use law, a real editor's signoff, current access policy, or an authentic observation history.

## Why this can ship early

The full desk promotion requirement (including the 30-day collecting period and Day-7/14/30 reviews) remains in force for **production archive admission**. That requirement need not block external navigation to the publisher's own freely linked official listings. A reader can consult official sources directly without IPR copying, translating, or storing that text publicly.

The public beta does the following:
- Adds an explicitly named “Public research access” section to the Philippines and Vietnam desk pages, near the beginning of the page.
- Pulls **two** Philippines (AFP and NSC) and **four** Vietnam (Government News, MPS, MOIT Energy, MOIT Foundational Industry) publisher entrypoint URLs from `desks/registry.json` rather than maintaining duplicate unverified URLs.
- States plainly that links are not IPR-reviewed specific article citations, not claims of complete collection, not verified events, and not admitted corpus rows.
- Keeps the separate `research/{philippines,vietnam}_reviewed_links.json` human approval surfaces empty. No new government article title, copied text, image, machine summary, file attachment, or publisher-body URL is added to the production corpus.

Japan, Korea and Indonesia already offer narrower, differently documented official-source bibliographies or external-link directories. This PR intentionally does not modify their pages, statuses, rights gates, or historical provenance.

## Release acceptance — no invented approvals

1. On PR #642 exact HEAD, require green **Public country reviewed references**, **Country research desks — render-only release**, and repository-wide offline CI; verify no required check is skipped or cancelled. Recheck current main before merging.
2. Inspect the `public-reference-beta-preview-<run_id>` artifact emitted by the country render-only PR contract. Review Philippines, Vietnam and unchanged Desks HTML visually, hyperlinks, copy and responsive readability. Verify no “live”/admitted corpus wording for PH or VN.
3. Verify scoped diff has only template, contract tests and release-workflow guard additions. No tracked `pla_watch.db`, original `shadow/` state or committed generated `output/` should be altered in the source PR.
4. Merge the PR only after exact-head green checks and actual rendered page review.
5. In GitHub Actions on `main`, select **Country research desks — render-only release → Run workflow**. Supply the **current full 40-character main SHA** into `approved_main_sha` and set `publish=true` only for an authorized actual release. The action rerenders into scratch, stages only reviewed country pages/CSS/JS, validates the complete `output/` tree and current DB SHA, refuses concurrent main changes, and commits the generated scoped country pages to main before deploying to `gh-pages`.
6. Verify the live `https://indopacificrecord.org/philippines.html`, `https://indopacificrecord.org/vietnam.html` and `/desks.html` afterward. Check that source links open the official first-party publishers. Record the exact workflow run ID/attempt, deployed commit and live page results.

**No actual deployment is implied by merging the source PR.** The connected repository API may not expose the GitHub Actions `workflow_dispatch` write action; if unavailable, the repository owner must run the guarded release action from Actions. Never obtain a green deployment merely by weakening source/copyright status or redirecting `gh-pages` without the governed workflow.

## Parallel path to fully admitted production

- AFP: complete the formal pinned Day-7 attempt/job audit, version-bound 22-original human review, publisher terms and 30-day continuity; keep source-body storage restricted until custody and rights decision.
- Indonesia: Day-7 machine evidence exists; reconcile source-specific geography/chronology claims, named Indonesian review and rights, then next actual reliability/human checkpoints.
- Korea: three-source local manuscript evidence exists; secure original evidence custody, authenticate Korean reviewing and a new successful collection interval. October 12 remains failed historically.
- Japan: observe lawful MOD retrieval and JCG schedule, do not reinterpret source access gaps as a qualified collecting sequence.
- Vietnam: Oct 14 original-capture fidelity verification merged; MOIT robots MIME/rights and the late/missing collection slot remain separate; human reviews are still required.
- Singapore/China: already production; maintain source integrity and preservation-first editorial selection.

**Deadline:** aim to release the honest public reference beta by Friday, October 16, contingent on exact-head green and visual review. Saturday October 17 is a reader-facing objective, not permission to bypass red CI, false rights declarations or source-data custody controls.
