# Vietnam MPS — metadata-only production preflight (no article publication)

**Purpose:** rehearse a realistic three-record Vietnam intake using only
source-identifying metadata and short **original, unapproved IPR abstracts**.
This does not write to `articles` or authorize Vietnam Desk production
or public display. It leaves the signed full-text staging gate
(`prepare_vietnam_mps_pilot.py`) unchanged.

## Why not put the three records into `articles`?

The existing production article table participates in scraping, analysis,
rendering, and downstream source counts. Inserting metadata-only records
with empty bodies would misleadingly register them as collected articles,
particularly while public text-retention rights and human source review
remain unresolved. A disabled source row alone is not a publication barrier
once `articles` contains data.

Instead `scripts/preview_vietnam_mps_metadata.py` creates **a new isolated
SQLite file**, outside the IPR checkout. The only user-defined table is
`preview_records`, and its schema enforces
`publication_authorized=0`, `original_article_body_retained=0`,
`rights_state='unresolved'` and
`review_state='pending_human_signoff'`.

## Exact inputs and trust boundary

The script reads three sources only:

1. The exact MPS shadow commit
   `46f6a0e59e25b03868bf7ad600963d6921ee5124`, reachable from the
   `shadow/vietnam-mps-foreign-affairs` branch. It runs the complete
   existing immutable ledger/database/capture verifier and rebuilds the
   signed-*nothing* queue (digest
   `a32a445f1e6734ca0763ceac30986ce137b305e1130dc447fe40410a2460d582`).
   No stored Vietnamese publisher article body is copied into the preview.
2. A **copy** of the migrated production database stored outside this
   repository. It is opened `mode=ro&immutable=1`; the script checks
   `PRAGMA integrity_check`, the required table/column contract and SHA-256
   before/after. Its only data operation is a URL-collision check.
3. A version-locked three-record IPR editorial draft roster. Each original
   abstract is newly authored by IPR rather than copied from MPS, and
   references a specific current source-content hash. Absent/mismatched
   records, machine holds, or an attempt to infer signoff are refused.

Both the source clone and output must be outside the checkout. The output
directory must not exist, and is created only after the provenance, exact
three-record roster, production schema, and collision checks pass.

## Command (local or disposable GitHub Actions runner)

```bash
git clone --single-branch --branch shadow/vietnam-mps-foreign-affairs \
  https://github.com/VSSpowerlifting/China-Mil-Watch.git \
  /tmp/vn-mps-readonly-state

cp pla_watch.db /tmp/ipr-prod-snapshot-for-preview.db

python scripts/preview_vietnam_mps_metadata.py \
  --state-repo /tmp/vn-mps-readonly-state \
  --state-commit 46f6a0e59e25b03868bf7ad600963d6921ee5124 \
  --production-snapshot /tmp/ipr-prod-snapshot-for-preview.db \
  --out-dir /tmp/vn-mps-metadata-preflight
```

Output: `unapproved_metadata_preview.db` and
`preview_manifest.json`, both external to the repository. The manifest
includes the exact state and queue fingerprints, a hash of the read-only
production snapshot and preview DB, per-record identity/date/title hash,
collision flags, and **zero approval, article-import or rights fields**.
The source original titles are present as identification metadata inside
the isolated preview DB; no source article prose/HTML, capture files,
stored review signoff, or public build artifacts are included.

## Editorial abstract / policy-status checks

- `mps-vi:1791199100`: prospective Türkiye security-technology
  cooperation. **No executed industrial transfer or procurement award**
  is established by the source.
- `mps-vi:1791199677`: Concordia research/training discussions.
  Its cited memorandum concerns the **Vietnamese education ministry**,
  not an executed MPS–Concordia agreement.
- `mps-vi:1790933646`: Vietnam–Myanmar anti-crime discussions.
  Distinguish **prior signed agreements** from proposed treaty/MOU
  negotiations and renewed dialogue.

The original IPR summaries are **drafts** tied to the source digests and
must receive separate editorial review before any eventual public use.

## Never inferred from a successful run

A passing preview proves only that the current production schema can be
inspected, the source identities/versions are stable, and three pieces
of metadata plus original draft abstracts can be stored in an isolated
SQLite schema. It does **not** prove that copyrighted source text can
be archived or republished, that the editor signed six checks, that
`articles` was written, that Vietnam is a public desk, or that Day
7/14/30 collection qualification has been met.

For future promotion, first resolve human rights/integrity signoff and
desk-wide publisher/consumer presentation choices. A separate reviewed
production implementation must explicitly decide whether it supports
metadata-only reference records in a new dedicated table with an
approved reader, or retains full original body under a lawful source-use
basis. **Do not insert placeholder bodies into the existing articles
table as a shortcut.**
