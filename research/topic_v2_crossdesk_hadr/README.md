# Regional Topic v2 — cross-desk military HADR review controls

**Status:** editor-facing, **provisional**, and **not human-adjudicated**. This packet does not modify v1/v2 vocabularies, approve labels, attach topics to any record, or authorize a backfill, production schema, collection or deployment change.

The 15 newly sampled records in PR #135 were all China Desk records. The merged seven-desk pilot (#128) already contains useful **other-desk HADR and negative-control candidates**. This packet reuses only that frozen evidence, without claiming independently recollected or freshly verified official records.

## Actual breadth, without inflated independence claims

| Origin desk | Pilot source IDs | Why sampled | Provisional role |
|---|---|---|---|
| China | P16, P21 | Chinese–Lao humanitarian medical rescue exercise and routine holiday armed-police patrol | Positive candidate / negative |
| Singapore | P35, P36 | Combined ADMM-Plus disaster-response exercise; related infographic with **zero archived body text** | Positive candidate / **unassessable** |
| Japan | P38 | Described Kumamoto earthquake-recovery military support allowances, civilian-vessel operating costs and bathing services | Positive candidate, expenditure/mission boundary |
| Philippines | P51, P52, P49 | AFP/PNP/PCG earthquake-response interoperability exercise, plus a non-HADR naval-readiness item | **Two records about the same Sanlakas exercise**, and a negative |
| Indonesia | P57 | Indonesian defense ministry account of Japanese military wildfire assistance (published in a medal context) | Positive candidate; the award ceremony itself is not the assistance |
| Vietnam | P44 | Vietnam–Myanmar policing and crime-control cooperation, **not** disaster response | Negative only |
| Korea | P58 | Defense response to North Korean ballistic missile launch, **not** civilian disaster relief | Negative only |

The **11 source records cover seven desks**, but only **five desks have positive HADR candidates**. There are **six positive candidate records**, **four negative controls**, and **one unassessable body**. Distinct event/context keys total **nine**, not eleven. P51/P52 describe the same Philippine exercise; P35/P36 concern the same multinational exercise, although the latter has no captured original body. Multiple source mentions are not independent corroboration of a single event.

All selected excerpts were originally chosen by a model, not an independent human reviewer. The additional role choices in this packet were also editor-assistant proposed. This is a **selection for review**, not a certification that each positive candidate qualifies under v2.

## Provenance rules

Each row in [`packet.json`](packet.json) pins the exact original pilot ID, origin desk/source, issuer URL, source-stated date, title in its original language, source blob/commit/ref and original stored-body SHA-256. Excerpts are copied exactly from the merged pilot, including any truncated wording. No replacement English translation is invented. The origin and row locators allow a qualified reviewer to find and inspect the **entire** frozen body in the corresponding production or shadow snapshot.

Check the packet against the saved pilot:

```sh
python3 scripts/validate_topic_v2_crossdesk_hadr.py
python3 -m unittest tests.test_topic_v2_crossdesk_hadr -v
```

The offline validator replays every identity, source/date, original excerpt, archived-origin pointer, case role, duplicate-event family and pending approval state against the **unchanged pilot ledger**, verifying that ledger's exact Git blob SHA. It does **not** independently open all historical production/shadow database Git blobs or verify factual statements by the governments concerned. To upgrade from source-pinned candidate to accepted human label, the original full bodies and language must be independently inspected.

## Editorial review questions

- **P16:** Is it mission-specific humanitarian aid and medical rescue, rather than automatically treating all military medical training as HADR? Does the delivered public service supply the humanitarian nexus?
- **P35:** Are disaster-response operations described materially, or only listed as an exercise topic? Does the source distinguish cybersecurity support from the civilian relief mission?
- **P38:** Does a dedicated military disaster mission and explicit support expenditure qualify for HADR even without completed operations? It must not manufacture `procurement_acquisition` from budget lines.
- **P51/P52:** Which parts of the Philippine exercise concern civilian disaster response, and which are routine interagency readiness? Both mentions count as **one event**, and PCG participation does not imply gray-zone coercion.
- **P57:** Are wildfire assistance operations described substantively enough to support HADR, independently of diplomatic recognition and awards?
- **P21/P44/P49/P58:** Confirm these are genuine hard negatives under the new HADR scope, not automatically imported from their non-HADR v1 statuses.
- **P36:** No archived article body was present. Keep **unassessable** and do not substitute the P35 press release as evidence for infographic contents.

## Human and production boundaries

Do not give this editor-facing role-marked packet to a supposedly **blind** independent reviewer. The source-first reviewer tool in PR #142 provides separate unsigned blind packets and requires a real independent original-language reading before comparing proposals. Do not mark `review_state` as approved in this file, or publish model-assisted roles as gold labels.

PR #137 defines v2 and its twentieth topic `military_hadr`. This packet can be reviewed while its checks run. Neither its presence nor subsequent merge changes any `record_topics` database row. Production adoption, migration, and labeling remain separately authorized phases.

**Gap remaining:** Strong independent positive and negative **full-body** controls for `space_security`, `east_china_sea` and `export_controls_sanctions` from non-China desks still need to be collected and reviewed. None has been invented here.
