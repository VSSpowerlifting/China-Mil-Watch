# Korea private custody — read-only copy-equivalence preflight

**October 15, 2026. Implementation-only evidence tool, not migration authorization.** [Merged #608](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/608) establishes the proposed architecture: a dedicated **private Git repository** for Korean originals. [Custody issue #520](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/520) remains open until actual restricted custody is verified. Choosing private Git does not authorize moving data, changing credentials, disconnecting the collector or erasing a public branch.

## Verification provided

[scripts/verify_korea_private_custody_equivalence.py](../../scripts/verify_korea_private_custody_equivalence.py) compares two **already provisioned, separately checked-out** local Git clones of exactly the same preserved Korean shadow-state tip. It does not clone, fetch, send, copy, push, commit, publish or call the government source.

- Both clean Git histories must contain frozen 14-source commit 0595f0fd29b769cbab5dd57c2ef57af174237a67, with **identical checked-out HEAD SHA**.
- The state tree must contain exactly captures, ledger, clock.json, and shadow.db, with no symlinks, unknown files or excessive file sizes. Every stored capture must match its own SHA-256 filename.
- The ledger/capture/database/clock file sets and every SHA-256 must match exactly. The shadow SQLite database must pass integrity checks, report Korea as its sole desk, contain valid canonical MND source IDs/URLs, and bind all original text hashes and article/HWPX captures to real files.
- October 6 day-zero remains unchanged, while October 12 remains without a successful **scheduled** collection slot. No successful manual lookback is counted as replacing that lost scheduled run.
- The stdout JSON receipt includes only the shared Git commit, counts, day-zero and deliberately false release/visibility/credential flags; **no HWPX bytes, raw source text, reviewer names, entire ledger bodies or email/model input** are emitted.

## Manual operator procedure only after separate copy approval

An authorized owner/operator must first choose an actual private remote, custodians and access policy, verify that remote really is private, provision minimally scoped credentials outside public repository code, and arrange a private backup and restore test. Obtain explicit approval **for the actual evidence-preserving copy**. The current Korea collector still writes to a public Git ref and no cutover is permitted by this PR.

Once approved and copied by an authorized operator, check out the same exact source history commit in two separate local directories outside the public IPR worktree. Run:

    python -m scripts.verify_korea_private_custody_equivalence --source-checkout /absolute/source-shadow-checkout --candidate-checkout /absolute/private-destination-checkout --explicit-local-read-only

On any mismatch, the command fails with no success receipt. **This tool never performs the copy itself.** No real Korean originals are fetched or uploaded in CI.

Even a PASS does **not** verify that the destination remote is private; nor does it prove token scope, completed backup restoration, independent Korean review, copyright permission, rights for complete HWPX/media, suitability for AI use, Sunday manuscript eligibility, editor email approval, production readiness or historical artifact deletion. All those flags stay FALSE in the receipt. Git history deletion cannot retroactively remove prior public copies or clones.

A separately approved engineering PR must eventually ensure **one Korea-only writer**, no fallback to the public original branch on a missing private credential, continued Indonesia operation, preserved ledgers/day-zero, and a genuinely observed new scheduled collection in the private destination. Do not force-push/delete public refs or purge artifacts without separately verified backups and express owner authorization.

## Tests and boundaries

The [focused workflow](../../.github/workflows/korea_private_custody_equivalence_contracts.yml) uses synthetic local five-record Git clones. It covers exact-equivalence PASS and corrupt capture, changed Git tip, missing ledger, symlinks, foreign source DB, altered Korean text digest, wrong day-zero, untrusted ancestry and a fabricated successful October 12 schedule. Repository-wide exact-head offline CI is a separate required merge gate. This PR never changes actual collections, archive content, publication, source registry, AI, editor email or site deployment.

**Disposition:** read-only migration-preflight capability; private destination creation, data transfer, credential assignment, switch-over and retention decisions all remain separate approved work.