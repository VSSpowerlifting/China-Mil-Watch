# Actual production browser review

These are Chromium 147.0.7727.15 captures of the implemented production renderer output, not generated concepts. Desktop is 1440px, tablet 768px and mobile 375px. Source/output head: `6a18744e0289792f174eb1cfc20730d53e396fc4`. Screens remain identical after the parallel test-only #316 fixes.

693 cases pass: 33 representatives × three widths × seven profiles. See [BROWSER_QA.json](BROWSER_QA.json) for cases, 40 flow entries, resource requests, private timeline review and exact rerun/retention methodology. The separate [READER_QA.json](READER_QA.json) holds 75 additional cases and 13 interaction journeys.

Full captures naturally scroll to trigger real reveals and lazy images. Baseline captures compare current main `61eee2786` and released `4dbf42c5`. Matrix requests block Google fonts; the separate candidate font probe permits network requests and confirms actual local faces with no Google requests. Historical baseline transfer totals therefore omit blocked remote fonts and cannot establish a complete baseline delivery saving. Cold/repeat loopback requests returned the same bytes; this server did not demonstrate CDN caching.

| Route | Desktop | Mobile | Tablet |
|---|---|---|---|
| `index.html` | [desktop](home-desktop.png) | [mobile](home-mobile.png) | [tablet](home-tablet.png) |
| `archive.html` | [desktop](archive-desktop.png) | [mobile](archive-mobile.png) | [tablet](archive-tablet.png) |
| `analysis.html` | [desktop](catalog-desktop.png) | [mobile](catalog-mobile.png) | [tablet](catalog-tablet.png) |
| `desks.html` | [desktop](desks-map-desktop.png) | [mobile](desks-map-mobile.png) | [tablet](desks-map-tablet.png) |
| `china.html` | [desktop](desk-china-desktop.png) | [mobile](desk-china-mobile.png) | [tablet](desk-china-tablet.png) |
| `singapore.html` | [desktop](desk-singapore-desktop.png) | [mobile](desk-singapore-mobile.png) | [tablet](desk-singapore-tablet.png) |
| `us-indopacific.html` | [desktop](desk-held-desktop.png) | [mobile](desk-held-mobile.png) | [tablet](desk-held-tablet.png) |
| `vietnam.html` | [desktop](desk-research-desktop.png) | [mobile](desk-research-mobile.png) | [tablet](desk-research-tablet.png) |
| `about.html` | [desktop](about-desktop.png) | [mobile](about-mobile.png) | [tablet](about-tablet.png) |
| `methodology.html` | [desktop](methodology-desktop.png) | [mobile](methodology-mobile.png) | [tablet](methodology-tablet.png) |
| `coverage.html` | [desktop](coverage-desktop.png) | [mobile](coverage-mobile.png) | [tablet](coverage-tablet.png) |
| `sources.html` | [desktop](sources-desktop.png) | [mobile](sources-mobile.png) | [tablet](sources-tablet.png) |
| `corpus-guide.html` | [desktop](corpus-guide-desktop.png) | [mobile](corpus-guide-mobile.png) | [tablet](corpus-guide-tablet.png) |
| `corpus.html` | [desktop](corpus-desktop.png) | [mobile](corpus-mobile.png) | [tablet](corpus-tablet.png) |
| `pla-watch.html` | [desktop](compatibility-bridge-desktop.png) | [mobile](compatibility-bridge-mobile.png) | [tablet](compatibility-bridge-tablet.png) |
| `record/3924.html` | [desktop](record-paired-desktop.png) | [mobile](record-paired-mobile.png) | [tablet](record-paired-tablet.png) |
| `record/476.html` | [desktop](record-largest-desktop.png) | [mobile](record-largest-mobile.png) | [tablet](record-largest-tablet.png) |
| `record/3537.html` | [desktop](record-original-only-desktop.png) | [mobile](record-original-only-mobile.png) | [tablet](record-original-only-tablet.png) |
| `briefs/maritime-cooperation-2026.html` | [desktop](brief-maritime-cooperation-2026-desktop.png) | [mobile](brief-maritime-cooperation-2026-mobile.png) | [tablet](brief-maritime-cooperation-2026-tablet.png) |
| `briefs/trident-resolve-regional-scale-specific-chinese-tasks.html` | [desktop](brief-trident-resolve-regional-scale-specific-chinese-tasks-desktop.png) | [mobile](brief-trident-resolve-regional-scale-specific-chinese-tasks-mobile.png) | [tablet](brief-trident-resolve-regional-scale-specific-chinese-tasks-tablet.png) |
| `briefs/xiangshan-security-frames-defense-ties.html` | [desktop](brief-xiangshan-security-frames-defense-ties-desktop.png) | [mobile](brief-xiangshan-security-frames-defense-ties-mobile.png) | [tablet](brief-xiangshan-security-frames-defense-ties-tablet.png) |
| `source/pla_daily.html` | [desktop](source-live-desktop.png) | [mobile](source-live-mobile.png) | [tablet](source-live-tablet.png) |
| `source/jp_mod_news_ja.html` | [desktop](source-shadow-desktop.png) | [mobile](source-shadow-mobile.png) | [tablet](source-shadow-tablet.png) |
| `week-2026-07-27.html` | [desktop](week-desktop.png) | [mobile](week-mobile.png) | [tablet](week-tablet.png) |
| `week-2026-05-04-2.html` | [desktop](week-pagination-desktop.png) | [mobile](week-pagination-mobile.png) | [tablet](week-pagination-tablet.png) |
| `the-pla-watch/posts/2026-05-09.html` | [desktop](historical-oldest-desktop.png) | [mobile](historical-oldest-mobile.png) | [tablet](historical-oldest-tablet.png) |
| `the-pla-watch/posts/2026-08-01.html` | [desktop](historical-largest-desktop.png) | [mobile](historical-largest-mobile.png) | [tablet](historical-largest-tablet.png) |
| `the-pla-watch/posts/2026-08-15.html` | [desktop](historical-latest-desktop.png) | [mobile](historical-latest-mobile.png) | [tablet](historical-latest-tablet.png) |
| `the-pla-watch/index.html` | [desktop](historical-index-desktop.png) | [mobile](historical-index-mobile.png) | [tablet](historical-index-tablet.png) |
| `the-pla-watch/archive.html` | [desktop](historical-archive-desktop.png) | [mobile](historical-archive-mobile.png) | [tablet](historical-archive-tablet.png) |
| `the-pla-watch/terms.html` | [desktop](historical-terms-desktop.png) | [mobile](historical-terms-mobile.png) | [tablet](historical-terms-tablet.png) |

## Full documents

- home: [desktop](home-desktop-full.jpg), [mobile](home-mobile-full.jpg)
- archive: [desktop](archive-desktop-full.jpg), [mobile](archive-mobile-full.jpg)
- catalog: [desktop](catalog-desktop-full.jpg), [mobile](catalog-mobile-full.jpg)
- desks-map: [desktop](desks-map-desktop-full.jpg), [mobile](desks-map-mobile-full.jpg)
- brief-maritime-cooperation-2026: [desktop](brief-maritime-cooperation-2026-desktop-full.jpg), [mobile](brief-maritime-cooperation-2026-mobile-full.jpg)
- historical-largest: [desktop](historical-largest-desktop-full.jpg), [mobile](historical-largest-mobile-full.jpg)

## Interaction and baseline captures

- [archive-expanded-filters-1440](archive-expanded-filters-1440.png)
- [archive-expanded-filters-375](archive-expanded-filters-375.png)
- [archive-expanded-filters-768](archive-expanded-filters-768.png)
- [current-main-archive-desktop](current-main-archive-desktop.png)
- [current-main-archive-mobile](current-main-archive-mobile.png)
- [current-main-archive-tablet](current-main-archive-tablet.png)
- [current-main-catalog-desktop](current-main-catalog-desktop.png)
- [current-main-catalog-mobile](current-main-catalog-mobile.png)
- [current-main-catalog-tablet](current-main-catalog-tablet.png)
- [current-main-historical-largest-desktop](current-main-historical-largest-desktop.png)
- [current-main-historical-largest-mobile](current-main-historical-largest-mobile.png)
- [current-main-historical-largest-tablet](current-main-historical-largest-tablet.png)
- [current-main-home-desktop](current-main-home-desktop.png)
- [current-main-home-mobile](current-main-home-mobile.png)
- [current-main-home-tablet](current-main-home-tablet.png)
- [current-main-record-largest-desktop](current-main-record-largest-desktop.png)
- [current-main-record-largest-mobile](current-main-record-largest-mobile.png)
- [current-main-record-largest-tablet](current-main-record-largest-tablet.png)
- [desks-map-focus-mobile](desks-map-focus-mobile.png)
- [historical-citation-mobile](historical-citation-mobile.png)
- [home-coast-focus-1440](home-coast-focus-1440.png)
- [home-coast-focus-375](home-coast-focus-375.png)
- [home-coast-focus-768](home-coast-focus-768.png)
- [home-hero-focus-1440](home-hero-focus-1440.png)
- [home-hero-focus-375](home-hero-focus-375.png)
- [home-hero-focus-768](home-hero-focus-768.png)
- [home-menu-focus-1440](home-menu-focus-1440.png)
- [home-menu-focus-375](home-menu-focus-375.png)
- [home-menu-focus-768](home-menu-focus-768.png)
- [private-timeline-desktop](private-timeline-desktop.png)
- [record-citation-mobile](record-citation-mobile.png)
- [record-history-mobile](record-history-mobile.png)
- [released-archive-desktop](released-archive-desktop.png)
- [released-archive-mobile](released-archive-mobile.png)
- [released-archive-tablet](released-archive-tablet.png)
- [released-catalog-desktop](released-catalog-desktop.png)
- [released-catalog-mobile](released-catalog-mobile.png)
- [released-catalog-tablet](released-catalog-tablet.png)
- [released-historical-largest-desktop](released-historical-largest-desktop.png)
- [released-historical-largest-mobile](released-historical-largest-mobile.png)
- [released-historical-largest-tablet](released-historical-largest-tablet.png)
- [released-home-desktop](released-home-desktop.png)
- [released-home-mobile](released-home-mobile.png)
- [released-home-tablet](released-home-tablet.png)
- [released-record-largest-desktop](released-record-largest-desktop.png)
- [released-record-largest-mobile](released-record-largest-mobile.png)
- [released-record-largest-tablet](released-record-largest-tablet.png)

## Review verdict

The homepage gains depth from the unchanged credited fleet image meeting the tactile finder; the catalog and native Briefs carry the strongest flowing compositions. Desktop margin contours remain quiet beside evidence. Mobile controls have visible focus, readable expanded filters and citation/custody layouts. Tables and prose stay on clean grounds. The material seams are unobtrusive in reviewed captures. Long no-photo Brief decks and the largest record heading remain tall; supporting pages are deliberately subtler. Historical low-resolution photographs and inherited citation styling remain unchanged.

Print overflow in native Brief coverage and the corpus-guide dictionary was found and corrected; all final print cases pass. No new sustained animation was introduced. Reduced motion/no-JS/CSP/forced-colors profiles retain finished usable content. Private timeline checks do not publish it.

Cross-browser Safari/Firefox, physical touch devices and production CDN caching were not measured. Receipts and complete conservative all-route budgets are supplied separately.
