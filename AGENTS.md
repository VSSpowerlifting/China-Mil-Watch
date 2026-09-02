# Agent Operating Rules — Indo-Pacific Record

Read `CLAUDE.md` first — it is the authoritative operating file for this
repository (orientation, hard rules, commands, doc map). This file exists
for tools that read AGENTS.md instead.

The public identity is **Indo-Pacific Record**. "China Mil Watch" is the
retired predecessor name and is used only when describing history. "The PLA
Watch" is current: the China Desk's weekly analytical series.

Summary of the non-negotiables:

- Work only inside `~/pla-watch`; never touch sibling repositories.
- Never hand-edit `output/` (generated) or sidecar JSON (canonical edition
  records). Fix templates/scripts, then re-render.
- Never invent Chinese text, translations, titles, outlets, dates, units,
  ranks, or claims. Historical gaps stay as recorded warnings.
- Never defeat a source's access challenge or impersonate a browser; an
  institution must be able to recognise this collector and refuse it.
- No shadow desk is promoted automatically, and none may be described as
  qualified.
- Do not commit, push, deploy, publish, or regenerate output unless
  explicitly asked. CI deploys what is committed on main.
- Production renderer is `.venv/bin/python site/render.py`; the deploy gate is
  `.venv/bin/python scripts/validate_output.py`, whose governed baseline is
  10 warnings.
- Be token-efficient: smallest safe change, no full-file pastes, no
  unrequested refactors; report files changed + what changed + how to test.
- Session start: read `PROJECT_STATE.md`; deeper doctrine in `docs/`
  (product/editorial, architecture & publishing, agent workflows, roadmap,
  shadow collection and review, design system, visual & motion).
