# Japan MOD: independently inspect three remaining non-HTML PDF source gaps (2026-10-13)

**Verdict: two original PDF documents are independently visually readable, but are correctly uncollected as machine text; the third remains uninspected under the collector's resource-size refusal. None may be silently reclassified as a complete archive original or moved into production.**

This is actual, publisher-specific source research on the **three non-challenge failures**, not another collection system, OCR proposal, rights approval, full-Japan coverage claim or source-license certification. All URLs point to first-party Japan Ministry of Defense originals.

## Why these particular documents

The [October 13 MOD shadow ledger](https://github.com/VSSpowerlifting/China-Mil-Watch/blob/shadow/jp-mod/state/ledger/20261013T031019%2B0000-38340339981-1.json), exact blob `366291139240965db5a9b02214858e6a26b3ad2e`, records logical **October 12**, `result=ok_all_duplicates`, **health=partial**, five stored originals, 158 outstanding gaps, **155 known challenged**, and this run's **one fetch failure plus two extraction failures**. The scheduled Actions [run #38340339981](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38340339981) and its finished job #115109674334 confirm that summary. That does **not** mean three new items first failed on October 12: older gaps are retried, and the ledger retains source-history separation.

Read-only inspection of the actual 217,088-byte historical `shadow/jp-mod:state/shadow.db` (Git blob **`f51ae16a0d6f1ebf8ece9292f8340b38b81ff8c5`**) identifies these **exact unretrieved source identities and stored reasons**:

| Source URL | Published (publisher path/notice) | Recorded gap reason | What it means |
| --- | --- | --- | --- |
| [`2026/09/17a.pdf`](https://www.mod.go.jp/j/press/news/2026/09/17a.pdf) | September 17 | **`pdf: no_text_layer`** | PDF response is not admitted as text. The machine's output is not a missing or zero-content government notice. |
| [`2026/09/29d.pdf`](https://www.mod.go.jp/j/press/news/2026/09/29d.pdf) | September 29 | **`pdf: no_text_layer`** | Substantial multi-page visual/typographical source exists, but the configured text parser has no extractable text. |
| [`2026/10/02b.pdf`](https://www.mod.go.jp/j/press/news/2026/10/02b.pdf) | October 2 | **`oversized_response`** | The collector's controlled response-size rule refused this URL. We did not obtain or independently read the document. |

**Source-access and policy:** `processing/pdf_text.py` has `MAX_BYTES=8_000_000` and `MAX_PAGES=200`; refusals produce **no partial text**, even when a document is plainly substantive. The adapter's network fetch also bounds response bytes **before parsing**. `no_text_layer` means no sufficient extractable PDF text layer under this parser; it does not prove the publication is blank, that the paper lacks visible words, or that OCR has been authorized. `oversized_response` is a bounded intake decision rather than a publisher HTTP-403 or evidence of file corruption. Do **not** increase the global budget just to change this ledger result or bypass the MOD HTML Cloudflare challenge.

## September 17: Camp Zukeran land-return notice — both original pages inspected

The exact first-party [September 17 PDF](https://www.mod.go.jp/j/press/news/2026/09/17a.pdf) was independently opened via a public document reader and **both** publisher-rendered pages were inspected visually (2/2). The reader exposed **no extracted text lines**, consistent with the collector's `no_text_layer` reason, while the original clearly contains readable Japanese.

- **Page 1:** MOD `お知らせ` dated September 17, 2026, `日米合同委員会合意について`. Reports Joint Committee agreement to return **part of FAC 6044 Camp Zukeran**; annex referenced.
- **Page 2:** Separate agreement overview, FAC 6044 Camp Zukeran, located within Okinawa Prefecture's **Okinawa City, Kitanakagusuku Village and Chatan Town**; approximately **7,900 m²** of land for return; the notice describes planned return by **May 31, 2027** after the land became unnecessary for U.S. use. The page contains an extensive site plan/map, which is **not** a cleared textual reuse component.
- **Editorial distinction:** approved/proposed return on a future deadline is not independent evidence that the land has already been handed back. The two-page document is **one publisher original**, not a separate record for every administrative municipality.

**Current disposition:** original accessible and content substantively classified; archive remains **unretrieved**, no text-layer equivalence, raw-PDF SHA/capture identity, map rights or model permissions established.

## September 29: eight Joint Committee matters across 13 original pages — complete visual review

The first-party [September 29 PDF](https://www.mod.go.jp/j/press/news/2026/09/29d.pdf) was independently opened and **all thirteen original rendered pages inspected** (13/13). The reader exposed **zero extracted text lines**, again concordant with `no_text_layer`, but each page has readable headings/annex fields and numerous **original maps/site drawings**. Cover publication: **September 29, 2026**, `日米合同委員会合意について`; annex approvals are dated **September 17**, which is **not** the release date. The cover says the first named facility matter **plus seven others**, i.e. **eight distinct matters within one official PDF**.

| PDF pages (1-based) | Publisher-visible matter and qualification |
| --- | --- |
| **1** | Cover: introductory notice for joint use involving **FAC 6022 Kadena Ammunition Storage Area**, **FAC 6037 Kadena Air Base**, **FAC 6077 Tori Shima Range**, and **FAC 6078 Idesuna Jima Range**, plus seven other approvals. |
| **2–5** | **First matter**, multiple associated facilities and map pages: Kadena Ammunition Storage Area, Kadena Air Base, Tori Shima and Idesuna Jima. Military exercise cited as **Keen Sword 27**. Some relevant land uses are prospective October 19–29; one Kadena usage area extends October 1–31. Airspace/land/building scopes differ and **should not be summed indiscriminately**. |
| **6** | **Second matter**, **FAC 5121 Tsuiki Air Base**: limited use of a portion of one building, approximately **20 m²**. The annex prints **福岡県春日市 (Kasuga City, Fukuoka Prefecture)** as the location, like the independently reviewed August 28 original; the later October 5 notice instead names **Chikujo Town and Yukuhashi City**. Preserve this as a source-specific municipality conflict pending an official correction; do not silently harmonize. These are distinct original notices: **do not deduplicate on facility or generic title**. |
| **7–8** | **Third matter**, facilities around **Oyanohara/Kirishima** and Japan Ground Self-Defense Force garrison locations, with distinct training areas and building details; two annex pages, **not two separate ministry release identities**. |
| **9** | **Fourth matter**, **FAC 3017 Fuchu Air Base**: limited use of land/property. |
| **10** | **Fifth matter**, **FAC 3189 Asaka Garrison (朝霞駐屯地)**: limited use of property, including buildings; the original does **not** label this site as a dependent housing area. |
| **11** | **Sixth matter**, **FAC 3035 Narashino Training Area**: land and building scopes separately specified. |
| **12** | **Seventh matter**, **FAC 4161 Komatsu Air Base (Kyogamisaki communications-related site)**: limited land and building use. |
| **13** | **Eighth matter**, **FAC 4180 Hofu Kita Air Base**: limited land/property use, with prospective October training time period. |

**Interpretation:**
- The eight formal approvals are **not eight independently collected PDFs**. Only the publisher's **one 13-page notice** is the source record candidate. Matter-level analysis would need review and citations to exact annex/page.
- Prospective **Keen Sword 27** use and dates are planned/authorized uses, **not** independently observed exercise execution, future outcome or proof of transferred assets. Military-site map graphics, layers, aerial/base information, Japanese labels and third-party cartographic content remain **reuse and model-image HOLD**.
- The PDF requires OCR/other explicitly authorized image-to-text work if machine extraction is desired. Reclassifying it as an “empty document,” manually copying full annex prose into the shadow corpus or silently forcing `extract=OK` would corrupt archive integrity.

**Current disposition:** 13/13 page visual reading certifies this bounded source identification, **not** current original-byte hash, collector-client raw parity, map custody, a page-perfect machine transcript or source-by-source rights.

## October 2: oversized PDF — bounded unresolved access, no claimed contents

The shadow collector records [`2026/10/02b.pdf`](https://www.mod.go.jp/j/press/news/2026/10/02b.pdf) as **`oversized_response`** under the existing 8 MB configured maximum. The public document reader was **unable to open** the original at that URL on this review. Consequently we have **not** established its current served file's exact byte count, page count, internal notice date, official subject(s), map/photo content, extraction fidelity or individual reuse rights. The source URL is real in the collector's feed-derived identity and unresolved-state ledger, but no content-specific assertion is made.

Do **not** automatically lift limits, split/recompress a copied file to fit, guess titles or write any replacement text to production. A separately authorized, publisher-compliant, resource-bounded exact-version observation may record MIME, status, byte length, page count and SHA as permitted, followed by a reviewed decision whether a narrowly scoped high-size PDF mode is justified. The ordinary Japan MOD collector remains unchanged.

## Consequences and next human decisions

1. **No technology-only promotion shortcut.** The two page-visible PDF notices illustrate why the existing PDF extraction health is partial: machine-readable original text is not available under the approved parser. A field-level human interpretation may inform an IPR-authored research note **with publisher citation**, but is not original-language PDF text suitable for the immutable `text_original` model.
2. **Source-by-source rights check.** Government-owned prose potentially falls under MOD's PDL1.0 baseline **only** if the relevant document/version and separate ownership exceptions are verified. Maps, charts, third-party overlays, insignia, original image/scan bytes and AI model processing need independent review. No long passages, maps or page images are embedded in this research document.
3. **Do not alter source history.** Preserve the exact `shadow_unretrieved` statuses and five archived text-bearing PDFs. The additional originals are genuinely published and observed, but **not** source-qualified collecting days and not production-admitted records. The MOD HTML 403/challenge boundary and JCG guarded collection clock remain separate.
4. **Potential future controlled scope:** named reviewer can approve a *metadata-only* bibliography entry or independently authored explanatory prose for these visible originals, and separately decide whether a publisher-compliant, constrained OCR/text extraction experiment is lawful and worthwhile. That would require original-byte identity, every-page comparison, media exclusion, rights and named owner signoff. **No such authorization occurred in this work.**

**Changes in this PR:** one engineering research Markdown file. No `output/`, `gh-pages`, collector, tests, production/shadow databases, deployment, source license adjudication, cron/feature gate or PDF custody changed.
