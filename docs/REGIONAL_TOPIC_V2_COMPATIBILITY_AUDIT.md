# Regional Topic v2 — exact-definition compatibility audit

**Status:** read-only analysis, pending v2 merge and editorial review. This phase never authorizes migration, bulk classification, human approval or publication.

Matching taxonomy slugs do not mean old record assignments were approved against new scope. In v2, 11 existing topic definitions have revised scope guidance, eight are textually identical, and one entirely new topic is added.

## Reproduce the audit

From a checkout containing the pending versioned v2 vocabulary:

    python3 scripts/audit_topic_v2_compatibility.py
    python3 scripts/audit_topic_v2_compatibility.py --format json
    python3 -m unittest tests.test_topic_v2_compatibility_audit -v

The CLI reads only two versioned local JSON vocabularies and prints to stdout. It never opens SQLite, reads production/shadow records, downloads files, invokes a model, assigns labels, or alters generated output. Machine output contains all old and new definitions and exact modified fields.

| Boundary | Expected outcome |
|---|---|
| V1 existing slugs | All 19 retained |
| New v2 slug | military_hadr only, in the operations group |
| Removed/renamed slugs | Zero |
| Modified legacy definitions | 11 |
| Identical legacy definitions | Eight |
| Changed group definitions | Zero |
| Automatically promoted record assignments | Zero |
| Human/editorial approval implied | None |

Both frozen files are pinned by their exact Git blob hashes: v1 = a068839cb0bd9227b3edcc92991e21865119c23a; v2 = c3bd2e51661055ce61fd439c582ab5d44604ad0a. Even a changed space or an altered phrase in an already-modified topic's scope will force an explicit updated review of the candidate, not silent compatibility.

## What actually changed?

| Existing topic slug | v2 scope distinction | Changed fields |
|---|---|---|
| force_posture_basing | Operational port access may qualify; venue mentions do not | scope_note |
| defense_diplomacy | Military/defense nexus; police ceremonies are not automatically included | scope_note |
| alliances_partnerships | Actual sustained relationship or agreement; bare agenda lists do not establish partnerships | scope_note |
| procurement_acquisition | Specific acquisition, contracted purchase or sustainment decisions; relief expenditure is not automatically procurement | scope_note |
| emerging_technology | Developed military/security-technology content; civilian AI affiliation alone is insufficient | scope_note |
| cyber_information | Specific security-relevant cyber/information subject; do not infer attacks from networks or crime mentions | scope_note |
| space_security | Developed military/security-space matter, not generic civil launches or personnel association | scope_note |
| east_china_sea | Substantive East China Sea security/dispute issue; geographic location is insufficient | scope_note |
| export_controls_sanctions | Concrete controls or formally proposed restrictions, not sanction rhetoric or mere advisory | scope_note |
| critical_minerals_supply_chains | Security-linked supply resilience can be broader than minerals; materials must not be invented | display_name, description, scope_note |
| doctrine_strategy | Developed strategic concept/force-employment framework; slogans alone insufficient | scope_note |

Eight existing definitions are unchanged: military_exercises, maritime_security, gray_zone_coast_guard, defense_industry, nuclear_deterrence, taiwan_strait, south_china_sea, and economic_security. No editor has authorized copying v1 record-level judgments even for these.

The new military_hadr topic has no v1 assignment equivalent; separate positive/negative controls and source-language review are necessary. Related draft work includes #133's pending owner decisions, #142's independent human-review gate and #153's cross-desk HADR evidence.

## Editorial next gate

1. Verify precise old and new versions and the original complete source text.
2. Check a record against any revised materiality/nexus boundaries before proposing a v2 topic.
3. Require independent human record-level review before granting v2-specific approval. No automatic copy of v1 assignments, even for unchanged slugs.
4. Only with separate authorized schema/attachment action may approved v2 records be persisted. Keep all China Desk local categories unchanged.
5. If the v2 taxonomy wording changes, update the scope adjudication and pinned compatibility contract first.

This audit is a **metadata compatibility report**, not evidence of independent factual corroboration, full taxonomy correctness or review completion. Its tests are drafted and have not yet passed full exact-head CI.
