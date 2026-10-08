# Philippine event-source independence pilot — archival lineage before corroboration

**Scope:** Read-only governance and engineering evidence. The pilot is **not** a production classification engine, an accepted event registry, or a signed editorial review.

## The mistake this prevents

Indo-Pacific Record now holds several AFP press releases about one exercise and may eventually collect PCG-originated documents through more than one institutional website. Counting **links**, **articles**, **hosts**, **issuer credits**, and **independent institutional sources** as if they were interchangeable will overstate regional evidence.

The AFP released three separate articles on the 2026 Sanlakas exercise, with preserved IDs `afp:1391`, `afp:1393`, and `afp:1394`. Those articles establish a useful *publisher-reported chronology*, not three independently corroborating institutional viewpoints. The separate September 29 JPSCC meeting (`afp:1390`) is a different proposed event, even though it involves the same institutions.

PIA hosts pages that prominently display the byline `By PCG`. The byline identifies a **claimed contributing/issuing organization**, while the **hosting organization** is the Philippine Information Agency. Until independently authenticated, the PCG byline is an attributed origin, **not a verified origin**. If an identical PCG-original publication later appears on a PCG website and on PIA, two hosted copies should still count as **one originating institutional assertion**. The PIA copy does not become an independent PIA voice by virtue of appearing on a government site.

## Exact research input

- `research/philippines/sanlakas_2026/source_event_candidates.json`: existing four-AFP-source, eleven-claim, two-proposed-event dossier, with its original shadow commit and exact original extracted-text and capture hashes
- `research/philippines/evidence_independence/pilot.json`: four AFP first-party archive references, two separate provisional event memberships, and two **unadmitted** PIA-hosted pages displaying PCG credit
- `scripts/audit_ph_event_source_lineage.py`: pure offline validator and report generator
- `tests/test_ph_event_source_lineage.py`: 23 synthetic contracts including multi-host mirrors, issuer/host separation, unrelated-event attribution and counterfeit human approvals

The two PIA links in the pilot are **public discovery URLs**, not IPR archived source rows. Their original response SHA-256 fields are intentionally absent, and neither is linked as evidence for the two provisional AFP events. The pilot refers to these leads independently of #191, whose admission criteria remain separately subject to review.

## What the report means

Run from the repository root:

    python3 scripts/audit_ph_event_source_lineage.py

The validator reads the already merged event dossier and the separate attribution pilot. It confirms **exact AFP source IDs, original source URLs, publisher-preserved text SHA-256 and capture SHA-256**, fixed event membership, eleven AFP-origin evidence claims, distinct event identity, and all unfinished human/rights/timeline gates. It does not fetch originals from the live web or independently replay shadow SQLite; the Day-0 archive gate remains the authority for that underlying historical Git replay.

Expected conservative logic:

| Event hypothesis | AFP article records | Provisionally attributed issuing institutions | Independently authenticated institutional confirmations |
|---|---:|---:|---:|
| September 30–October 2 Sanlakas 2026 exercise | 3 | 1 (AFP) | 0 |
| September 29 JPSCC meeting | 1 | 1 (AFP) | 0 |

**Zero authenticated confirmations does not mean the AFP reports are false.** It means this pilot cannot claim human-audited independent corroboration. Likewise, one provisional issuer voice is *not* a completed source-integrity review.

The two PIA-hosted, PCG-credited source leads count as **zero** independent corroborations of Sanlakas/JPSCC, since neither is archived or substantively linked to those events in IPR. They also do not count as sources in the four-record AFP archive.

## Reusable engineering distinctions

1. **Record**: one source-version entry, with exact original response digest.
2. **Hosting institution**: the organization controlling the URL/domain.
3. **Credited issuer**: an authorship statement displayed on that page. It can be false, incomplete or syndicated.
4. **Verified originating institution**: established by a later independent, attributable editorial provenance decision.
5. **Mirror relationship**: evidence-backed correspondence between two instances of **the same originating statement**; host differences never create independent claims.
6. **Event occurrence**: a date-specific proposed event with possibly multiple reporting stages; not identical to its parent recurring exercise series.
7. **Independent institutional corroboration**: a later human-reviewed source independently attributable to a separate institution, substantively supporting the same specific claim; it is not inferred from a government domain, a byline, a news report quoting an official, or an unsourced topical similarity.

This pilot's output purposefully distinguishes counts (1) and (3) from count (7). The synthetic `verified_origin_count` helper groups by **originating institution** rather than host and only counts entries that an external process has independently authenticated and genuinely reviewed. The helper's booleans are **not** evidence of an actual reviewer or confirmation of source independence. A later workflow must verify the human approval itself and distinguish syndicated copies from independently authored statements before using the count.

## Unresolved source governance

PIA's public footer says its site content is in the public domain **unless otherwise stated**. That conditional statement does not clear PCG-supplied text, images, third-party material, persistent crawling or republication without further review. The September 2026 PIA pages displaying `By PCG` are useful source-admission leads, not automatic collector permissions. The remaining PCG-via-PIA source-admission work remains tracked in #191.

No source collects, shadow database, production `pla_watch.db`, published corpus, regional topic attachment, entity merge, events table, public timeline or actual reviewer decisions are modified by this pilot.

## Required downstream editorial judgments

Before describing Sanlakas as independently corroborated, a reviewer must identify the exact claim, retrieve a separately originated primary-source statement, verify its issuing body, date and original text, and determine whether it truly corroborates rather than republishes AFP. A PCG story on PIA about an *unrelated* incident cannot support the exercise. Even a PCG statement on Sanlakas requires manual origin and same-claim examination before it contributes additional evidence.

**Testing:**

    python3 -m unittest tests.test_ph_event_source_lineage -v

Synthetic tests are not real-world source audits. Do not merge without current-head passing CI and database/output preservation checks.
