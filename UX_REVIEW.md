# UX_REVIEW — The PLA Watch / China Mil Watch

Reviewed: 2026-07-09. Perspectives: ux-auditor, visual-designer,
mandarin-source-reviewer. Verified in browser at desktop (1280) and mobile
(375) widths against the re-rendered output.

## Reader journey

- **Entry → identity**: PLA Watch landing page now states in the first
  paragraph what the publication is, that it is independent, and that it
  monitors official PRC sources in the original Mandarin. Fixed 2026-07-09.
- **Landing → issue**: latest-edition card carries issue No., human date,
  edition badge, stats, cover thumb, and two clear actions ("Read this
  edition" / "All editions"). Good.
- **Issue → sources**: source trail links every item to the original
  81.cn/PRC URL with source name and (where recorded) date; significant items
  are flagged. Weakness: no Chinese titles displayed (DESIGN_BACKLOG P1-3).
- **Issue → next issue**: dead end — post-nav lacks prev/next edition links
  (DESIGN_BACKLOG P1-2).
- **Daily ↔ weekly**: sidebar "How it relates" card explains the two layers
  well; daily-site pages under-promote the weekly brief (P2-5).

## Consistency (fixed 2026-07-09)

- Week-ending labels were raw ISO (`2026-07-04`) in every reader-facing
  surface; now "4 July 2026" via shared `format_date`. ISO retained in
  tabular meta (covers range, snapshot) deliberately.
- Issue numbers now displayed and validated; previously absent entirely.
- Edition badges were three different light-theme chips pasted onto the dark
  theme (index amber, archive white/red, post amber); now one shared
  dark-theme set in `pla-watch-base.html`.
- Author title varied across editions ("Founder & Principal Analyst" vs
  "Principal Analyst"); normalized.

## Mobile (375px, verified)

- Masthead collapses correctly; tagline and rule hidden; nav readable.
- Post hero, byline, and stat rows wrap cleanly; snapshot grid 4→2 columns.
- Archive entries stack date-above-title; thumbs scale.
- No horizontal scroll observed on index, archive, or post pages.

## Typography and hierarchy

- Source Serif display + Inter meta is a strong, credible editorial pairing;
  drop cap on opening note is restrained; keep.
- Body measure ~700px, line-height 1.78 — comfortable.
- Watermark "PLA WATCH" at 4.5–5% opacity: at the threshold of intelligence
  cosplay but currently subtle enough; do not strengthen it.

## Source presentation (mandarin-source-reviewer)

- Chinese terms appear inline in titles where the source used them
  (e.g. 战备警巡, 体系练兵) — preserved verbatim from records; good.
- Trail titles are English translations only; original headline text should
  ride along in future sidecars (never re-derived after the fact) — P1-3.
- Cover credit notes state "visual context only; not evidence" — good norm,
  keep mandatory.
