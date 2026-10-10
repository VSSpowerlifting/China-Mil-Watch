# Architecture & Publishing — Indo-Pacific Record

Authoritative map of what produces what, what is source vs generated, and how
changes reach production. Session state lives in PROJECT_STATE.md; durable
identity and editorial principles live in PRODUCT_AND_EDITORIAL_DOCTRINE.md.

The published site is **Indo-Pacific Record** at `https://indopacificrecord.org`.
"China Mil Watch" is the retired predecessor identity and appears below only
where it describes the rollback path or historical behaviour.

## 1. Repository boundary

Everything happens inside `~/pla-watch`. Never touch sibling repositories
(`strategic-materials-policy-tracker`, `managed-contact-risk-dashboard`,
`second-brain`, …) or unrelated home-directory files.

## 2. Layer map

| Layer | Source of truth | Producer | Output |
|---|---|---|---|
| Scrape + analyze | official PRC outlets | `pipeline.py` (scraper/, analysis/, storage/) | `pla_watch.db` (SQLite, committed) |
| Mode selection | — | **`site/render.py`** — the only place a frontend is chosen; `DEFAULT_SITE_MODE` is `indo-pacific-record` | dispatches to one of the two renderers below |
| Record site (production) | `pla_watch.db` | `site/preview/generate_preview.py`, driven by `render_site()` | `output/index.html`, `record/*.html`, `archive.html`, `coverage.html`, `methodology.html`, desk pages, `article/*.html` compatibility stubs, `data/`, sitemap |
| Legacy site (rollback only) | `pla_watch.db` | `site/generator.py` + `site/templates/{base,index,archive,article,signals,methodology}.html` | the predecessor's tree; **not** the production build |
| Weekly edition (predecessor series) | — | `scripts/generate_pla_watch.py` — **closed to new issues since 2026-09-23**: refuses before any DB read or API call | nothing |
| Brief (human-controlled publication) | `pla_watch.db`, read through a scratch copy (`scripts.reconcile_db.read_only`) | `scripts/author_brief.py` + `core/brief_contract.py`; selection by desk via `storage.db.get_articles_for_desks` | canonical source in `briefs/<slug>.json`; draft/check/readiness/authorized approval; native article, Analysis, homepage, Atom feed and sitemap through the production renderer |
| Weekly re-render (no API) | **sidecar JSON** (canonical edition record: metadata + trail + full body) | `scripts/rerender_pla_watch.py` + `site/templates/pla-watch-*.html` | posts/index/archive/terms HTML + feed.xml |
| Shared weekly env | `scripts/pw_env.py` — one Jinja environment (autoescape ON), `format_date`, `inline_markup` (whitelists bare `<strong>/<em>` only), `first_cjk`, `build_atom_feed` | both weekly renderers | — |
| Evidence Timeline (human-controlled chronology) | `timelines/<slug>.json` + exact preserved DB records via `scripts.reconcile_db.read_only` | `core/timelines.py`, `scripts/validate_timelines.py`, production renderer | approved-only `timelines.html` and `timeline/<slug>.html`; explicit private draft review outside the repository; no feed or DB migration; contract and review in `docs/EVIDENCE_TIMELINES.md` |
| Deploy gate | `scripts/validate_output.py` (stdlib-only) | CI + local | non-zero exit blocks deploy |

**Source (hand-maintained):** `site/templates/`, `scripts/`, `analysis/`,
`scraper/`, `site/render.py`, `site/preview/`, `site/generator.py`,
`pipeline.py`, `config.py`, `desks/`, `shadow/`, `timelines/`, docs, sidecar prose (via
publish flow only).
**Generated (never hand-edit):** everything under `output/` — including
`output/the-pla-watch/posts/*.html`. Fix templates or sidecars, then
re-render. Sidecar JSON under `output/.../posts/*.json` is generated at
publish but is the *canonical record* — edit only via deliberate,
validated migration scripts, never casually.

Modern decorative primitives are source-owned in `site/preview/templates/_terrain.html`
and `site/preview/enrichment.css`, with prepared materials under `site/assets/material/`.
The record renderer copies those sources and exact local font kits into production.
Historical articles use the current IPR shell through `historical-brief.html`,
including the same bounded Brief edge primitive and exact historical citations.
Compatibility index/archive/terms preserve `topography.css` and deterministic
`core/topography.py` profiles, with compact `historical-enrichment.css` and local
original fonts. Historical HTML still requires the normal sidecar re-render to pick
up base-template edits. See `docs/FRONTEND_ENRICHMENT_2026-10-09.md` for coverage,
provenance, delivery measurements and browser review.

## 3. Commands

```bash
.venv/bin/python scripts/validate_output.py              # deploy gate (also runs on system python3 — stdlib-only)
.venv/bin/python site/render.py                          # PRODUCTION renderer: daily site from DB
.venv/bin/python scripts/rerender_pla_watch.py --no-covers  # weekly pages from sidecars (refuses empty-body sidecars)
.venv/bin/python scripts/author_brief.py scaffold --desks china,singapore --week-ending YYYY-MM-DD --out PATH  # draft a brief (no API; read-only on disk)
.venv/bin/python scripts/author_brief.py check PATH      # schema/numbering contract; a draft may still have empty prose
.venv/bin/python scripts/author_brief.py ready PATH      # complete prose/citations and exact parity with preserved records
.venv/bin/python site/render.py --review-brief briefs/<slug>.json --out /tmp/<private-review>  # private candidate, no approval or number
.venv/bin/python scripts/validate_timelines.py             # offline shape + preserved-source parity; no approval
.venv/bin/python site/render.py --review-timeline timelines/<slug>.json --out /tmp/<private-review>  # unpublished chronology; no origin/feed/sitemap
# scripts/generate_pla_watch.py authors nothing new: no issue is published as The PLA Watch after No. 14
```

`site/render.py` resolves its mode by precedence — an explicit argument, then
`PLA_WATCH_SITE_MODE`, then `DEFAULT_SITE_MODE` — and no workflow sets the
environment variable. Calling
`site/generator.py` directly builds the **legacy** predecessor tree; it is the
documented rollback path and must never be used as the production build. Mode
mechanics and the rollback procedure are in `docs/SITE_MODES.md`.

Preview: Claude Code sessions use the Browser pane server `pla-watch-site`
(`.claude/launch.json`, port 8765, serves `output/`). Outside Claude Code:
`python3 -m http.server 8765 --directory output`.
Note: the in-app browser's screenshot capture goes stale after scrolling;
for full-page visual review use Playwright (installed in `.venv`) full-page
screenshots at 1280 and 375 widths.

## 4. CI / deployment (`.github/workflows/`)

- `daily_update.yml` — scheduled (five retry windows, one success per NY
  day): runs the offline suite, then the pipeline (which renders through
  `site/render.py`), commits `pla_watch.db` + `output/` to main, deploys
  `output/` → `gh-pages` (peaceiris/actions-gh-pages@v3,
  `cname: indopacificrecord.org`). Python 3.9 on the runner — keep the
  validator and both renderers 3.9-compatible.
- `deploy_output_only.yml` — manual: validates then publishes the
  already-committed `output/` from main, with the same CNAME. Use after local
  re-renders.
- `pr_offline_checks.yml` — offline checks on pull requests.
- `singapore_shadow.yml`, `japan_shadow.yml` — daily shadow collection into
  isolated orphan state branches. They publish nothing, deploy nothing, and
  never open `pla_watch.db` or `output/`. See `docs/SHADOW_COLLECTION.md`.

**Both deploy workflows must keep naming `indopacificrecord.org`.** A domain is
held by one Pages site at a time, and `chinamilwatch.org` is served by a
separate redirect-only site; a workflow that reclaimed the old domain would
turn every preserved legacy address back into the predecessor's site. Pinned by
test.

`peaceiris/actions-gh-pages` writes `.nojekyll` at the root of `gh-pages`. It
is not tracked under `output/`, and it does not need to be.

**A green Actions run is not evidence that the pipeline executed.** Five
scheduled windows report success each day and a scheduling guard admits one;
the other four skip every step. Read the `Scheduling guard` step, which prints
`should_run=true` or `should_run=false`.

**The daily render is told which day it is.** `Last full update` comes from
`.github/state/last_daily_run_date.txt`, which the workflow writes in its LAST
step — after validation, commit and deploy — so that only a run that finished
everything records one. The render happens well before that, so reading
the marker there published the *previous* run's date. The scheduling
guard's `today_ny` is passed to the pipeline as `PLA_WATCH_DAILY_RUN_DATE`,
through `site/render.py` into `PublicView.freshness()`, and is used instead.
The marker itself is unchanged, unwritten during the render, and still
advances only at `Record successful run`. Builds with no run context
(local, and every other workflow) keep reading the marker. Pinned by
`tests/test_daily_render_freshness.py`.

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
undated early trail entries, cadence notes. Baseline: **passes with 10
governed warnings** (verified 2026-09-02) — three no-date source-trail
warnings, two `n_significant` warnings with no marked trail entry, one pilot
week-span warning, three missing LinkedIn files for editions 1–3, and one
cadence gap (2026-07-18 → 2026-08-01). Any new warning must be explained in
PROJECT_STATE.md, and none is ever cleared by invention.

## 7. Editorial production flow

**Indo-Pacific Record Briefs** (since 2026-09-23; doctrine §5b):

1. `scripts/author_brief.py scaffold --desks … --week-ending …` drafts from the
   named desks' records: explicit identity, per-desk coverage, a candidate
   trail in which every entry keeps its record's desk and language, empty
   analyst fields, no issue number. No API; the database is read through a
   scratch copy; nothing is written under `output/`. Records screened and not
   selected are counted but not offered (`--include-not-selected` offers them).
2. The analyst keeps the trail entries the brief cites, records the
   `development` and each cross-desk claim with its citations, and writes the
   prose in the existing anatomy.
3. `scripts/author_brief.py check PATH` validates schema and whole-collection
   numbering; empty drafts may pass. `ready PATH` requires finished standing
   sections, development and comparison citations, a Saturday reporting endpoint,
   a signal of at most 28 words, source metadata, and exact source-trail and
   per-desk coverage parity with the preserved corpus. Source state conflicts
   are refused with the changed fields; review a fresh scaffold rather than
   silently replacing evidence. A schema check or readiness pass is never an
   editorial sign-off.
4. Complete `EDITORIAL_QA_CHECKLIST.md`, including source-to-claim and original
   language review. Preview the exact candidate with the production renderer:

   ```sh
   .venv/bin/python site/render.py --review-brief briefs/<slug>.json --out /tmp/<private-review>
   ```

   Review mode renders the article, Analysis lead/catalog and homepage in a
   private tree with visible notices, no issue number or invented approval,
   `noindex`, no native feed and no sitemap. It refuses `output/` and legacy
   mode. Ordinary rendering withholds every draft. Inspect actual 1280px and
   375px screenshots, source links, keyboard focus and reduced motion.
5. Once the human has approved this exact editorial version, record that actual
   authorization; do not ask again when the session already supplies it:

   ```sh
   .venv/bin/python scripts/author_brief.py approve briefs/<slug>.json \
     --approved-by 'Benjamin Yang' --approved-on YYYY-MM-DD \
     --approval-reference '<location of actual human approval>'
   ```

   Approval assigns one more than the collection's highest number, including
   native and predecessor issues. A local publication lock serializes assignment,
   and the canonical source is replaced atomically. An identical repeated
   approval is a no-op; changed evidence or a second number is refused. Scaffold
   refuses an existing destination. The command records authorization supplied
   by its caller; it cannot independently establish that a human gave it.
   Approval freezes the reviewed evidence snapshot. Later pipeline screening
   does not rewrite an approved Brief or block its ordinary re-render.
6. Render with `.venv/bin/python site/render.py`; validate with
   `.venv/bin/python scripts/validate_output.py`. The native article is
   `briefs/<slug>.html`; Analysis and the homepage use the same unified catalog.
   Both the catalog and native feed sort newest coverage endpoint first,
   breaking ties by number and slug. Numbers remain approval order; Atom dates
   remain actual approval dates. Predecessor feed entries are untouched.
   The validator refuses draft/stale native routes, missing approved pages,
   mismatched title/number, missing canonical, catalog/feed/sitemap entries,
   and a native feed without approved sources. Its historical baseline remains
   10 governed warnings.
7. Prepare source/docs/generated-output commits separately (§5), then use the
   existing PR checks and deployment path (§4) within recorded authorization.
   A PR or successful workflow is not evidence of publication. Fetch the actual
   public article, Analysis, home, native feed and sitemap after deployment and
   verify the correct title, number, source links and editorial version. A
   subsequent ordinary render must preserve it without any paid API call.

**The existing issues** (published as *The PLA Watch*) re-render from their
sidecars with `scripts/rerender_pla_watch.py`. `scripts/generate_pla_watch.py`
authors nothing new, and `generate_pla_watch_draft.yml`, which only dispatched
it, is retired (DECISION_LOG 2026-09-23). After any publication, update
PROJECT_STATE.md and record constraining rulings in DECISION_LOG.md.
