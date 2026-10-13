# Philippine Coast Guard MEPCOM — source feasibility (12 October 2026)

**Scope:** Philippines Desk research, first-party Marine Environmental Protection Command (MEPCOM) environment/pollution-response source family. [Issue #223](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/223).

This is an independent **source-identification engineering checkpoint**, not a collector, archive, source permission, human signoff or desk promotion. It does not establish comprehensive PCG operations coverage, South China Sea monitoring, or military activity reporting.

## What the publisher's public website shows

- The [MEPCOM homepage](https://mepcom.coastguard.gov.ph/) presents linked articles with publisher-visible posting dates, including two posts dated **September 10, 2026**. One concerns a **July 21** budget/performance review; another concerns **July 21–22** Central Visayas oil-spill response training. The event dates are not publication dates.
- The named [News page](https://mepcom.coastguard.gov.ph/news-2/) was readable through a public text-view service on October 12 but provided **no visible article listing in that extracted view**. That is not proof it is empty to a browser, lacks hidden dynamic content, or is an official complete enumerator.
- A [July 2026 paginated archive](https://mepcom.coastguard.gov.ph/2026/07/page/8/) independently demonstrates historical listing navigation and displays **July 28** posting dates for multiple articles, including an ASEAN-focused abandoned fishing-gear coordination meeting. A page/8 route is not proof of complete chronology or stable pagination.
- The sampled WordPress-style article paths contain percent-encoded mathematical-alphabet Unicode characters. A slug reconstructed from normalized display text will **not** necessarily refer to the same resource. Preserve the exact publisher-linked URL, including percent escape case, as the source identity.

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
