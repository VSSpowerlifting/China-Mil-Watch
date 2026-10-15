# China: reduce the active SQLite corpus, not merely browse prominence

**October 15, 2026 — owner direction: retire several thousand old China records from the active database.**

The first source-balanced, automated 600-China-record browsing change is [#636](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/636); its archive-only publication gate is [#647](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/647). Neither should be held hostage to the larger database cleanup. This document records a new, separate production-data objective.

## Proposed actual retention rule

Compute against an **exact regenerated and disclosed focus index** after #636 goes live:

1. Keep every one of the 600 focused China source IDs. This is a provisional research-utility selection, **not** a claim of 600 human reviews.
2. Keep every source ID cited by a published Brief (the October 14 index lists 182 trail references, including 178 China records). Importantly, some cited captures are contaminated and need correction; citation protection is not an endorsement.
3. Keep both specifically identified, consequential original-language Chinese Foreign Ministry leads (#2391, #2849), if they exist. Separately read the canonical `briefs/*.json` source trails and `timelines/*.json` evidence objects and retain every explicitly referenced record ID, including references in unpublished timeline drafts. This independently checks dependencies rather than assuming the compact index's published-trail list captured them all.
4. Keep every non-China source ID, including all 86 Singapore records in the baseline.
5. Consider every other China article row **for retirement from the active database**. This removes thousands of *rows*, not just UI listings. A retired record is not automatically declared inauthentic, duplicate, wrong, or low-quality; it simply falls outside the much narrower **active** collection.

This is a **retention policy**, not an individualized editorial verdict. The owner-approved physical retirement range is **4,300–4,500 China rows**, with a 4,400-row preferred target. When the initial protected focus/citations would leave more than 4,400 removable China rows, the planner preserves a small additional **automated contextual reserve**, favoring non-PLA official sources and recent material and excluding known contaminated historical captures. The reserve is not described as editorially checked. If citations and dependencies make fewer than 4,300 rows removable, or too few safe reserve candidates exist, the plan fails instead of silently changing the owner's scope. The SHA-256 of the exact sorted retirement IDs is in the rehearsal report; there are no invented per-record signoffs.

## Existing physical and legal realities

- SQLite `pla_watch.db` is tracked directly in Git. Deleting its rows and re-rendering shrinks today's *active* corpus but does **not** purge earlier Git history. Rewriting Git history is **out of scope**.
- The original official text has third-party rights and already appears in published pages and citations. Source rights are not changed by our deletion.
- Dropping public `record/{id}.html` for previously published IDs may break **external researchers'** bookmarks and links, even if all 182 internally published trails remain. A true deletion has this cost. Before deployment, enumerate the exact retired routes and either intentionally withdraw them with a transparent notice where feasible or approve the loss; do not pretend they remain accessible.
- The site `output/` is generated. Never hand-remove files from the public output tree; site generation, link checks, and sitemap must use the reduced database, with stale old routes removed under a guarded publishing procedure.
- Daily source collection can reinsert a retired original URL after deletion, because article URL deduplication lives in the active `articles` table. A **persistent URL-hash tombstone/re-ingestion protection** must be designed and tested before a production purge, then future China source volume must be governed. A one-off database delete without these controls merely recreates the imbalance.
- Existing reconciliation code merges by URL and regards origin as the published source of truth. A branch carrying an old DB can resurrect retired rows. Production release needs a frozen reviewed `main`, serialized daily-update slot and merge/reconcile exclusion for retired identities.

## Rehearsal already implemented

`scripts/plan_china_active_retirement.py` takes `output/corpus-index.json` (must contain `focus_ids` from #636) and computes a complete keep/delete set. The candidate must contain at least 3,500 China retirements and **zero** non-China retirements, preserve all published trail IDs and reject historical body holds in the focus.

```sh
python -m unittest -v tests.test_china_active_retirement
python -m scripts.plan_china_active_retirement
# Optional, scratch copy only, NOT production:
python -m scripts.plan_china_active_retirement \
  --scratch-db /private/tmp/ipr-china-retirement-candidate.db \
  --tombstones-out /private/tmp/ipr-china-retired-url-hashes.json
```

The integrated scratch operation reads the tracked SQLite file through `scripts.reconcile_db.read_only`, verifies its article IDs exactly match the frozen corpus index, and writes a **new file outside the repository**. It applies any missing migrations only to that disposable clone, then uses `scripts.stage_china_retirement_atomic.stage_atomic_retirement` to insert the permanent URL/ID ledger entries **and delete the article rows in the SAME SQLite transaction**, with rollback and integrity checks. The former delete-without-ledger path has been removed. The optional tombstone manifest contains only sorted SHA-256 digests of the exact canonical URLs for every retired row and is mode 0600 in private runner scratch. It is a future ingestion-denylist candidate, **not** an active ingestion guard: the collector still needs a separate code change to consult the manifest. No production DB, generated page, backup, database commit or deployment is altered by this PR.

## Authenticated private backup — first genuine restore proof

On October 15, private GitHub Actions [run #38797212318](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/38797212318) succeeded in copying the exact **pre-retirement** tracked database and protected editorial inputs from public commit `49913c5a41f33082b7d3acdbf7f6d0f3bda408bd` into an immutable branch of the existing private evidence repository:

- Private ref: `archive/china-active-before-49913c5a41f33082`.
- Source SQLite SHA-256: `7aa9c4a60fc82b819340b478f109103f95220833f7e7c5bdc5c396c31fbc4f24`.
- Restored census: **5,273 active records**; **5,187 China**, **86 other desks**.
- Included `pla_watch.db`, canonical Brief/Timeline JSON, and existing weekly-issue/editorial assets. Original historical generated record pages remain accessible through their pre-cull public Git revision, not through this private snapshot.
- The job independently downloaded the private ref, compared restored database bytes and manifest, and passed `PRAGMA integrity_check` and article-count verification.

**This is a successful real GitHub-only backup/restore test, not yet a release-head gate.** If daily collection or other changes advance the tracked corpus, re-run the private workflow and pin the *new exact public commit*, DB digest and restored record counts before promoting the deletion. Do not claim that the October 15 snapshot protects records added afterward. Off-GitHub recovery is not provided, per the accepted single-provider storage decision.

## Release boundary — not yet satisfied

Do not deploy a real deletion until ALL of the following hold:

1. #636 and #647 have passed exact-head full CI, merged, and the 600-first browsing release is verified.
2. The exact-current corpus yields a deterministic plan, complete per-source impact report, canonical URL/hash retirement inventory, and an explicit production deletion target. Confirm internal Brief citations and any other canonical manuscripts/timelines and source-linked references also survive.
3. A **private GitHub recovery copy**, in the owner-approved private evidence repository, of the exact pre-retirement database revision and affected historical site/source assets exists, and a fresh restore **actually succeeds**. Encryption is optional per owner direction; private-repository access restrictions, commit identity, original Git provenance and byte-for-byte verification still matter. A matching checksum alone proves byte consistency, not that a file genuinely came from GitHub. No public GitHub Actions artifact should become the only recovery copy.
4. A fully tested permanent retired-URL defense and reconciliation rule prevent next-day reinsertion; all new China records have a prospectively governed admission or source-volume policy.
5. The deletion from a scratch DB and complete site regeneration produce correct reduced source counts, stable protected citations, correct output inventory/sitemap and link behavior, no orphan categories or SQLite FK violations, and baseline validator warnings only.
6. Separate owner-approved exact-head publication of the changed DB and rendered `output/`. This is **not** the three-file browse-only release; do not use #647 to push a reduced database.

## Phasing

- **This PR**: auditable and tested true active-database deletion *rehearsal*, without modifying production data.
- **Next coherent phase**: retirement URL tombstone / daily pipeline enforcement and exact-corpus live-site generation proof.
- **Release phase**: verified private backup, main-locked production purge, full re-render, post-release link and ingestion checks.

**Bottom line:** the operator can delete thousands of active China records, but doing so safely is materially different from switching a browse scope. This rehearsal makes the physical deletion precise and testable while keeping the public archive functioning during the change.