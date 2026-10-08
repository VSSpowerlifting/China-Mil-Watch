# Regional Topic Taxonomy v1 — classification pilot findings

## Result and evidence

The 19-topic vocabulary can provisionally describe 45 of 60 selected records
across seven desks. Sixteen topics have proposed examples; fifteen records have
no proposed topic, including one empty-body infographic. Twenty-eight records
are multi-label, and thirty carry scope/ambiguity questions or limitations for
human review. These are **Codex proposals, not accepted labels**. Reliability
has not been established: there is no independent human gold set or agreement
measurement. No vocabulary change is made by this phase.

Canonical evidence: [`ledger.json`](../research/topic_pilot_v1/ledger.json).
Human review: [`LEDGER.md`](../research/topic_pilot_v1/LEDGER.md).
Sampling/replay/review procedure:
[`README.md`](../research/topic_pilot_v1/README.md).
All findings below cite stable pilot IDs with exact source excerpts in the ledger.

| Desk | Production | Shadow | Main limitation |
|---|---:|---:|---|
| China | 24 | 0 | Purposive recent sample, three outlets; local labels are contextual only |
| Singapore | 12 | 0 | One publisher; repeated vessel/exercise accounts; one empty capture |
| Japan | 0 | 5 | All available stored bodies, heavily concentrated in facility PDFs |
| Vietnam | 0 | 6 | All current stored ministry versions; narrow first batches |
| Philippines | 0 | 7 | AFP only; NSC pin has zero records |
| Indonesia | 0 | 3 | Small additional-desk sample |
| Korea | 0 | 3 | Small additional-desk sample |
| **Total** | **36** | **24** | Selection is not a corpus prevalence estimate |

## Distribution

Counts are proposed record-topic occurrences; topics overlap and reports can
cover the same incident. Zero means untested or withheld in this sample, never
absence from the wider corpus.

| Topic | Records | Topic | Records |
|---|---:|---|---:|
| military_exercises | 17 | force_posture_basing | 7 |
| maritime_security | 8 | gray_zone_coast_guard | 1 |
| defense_diplomacy | 7 | alliances_partnerships | 11 |
| procurement_acquisition | 2 | defense_industry | 3 |
| emerging_technology | 7 | nuclear_deterrence | 2 |
| cyber_information | 7 | space_security | 0 |
| taiwan_strait | 1 | south_china_sea | 3 |
| east_china_sea | 0 | economic_security | 5 |
| export_controls_sanctions | 0 | critical_minerals_supply_chains | 3 |
| doctrine_strategy | 2 | | |

## Decisions that need human adjudication

1. **Operational/security overlap.** P11 legitimately spans Taiwan, maritime
   activity and security-relevant coast-guard patrols, but routine enforcement
   language requires a materiality judgment. P51 has coast-guard participation
   in earthquake training and withholds the gray-zone topic. Participation or
   publisher affiliation should not substitute for subject evidence.
2. **Geography versus flashpoint.** P12 records naval training in the East China
   Sea but no substantive regional dispute; that geographic label is withheld.
   P11's waters east of Taiwan do not automatically imply East China Sea.
   Test a positive flashpoint example before judging that topic's usefulness.
3. **Defense engagement versus durable partnership.** P15 describes recurring
   military mechanisms; P29 introduces an overarching bilateral exercise
   framework; Japan's P37/P39/P40 cite facility access under the status-of-forces
   agreement. Those support partnership proposals. Ordinary country co-mention
   in an exercise report such as P02 does not. P26's joint committee framework
   and P56's ceremonial attache meeting need careful threshold review.
4. **Acquisition versus industry versus technology.** P27/P28 describe a concrete
   vessel program and production, while P19 is conversion training and receives
   no procurement topic. P10's historical wartime merchant-ship production is a
   difficult defense-industry edge case. P43's police security industry must not
   silently become defense industry; only its security-linked AI receives a
   provisional technology label.
5. **Cyber breadth and agenda materiality.** P04's military information networks,
   P07's defensive cyber hygiene and P18's electronic warfare fit different
   parts of the broad cyber/information definition. P31 lists several cooperation
   areas in one sentence; P33 discusses multiple future-force themes. Human
   reviewers must adjudicate materiality and omitted labels rather than equate
   any keyword mention with a topic.
6. **Economic security requires an explicit nexus.** Vietnam P45/P46 explicitly
   invoke energy security, and P47 explicitly links supporting industry with
   economic security and strategic autonomy. Those are positive examples, unlike
   P55's forest restitution ceremony. P47's industrial resilience proposal and
   P31/P33's defense supply-chain proposals expose the breadth of a topic whose
   name also includes critical minerals. No sampled proposal establishes mineral
   content. P08 concerns an attributed cybersecurity advisory; it is not evidence
   of an imposed sanction or export restriction.
7. **Desk-local labels do not decide regional topics.** P03 keeps its China-local
   `nuclear` label as recorded but withholds `nuclear_deterrence`: Rocket Force
   simulated-launch training does not identify nuclear capability. P01's local
   `coast_guard` does not change its text's identification of PLA forces.
   P19's local `modernization` does not establish a procurement action. The
   existing categories and their meaning remain untouched.
8. **Coverage gaps versus scope exclusions.** Military disaster response recurs
   across China P16, Singapore P35, Japan P38, Philippines P51/P52 and Indonesia
   P57. Training/partnership labels partially cover it; P38 remains unclassified.
   Vietnam P44's police cooperation has no straightforward defense-diplomacy fit.
   Korea P58 has a substantive missile/peninsula-security subject with no
   geographic flashpoint topic and no established nuclear content. These are
   evidence-backed candidates for scope review, not automatic additions.

Unclassified IDs: P20, P21, P22, P23, P24, P32, P34, P36, P38, P44, P48,
P50, P54, P55 and P60. Their reasons distinguish missing evidence (P36),
plausible scope gaps (P38/P44), and subject exclusions such as political work,
personnel discipline, remembrance and civilian social activity. P22/P23 concern
civil space activity without an established security nexus: they cannot validate
`space_security` by title alone. Personnel/ceremonial material across several
desks shows why v1 should permit zero topics, rather than importing China's
`personnel`, `internal_security` or `political_work` categories.

## Recommendation

Keep v1 unchanged pending independent human adjudication. First review the
thirty flagged records, then check the remaining records for missed labels and
false positives. Establish an accepted gold set and measure per-topic agreement,
precision of proposals and abstention decisions; this single proposer sample
cannot supply those measurements.

The strongest candidate for a later vocabulary proposal is a distinct military
humanitarian-assistance/disaster-response topic, supported by multiple desks.
Review whether police/security cooperation belongs in a separate topic or is an
intentional scope exclusion. Review Korean Peninsula coverage with additional
records. Clarify cyber/info scope, partnership thresholds, temporary port access,
and strategic supply-chain versus minerals use before splitting or renaming any
stable identifiers. There is insufficient evidence here to recommend adding a
blanket industrial-policy topic or deleting the three zero-coverage topics.

A follow-on review-only sample should target positive space-security,
export-control/sanctions and East China Sea flashpoint examples **from preserved
available evidence**, plus more than one Taiwan and gray-zone example. Japan's
access limitations and narrow Vietnam samples remain constraints. No collector
activation or automated classifier is implied. Production migration, attachment
writes and public topic UI remain separately authorized phases.

## Verification and preservation

The all-desk source replay verifies all 60 rows against eight exact Git database
blobs (one production and seven shadow stores), including Vietnam's versioned
body joins. Excerpts, source metadata, body hashes, stable identity, and production
local categories match their pins. Inputs are temporary immutable copies; no
production/shadow database is opened for mutation or receives topic tables/rows.
Tests cover valid/unknown/duplicate topics, unsupported or tampered evidence,
identity/layer errors, provisional-state enforcement, deterministic reporting,
source parity, and byte preservation. The report is generated from the canonical
ledger rather than separately authored classification.

Local verification: 114 focused pilot/taxonomy/manifest/migration tests passed;
all-desk replay passed 60/60. A further 349 shadow/promotion regression tests passed as a complete run. The
existing output validator passed with the same 10 governed warnings. Negative
fixture diagnostics in that regression log are expected test evidence, not suite
failures. Machine-readable receipts are in
`research/topic_pilot_v1/verification.json`. The protected production database/output snapshot
has 7,457 files; compare its bytes and file list before and after verification.
No database, generated public output, vocabulary, desk categories, collector,
workflow or UI changes are part of this PR.
