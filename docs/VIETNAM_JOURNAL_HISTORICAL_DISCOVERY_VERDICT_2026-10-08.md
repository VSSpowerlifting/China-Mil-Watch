# Vietnam National Defence Journal English — historical discovery verdict

**Observation:** October 8, 2026 UTC.  
**Decision:** **bounded first-page / rolling-window discovery, historical completeness NOT PROVEN.**  
**Source status:** disabled research candidate. No automated journal collector, metadata/full-text persistence approval, public records, or journal Day 0 / Day 7 / Day 14 / Day 30 reliability clock.

## One-shot official-host evidence

A disposable [research PR #173](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/173) was closed **unmerged** after a successful [Actions proof, run 37729004599](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37729004599), job 113153607977, at exact head `9e7b25fc96b799a5544a53e595d0d58ce26d630d`.

The synthetic tests passed **7/7** before publisher requests. The research code then completed **exactly six declared desktop HTTPS GET requests** under the existing shadow collector identity: a verified desktop `robots.txt`, four named English category first pages, and one exact publisher-exposed English keyword page (`/Keywords/Keyword.aspx?cul=en&key=Defence`). It respected the observed robots policy, at least two seconds between requests, fixed response size/time/host/redirect/challenge limits, and a no-retry rule. It requested **no article page, page-2 result, postback endpoint, invented route or mobile URL**.

| Publisher first page | Canonical IDs visible | Local date hints | Oldest observed hint | Latest observed hint |
| --- | ---: | ---: | --- | --- |
| News | 18 | 18 | 2021-04-05 | 2026-01-24 |
| Theory and Practice | 20 | 17 | 2026-09-10 | **2026-10-08 (suspect)** |
| Events and Comments | 15 | 15 | 2026-06-18 | **2026-10-08 (suspect)** |
| Research and Discussion | 19 | 18 | 2026-07-24 | 2026-09-28 |
| **Distinct union** | **72** | **68** | — | — |

These are *currently visible* links and hints. They are not proven section-level inventories: the website shows recommendations and repeated/sidebar links across pages. They are not first/last publication dates or a census of the publisher's article history. Earlier bounded observations obtained **74** and **71** IDs; because those proofs retained only aggregates/hashes and used differing hint heuristics, the historical 74 → 71 → 72 sequence does **not** identify additions, disappearances, deletions or posting cadence.

The keyword result's numbered controls (`2, 3, 4, 5, >|`) were verified against actual HTML structure as **JavaScript postbacks** in paging-style elements. These are *not* reusable category pagination URLs. The probe did not submit state tokens, click a later page, inspect undisclosed POST bodies, or prove a dated chronological search. Keyword-specific paging alone cannot enumerate all articles.

## Date-integrity anomaly and repair

The one-shot parser reported two `2026-10-08` **listing date hints**, for Theory and Practice and Events and Comments. The visible top article publication dates on the public first pages were older at observation, while the publisher displayed an October 8 running clock. This raises a **site-clock contamination risk**, not proof of an October 8 article publication. Do not use these hints as release dates.

The strictly offline repair in the accompanying change to `vn_journal_listing.py` refuses any date inherited through an ancestor containing the publisher's known live-clock element `#subTopMenu-time`. A local timestamp in an actual article row remains eligible as a provisional hint; no hint becomes an independently article-verified date. The synthetic tests cover both paths. This is a conservative parser improvement, **not a re-run or live validation** of October 8 pages, and does not establish that all other date hints are sound.

## Durable evidence and permission boundary

The [metadata-only artifact 11529266512](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37729004599/artifacts/11529266512) (ZIP SHA-256 `179fb7110283fff73d95072d5cab8d5c1aa0ae5c3a8213d842a15907bc7ca62c`, expires **2026-10-22 UTC**) includes bounded response digests, per-page totals, ID-set hashes, provisional hint extrema, and structural link/form categories. **No publisher HTML, article prose, headlines, PDFs, images, postback tokens, or individual article ID lists** were retained.

A historical backfill could only be considered after identifying and verifying a genuinely supported, permitted, repeatable, date-bounded enumeration interface. Do **not** infer such a route from JavaScript state, fabricate GET query parameters, brute-force numeric article IDs, or treat keyword-specific results as an exhaustive feed. Future forward-window reliability would need its own separately authorized shadow observation cadence and missed-item audit, not the ministry MPS/MOIT clock.

See [historical-coverage investigation #154](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/154) for evidence context, and [source-use and retention rights #155](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/155) for the **still open** permission decision. Working parsers or public accessibility do not authorize permanent article-text retention or republication.

**No activation, full-text capture, inferred legal approval, production database/output change, or scheduled workflow results from this report.**
