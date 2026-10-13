# Philippine Coast Guard MEPCOM — source feasibility (12 October 2026)

**Scope:** Philippines Desk research, first-party Marine Environmental Protection Command (MEPCOM) environment/pollution-response source family. [Issue #223](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/223).

This is an independent **source-identification engineering checkpoint**, not a collector, archive, source permission, human signoff or desk promotion. It does not establish comprehensive PCG operations coverage, South China Sea monitoring, or military activity reporting.

## What the publisher's public website shows

- The [MEPCOM homepage](https://mepcom.coastguard.gov.ph/) presents linked articles with publisher-visible posting dates, including two posts dated **September 10, 2026**. One concerns a **July 21** budget/performance review; another concerns **July 21–22** Central Visayas oil-spill response training. The event dates are not publication dates.
- The named [News page](https://mepcom.coastguard.gov.ph/news-2/) was readable through a public text-view service on October 12 but provided **no visible article listing in that extracted view**. That is not proof it is empty to a browser, lacks hidden dynamic content, or is an official complete enumerator.
- A [July 2026 paginated archive](https://mepcom.coastguard.gov.ph/2026/07/page/8/) independently demonstrates historical listing navigation and displays **July 28** posting dates for multiple articles, including an ASEAN-focused abandoned fishing-gear coordination meeting. A page/8 route is not proof of complete chronology or stable pagination.
- The sampled WordPress-style article paths contain percent-encoded mathematical-alphabet Unicode characters. A slug reconstructed from normalized display text will **not** necessarily refer to the same resource. Preserve the exact publisher-linked URL, including percent escape case, as the source identity.

## Original publisher article review — verified in a public reader

Both source-linked article pages were opened directly through the MEPCOM homepage's own article anchors on October 12 (not through a search-engine title match):

- **Fiscal / program performance review (MEPCOM):** the original publisher page explicitly says **posted September 10, 2026**. Its body dates the unit performance and budget-utilization review to **July 21, 2026**. This is MEPCOM's **self-reported internal administrative review**, not evidence of completed maritime patrols, delivered procurements, or operational military exercise activity.
- **Central Visayas oil-spill training (MEPG-CV):** the original publisher page explicitly says **posted September 10, 2026** and dates the training to **July 21–22, 2026**. It describes classroom instruction, equipment familiarization, and a tabletop coordination exercise. This is **a subordinate environmental-response training activity**, not proof of a live oil-spill response deployment or a second independent PCG publication.
- **Opaque permalinks:** the actual linked source URL strings match the exact two URLs recorded in the packet. The math-alphabet percent encoding is part of the publisher's permalink and must not be reconstructed from plain Latin titles.

**Method limit:** These are public web-reader observations with issuer/date content visible on each page. No reproducible raw HTTP response, checksum, server headers, full HTML fidelity check, or collector-identity acceptance was obtained. They establish a preliminary source-specific **semantic/date review**, not archive fidelity or permission to store/redistribute publisher text or imagery.

**Robots/access check:** public web retrieval of the first-party `/robots.txt` returned an internal access error. A separate, single bounded HTTP request to `/robots.txt` with an identified research User-Agent failed at **DNS resolution**, before any server response. This does **not** establish robots allowed, robots denied, or a publisher policy. Do not activate a collector.

## Bounded source record candidate metadata

The two original article URLs from the homepage and their date distinctions are in [discovery_2026-10-12.json](discovery_2026-10-12.json). The offline verifier `scripts/validate_ph_mepcom_candidate.py` refuses URL normalization, invented raw bytes or archive IDs, reverse-dating events, generic PCG relabeling of subordinate units, and accidental authorizations.

**Original issuing entity matters:** the fiscal review is attributed to MEPCOM; the oil-spill training is reported as conducted by Marine Environmental Protection Group – Central Visayas (MEPG-CV), a subordinate component. The host is MEPCOM's institutional web estate. Neither post represents independent third-party confirmation.

## Actual remaining gates

1. **Robots / access:** `https://mepcom.coastguard.gov.ph/robots.txt` could not be reliably opened through the public text-view service. Treat robots rules, redirects, HTTP policy headers and publisher access posture as *unverified*. Perform a separate, bounded first-party request using the repository's honest collector identity before proposing a collector. Stop if refused or ambiguous.
2. **Enumeration:** establish which index/page feed is genuinely navigable as a stable and complete publication listing, with exact source-discovered URLs and pagination. Homepage snippets and single archive page do not qualify.
3. **Raw parity:** capture genuinely authorized bytes into a **private** evidence fixture and compare original text, date, issuer, and canonical URL against extraction. There is currently **no retained raw response** for either sample in this work.
4. **Use rights:** review original-text storage, translated extracts, images, and public titles/links independently. Do not assume first-party government hosting grants permission to republish full articles.
5. **Qualification:** only after these gates, assess scoped marine environmental response relevance and future shadow pilot; neither AFP nor NSC source clocks transfer to MEPCOM.

## Operator command (offline; no network)

```bash
python scripts/validate_ph_mepcom_candidate.py
python -m unittest tests.test_ph_mepcom_candidate
```

This is explicitly **not** a signal to add MEPCOM to production, enable a workflow, collect history, update the corpus, or cite these as qualified IPR archive records.
