# AFP and Kemhan: real-origin held metadata handoff (October 15, 2026)

The release target is a permanent **regional official-source index**, not a
second isolated shadow browser. This PR supplies the version-bound,
metadata-only **candidate stage** for AFP and Kemhan. It never auto-admits a
record, changes `pla_watch.db`, alters a desk status, or publishes a link.

## Actual existing-source proof

The [GitHub Actions held-metadata CI](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38800041251)
read the **actual** immutable Git shadow states into transient runner
checkouts and ran `scripts.private_country_desk_reader.build` followed by the
two-family canonical source-projection contract:

| Family | Pinned state SHA | Rows | Holds |
| --- | --- | ---: | ---: |
| Philippines AFP `ph_afp_articles` | `8a63ba423818e30d147096fd1a32949cf6905ee5` | 23 | all held |
| Indonesia Kemhan Berita `id_kemhan_news` | `0595c6677be24f8f0f33aecb28eec0050e36e8f9` | 31 | all held, including one known publisher-geography discrepancy |

The first real run passed. It returned deterministic metadata manifest hashes
but no original article titles/bodies, document binaries, photos or media.
Exactly one Indonesia semantic exception remains held.

**AFP roster reconciliation:** the earlier approved-to-review **22-original
unsigned docket** in `docs/PH_AFP_22_ORIGINALS_HUMAN_REVIEW_2026-10-15.md`
covers pinned historical capture runs, while the current state reader returned
**23 stored records**. The additional current record must be reconciled to
its actual collecting run and independently reviewed; 22 must not be
represented as a complete current 23-record source review. No existing 22
review item inherits automatic approval.

**Indonesia roster reconciliation:** the 31 count equals
`docs/INDONESIA_31_ORIGINALS_PERMANENT_REVIEW_2026-10-15.md`.
Fifteen previously released publisher-directory links are *not* fifteen
production archive records. One source is withheld for the known geographic
discrepancy; the remaining unpublished and unapproved items are only review
candidates.

## The exact next production increment

1. Finish the fully authenticated scheduled-run/attempt/job and source-ledger
   qualification for each family. AFP's Day-7 and Kemhan's Day-7 evidence are
   independently scoped. Do not substitute manually rerun captures for a
   genuine successful scheduled collection date.
2. Revalidate exact stored first-party body/capture hashes and source
   authenticity where required; source-version metadata hashes in this PR
   **are not body/capture hashes**. Evaluate source-specific original-language,
   factual holds, link-use authority, publisher noindex and rights evidence.
   A source family is not eligible because a syntactically valid candidate
   packet says `all_candidates_held: true`.
3. Define an exact owner-approved, family-specific **link-only** decision and
   an authenticated receipt linking collector evidence, reviewed source
   version, allowed URLs/dates/issuer or publisher metadata and release scope.
   The standing permission for Korean MND links must not be silently treated
   as a blanket permission for every AFP/Kemhan original or other family.
4. Build/reuse **one** regional source-index SQLite migration and guarded
   importer once the concurrently proposed Korea and China migrations resolve
   their duplicate `0008` version conflict. Retain the legacy `articles`
   collection, issue citations, China retirements and held shadow originals.
   Idempotency, URL collision review and failed-run rollback must be tested.
5. Integrate the eligible source family's scheduled collector output into the
   serial production writer, render only its desk page and shared source index
   in scope, and independently verify committed SQLite and `gh-pages` bytes.
   Prove that one *new* external official release becomes discoverable without
   a manual record PR before marking that family fully operational.

**Issuer vs publisher:** AFP articles are first-party AFP publications.
Kemhan Berita is first-party Indonesian Defense Ministry newsroom publishing;
its stored original metadata has no separate issuing authority, so the
regional candidate represents `official_issuer: null`,
`official_publisher: id_kemhan`, and `official_republisher: null` rather
than inventing a separate formal ministry statement or a republication.

This staging stage intentionally does **not** access new external publisher
websites, copy original titles or texts into public SQLite, run AI, send editor
emails, or authorize the source-linked public archive. It is evidence-bound
engineering preparation for the permanent activation program in #673.
