# China Mil Watch — Claude Operating Rules

Independent Mandarin-source monitoring and analysis publication. Two layers,
one masthead: the **Daily Brief** (automated record from `pla_watch.db`) and
**The PLA Watch** (weekly human-controlled analytical brief). Never "OSINT
tool" or intelligence cosplay.

## Session start
1. Read `PROJECT_STATE.md` (current state, known issues, next tasks).
2. For architecture / "where do I edit" questions: `graphify-out/GRAPH_REPORT.md`
   first, targeted `rg` second, file reads third. No broad repo scans.
3. Before design, editorial, pipeline, or agent work, read the governing doc:

| Doc | Governs |
|---|---|
| `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` | mission, audiences, page anatomy, evidence-vs-inference rules |
| `docs/DESIGN_SYSTEM.md` | dual-surface tokens, typography, color, a11y + performance budgets |
| `docs/VISUAL_AND_MOTION_SYSTEM.md` | motion rules, flagship visual specs, image policy, metadata fields |
| `docs/ARCHITECTURE_AND_PUBLISHING.md` | layer map, source vs generated, CI, commit strategy |
| `docs/AGENT_WORKFLOWS.md` | model routing, skills, agents, Ruflo/Headroom limits |
| `docs/ROADMAP.md` | releases and implementation tickets |
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
- Do not commit, push, deploy, publish, or regenerate output unless
  explicitly asked. CI deploys what is committed on main.
- `base.html`, `pla-watch-base.html`, `scripts/pw_env.py` are single-owner
  files — no concurrent agent edits.

## Commands
```bash
.venv/bin/python scripts/validate_output.py                 # deploy gate — run before/after output changes
.venv/bin/python scripts/rerender_pla_watch.py --no-covers  # weekly pages from sidecars
.venv/bin/python site/generator.py                          # daily site from DB
```
Preview: Browser-pane server `pla-watch-site` (port 8765, serves `output/`).
Full-page visual review: Playwright in `.venv` at 1280 + 375 (in-app
screenshots go stale after scrolling).
Baseline: validator passes with 9 historical warnings; explain any new one.

## Design north star (details in docs/DESIGN_SYSTEM.md)
A living editorial intelligence publication — Paper Ledger (light, daily
record) + Night Desk (dark, weekly analysis), Source Serif 4 / Inter /
IBM Plex Mono, one crimson signal family reserved for analytical meaning.
No SaaS/dashboard/terminal aesthetics; no box shadows; mono never in prose;
motion is reveal-based, reduced-motion-safe, transform/opacity only.

## Model routing (details in docs/AGENT_WORKFLOWS.md)
Fable: direction, design judgment, cross-route architecture, final review.
Sonnet: ticket implementation, generators, fixes, re-renders, QA.
Haiku: inventory, link checks, log summarization.
Ruflo only for genuine parallelism (max 4 agents); Headroom only for long
logs — never authoritative for Chinese text or claims.

## Working style
Token-efficient by default: smallest safe change; no full-file pastes; no
unrequested refactors; summarize long outputs; report files changed + what
changed + how to check. After meaningful work update `PROJECT_STATE.md`;
after structural changes run `graphify update .`; record constraining
rulings in `DECISION_LOG.md`.
