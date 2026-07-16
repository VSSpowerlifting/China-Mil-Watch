# PROJECT_STATE — China Mil Watch / The PLA Watch

Updated: 2026-07-17 (recovery/reconciliation + No. 10 publication). State
only — durable doctrine lives in CLAUDE.md and docs/ (see CLAUDE.md table).

## Working tree (as of this update)

Clean. The previously uncommitted 2026-07-12 production-completion pass,
2026-07-13 Signal Veil pass, and 2026-07-16 J-20 atmospheric pass (see
DECISION_LOG entries of those dates) were reconciled onto `origin/main`
and committed on branch `reconcile/unfinished-pla-watch-2026-07-16`
(DECISION_LOG 2026-07-17 records the recovery mechanics). Local-only
safety branch `rescue/unfinished-pla-watch-2026-07-16` preserves the raw
WIP snapshots and must not be pushed or treated as production history.
The old local `main` (`1f0917c`, patch-id-identical to remote `5e92dc4`)
was intentionally left untouched in `~/pla-watch`.

## Publication state

10 editions, No. 1–10, weekly without cadence gaps: 2026-05-09 (pilot,
2-day window) through 2026-07-11 ("Beijing's Public SLBM Test and What It
Was Designed to Do", Significant, 39 articles / 2 model-flagged, Jin-class
SSBN veil). Issue numbers stored in sidecars, validated unique +
chronological. Next edition: No. 11, week ending 2026-07-18.

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

None. The 2026-07-11 analyst rulings resolved the then-open items;
"Model-flagged" stays the only reader-facing label for automated
classifications (all surfaces verified). Note: `executive_readout` /
`recurring_threads` adoption was deferred by analyst instruction — No. 10
shipped without them (DECISION_LOG 2026-07-17 §2); adopt from a later
edition when the analyst authors one.

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
