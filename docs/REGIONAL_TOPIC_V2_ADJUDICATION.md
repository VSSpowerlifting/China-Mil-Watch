# Regional topic v2 — editorial adjudication and ratified scope

**Decision scope:** An evidence-based assistant editorial adjudication, performed under the owner's instruction to finalize v2 vocabulary definitions. These are authoritative **v2 scope-design decisions** for implementation, **not** a human adjudicator's acceptance of individual record assignments. The pilot's original and second-pass model proposals remain untouched; all 15 sampled candidate records remain `review_state: pending_human`, and no `record_topics` rows are written.

## Evidence boundary

The 15 candidate records and exact evidence offsets are in `research/topic_v2_evidence/*.json` (from the scoped evidence branch/PR #135). All are pinned to production commit `e649b5d11b51aa3334fddfb4952d132b6780eb30` and its 4,930-record, 2026-10-06 index. They originate from the **China Desk** even when describing other countries. A matching pinned original text demonstrates what the archive recorded, not the factual accuracy of official claims or source independence. PR #128 adds cross-desk HADR subject examples, but its original decisions are not rewritten or laundered into human labels.

**Ruling convention:** `include` = defensible positive control under v2 scope; `exclude` = insufficient subject materiality for the target topic; `unassessable` = inadequate source body. All are **model editorial rulings requiring human review before persistent record-level assignment**.

| Subject | Preserved record | Ruling | Rationale |
|---|---|---|---|
| space_security | [#787](http://www.81.cn/fyr/16464050.html) | **include** | Distinct, substantive reported military-reconnaissance satellite policy; Chinese statement, not verification of Japan's action. |
| space_security | [#2293](http://www.81.cn/yw_208727/16472683.html) | **include** | Developed reported military-space organization and operational policy; separate Chinese statement, not independent Japanese evidence. |
| space_security | [#4588](http://www.81.cn/yw_208727/16488978.html) | **exclude** | Satellite launch and technology trial have no established national-security or military space mission. |
| space_security | [#3005](http://www.81.cn/yw_208727/16478187.html) | **exclude** | Military Space Force affiliation and equipment maintenance do not identify the space-security function of the equipment. |
| east_china_sea | [#4047](http://www.81.cn/yw_208727/16484929.html) | **include** | Disputed-island coast-guard rights patrol makes East China Sea maritime sovereignty/security substantive; retain issuer attribution. |
| east_china_sea | [#702](http://www.81.cn/yw_208727/16463547.html) | **include** | Separate date and reported enforcement encounter near disputed islands is a substantive flashpoint event; legality not independently verified. |
| east_china_sea | [#4245](http://www.mod.gov.cn/gfbw/wzll/hj/16486972.html) | **exclude** | Only a naval training location; no East China Sea dispute or distinct regional-security nexus in the body. |
| east_china_sea | [#1857](https://www.globaltimes.cn/page/202606/1364568.shtml) | **unassessable** | Original captured body missing; headline location cannot support a topic ruling. |
| export_controls_sanctions | [#1667](http://eng.chinamil.com.cn/2025xb/H_251454/L_251456/16468736.html) | **include** | Concrete named entities, dual-use control list, prohibited exports and effective-date description. |
| export_controls_sanctions | [#1296](http://www.81.cn/fyr/16466779.html) | **include** | Described entry restrictions and bans on transactions/cooperation are concrete sanctions measures. |
| export_controls_sanctions | [#3506](http://eng.chinamil.com.cn/2025xb/V_251452/16481282.html) | **exclude** | Developed diplomatic criticism of non-specific sanctions threats, but not a concrete proposed/issued restriction mechanism in this preserved body. |
| military_hadr | [#3927](http://www.81.cn/yw_208727/16483879.html) | **include** | Specific reported civilian evacuation, debris clearance and relief operations by armed forces and associated units. |
| military_hadr | [#1903](http://www.81.cn/yw_208727/16470480.html) | **include** | Specific earthquake-response mobilization, damage survey, road opening and civilian support. |
| military_hadr | [#184](http://www.81.cn/wj_208567/16460109.html) | **include** | Dedicated disaster-response preparedness and rescue training; not actual disaster operations. |
| military_hadr | [#856](http://www.81.cn/yw_208727/16464447.html) | **exclude** | Guidance about protecting troop health while responding is not developed civilian humanitarian support. |

**Summary:** 9 include / 5 exclude / 1 unassessable. Two originally borderline cases (#3005 and #3506) now receive explicit exclusion decisions. One missing-text record (#1857) remains unassessable; no title-only classification.

## Ratified v2 topic model

**Add one topic**: `military_hadr`, **Military Humanitarian Assistance & Disaster Response** (operations group). Inclusion requires a substantive military contribution to civilian humanitarian/disaster response, directly tasked response logistics/spending, or a dedicated HADR training exercise. Exclude routine civilian health, generic troop welfare, disaster imagery, affiliation alone, or ordinary non-HADR medicine. Exercises, diplomacy, maritime security, procurement and HADR may co-occur only if independently evidenced. Japan pilot P38's specified disaster-support operating costs are **in HADR scope** even without proof of a finished response, but do not automatically count as procurement or sustainment decisions.

Retain **all 19 v1 slugs** with the same identifiers; v1 is immutable. The one deliberate v2 display clarification is `critical_minerals_supply_chains`, displayed as **Strategic Materials & Supply-Chain Resilience**. That existing slug can encompass expressly strategic/defense-linked supply dependencies and industrial resilience without claiming critical minerals where none are documented. No split into two topics now: the sample did not test a separate minerals-only coverage distribution.

Additional controlled **v2 scope clarifications**:
- **Topic materiality:** a developed passage, mechanism, named action, or specific exercise must make each attached topic substantively relevant; an unelaborated diplomatic agenda list cannot justify multiple topics. There is no arbitrary topic-count ceiling where evidence supports each.
- **Flashpoint geography:** the East China Sea / South China Sea labels require a substantive dispute/security subject; geography-only exercises do not automatically qualify.
- **Space:** require military/security nexus; civilian launches and astronaut greetings without it stay unclassified for `space_security`.
- **Cyber:** military networks, cyber defense, electronic warfare and information operations may qualify, but none imply a cyberattack unless the evidence describes one. Routine press statements, generic digitization and agenda keywords do not qualify.
- **Export controls and sanctions:** qualify named restrictions, designation/list decisions and materially described **concrete** proposed controls; generic secondary-sanction threats or general foreign-policy commentary are insufficient.
- **Police/public-security technology:** a concrete security-relevant technical mechanism is necessary; ordinary police diplomacy is not military diplomacy. Police institutional affiliation alone is insufficient for defense-industry topics.
- **Temporary port access:** substantive access arrangements may qualify force posture even if short-lived; an event venue at a base does not.
- **Historical/out-of-region source subjects:** classify the material subject, retain actual desk provenance and event chronology, and do not imply contemporary/Indo-Pacific operations from source ownership.
- **Composite captures:** source extraction and boundaries must be reviewed before an article's separate segments are treated as one coherent topical subject.

These rulings clarify **what v2 means**. They do **not** mechanically reassign the PR #128 record proposals, nor imply that all remaining 19 owner questions have received independent original-language human review.

## Version policy / engineering boundary

The active compatibility default remains `load_taxonomy()` → v1, including the original v1 file and its 19 topics. Explicit `load_taxonomy(version=2)` selects the 20-topic v2 file. `TopicAssignment(taxonomy_version=2)` must validate against v2 even if no taxonomy object is passed. Reads via `topics_for_record(..., taxonomy_version=2)` return only v2 rows; v1 reads stay isolated. Unsupported/bool versions and mismatched file/declared versions fail closed. `record_topics` already keys assignments by version; no change to SQLite DDL or migration number is required **for the storage-neutral opt-in contract**, but **production adoption still requires a separate numbered migration** and explicit owner authorization.

This phase's code/tests use only ephemeral SQLite fixture stores. No production/shadow database is opened, no classifier is added, no assignment written, no collection activated, and no published archive output modified. This is a **vocabulary/contract implementation**, not a decision to deploy or backfill.

## Next gate

Before any official regional record topics are applied, obtain a human owner/second-reader review of source-language excerpts, original full source text and topic materiality. Retain source ownership and immutable v1 assignments if they ever exist. Then authorize the production schema and small, audited attachment pilot **separately**. The new candidate taxonomy can be merged as a versioned library without triggering record classification.
