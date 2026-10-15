# AFP and Kemhan — owner-authorized permanent link metadata, not yet publicly released

**Owner decision recorded October 15, 2026.** The owner explicitly approved
bringing `ph_afp_articles` and `id_kemhan_news` online as **permanent,
automatically updated, verified official-link metadata feeds** and stated that
**human review has occurred**. This is a real owner declaration; it supersedes
"general approval remains to be sought" for these exact two metadata-only
families. See [activation program #673](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/673).

Do **not** turn that assertion into invented source-specific review decisions.
No machine-readable named reviewer/checklist/signature/time-per-record has been
supplied in this branch. The recorded statement is truthful:
`owner_confirms_human_review_occurred=true` while
`machine_verified_record_specific_human_review_receipts_in_repository=false`.
Collect or locate the actual existing review attestations and **match** their
source IDs, version digests and dispositions; do not insist the owner repeat the
human review. Independently confirm link-use and noindex decisions.

## Version-bound scope

- **AFP:** frozen reviewed cohort `shadow/ph-afp` exact Git
  `8a63ba423818e30d147096fd1a32949cf6905ee5`, 23 captured originals.
  Last new source `afp:1409` matched the original Oct 15 run
  `38731523240-1` and its source SHA in [PR #678](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/678).
  Genuine real-source metadata candidate proof is in [PR #676](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/676).
- **Kemhan Berita:** `shadow/indonesia-kemhan` exact Git
  `0595c6677be24f8f0f33aecb28eec0050e36e8f9`, 31 originals.
  The one Yonif 880 publisher-geography discrepancy is always **held** and
  excluded from release. Official Berita is *first-party Kemhan publishing*,
  not a republication by a second organization.

The two actual Git rehearsal metadata manifest digests are pinned in
`config/afp_kemhan_owner_link_activation.json`. This source-bounded policy
contains no right to publish original articles, headlines, photographs, PDFs,
translations, editorial analysis, model inputs, or weekly mail.

## Implemented release engine

`core/regional_official_link_release.py` supplies:

- A typed, country-neutral **metadata-only** `regional_official_source_links`
  SQLite schema contract, deliberately separate from the legacy `articles`
  corpus and Korea's temporary country-specific table.
- Exact-source cohort pin checks against immutable Git + deterministic
  manifest SHA from the existing #676 intake; title/body fields, forged
  permissions, mismatched labels and unheld exclusions are refused.
- Strict per-source ID/date/canonical HTTPS official URL/issuer or publisher
  attribution; rejects duplicate official URLs and collisions with legacy
  article URLs.
- Atomic savepoint import, rollback on conflict and idempotent matching reruns.
  Changing the version/date of a previously published link causes a HOLD, not
  a silent replacement. A first-party link never implies full-text custody.
- **Fail-closed release trust:** a purported review/Actions JSON with positive
  flags is *insufficient*. The actual writer requires a trusted independent
  verifier callback authenticating provenance against current original
  collection and review evidence. No production workflow supplies that yet.

**Important:** `SCHEMA_SQL` is for *disposable synthetic test databases only*.
We deliberately do **not** claim a migration is deployed. Concurrent PR #657
(China tombstones) and PR #670 (Korea link metadata) currently both specify
migration `0008`; do not merge a third migration or run this CREATE TABLE
against tracked `pla_watch.db` until migrations are explicitly serialized
and the migration ledger is reconciled. This branch does not touch `pla_watch.db`,
`output/`, `gh-pages`, shadow Git or real publisher endpoints.

## Exact remaining steps to permanent production

1. Merge the source-cohort work (#676, #678) only after full exact-head tests
   pass and current main is rebased. Preserve the existing historic receipts.
2. **Recover, don't invent** completed reviewer attestation(s) and bind each
   permitted publisher link to source ID and actual captured version;
   ambiguous/not-included records remain held. This owner declaration is
   already recorded for both exact families.
3. Run authenticated all-visible attempt/job + original source ledger
   qualification for each family. For AFP, the Oct 7–13 seven positive
   collection days are supported by machine evidence, but deleted historical
   attempts cannot be asserted exhaustively verified. Indonesia's Day-7
   machine proof is consistent but remains separately review-scoped.
4. Finish the unique versioned regional-source-index migration after #657
   and #670 collision is resolved. Check real DB migration ledger and
   `verify_db_current.py` on a disposable real-schema copy.
5. Replace the synthetic `trusted_validator` seam with a **real immutable
   Git original + source review + Actions-history + owner authorization**
   verifier inside the one production publisher. Never substitute an unsigned
   caller-supplied receipt or test lambda.
6. Serialize production DB updates with existing daily writer, expose
   admitted links in regional search + AFP/Kemhan country pages, and deploy
   only allowlisted changed Pages files. Prove exact `main` SQLite →
   `main:output/` → `gh-pages` parity.
7. Watch one genuinely new official AFP/Kemhan source item after activation:
   scheduled collector → checked new version → DB row → site entry without a
   human-authored record PR. A zero-new-record healthy run is valid but does
   not prove first-new arrival.

The release is **not done** until all those checks succeed, however
unambiguous the owner's go-ahead is. There is no policy reason to build
another standalone collector or demand a second general owner permission.
