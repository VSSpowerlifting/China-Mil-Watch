# DESIGN_BACKLOG — The PLA Watch / China Mil Watch

Prioritized. Preserve the navy/crimson editorial-brief identity; no generic
SaaS blocks, no intelligence cosplay. Done items move to the bottom.

## P1 — high value, low risk

1. **Executive-summary block on issue pages.** "This week's signal" exists,
   but a 3-bullet "If you read nothing else" readout under the hero would
   serve policy readers. Needs a new sidecar field — content must be written
   or approved by the analyst, not synthesized at render time from old issues.
2. **Prev/next edition links on post pages.** `post-nav` only links archive +
   home. Sidecars know the sequence; add No. N−1 / N+1 links for reader flow.
3. **Source trail: original Chinese titles.** Trail shows English titles only.
   The daily DB stores `title_original`; carrying it into future sidecars
   (`title_zh`) and rendering it as a secondary line would let readers verify
   against the original Mandarin without clicking through. Backfill for old
   editions only where the URL matches a DB record exactly — never retranslate.
4. **Archive year/month grouping.** At 9 editions a flat list works; past ~20
   it needs month headers. Low effort, do when count warrants.

## P2 — moderate value

5. **Signals page and daily index cross-promotion of latest PLA Watch
   edition** (daily templates currently link only in nav/footer).
6. **Print/PDF stylesheet for issue pages** — policy readers forward PDFs.
7. **Term-to-know archive page** — terms accumulate one per week and are
   currently buried in back issues.
8. **RSS/Atom feed for The PLA Watch** — natural for the audience; needs a
   small generator addition plus validation.

## P3 — polish

9. Cover PNG typography: regenerate historical covers with the current
   template for visual consistency in the archive thumbs (needs
   `--force-covers` run + eyeball pass; PNGs are committed artifacts).
10. `sources_seen` in the hero meta can wrap awkwardly on mid widths with
    3 long source names; consider truncating to count + tooltip-style list.
11. Consider `prefers-color-scheme: light` handling for outbound link
    previews (site is committed dark; only if reader feedback asks).

## Done (2026-07-09)

- Human-readable week-ending dates in all reader-facing labels.
- Issue numbers (Vol. I · No. N) across masthead, hero, archive, sidebar.
- Dark-theme edition badges (significant / routine / pilot) shared in base
  template; removed light-theme chips.
- Identity paragraph on the PLA Watch landing page (independent,
  Mandarin-source, official PRC sources).
- Author title normalized to Principal Analyst.
