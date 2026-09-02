# Indo-Pacific Record — Claude Operating Rules

Independent, source-grounded monitoring and analysis of official Indo-Pacific
defense and security publication. Two layers under one masthead: the **record**
(automated preservation and rendering from `pla_watch.db`) and **The PLA
Watch** (the China Desk's human-controlled weekly analytical series). Never
"OSINT tool," never intelligence cosplay.

"China Mil Watch" is a **legacy name**: the predecessor identity, retired
2026-08-27. Use it only when describing history.

## Session start
1. Read `PROJECT_STATE.md` (current state, debt, immediate priorities).
2. For architecture / "where do I edit" questions: `graphify-out/GRAPH_REPORT.md`
   first, targeted `rg` second, file reads third. No broad repo scans.
3. Before design, editorial, pipeline, or agent work, read the governing doc:

| Doc | Governs |
|---|---|
| `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` | identity, audiences, page anatomy, evidence-vs-inference rules |
| `docs/ARCHITECTURE_AND_PUBLISHING.md` | layer map, source vs generated, commands, CI, commit strategy |
| `docs/AGENT_WORKFLOWS.md` | model routing, skills, agents, parallelism limits |
| `docs/ROADMAP.md` | current priority order |
| `docs/DESIGN_SYSTEM.md` | dual-surface tokens, typography, color, a11y + performance budgets |
| `docs/VISUAL_AND_MOTION_SYSTEM.md` | motion rules, flagship visual specs, image policy, metadata fields |
| `docs/SHADOW_COLLECTION.md` / `docs/SHADOW_REVIEW.md` | shadow desk isolation; human checkpoint reviews |
| `DECISION_LOG.md` / `EDITORIAL_QA_CHECKLIST.md` | standing rulings; weekly publish gate |

## Hard rules
- Work only inside `~/pla-watch`. Never touch sibling repos.
- **Never hand-edit `output/`** — it is generated. Fix templates/scripts/
  sidecars and re-render. Sidecar JSON (`output/the-pla-watch/posts/*.json`)
  is the canonical edition record — no casual edits, ever.
- Never invent Chinese text, translations, titles, outlets, dates, units,
  ranks, or claims. Historical gaps stay recorded as warnings, not fixed.
- Public label is "model-flagged," never "significant" (see DECISION_LOG).
- `executive_readout` is analyst-authored only — never synthesize it.
  `recurring_threads` slugs only from the V&M §4 vocabulary, only for
  threads the edition materially analyzes.
- Never defeat a source's access challenge, impersonate a browser, or route
  around `robots.txt`. An institution must be able to recognise this collector
  and refuse it.
- No shadow desk is promoted automatically, and none may be described as
  qualified. Promotion needs 30 consecutive collecting days, completed human
  checkpoint reviews, and owner sign-off in `DECISION_LOG.md`.
- Do not commit, push, deploy, publish, or regenerate output unless
  explicitly asked. CI deploys what is committed on main.
- `base.html`, `pla-watch-base.html`, `scripts/pw_env.py` are single-owner
  files — no concurrent agent edits.

## Commands
```bash
.venv/bin/python scripts/validate_output.py                 # deploy gate — run before/after output changes
.venv/bin/python site/render.py                             # PRODUCTION renderer: daily site from the DB
.venv/bin/python scripts/rerender_pla_watch.py --no-covers  # weekly pages from sidecars
```
`site/render.py` is the only place a frontend is selected. `DEFAULT_SITE_MODE`
is `indo-pacific-record`; `site/generator.py` is the `legacy` renderer and is
the rollback path only — never call it as the production build.

Preview: Browser-pane server `pla-watch-site` (port 8765, serves `output/`).
Full-page visual review: Playwright in `.venv` at 1280 + 375 (in-app
screenshots go stale after scrolling).
Baseline: **validator passes with 10 governed warnings**; explain any new one
in `PROJECT_STATE.md` and never fix one by invention.

## Design north star (details in docs/DESIGN_SYSTEM.md)
A living editorial intelligence publication — Paper Ledger (light, the record)
+ Night Desk (dark, weekly analysis), Source Serif 4 / Inter / IBM Plex Mono,
one crimson signal family reserved for analytical meaning.
No SaaS/dashboard/terminal aesthetics; no box shadows; mono never in prose;
motion is reveal-based, reduced-motion-safe, transform/opacity only.

## Model routing (details in docs/AGENT_WORKFLOWS.md)
Fable: direction, design judgment, cross-route architecture, final review.
Sonnet: ticket implementation, generators, fixes, re-renders, QA.
Haiku: inventory, link checks, log summarization.
Parallel agents only for genuine parallelism (max 4); long-log compression
tools are never authoritative for Chinese text or claims.

## Working style
Token-efficient by default: smallest safe change; no full-file pastes; no
unrequested refactors; summarize long outputs; report files changed + what
changed + how to check. After meaningful work update `PROJECT_STATE.md` —
keep it a current snapshot, not a diary; after structural changes run
`graphify update .`; record constraining rulings in `DECISION_LOG.md`.
