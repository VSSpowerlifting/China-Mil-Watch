# DESIGN_BACKLOG — superseded

**Open items moved to `docs/ROADMAP.md` (2026-07-11).** Add new work there
using its ticket format. This file remains only as the done-item record for
the 2026-07-09 → 2026-07-11 design pushes.

Mapping of the last open items: executive-summary block → ROADMAP T5;
archive month grouping → T1 (daily) and R4 (weekly); cover-PNG regeneration
→ ROADMAP deferred (P3); `prefers-color-scheme` for outbound link previews
→ ROADMAP deferred (P3, only on reader feedback).

## Done

- 2026-07-11: Atom feed for The PLA Watch (`the-pla-watch/feed.xml`) —
  deterministic, sidecar-dated, written by both weekly renderers via shared
  `pw_env.build_atom_feed`; autodiscovery link in the weekly head; validated
  in the deploy gate (well-formed, one entry per edition).
- 2026-07-11: Terms-to-Know running glossary (`the-pla-watch/terms.html`) —
  verbatim reuse of each edition's published term, linked back to its
  edition; nav + footer links; deploy gate checks every term-bearing edition
  appears.
- 2026-07-11: Signals page cross-promotes the latest PLA Watch edition
  (dark band between sections A and B; generator passes `pw_latest`).
- 2026-07-11: sources_seen in the post hero truncates to a count (with
  title-attribute list) when >2 sources; full names stay in the snapshot.
- 2026-07-11: sitemap.xml now covers weekly edition pages, the PLA Watch
  archive, and the terms page.
- 2026-07-11: visual refinement pass — homepage pipeline plate, edition
  tick strip, Signals 30-day volume strip, Terms specimen plates, source
  trail evidence spine, shared motion primitives (see PROJECT_STATE).
- 2026-07-10: Print stylesheet — issue pages print as a light, single-column
  brief (chrome/sidebar/dark cover hidden, source-trail URLs printed in
  full, cards kept unbroken across pages).
- 2026-07-10: Prev/next edition links on post pages (issue No. + date).
- 2026-07-10: Original Chinese headlines in the source trail (`title_zh`
  backfilled from DB records by exact URL match; generator carries it
  forward automatically).
- Human-readable week-ending dates in all reader-facing labels.
- Issue numbers (Vol. I · No. N) across masthead, hero, archive, sidebar.
- Dark-theme edition badges (significant / routine / pilot) shared in base
  template; removed light-theme chips.
- Identity paragraph on the PLA Watch landing page (independent,
  Mandarin-source, official PRC sources).
- Author title normalized to Principal Analyst.
