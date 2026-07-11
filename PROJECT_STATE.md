# PROJECT_STATE — China Mil Watch / The PLA Watch

Updated: 2026-07-11 (operating-system pass). State only — durable doctrine
lives in CLAUDE.md and docs/ (see the table in CLAUDE.md).

## Working tree (as of this update)

Substantial **uncommitted** work is present and must be preserved:
- 2026-07-11 frontend pass (source): Atom feed builder in
  `scripts/pw_env.py`; Terms page (`site/templates/pla-watch-terms.html`);
  Signals cross-promo; sitemap coverage; validator additions.
- 2026-07-11 visual refinement pass (source): animated editorial components
  from real data — homepage "How the record is built" plate (SVG draw-in,
  live-source dots), PLA Watch band edition tick strip, Signals 30-day
  daily-volume strip (`_daily_series`), Terms specimen plates with verbatim
  CJK ghost glyphs (`first_cjk`), source trail on an evidence spine, shared
  motion primitives in both base templates (no-JS/print/reduced-motion
  render finished artwork). QA'd via Playwright, 4 routes × 3 modes.
- Regenerated `output/` (~470 files) matching those source changes.
- 2026-07-11 operating-system pass: rewrote CLAUDE.md + this file; created
  `docs/{PRODUCT_AND_EDITORIAL_DOCTRINE,DESIGN_SYSTEM,
  VISUAL_AND_MOTION_SYSTEM,ARCHITECTURE_AND_PUBLISHING,AGENT_WORKFLOWS,
  ROADMAP}.md`; added `.claude/agents/` (3) and `.claude/commands/` (2);
  retired the inaccurate skillui design skills; aligned README/AGENTS.md/
  style_guide.md identity language; DESIGN_BACKLOG.md superseded by
  docs/ROADMAP.md.

Commit sequence **approved 2026-07-11** (DECISION_LOG; ARCHITECTURE_AND_
PUBLISHING §5): docs/OS commit → frontend source (templates/scripts) commit
→ regenerated output commit → validation/cleanup fixes where needed.
Nothing staged or committed until the analyst approves the staged plan.

## Publication state

9 editions, No. 1–9, weekly without cadence gaps: 2026-05-09 (pilot, 2-day
window) through 2026-07-04. Issue numbers stored in sidecars, validated
unique + chronological. Next edition: No. 10, week ending 2026-07-11.

## Validation status

`validate_output.py`: **passes, 9 warnings** — all historical, ruled on
2026-07-09/10 (missing LinkedIn files eds. 1–3; undated early trail
entries; related notes). Do not fix by invention; explain any NEW warning
here.

## Known issues / gaps (recorded, not explained away)

- `output/archive.html` is 804 KB flat list (446 articles) — ROADMAP T1.
- Cover PNGs ~8.2 MB total; photo-overlay covers duplicate titles — ROADMAP
  T2 (Edition Plate) + T4 (asset hygiene).
- Source coverage is effectively PLA Daily only; other outlets remain
  "configured / expanding" — visuals must show this honestly.
- 2026-05-16 sidecar lacks `edition_label` (no badge, by design); its body
  carries literal `<strong>` handled by the `inline_markup` whitelist.
- `pla_watch.db` committed to main by the daily workflow — revisit if it
  grows.
- No enforced review gate between weekly generation and publication;
  discipline is EDITORIAL_QA_CHECKLIST + validator.
- In-app Browser-pane screenshots go stale after scroll; use Playwright
  (in `.venv`) for full-page visual review at 1280 + 375.

## Outstanding decisions (analyst input needed)

None. The 2026-07-11 analyst rulings (DECISION_LOG, top entry) resolved all
open items: `executive_readout` adopted from No. 10 (manually authored,
never synthesized); `recurring_threads` adopted with controlled vocabulary
v1 (V&M §4, material relevance only); "Model-flagged" ratified as the only
reader-facing label for automated classifications (all surfaces verified);
commit sequence approved (split above).

## Next tasks

Sonnet tickets T1–T5 in docs/ROADMAP.md (archive month grouping; Edition
Plate v1; Signal Field v1; asset hygiene; executive readout). Fable reviews
rendered results of T2/T3 before regenerated output is committed.

## Recent completed work (compressed; details in DECISION_LOG.md)

- 2026-07-11: frontend pass (feed, Terms, Signals cross-promo, sitemap) and
  visual refinement pass (see Working tree above) — validation green, same
  9 historical warnings.
- 2026-07-10: identity language de-OSINT'd; "model-flagged" rename across
  all surfaces; methodology trust ladder; homepage latest-edition module;
  mobile header fix; focus-visible outlines.
- 2026-07-09: sidecar body backfill (sidecars canonical); shared Jinja env;
  issue numbering; date convention; print stylesheet; Chinese trail
  headlines; prev/next edition navigation.
