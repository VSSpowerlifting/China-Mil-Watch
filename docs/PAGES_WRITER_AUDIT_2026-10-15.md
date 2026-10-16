# GitHub Pages writer audit and stale-deploy reproduction — 2026-10-15

Issue #346 (audit phase only). Audited at `main` `7763663963`; rebased onto `c56d9714d0`. **The race is not
fixed.** This change adds detection and reproduction only. No workflow, Pages
branch, database, collector or content was changed or pushed.

Deliverables:

- `scripts/audit_pages_writers.py`: a read-only, standard-library auditor with
  a registry ratchet.
- `tests/test_pages_writer_audit.py`: inventory and ratchet tests, 20 cases.
- `tests/test_pages_stale_deploy_race.py`: hermetic interleaving
  reproductions plus a test-only reference fence, 15 cases.

## 1. Writer inventory (18 jobs across 212 workflow files; auditor output)

| Writer (`file::job`) | Class | Concurrency held | Checkout | Freshness before publish |
|---|---|---|---|---|
| `daily_update::update` | full-tree | daily-update | main @ job start | **none** on the no-commit path; rebase+push then a window before deploy |
| `deploy_output_only::deploy` | full-tree | **pages-deploy only** | **trigger SHA, any ref** | **none**; no `refs/heads/main` guard |
| `briefs_render_only_release::publish` | full-tree | daily-update | main | approved SHA + main CAS |
| `china_focus_release::release` | full-tree | daily-update | main | approved SHA + main CAS |
| `china_retirement_release::release` | full-tree | daily-update | main | approved SHA + main CAS |
| `china_retirement_pages_retry::verify-and-redeploy` | full-tree | daily-update | main | approved SHA at start; main is not rechecked at deploy |
| `country_research_render_only_release::release` | full-tree | daily-update | main | approved SHA + main CAS |
| `indonesia_official_links_release::publish` | full-tree | daily-update | main | main CAS |
| `indonesia_press_links_release::publish` | full-tree | daily-update | main | main CAS |
| `korea_public_bibliography_release::release` | full-tree | daily-update | main | main CAS |
| `desks_p4a_render_only_release::release` | overlay (`keep_files`) | daily-update + pages-deploy | main | approved SHA + main CAS |
| `korea_pages_file_only_release` | file-only push | daily-update | main | main CAS + Pages CAS |
| `korea_verified_official_link_production` | file-only push | **own group** (deliberate) | main | main CAS + Pages CAS |
| `korea_original_text_pages_release` (#722, merged during this audit) | file-only push (`korea.html`, `korea-originals/`) | **korea-verified group** | main | main CAS + Pages CAS |
| `treasury_verified_official_links_release` | file-only push | daily-update | main | main CAS + Pages CAS |
| `uscc_verified_official_links_release` | file-only push | daily-update | main | main CAS + Pages CAS |
| `us_bis_verified_official_links_release` | file-only push | daily-update | main | main CAS + Pages CAS |
| `us_pacom_pages_file_only_release` | file-only push | daily-update | main | main CAS + Pages CAS |

Every full-tree writer replaces all of gh-pages with its own `output/`. It can
therefore overwrite any other desk's page. Overlay and file-only writers
can revert only their own files.

The scan also covered:

- **Readers, not writers:** `us_bis_deployed_metadata_readback` and
  `us_desk_public_distribution_preflight`. Both check out `gh-pages` read-only.
- **Non-Pages pushes, resolved to literal shadow/review branches:** for
  example the `vietnam_ministry_shadow` slug pairs and `STATE_BRANCH` values.
- **Scripts:** none pushes to gh-pages.
- **Writers outside the repository, undetectable from workflow text:** owner-local
  and web/API pushes. They are visible only as git evidence (§3).

## 2. Reproduced failure modes (hermetic, `tests/test_pages_stale_deploy_race.py`)

The primitives mirror `peaceiris/actions-gh-pages@v3` (resolved commit
`373f7f26`). It does a depth-1 clone, `git rm -r '*'` unless `keep_files`, a
commit, and one **non-force push with no retry**. The file-only workflows use
the same `origin/gh-pages` check and push.

**Confirmed by reproduction and present in current workflow text:**

1. **A stale full-tree publish silently overwrites a newer release.** A checks
   out main (v1). B commits v2 and publishes it file-only. A then publishes:
   its push is a clean fast-forward, and Pages reverts to v1 while main holds
   v2. peaceiris re-clones the gh-pages tip at publish time, so the parent
   check never sees the staleness. The staleness lives in A's `output/`.
2. **The parent CAS covers only the clone→push window.** A move inside that
   window is rejected. Re-running the same stale tree seconds later succeeds.
3. **`daily_update`'s no-commit path deploys the job-start tree.** That tree
   reverts a `korea_verified_official_link_production` publish made meanwhile.
   This is reachable today, because that workflow is deliberately outside
   `daily-update`. The same exposure now applies to
   `korea_original_text_pages_release`, which shares that group.
4. **`daily_update`'s commit path has the same exposure.** The window is after
   `pull --rebase && push` and before peaceiris.
5. **A fresh full-tree deploy erases content that exists only on gh-pages.**
   Owner-local scoped pushes create such content. The desks_p4a workflow
   comment already acknowledges the condition. This happens even when every
   writer is perfectly serialized.
6. **A stale overlay preserves unrelated pages but reverts its own files.**
7. **`deploy_output_only` publishes whatever ref or SHA was dispatched.** It
   holds only `pages-deploy`, so it is never serialized with the fourteen
   writers that hold only `daily-update`. Its own text shows this; the race
   tests reproduce it in mechanism 1.
8. **No authorized rollback is distinguishable from a stale republish.** Both
   are a plain full-tree push of an older tree.
9. **A crash between deploy and the success marker leaves no attestation.**
   The gh-pages commit records `Deploy: <run_id>`, and peaceiris v3 takes the
   hash from `GITHUB_SHA` (the trigger), not the deployed source. Recovery
   cannot tell what is live without diffing whole trees.

**Theoretical or liveness, not demonstrated as a stale overwrite:**

- **Pending-slot replacement in `daily-update`.** A newer queued run cancels
  an older queued run. Run history shows 54 cancelled scheduled
  `daily_update` runs, 13 Treasury runs and 14 USCC runs (2026-08-10 →
  10-15), which is consistent with this. It loses runs (liveness) but does
  not publish stale content.
- **Out-of-band owner pushes racing a workflow.** The window is real. No
  instance was observed.

## 3. Production evidence (read-only, local refs)

Run `python scripts/audit_pages_writers.py --git-evidence`; it is not part of
CI because refs move. Results on 2026-10-15:

- `origin/gh-pages` matches `origin/main:output` exactly, ignoring
  `.nojekyll` and `CNAME`.
- Of 242 first-parent gh-pages commits, 189 are `github-actions[bot]` and
  53 are out-of-band (owner-local or web).
- There were 253 reversion candidates: a reused blob, or a deletion soon
  after a write. **All 253 match main's content at deploy time; 0 are
  unexplained.** `56ea3181eb` is an explicit owner revert.
- **So no past stale rollback is evidenced.** The hazard is structural and
  reproducible, not an observed incident.
- **Limit of this scan:** main parity is approximated by the first-parent
  main commit before each deploy's committer time.

## 4. Fencing evaluation

**Why concurrency groups alone are insufficient.** A group serializes only
the writers that join it. It is repository-wide, and with
`cancel-in-progress: false` it keeps only one pending slot. It is also
sufficient only if three conditions all hold:

1. Every writer holds the *same* group.
2. Each writer checks out main *after* acquiring the lock.
3. Each writer commits to main before deploying.

Today all three fail somewhere:

- `deploy_output_only`, both korea-verified-group writers and owner pushes
  are outside the group.
- `daily_update` deploys a tree that can be older than current main.
- Content can exist only on gh-pages.

Adding everyone to `daily-update` also worsens the pending-slot
cancellations, which is the reason Korea left the group. A group expresses
"one at a time". It does not express "never older than what is deployed".

**What a fix must add (sketch in `ReferenceFence`):**

1. **Generation attestation in the same commit.** Write a manifest, for
   example `.ipr-release.json` with `generation`, `source_sha`, `writer` and
   `rollback`, in the *same* gh-pages commit as the content, so the two can
   never disagree.
2. **CAS on the expected generation, plus the existing non-force push.** The
   writer reads the manifest, publishes `generation + 1`, and refuses if the
   generation changed.
3. **Monotonic source.** Forward publishes require
   `git merge-base --is-ancestor <deployed source_sha> <my source_sha>`.
4. **Explicit rollback.** A rollback must name `expected_current` and
   `target`. It is refused if either is stale. The tests show a stale
   authorization being refused.
5. **Preserve unrelated desks by rebuilding, never by forcing.** On refusal,
   re-checkout current main and re-render, or exit and let the next run
   publish. File-only and overlay writers must bump the manifest too.
   Otherwise full-tree writers cannot see them.
6. **Crash recovery.** If the manifest's `source_sha` equals main, only the
   success marker needs writing and no redeploy is required. If not, redeploy
   from current main.
7. **Out-of-band pushes still bypass any fence.** The test
   `test_fence_does_not_cover_writers_that_bypass_it` shows this. Policy must
   require that public content lands in `main:output` first. Optionally, a
   post-deploy readback can fail on drift.

**Simpler alternative to evaluate first: a single deployer.**

- Exactly one workflow publishes, in its own lock, always from
  `origin/main:output` fetched *at deploy time*, with the manifest.
- All other workflows only commit to main and trigger it.
- This removes items 3–7 of §2 by construction and keeps per-desk workflows
  focused on rendering.
- The cost is one more hop and a full-tree deploy per desk update.

## 5. Recommendations and acceptance criteria for the fix PR

**Exact next implementation step:** add the generation manifest and the
pre-push check to one shared, tested helper (script or composite action).
Adopt it first in `deploy_output_only` and `daily_update`, which carry the
two highest-risk hazards. In the same PR:

- add a `refs/heads/main` guard to `deploy_output_only`;
- have it check out `main` instead of the trigger SHA;
- have `daily_update` refuse or re-render when `origin/main` has moved past
  its tree before Step 7.

**Acceptance criteria:**

1. The auditor reports `generation_fence: true` for every writer.
   `test_no_writer_has_a_generation_fence_yet` is flipped deliberately.
2. Each `test_current_*` hazard test is converted to assert refusal. For
   every mechanism in §2.1–2.4 and 2.6–2.8, a matching test runs against the
   real helper, not the reference class.
3. An authorized rollback succeeds only with a matching `expected_current`
   and `target`, and is recorded in the manifest.
4. A crash after deploy and before the marker recovers without redeploying
   when the manifest's `source_sha` equals main.
5. Unrelated desk pages survive a refused stale publish followed by its retry.
6. The gh-pages provenance records the deployed source SHA, not `GITHUB_SHA`.
7. A written policy (DECISION_LOG) covers out-of-band gh-pages pushes, or a
   post-deploy drift readback blocks on drift.

## 6. Keeping the ratchet current

A new or changed Pages writer must be added to `REGISTRY` in
`scripts/audit_pages_writers.py`, in a reviewed PR. Both new test modules run
under `python -m unittest discover -s tests -t .`. That command runs in two
places:

- `pr_offline_checks.yml`, on non-draft PRs.
- `daily_update.yml` Step 4c, before collection.

So an unregistered writer that reaches main without passing PR checks halts
the daily run. That is fail-closed by design. The suite then fails in any of
these cases:

- an unregistered writer;
- an unresolved `git push` target;
- a scope escalation (file-only → overlay → full-tree, force, orphan);
- a dropped concurrency lock;
- a dropped guard.

Open PRs that touch workflows (#679 edits the registered
`china_retirement_pages_retry`) keep passing unless they remove a registered
guard or lock.
