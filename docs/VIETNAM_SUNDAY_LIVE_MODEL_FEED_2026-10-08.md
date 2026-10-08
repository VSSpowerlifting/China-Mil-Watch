# Vietnam MPS → the same Sunday thematic Brief generator

**Implementation:** PR #207 depends on the unified writer in #203. It is
deliberately narrow to avoid code conflicts with the separate Japan Desk work.

## What readers and Dylan should see

A single, AI-assisted article, not separate Japan/Vietnam appendices waiting
to be stitched together. The writer sees up to ten verified production corpus
records and up to eight separately labeled Japan/Vietnam official-source
research leads. It chooses one specific regional theme and is explicitly
allowed to OMIT a country when its material is unrelated. Dylan edits the
article and checks referenced primary sources. Ben remains responsible for
actual source approval and publication.

### Source hierarchy, **not** artificial desk promotion

1. **Production record:** archive row with full text and numeric IPR ID,
   offered by a live production-backed desk. This is the normal Briefs
   source trail and its usual two-live-desk publication threshold.
2. **Pinned, source-specific private synopsis:** for Vietnam, a short
   attributed editorial note whose record's source URL, Vietnamese headline,
   visible publication date, MPS source identity, current-version digest,
   source hash rule and immutable Git source-state commit match a fully
   checked isolated shadow collector state. The note is NOT itself a
   complete or human-approved original translation.
3. **Metadata-only discovery:** a *new* MPS publication with a completely
   validated shadow source capture but no previously prepared synopsis.
   The model receives original-language headline, date, publisher, exact
   URL, immutable state commit and content-version digest, plus one **fixed**
   non-interpretive metadata-only explanation. It must never assert that
   the events described in a headline happened until the original text
   receives substantive review.

An article may enter a private model draft under classes 2 or 3; neither
class is permission to reproduce the stored Vietnamese source bodies or to
claim the Vietnam Desk is operational in the public archive. Full individual
source/rights review is still required before any non-production source can
support a public numbered Brief. Do not fill human approval booleans via code.

## Production-Sunday sequence (once owner activates the workflow)

- Sunday workflow resolves the New York-local Saturday reporting cutoff,
  checks Sunday's successful **production** database update and that the
  Friday SMTP service is not simultaneously enabled.
- Clone `shadow/vietnam-mps-foreign-affairs` into the ephemeral Actions
  runner. Clone is **read-only**; no publisher requests or Git pushes.
- Pass its actual HEAD commit to
  `scripts/prepare_vietnam_briefs_model_evidence.py`. It verifies the
  commit belongs to the claimed isolated branch and is its present tip,
  exports **Git-owned** state bytes to a disposable directory, then runs
  `review_vietnam_ministry_state.review` to check complete ledgers,
  capture hashes, current versions, source identities, dates, clock and
  SQLite integrity.
- A recent healthy shadow attempt is mandatory (target day between reporting
  Thursday and Sunday). A stale healthy run is **not** proof that Saturday's
  source window was covered.
- `prepare_vietnam_mps_review_queue.compile_queue` separately ensures only
  machine-review-eligible, unheld current-version records can be offered.
  A curated synopsis is reused only when its existing source version digest
  exactly matches this validated state. A version change downgrades it to
  **metadata only** rather than letting the model repeat stale specifics.
- The private export merges the new MPS items with Japan source notes from
  the existing exact-week packet. Optional
  `--japan-packet <exact Saturday JSON>` accepts an independently audited
  Japan export instead, refusing any Vietnam entries in that outside packet.
- Output is always a disposable `$RUNNER_TEMP/…/<Saturday>.json` file.
  It contains source links/metadata and brief authored notes, **never copied
  ministry article text**, and is neither committed, pushed, uploaded as a
  public artifact nor printed to CI logs.
- The Sunday writer receives
  `--full-week --include-research --research-packet <path>`. The model
  gets the same source-typed input contract for Japan and Vietnam; the
  returned `.txt` is one cohesive manuscript with an editable focus and a
  separate immutable official-source appendix.
- SMTP, approval, numbering and publication remain unchanged. There is NO
  scheduled email until the owner enables the guarded Sunday delivery
  variable and disables Friday's separately guarded service.

## October 10 evidence expected

The MPS collector's previous state has two original Vietnamese releases
dated October 5 about security-industrial discussions with Turkish firms
and a research/training meeting with Concordia University. A prior frozen
editorial synopsis exists for each with exact content-version checksums.
The Sunday feeder does **not** assume those texts have remained unchanged.
It verifies the newest shadow state; if current content versions differ,
the old details are NOT supplied to Claude.

It may be editorially inappropriate to combine these two releases with a
Japan exercise notice or Indonesian disaster-relief activity. The model is
instructed to pick a single defensible theme and leave irrelevant evidence
unused. If no coherent multi-desk narrative is supported, a private draft
should say so rather than fabricate coordination.

## Longer-term limits and path

- **New MPS articles automatically enter** as validated *metadata-only*
  discovery notes if the shadow collection has preserved complete source
  versions. This is a real automated research feed, but **substantive
  content synthesis for newly published Vietnamese reports still needs a
  reviewed source-use policy** and source-backed synopsis logic. The
  existing static October 10 notes are just the first source-specific input.
- MOIT energy and foundational-industry remain separate clocks and source
  policies; do not merge these into MPS without a source-specific module and
  human gate. Day 7 (October 14), Day 14 (October 21), and Day 30
  (November 6) still apply to the three independent Vietnam ministry
  collectors.
- Japan's `shadow/jp-mod` pipeline and its source integrity reviews are
  being handled independently. The handoff here is an optional **fully
  validated**, exact-week Japan JSON packet; do not alter Japan collectors,
  Japanese dates, rights decisions, or old source hashes in the Vietnam PR.
- Follow Issue #200 for an independently audited fully automatic Japan
  exporter, a source-use-safe way to derive *substantive* excerpts/synopses
  from new releases, reusable thematic selection, and a repeatable no-send
  editorial quality test.

## Tests / proof

```sh
python -m unittest -q tests.test_vietnam_briefs_model_feed tests.test_briefs_editorial_evidence
```

In addition, the isolated
`.github/workflows/vietnam_sunday_model_evidence_proof.yml` action performs a
**real read-only Git shadow-state replay** (not synthetic fixture only) from
the branch before the Sunday service is enabled. For October 10 it asserts
at least two genuine current-week MPS source cards and preserves both the
shadow clone and tracked production checkout. No model/SMTP call occurs.

This source proof is necessary but not sufficient: require green exact-head
full offline CI, an actual **one-article** Anthropic no-send rehearsal,
independent source-fidelity checks, owner signoff on Sunday delivery, and
human approval of any eventual published Brief.
