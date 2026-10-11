# S4 — canonical URL collisions, offline and non-admitting

This is a **private operator rehearsal**, not the first production import. It is stacked on S3 draft PR #406 because it reuses the *exact* read-only SQLite/snapshot and source-specific preflight contract, not a copied fork. S3 itself requires checkpoint-composer PR #403 and separate Vietnam anomaly-preservation PR #401. None of the three upstream draft PRs is automatically merged or authorized as an admission mechanism.

## Problem this resolves

A source may be reviewed against its original publisher and still collide with the existing public archive. Existing `articles.url` is unique and determines record identity; a collision must never silently change source attribution, article ID, content, published date or editorial status. Conversely, an already-registered source slug needs an explicit source-row migration and idempotence review, not a second row with a different slug. **No publisher record will enter production through this utility.**

The S3 inspector verifies the actual database schema/unique indexes, exact source slug registration count and a SHA-256 over frozen SQLite bytes. This S4 utility takes the output receipt of S3 and the reviewed source's *candidate metadata list*, then compares those URLs against the very same frozen production snapshot. It refuses any mismatch between the candidate inventory's source commit, preflight receipt, production DB hash or source family. It hashes the database before and after to detect changes, and queries only `sources.slug` through `articles.url` equality lookups: no production body, headline, record ID or original URL is exported.

## Supported source scopes

- `ph_afp_articles`: exact official `https://www.afp.mil.ph/news/<slug>` route, an immutable `afp:<integer>` identity and official publication day. **The AFP API integer ID does not derive from the website slug**, so this script cannot attest their pairing or assert publisher fidelity; original-source human review and capture SHA must establish that later.
- `vn_mps_foreign_affairs_vi`: exact ministry `https://bocongan.gov.vn/bai-viet/<slug>-<ten-digit-id>` URL, matching the repository's `core.collection.vietnam_sources.SOURCES` URL-derived `mps-vi:<ten-digit-id>` identity rule, with source SHA and publisher date.
- MOIT Energy, MOIT Foundational, Philippine NSC: **deliberately excluded** from this S4 implementation. MOIT still has independently unresolved source-use/written-permission/robots questions; NSC lacks article extraction proof. A clean AFP or MPS comparison cannot qualify them.

Every candidate inventory is a *bounded, explicit subset*. A source with 18 records might submit 18; another may submit one. Neither implies the entire shadow corpus was inspected or that the candidate list is complete.

## Operator input (private only)

Create `$SECURE_DIR/afp-candidates.json` outside the public working checkout and any GitHub Actions artifact upload. Derive it *only* from independently reviewed source originals and immutable state/capture identity; **do not fill it with invented URLs, presumed legal permissions, or AI-generated article text**. It contains URLs and source identities and must remain private. Example below is **synthetic test syntax, not an actual source or approved review**:

~~~json
{
  "schema": "ipr-country-source-url-candidates/1",
  "source_slug": "ph_afp_articles",
  "state_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "checkpoint_receipt_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "production_database_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "records": [
    {
      "source_identity": "afp:1395",
      "canonical_url": "https://www.afp.mil.ph/news/synthetic-contract-example",
      "publisher_date": "2026-10-06"
    }
  ]
}
~~~

Replace all fictional pins with the literal pinned values from the *same* S3 report, and all synthetic rows with real **separately reviewed private** candidate metadata. This utility does not fetch the shadow branch or source website and does not attest that the provided inventory faithfully covers them. Identifying actual reviewed records will be an operator/custody task, not an automated claim.

Run after S3 and the real Oct 13/14 checkpoint operators have produced the genuine machine receipts:

~~~sh
python -m scripts.inspect_country_admission_boundary \
  --source ph_afp_articles \
  --checkpoint "$SECURE_DIR/afp-checkpoint.json" \
  --database "$FROZEN_PRODUCTION_DB" \
  > "$SECURE_DIR/afp-s3.json"

python -m scripts.audit_country_source_url_collisions \
  --s3-preflight "$SECURE_DIR/afp-s3.json" \
  --candidates "$SECURE_DIR/afp-candidates.json" \
  --database "$FROZEN_PRODUCTION_DB" \
  > "$SECURE_DIR/afp-collision-summary.json"
~~~

Use `vn_mps_foreign_affairs_vi` and the corresponding Vietnam source-state/candidate list for MPS. Do not use live production SQLite while a write is in flight: S3/S4 require a consistent **already frozen** snapshot, with no WAL/SHM/rollback-journal sidecar and unchanged SHA-256. The report outputs no URL, original title, body, publisher quote or candidate identity; only source slug, digest bindings, fixed machine counts, outcome counts and fixed hold names. The candidate JSON and any signed human reviews must **not** be committed or attached to a public PR.

## Outcomes are not approvals

The four mutually exclusive classifications are:

- `new_URLs`: no existing row at that precise canonical URL in this frozen production DB;
- `already_present_same_source`: exact URL already points to this source slug (separate idempotence/record-version review needed);
- `foreign_source_URL_collisions`: exact URL is already attributed to another source and must not be reassigned;
- `orphan_source_URL_collisions`: URL points to a missing/NULL source row and needs independent DB integrity remediation.

The sum of those counts must equal the supplied candidate count. A report may say `supplied_URLs_no_detected_collisions_not_an_admission`. This means **exactly** what it says: the provided URLs did not collide in that frozen snapshot. It does **not** authenticate the source-original capture, AFP numeric IDs, representativeness, complete run history, human review identity, publisher license, rights, custody, Day 30 maturity, or production/publication eligibility. All import, public projection, model, deployment and source-rights authority booleans remain false.

## Next engineering gates after S4

1. Privately bind candidate URL metadata to each real immutable original/capture SHA and verify exhaustive source inventory and positive named-human original-source checks; do not publish evidence objects or human signatures.
2. Source-specific admission manifest proposal outside discoverable `desks/*/manifest.json`, reviewed against each official institution and publisher action rights.
3. Transactional, **disposable DB copy-only ingest rehearsal** on the *same* pinned source generation and approved snapshots, with idempotence, no source reassignment, correct source/language, rollback and corpus-fingerprint preservation for all existing records. This is not the old Singapore promoter's implicit activation.
4. Separate private-custody and permitted public metadata/full-text/action projection with leak checks (binary/history still distinct), then separately owner-approved, exact-SHA deployment and rollback only after C1–C13 and rights.

S4 is not wired to `pipeline.py`, `desks/registry.json`, `storage/db.py`, `scripts/promote_shadow_records.py`, daily workflows, Sunday briefs, Pages, AI models or a write-capable release path.

## Verification

Run `python -m unittest tests.test_country_source_admission_schema tests.test_country_source_url_collisions -v` on Python 3.9. A dedicated PR-only workflow snapshots and verifies unchanged tracked production database, `output/`, `shadow/`, and `desks/`, and runs only source-free synthetic candidate and schema tests. Passing tests prove technical input binding and collision classification **only**. Independent exact-head review remains required before merge, and S4 cannot be merged into main until S3's actual main integration is independently approved.
