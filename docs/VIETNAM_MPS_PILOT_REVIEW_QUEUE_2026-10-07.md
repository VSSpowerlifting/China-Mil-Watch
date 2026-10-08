# Vietnam MPS — accelerated pilot record-review queue

**Purpose:** Move the merged PR #127 infrastructure from a generic approval
contract to an exact, human-reviewable inventory of records from one
immutable MPS shadow state commit. This is a preparation phase, **not**
record approval or live production admission. It does not alter a source,
schedule, checked-in database, website, or a reliability checkpoint.

## Inputs and trust boundary

The command `scripts/prepare_vietnam_mps_review_queue.py` requires:

* A clone of `shadow/vietnam-mps-foreign-affairs` with its Git objects and
  source ref (not an untrusted copied shadow.db).
* The source's exact 40-character state commit hash.
* A new output directory **outside** the IPR checkout.

The implementation reuses the existing formal source-state commit/reachability
verification, Git-blob-only export, complete raw-capture and database hash
validation, isolated ledgers and the MPS full-source review contract. It
then prepares a sorted per-record metadata inventory, preserving held rows
rather than silently omitting anomalies or incomplete bodies.

The output is three files:

| File | Contents |
| --- | --- |
| `review_queue.json` | Complete MPS record metadata, hashes, source URLs, machine blockers, state commit/tree, Day 0 and deterministic queue hash; no article body |
| `REVIEW.md` | Human-readable per-record source checklist and machine hold status; no article body |
| `approval_template.json` | Explicitly unsigned, `reviewer: null`, `reviewed_at_utc: null`, **zero selected records** and all six review checks blank |

**Machine candidate is not approved.** The only way forward is to inspect
the original Vietnamese source page, its archived **full** body/version,
date and issuing attribution, and separately establish a lawful and
documented decision about original-text retention and public reproduction.
Access to a government website is **not** automatically permission to
republish its prose. A hold cannot be bypassed by merely filling a template.

## Commands

Using a fresh source-state clone outside your working repository:

```sh
git clone --branch shadow/vietnam-mps-foreign-affairs --single-branch \
  https://github.com/VSSpowerlifting/China-Mil-Watch.git \
  /tmp/ipr-vietnam-mps-state
MPS_STATE_SHA=$(git -C /tmp/ipr-vietnam-mps-state rev-parse HEAD)

python scripts/prepare_vietnam_mps_review_queue.py \
  --state-repo /tmp/ipr-vietnam-mps-state \
  --state-commit "$MPS_STATE_SHA" \
  --out-dir /tmp/ipr-vietnam-mps-review-"$MPS_STATE_SHA"
```

The pinned evidence used by this command comes from the Git commit's
`state/` object tree, **not** a potentially dirty state checkout. The
output directory must be new and not symlinked. The resulting files contain
no captured source body or raw response bytes.

Inspect the source's archived content locally, never by putting source
article prose into a PR description or durable review metadata. For
example, the source-state database's text and version hashes are available
through a **read-only** SQLite connection in the local clone; reconcile each
selected version with its printed public source page. Preserve the original
Vietnamese without pretending that machine translation or keyword selection
has already been approved.

When every chosen record has actual human signoff (at most ten records per
authorization), construct a separate authorization in the schema required
by `scripts/prepare_vietnam_mps_pilot.py`, including:

- exact source identity and **current** SHA-256 from the queue,
- `checks` with all six decisions explicitly true, if verified,
- a named reviewer and an **actual** UTC review instant,
- `reuse_approved: true` only after verifying applicable reuse rights, with
  a substantive `rights_basis`.

The blank generated `approval_template.json` is not a valid authorization,
nor can it be used to infer approval. The PR #127 script still validates
approval *against the same pinned Git state*, and even then permits only
a **disposable copy** of the database to be changed.

## Maturity and release separation

The MPS remote Day 0 remains 2026-10-07. Its existing Day 7/14/30
milestones, success-only state publication and shared ministry host gate
are unchanged. MOIT energy, MOIT foundational industry, Government News and
the newly researched National Defence Journal are outside the review queue.

The future live release requires separately reviewed producer/consumer and
licensing decisions, a deterministic production DB and rendering diff,
deduplication/reconciliation with the still-running shadow collector, and
explicit owner signoff on any early-production exception. Nothing in
this PR approves those actions.
