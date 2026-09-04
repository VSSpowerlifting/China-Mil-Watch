# Design System — Indo-Pacific Record / The PLA Watch

Durable doctrine. The Night Desk tokens below are the live values in
`site/templates/pla-watch-base.html`. The Paper Ledger table in §3 describes
`site/templates/base.html`, which is the **legacy rollback renderer** — the
live record site is rendered by `site/preview/generate_preview.py` and its
tokens are in `site/preview/styles.css`, a related but distinct teal/ocean
palette. That divergence is recorded in §3 rather than papered over. If a
template and this document disagree, reconcile deliberately — do not silently
fork.
Motion and flagship visual components: docs/VISUAL_AND_MOTION_SYSTEM.md.

## 1. North star

**A living editorial intelligence publication** — the published desk of a
working analyst. It combines the reading comfort and credibility of a serious
journal with the visual clarity of a well-made analytical briefing: source
streams, temporal change, annotated evidence, recurring themes — expressed
abstractly and editorially.

Never: SaaS landing page, crypto dashboard, fake classified terminal,
cyberpunk command center, generic Tailwind blog, floating-card AI template.
Never: classified stamps, redaction bars, radar screens, crosshairs, threat
meters, fake live feeds. The existing faint "PLA WATCH" watermark sits at the
threshold of intelligence cosplay — do not strengthen it.

## 2. Dual-surface identity (confirmed, keep)

Two expressions of one publication, distinguished by editorial function:

- **Paper Ledger (light)** — *the record*. Daily site: homepage, daily brief,
  archive, Signals, Methodology. A modern research journal: warm off-white,
  fine rules, structured density.
- **Night Desk (dark)** — *the analysis*. All `the-pla-watch/` routes:
  editions, PW index/archive, Terms. Focused and deliberate, not cinematic.

Shared DNA that makes them one publication: identical type stack, one crimson
signal family, mono micro-labels, 2px radius, the same ease curve and motion
primitives, the same footer honesty language. The homepage's dark
latest-edition band is the sanctioned crossover: Night Desk material embedded
in the Ledger. The inverse (light panels inside PW pages) is limited to print.

## 3. Color doctrine

### Paper Ledger tokens (`site/templates/base.html` — legacy rollback renderer)

**Not the live record site.** These are the predecessor's tokens, preserved
because the rollback path must still render as it did. The production record
surface is `site/preview/styles.css`, below.
| Token | Value | Role |
|---|---|---|
| `--paper` | #F6F3EC | page ground |
| `--paper-raised` | #FCFAF5 | cards, records, footer |
| `--paper-inset` | #EFEAE0 | recessed panels, tags |
| `--paper-header` | #FBF9F4 | masthead, nav rail |
| `--ink` | #1C2B3A | primary text; structural color; primary buttons |
| `--ink-2` | #4C4A44 | secondary text |
| `--ink-3` | #7B746A | muted text, captions, mono labels |
| `--line` / `--line-soft` | #CFC6B8 / #E2DBCE | rules |
| `--signal` | #A31626 | crimson signal (light surface) |
| `--signal-ink` | #7E0E1B | crimson hover/pressed |
| `--signal-tint` | #F5E7E4 | signal panel background (analyst readout) |
| `--signal-line` | #D9A9A3 | signal borders |

### Night Desk tokens (pla-watch-base.html)
| Token | Value | Role |
|---|---|---|
| `--color-bg` | #0E1520 | ink-navy page ground |
| `--color-bg-card` | #131C29 | lifted surface |
| `--color-bg-header` | #0A1019 | masthead |
| `--color-bg-sidebar` | #18222F | sidebar surface |
| `--color-text-primary` | #EDE9E0 | warm off-white (never pure white) |
| `--color-text-secondary` | #A8A29A | mid warm gray |
| `--color-text-muted` | #746E67 | quiet gray |
| `--color-border` / `-soft` | #273040 / #1C2534 | dark rules |
| `--color-brand` | #B3132B | crimson (dark surface) |
| `--color-brand-light` | #D8354C | links on dark (contrast-lifted) |
| `--signal-bright` | #E05A6D | focus outlines, flagged badges on dark |

The crimson differs by surface on purpose (#A31626 on paper, #B3132B/#D8354C
on navy) — same family, tuned for contrast. Do not unify them numerically.

### Live record-site tokens (`site/preview/styles.css`)
| Token | Value | Role |
|---|---|---|
| `--paper` | #F5F8F6 | page ground |
| `--ink` | #10252E | body text, dark bands (14.81 on paper) |
| `--deep` | #123E4A | secondary text (10.83) |
| `--ocean` | #176B87 | sole structural accent (5.63) |
| `--turquoise` | #28B8A6 | decoration on paper; text on ink |
| `--seaglass` | #CBEAE5 | fills, rules, marks — never text |
| `--signal` | #9C4B36 | rust: machine-generated ONLY (5.65) |
| `--abyss` | #0A1A22 | masthead ground, `theme-color` |
| `--parchment` | #EDE9E0 | primary text on dark |
| `--crimson` | (dark chrome only) | editorial accent, never on paper |

### Meaning rules
- **Crimson = analytical signal only**: model-flagged markers, key-judgment
  emphasis, active nav, eyebrow dashes, the PW brand rule, primary CTAs on
  dark. Never decorative fills, never large backgrounds (the signal-tint
  readout panel is the ceiling), never body text.
- **Evidence is neutral**: source-trail records, quotes, stats render in
  ink/gray. Inference and analyst emphasis may use crimson. This is the
  visual half of the evidence-vs-inference doctrine.
- The muted category-tag palette in base.html (Taiwan terracotta, SCS/ECS
  slate blue, Exercises olive, etc.) is the only sanctioned polychrome; keep
  those chips small and low-saturation.
- Badges: significant (crimson-tinted), routine (neutral outline), pilot
  (amber) — defined once in pla-watch-base.html, reused everywhere.

## 4. Typography doctrine

Stack (both surfaces, Google Fonts, weights capped):
- `--serif` **Source Serif 4** (optical sizing on) — publication identity,
  display and article headlines, deks on PW, long-form body on PW posts and
  Methodology, footer names. Italic serif is reserved for identity moments
  (hero emphasis line, "The" in the PW nameplate) and quotations.
- `--sans` **Inter** — UI: nav, buttons, deks on the daily site, card
  summaries, article body on daily records, footer links.
- `--mono` **IBM Plex Mono** — metadata only: eyebrows/labels (`.label-caps`,
  0.62–0.7rem, letter-spaced, uppercase), timestamps, stats labels, issue
  numerals, masthead kickers, citations. **Cap: mono never exceeds one line
  of content; never headings, never body prose.** This is the guard against
  terminal aesthetics.
- `--zh` PingFang SC / Hiragino Sans GB / Noto Sans CJK SC — all Chinese
  text, always wrapped `lang="zh-Hans"`, never italicized, never letter-
  spaced, minimum 0.8rem rendered size. Chinese headlines in trails render
  under their English titles at secondary color.

Reading rules:
- Long-form measure ~700px (existing PW post body), line-height ~1.7–1.8.
- Base 16px; body drops to 0.9375rem below 900px — keep.
- Headline scale is responsive per template (hero ~3rem desktop → ~1.9rem
  mobile); no fixed global scale, but keep serif display weight 700 with
  tightened letter-spacing (−0.01 to −0.015em) and line-height ≤ 1.15.
- No more than ~4 type sizes per viewport region.

## 5. Grid, spacing, structure

- Shell widths: Ledger `--shell: 1180px`; Night Desk `--shell: 1100px`;
  long-form reading column ~700px inside the PW post grid.
- Page gutters: 2rem desktop → 1.25rem ≤900px → 1rem ≤600px.
- Layouts are asymmetric two-column (main + sidebar) on homepage, daily
  brief, PW index, PW post. **Avoid three-equal-card rows**; the only
  sanctioned card grid is the Signals "how to read this site" 2×2.
- Rules (1px `--line`) do the structural work; radius is 2px everywhere;
  **no box-shadows** except the hairline under the sticky nav rail; flat
  elevation via surface shifts.
- Sticky elements: Ledger nav rail (top), PW reading-progress rail. Nothing
  else sticks.

## 6. Components (inventory of the live system)

Defined in base templates or per-page `extra_styles`; reuse before inventing:

- **Masthead/nameplate** — Ledger: logo + serif wordmark + mono kicker +
  right plate; Night Desk: italic serif nameplate + crimson top rule + mono
  masthead-rule row (Vol. I · issue).
- **Nav rail** (Ledger) / **pw-nav** (Night Desk) — uppercase, crimson
  underline scaleX on hover/active; PW link tinted crimson in Ledger nav.
- **Section rule / eyebrow** (`.section-rule`, `.brief-eyebrow`,
  `.mod-heading`) — mono caps with 18px crimson dash; the standard section
  opener on both surfaces.
- **Analyst readout** — signal-tinted panel, WHAT MATTERED / WHAT WAS
  ROUTINE / WHAT TO WATCH rows. The daily site's only crimson panel.
- **Record card** (`.article-card`) — tags, English title, verbatim 中文
  title, summary, source footer with original link.
- **Ledger stats** (`.hero-ledger`, sidebar stat rows) — mono label +
  tabular numeral rows separated by rules. Not "stat cards."
- **Edition badges** (`.pw-badge--significant/routine/pilot`).
- **Source trail record** — numbered, flagged marker, English + Chinese
  titles, outlet, date, URL.
- **Term plate** — dark card, CJK backdrop motif via `first_cjk` (verbatim
  glyphs only, never invented), term + pinyin + translation + explanation.
- **Citation copy** (`.cite-copy`) on PW posts.
- **Prev/next edition nav**; **progress rail** (CSS scroll-timeline).
- **Signal Field plate** (homepage "How the record is built") and **dark
  edition band** — flagship visuals, spec'd in VISUAL_AND_MOTION_SYSTEM.

## 6a. Identity assets (added 2026-09-04)

One canonical mark, several derivatives, documented in full in
`site/assets/identity/IDENTITY_ASSETS.md` and built by
`scripts/build_identity_assets.py`.

- **Canonical:** `ipr-compass-logo.png` — owner-supplied, PNG 500 × 500, RGB,
  no alpha, SHA-256 `7e3f3b60…45762f`. Never redrawn, recoloured, cropped or
  stretched. Never served directly.
- **Measured floor: 48 CSS px.** The canonical artwork's two outer rings are
  4 px strokes with an 11 px gap on a 500 px field. Below 48 px the rings merge
  into a grey halo and the mark stops reading as a compass. Masthead is 56 px
  desktop, 48 px compact; a test enforces the floor.
- **Simplified derivative:** `ipr-compass-mark-small.svg` covers favicon sizes
  (16/24/32 px) with one ring, filled points, no ticks. It is a derivative,
  never a replacement, and never presented as the mark at display size.
- **The brand gradient appears in exactly one place** — inside the mark itself.
  The accent budget still forbids gradients as decoration anywhere else.
- `logo-icon.png`, `logo-wordmark.png`, `og-image.png` and `favicon.svg` are
  **retired**: the predecessor's eagle, its wordmark, and a screenshot of its
  homepage. They remain in `output/` only because pages not yet re-rendered
  reference them. They are not current identity assets.

## 7. Accessibility standards (permanent)

- Semantic landmarks (`header/nav/main/footer`), one h1 per page, ordered
  headings; sections labeled via aria where headings are visual-only.
- `:focus-visible` outlines: 2px signal (light) / signal-bright (dark) —
  already implemented; never remove.
- Keyboard: all interactive elements reachable; disclosure controls real
  `<button>`/`<details>`; no click-only divs.
- Contrast: body text ≥ 4.5:1 on both surfaces (warm off-white on #0E1520
  passes; #746E67 muted text is for non-essential metadata only).
- Reduced motion: global `prefers-reduced-motion` kill-switch + `.no-anim`
  JS gate + no-JS renders finished state. Every new animation must satisfy
  all three paths (pattern exists in both base templates).
- Chinese text: `lang="zh-Hans"` mandatory (screen readers + font stack).
- SVG plates: `role="img"` + `<title>/<desc>` or `aria-label`; decorative
  SVG `aria-hidden="true"`. Data shown in a plate must also exist as text.
- Touch targets ≥ 40px on mobile nav/buttons; no horizontal scroll at 375px
  (regression-check every change; verified clean 2026-07-09).
- Print: PW posts print as light single-column brief with full URLs — keep
  the print token remap in pla-watch-base.html working.

## 8. Performance budgets

**Measured 2026-09-02 on the production tree.** These replace the 2026-07-11
figures, which described the predecessor's static site:
index 15.6 KB, `archive.html` 15.9 KB, coverage 17.3 KB, desks 13.3 KB,
methodology 9.7 KB, largest generated week page 29.9 KB, largest record page
64.7 KB, PLA Watch post 81.2 KB — all HTML with CSS inlined. JS ≈ 1 KB vanilla
(IntersectionObserver); zero external libraries. **Fonts differ by surface:**
The PLA Watch loads the three families from Google Fonts; the record site
loads none at all and renders on its fallback stack (Georgia / system-ui /
system mono). Unifying them is an open owner decision, deliberately not taken
in the identity tranche.
Covers remain ~8.5 MB total (~430 KB average) and are the one budget still
missed.

**`archive.html` is no longer a defect.** The 804 KB flat all-records page that
retired roadmap ticket T1 was written against no longer exists: the record
archive is now a compact index of 18 weeks linking out to 85 generated
`week-*.html` surfaces, paginated within a week where needed. Do not carry the
old figure forward.

Budgets for all future work:
- HTML+inline CSS per page ≤ 120 KB; ≤ 300 KB for any index or archive
  surface. Re-open archive navigation only if a measurement crosses those.
- Client JS ≤ 10 KB per page, vanilla only; no frameworks, no chart libs,
  no canvas unless a spec explicitly justifies it.
- Images: explicit width/height (no CLS), `loading="lazy"` below fold,
  cover thumbs ≤ 60 KB, full covers ≤ 250 KB, og-image PNG ≤ 300 KB.
- Fonts: current three families, weights already capped — do not add more.
- Animation: transform/opacity only (no layout properties); one ambient
  animation per page maximum.
- No client-side rendering of primary content; the site must read fully
  with JS disabled.
