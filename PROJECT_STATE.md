# PROJECT_STATE — China Mil Watch / The PLA Watch

Updated: 2026-07-09

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
  A `the-pla-watch/linkedin/2026-05-10.txt` exists — dated one day after the
  05-09 pilot; relationship unconfirmed. Validator warns, does not block.
- **Early source trails have no per-item dates** (editions 1–3). Real
  limitation of early data; left missing, warned, never invented.
- **Editions 1–2 have no `is_significant` flags in trails** although
  n_significant is 1 and 3. Warned; needs human review to mark, if desired.
- **2026-06-20 has no "Why It Matters" section** in its published HTML/sidecar;
  the other 8 editions have all sections. Structural inconsistency, unexplained.
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

## Recent changes (2026-07-09)

Workflow: sidecar body backfill + rerender guard + PLA Watch validation in the
deploy gate. UI: human-readable week-ending dates, issue numbers, dark-theme
edition badges, identity copy on the PLA Watch landing page. See DECISION_LOG.md.
