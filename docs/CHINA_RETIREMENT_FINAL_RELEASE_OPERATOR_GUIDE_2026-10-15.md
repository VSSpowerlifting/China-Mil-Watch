# China active archive retirement — operator release and recovery guide

**Current status:** preflight only, no production deletion. The owner approved
retiring approximately 4,300–4,500 China entries, preferably exactly 4,400,
subject to cited-source and cross-desk holds. Do **not** use this guide to
override a failing review gate or force an unverified GitHub Pages publication.

Canonical public repo: `VSSpowerlifting/IndoPacificRecord`.
Private custody: `VSSpowerlifting/ipr-source-evidence-private`.
Neither old project/repository spelling nor redirected Git URLs should appear
in release inputs.

## 1. Code and checks must be on main first

Merge the original PRs in dependency order: #657 (source URL & ID
re-ingestion prevention), #663 (single-transaction SQLite delete plus tombstone),
#665 (reviewed original ID selection and full-site reduction), then #675
(manual SHA-locked site and database cutover). Resolve the Desks-page size
regression in #681 independently. Retarget stacked PRs to current main and
require exact-head focused plus repository-wide CI; do **not** merge the
verification-only integration PR #679.

PR #679's current-main CI is release evidence only, not a substitute for
the final merged code's CI. The baseline rehearsal proved 5,273 → 873 records,
4,400 durable tombstones, 182 citation-protected source records, 633 analyzed
JSON-export rows and byte-identical 1,815-file Pages packaging. Counts will
depend on the exact source commit and must not be copied into a new release
receipt without testing them again.

## 2. Produce and independently restore the exact pre-release private backup

At the private vault, run workflow
`China active corpus — private pre-retirement recovery snapshot` against
its main branch. Confirm **success**, not just a pushed archive branch.
The private log supplies:

- the **public source commit SHA** (`approved_main_sha`);
- the immutable archive branch (`approved_backup_ref`);
- the **private backup commit SHA** (`approved_backup_commit_sha`, fetched
  from the private branch, not guessed);
- the original SQLite SHA-256 (`expected_db_sha256`) and original row counts.

The restored manifest must name the current canonical public repository,
the **backed-up** source Git commit and SQLite Git blob, byte count, SHA-256
and complete China/non-China census. The workflow reads back the private branch
into a new checkout and runs `PRAGMA integrity_check`.
A backup from an **ancestor** of the release's current `main` is acceptable
when its *original tracked SQLite Git blob* is bit-for-bit identical to the
current tracked database and the SHA-256 of those bytes still matches the
restored private manifest. The guard proves Git ancestry, old/current Git
blob equality and a fresh byte digest. It rejects diverged history or any
database-content change. Code-only desk merges therefore do **not** require
another private snapshot. New source records or any updated SQLite bytes do.
The actual release SHA is separately pinned at workflow checkout and must
remain exactly equal to remote `main` before any destructive promotion or push. The vault is private GitHub-only storage, not independent off-GitHub
custody.

## 3. Configure the backup-read token without sharing it

The public repository Actions secret
`IPR_PRIVATE_VAULT_READ_TOKEN` must exist before an actual publication.
Create a fine-grained GitHub token with **Contents: read only** on the private
`ipr-source-evidence-private` repository, and add it using the public repo's
Settings → Secrets and variables → Actions → Repository secrets.
Do not paste it in chat, commit it, print it in CI or provide it to the
public site. If a secret already exists, don't rotate needlessly. The
production workflow refuses to publish without successful private vault
authentication.

## 4. Rehearse the exact final release SHA on main

In the public repo's Actions tab, choose
`China active archive retirement — guarded full-site cutover`.
Provide the four inputs from **the exact verified private backup**, with
`publish: false` first. It must create only a disposable scratch database
and site, rerun contracts, match the approved 4,400 IDs and digest, show
retained citations, and validate every generated site route and export.
Check no production SQLite/output diff or sidecar residue.

Do not run the release by merging the integration branch or by triggering
the three-file focus-only publisher; those do not physically retire the
active SQLite collection.

## 5. Execute the real release and audit the same bytes

Only with all previous gates satisfied, run the same SHA-locked workflow
with `publish: true` and the four validated inputs. This serializes with
`daily-update` and pins and checks the actual current main SHA again. It then promotes the verified
SQLite+entire-site scratch tree together into one reviewed `main` commit,
publishes all of `output/` to `gh-pages`, fetches the remote Pages Git
branch, and compares **every file** and record identity against the released
database. Main may change during the preflight due to other desks; in that
case the workflow must stop instead of using stale backup or source IDs.

Do not call this completed until the main database has 4,400 durable
retirement tombstones, no retired active URL/ID, retained citation routes
remain valid, the remote Pages branch matches, and the post-release live
domain shows the smaller active collection. A Git readback does **not** prove
CDN cache propagation; spot-check the actual public domain separately.

## 6. Recovery and first-next-day checkpoint

- **Site publish fails after the main DB commit:** never rerun the 4,400
  deletion. Use the dedicated `China retirement — verified Pages-only
  deployment retry` workflow with the exact post-cull main commit SHA and
  reduced SQLite digest. It validates the already-reduced DB/site, then
  republishes Pages only and independently compares remote bytes.
- **A database release fails before commit:** canonical main and Pages are
  unchanged; discard runner scratch. Never force the checkout to overwrite
  unrelated desk work.
- **A bad database change is discovered after commit:** stop automated
  collection first and use the previously verified *private* Git backup for
  an explicit, separately reviewed forward recovery. Do not blindly push an
  older Git tree: it would erase unrelated Korea, U.S., Philippines or other
  desk progress.
- **Next collection:** the `China retired-source integrity — after daily
  pipeline` workflow serializes with the daily/page writers, then verifies
  all retirement IDs/URLs remain absent, the active SQLite IDs match the site,
  and GitHub Pages matches the tracked site. An unexpected result is a
  failed integrity gate, not proof of a valid source admission.

**No steps in this document are authorization to bypass a failed CI, source
evidence check, missing custody proof, missing token, or current-main race.**
