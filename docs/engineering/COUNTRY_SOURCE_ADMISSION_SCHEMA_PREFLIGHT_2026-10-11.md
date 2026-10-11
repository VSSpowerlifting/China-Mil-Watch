# Country-source admission S3 — read-only schema boundary

**Status: operator engineering only. No source admission, private-custody activation, public record or website deployment.**

The next step after draft PRs #401 and #403 is to test the production storage assumptions against which an individually qualified AFP or Vietnam source would eventually be integrated. The code in **scripts/inspect_country_admission_boundary.py** is an offline, read-only preflight. It deliberately does not reuse the historical Singapore shadow promoter as a live mechanism.

## Existing boundaries

The current tracked production SQLite database drives publicly generated record pages. Registering a new source under a production manifest or inserting an article can therefore affect public claims or expose original publisher material. The new preflight reads table/index *schema* and counts only entries with the one supplied exact source slug; it never opens publisher bodies or article URLs, and cannot insert or update data.

It checks that **sources.slug** and **articles.url** are uniquely indexed and that the required source/article columns exist. An existing production source row is a **collision hold** rather than permission to replace or reuse it. This tool does not yet inspect source-article URL collisions: that will need a subsequent confidential candidate-by-candidate rehearsal, on a frozen database and rights-reviewed private metadata. The report binds the inspected production baseline with **SHA-256 of the complete SQLite file**, checked before and after read-only schema introspection to detect concurrent changes; the database bytes are hashed in chunks but no article rows or body text are selected or emitted. Pending WAL, SHM or rollback-journal files are refused.

## Input binding

Command syntax:

~~~bash
python -m scripts.inspect_country_admission_boundary \
  --source ph_afp_articles \
  --checkpoint "$SECURE_DIR/afp-checkpoint.json" \
  --database "$FROZEN_PRODUCTION_DB"
~~~

The checkpoint JSON comes from the existing composer in draft PR #403 after the real October 13 AFP slot or October 14 Vietnam source runs. It must carry a correct source-specific immutable Git state SHA, canonical date and all upstream permission flags **false**. It must preserve explicit external source-rights and owner-release holds. The source named here must agree with the original desk receipt; AFP clocks never certify NSC, and Vietnam MPS cannot inherit MOIT authorization.

The database must be a stable SQLite snapshot. It is opened immutable/read-only, with query-only set; WAL and shared-memory sidecars and symlinks are refused. Treat it as a confidential custody artifact when applicable. The inspector writes JSON to stdout containing only fixed source names, frozen source SHA, a hash of the supplied report, safe schema booleans, source slug collision count and the next required gates. It never echoes arbitrary checkpoint text, article URLs or source bodies.

## Scope-specific holds

| Family | Allowed result |
| --- | --- |
| AFP articles | Schema rehearsal candidate only; real original-source review, rights, 30 days and human owner authorization still missing |
| Vietnam MPS foreign affairs | Schema rehearsal candidate only; all Vietnamese-language, version and rights checks separate |
| MOIT Energy | Hard source-rights and robots review hold, even with valid schema |
| MOIT Foundational Industry | Same independent hard hold |
| Philippines NSC | Excluded: its own article-capture and source qualification not proven |

Even a report marked **structure_compatible_no_admission** confirms only that the frozen database can support the expected schema and does not already contain that exact source slug. It does not prove qualified sources, publisher licensing, source-record URL uniqueness, private custody, full 30-day evidence, rights, human signatures or any release decision. The report sets production writes, public projection, model, source admission and release authority **false** unconditionally.

## Engineering work packages following this phase

1. Private immutable source generation/custody with controlled access and safe restore. The present application custody session is test-only and is not permission to use a real store.
2. Exact source registration proposal outside discoverable production manifests, including publisher/issuer, language, collection and permitted source-use actions.
3. Per-candidate canonical URL collision and source-to-record assignment audit against frozen production snapshots, with no body/URL export.
4. Copy-only transaction and idempotency rehearsal in an isolated database, preserving existing IDs and source identities; no active production DB rewrite.
5. Rights-reviewed metadata/link/body/photo projection through the existing governed publication contract, plus textual, binary, cache and old-history disclosure checks.
6. Owner-approved, exact-commit release plan, site output validation and verified rollback. Activation is a separate PR after genuine Day 7/14/30, 30 consecutive days and C1–C13 reviews.

**Do not implement ingestion in this PR.** The older Singapore-specific scripts/promote_shadow_records.py utility does not confer AFP/Vietnam permission or provide a modern private-custody production boundary.

## Verification and stop conditions

The focused Python 3.9 tests use only synthetic SQLite and synthetic checkpoint receipts for malformed/forged approval, wrong source pins, duplicate JSON, symlinks, WAL sidecars, missing unique indexes, pre-existing source rows, no-body-leak checks and database preservation. One test inspects only the real checked-in database's columns/indexes and a source-specific registration count. The PR-only CI workflow checks unchanged production database, output and shadow source declarations.

Prerequisites remain independently reviewed draft PR #401 (per-run MOIT source-surface warning preservation), PR #403 (frozen cross-system checkpoint binding), issues #196 (MOIT rights), #332/#342 (real custody/release architecture) and #373 (source-specific desk program). Their approval is not implied by this new PR.

**Stop here after exact-head CI:** wait for authentic Oct 13/14 source evidence and human review; the next distinct technical phase is a metadata-only canonical identity/collision rehearsal, not auto-admission.
