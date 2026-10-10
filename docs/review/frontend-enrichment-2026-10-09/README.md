# Actual production browser review

Actual Chromium implementation captures, not generated concepts. Desktop 1440px, tablet 768px, mobile 375px. Final source/output head `de6cecef4e3af3bf410e2b99a9b8038c94ca7ad9`; reconciled main `0487bfc04`. Unchanged non-historical captures retain their earlier provenance.

[BROWSER_QA.json](BROWSER_QA.json) records 924 cases: 44 representatives × three widths × seven profiles, zero errors. It explicitly retains 567 unchanged non-historical cases and reruns 357 historical cases (all 14 articles + three compatibility hubs). [READER_QA.json](READER_QA.json) adds 75 cases / 13 journeys. Fresh all 7,462-route parity/delivery receipts accompany the matrix.

Newer main consolidated historical articles into the current IPR shell. Those final captures replace earlier historical chrome; [prior-historical-chrome](prior-historical-chrome/) and [PRE_CONSOLIDATION_BROWSER_QA.json](PRE_CONSOLIDATION_BROWSER_QA.json) are historical checkpoints, not final article captures. Released baseline remains 4dbf42c5; fresh historical main comparisons use 0487bfc04.

Full screenshots naturally scroll to trigger actual reveals and lazy images. Matrix blocks Google font requests; a separate network-enabled compatibility probe proves local historical faces and zero Google requests. Cold/repeat loopback totals do not establish production CDN caching.

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
| `the-pla-watch/posts/2026-05-09.html` | [desktop](historical-post-2026-05-09-desktop.png) | [mobile](historical-post-2026-05-09-mobile.png) | [tablet](historical-post-2026-05-09-tablet.png) |
| `the-pla-watch/posts/2026-05-16.html` | [desktop](historical-post-2026-05-16-desktop.png) | [mobile](historical-post-2026-05-16-mobile.png) | [tablet](historical-post-2026-05-16-tablet.png) |
| `the-pla-watch/posts/2026-05-23.html` | [desktop](historical-post-2026-05-23-desktop.png) | [mobile](historical-post-2026-05-23-mobile.png) | [tablet](historical-post-2026-05-23-tablet.png) |
| `the-pla-watch/posts/2026-05-30.html` | [desktop](historical-post-2026-05-30-desktop.png) | [mobile](historical-post-2026-05-30-mobile.png) | [tablet](historical-post-2026-05-30-tablet.png) |
| `the-pla-watch/posts/2026-06-06.html` | [desktop](historical-post-2026-06-06-desktop.png) | [mobile](historical-post-2026-06-06-mobile.png) | [tablet](historical-post-2026-06-06-tablet.png) |
| `the-pla-watch/posts/2026-06-13.html` | [desktop](historical-post-2026-06-13-desktop.png) | [mobile](historical-post-2026-06-13-mobile.png) | [tablet](historical-post-2026-06-13-tablet.png) |
| `the-pla-watch/posts/2026-06-20.html` | [desktop](historical-post-2026-06-20-desktop.png) | [mobile](historical-post-2026-06-20-mobile.png) | [tablet](historical-post-2026-06-20-tablet.png) |
| `the-pla-watch/posts/2026-06-27.html` | [desktop](historical-post-2026-06-27-desktop.png) | [mobile](historical-post-2026-06-27-mobile.png) | [tablet](historical-post-2026-06-27-tablet.png) |
| `the-pla-watch/posts/2026-07-04.html` | [desktop](historical-post-2026-07-04-desktop.png) | [mobile](historical-post-2026-07-04-mobile.png) | [tablet](historical-post-2026-07-04-tablet.png) |
| `the-pla-watch/posts/2026-07-11.html` | [desktop](historical-post-2026-07-11-desktop.png) | [mobile](historical-post-2026-07-11-mobile.png) | [tablet](historical-post-2026-07-11-tablet.png) |
| `the-pla-watch/posts/2026-07-18.html` | [desktop](historical-post-2026-07-18-desktop.png) | [mobile](historical-post-2026-07-18-mobile.png) | [tablet](historical-post-2026-07-18-tablet.png) |
| `the-pla-watch/posts/2026-08-01.html` | [desktop](historical-largest-desktop.png) | [mobile](historical-largest-mobile.png) | [tablet](historical-largest-tablet.png) |
| `the-pla-watch/posts/2026-08-08.html` | [desktop](historical-post-2026-08-08-desktop.png) | [mobile](historical-post-2026-08-08-mobile.png) | [tablet](historical-post-2026-08-08-tablet.png) |
| `the-pla-watch/posts/2026-08-15.html` | [desktop](historical-post-2026-08-15-desktop.png) | [mobile](historical-post-2026-08-15-mobile.png) | [tablet](historical-post-2026-08-15-tablet.png) |
| `the-pla-watch/index.html` | [desktop](historical-index-desktop.png) | [mobile](historical-index-mobile.png) | [tablet](historical-index-tablet.png) |
| `the-pla-watch/archive.html` | [desktop](historical-archive-desktop.png) | [mobile](historical-archive-mobile.png) | [tablet](historical-archive-tablet.png) |
| `the-pla-watch/terms.html` | [desktop](historical-terms-desktop.png) | [mobile](historical-terms-mobile.png) | [tablet](historical-terms-tablet.png) |

## Full documents and comparison states

- [archive-desktop-full](archive-desktop-full.jpg)
- [archive-expanded-filters-1440](archive-expanded-filters-1440.png)
- [archive-expanded-filters-375](archive-expanded-filters-375.png)
- [archive-expanded-filters-768](archive-expanded-filters-768.png)
- [archive-mobile-full](archive-mobile-full.jpg)
- [brief-maritime-cooperation-2026-desktop-full](brief-maritime-cooperation-2026-desktop-full.jpg)
- [brief-maritime-cooperation-2026-mobile-full](brief-maritime-cooperation-2026-mobile-full.jpg)
- [catalog-desktop-full](catalog-desktop-full.jpg)
- [catalog-mobile-full](catalog-mobile-full.jpg)
- [current-main-archive-desktop](current-main-archive-desktop.png)
- [current-main-archive-mobile](current-main-archive-mobile.png)
- [current-main-archive-tablet](current-main-archive-tablet.png)
- [current-main-catalog-desktop](current-main-catalog-desktop.png)
- [current-main-catalog-mobile](current-main-catalog-mobile.png)
- [current-main-catalog-tablet](current-main-catalog-tablet.png)
- [current-main-historical-largest-desktop-full](current-main-historical-largest-desktop-full.jpg)
- [current-main-historical-largest-desktop](current-main-historical-largest-desktop.png)
- [current-main-historical-largest-mobile-full](current-main-historical-largest-mobile-full.jpg)
- [current-main-historical-largest-mobile](current-main-historical-largest-mobile.png)
- [current-main-historical-largest-tablet](current-main-historical-largest-tablet.png)
- [current-main-historical-post-2026-05-09-desktop-full](current-main-historical-post-2026-05-09-desktop-full.jpg)
- [current-main-historical-post-2026-05-09-desktop](current-main-historical-post-2026-05-09-desktop.png)
- [current-main-historical-post-2026-05-09-mobile-full](current-main-historical-post-2026-05-09-mobile-full.jpg)
- [current-main-historical-post-2026-05-09-mobile](current-main-historical-post-2026-05-09-mobile.png)
- [current-main-historical-post-2026-05-09-tablet](current-main-historical-post-2026-05-09-tablet.png)
- [current-main-home-desktop](current-main-home-desktop.png)
- [current-main-home-mobile](current-main-home-mobile.png)
- [current-main-home-tablet](current-main-home-tablet.png)
- [current-main-record-largest-desktop](current-main-record-largest-desktop.png)
- [current-main-record-largest-mobile](current-main-record-largest-mobile.png)
- [current-main-record-largest-tablet](current-main-record-largest-tablet.png)
- [desks-map-desktop-full](desks-map-desktop-full.jpg)
- [desks-map-focus-mobile](desks-map-focus-mobile.png)
- [desks-map-mobile-full](desks-map-mobile-full.jpg)
- [historical-largest-desktop-full](historical-largest-desktop-full.jpg)
- [historical-largest-mobile-full](historical-largest-mobile-full.jpg)
- [historical-post-2026-05-09-desktop-full](historical-post-2026-05-09-desktop-full.jpg)
- [historical-post-2026-05-09-mobile-full](historical-post-2026-05-09-mobile-full.jpg)
- [home-coast-focus-1440](home-coast-focus-1440.png)
- [home-coast-focus-375](home-coast-focus-375.png)
- [home-coast-focus-768](home-coast-focus-768.png)
- [home-desktop-full](home-desktop-full.jpg)
- [home-hero-focus-1440](home-hero-focus-1440.png)
- [home-hero-focus-375](home-hero-focus-375.png)
- [home-hero-focus-768](home-hero-focus-768.png)
- [home-menu-focus-1440](home-menu-focus-1440.png)
- [home-menu-focus-375](home-menu-focus-375.png)
- [home-menu-focus-768](home-menu-focus-768.png)
- [home-mobile-full](home-mobile-full.jpg)
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

## Visual verdict

The strongest gains are the photograph-led home meeting its tactile finder, asymmetrical catalog and native/current-shell historical Brief openings. Mobile filters, record custody/citation and focus remain readable. Evidence rails, maps and longform stay clean; contours occupy bounded margins. Historical photo-credit text/links were visibly weak on navy and were corrected and measured at ≥4.5:1. Long unchanged decks remain tall and inherited low-resolution archival photos remain a limitation.

All final print cases pass after correcting coverage/dictionary overflow. No sustained decorative animation was added. Reduced-motion/no-JS/CSP/forced-color states retain usable content. The timeline is reviewed privately and remains unpublished. Safari/Firefox, physical touch devices and production CDN caching were not measured.
