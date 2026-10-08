# Singapore strategic goods — metadata-only source-admission review

**Research cutoff:** 2026-10-08 · **Issue:** [#168](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/168) · **Status:** curator research only; **not** an archive, activation, source-use compliance signoff, or independent human review.

The owner authorized a **narrow review of exactly two original Singapore legal instruments**, not ongoing Singapore Customs/Gazette monitoring, collection, publication, or automatic `export_controls_sanctions` labeling. The adjacent `source_admission.json` pins only externally observable documentary metadata and explicit closed approval gates. The source PDFs and their full text are **not saved to this repository**.

## Source-first legal chronology

| Original Singapore Government Gazette | Made | First gazetted (local Singapore time) | Commencement | Revokes |
| --- | --- | --- | --- | --- |
| [**S 660/2025** — Strategic Goods (Control) Order 2025](https://assets.egazette.gov.sg/2025/Legislative%20Supplements/Subsidiary%20Legislation%20Supplement/660.pdf), **519** pages | 2025-09-30 | 2025-10-01, **17:00** | **2025-12-01** | S 641/2024 |
| [**S 741/2026** — Strategic Goods (Control) Order 2026](https://assets.egazette.gov.sg/2026/Legislative%20Supplements/Subsidiary%20Legislation%20Supplement/26sls741.pdf), **523** pages | 2026-09-24 | 2026-10-01, **17:00** | **2026-12-01** *(future as of research cutoff)* | S 660/2025 |

**Exact external PDF page anchors:** p. 1 of each original establishes title, Gazette number, first-publication time, enabling Act section 4A(1), legal maker, citation, commencement and revocation; the last numbered page (**519 / 523**) establishes the made date and signatory. These are **publisher-page locators, not IPR archived quote offsets**. The 2026 Order is already made/published but **not effective in October 2026**. Its revocation of the 2025 Order is part of the **future** effective legal succession, not an October 1 repeal.

The **legal maker** is the Minister for Trade and Industry (Trade in 2026); the **publisher** is Singapore's Government Gazette; **Singapore Customs** supplies administrative guidance. They are not interchangeable issuing identities. The two documents represent **one regulatory succession**, not two independent confirmations of a new enforcement event. No line-by-line 519-versus-523-page controlled-item delta was performed, and no specific new restrictions are claimed.

## Actual Gazette Terms of Use — conditional reuse, not presumed blanket license

[Official e-Gazette Terms of Use](https://www.egazette.gov.sg/terms-of-use/), **last updated July 10, 2026**, distinguish the general restriction in clause 6 from the **conditional permission to reproduce e-Gazettes** in clause 11. This is a meaningful improvement on a generic "rights unknown" statement, **but it is not yet an IPR-specific compliance decision**.

Required conditions recorded for later human/editor assessment include government copyright and permission attribution; a reference to the current e-Gazette; responsibility for reproduction accuracy; no implication of government affiliation; restrictions on automated extraction (non-abusive, non-deceptive, non-disruptive, no circumvention); and clause 12's ability to revoke or modify permission. Clause 17 permits links subject to conditions while prohibiting framing/embedding. Government Gazette rights, Singapore Customs site rights, and the independent IPR publishing context must not be conflated. This phase **did not contact the publisher, request bespoke permission, implement a takedown workflow, automate harvesting, or approve any body retention/display**.

Before any archive ingestion the editor should document whether IPR's exact intended preservation and display satisfy these terms, how current-source links and mandatory notices will appear, and how takedown/revocation and automated-access policy will be observed. A legal/rights assessment may be appropriate if uncertainty persists. The source-use status in the JSON remains **not adjudicated**.

## Provenance and editorial boundary

On inspected `main`, [Singapore's production manifest](../../desks/singapore/manifest.json) (Git blob `8b0cdf32159c6c385a070153fa282428221fe695`) contains **only** `sg_mindef_releases`, not Gazette or Customs. That establishes a direct producer-registration gap, **not** a proof that no copies exist anywhere in IPR history.

- **SGEC25**: editor-only hypothesis for a *specific existing strategic-goods restriction*.
- **SGEC26**: editor-only hypothesis for a *formally published, future-effective restriction*.

These are candidates, **not approved positive examples**. Do not pass role-labeled JSON into a blinded reviewer packet. Independent readers must consult publisher originals; the future year of effect, actual enforcement, full controlled-goods schedule changes, and attribution of agency claims require separate determinations. Previously verified negative/borderline candidates (Vietnam **P46**, Korea **P58**) remain in Issue #168 and are **not part of this two-instrument packet**. Historical Singapore **P33** is also unresolved and has not been replayed here.

## Reproducibility and stop condition

```bash
python3 scripts/validate_singapore_strategic_goods_metadata.py
python3 -m unittest tests.test_singapore_strategic_goods_metadata -v
```

The validator performs **offline structural assertions only**. It refuses altered original URLs/dates, an invented second policy succession, omitted Gazette rights conditions, fake archived hashes/quote offsets/IDs, premature human approvals, full-text fields, and collector permissions. A passing test **does not** prove legal compliance, source capture, original-PDF integrity, human judgment, or a historical classifier accuracy score.

**Stop here:** No PDF bytes, publisher article body, source archive IDs, corpus mutation, production manifests, active collectors, workflow changes, topic attachments, or public output are added. The next separately authorized step is a **bounded archival source capture and source-language human review**, *only after* an owner/editor makes an explicit source-use compliance decision. It must collect verifiable capture dates, source PDF hashes, and archived original quote offsets instead of inventing them.
