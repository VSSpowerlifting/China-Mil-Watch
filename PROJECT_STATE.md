# PROJECT_STATE — China Mil Watch / The PLA Watch

Updated: 2026-07-10

## Identity

- **China Mil Watch** — independent Mandarin-source monitoring and analysis
  project tracking Chinese military and security reporting from official and
  authoritative PRC sources. Daily monitoring layer (index, archive, signals).
- **The PLA Watch** — the weekly analytical brief. Vol. I, numbered editions,
  week ending Saturday, published Sunday.
- Public role title: **Principal Analyst** (normalized everywhere 2026-07-09;
  older "Founder & Principal Analyst" strings removed from scripts and sidecars).

## Architecture (what produces what)

| Layer | Source | Output |
|---|---|---|
| Daily pipeline | `pipeline.py` (scrape → analyze → DB) | `pla_watch.db` |
| Daily site | `site/generator.py` + `site/templates/{index,archive,article,signals,methodology}.html` | `output/*.html`, `output/data/articles.json` |
| Weekly edition | `scripts/generate_pla_watch.py` (Claude API, structured tool output) | `output/the-pla-watch/posts/{date}.{json,html}`, `the-pla-watch/linkedin/{date}.txt` |
| Re-render (no API) | `scripts/rerender_pla_watch.py` | posts/index/archive HTML from sidecar JSON |
| Deploy gate | `scripts/validate_output.py` (CI: `deploy_output_only.yml`, `daily_update.yml`; Python 3.9) | blocks deploy on error |

Sidecar JSON in `output/the-pla-watch/posts/` is the canonical record of each
edition: metadata, source trail, **and full body text** (backfilled 2026-07-09;
`generate_pla_watch.py` now writes body fields at publish time).

## Publication state

9 editions, No. 1–9, weekly with **no cadence gaps**: 2026-05-09 (pilot,
2-day window) through 2026-07-04. Issue numbers are stored in sidecars and
validated (unique + chronological).

## Known gaps and irregularities (do not invent explanations)

- **LinkedIn .txt missing** for editions 2026-05-09, 2026-05-16, 2026-05-23.
  Analyst ruling (2026-07-10): `2026-05-10.txt` is most likely the pilot's
  post under its publish date. File left unrenamed; validator warns, does
  not block.
- **Early source trails have no per-item dates** (editions 1–3). Real
  limitation of early data; left missing, warned, never invented.
- **Editions 1–2 have no `is_significant` flags in trails.** Analyst ruling
  (2026-07-10): no significant articles arose those weeks; flags are correctly
  absent. Residual: sidecars/pages still display n_significant of 1 and 3
  (early pipeline auto-counts) — reconcile only if the analyst chooses.
- **2026-06-20 has no "Why It Matters" section**; analyst ruling
  (2026-07-10): leave as is.
- 2026-05-16 sidecar has no `edition_label`, so its pages show no edition badge.
- 2026-05-16 body text carries literal `<strong>` emphasis; rendered via the
  `inline_markup` whitelist filter (only `<strong>`/`<em>` pass; rest escaped).

## Commands

```bash
python3 scripts/validate_output.py            # deploy gate (stdlib-only)
python3 scripts/rerender_pla_watch.py --no-covers   # re-render weekly pages from sidecars
python3 scripts/backfill_sidecar_bodies.py --dry-run # one-time migration tool (idempotent)
python3 site/generator.py                     # daily site from DB
```

Validation currently: **passes, 9 warnings** (all historical items above).

## Guardrails

- Rerender refuses to overwrite a post whose sidecar lacks body text
  (`--allow-empty-body` to override deliberately).
- Both weekly renderers share `scripts/pw_env.py` (autoescape on, same filters).
- Never invent Chinese text, translations, titles, outlets, dates, units,
  ranks, or claims. Repetition alone is not novelty or escalation.
- Do not push/publish/deploy without explicit request; CI deploys on push.

## Recent changes

- 2026-07-10: source trail shows original Chinese headlines (title_zh from DB
  records, exact URL match, 100% coverage across all 9 editions); prev/next
  edition navigation on post pages. Note: a newly published edition's
  predecessor gains its "next" link on the next rerender run.
- 2026-07-09: sidecar body backfill + rerender guard + PLA Watch validation
  in the deploy gate; human-readable dates, issue numbers, dark-theme badges,
  identity copy on the landing page. See DECISION_LOG.md.
