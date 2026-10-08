# Regional Topic v2 — eleven-record HADR independent-review handoff

**Status:** source-first review infrastructure. NOT classification, human approval, a gold standard, corpus backfill or deployment. Related: #128 frozen 60-record pilot, #137 v2 vocabulary, #142 60-record independent-review protocol, #153 editor-facing cross-desk evidence, #162 task.

This workflow is intentionally separate from the 60-record source-first review. It is a purposively selected **11-record** v2 HADR packet spanning **seven desks and nine event/context groups**, including **one record with no archived body** (P36). An assistant chose the cases and source excerpts. The reviewer is blinded to proposed assignments and candidate control roles, **not** to the subject of the sample or its model-assisted selection. It is neither a representative validation sample nor independent event corroboration.

## Generate handoff from the repository root

Use a local environment with the merged, unchanged frozen pilot ledger and the v2 vocabulary.

    python3 scripts/topic_v2_hadr_review.py packet > /tmp/ipr-hadr-blind.md
    python3 scripts/topic_v2_hadr_review.py template > /tmp/ipr-hadr-decisions.json

The Markdown contains original titles, issuer URL, source-stated date, original-language stored excerpts, source body hash, exact historical origin commit/blob/path, and the twenty v2 definitions. It deliberately omits assistant-proposed topic decisions, reviewer questions, HADR candidate roles and event-family keys.

Do **not** send the editor-facing research/topic_v2_crossdesk_hadr/packet.json to a purportedly independent reviewer. That packet exposes control roles and event grouping.

Reviewers must be qualified to read the original source language. Supply the pinned **full** original-language body via the archive, not merely selected excerpts, title, machine translation, or current URL. If the exact source is inaccessible, record an unassessable result rather than infer from a nearby document. In particular, P36 has no archived body; the corresponding P35 article is **not** P36's missing evidence.

## Review decisions: each record has its own human

Edit the generated JSON without altering identity fields, packet/taxonomy hashes, scope or the eleven-record membership. Multiple qualified reviewers may complete different rows; all entries remain bound to the identical source/version pins. A reviewer must supply their real name, the language they read, and an independent-reading attestation **for each record**. For each completed row:

- decision: classified, abstain, or unassessable (pending while work remains).
- topics: valid v2 slugs only for classified; multiple topics permitted only when supported by the full source. For abstain and unassessable use an empty array.
- rationale: a specific statement of the source-based reasoning or why assessment is impossible. Distinguish the issuing institution's assertions from independent factual verification.
- read_full_source: true for classified or abstain.
- reviewer.name: actual human reader; never a bot or an automatic fixture.
- reviewer.language_read: actual source language read for classified or abstain.
- reviewer.independent_reading_attested: true only if decisions were formed without seeing the editor-side candidate roles/model assignments.
- reviewer.original_language_reading_attested: true when full original-language text was actually read (mandatory for classified or abstain).
- reviewed_at_utc: real UTC judgment timestamp ending Z.

For an unassessable record, record a substantive rationale and actual reviewer identity. Do not assert full-body reading if the archive body is absent. No program can authenticate whether a name is real or whether a reviewer really read the source; oversight remains an editorial responsibility.

## Validate and compare in separate stages

Fast provenance, zero network/database writes (consistency with frozen pilot excerpts and source pointers):

    python3 scripts/topic_v2_hadr_review.py provenance

Optional stronger offline source replay from the **exact six original historical database Git objects**:

    python3 scripts/topic_v2_hadr_review.py provenance --verify-sources

Replay is a **separate checkpoint**. It does not fetch substitutes, trust current branch snapshots, certify source claims, or complete human review. An absent pinned historical object causes failure. Store actual result and commit pins in the editorial audit trail; do not claim it ran merely because fast provenance passed.

Partial decision review, without revealing model suggestions:

    python3 scripts/topic_v2_hadr_review.py validate --decisions /tmp/ipr-hadr-decisions.json

After all eleven source-specific decisions are independently made:

    python3 scripts/topic_v2_hadr_review.py validate --decisions /tmp/ipr-hadr-decisions.json --require-complete
    python3 scripts/topic_v2_hadr_review.py compare --decisions /tmp/ipr-hadr-decisions.json > /tmp/ipr-hadr-editor-comparison.md

Compare fails closed until **all eleven** decision rows have a named, self-attested reviewer, dated judgment and evidence-based rationale. Only then does it show the editor-facing provisional control roles and nine context groups alongside the independently selected v2 labels. P51/P52 share the same Philippine Sanlakas event; P35/P36 are related to the same Trident Resolve event. Eleven record judgments do not prove eleven independent occurrences.

Comparison is descriptive only: no v1-to-v2 unapproved label conversion, gold labels, accuracy estimates, record_topics inserts, topic-approval flags, or publication authorization. Resolve disagreements and secure explicit owner approval in a **subsequent editorial phase** before any production attachment.

## Tests and non-goals

    python3 -m unittest tests.test_topic_v2_hadr_review -v

The new code writes only to stdout. Shell redirection above creates local handoff files under /tmp, **not** repository assignments. The scripts neither open SQLite for writes nor contact source websites. Frozen #142 and #153 artifacts are not modified. There is no automated email or review impersonation. CI/browser/DB-output preservation must pass on the exact PR head before merge.

**Scope caution:** the 60-record independent review remains governed by scripts/topic_review_gate.py. Completing this smaller HADR task must never be treated as completing a 60-record review or regional taxonomy activation. Strong independent non-China controls for space_security, east_china_sea and export_controls_sanctions remain open research gaps.
