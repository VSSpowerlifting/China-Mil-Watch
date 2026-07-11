# Architecture & Publishing — China Mil Watch

Durable map of what produces what, what is source vs generated, and how
changes reach production. Session state lives in PROJECT_STATE.md.

## 1. Repository boundary

Everything happens inside `~/pla-watch`. Never touch sibling repositories
(`strategic-materials-policy-tracker`, `managed-contact-risk-dashboard`,
`second-brain`, …) or unrelated home-directory files.

## 2. Layer map

| Layer | Source of truth | Producer | Output |
|---|---|---|---|
| Scrape + analyze | official PRC outlets | `pipeline.py` (scraper/, analysis/, storage/) | `pla_watch.db` (SQLite, committed) |
| Daily site | `pla_watch.db` | `site/generator.py` + `site/templates/{base,index,archive,article,signals,methodology}.html` | `output/index.html`, `archive.html`, `signals.html`, `methodology.html`, `article/*.html`, `data/articles.json`, sitemap |
| Weekly edition (publish) | Claude API + week's DB records | `scripts/generate_pla_watch.py` (structured tool output) | `output/the-pla-watch/posts/{date}.{json,html}`, covers, LinkedIn txt, feed.xml |
| Weekly re-render (no API) | **sidecar JSON** (canonical edition record: metadata + trail + full body) | `scripts/rerender_pla_watch.py` + `site/templates/pla-watch-*.html` | posts/index/archive/terms HTML + feed.xml |
| Shared weekly env | `scripts/pw_env.py` — one Jinja environment (autoescape ON), `format_date`, `inline_markup` (whitelists bare `<strong>/<em>` only), `first_cjk`, `build_atom_feed` | both weekly renderers | — |
| Deploy gate | `scripts/validate_output.py` (stdlib-only) | CI + local | non-zero exit blocks deploy |

**Source (hand-maintained):** `site/templates/`, `scripts/`, `analysis/`,
`scraper/`, `site/generator.py`, `pipeline.py`, `config.py`, docs, sidecar
prose (via publish flow only).
**Generated (never hand-edit):** everything under `output/` — including
`output/the-pla-watch/posts/*.html`. Fix templates or sidecars, then
re-render. Sidecar JSON under `output/.../posts/*.json` is generated at
publish but is the *canonical record* — edit only via deliberate,
validated migration scripts, never casually.

## 3. Commands

```bash
.venv/bin/python scripts/validate_output.py              # deploy gate (also runs on system python3 — stdlib-only)
.venv/bin/python scripts/rerender_pla_watch.py --no-covers  # weekly pages from sidecars (refuses empty-body sidecars)
.venv/bin/python site/generator.py                       # daily site from DB
.venv/bin/python scripts/generate_pla_watch.py           # PUBLISH a new edition (Claude API; only on explicit request)
```

Preview: Claude Code sessions use the Browser pane server `pla-watch-site`
(`.claude/launch.json`, port 8765, serves `output/`). Outside Claude Code:
`python3 -m http.server 8765 --directory output`.
Note: the in-app browser's screenshot capture goes stale after scrolling;
for full-page visual review use Playwright (installed in `.venv`) full-page
screenshots at 1280 and 375 widths.

## 4. CI / deployment (`.github/workflows/`)

- `daily_update.yml` — scheduled (five retry windows, one success per NY
  day): runs pipeline, regenerates daily site, commits `pla_watch.db` +
  `output/` to main, deploys `output/` → `gh-pages`
  (peaceiris/actions-gh-pages, CNAME chinamilwatch.org). Python 3.9 on the
  runner — keep validator/generator 3.9-compatible.
- `deploy_output_only.yml` — manual: validates then publishes the
  already-committed `output/` from main. Use after local re-renders.
- `generate_pla_watch_draft.yml` — manual, artifact-only draft; does not
  commit or deploy.

**Deploys publish what is committed on main.** There is no build step in
Pages — `output/` must be committed for anything to go live. Nothing blocks
a hand-commit to main; discipline lives in the validator + review flow.

## 5. Commit strategy (approved 2026-07-11; nothing auto-commits from sessions)

Do not commit/push/deploy without the analyst's explicit request. When asked:

1. **Docs / operating system** — own commit (`docs: …`).
2. **Source change** (templates, generator, scripts) — own commit with the
   narrowest scope (`Weekly pages: …` / `Homepage: …` style, matching log).
3. **Regenerated output** — separate commit immediately after its source
   commit (`Re-render weekly pages from unchanged sidecars` /
   `Regenerate daily site`). Keeping output separate keeps source diffs
   reviewable; keeping it adjacent keeps main deployable at every point.
4. **Validation / cleanup fixes** where needed — own commit(s) after the
   output commit, narrowest scope.
5. **Never** mix `pla_watch.db` changes into design commits — the daily
   workflow owns DB commits.
6. Run `scripts/validate_output.py` before any commit that touches output,
   and before asking to deploy.

## 6. Validation contract

`validate_output.py` checks: index exists; no unrendered Jinja anywhere;
articles.json parses and paths exist; PW sidecar/HTML pairing; dates =
filenames = week_ending; 6-day week span (pilot exempt); issue numbers
unique + chronological; counts consistent; body text sufficient to
re-render; trail entries carry title/url/source; index + archive + terms
link every edition; feed well-formed. Warnings (do not "fix" by invention —
see PRODUCT_AND_EDITORIAL_DOCTRINE §4): missing LinkedIn files (eds. 1–3),
undated early trail entries, cadence notes. Baseline: **passes with 9
historical warnings**; any new warning must be explained in PROJECT_STATE.

## 7. Editorial production flow (weekly)

1. `generate_pla_watch.py` drafts from the week's DB records (or the draft
   workflow produces an artifact).
2. Analyst reviews/edits; EDITORIAL_QA_CHECKLIST.md is the gate (source-to-
   claim tracing, banned superlatives, messaging-not-intent, mechanics).
3. Validate → preview (desktop + 375px) → analyst approves.
4. Commit source-of-record (sidecar + HTML + LinkedIn txt) on request;
   deploy via push (daily workflow) or `deploy_output_only`.
5. Update PROJECT_STATE.md (edition count, new gaps recorded not explained
   away); log any constraining ruling in DECISION_LOG.md.
