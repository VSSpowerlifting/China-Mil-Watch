# Korea DAPA — October 8 two-release first-party rights and attachment review

**Research observation:** 2026-10-13. **Disposition:** SOURCE-REVIEW EVIDENCE ONLY; NO COLLECTOR OR PRODUCTION ADMISSION.

This verifies **two distinct releases** by the South Korean Defense Acquisition Program Administration (DAPA, `방위사업청`) as republished by the Korean government's Policy Briefing portal. It supplies per-document, first-party permission observations beyond the standing general rights policy; it does **not** certify linked HWPX/PDF bytes or authorize model/editorial/public ingestion. These are publisher-level observations from publicly rendered pages, **not** an authenticated GitHub Actions-run access canary.

## 1. Two exact first-party identities, not four sources

The [DAPA-filtered official press-release index](https://www.korea.kr/briefing/pressReleaseList.do?pWiseMinistry=ministryNews&repCode=B00008&repCodeType=%EC%A0%95%EB%B6%80%EB%B6%80%EC%B2%98) currently lists both items under the **B00008** issuer filter, each with **October 8, 2026** portal posting dates. DAPA is the attributed **issuer**; the portal is the **republisher**. Neither is an MND `A00005` identity, and neither belongs in the five-link MND public bibliography.

| Item | Official portal identity and observed original-language claim | Visible original attachment link labels | On-page use notice |
| --- | --- | --- | --- |
| [`newsId=156784618`](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784618) | Joint DAPA/space-agency release: expansion of defense-industry mutual-aid association eligibility to aerospace and military-support-system suppliers, **reported as effective October 8**. This is a government policy claim, not evidence of take-up or reduced actual premiums. | One `261008` PDF and one `261008` HWPX, with the same joint-release identity in their labels. | **KOGL Type 0, text only**; other media excluded from the scope of the displayed notice. |
| [`newsId=156784625`](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784625) | DAPA release reports **1,374** registrations for the eighth defense program-management national qualification exam and a 37.8% year-on-year increase. These are agency-reported applicant counts, not independently audited participation or qualification outcomes. | One `261008` HWPX and one `261008` PDF, with the same exam-release identity in their labels. | **KOGL Type 0, text only**; other media excluded from the scope of the displayed notice. |

**Provenance precision:** the official pages label these as government agency press releases that the Policy Briefing service has republished. A PDF and HWPX attached to the *same release* are alternate file formats, **not two corroborating original sources**. The displayed attachment filename prefixes are **date cues**; neither their binary payloads nor internal document creation/distribution times have been obtained here. On the public page renderer, the article body appears as a linked `content` shell; page availability alone is not proof of reviewed original text.

## 2. Exact DAPA publisher attachment targets (link identities, NOT retrieved originals)

The public first-party Policy Briefing HTML exposes the following download links,
with `tblKey=GMN`, and the web browser resolves each target to an
`application/x-download` response that its text reader **cannot render**:

| Portal press ID | Document format and visible `261008` label | Original publisher-hosted download identity | Bytes, digest and text fidelity |
| --- | --- | --- | --- |
| `156784618` | Joint DAPA/KASA **PDF** | [`fileId=198567088`](https://www.korea.kr/common/download.do?fileId=198567088&tblKey=GMN) | **Not retrieved or hashed** |
| `156784618` | Joint DAPA/KASA **HWPX** | [`fileId=198567089`](https://www.korea.kr/common/download.do?fileId=198567089&tblKey=GMN) | **Not retrieved or hashed** |
| `156784625` | DAPA exam **HWPX** | [`fileId=198567114`](https://www.korea.kr/common/download.do?fileId=198567114&tblKey=GMN) | **Not retrieved or hashed** |
| `156784625` | DAPA exam **PDF** | [`fileId=198567115`](https://www.korea.kr/common/download.do?fileId=198567115&tblKey=GMN) | **Not retrieved or hashed** |

These are exact first-party **link** identities, not archival capture
receipts. A local attempt to reach the publisher from the available
execution environment failed DNS resolution, which establishes
**environmental inaccessibility only**, not an invalid publisher URL or
publisher access restriction. No response bytes, file SHA-256, embedded
media permission, page-count parity, original document publication time,
or successful Actions-run retrieval is asserted.

## 3. Joint release cross-posted by Korea AeroSpace Administration — rights conflict

The [Korea AeroSpace Administration (KASA) own-host press release
`plcyBrfNo=518`](https://www.kasa.go.kr/prog/plcyBrf/brief/kor/sub01_01_04/view.do?plcyBrfNo=518)
is a **separately hosted publication by the joint announcing agency**
about the same October 8 mutual-aid eligibility reform. It reports
**posted October 8, 2026, 08:00 KST** and explicitly describes the
membership expansion as implemented effective October 8. The KASA
article body discusses the underlying legal change, qualifying
aerospace/space/defense-support suppliers and the added eligible
guarantee-business scope. This is contemporaneous first-party
corroboration of the agencies' joint public *announcement*, **not an
independently observed uptake, payment or insurance-cost outcome**.

The KASA page links one `261009(조간)` **HWPX** and one similarly
named **HWP**, contrasting with the Policy Briefing DAPA edition's
`261008` **HWPX/PDF** pair. These labels reflect distinct public
distribution editions and anticipated morning publication, and
**do not authenticate the internal creation timestamps or byte-level
equivalence of any of the four files**. A separate
[KASA-attributed Policy Briefing republication
`newsId=156784666`](https://m.korea.kr/briefing/pressReleaseView.do?newsId=156784666&pWiseMinistry=ministryNews&repCode=B00026&repCodeType=%EC%A0%95%EB%B6%80%EB%B6%80%EC%B2%98)
also exists. It has a distinct portal newsId/issuer filter, but
the underlying announcement is the **same policy event**. Do not
duplicate counts or mistake cross-posting for independent claims.

**Material rights conflict:** the DAPA-attributed Policy Briefing page
`156784618` displays **KOGL Type 0, for text only**. KASA's
*own-host page* prominently displays **KOGL Type 4 (attribution,
non-commercial use only, no modification)** on its own publication.
These are **different edition-specific publisher rights notices**;
neither is a blanket license for the other's article or attachments.
In particular, do **not** use the Type 0 notice to reproduce,
translate/adapt or commercially reuse KASA's Type 4 original text
or HWP/HWPX. Independent third-party media remain separately held,
even where another edition displays a permissive text-only notice.

The right engineering abstraction is a **single policy-event cluster
with multiple publisher editions**, each keeping its own issuer,
publisher host, original format, source-date cues, rights notice,
capture hashes (pending), text-review disposition (pending), and
editorial approval flag (false). This does not add the KASA host
to the DAPA or MND shadow collector or approve a cross-host request.

## 4. Per-page rights decision and the important policy discrepancy


Both specific release pages expressly mark their **text** with `공공누리 제0유형(자유이용)` (KOGL Type 0: free use) and immediately distinguish photographs, illustrations, video and other non-text materials, whose rights might belong to third parties. This is a genuine **page-specific Type 0** observation, not an absent or automatically defective KOGL mark.

However, the portal's separately published [general copyright policy](https://www.korea.kr/guide/copyRight.do) describes **Type 1** publication/attribution as its standard freely usable text category and asks visitors linking directly to portal material to link the copyright policy as well. That standing wording is **not identical** to the two Type 0 article notices. Preserve both facts; do not silently relabel the DAPA items as Type 1 or interpret their Type 0 labels as blanket binary/media permission.

**Disposition by material:**

- **Direct article-page links, official titles, factual metadata, non-substantial original editorial descriptions:** suitable for **private research cross-reference** with explicit first-party attribution. This finding itself does not alter any production publisher gate.
- **Page-marked text:** a favorable **text-only KOGL Type 0 reuse observation** for each exact page. Before a public English synopsis, separately review the Korean text and licensing/attribution requirements, preserve a source hash, and require owner/editorial approval. This record does not grant that approval.
- **HWPX/PDF originals as distributed files:** **HOLD** for capture SHA-256, content/format comparison, document-level embedded figures/tables, alternate third-party works and reuse-scope review. Do not mirror full originals publicly simply because their landing pages carry Type 0 text marks.
- **Press images, graphics, illustrations, video, other third-party media:** **NOT CLEARED** for IPR reproduction.
- **Collector authority:** public reader access is not proof of GitHub-runner permissions, robot-compliant authenticated collection, or DAPA source qualification.

The same host's publicly readable [robots policy](https://www.korea.kr/robots.txt) currently gives wildcard `Allow: /`; this **does not** substitute for the independently required DAPA GitHub-runner, robots-first canary, response inspection, and separate second-institution approval. DAPA must not inherit the MND collector's qualification or its exactly-one-HWPX shape rule.

## 5. What remains before admission

The [Phase 2 Korea issue #221](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/221) describes the manual, one-shot DAPA source-access canary added under PR #381. That canary remains a **separately authorized operator action**, not a completed observation in this dossier. Required subsequent gates:

1. Obtain the actually authorized robots-first GitHub-runner listing access result, preserving its exact run SHA, policy verdict and issuer-filter identity; stop on denial, challenges or incompatible filters.
2. Acquire the relevant public HTML and both original linked file formats through a separately approved, bounded path. Verify MIME/format/size, hash each original, inspect text/tables/figures, and establish whether the PDF and HWPX are substantively equivalent.
3. Conduct source-specific, independent Korean-language and copyright review. Distinguish **agency announcement/effective date** from independently measured implementation or contract outcomes; distinguish **applications received** from exam qualifications.
4. Maintain a separate DAPA private state/identity space if later authorized. No automatic MND fusion, Sunday-brief export, SQLite import, new public corpus rows, or expansion of the fixed Korea bibliography.
5. Only after record-specific rights, human review and owner production authorization may an English analytical synopsis be considered for publication.

**Decision at this checkpoint:** The two October 8 DAPA articles are **distinct and text-rights-labeled first-party leads**, with **four visible attachment links across two source identities**. Their publisher-page reuse notices are now verified separately. Full original-document fidelity, publisher-runner access, independent translation, record admission and public release all remain **HOLD**.
