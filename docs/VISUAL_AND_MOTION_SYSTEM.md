# Visual & Motion System — China Mil Watch

Durable specification for motion and the flagship visual components.
Tokens/typography: docs/DESIGN_SYSTEM.md. Tickets: docs/ROADMAP.md.

## 1. Motion doctrine

Motion communicates hierarchy, state change, connection, and progression —
never spectacle. The infrastructure already exists in both base templates;
new work must reuse it, not reinvent it.

### Existing primitives (reuse these)
- **Reveal-on-scroll**: `[data-reveal]` + IntersectionObserver (one-shot,
  rootMargin −8%), opacity 0→1 + translateY 14px→0, 0.65s `--ease`
  (cubic-bezier(0.16,1,0.3,1)), stagger via `--ri` × 70ms.
- **Draw-path**: `.draw-path` SVG strokes (pathLength=1), dashoffset 1→0,
  1.0–1.1s, stagger `--pi` × 90ms.
- **Ink node**: `.ink-node` scale 0→1, 0.5s, stagger `--ni`, capped delay.
- **Rule wipe**: eyebrow/section-rule `::before` scaleX 0→1, 0.7s.
- **Bar fill**: `.cat-bar-fill`/`.snap-bar-fill` scaleX, 0.8–0.9s.
- **Ambient pulse**: `.pulse-dot` opacity 3.4s loop — the only infinite
  animation; one instance per page maximum.
- **Progress rail** (PW posts): CSS `animation-timeline: scroll()`, no JS.

### Categories and budgets
| Category | Duration | Where |
|---|---|---|
| Micro-interaction | 140–200ms | links, nav underlines, buttons, copy-citation, disclosure |
| Editorial transition | 500–900ms | section reveals, band entries, bar fills |
| Analytical motion | ≤1.1s + stagger | draw-path lines, node highlighting, plate assembly |
| Ambient | ≥3s loop, subtle | signal dots in the Signal Field / dark band only |

### Hard rules
- Transform/opacity only; zero layout shift; content never waits on motion
  (start states only under `.js` inside un-revealed containers, so no-JS,
  print, and reduced-motion render the finished artwork — keep this exact
  pattern for every new component).
- Every page must satisfy three fallback paths: no-JS, `.no-anim`,
  `prefers-reduced-motion` (global kill-switch exists).
- Prohibited: bouncing, floating cards, glow, cursor-following, radar
  sweeps, animated backgrounds, entrance animations >1.2s, per-paragraph
  animation, autoplaying video, parallax.
- Prefer CSS/SVG. JS only for IntersectionObserver gating and interactions
  that provide analytical value (e.g., node highlighting).

## 2. Image & asset policy

| Class | Use | Rules |
|---|---|---|
| Original editorial graphics (SVG plates) | flagship visuals, edition plates | abstract, generated from real repo data; must read as editorial, not evidentiary |
| Data-derived visualizations | Signals dashboard, snapshot bars | only fields the pipeline reliably produces; label gaps honestly |
| Source photographs | inside editions as context | verbatim from the cited article; credit + "visual context only; not evidence" note (mandatory, existing norm); no misleading crops |
| Maps | none currently | only with rights-cleared bases + honest generalization; no fake operational maps |
| Generated abstract imagery | backgrounds of plates | never depicting real events as documentary; no imitation photography |
| Stock imagery | — | banned |

All images: accurate attribution, explicit width/height, meaningful alt
(or `alt=""` + aria-hidden when decorative), lazy-load below fold, budgets
per DESIGN_SYSTEM §8.

## 3. Flagship visual systems

### 3.1 Signal Field (homepage) — evolve the existing plate

**Purpose.** Communicate the method in one glance: official Mandarin sources
→ daily record → weekly analysis. It explains identity; it must not imply
live surveillance or quantitative precision.

**Placement.** Homepage, directly under the hero (replaces/upgrades the
current "How the record is built" strip in `site/templates/index.html`).

**Data.** From `site/generator.py` at build time: configured outlets with
per-outlet 30-day collected-article counts from the DB (`pla_daily` real;
others render in a visibly quieter "configured / expanding" state — never
fake activity), plus latest-edition metadata from the newest sidecar.

**Structure.** One inline SVG plate (viewBox ~1100×260 desktop): left column
of outlet labels (mono caps; active outlets carry a small count, dormant ones
the expanding label at muted color); curved connector lines converging on a
central "Daily record" node (serif label + today's date); one heavier line
continuing right to "The PLA Watch" node rendered as a small Night Desk
swatch (navy fill, warm text). A one-line mono caption below states the
honest claim: "N official PRC outlets monitored · the daily record is the
evidence; the weekly brief is the analysis."

**Motion.** On reveal: rule wipe on the section eyebrow; draw-path connectors
(stagger `--pi`); ink-node pops for the two nodes; a single pulse-dot on the
active outlet marker. Reduced-motion/no-JS: finished plate.

**Layout.** Desktop: full-shell-width plate. Mobile (≤700px): SVG swaps to a
vertical variant (sources stacked above record above brief) or falls back to
the existing stacked-list treatment — no horizontal scroll, no tiny text
(<11px rendered labels forbidden).

**Accessibility.** `role="img"` + `<title>/<desc>` naming the outlets and
flow; counts duplicated in visually-hidden text or the caption.

**Acceptance.** Plate renders from real DB counts at generation time; dormant
sources visually distinct; all three motion fallbacks; lighthouse CLS 0;
no JS beyond the existing observer.
**Prohibited shortcuts.** Hardcoded counts; invented activity for dormant
outlets; canvas; an animation library.

### 3.2 Edition Plate — replaces photo-cover identity

**Purpose.** A generatable visual identity per edition, so editions are
recognizable without weekly manual artwork. The current photo+title-overlay
cover PNGs duplicate the headline and read like social cards; they are
demoted to og:image duty (regenerate style later) while in-page identity
becomes the plate. Source photos stay inside editions as captioned context
figures.

**Placement.** PW index latest-edition card, PW archive entries (thumb
position), PW post hero (compact variant), homepage dark band (mini variant).

**Data.** Entirely from the edition sidecar: issue_number, week_ending,
edition_type, title theme line(s), n_articles, source_trail length +
per-item is_significant, distinct sources, `first_cjk(term_to_know_term)`
motif.

**Structure.** Deterministic inline SVG (rendered by a Jinja macro shared by
both weekly renderers via `scripts/pw_env.py` context): ink-navy field
(#0E1520) with a 4px crimson top rule; oversized issue numeral (serif,
tabular) anchored left; mono week-ending date; a tick row — one tick per
trail record, crimson when flagged, warm-gray otherwise (honest density: 13
records = 13 ticks); the CJK motif glyphs at low opacity (≤6%) as backdrop,
only when the term begins with CJK (existing `first_cjk` contract, returns
'' rather than inventing). Edition badge color-codes type. No photography.

**Motion.** Static in lists. On the PW post hero only: tick row may bar-fill
on reveal. Nothing infinite.

**Layout.** Aspect 16:9 (list/archive), 21:9 compact (post hero), 4:3 mini
(homepage band). SVG scales; text sizes fixed in viewBox units so
proportions hold.

**Accessibility.** `role="img"`, aria-label "Edition No. 9, week ending 4
July 2026, 13 source records, 1 model-flagged." All plate data also exists
as adjacent text.

**Acceptance.** Same sidecar in → identical SVG out (deterministic);
renders for all 9 editions including the label-less 2026-05-16 (fallbacks:
missing edition_label → no badge; no CJK term → no motif); validator passes;
archive page weight drops (SVG replaces PNG thumbs).
**Prohibited shortcuts.** Raster generation for in-page use; invented
themes/glyphs; per-edition hand-tuning.

### 3.3 Continuity Strip (edition-to-edition) — phased

**Purpose.** Serve the returning reader (journey #5): where does this
edition sit in the run, and what recurs.

**Phase 1 (buildable now).** A horizontal strip on PW post pages (above
prev/next) and the PW archive header: one tick per published edition from
the sidecar set — position = chronology, height/color = edition_type,
current edition highlighted, each tick a link. Data: the already-loaded
sidecar list. This generalizes the homepage band's existing "1…9" ticks into
a shared component.

**Phase 2 (requires new metadata; do not fake).** Thread lines connecting
editions that share a recurring analytical thread (e.g., Scarborough Shoal
across Nos. 8–9), driven by an optional sidecar field (see §4). Until the
field exists, render Phase 1 only.

**Motion.** Draw-path on reveal for the strip rule; current-edition tick
gets the ink-node pop. **Accessibility.** `<nav aria-label="All editions">`
list semantics under the hood; ticks are real links with focus states.
**Acceptance.** Strip renders identically from generate and rerender paths;
keyboard navigable; degrades to a plain link list without CSS.

### Deferred candidates (do not build yet)
Term relationship cards; annotated regional plates; evidence stacks;
edition-comparison modules; archive chronology bands. Revisit after
Releases 1–3 (ROADMAP).

## 4. Structured-content requirements

Available now (edition sidecars): date, week_ending/start, title, dek,
signal, n_articles, n_significant, days_covered, edition_type/label,
source_trail[{title, url, source, date, is_significant, title_zh}],
issue_number, body sections (opening_note, what_stood_out, why_it_matters,
what_was_routine, what_im_watching_next), term_to_know_{term,explanation},
author fields, media_items, cover paths.
Available now (daily DB via generator): per-article categories (14 labels),
source slugs, dates, model flags, title_original (中文).

**Adopted** optional, backward-compatible sidecar fields (decision
2026-07-11; missing field → feature silently absent; validator treats
presence as optional, malformed as warning):

| Field | Type | Purpose | Used by |
|---|---|---|---|
| `executive_readout` | list[str], 2–4 bullets, **manually authored by the analyst at publish** — never synthesized automatically, from any source | "If you read nothing else" block under the hero | Roadmap T5; adopted from Edition No. 10 |
| `recurring_threads` | list[str] slugs from the controlled vocabulary below | Continuity Strip Phase 2; Signals recurrence | §3.3 |

Proposed, not yet adopted:

| Field | Type | Purpose | Status |
|---|---|---|---|
| `regions` | list[str] fixed vocabulary | regional emphasis on plates | deferred |

### `recurring_threads` controlled vocabulary (v1, 2026-07-11)

Grounded in threads that have actually recurred across Editions 1–9:

| Slug | Thread |
|---|---|
| `scarborough-shoal` | Huangyan Island patrols and framing |
| `taiwan-strait` | cross-strait operations and messaging |
| `ccg-maritime-friction` | Coast Guard operations and statements |
| `carrier-operations` | Liaoning / Fujian / far-seas strike-group activity (远海训练) |
| `rocket-force-readiness` | Rocket Force training, manning, discipline |
| `political-rectification` | loyalty campaigns, 思想整风, cadre discipline |
| `training-reform` | combat realism, 训战脱节, system-of-systems training |
| `senior-cadre-oversight` | CMC directives on senior officers, verdicts |
| `unmanned-systems` | drones, loitering munitions, counter-UAS |
| `military-diplomacy` | port calls, foreign engagement, forum framing |

Governance: assign a slug only when the edition **materially analyzes** the
thread (a standing section engages it) — never for a passing mention.
Typical count 0–3 per edition; an edition with none carries no field.
Adding a slug requires a DECISION_LOG entry. Historical backfill only by
re-reading the published edition text, never from memory.

Never add fields whose values the pipeline cannot reliably produce or the
analyst does not deliberately write. No schema migration of historical
sidecars: absence is the documented state for old editions.
