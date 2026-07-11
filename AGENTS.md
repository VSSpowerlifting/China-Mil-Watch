# Agent Operating Rules — China Mil Watch

Read `CLAUDE.md` first — it is the authoritative operating file for this
repository (orientation, hard rules, commands, doc map). This file exists
for tools that read AGENTS.md instead.

Summary of the non-negotiables:

- Work only inside `~/pla-watch`; never touch sibling repositories.
- Never hand-edit `output/` (generated) or sidecar JSON (canonical edition
  records). Fix templates/scripts, then re-render.
- Never invent Chinese text, translations, titles, outlets, dates, units,
  ranks, or claims. Historical gaps stay as recorded warnings.
- Do not commit, push, deploy, publish, or regenerate output unless
  explicitly asked. CI deploys what is committed on main.
- Be token-efficient: smallest safe change, no full-file pastes, no
  unrequested refactors; report files changed + what changed + how to test.
- Session start: read `PROJECT_STATE.md`; deeper doctrine in `docs/`
  (product/editorial, design system, visual & motion, architecture &
  publishing, agent workflows, roadmap).
