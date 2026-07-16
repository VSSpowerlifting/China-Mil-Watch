# PROJECT_STATE — China Mil Watch / The PLA Watch

Updated: 2026-07-16 (J-20 homepage atmospheric swap). State only —
durable doctrine lives in CLAUDE.md and docs/ (see the table in CLAUDE.md).

## Working tree (as of this update)

**Uncommitted 2026-07-16 J-20 homepage atmospheric pass** (DECISION_LOG
top entry; preserve with the earlier uncommitted passes below):
- New manifest entry `chengdu-j20` (emperornie, Flickr via Commons,
  CC BY-SA 2.0, license-verified through fetch_editorial_image.py) with
  the new explicit `"placement": "homepage-atmosphere"` field + duo-paper
  derivative. Homepage veil now selects only by that field
  (`_select_home_atmosphere` in site/generator.py); the model-flagged
  signal card stays on `_select_home_editorial` (SLBM article, unchanged)
  and the two never couple. Jin-class entry unchanged (card + article
  figure); its veil no longer renders on the homepage.
- index.html: veil/bracket/inline credit read `home_atmosphere`;
  homepage-only desktop crop (118% + mask_focus 10% 8%), mobile reset
  (cover, 62% 42%); paper whisper behind .hero-signal.
- Output regenerated (idempotent; only index.html + new assets changed);
  validator green at the 9 historical warnings; editorial regression tests
  pass; QA evidence + checks in `tmp/j20-homepage-swap-2026-07-16/qa/`
  (all programmatic checks passed, incl. J-20/SLBM separation assertions).
- The 3D-model / Assembly Plate / Blueprint Resolve / Remotion /
  commissioned-model explorations are closed (superseded by this
  direction); their tmp/ dirs remain untouched and gitignored.

The 2026-07-11 work (frontend/visual passes, operating-system docs) was
committed and pushed through `0154b0f`; HEAD matched origin/main at session
start. The actual GitHub remote is ahead by daily-workflow data commits
(live shows "Updated 2026-07-11"; local DB runs through 2026-07-10) —
expected drift, same frontend generation.

**Uncommitted 2026-07-12 production-completion pass** (preserve; commit
sequence at the bottom of this section):
- First-paint fix: above-fold content no longer starts at opacity 0;
  `data-reveal="art"` variant + hardened observer JS in both base
  templates; per-page static hero/identity blocks; homepage brief-date
  h1→h2. (DECISION_LOG 2026-07-12 §1, §6.)
- Editorial image system: `site/assets/editorial/` manifest + 4 rights-
  cleared pilot assets (license-verified via Commons API); shared loaders
  in `scripts/pw_env.py`; homepage lead-signal figure, daily-article lead
  figures, weekly render-time Visual Context merge; fetch tool
  `scripts/fetch_editorial_image.py`. (DECISION_LOG §2, §3.)
- Daily summary prompt sharpened (`analysis/prompts.py`); offline editorial
  regression set in `tests/` (fixtures from 8 archived articles + lint +
  contract tests; run `python3 tests/test_editorial_regression.py`).
- Analyst Readout rebuilt for no-flag days: names the top-ranked item with
  its mechanical basis, single-source coverage clause, per-category
  falsifiable watch indicators.
- Weekly prompts: PROSE MECHANICS + SYNTHESIS blocks in STYLE_EXTRACT,
  sharpened tool-schema descriptions, non-blocking `prose_warnings()` at
  draft time (DECISION_LOG §5).
- Regenerated `output/` (daily + weekly) matching those source changes;
  validator green at the 9 historical warnings; idempotency verified.
- QA artifacts in `tmp/qa-2026-07-12/` (not for commit).

**Uncommitted 2026-07-13 Signal Veil pass** (production visual system —
DECISION_LOG "Production visual system: Source-Derived Signal Graphics"):
- Concept A Signal Veil live on all four image surfaces: homepage hero,
  daily-article header band (Paper Ledger, paper duotone), weekly post
  hero + PW index latest-edition module (Night Desk, navy duotone).
  Concept C dither = Paper Ledger fallback via optional manifest
  `treatment` field (in use: plan-destroyer-xian). Conventional figures
  retired everywhere (`lead-figure`, `hero-figure`, `issue-cover-thumb`,
  in-page `cover-figure`, archive `entry-thumb`); cover PNGs are
  og:image-only with an in-page attribution note.
- Provenance: red analyst bracket + stacked mono metadata on desktop,
  compact inline credit on mobile; every placement links the source page
  and carries "context, not evidence."
- Night Desk tick row (post hero + index module): one tick per source-trail
  record, red = model-flagged, labeled "part of the monitored weekly
  record · of N articles analyzed"; ticks hide ≤480px (text remains).
- Deterministic derivatives: `scripts/generate_editorial_derivatives.py`
  (Pillow) → `site/assets/editorial/derivatives/` (4 files, only required
  treatments), copied to output at build; helpers + safe fallbacks in
  `scripts/pw_env.py`; missing manifest/asset/derivative → text-led layout.
- Byline reverted to "Principal Analyst, China Mil Watch" in both weekly
  renderers (DECISION_LOG 2026-07-12 §4 corrected).
- Mobile nav fits at 390/375 (compact spacing ≤480px; scroll-fade ≤350px);
  post h1 drops the redundant "The PLA Watch:" prefix (display-only).
- `validate_output.py` extended: derivative existence, rendered-reference
  resolution, credit links, aria-labels, exact manifest association,
  retired-figure patterns. Validator: 0 errors, the same 9 historical
  warnings; double-regeneration byte-identical; pilot images byte-identical.
- QA artifacts in `tmp/qa-2026-07-13/` (not for commit). Known follow-up:
  Signals category bars use crimson decoratively (pre-existing; flagged
  by the 2026-07-13 read-only critic; separate task).

Recommended commit sequence (per ARCHITECTURE_AND_PUBLISHING §5):
frontend source/templates/scripts + validation → editorial prompts/tests →
image assets + manifest → regenerated output.

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
- Homepage image-load-failure path: the `.src-bracket` credit still renders
  even when the `.pl-veil`/derivative fails to load, so the attribution
  bracket can appear with no image behind it. Accepted as a deferred minor
  issue 2026-07-16 (analyst-approved); pre-existing behavior of the Signal
  Veil system, not introduced by the J-20 swap. Not fixed by invention.
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
