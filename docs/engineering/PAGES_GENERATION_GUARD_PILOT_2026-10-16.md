# GitHub Pages generation guard — isolated implementation pilot

Issue [#346](https://github.com/VSSpowerlifting/IndoPacificRecord/issues/346). This is a **source-only, opt-in pilot**, not a cutover, an approved publication policy, or a completed Pages race fix. **No existing workflow invokes it.** It writes neither `main` nor tracked `output/`. Its default mode reads existing Git references and prints only a deterministic generation plan; pushing to `gh-pages` requires the explicit `--push` argument. Do not use `--push` against production before the C4/C5 review, complete writer migration, and approved rollback/carry-forward policy.

## What is implemented

`python scripts/pages_generation_guard.py --mode file-only --writer <name> --path korea.html` prints a candidate manifest without publishing. It requires a full checkout of `main` matching `origin/main`, an exact committed `main:output` snapshot, and existing manifest provenance. `--mode full-tree` checks for unapproved removal and for same-path divergence between the live Pages tree and the prior committed source. A full-tree release can explicitly carry Pages-only paths via `--preserve`, but those paths require independent rights, editorial, and persistence authorization before production use.

The pilot can bootstrap an unmanifested Pages branch **only** if existing content is exactly equal to current `main:output`, aside from the controlled Pages infrastructure files `CNAME` and `.nojekyll`. Bootstrap is separately opt-in (`--bootstrap`) and performs the same readback. A manifest has schema, monotonically increasing generation, exact source SHA, writer identity, final assembled-tree digest, and null rollback marker. It is written **in the same commit as the files**, under `.ipr-release.json`.

All branch writes occur only in a disposable gh-pages clone. Before an opt-in publication, the pilot rechecks `origin/main` and `origin/gh-pages`; the push is non-force and fast-forward-only. Remote changes, a local stale checkout, divergence between the manifest and actual live files, unexpected symlinks, missing source files, mismatched DNS (including file-only and first bootstrap releases), reserved Git paths, or unapproved carried-forward artifacts **hold rather than publish**.

The 26 dedicated tests execute actual commits/pushes against disposable local bare repositories. They include bootstrap parity, dry-run no-mutation, stale source, CAS concurrency, same-name out-of-band changes, Pages-only new files, exact carry-forward, CNAME preservation, and refusal to imply authorized rollback.

Run: `python -m unittest tests.test_pages_generation_guard -v`.

## Still required before any production cutover

1. Merge the audit/collection-isolation PR #725 separately and confirm exact-head checks. This pilot has no dependency on its source files.
2. Independent review of all Pages writers and an explicit, version-bound authoritative source policy for Pages-only Korean originals, translations and analysis. The current `main:output` may not contain those bytes.
3. An authenticated publication-policy receipt and full artifact approval. This pilot's manifest proves **integrity consistency**, not trustworthiness or legal authorization. Anyone already authorized to rewrite the Pages branch can forge an internally consistent manifest.
4. Define and implement a real, explicitly authorized rollback flow. **Rollback publication is rejected in this pilot.** A new forward main commit reverting the site is permitted by ordinary ancestry but still requires the site's normal editorial authorization.
5. Coordinate all 20 currently registered writers through this or a replacement protocol. Any remaining unfenced writer can bypass generation checks. A SHA freshness check and a Pages compare-and-swap are *not* atomic across `main` and `gh-pages` refs; a concurrent main commit can still move between the final check and push.
6. Production dry-runs against full-fidelity real Pages data, crash recovery, exact deployed HTTPS readback, and regression tests against the final assembled site and any authorized `CARRIED_FORWARD` content.

**Stop condition for this PR:** Tests passing and one source-only PR open for review. No live release, workflow edits, owner approvals, merger, or deployment.

## October 16 follow-up hardening

The file-only path now enforces the same committed `CNAME` and `.nojekyll` consistency contract as full-tree publication, including the initial bootstrap. It refuses to attest a release whose committed site infrastructure conflicts with the live Pages branch, without modifying any site artifact. The guard also rejects the reserved root `.git` path. Three additional offline integration cases cover these holds; **26 focused tests pass**. No production workflow or live release was changed.

A second adversarial check simulates `origin/main` advancing between the candidate build and final publication freshness check, and verifies a hard refusal with no Pages push. Another supplies a real Git-tracked symlink on `gh-pages` to verify the walker never follows it. These brought the hermetic suite to 20 cases.

## Committed-artifact integrity correction

A further regression exposed a real omission: `git add -A` honors a newly committed `.gitignore` in the assembled Pages checkout. Previously, the guard could calculate a correct digest from the *working files* but push a commit that omitted an ignored file. The source SHA and manifest then falsely attested an artifact absent from the deployed Git tree.

Immediately after preparing the commit and before any remote push, `verify_committed_release()` now reads Git HEAD's actual tree and compares every path and blob SHA-1 to the exact approved bytes, including the manifest. Missing, additional, transformed or unsupported entries HOLD. A real local Git regression reproduces the old omission and proves zero remote mutation with the new check. The pilot now has **26 passing integration tests**. This is a commit-content integrity check, not publisher rights approval.

## Mixed-generation release and dry-run proof (2026-10-16)

The source-only pilot now stages, commits and verifies its proposed Pages tree **even during dry-run**, solely in a disposable temp clone. This is necessary: earlier dry-run would bless a candidate containing a Git-ignored file that the eventual Git commit omitted. The new regression proves dry-run fails before any remote mutation; another proves dry-run and push attest identical source SHA, generation and final-tree SHA256 when no refs move.

A dedicated mixed-generation test demonstrates the unresolved **liveness boundary**: after a file-only Korea release advances the manifest source SHA while another route remains at older source bytes, the subsequent normal full-tree release HOLDS because v1 cannot attest per-path historical provenance. Do not loosen that HOLD to make green tests. The production protocol must carry explicit, reviewer-authorized per-path provenance or use a unified assembled-tree deployer that reads an authoritative projection. It must distinguish a legitimate older carried file from unapproved Pages-only content and from a now-revoked publication. Until this exists, the pilot does not support automatic safe publication for all desk writers.

A further test proves a file-only release refuses to reattest content **removed from current `main:output`** (when it previously belonged to the committed published tree). This is a public revocation-safety HOLD; an explicit source-use/preservation receipt is needed before carrying Pages-only content forward. Neither the test nor the helper authorizes a rollback or changes live Pages. **25 hermetic local integration tests pass.**

## Owner-released same-path protection

File-only writers now apply the same Pages-only override conflict fence as full-tree writers **to the exact paths being published**. A source-only desk update cannot silently replace an independently attested Pages version whose bytes differ from the previously recorded committed `main:output` projection. This matters for owner-released Korea original, translation, and analysis views. A synthetic attested Pages-only override and file-only attempted overwrite test HOLD with no branch mutation; a future per-path rights/provenance receipt must authorize any intentional replacement. This guard is not yet a production deployment protocol. **26/26 local integration tests pass.**
