# Sunday Briefs — enforce the production corpus audit before Anthropic or SMTP

## Problem

PR #240's `scripts/sunday_corpus_readiness.py` independently audited the actual production SQLite archive and same-Sunday successful daily marker, but it did not gate the live Sunday handoff itself. The writer's later `choose_evidence` check still rejected insufficient full text, but the workflow did not publish an earlier clear corpus readiness refusal **before** the Vietnam research refresh, draft scaffolding and potential model call.

## New workflow gate

`.github/workflows/sunday_briefs_editorial_handoff.yml` now calls
`python -m scripts.sunday_before_model_gate` immediately after resolving the Saturday reporting window and production desk registry. The independent audit uses `reconcile_db.read_only`, actual source selection rules and the tracked success marker. The command emits only selected production desk identities, eligible full-text counts, a bounded provenance label and explicit false approval flags. It does not output source texts or URLs.

On New York-local **Sunday October 11, 2026**, for the week ending **Saturday October 10**, the gate requires:

- The full Saturday reporting window, never a Thursday/Friday approximation.
- The tracked **October 11 successful production update marker**.
- At least two distinct **production** desks with stored, eligible, >=250-character full-text evidence. Japan/Vietnam shadow-research candidates do not satisfy this.
- No duplicate IDs, out-of-declared-desk records or misleading screened-out evidence.

On an **older week** explicitly selected via the existing `workflow_dispatch` mechanism, the gate still requires archived usable full-text evidence from two production desks, but labels the result `historical_snapshot_only_sunday_collection_unattested`. The present repository cannot reconstruct a past Sunday's successful update from its *current* marker. The read-only audit's allowed review horizon is aligned to the existing resolver: a reporting Saturday up to 91 days behind the latest reached Saturday can be previewed through the subsequent Friday (up to 96 days after the old Sunday), still without claiming that its collection marker is present. This historical path never claims completion proof, editorial approval or source-rights clearance. The existing resolver independently controls historical delivery authorization and Friday/Sunday exclusivity.

Any refusal halts before the model and SMTP steps. No fallback to headline-only input or manufactured desk coverage is permitted.

## Relationship to concurrent work

This change does **not** edit Claude prompts, `scripts/sunday_briefs_auto_writer.py`, editorial source receipts in #246, Japan research inputs, Vietnam MPS current-state reconciliation (#243), the strict October 10 MPS completeness policy, publisher reuse rules, country desk eligibility, production database, official daily collection, or email settings. Neither scheduled editor delivery nor publication is activated by merge.

## Verification

`python -m unittest tests.test_sunday_before_model_gate tests.test_sunday_corpus_readiness -v` exercises the actual wrapper and existing pure audit against synthetic two-desk evidence, the exact daily marker, premature Saturday, missing original text, old-week replay, and absence of approval. A focused read-only GitHub workflow tests that the Thursday October 8 source snapshot cannot be treated as a completed Sunday week. The full repository suite remains mandatory.

After the Sunday October 11 production update succeeds, this will be an enforceable **necessary** check for an owner-only manuscript preview, not a judgment that Claude's claims, translations or thematic argument are correct. Ben and Dylan still need the separate source and editorial reviews before delivery/publication.
