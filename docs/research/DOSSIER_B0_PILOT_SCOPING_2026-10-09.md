# Living Dossiers B0 — preserved-source pilot scope decision packet

**Prepared:** 2026-10-09 (US Eastern)  
**Status:** EDITOR REVIEW — conditional research go; no dossier created, approved or published  
**Parent:** [#318](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/318) · **Gate:** [#319](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/319)  
**Reproducible runner:** [Actions #38010490752](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38010490752) · \`scripts/audit_dossier_candidates.py\`  
**Exact runner commit:** \`3ab5dc889dffbcf51d6f8e3dba367493ed3b22c5\`  
**Tracked DB SHA-256:** \`443e5c477e515da4a0408b631dbaeec7638b98d85573a4bacd95c49fff941420\`

## Executive research decision

**Recommend, for owner selection as IPR's first draft-only living dossier:**  
*Republic of Singapore Navy International Exercise Participation — Selected Official Releases, July–October 2026.*

This narrowly describes the **Singapore Ministry of Defence's publicly preserved accounts**, rather than claiming to reconstruct every exercise, certify partners' assessments, or cover all of Singapore's naval diplomacy. A focused topic, short reporting window, seven archived releases, and multiple substantively distinct exercise activities support a credible editorial pilot. Unlike the existing *Maritime Cooperation 2026* Timeline (#158/#181), this dossier would compare **formats, counterpart relationships, missions and activities across several exercises**, not retell the chronological stages of one exercise.

**Conditional go only for editorial-scoping work**; do not proceed into the B1 public-content schema or change the frontend until Ben reviews and explicitly selects this pilot. Independent archive-body parity, publisher source-use, event/statement interpretation and rights decisions remain pending. No publication is authorized by this research recommendation.

## Evidence inventory: reproducible boundaries

GitHub Actions ran the read-only title/category discovery across the **5,020** tracked article rows (4,936 China; 84 Singapore) with publisher dates **2026-05-07 through 2026-10-09**. China and Singapore are the two live production desks; Japan is shadow, Vietnam is research, and the US Indo-Pacific reference desk is access-blocked. Their private research records are **not** production archive records and were excluded. No database or public output changed, and SQLite integrity and foreign-key checks passed.

These are **lexical discovery hits, not documents independently admitted as relevant and not event counts**:

| Candidate | Title/category leads | Desks represented | Decision |
| --- | ---: | --- | --- |
| South China Sea maritime reporting | 167 (46 in titles) | China only | Later: too broad and source-perspective constrained |
| China–Singapore military contact | 15 | China, Singapore | Hold: mostly the same September exercise, not demonstrated multi-event breadth |
| Philippines maritime security | 40 | China only | Hold: a China-official-record dossier might be viable, but not a balanced bilateral chronology |
| Regional exercise diplomacy | 99 | China, Singapore | Hold: mixes disparate institutions, countries and mission types; needs a sharper scope |
| Singapore naval exercise diplomacy | **7** title-matched releases | Singapore MINDEF only | **Pilot candidate** |
| Taiwan Strait military messaging | 153 (73 in titles) | China only | Later: category-origin false-positive risks and heavily concentrated issuing perspectives |

No completeness percentage is claimed. The category labels are model-originated and are used here only for preliminary discovery. A title hit does not establish that an entire source body supports a desired claim. Source titles and dates are preserved archive metadata, not automatically proof of events as described.

### Frozen seven-record source shortlist

All seven records are stored under the live Singapore Desk / \`sg_mindef_releases\`. The external official pages were separately opened and checked for title/date/source content during scoping; **the exact archived original-body bytes and source-use rights still require formal reconciliation**.

| Archived record | MINDEF published | Program or activity (issuer description) | Status in release | Original official source |
| --- | --- | --- | --- | --- |
| 4454 | 2026-07-30 | RSN participation in RIMPAC 2026; exercise stated as 25 Jun–1 Aug | Reported participation while exercise underway; not an end-of-exercise attestation | [MINDEF](https://www.mindef.gov.sg/news-and-events/latest-releases/30jul26-nr2/) |
| 4452 | 2026-08-29 | Singapan (Japan); held 27–28 Aug | Reported concluded | [MINDEF](https://www.mindef.gov.sg/news-and-events/latest-releases/29aug26-nr/) |
| 4466 | 2026-09-05 | Maritime Cooperation with PLA Navy; stated planned 5–9 Sep, including later sea phase | Opening/planned activities, not retrospectively completed | [MINDEF](https://www.mindef.gov.sg/news-and-events/latest-releases/5sep26-nr2/) |
| 4472 | 2026-09-09 | Maritime Cooperation with PLA Navy; reported 5–9 Sep | Reported concluded; **same exercise as 4466** | [MINDEF](https://www.mindef.gov.sg/news-and-events/latest-releases/9sep26-nr/) |
| 4428 | 2026-09-18 | Singaroo (Australia); held 15–18 Sep | Reported concluded | [MINDEF](https://www.mindef.gov.sg/news-and-events/latest-releases/18sep26-nr2/) |
| 4849 | 2026-10-02 | ASEAN–India Maritime Exercise (28 Sep–2 Oct) **and** ADMM-Plus maritime-security JCA (21–25 Sep) | Reported participation in **two** activities, one publication | [MINDEF](https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-nr3/) |
| 4983 | 2026-10-08 | Pelican (Brunei); held 2–6 Oct | Reported concluded; separate 8 Oct demonstration described | [MINDEF](https://www.mindef.gov.sg/news-and-events/latest-releases/8oct26-nr2/) |

The shortlist describes **seven exercise/program activities, supported by seven preserved releases**: the ASEAN release covers two; two Maritime Cooperation releases concern one. The separate underwater-demolition demonstration associated with Pelican is *not* automatically counted as another exercise. These are human-reviewed interpretations of what the issuer **reports**, not independently verified operational events.

**Explicit rejection:** record **4440** is the Singapore–Malaysia *air-force* SAREX MALSING announcement, and therefore does **not** belong in the naval pilot despite a broad initial lexical match. The tightened repeatable audit now returns seven naval records, not the initial eight.

**Source diversity caveat:** MINDEF is the *single* originating institution for all seven. Multiple foreign counterparts do not make them independent sources. China Desk records 3924, 4102 and 4164 provide a relevant separately issued perspective for Maritime Cooperation but are already governed by the unapproved Timeline pilot; they are **not** imported as automatically approved dossier statements. Do not claim Japanese, Bruneian, Australian, Chinese or multilateral institutional endorsement absent their separately verified source records.

## What makes this a dossier rather than a timeline

**Reader question:** How does Singapore's Ministry of Defence document the Navy's bilateral and multilateral exercise participation during this preserved July–October 2026 window, including participating organizations, exercise type, stated training objectives and what is not documented?

**Proposed structure (editorial draft, not published prose):**

1. **Scope, provenance and limits.** The selected publication family, title-discovery methodology, exact date window and exclusions; no blanket Singapore Navy or bilateral relations coverage claim.
2. **Bilateral exercise relationships.** Brunei/Pelican, Australia/Singaroo, Japan/Singapan and China/Maritime Cooperation; carefully distinguish the issuing account from mutual confirmation.
3. **Multilateral participation.** RIMPAC, ASEAN–India Maritime Exercise, ADMM-Plus maritime-security JCA; distinguish exercise participation from role/leadership.
4. **Documented activities and training domains.** Labelled issuer descriptions of manoeuvres, gunnery, communications, maritime security, HADR/search-and-rescue, diving, and information-sharing where an exact source says so. Do not infer gains in operational readiness or trust from participation alone.
5. **Disagreements and knowledge gaps.** Exercise announcement versus completion; Maritime Cooperation start-date disagreement stays in the separately approved Timeline if/when admitted; unobserved ministry releases or other governments' sources are coverage limitations.
6. **Primary-source register and dated changes.** Exact record IDs, publisher date, actual event interval when attributed, issuing body, link to archive, link to original MINDEF page, most recent independent human review. A later revision states exactly which sections and source citations changed.

This is nonchronological, maintained *subject research*: users can compare forms of cooperation and cited training domains without treating IPR's lexical inventory as comprehensive.

## Go/no-go gates before B1

- [ ] Owner selects this specific narrow subject, period and source restrictions. Research recommendation alone is not owner approval.
- [ ] Independently re-open each of the seven preserved original bodies via read-only scratch SQLite and compare precise stored original wording/metadata/URL with the current first-party releases; record hashes and any drift, truncation or missing bodies.
- [ ] Review copyright/source-use and any media rights, per \`CONTENT_AND_DATA_RIGHTS.md\`; don't republish full third-party bodies or images.
- [ ] Produce an **editor-reviewed** claim-to-excerpt/source matrix. Every proposed public assertion must be explicitly attributable; distinguish a stated future phase from an after-action report.
- [ ] Verify context, duplication, and negative cases; a high count or lexical similarity cannot establish coordination or significance.
- [ ] Explicitly decide how an approved Dossier references *approved* Brief No. 15 and the still-**draft/unpublished** Maritime Timeline. Never auto-admit or link a private timeline as public.
- [ ] If substantive claims across distinct activities prove thin, **decline** the pilot rather than publishing a dressed-up list.

## Mechanical verification and scope isolation

The branch-only GitHub Actions job compiles the Python script, reads the existing DB through \`scripts.reconcile_db.read_only\`, checks SQLite integrity and foreign keys, inventories actual registered desk state, and compares SHA-256 plus Git status before and after. It does not scrape, use models, send mail, modify \`pla_watch.db\`, render \`output/\` or run a public publish path. All checks passed in [run #38010490752](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38010490752).

**Stop condition:** source audit and owner decision packet. Do **not** continue automatically into B1, B2, Timeline merges, or Sunday Brief production. This research audit has no journal or extra publication format.
