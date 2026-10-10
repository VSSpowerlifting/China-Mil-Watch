# Public frontend visual enrichment — 9 October 2026

Site-wide implementation through IPR’s production renderer, reviewed in a working browser. [PR #314](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/314) is the review boundary. No merge or deployment was performed by this task. The timeline remains unpublished.

Branch: `codex/ipr-sitewide-enrichment-20261009`. Isolated worktree: `/Users/benjaminyang/.codex/worktrees/ca1c/pla-watch`. Initial base: `61eee2786cfd1aeffbca703e71b914594f58c65a`. Reconciled main: `0487bfc04` (including historical-shell PR #287). Final source/output head: `de6cecef4e3af3bf410e2b99a9b8038c94ca7ad9`; parallel test fixes from #316 were preserved, and newer main’s historical-shell consolidation was reconciled in merge `1e7f722f1`. The documentation commit follows it. The final delivery checkpoint records the exact PR head. Released comparison: `4dbf42c5ca778eb5c55a9134fc51cac4fdc16a4f`.

The original Briefs-only scope was superseded by the owner’s site-wide correction. The pilot [PR #296](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/296) was subsequently merged externally into main as `534f3b3f1`. A parallel daily update added 40 records. This branch was recreated from current main and carried forward only the enrichment source, then rendered the current 5,020-record corpus. Private editorial and operations changes on main are preserved. An initial comparison through main `4b787d218` found unrelated collection/analysis changes. Main subsequently advanced to `0487bfc04`, integrating #287’s owner-directed historical article shell. Its current IPR masthead, provenance, unchanged citations and existing images are preserved. Generated conflicts were resolved from main and the combined source was rerendered; a root-path link correction and reusable Brief edge treatment reach all 14 historical articles. An inherited low-contrast photo-credit color was corrected and measured. The supplied bundle’s README and verification receipt informed the exploration; its generated concept is not an implementation screenshot or an instruction to reproduce its HTML.

## Coverage and source ownership

| Public family | Production source / considered treatment | Review representatives |
|---|---|---|
| Homepage | `home.html`, shared base and enrichment CSS; unchanged fleet photograph, contour at the open edge, paper finder, distinct navy coast band and quiet methodology/footer transitions | Home, opening and full page |
| Records archive | Shared base/family CSS; paper controls, open ledger rows, full-width filter disclosure, clear pressed/disabled/focus feedback | Search, date/desk/trail filters, pagination, empty state, Back restoration |
| Individual records | Shared base/family CSS; right-margin artwork on wide openings, clean opaque evidence rail, restrained custody/citation controls | Paired-language record, original-only record, largest record |
| Briefs | Catalog pilot plus native `brief.html`; asymmetric flow in the catalog, local navy grain and edge contours in native openings, paper transition into clean longform | Catalog and all three native Briefs, with and without photographs |
| Country desks | Shared family CSS; varied edge composition rather than a copied analysis hero; map remains authoritative geographic data | China, Singapore, held US desk, research Vietnam desk; shared gate covers all five |
| Supporting pages | Shared family CSS; shallow desk/source openings and reserved margins on longform about/methodology; chart/table surfaces remain clean | About, methodology, coverage, sources, source profiles, corpus guide and corpus |
| Week indexes | Shared source/base, finished decoration with no script requirement | Largest week shard and paginated shard; all 114 stay script-free |
| Compatibility | Source redirect constants and readable compact inline styling; refresh/canonical and original destinations unchanged | `pla-watch.html`, signals redirect, article redirect; all 2,282 redirects checked |
| Historical collection | Newer main’s `historical-brief.html` uses the current IPR shell and reusable Brief artwork/material, retaining historical provenance and exact citations. Compatibility index/archive/terms keep `pla-watch-base.html`, compact decoration and exact local fonts. | Every one of the 14 articles, plus all three compatibility hubs |
| Shared shell | Base template, existing shell controller and family CSS; material masthead/footer, native disclosure semantics, stronger open/focus/press states | Desktop and mobile menus, skip link, footer identity |

Every non-redirect public route must link the appropriate owned enrichment stylesheet. The complete output contains 7,462 routes: 5,020 records, 2,281 article redirects, 114 week shards, 10 source pages, five country desks, three native Briefs, 17 historical pages and 12 root pages. Templates, not captured prototype HTML, determine production output.

The private timeline was rendered separately outside `output/`, reviewed with its existing controller and verified as noindex/no canonical. Its shared shell works, but the new decorative treatment is excluded. No public timeline route, navigation, feed, approval or editorial content was added.

## Visual and motion decisions

The system uses localized paper and navy materials, bounded inert terrain primitives and route-specific composition. It keeps the selected lowercase ipr derivatives and turquoise accent untouched. Instrument Serif, Inter and Source Serif 4 remain the modern typography; historical compatibility hubs and the rollback templates retain exact original Inter, IBM Plex Mono and Source Serif 4 delivery. Historical articles use the current typography required by newer main.

Desktop gets flowing margin geometry and differentiated section edges. Mobile gets smaller, quieter crops that preserve title space. Archive controls, maps, citations and record bodies stay crisp. No shadow-based card system, moving prose, cursor effect, sustained decorative loop or animation framework was added. The existing controller handles finite artwork entrance; menus and control feedback use brief transitions. New decorative entrance is 720ms, with 140–150ms control/disclosure feedback. Reduced motion, `.no-anim`, no JavaScript and script failure keep finished content and artwork usable. Print and forced colors remove decoration. Historical autonomous contour loops are stopped; its reading navigation remains functional.

Browser review found the strongest gains in the photo-led homepage, material finder, catalog’s asymmetry and native Brief openings. The record rail and map deliberately remain quieter. Initial contours crossed too much type; final placements reserve margins. The final tile reads as uncoated paper, without visible seams in the reviewed captures. Historical article prose/citations remain exact through newer main’s shell consolidation; its current type and wrapping are preserved. Compatibility typography remains faithful after font localization. Existing low-resolution historical photography is unchanged and is not presented as improved documentary evidence.

The remaining visual weaknesses are modest: long no-photo Brief decks occupy much of a mobile opening, and the longest record title remains tall. Supporting pages use subtler enrichment than the catalog. Keeping original copy and readable type is preferable to compressing those openings merely for a shorter screenshot. Wider design work should carry forward localized materials, route-specific terrain crops, opaque evidence surfaces and restrained feedback. It should avoid stronger all-page noise, repeated analysis heroes and loops.

Independent specialists handled bounded material/font preparation, engineering verification and read-only visual review; the primary agent alone owned shared renderer/templates/output. The archive disclosure/focus interaction scored 9/10 against the applied microinteraction framework, with moderate confidence; that score is specific to the reviewed flow, not a claim about the whole site.

## Asset and resource provenance

- Supplied generated 1,254² paper master: 2,600,875 bytes. The retained 256² indexed seamless paper tile is 14,086 bytes (99.46% smaller), with a navy derivative of the same size. Each decodes to 262,144 RGBA bytes. Mirrored seams and bounded placements avoid large compositing surfaces. Original generation prompt/model was not supplied; the receipt states that limitation.
- Two approximately 3 KB SVG derivatives preserve the original 12-path IPR contour geometry. They are abstract decoration, not geographic or evidentiary maps. `ASSET_RECEIPT.json` and `NAVY_RECEIPT.json` retain source hashes, builders and purpose.
- The existing authentic U.S. Navy / Nathan Burke fleet photograph, dated 23 November 2015 and attributed as public domain, keeps its original context label, source link and responsive derivatives. Native Brief photographs and credits are unchanged. No generated photograph or invented documentary scene was introduced.
- Historical fonts are 18 unchanged original WOFF2 files, 738,140 bytes when every subset is counted, plus a 4,971-byte local CSS kit. `site/assets/fonts/historical/RECEIPT.json` records ordinary official Google delivery URLs/hashes, exact subset assignments and three official OFL licenses. An offline preparation check reproduces the prepared files byte-for-byte. Forty-eight controlled original/local matching cases have identical widths, ascent and descent. This is a matching proof; separate browser receipts establish delivery.
- Font preparation used fontTools 4.60.2 and Brotli 1.2.0 in a temporary developer environment. Production needs no new runtime dependency. Historical cover PNGs are retained for compatibility/social use; the earlier legacy navigation probe requested none. The reconciled article shell’s existing context images and source credits are preserved and measured in the final delivery receipt. Existing reuse/quality limitations remain explicit.

Actually applied skills: installed Frontend Design and Microinteractions; Impeccable’s brand/polish guidance; 21st review guidance; Graphify for source-map refresh. Browser review used Chromium/Chrome, production Python/Jinja, Pillow and specialist agents. The supplied material was optimized rather than regenerated.

Researched resources included the official OpenAI frontend-builder guidance, [Motion performance](https://motion.dev/docs/performance) and animation documentation, Framer reduced-motion guidance, shadcn navigation, [21st](https://21st.dev/), UI Skills Finder and [React Bits](https://www.reactbits.dev/get-started/index), plus MDN masks/layout guidance. They informed bounded motion and composition; no third-party component or React runtime was copied. Figma and Sites were available but not needed for this renderer workflow. Mobbin’s paid access remained unavailable. An Impeccable bootstrap write was blocked in protected `.agents`; existing readable guidance was used and the guard was not bypassed. These optional resources did not block delivery.

## Delivery and preservation

The complete gate measures inline and linked CSS/scripts recursively, plus fonts, icons, CSS graphics/textures, image sources and all responsive variants. Missing local dependencies fail. Conservative asset totals include every declared variant, not merely the resources fetched at one viewport. Actual cold/cached browser receipts are separate and should not be confused with production CDN measurements. The unchanged archive index adds 740,765 bytes on the first search/filter request; it is deferred from arrival and is separate from the linked static-page budget.

| Representative | HTML + CSS bytes | Script bytes | Conservative graphic/font/image bytes | Complete local bytes |
|---|---:|---:|---:|---:|
| Home | 66,835 | 11,940 | 2,619,429 | 2,698,204 |
| Archive | 133,867 | 9,847 | 276,459 | 420,173 |
| Briefs catalog | 103,834 | 3,118 | 276,459 | 383,411 |
| Native maritime Brief | 77,800 | 5,322 | 1,244,950 | 1,328,072 |
| Desk map | 167,358 | 372 | 276,459 | 444,189 |
| China desk | 86,598 | 372 | 276,459 | 363,429 |
| About | 78,511 | 372 | 276,459 | 355,342 |
| Largest record, 476 | 118,767 | 5,322 | 276,459 | 400,548 |
| Week 2026-10-05 | 107,118 | 0 | 276,459 | 383,577 |
| the-pla-watch/index.html | 71,616 | 1,307 | 777,112 | 850,035 |
| the-pla-watch/posts/2026-08-01.html | 83,575 | 372 | 327,843 | 411,790 |

All 7,462 routes pass the unchanged governed limits: 120,000 HTML/CSS bytes for individual documents, 300,000 for designated hubs, 10,000 script bytes except the already governed 12,000 home allowance. Modern enrichment CSS is 8,278 bytes; the historical treatment is only 1,348 bytes. Before shell consolidation, historical font CSS arrived remotely at 20,612 decoded bytes and exposed the former largest issue’s delivery problem. The compatibility font kit is local; all reconciled modern historical articles and compatibility hubs fit the unchanged cap, with no external CSS/script dependencies. Home and archive scripts have little remaining headroom; new decoration adds no script payload.

Complete publication parity checks 7,462 routes, 280,237 links, 55,615 anchors and all redirects, with zero failures. Full-corpus integrity checks all 5,020 record bodies, titles, dates, citations, provenance fields and URLs; approved native relations retain exact stored URLs/backlinks. Database, Brief/timeline sidecars, historical JSON, corpus index and sitemap are unchanged against reconciled main. Output changes comprise regenerated HTML/assets only; no evidence or publication-copy changes.

## Verification and browser evidence

All 924 final browser cases pass with zero errors: 44 representatives at 375, 768 and 1440 widths, with default, no-JS, CSP script failure, reduced motion, no-animation, forced colors and print. The receipt retains 567 non-historical cases from the earlier 693-case checkpoint: Git proves their production HTML/assets unchanged. All 357 historical cases were rerun against reconciled main, covering every actual article and all three compatibility hubs. The earlier print-only rerun methodology remains in the superseded receipt rather than being presented as a fresh whole-site run.

The primary agent reviewed final mobile filters, custody, citation, dark-ground focus and map focus, then the reconciled historical desktop/mobile scenes and corrected photo-credit contrast. Final browser receipts and baseline comparisons are packaged with the captures. The separate reader-flow harness covers 75 cases at 320/375/768/1280/1440 plus 13 journeys: bilingual search, desk/trail/date filters, pagination/history, custody/citation copy, native Brief anchors/credits, menus, JPEG fallbacks, narrow freshness and private timeline navigation.

The final 27 focused checks pass after reconciling main (21.747 seconds); all 20 historical preservation/browser checks also pass (9.334 seconds), including readable photo-credit contrast, and the production validator retains exactly 10 governed historical warnings. Mandatory offline CI includes launched Chromium, the full offline suite, validator and an unchanged database/output assertion; the live exact-head PR check is authoritative. Draft PR runs that skipped checks are not test evidence. Earlier interrupted local broad runs are not claimed as complete green suites. Full CI on the integrated child head `859a65152` passed 5,272 tests with nine governed skips, but that is prerequisite evidence rather than proof of this final combined head. The earlier #314 run failed on missing locally owned font files in its browser fixture and compressed-PNG reproducibility assumptions. #316 repairs those fixtures and checks decoded artwork/provenance while retaining shipped asset hashes and fallback assertions; the final combined head must rerun the full gate.

Actual captures and machine receipts live in [the review directory](review/frontend-enrichment-2026-10-09/README.md). These are browser screenshots of production output, not the generated design concept. Baseline comparisons use both released SHA and the reconciled main tree. Full-page capture naturally scrolls the document to trigger real finite reveals and lazy images; it does not force content classes into a staged screenshot.

Limits: automated/visual review used Chromium and desktop Chrome on loopback, including emulated narrow widths; physical phones, Safari and Firefox were not tested. Loopback cold/cached totals establish resource selection, not deployed cache headers, CDN latency or production performance. No merge, deployment or public timeline publication was verified or performed.

## Engineering continuation checkpoint

The site-wide scope is covered through shared templates and all-route checks; the Briefs pilot is no longer the stop boundary. Future work can focus on field review in additional browser engines/devices, narrowly chosen mobile opening refinements and deliberately approved imagery. Editorial restructuring, collection/analysis changes and timeline publication remain outside this visual implementation. Review PR #314 and its exact-head checks; merging or deployment requires a separate owner action.

### Observed loopback request costs

These are 1440px cold request totals (navigation plus fetched resource bodies and headers), distinct from the conservative asset table above. Repeat navigation produced the same totals: this local server did not demonstrate caching. The released historical baseline uses the former shell and its Google requests were blocked; its partial total cannot establish a complete transfer saving. The fresh main article uses the current local-font shell and its total is comparable. Compatibility-index main still omits blocked remote fonts (66,109 bytes); candidate local-font delivery is 419,774 bytes. The separate final historical font probe allows Google requests, loads local font faces and observes no Google requests. Production CDN compression/cache behavior is unmeasured.

| Surface | Candidate transferred bytes | Current-main transferred bytes | Released transferred bytes |
|---|---:|---:|---:|
| Home | 432,405 | 388,073 | 388,328 |
| Archive | 267,791 | 241,145 | 242,490 |
| Catalog | 292,064 | 283,243 | 252,824 |
| Largest record | 276,030 | 249,530 | 249,530 |
| Largest historical issue, reconciled IPR shell | 330,046 | 288,913 | 162,511 (old shell; remote fonts omitted) |

## Wider frontend checkpoint

The expanded implementation covers every requested public family through shared source templates, including compatibility and historical routes. Retain the localized materials, reserved graphic margins, original photography and clean evidence rails. A subsequent refinement may shorten compositions around long unchanged mobile decks or replace inherited low-resolution historical context imagery after rights review. There is no pending Briefs-only integration or site-wide coverage gap. Cross-browser/physical-device checks and deployed delivery measurements remain explicitly unperformed. Review/merge and any deployment belong to the owner; no timeline publication or editorial restructuring is included.
