# Regional Topic v2 HADR — source-language reviewer handoff

**Status:** Administrative tooling for the already merged blinded human-review protocol (#164). It does not create human decisions, certify reviewer identity, approve a v2 classification, or change any source/production/shadow data. The sample is still **model-selected** and NOT a representative evaluation sample.

## Allocation by ORIGINAL source language

| Language | Pinned review IDs | Records | Archived original body available? |
|---|---|---:|---|
| English (en) | P35, P36, P49, P51, P52 | 5 | Four available; P36 has **zero archived body** |
| Chinese (zh) | P16, P21 | 2 | Two |
| Japanese (ja) | P38 | 1 | One |
| Indonesian (id) | P57 | 1 | One |
| Vietnamese (vi) | P44 | 1 | One |
| Korean (ko) | P58 | 1 | One |

The total is **11 review records across seven desks**; six language groups. This is not eleven independent events. Records P51 and P52 describe the same Philippine Sanlakas exercise, while P35 and P36 are linked to the same Trident Resolve exercise. None of the grouping information or assistant-proposed candidate labels belongs in the blinded reviewer packet.

**Staffing is intentionally blank.** No reviewer has been chosen, contacted, authorized, or represented as having read a source. Actual English-language reviewer(s) may cover the four readable English cases but must not manufacture a P36 source judgment from P35. Qualified people fluent in the relevant original written languages must perform the independent reading. Merely understanding an English translation is not an adequate original-language attestation.

## Export reviewer-specific source-first packets

From the repository root:

    python3 scripts/topic_v2_hadr_language_handoff.py packet --language en > /tmp/hadr-review-en.md
    python3 scripts/topic_v2_hadr_language_handoff.py template --language en > /tmp/hadr-decisions-en.json

Repeat for source-language codes zh, ja, id, vi and ko. Each Markdown file contains the twenty controlled v2 definitions and only that language's source IDs, titles, issuer URLs, immutable source archive pointers and **model-selected original-language excerpts**. It deliberately excludes editor roles, model topic proposals, event-group keys, review questions and other reviewers' records. The JSON files are unsigned.

**Important:** Neither the excerpt nor the URL is a substitute for the complete pinned original-language archived body. Before asking a human to attest to full-source reading, an editor must provide authenticated access to the entire preserved original at its named historical Git commit and body SHA-256. Merely supplying the Markdown packet is **not** completion of that step. Access must not be obtained by bypassing source restrictions or pretending the current website is the historical record.

Do not give a blind reviewer the editor-facing source packet at research/topic_v2_crossdesk_hadr/packet.json or a post-adjudication comparison. Tell reviewers transparently that the selection and excerpts were model-assisted. Reading the displayed v2 definitions is necessary for review and does not imply endorsement of assistant-suggested categories.

## Independent reviewer returns

Have each qualified human edit **only their assigned records' decision fields** in their unsigned JSON. Every completed record must include a genuine human name, a self-attested independent original-language source reading, an accurate source-language description, UTC timestamp and source-grounded rationale. A full archived source must be read to classify or abstain. If inaccessible, mark unassessable and explain why. In particular P36 has an empty body; the system forbids classifying it.

The editor may validate a partial returned packet:

    python3 scripts/topic_v2_hadr_language_handoff.py validate --language en --decisions /tmp/hadr-decisions-en.json

To require all five assigned records to have completed independent judgments:

    python3 scripts/topic_v2_hadr_language_handoff.py validate --language en --decisions /tmp/hadr-decisions-en.json --require-complete

Validation checks source IDs, packet/ledger/taxonomy hashes, canonical record fields, full-source self-attestation, reviewer attribution, timestamp, v2 topic slugs and decision consistency using the original #164 validator. It **cannot authenticate a reviewer's identity or prove they read the source**.

## Assemble six returned packets, then close the independent-review gate

After obtaining **all six independently completed language packets**, assemble them into exactly the canonical full eleven-record shape:

    python3 scripts/topic_v2_hadr_language_handoff.py assemble --decisions /tmp/hadr-decisions-en.json /tmp/hadr-decisions-zh.json /tmp/hadr-decisions-ja.json /tmp/hadr-decisions-id.json /tmp/hadr-decisions-vi.json /tmp/hadr-decisions-ko.json --require-complete > /tmp/hadr-combined.json

The assembler rejects duplicate or absent languages; unknown, altered or duplicate source IDs; modified source digests or taxonomy pins; false approvals; and any pending decision when completion is required. It preserves the **canonical order** of the #164 review contract. No model comparison is performed and no label approvals are created.

The owner must separately complete the original offline source replay and source-access audit:

    python3 scripts/topic_v2_hadr_review.py provenance --verify-sources

Then independently validate the combined document:

    python3 scripts/topic_v2_hadr_review.py validate --decisions /tmp/hadr-combined.json --require-complete

**Only after independent source-access and reviewer-integrity checks** should the editor run the separate comparison command. The comparison reveals provisional model roles **only after** all eleven signed decisions; disagreement resolution and any later topic application require explicit human editorial authorization. Human review can stop at this stage without ever classifying a production record.

    python3 scripts/topic_v2_hadr_review.py compare --decisions /tmp/hadr-combined.json

This tool never creates an email, sends drafts to Dylan or other editors, pre-fills a reviewer name, guesses which languages someone reads, opens source websites, certifies human approval, or writes production labels. It is an **independent reviewer operations handoff** rather than an editorial decision system.

## Offline testing

    python3 -m unittest tests.test_topic_v2_hadr_language_handoff -v

Tests use clearly labeled **synthetic test reviewers**, not actual completed reviews. Source materials, taxonomy, #164 scripts and original evidence packet are unchanged. Run exact-head PR CI before merge and never treat a green machine test as human approval.
