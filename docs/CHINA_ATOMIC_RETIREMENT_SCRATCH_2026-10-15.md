# China active-database reduction: atomic scratch transaction

**Engineering phase, 15 October 2026. No production deletion, publication or backup mutation.**

Owner-authorized target: retire **4,300–4,500 China rows** from the active SQLite database, preferably 4,400, only after protecting citation and dependency IDs. The 600-record China browse focus is already implemented in PR #636; retirement planning runs in PR #653; the permanent retired URL and numeric record-ID guard is PR #657.

This phase implements the precise atomic core of a future real deletion. It is based on PR #657 and should be retargeted to `main` after that prerequisite merges. It is **not a production release script**.

## Transactional contract

`scripts/stage_china_retirement_atomic.py` exposes `stage_atomic_retirement(conn, plan_data, retired_at)` for **a new disposable SQLite file outside the checkout**. It rejects the repository's tracked database, requires migration 0008's retired-URL ledger and ID trigger, and requires foreign-key enforcement.

The operation checks the exact row IDs from the reviewer-approved plan, matches their SHA-256 selection fingerprint and baseline article count, rejects non-China sources and unsafe foreign-key dependencies, and enforces the 4,300–4,500 bound by default. The `rehearse_on_new_scratch_copy(source_db, scratch_db, plan_data, retired_at)` wrapper creates a new outside-repository SQLite copy through the existing read-only-copy mechanism, invokes the atomic transaction on that copy, and removes the output copy if the transaction fails. No source file or sidecar is modified.

Within a **single `BEGIN IMMEDIATE` transaction**, it inserts immutable URL-hash and original-ID tombstones, deletes the corresponding `articles` rows, verifies every retained ID, verifies the one-to-one ledger delta, checks SQLite foreign keys and integrity, then commits. If anything fails, the entire transaction rolls back—no orphaned partial deletion and no ledger-only false retirement.

The tests use smaller explicit quotas solely to make in-memory and temporary-file fixtures practical. The production default is unchanged.

## Next integration work (still not done)

- Merge #657 with its full exact-head CI, then review/merge this atomic core.
- Wire the scratch database copy in #653 to this function; **remove its old delete-without-ledger path**. Do not run old #653 deletion logic after the real retirement starts.
- Freeze the reviewed snapshot and protect all native Brief and Timeline citations, historical source-trail URLs, any manually pinned analysis record IDs and the original-language holds.
- Verify the private recovery snapshot can actually be restored. A manifest checksum alone does not authenticate the original GitHub export.
- Render the complete site from the reduced scratch DB, compare the expected output removals, ensure the 600 browsing view is still coherent, verify live historical-route handling, and only then authorize a separate exact-SHA production release.
- Keep daily collection from reintroducing retired exact URLs using the persistent ledger, and keep every new numeric ID above the retired high-water mark.

**This PR changes only a helper module, fixtures, workflow and this document. It cannot run against the tracked database.**