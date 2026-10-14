# Regional Topic Taxonomy v2 — evidence and decision proposal

**Status:** proposal only, 2026-10-07. **Not** the active taxonomy, a human-approved gold set, a migration, or an import queue.

**Active contract:** `taxonomy/regional_topics.v1.json` (19 topics) and `core/topics.py`.  
**Evidence base:** the 60-record, seven-desk provisional pilot in [PR #128](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/128), specifically its frozen ledger and second-pass assessment at head `124c5a1a0b515ed49be96978e8dcde07fa2b330c`. PR #128 is **not a prerequisite for reading this proposal**, but its merge and owner review are independent gates before any classification is accepted. The second pass was performed in the same model conversation, not by an independent human. Its disagreements are editorial hypotheses, not measured accuracy.

## Decision in brief

1. **Propose** one additive twentieth subject, military humanitarian assistance and disaster response (HADR), for an eventual v2 vocabulary. Five desk ownerships furnish examples of a substantive military mission that is not captured by training, diplomatic engagement or procurement alone.
2. **Retain** the 19 v1 topic identifiers pending evidence. In particular, zero proposed positives for `space_security`, `east_china_sea`, and `export_controls_sanctions` are sampling gaps, **not** grounds to remove them.
3. **Clarify first, split only with evidence:** `critical_minerals_supply_chains` currently admits broader strategic/defense supply resilience; `cyber_information` admits heterogeneous military information, cybersecurity and electronic-warfare subjects. Neither category should be silently narrowed, renamed or split on the basis of this pilot.
4. **Do not apply** the 60 model-proposed topic sets. No original pilot entry, reviewer flag or second-pass recommendation has been marked human-approved.

## A. Candidate v2 addition — military HADR

| Field | Candidate (not installed) |
|---|---|
| Slug | `military_hadr` |
| Display name | Military Humanitarian Assistance & Disaster Response |
| Group | `operations` |
| Proposed description | Substantive military participation in humanitarian assistance, disaster preparation, disaster-response missions, evacuation, civilian rescue, relief logistics, medical assistance, and civilian recovery support. |
| Proposed inclusion threshold | The armed forces' **HADR mission** is materially described through a specific response, formally tasked mission, dedicated training/preparedness exercise, or directly documented support and expenditure for such operations. Domestic and international missions may qualify. |
| Proposed exclusion threshold | A civilian health statement; routine garrison welfare or troop medicine; generic goodwill language; a military ship/aircraft mentioned without a relief mission; unrelated civilian police activities; or a disaster named only as background. |
| Versioning | A new slug only in a separately authorized v2 vocabulary. No retroactive v1 assignment, recoding of `military_exercises`, or historical tag conversion. |

**Evidence drawn from the frozen PR #128 pilot (pinned bodies, not web retellings):**

| Pilot records | Desk ownership | What they test | Qualification |
|---|---|---|---|
| P16 | China | Joint humanitarian medical assistance and disaster-response exercise with rescue technology and services | Positive HADR mission candidate; `military_exercises` may separately apply |
| P35 | Singapore | ADMM-Plus disaster-response exercise including medical and infrastructure support | Positive HADR mission candidate; exercise/partnership only if separately material |
| P38 | Japan | Disaster deployment allowances and recovery-support expenditure, including support vessel costs | Positive mission-support candidate; **do not** infer procurement, completed work, or equipment delivery |
| P51/P52 | Philippines | Two records describing an interagency earthquake-response exercise | Positive HADR candidate **once as an event**, even though both records remain independently archived |
| P57 | Indonesia | Japanese military disaster-assistance activity described in an Indonesian defense source | Positive HADR mission candidate; source ownership remains Indonesia, not Japan |

These are six primary source records spanning five desk ownerships and approximately five described mission contexts, **not** six independently corroborated events. The records establish what issuing institutions published, not the independent truth of any operational success claim. Source-language assessment and human adjudication are still required. Related secondary context includes Singapore P30, but it is not necessary to justify the core proposal.

**Decision examples for future reviewers:**

- Joint military earthquake-response rehearsal: `military_hadr` **and** `military_exercises` only if both missions are independently substantive.
- Military relief vessel delivering civilian bathing/water support: HADR may apply; maritime-security, deployment/basing and procurement do **not** follow merely from vessel involvement.
- Defense officials discussing long-standing disaster-response cooperation: HADR if the relief mission itself is developed, `defense_diplomacy` if actual official defense engagement is developed, and `alliances_partnerships` only if durable mechanisms are substantive. One meeting does not force all three.
- Routine civilian hospital announcement (P34), ordinary troop care, memorial/personal-welfare release (P60), or isolated infrastructure flood-proofing (P41): **not** HADR without a substantive military civilian-relief mission.

**Residual boundary requiring an owner decision:** Does an official military budget line specifically earmarked for disaster deployment/support qualify even absent an account of completed operations? Recommended **yes for HADR**, because funding and logistical support are part of preparedness; **no** automatic `procurement_acquisition` absent a concrete contract, acquisition, or sustainment decision. This is a proposed editorial threshold, not a v1 reassignment of P38.

## B. Three zero-coverage topics — targeted positive-control plan

The v1 pilot proposed **zero** examples for all three subjects below. This proposal contains **no verified new positive record** for them; it must not claim that a source merely found on the web is in IPR's preserved collection. The next evidence task is source read-only sampling against stored original bodies and pinned revisions.

| Existing v1 topic | Target positive control (must be found in preserved source text) | Existing negative / borderline control | Source adjudication question |
|---|---|---|---|
| `space_security` | Military satellite operations, counterspace measures, space-domain awareness, or a specific security-linked space policy or mission | P22/P23: civilian astronaut or civil-orbit activity without demonstrated security nexus | Must an explicit military/security nexus exist? **Proposed yes**; a generic launch/astronaut story does not qualify. |
| `east_china_sea` | A substantive East China Sea security incident, dispute, coercion, policy, or military posture **tied materially to that area** | P12: amphibious training located in the East China Sea, without developed dispute/security context | Require regional security relevance, not an incidental place name. |
| `export_controls_sanctions` | A specific export restriction, sanctions designation, investment/technology control, licensing measure, or enforcement action with meaningful description | P08: cybersecurity advisory, not an enacted export restriction; P46: fuel-tax relief, not sanctions | Was a real restriction/control itself substantively discussed? Threatened or merely named sanctions alone may be insufficient. |

**Bounded follow-on sample:** Search only permitted, already preserved production and isolated shadow source bodies; do not collect remotely or bypass official access controls. For each of the three topics, aim for **at least two clear positive records from distinct reporting contexts**, plus the negative control above, with one additional borderline case when available. Prefer multiple desks/source publishers; do not fill quotas with duplicate accounts of one incident. If preserved positives do not exist, record **insufficient evidence**, not a manufactured match. Keep source URLs, stable `(desk_id, source_slug, canonical_url)`, source-stated date, pinned store commit/blob, excerpt offsets, original language, and any translation/reviewer uncertainty. Desks do not move between production and shadow, and the US Indo-Pacific/DVIDS route stays excluded.

**Acceptance criterion:** Human-reviewable, source-replayed records with explicit include/exclude decisions and an independent reviewer where practicable. Do not compute inter-rater reliability from two model passes in the same context. Do not delete or shrink an existing topic because a small purposive sample fails to locate a positive.

## C. Scope guardrails before v2 vocabulary approval

The following resolve many of the 19 open owner questions from PR #128 as **proposals**, not retroactive edits to the frozen pilot:

| Rule | Proposed editorial threshold | Pilot pressure tests |
|---|---|---|
| Materiality | Require a developed passage or concrete subject-specific action/mechanism. A list of diplomatic agenda keywords is insufficient. Multiple topics have no fixed cap if each separately meets this test. | P31 versus P33 |
| Geography | A named sea is not automatically a regional flashpoint; identify substantive security/dispute content connected to it. | P12 |
| Temporary access | A substantively described port-access arrangement may count under `force_posture_basing`; a meeting held at a base cannot. No inference of permanent basing from a port call. | P25 versus P59 |
| Public-security technology | Police/civil security cooperation alone does not become `defense_diplomacy`, `defense_industry` or a military technology record. A specific security-technology mechanism may justify `cyber_information` / `emerging_technology` only under an explicitly approved security nexus. | P42/P43/P44 |
| Supply-chain materiality | Explicitly strategic, national-security-linked or defense-relevant industrial resilience may qualify for the existing `critical_minerals_supply_chains` slug even without minerals; an incidental mention of "supply chains" does not. **Do not assert minerals evidence when none exists.** | P31/P33/P45/P47 |
| Cyber breadth | Security-relevant military networks, cyber defense, information operations or electronic warfare may fit; routine public communications, crime mentions or generic digital modernization do not. No assumption of offensive hacking. | P04/P07/P18/P31/P42 |
| Historical/geographic reporting | A preserved record may discuss historical or out-of-region material. Classify the **subject** when substantive, retain actual desk ownership and source chronology, and never turn historical events into current developments. | P05/P10 |
| Composite captures | Do not treat an excerpt from a multi-part capture as a complete record; preserve source boundaries and refer extraction questions for separate review. | P19 |
| Military HADR versus acquisition | Financial/logistical response support may qualify for HADR while falling short of a specific acquisition or sustainment action. | P38 |

Two further questions deserve broader source samples rather than immediate v2 labels: security-policy cooperation among civilian police institutions (P44) and substantive Korean Peninsula missile/security records (P58). One or three records are inadequate to establish new regional topics. Civilian space and security-linked police technology are owner scope choices; this proposal recommends a demonstrated security nexus, but does not pretend the owner has already approved it.

## D. Versioning and deployment boundary

The database assignment key in `core/topics.py` contains `taxonomy_version`, which **could** support multiple versions without rewriting record identity. However, the **current runtime does not accept v2**:

- `DEFAULT_TAXONOMY_PATH` points to `regional_topics.v1.json`.
- `TAXONOMY_VERSION = 1`; `load_taxonomy()`, `TopicAssignment.validate()`, and `topics_for_record()` require that version.
- The production database has **no topic-store migration or approved regional assignments**. The storage-neutral v1 table is installed only on explicit opt-in.
- Merely placing a `regional_topics.v2.json` file in the repo would not activate v2 and must not be represented as doing so.

A subsequent, **separately authorized** implementation phase must preserve the v1 file and its meaning, introduce the reviewed v2 vocabulary as an explicitly versioned resource, teach loader/validator/read paths to select the requested version without altering previous provenance, and test old-v1 and new-v2 behavior against isolated temporary stores. A later **separate** production schema/migration/application decision remains required. Do not map old v1 proposals or China categories automatically. A change to the displayed name/scope of an existing slug needs explicit compatibility review, not silent retroactive reinterpretation.

## E. Gate checklist and stop conditions

**Before approving the v2 vocabulary:**
1. Resolve the HADR mission/support spending boundary; original-language human review of P16/P35/P38/P51/P52/P57 and deduplication of related events.
2. Obtain pinned positive/negative controls for the three zero-coverage topics; report missing evidence without inventing it.
3. Ratify the common materiality and geographic rules and adjudicate their impact on the 19 open pilot questions, without changing the frozen model ledgers.
4. Decide whether the critical-minerals/supply-chain label needs a versioned display clarification or a genuinely justified split; likewise decide the civilian-security and cyber inclusion boundary.
5. Prepare a compatibility plan for the hardcoded v1 loader and future storage use, then seek explicit authorization to write a canonical v2 JSON file.

**This proposal phase intentionally does not:** update the canonical taxonomy, write topic attachments, change any SQLite database or shadow state, initiate collectors, publish/classify records, add a classifier, migrate schemas, alter public UI/output, or merge/deploy a PR. PR #128 remains its own pending review/merge decision. The proposal may be merged as documentation without constituting approval of the candidate vocabulary or any label.

**Next coherent engineering session (only after owner review):** design a frozen, coverage-oriented positive-control sample from existing preserved records for the three untested topics, plus independent human HADR adjudication. Stop at a reviewable ledger, with no taxonomy activation.
