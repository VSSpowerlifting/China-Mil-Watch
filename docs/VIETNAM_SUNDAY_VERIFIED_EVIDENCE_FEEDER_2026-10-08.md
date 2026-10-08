# Vietnam: recurring, pinned shadow-to-Briefs input

## Why this exists

The user wants a **single thematic Sunday manuscript**, not a Vietnam
supplement. The unified Sunday generator is being implemented in PR #203,
shared with parallel Japan engineering. This Vietnam-only lane supplies a
deterministic source-specific input to **that same writer**, without modifying
Japan's collector, Japan's source choices, or the model's editorial decisions.

## Verified input chain

Use the already-established read-only MPS review queue generator:

```sh
python -m scripts.prepare_vietnam_mps_review_queue \
  --state-repo /path/to/cloned-read-only-state-repo \
  --state-commit <full-exact-MPS-shadow-head-sha> \
  --out-dir /tmp/vietnam-mps-reviewed-queue
```

This verifies the exact Git commit/tree on
`shadow/vietnam-mps-foreign-affairs`, full capture provenance, source clock,
SQLite state, source-version hashes and request/observation chain before
generating **metadata only**. A queue's signed hash proves that its metadata
has not changed since generation; it does **not** independently prove a
source is true or legally reusable.

Then join that audited queue with separately prepared, version-bound editorial
notes. For the October 10 test window, notes live at
`research/vietnam_briefs_candidates/editorial_notes_2026-10-10.json`.

```sh
python -m scripts.prepare_vietnam_briefs_evidence \
  --queue /tmp/vietnam-mps-reviewed-queue/review_queue.json \
  --notes research/vietnam_briefs_candidates/editorial_notes_2026-10-10.json \
  --week-ending 2026-10-10 \
  --existing /tmp/editorial/2026-10-10.json \
  --out /tmp/sunday/2026-10-10.json
```

The `--existing` regional packet is optional, and is how the Vietnam
contribution preserves separate Japan entries **unchanged**. It never edits
that prior input and refuses to overwrite the output.

The output follows `ipr-private-drafting-evidence/1` as implemented in
PR #203. The Sunday writer then loads the temporary packet via its
`--include-research --research-packet /tmp/sunday/2026-10-10.json` flags.
This feeder is a **reusable tool**, not a deployed Sunday action yet.

## Source eligibility, rights and omissions

- Only MPS foreign-affairs Vietnamese originals, exact canonical HTTPS URL
  and ten-digit article identities; no National Defence Journal, inaccessible
  Ministry of National Defence pages, or unreviewed MOIT sources.
- One to three candidates per weekly editorial packet; publication must
  fall within the actual Sunday–Saturday reporting window. If a source has
  no matching synopsis, the producer does **not** invent any analysis.
- Candidate must be machine-reviewable, with no blockers and with original
  text state; the synopsis must pin the **current** source content-version
  digest, URL and publication date. A source revision invalidates an old
  synopsis until someone rechecks it.
- The JSON contains no ministry full text and no raw captures. Version
  hashes use MPS's `mps-vi-content-v1` rule, not the Japan PDF's separate
  `sha256-text-original-utf8` rule.
- Research synopses remain unapproved working interpretations; they have
  **not** received full-body human source-fidelity review or publisher
  reuse authorization simply because they are in this file.
- The output never counts the Vietnam Desk as live, fabricates numeric
  production IDs, grants rights, populates SQLite or approves publication.
- Japan entries are passed through but not reclassified. Japan-specific
  evidence validation and selection remain the responsibility of the
  separate Japan workstream and the shared #203 schema.

## What is and is not automated

Automated here: audited queue ingestion, exact source-version joins,
calendar cutoff, verified metadata handoff and deterministic private packet.

Still needed for genuinely **autonomous Sunday operation**: the runner must
read the exact, current MPS shadow commit after Saturday, execute both
review scripts offline, provide an actually current source-specific synopsis
catalog, join the common Japan packet and pass the result to PR #203's private
drafting CLI. No scheduled workflow or publisher network access is changed in
this PR. Source synopsis preparation needs an independently lawful and verified
process; **do not automatically treat a newly captured headline as its
article summary**.

## Coordination contract with Japan and Sunday writer

- Japan branch owns Japan source review and the entries with `desk=japan`.
- Vietnam branch owns MPS-only review and entries with `desk=vietnam`.
- Shared PR #203 owns editorial theme selection, Claude prompt, citation
  schema, full-week cutoff, email and returned-file checks.
- Final CI/rehearsal must prove both country families can appear in the same
  **one** private model prompt with distinct IDs; a coherent editorial focus
  should permit dropping one country when the stories are unrelated.
- Sunday's message must be a single draft for Dylan, never a compilation
  assignment. All external sources cited publicly still need separate human
  source approval and Brief owner signoff.

Run `python -m unittest tests.test_vietnam_briefs_evidence_feeder`, then
the exact-head full offline CI before merging. Shadow-state validators should
also be run against current immutable state as a separate, external-to-checkout
rehearsal.
