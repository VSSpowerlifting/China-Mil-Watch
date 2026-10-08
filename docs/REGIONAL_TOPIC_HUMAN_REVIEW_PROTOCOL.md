# Topic taxonomy: independent human-review protocol

**Status:** workflow infrastructure only. Nothing in this phase approves a record label, changes the taxonomy, attaches a topic, touches production/shadow databases, rerenders pages or alters collection. The frozen 60-record pilot is already part of the repository from PR #128.

## Why this exists

The original 60-record study and its skeptical second pass were both model-authored. Comparing them does not create a genuinely independent ground truth. Indo-Pacific Record needs a source-first independent-review step **before** accepting labels, measuring model performance or applying any classification at scale.

This protocol deliberately separates the **blind phase** (source identity, original-language evidence, vocabulary, reviewer choices) from the **comparison phase** (original and second-model suggestions). The first phase does not read \`review/assessment.json\` or display the original model's proposed topic assignments. However, the initial excerpts were selected by the model; consequently, it is **partially blinded rather than a fully independent corpus sample**. Review the entire pinned body, not excerpts alone.

## Step 1: generate an unsigned packet

From the repository root:

\`\`\`sh
python3 scripts/topic_review_gate.py --taxonomy-version 1 packet > /tmp/ipr-topics-blind.md
python3 scripts/topic_review_gate.py --taxonomy-version 1 template > /tmp/ipr-topics-review.json
\`\`\`

The packet shows all 60 records, the available original-language quotes, original titles, source URLs, stable desk/source identity, source dates and preserved-body SHA-256. It hides model recommendations and the 30 original flags. The template contains **only pending decisions**, blank reviewer information, and no populated topics. Neither command reads or changes SQLite.

For v2 once it has been merged, use \`--taxonomy-version 2\` to generate a **separate** review whose vocabulary includes \`military_hadr\`. The validator pins the exact taxonomy version and file contents. Do not edit an old v1 template to claim it is v2 or silently port prior assignments.

## Step 2: independently read, then write decisions

Provide the packet and original sources to a real reviewer with the language expertise to assess the record. The reviewer should not read \`ledger.json\` proposals, \`LEDGER.md\`, \`review/assessment.json\` or \`review/REVIEW.md\` before completing their independent decisions.

Use the generated JSON fields for each record:

| Field | Required meaning |
|---|---|
| \`decision\` | \`pending\`, \`classified\`, \`abstain\`, or \`unassessable\` |
| \`topics\` | Slug(s) from the **selected** vocabulary, only when classified |
| \`rationale\` | Specific reason for classification, abstention or insufficient evidence |
| \`read_full_source\` | Boolean; must be true for classified/abstain decisions |
| \`reviewed_at_utc\` | Actual reviewer judgment time in UTC ISO format, ending in \`Z\` |
| \`reviewer.name\` | Actual reviewer's name, not a model or synthetic fixture |
| \`reviewer.independent_reading_attested\` | Explicit true only if reviewer independently reviewed originals **before** seeing suggested topics |

A missing-body record should remain \`unassessable\` with a reason rather than be forced into a topic; the validator permits \`read_full_source: false\` for that case. No reviewer fields should be auto-populated. The program checks syntax and self-attestation but **cannot prove** that the author is human, independent or correct.

For each classification, read the original-language full body pinned by the original pilot; the excerpt may be incomplete, biased, or end mid-sentence. Check every proposed positive topic and important omitted topics. Source language and sovereignty assertions remain attributed to the issuer, not validated as facts. If a record contains multiple articles or sections, annotate that limitation in its rationale.

The review JSON is a separate proposed human-review artifact, **not** a set of \`TopicAssignment\` database rows. Do not copy it directly into any corpus.

## Step 3: validate without revealing suggestions

\`\`\`sh
python3 scripts/topic_review_gate.py --taxonomy-version 1 validate \
  --decisions /tmp/ipr-topics-review.json
\`\`\`

Partial reviews are valid while unfinished, but their reported \`reviewed\` count is descriptive. The validator checks the exact frozen ledger and taxonomy hashes, 60 unique stable record identities, the topic slug vocabulary, nonduplicate labels, supported abstentions, nonempty rationales, UTC review times, full-body reading attestations, and named reviewer self-attestation.

When all decisions are complete:

\`\`\`sh
python3 scripts/topic_review_gate.py --taxonomy-version 1 validate \
  --decisions /tmp/ipr-topics-review.json --require-complete
\`\`\`

No incomplete, unsigned, tampered, changed-vocabulary or fake-version review should pass the full-review gate.

## Step 4: only then compare judgments

\`\`\`sh
python3 scripts/topic_review_gate.py --taxonomy-version 1 compare \
  --decisions /tmp/ipr-topics-review.json > /tmp/ipr-review-comparison.md
\`\`\`

The comparison **refuses** to reveal model suggestions until all 60 records have completed reviewer choices, real reviewer identity fields, and the explicit independent-reading attestation. It then displays original model topics, second-model suggestions and the reviewer-selected topics side by side.

The script does **not** assign human approval, produce accuracy scores, declare reliability or migrate/import topics. A v2 reviewer cannot compare v2 choices directly against v1 model suggestions without a separately specified cross-version interpretation. For publication-grade reliability, obtain a second genuinely independent source-language reviewer and handle disagreements openly.

## Preservation and boundaries

- Inputs: immutable PR #128 pilot ledger, optional prior second-pass assessment **only in the completed comparison**, versioned vocabulary.
- Outputs: stdout only; redirect to temporary documents when wanted. The program creates no review record on its own.
- Unchanged: \`research/topic_pilot_v1/ledger.json\`, \`research/topic_pilot_v1/review/assessment.json\`, \`taxonomy/regional_topics.v1.json\`, all DB/output files, and all shadow stores.
- This phase can merge as a **tool for real review** before/after PR #137. It does not depend on v2 activation or clear an existing record-level human-approval gate.

Suggested next owner action: invite a suitable source-language reviewer to complete the blind v2 review after #137 lands, separately record judgments, then request editorial adjudication of disagreements. Do not begin production backfill on the strength of this tool alone.
