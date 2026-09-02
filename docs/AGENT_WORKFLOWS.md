# Agent Workflows & Model Routing — Indo-Pacific Record

How future Claude sessions allocate models, skills, and agents, and the
constraints every agent works under. Durable.

## 0. Documentation hierarchy

An agent reads down this list and stops at the document that governs the change
it is making. Do not restate one document's content inside another.

| Document | Governs |
|---|---|
| `README.md` | public and contributor overview |
| `PROJECT_STATE.md` | current operational snapshot and immediate handoff |
| `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` | identity, editorial standard, provenance, publication principles |
| `docs/ARCHITECTURE_AND_PUBLISHING.md` | technical layer map, commands, publishing and deployment |
| `docs/AGENT_WORKFLOWS.md` (this file) | agent operating constraints and model routing |
| `docs/ROADMAP.md` | current priority order |
| `DECISION_LOG.md` | durable decisions that constrain future work |
| Git history | superseded state and incident history |

`PROJECT_STATE.md` is a **current snapshot, not a diary**. Update it in place
and let Git hold the previous version; do not append a new dated section for
every session.

## 1. Model routing

### Fable (or the strongest available tier)
Product direction, information architecture, design-system decisions,
flagship-visual design judgment, cross-route refactors, rendered-output
design review, tradeoff resolution, final integration review, roadmap
re-planning, edits to the durable docs (docs/*.md doctrine files).
**Do not spend Fable on:** repetitive CSS edits, page regeneration,
mechanical consistency fixes, log reading.

### Sonnet (default implementation model)
Implementing ROADMAP tickets, template/CSS/SVG/JS work inside an approved
spec, generator changes, responsive and accessibility fixes, re-render +
validate loops, documentation updates tied to implementation, bounded
refactors, test/validation runs.

### Haiku / lightweight
File and route inventory, repeated-pattern searches, link checking, log and
validator-output summarization, screenshot batch triage. Never let a
lightweight model decide design direction, editorial meaning, or
architecture.

### Standing rules (any model)
- Read PROJECT_STATE.md at session start; read the relevant docs/*.md
  before changing what they govern; update PROJECT_STATE.md after
  meaningful work, keeping it a snapshot rather than a diary.
- Editorial-integrity rules (PRODUCT_AND_EDITORIAL_DOCTRINE §4) bind every
  model at every tier: never invent Chinese text, translations, dates,
  ranks, sources, or claims — in code, copy, tests, or fixtures.
- Never commit, push, deploy, publish, or regenerate output unless the
  analyst explicitly asks.
- Never hand-edit `output/`; never modify `pla_watch.db` outside the pipeline;
  never modify shadow branches, ledgers or stored shadow records.
- Never defeat a source's access challenge, impersonate a browser, or route
  around `robots.txt`, however much coverage it would unlock.
- Never describe a shadow desk as qualified and never promote one. Promotion
  needs 30 consecutive collecting days, completed human checkpoint reviews,
  and owner sign-off in DECISION_LOG.md.
- The production renderer is `site/render.py`; the deploy gate is
  `scripts/validate_output.py`, whose governed baseline is **10 warnings**.
  A new warning is explained, never invented away.
- **Do not invent facts to fill a documentation gap.** State the uncertainty
  and name the authoritative source — the database, the ledger, the registry,
  the workflow file, or Git history.

## 2. Skills

| Skill | Use for | Not for |
|---|---|---|
| **ui-ux-pro-max** | IA and flow changes, navigation, responsive layout patterns, component behavior review | visual taste decisions (defer to doctrine) |
| **impeccable** | final visual refinement passes on rendered pages: typography, spacing, alignment, hierarchy; live-browser iteration | inventing new direction; anything conflicting with DESIGN_SYSTEM.md |
| **design-taste-frontend / taste review** | art-direction checks; catching generic/template drift before it lands | replacing the north star |
| **awesome-design-md / skillui** | keeping design documentation synchronized after approved visual changes | generating auto-extracted token dumps as doctrine (the 2026-07 skillui extraction was inaccurate and was retired — DESIGN_SYSTEM.md is authoritative) |
| **Journalism skills** (fact-check-workflow, source-verification, newsroom-style, ai-writing-detox/humanizer) | editorial passes on edition prose, headline/dek treatment, corrections handling, evidence presentation | rewriting published editions without the analyst |
| **graphify** | architecture/where-should-I-edit questions (`graphify-out/GRAPH_REPORT.md` first, then targeted rg); refresh with `graphify update .` after structural changes | decorative relationship visuals for the site |
| **Ruflo (swarm)** | genuinely parallel work only — e.g., one agent per route family in a multi-route implementation, or research/verification/QA role separation on a publish | single-file fixes, nav changes, README edits, routine build errors |
| **Headroom / TokenSave** | compressing long validator logs, screenshot batches, repeated repo inspection | authoritative reading of Chinese text, translations, dates, ranks, claims |

Ruflo limits: max 4 agents; one owner per template file (`base.html`,
`pla-watch-base.html`, and `pw_env.py` are single-owner, never concurrent);
the lead session integrates and is the only writer of PROJECT_STATE.md.

## 3. Project agents (`.claude/agents/`)

Minimum useful set — three agents plus one human-in-the-loop role:

- **Design Director** — *not an agent file.* This is the Fable-led main
  session role: reviews rendered output against DESIGN_SYSTEM.md +
  VISUAL_AND_MOTION_SYSTEM.md, approves/rejects visual work, updates
  doctrine. Runs before any design release is called done.
- **frontend-implementer** (Sonnet) — implements one bounded ticket:
  templates/CSS/SVG/JS + regenerate + validate + screenshot proof. Stays
  inside the ticket's file list.
- **editorial-integrity-reviewer** (Sonnet, read-only) — source-to-claim
  tracing, evidence-vs-inference presentation, verbatim Chinese text,
  citation and metadata accuracy. Output: pass/fail findings list.
- **release-qa** (Sonnet) — pre-deploy sweep: validator, preview, responsive
  (1280/375), keyboard + focus, reduced motion, console errors, link spot
  checks. Output: go/no-go report with evidence.

## 4. Project commands (`.claude/commands/`)

- **/publish-edition** — the weekly publish workflow end to end (draft →
  editorial QA → validate → preview → stop before commit for analyst
  approval).
- **/release-check** — the release-qa sweep on demand.

Commands encode the repeatable workflow; agents supply the reviewer roles.
Do not add more agents/commands without a recurring need that a doc line
cannot serve.
