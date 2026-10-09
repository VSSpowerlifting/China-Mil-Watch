# Regional research: machine-attestation reconciliation (Issue #271)

This optional **metadata-only HOLD join** takes the separately generated
Japan historical MOD source attestation and up to four independently generated
Vietnam MPS historical review queues, then compares each to the existing
regional research HOLD receipt. **No held record becomes eligible for the
regional thematic AI selector, the private Sunday manuscript, editor email,
production publication or source-body reuse.** No source text is returned.

This layer deliberately reuses existing source-specific verification instead
of rebuilding its own PDF extractor or Ministry of Public Security shadow
database checker.

## What each machine receipt can establish

- **Japan MOD:** the existing
  `scripts.attest_japan_sunday_research` validates the precise Oct 10 roster,
  and for `JP-W41-06` rechecks the historical shadow Git-object SQLite row
  and Japanese extracted-text digest. The two official HTML entries still have
  **no immutable full article body capture**; an extracted-text digest is
  **not** proof that the original PDF bytes were preserved or that humans
  checked its full content.
- **Vietnam MPS:** the existing
  `scripts.prepare_vietnam_mps_review_queue` exports a metadata review queue
  from an independently verified exact Git shadow-state commit. The queue's
  self-digest detects later modifications; **a caller-created hash is not
  independent proof that its alleged Git state actually existed**. Its
  source-specific version and canonical URL still have to agree with each
  held citation.
- **Multiple historical commits:** the Oct 10 research packet refers to
  *two different Vietnam MPS historical state commits*. Oct 5 records use
  `46f6a0e59e25b03868bf7ad600963d6921ee5124`; the Oct 7 Australia note
  uses `c7c13dc7c15d855412afff99db23695dd50e51a5`. The reconciler
  expects separate queues for each commit. It never silently treats one
  queue as verifying both, or fabricates missing records.
- **All claims remain historical:** a Git commit and immutable extracted-text
  proof are not current-publisher page verification, original-language
  human editorial review, copyright clearance, research promotion, or public
  publication permission.

## Operator workflow

First create the regional HOLD report with
`scripts.regional_typed_research_holds`. Independently run the existing
read-only Japan source-attestation workflow against `shadow/jp-mod`, and
generate the two Vietnam queues from the validated `shadow/vietnam-mps-foreign-affairs`
branch with `scripts.prepare_vietnam_mps_review_queue`. The queues must be
derived from the **actual Git state**, not assembled from this documentation
or an AI output. Only then compare them:

```bash
python -m scripts.regional_typed_machine_receipts \
  --holds /private/held-japan-vietnam-evidence.json \
  --japan-attestation /private/japan-source-attestation.json \
  --vietnam-queue /private/oct5-mps-review/review_queue.json \
  --vietnam-queue /private/oct7-mps-review/review_queue.json \
  --out /private/regional-machine-reconciliation.json
```

Paths above are illustrative. The input files must already exist; the
output directory must already exist, outside the repository. The new
output JSON is exclusively created, mode 0600, never overwritten. It
includes the exact typed IDs and the evidence *class*, not publisher URLs,
titles, analyst synopses, copied bodies, SMTP recipients or credentials.
Omit an input receipt rather than forge one: the missing attestation/commit
is shown as a **HOLD**, not treated as absence of official publishing.

The output always says:
`model_input_authorized: false`,
`editor_email_authorized: false`,
`production_desk_promoted: false`, and
`publication_authorized: false`.

## Later stage: actual owner review

Reviewers must independently compare the **current** official publisher
version, original language and source-use/retention rights for each source;
sign an appropriately scoped edition-specific human approval; and recheck
the Sunday reporting window. This machine receipts PR intentionally **does
not** create such a signature or wire any of these typed IDs into #263 or
#266. The first Sunday exact-manuscript owner release remains unchanged.
