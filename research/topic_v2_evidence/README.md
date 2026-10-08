# Regional Topic v2 — targeted archived evidence controls

**Status:** source-backed **provisional** selection; not an adjudicated gold set, new taxonomy, approved topic assignments, or a production import list. The target is the owner-review questions in [the v2 proposal](../../docs/REGIONAL_TOPIC_V2_PROPOSAL_2026-10-07.md) and the [60-record pilot PR #128](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/128).

## Frozen source and reproducibility

- Repository: `VSSpowerlifting/China-Mil-Watch`.
- Exact archive/corpus-index commit: `e649b5d11b51aa3334fddfb4952d132b6780eb30` (an already-preserved production snapshot, not a new collection).
- `output/corpus-index.json` blob: `38b256ec7884d0b9b69b3b4dcd31ac3dace72ff8`; its declared snapshot is **2026-10-06, 4,930 records**.
- Every ledger row pins the record's existing generated HTML blob, stable `(desk_id, source_slug, canonical_url)`, source-stated date and original title.
- Short evidence quotes come only from the *Stored source text* field of the pinned `output/record/<id>.html` Git blob. Their offsets refer to the normalized HTML-rendered original text: strip tags, decode named/numeric HTML entities and collapse whitespace. They do **not** claim offsets in `pla_watch.db.text_original`.
- For each record, the source's claims and territorial/legal characterizations remain **attributed**. A successful replay establishes preservation and what was published, not the truth of a claim or an editor-approved classification. Machine-translated English titles are context only; the preserved original title/text rules.
- `scripts/verify_topic_v2_evidence.py` reads pinned Git objects only and fails closed on missing objects, identity/source/date drift, or excerpt mismatch. It neither opens SQLite nor mutates data. Run from a checkout that has those historical objects:

```sh
python3 scripts/verify_topic_v2_evidence.py
```

The script is a validation mechanism; it does not independently adjudicate topic meaning. A shallow or partial clone lacking the pinned objects must fail rather than silently substitute newer source versions.

## New sample: 15 preserved production records

| Subject | Positive candidate IDs | Negative candidate IDs | Borderline or unassessable IDs | Question tested |
|---|---|---|---|---|
| `space_security` | **787, 2293** | **4588** | **3005** borderline | Is an explicit military-space mission or policy needed? |
| `east_china_sea` | **4047, 702** | **4245** | **1857** unassessable | Does a dispute-related security act matter, rather than mere geographic presence? |
| `export_controls_sanctions` | **1667, 1296** | Original pilot **P08** is the cross-reference negative | **3506** borderline | Are enacted/listed controls distinct from rhetoric about threatened measures? |
| Proposed `military_hadr` | **3927, 1903, 184** | **856** | Cross-desk pilot **P38** tests support expenditure | Does civilian-relief response/preparedness stand as its own military mission? |

The exact existing production URLs and text are in the four JSON files. The original v1 pilot P08 is an **external cross-reference**, not one of these 15 new rows; all original pilot judgments remain provisional. Newly sampled statuses: **9 positive, 3 negative, 2 borderline, 1 unassessable**. Positive means an evidence-supported *candidate* meeting the proposed scope, not a persisted, accepted label.

### Space Security: two related official positions, not two independent confirmations

- **787 (2026-05-28):** Chinese defense spokesperson discusses reported Japanese low-orbit military reconnaissance-satellite operations, exercises, and space weapons policy.
- **2293 (2026-07-09):** A later Chinese defense spokesperson statement discusses Japan's reported legal/organizational changes to military space operations.
- **4588:** Civil/state satellite launch and electromagnetic detection experimentation. Neither a military publisher nor ambiguous dual-use technology establishes the military/security nexus alone.
- **3005:** The story clearly identifies the Military Space Force, but the named equipment's specific space mission is withheld; a personnel profile alone should not receive a capability label by implication.

Both positives are **China Desk / Chinese MND statements about Japan**. They involve distinct reported measures, but cannot stand in for a Japan Desk record or independent verification. Human review should retain that limitation.

### East China Sea: two distinct described events

- **4047 (2026-09-10):** Chinese Coast Guard rights patrol in disputed Diaoyu/Senkaku territorial waters, an explicitly sovereignty-related operation.
- **702 (2026-05-26):** Chinese Coast Guard report of warning and expelling a Japanese vessel at the disputed islands; issuer's legal account is not independently adjudicated.
- **4245 (pilot P12):** Named East China Sea operating area but solely amphibious ship-to-craft training, without developed flashpoint relevance.
- **1857:** Title describes a China-Russia strategic air patrol over several areas including the East China Sea, **but original source text is unavailable** in the pinned record. It contributes no positive or negative finding; do not infer content from title.

These first two are distinct dates and reported actions, but both come through Chinese sources and should not be treated as independent cross-party incident confirmation.

### Export Controls & Sanctions: mechanisms versus rhetoric

- **1667 (2026-06-22):** A preserved English report specifies China adding 10 named U.S. entities to its dual-use export-control list and explicitly prohibiting exports to them.
- **1296 (2026-06-11):** Chinese foreign-ministry announcement specifies transaction/cooperation restrictions and an entry ban concerning the Philippine defense minister and family.
- **3506:** Commentary on reported U.S. secondary-sanctions threats relating to Iran, without a new implemented measure documented in the stored text. **Borderline**: v1's broad scope might still include developed *policy debate about proposed restrictions*. Owner should decide rather than silently treating all sanctions rhetoric as a control.
- **P08** in PR #128: a cybersecurity advisory is not an export control or enacted sanction; it remains the clear negative contrast.

These examples show two concrete mechanisms in separate subject contexts. They **do not** measure topic prevalence or demonstrate an export-controls classifier's accuracy.

### Military HADR: separate mission, not a synonym for exercises

- **3927 (2026-09-06):** Military/armed-police/militia involvement in actual flood rescue, evacuation, debris and recovery support across Jiangxi and Fujian.
- **1903 (2026-06-29):** Military and militia earthquake response, reconnaissance, road clearance, and support to civilians in Sichuan.
- **184 (2026-05-12):** A military/armed-police earthquake/rescue rehearsal with engineering, search and evacuation. Proposed positive for **mission-specific preparation**, not an actual response event.
- **856:** Troop health-and-water safety advice set against flood-relief deployment. Incidental disaster backdrop and troop-welfare guidance do not make the civilian-relief mission the substantive subject.

For cross-desk scope, also read original PR #128 frozen **P16 China, P35 Singapore, P38 Japan, P51/P52 Philippines, P57 Indonesia**. These are six primary records across five desk ownerships but include correlated accounts of one event. They are not copied into this ledger, approved or applied. P38 is the key boundary: disaster-response allowances and vessel support expenditure may justify HADR even without a recorded finished mission, but not automatic `procurement_acquisition`.

## Owner adjudication checklist

1. **Military space nexus:** Keep a positive only with a substantively discussed military/security space mission, institution/policy, counterspace measure, or identifiable security-linked program. Attribution of alleged foreign activity must remain explicit. Decide whether an unidentified piece of equipment at a military-space unit is enough (recommend **no**).
2. **East China Sea flashpoint:** Require an identifiable substantive security/dispute connection, not just geographic placement. Separate reports of one incident are correlated, not independent confirmations.
3. **Export controls/sanctions:** Keep concrete designations, enforceable restrictions, licensing measures and specified controls. Decide whether developed discussion of threatened/proposed controls (3506) qualifies even before adoption; do not tag mere advisory or routine tax relief.
4. **HADR:** Accept direct military civilian-relief operations and dedicated rescue preparedness. Decide whether documented response support spending (P38) qualifies independent of completed relief activity (recommend **yes for HADR**, not automatic acquisition). Do not equate military public-health guidance with providing humanitarian services to civilians.
5. **Review protocol:** A human reader must check the original language, the whole archived body (not just the quote), explicit subject materiality, category overlap, and any missing or incomplete captures. Record reviewer/date and accept/reject/revise in a **new** review artifact. No original or proposed labels are thereby overwritten.
6. **Coverage limits:** All **15 new** records are from the production **China Desk**, although their contents concern other countries and international subjects. That is source ownership, not proof of 15 China-only events. Cross-desk HADR feasibility comes from PR #128, but three zero-coverage categories still need additional independent desk coverage when preserved non-China originals are available. Do not fabricate quota-filling shadow examples or activate collectors.

## Explicit exclusions / next gate

This phase does not change `taxonomy/regional_topics.v1.json`, the hardcoded v1 runtime API, the proposed v2 vocabulary, any existing pilot artifact, the production/isolated shadow SQLite stores, daily outputs, collector schedules, desk status, or public UI. It does not run a classifier, approve topics, merge a PR, or deploy. The evidence sample can be merged later as **provisional research only** after verification. The next real milestone is independent human adjudication and a version/compatibility decision; adding `military_hadr` to executable v2 is not yet authorized.
