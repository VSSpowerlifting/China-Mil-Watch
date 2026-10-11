# South Korea Desk — DAPA second-issuer identity pilot

**Prepared October 11, 2026.** Status: research observations + synthetic-only engineering contract. **No collector, publisher contact via GitHub Actions, original-document body retrieval, state branch, source admission, or rights approval.**

## Grounded official source observations

South Korea's government Policy Briefing portal has a real **Defense Acquisition Program Administration** (DAPA; 방위사업청) press-release filter, not the same issuing body as the existing **Ministry of National Defense** (MND; 국방부) family:

- DAPA-filtered publisher listing: https://www.korea.kr/briefing/pressReleaseList.do?pWiseMinistry=ministryNews&repCode=B00008&repCodeType=%EC%A0%95%EB%B6%80%EB%B6%80%EC%B2%98
- First candidate, October 8, 2026, press release on defense-sector mutual-aid association eligibility expanding to aerospace and military-support suppliers: https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784618
- Second candidate, October 8, 2026, record of qualification examination applications: https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784625

The official portal labels both as issued by DAPA and **republished by the government Policy Briefing host**. This is **not direct dapa.go.kr retrieval** and does not independently corroborate a DAPA claim if the same release is also shown on a separate government distribution page. The October 8 sample page identifies **both an HWPX and a PDF** of the same release, unlike the existing MND-family collector's strict exactly-one-HWPX document contract.

The October 8 DAPA sample also displays a Korean text-only **KOGL Type 0 free-use notice**; an earlier MND sample showed a different KOGL Type 1 notice. Their text-use labels are **page-specific publisher claims**, not blanket permission for every attachment, embedded image, full-text archival copy or translation. Confirm actual original source text, authorization, license and terms with a human before retaining anything beyond permitted metadata. Never conflate a page notice with an HWPX/PDF attachment license.

## Delivered: an explicitly disabled source identity contract

- scripts/review_korea_dapa_source_contract.py validates the fixed DAPA filter and strict **www.korea.kr** news identity `korea-dapa-policy:<newsId>`. Only known link-navigation parameters may be dropped to canonicalize a newsId. A URL query claiming `A00005`/MND, administrative aliases, off-host redirects and duplicate/invalid IDs are rejected.
- A **synthetic HTML prototype** checks DAPA's separate issuer label/code, publication date consistency, document attachment count and two supported file extensions. It does not extract bodies, fetch links or store originals. HWPX and PDF have distinct `fileId` identities; these are different formats of an issued document, **not two independent releases**.
- Observed licence labels remain `KOGL_type_0_notice_only`, `KOGL_type_1_notice_only` or `unverified`, with `publisher_permission_approved=false` regardless. The current synthetic marker for the licence block, as well as attachment container selectors, are **fixture placeholders** and require an explicitly authorized source-served DOM comparison before any live parser or collector can be proposed.
- All production, publisher-access, original-body and registry flags stay false. The module contains no network calls, source capture, clock, scheduled job, shadow manifest or email. Its tests do not contact korea.kr.

## Next independent gates

1. **Publisher rights and access.** Human/operator checks exact korea.kr robots and copyright policy and assesses whether a bounded server-side filter POST/GET is permitted. A web-page appearance and canonical source-link existence **do not certify GitHub Actions access** or reproduction rights. If robots unreadable or access denied, stop rather than evade.
2. **Rendered issuer/filter truth.** When permitted, compare real official HTML DOM and dates against this synthetic provisional contract. Resolve pagination, posted versus effective dates, missing/duplicate releases and issuer syndication labels, including the joint DAPA/KASA release: a joint issuer is not a new independent corroborator.
3. **Document truth.** Determine whether HWPX, PDF or both are publisher-served with stable file IDs and accurate Korean content; preserve version linkage. Do not count two attached formats as two events or assume PDF text equals HWPX. Use source-specific document license review.
4. **Disabled source candidate, own clock.** Only after original and rights gates, an independent PR can propose a DAPA-only shadow manifest, bounded adapter and tests. It **cannot inherit** the existing MND Policy Briefing shadow state, clock, human verification or public-registry standing.
5. **Human review/qualification.** Apply source-bounded 7/14/30-day reliability and original-language semantics, source-use receipts and owner decision. Korea is currently **not** an admitted public desk; nothing here changes that.

### Negative contract proof

Run `python -m unittest tests.test_korea_dapa_source_contract -v`. Tests reject MND `A00005` links, off-site download references, duplicated document IDs, wrong issuer text/code, wrong dates, unknown attachments, misleading licence markup and novel query fields. No Actions network invocation, no model tokens, no source database or source manifest changes.

**Release decision:** the code and source observations can be reviewed as **disabled engineering groundwork only**. This is not a source qualification or automatic pipeline enrollment.
