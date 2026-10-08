# Japan \`space_security\` — source-admission research (2026-10-08)

**Scope:** editor-facing discovery and archive-coverage preparation only. The six linked Japanese official documents **are not** verified IPR archive captures. No human has approved their proposed control roles, no original full bodies or immutable hashes have been admitted, and no automated collector or topic assignment is authorized.

This tranche addresses issue #168 and the China-heavy \`space_security\` v2 controls from #135. The 60-record v1 pilot includes only five Japan-origin records, all concerned with basing/access or disaster-support matters; it is **not** a census of the Japan shadow database. Lack of a pilot hit cannot prove a source is missing from the overall archive.

## Official-source discovery queue (not human decisions)

| ID | Issuer / document | Preliminary editor role | Context and boundary question |
|---|---|---|---|
| JSP01 | [Japan MOD, 2026 Defense White Paper, cross-domain capabilities](https://www.mod.go.jp/j/press/wp/wp2026/html/n310204000.html) | Potential positive | Substantive space-domain awareness, satellite protection, surveillance, and planned programs. Distinguish capabilities and intentions from launches already completed. |
| JSP02 | [Japan MOD, minister's press conference, 2026-03-06](https://www.mod.go.jp/j/press/kisha/2026/0306a.html) | Potential positive | The announced March 23 formation of an expanded Space Operations Wing; an announcement is not the completed formation. |
| JSP03 | [Japan Air Self-Defense Force Space Operations Wing, 2026-03-23](https://www.mod.go.jp/asdf/ssa/activities/report01/) | Potential positive | Original service statement says the wing was formed on March 23; it is the **same organizational event** discussed in JSP02, not another event or independent confirmation outside government. |
| JSP04 | [Japan MOFA, Diplomatic Bluebook 2026, Japan–U.S. Security Arrangements](https://www.mofa.go.jp/mofaj/gaiko/bluebook/2026/html/chapter3_01_02.html) | Potential positive | Security-oriented space-domain awareness information sharing, hosted payloads and HGV-tracking satellite cooperation. Some agreements are earlier than 2026: source year is not event year. |
| JSP05 | [JAXA, 2026-06-12 H3 Flight 6 launch outcome](https://www.jaxa.jp/press/2026/06/20260612-1_j.html) | Potential hard negative | Civil launch/test and small spacecraft deployments. Confirm the full payload descriptions before concluding that no security mission is substantively present. |
| JSP06 | [JAXA, 2026-08-20 H3 Flight 10/MMX launch plan](https://www.jaxa.jp/press/2026/08/20260820-1_j.html) | Potential hard negative | A planetary research mission; **October 20, 2026 is a future scheduled launch**, not a completed event at the research cutoff. |

There are **six documents, four potential positives and two potential negatives**, across **five event/policy contexts**, not six independent incidents. JSP02/JSP03 refer to the March 23 reorganization. JSP01 and JSP04 are 2026 annual documents, so their exact page-publication dates are **not invented**; original issuer year only is recorded until better primary-source metadata is captured.

JASDF is an organization within Japan MOD and not independent external corroboration. JAXA is a separate institution, but different issuers do not automatically make the substantive events independent. The candidate selection is assistant-curated and topic-targeted, not a random or human-blinded sample.

## Known evidence and temporal complications

- Japan MOD's 2026 white-paper chapter describes plans for an SDA satellite launch in fiscal 2026. A separate JASDF history page has schedule graphics referring to a planned launch in fiscal 2027. **Do not reconcile this into a completed launch or claim the sources agree about timing**; identify page revision/plan dates if researching this divergence.
- A flight test or civilian space mission is not automatically \`space_security\`. Conversely, the JAXA agency label alone cannot establish absence of defense-related payloads; review every substantive mission described in the full original language.
- MOD's white paper, MOD press conference, and JASDF report represent closely related official Japanese institutional voices. This improves non-China **issuer-side evidence** but not necessarily independent verification of every claimed capability.
- For JSP06, the 2026-08-20 publication date is in the past; the planned mission date is in the future. Do not confuse the two.
- Source claims on military or alliance arrangements are statements from the issuing authorities. No external investigation or independent claim corroboration has occurred in this phase.

## Archive admission gate

First, perform a repository-wide **read-only inventory** of production and every relevant Japan shadow collection, by exact canonical URL and title. Check whether these six original-language full bodies are already captured. If an existing record is found, save its stable desk/source identity, source-stated date, archive capture date, text/PDF, immutable commit/blob and body checksum in a **new separately reviewed admission proposal**; do not insert bogus archive keys into this discovery ledger.

If not present, document source/collector ownership and a narrowly scoped candidate registration on the Japan Desk. New official issuers (especially MOFA and JAXA) may need a separately approved addition to the source registry. Do **not** silently include JAXA's general civilian feed as a full production collector merely to obtain two negative controls. A bounded one-off source capture, with independent editorial acceptance, may be more proportionate.

Only after full-source preservation can an additional provenance verifier pin quote offsets, source hashes and immutable Git objects. Human source-language assessment then belongs in a *separate* blind review workflow; **never distribute** this role-labeled editor-facing packet to a reviewer as a blind packet. No comparison/gold-set/accuracy calculations are authorized by this proposal.

## Read-only structural validator

From repository root:

    python3 scripts/validate_topic_v2_japan_space.py
    python3 -m unittest tests.test_topic_v2_japan_space_admission -v

The validator verifies the six whitelisted official URL identities, their proposed roles and event groups, Japan desk target, source-date precision, v2 topic identity, the absence of archive claims or approvals and five distinct context groups. It performs **no network requests**, no Git historical-source replay, no database access and no file mutation. Passing it verifies **proposal structure only**, not whether an official webpage has been archived, whether each fact is correct, or whether a human would apply \`space_security\`.

**Phase stop:** a reviewable discovery packet, validator and tests. Do not proceed to collector registration, body capture, classification, human approval, backfill, UI or deployment without a separate explicit phase.
