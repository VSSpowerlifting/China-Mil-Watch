# Roadmap — China Mil Watch frontend & product

Authoritative forward plan (supersedes DESIGN_BACKLOG.md, 2026-07-11).
Pipeline-layer backlog (analyzer, scrapers, relevance filter) lives
separately in docs/v2_roadmap.md.
Completed work is recorded in PROJECT_STATE.md / DECISION_LOG.md, not here.
Specs referenced: docs/VISUAL_AND_MOTION_SYSTEM.md (V&M),
docs/DESIGN_SYSTEM.md (DS).

## Release sequence

- **R1 — Foundation stabilization**: archive weight fix, asset optimization,
  README/public-copy alignment. (Tickets T1, T4)
- **R2 — Homepage & edition identity**: Signal Field v1, Edition Plate v1.
  (T2, T3)
- **R3 — PLA Watch reading depth**: executive readout, Continuity Strip
  Phase 1. (T5, then strip)
- **R4 — Discovery**: Signals recurrence + archive month grouping (both
  surfaces), edition comparison entry points. `recurring_threads` adopted
  2026-07-11 (vocabulary in V&M §4); data accrues as editions carry it.
- **R5 — Terms & institutional knowledge**: glossary categories,
  cross-edition term appearances, related entries — only from real sidecar
  data.

Deferred until archive depth or metadata exists: Relationship Plate beyond
the Signal Field (needs >1 active source to be honest), regional plates,
edition-comparison modules, cover-PNG regeneration in plate style (P3).

---

## First five Sonnet tickets

### T1 — Archive: month grouping + weight reduction
- **Objective:** `output/archive.html` is 804 KB / ~23,000px flat list of
  446 articles. Split into month sections with per-month archive pages
  (`archive/2026-06.html`…) and a compact index page listing months with
  counts + the current month inline. Keep client-side filters working
  within a month page.
- **Reader value:** archive becomes browsable (journeys #3, #5); page
  weight within budget (DS §8: ≤300 KB).
- **Files:** `site/generator.py` (new month-page emission + index),
  `site/templates/archive.html`, `scripts/validate_output.py` (check month
  pages exist for every month with data + links resolve), sitemap emission.
- **Risk:** medium — URL structure changes; keep `archive.html` as the
  index URL so inbound links survive. No DB or sidecar changes.
- **Acceptance:** every article reachable in ≤2 clicks from archive index;
  largest emitted archive page ≤300 KB; validator green; 375px no overflow.
- **Model/skills:** Sonnet; ui-ux-pro-max optional for the index layout.
  Ruflo: no.

### T2 — Edition Plate v1 (spec V&M §3.2)
- **Objective:** deterministic SVG edition plates from sidecar data via a
  shared Jinja macro in `site/templates/` (context from
  `scripts/pw_env.py`); replace cover-PNG thumbs on PW index latest-edition
  card, PW archive entries, and homepage dark band. PNG covers remain for
  og:image only. Source photos remain inside editions as captioned figures.
- **Files:** new `site/templates/_edition_plate.html` (macro),
  `pla-watch-index.html`, `pla-watch-archive.html`, `index.html` (band
  mini), `scripts/pw_env.py` (expose macro context), re-render.
- **Dependencies:** none — all fields exist in sidecars. Fallbacks per spec
  (no badge, no CJK motif) must render for eds. 1–3 and 2026-05-16.
- **Acceptance:** V&M §3.2 acceptance list; identical output from generate
  and rerender paths; validator green; PW archive page weight drops.
- **Model/skills:** Sonnet build → Fable/impeccable visual review before
  regeneration is committed. Ruflo: no.

### T3 — Signal Field v1 (spec V&M §3.1)
- **Objective:** upgrade the homepage "How the record is built" strip into
  the Signal Field SVG plate with real per-outlet 30-day counts from the DB,
  draw-path/ink-node reveal, honest dormant-source states, and the
  mobile vertical variant.
- **Files:** `site/generator.py` (outlet counts query + context),
  `site/templates/index.html` (plate markup/styles).
- **Acceptance:** V&M §3.1 acceptance list; counts match
  `data/articles.json` reality; a11y title/desc present; three motion
  fallbacks verified.
- **Model/skills:** Sonnet; Fable reviews the rendered plate. Ruflo: no.

### T4 — Image and asset hygiene pass
- **Objective:** meet DS §8 image budgets: recompress covers/thumbs
  (currently ~8.2 MB total), add explicit width/height and
  `loading="lazy"` where missing (edition figures, archive thumbs until T2
  lands), verify og-image sizes.
- **Files:** `scripts/generate_pla_watch_cover.py` (output size caps),
  a one-off recompression script in `scripts/`, templates where img tags
  lack dimensions. No visual redesign.
- **Acceptance:** thumbs ≤60 KB, covers ≤250 KB, no CLS from images
  (spot-check via Playwright), validator green, visual diff imperceptible.
- **Model/skills:** Sonnet or Haiku for inventory + Sonnet for changes.
  Ruflo: no.

### T5 — Executive readout block (DESIGN_BACKLOG P1 carried forward)
- **Objective:** render an optional `executive_readout` (2–4 analyst-written
  bullets) under the edition hero as an "If you read nothing else" block —
  render-if-present only; never synthesized from old editions.
- **Files:** `scripts/generate_pla_watch.py` (accept/write field at publish;
  prompt asks the analyst-reviewed draft to propose bullets clearly marked
  for human approval), `site/templates/pla-watch-post.html` (block +
  styles per DS: signal-tinted treatment ceiling applies),
  `scripts/validate_output.py` (optional-field validation: 2–4 items,
  strings), docs note in V&M §4 already present.
- **Dependencies:** none — field adopted starting Edition No. 10 (decision
  2026-07-11); manually authored only; historical editions render unchanged.
- **Acceptance:** absent field → page byte-identical except template
  comments; present field → block renders on desktop/mobile/print;
  validator green.
- **Model/skills:** Sonnet; editorial-integrity-reviewer confirms no
  auto-synthesis path exists. Ruflo: no.

---

## Ticket hygiene

Every future ticket must state: objective, reader value, affected routes,
files, dependencies, required metadata, model + skills, Ruflo yes/no,
complexity, risk, acceptance criteria, validation method. Tickets that
cannot fill the metadata row honestly (data doesn't exist) go to §Deferred,
not to implementation.
