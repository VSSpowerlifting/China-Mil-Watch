# Japan Coast Guard linked-PDF completeness — research review (2026-10-08)

**Status: bounded research only; no documents admitted, no collector changes, no editorial approval.** This work is deliberately separate from main-target collector integration PR #212 and does not alter its CI.

## Why this matters

The JCG English HTML releases are first-party, substantive original sources, but each links a distinct original PDF. The live JCG adapter (#208, consolidating into #212) correctly archives only English HTML article body text and preserves the linked PDF URLs as *uncollected attachments*. An extracted HTML body of 985, 1,158 or 1,191 characters **cannot be called the entire release document** without comparing the attachments and determining their publication/status relationship.

Three official release identities are fixed for this test:

| ID | Official release | Publisher date | Linked attachment |
| --- | --- | --- | --- |
| jcg-en:9455 | https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html | 2026-10-06 | one official linked PDF, URL obtained from article |
| jcg-en:9453 | https://www.kaiho.mlit.go.jp/e/topics_archive/article9453.html | 2026-10-06 | one official linked PDF, URL obtained from article |
| jcg-en:9436 | https://www.kaiho.mlit.go.jp/e/topics_archive/article9436.html | 2026-09-29 | one official linked PDF, URL obtained from article |

The public BAKAMLA and PCG pages expose those links separately from the English HTML prose. The links are not citation-neutral duplications unless their actual contents establish it.

## Exactly scoped Actions experiment

`scripts/probe_japan_jcg_pdf_completeness.py` performs one `robots.txt` request (readable policy or an exact 404 absence only), then at most one GET for each of the three declared HTML article URLs, followed by one GET for the **single, publisher-linked, same-origin PDF** on each page. No URL guessing, redirects, retries, proxies, challenge solving, cookies, or third-party mirrors.

- HTML maximum 256 KiB; PDF maximum 2 MiB; max 12 PDF pages; request timeout 18 seconds and delay 2 seconds between GETs.
- PDFs are parsed **in memory** using the already declared `pypdf` dependency; encrypted, malformed or oversized documents are refused.
- Emit only official source URLs, HTTP-independent content SHA-256, byte count, PDF page count, machine-extracted text character counts, possible image-only pages, and limited token-overlap metrics.
- Never log, upload, commit or preserve PDF bytes, original HTML, extracted original prose, photographs or images. The Actions artifact is metadata only.
- Source-policy check: the JCG's stated PDL 1.0 default does **not** grant automatic permission over logos, separately marked material, or third-party photographs. This work does not copy any media or images.

## How to interpret the metrics

`html_coverage_ratio` is a mechanically computed approximate overlap of English word tokens found in the extracted PDF vs the scoped HTML body. It is not semantic equivalence, independent corroboration, translation verification or a publication permission determination. PDF image pages may contain text that `pypdf` cannot extract. It is **not** an automated statement that the HTML body contains every publisher disclosure.

- If PDFs provide additional substantive prose, create an **independently governed PDF companion extractor**, with official URL/date/issuer association, attachment-specific hashes, rights checks and distinct extraction fidelity tests. Do not inject new words into the existing HTML source record without an audit trail.
- If PDF is substantially identical to the HTML but adds images, preserve metadata about the linked original PDF and explain that its imagery was not archived.
- If a PDF is text-sparse or image-only, escalate to human original-document comparison. Do not substitute OCR or make invented completeness claims.
- If origin/rights/size/route is blocked, record explicit **not retrieved**, do not reinterpret the HTML article as full publisher coverage.

## Relation to production promotion

JCG can be a **narrow HTML-only** shadow source while attachment completeness is under assessment, as long as every stored record is transparently labeled `published_html_text_only`. This does **not** qualify it for full-document production claims. The Day 7/14/30 review, publisher original-language comparison, exact-state-commit review, and owner promotion approval remain mandatory.

Once the metadata-only Actions run finishes, preserve its exact run ID and the three per-source verdicts in activation issue #205. This research does not authorize any state branch writes or immediate production admission.
