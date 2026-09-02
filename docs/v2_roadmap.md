# Pipeline backlog (originally "v2 Roadmap")

Pipeline-layer backlog — analyzer, scrapers, relevance filter. Product and
publishing priorities are in `docs/ROADMAP.md`, which is the authoritative
ordering; nothing here outranks it.

Items scoped out of v1 during initial development.  Each entry includes
the failure mode or limitation that motivated it and a rough implementation
direction.  Ordered roughly by analytical impact.

**Status, 2026-09-02.** Some entries below have since shipped and are marked
so; the rest are still open. Nothing here should be read as a current
description of the system — for that, see `PROJECT_STATE.md` and
`docs/ARCHITECTURE_AND_PUBLISHING.md`.

---

## P1 — High impact, clear implementation path

### Structured output for LLM analysis tasks

**Partly delivered.** Translation now uses a forced `emit_translation` tool
call (DECISION_LOG 2026-07-30); the remaining analysis tasks are still open.

**Motivation:** The current `_parse_json()` method in `analysis/analyzer.py`
strips markdown code fences via regex.  Long responses — particularly
multi-thousand-character translation outputs for doctrinal and historical
essays — intermittently produce formatting drift that bypasses the regex.
Two articles failed on a 23-article batch (8.7% failure rate on long content).

**Fix:** Migrate all four analysis tasks to the Anthropic API's tool-use /
structured output mode.  Pass each task's JSON schema as a `tools` definition
and set `tool_choice` to force a structured response.  This eliminates
free-text JSON parsing entirely.

**Affected file:** `analysis/analyzer.py` — `_call()` and all four task methods.

---

### Cadence-aware summaries for routine patrol/exercise reporting
**Motivation:** The current summary prompt produces analytically correct but
context-free descriptions of routine events.  For CCG Diaoyu patrols, PLAN
exercise announcements, and similar recurring operations, "follows a standard
pattern" is accurate but not maximally useful.  A summary that says "the 4th
CCG patrol of the Diaoyu Islands in 7 days, compared to a baseline of ~2/week
in Q1 2026" is more actionable.

**Fix:** After accumulating 30+ days of archive depth, add a context-injection
step before the summary prompt: query the DB for prior articles matching the
same category + geographic area within a configurable lookback window, extract
cadence data, and pass it as a `[CONTEXT]` block.

**Dependency:** Requires archive depth to be meaningful.  Revisit mid-summer.

**Affected files:** `analysis/prompts.py` (summary prompt), `analysis/analyzer.py`
(pre-prompt context fetch), `storage/db.py` (cadence query).

---

## P2 — Medium impact, some complexity

### Tighten relevance filter for classical military history content
**Motivation:** The keyword pre-filter passes articles on ancient/classical
Chinese military history (e.g., Battle of Changping analysis, 孙子兵法 essays)
because they contain military terminology.  These score 0.6–0.7 on LLM
relevance — technically above threshold — but carry no intelligence value
about current PLA posture, capabilities, or activities.

**Fix (option A):** Add a clause to the relevance scoring prompt: "Articles
whose primary subject is pre-20th-century military history, classical military
philosophy, or historical fiction — even if written with PLA political-work
framing — should score 0.1–0.3 unless they contain specific claims about
current PLA doctrine, capabilities, or unit activities."

**Fix (option B):** Add a keyword blocklist for classical-history signals
(长平之战, 赤壁, 孙子, 三十六计, etc.) that downgrades, but does not eliminate,
articles from the LLM relevance pass.

Option A is cleaner and doesn't require maintaining a blocklist.

**Affected file:** `analysis/prompts.py` — `build_relevance_messages()`.

---

### Resume robustness for translation failures
**Motivation:** Articles whose translation fails (Stage 2) have
`passed_relevance=1` and `analyzed_at=NULL` and are correctly picked up
by `get_articles_pending_analysis()` on re-run.  However, re-running
relevance scoring (Stage 1) on articles that already passed wastes one
API call per article.

**Fix:** Add a `skip_relevance` flag to `Analyzer.analyze()`.  The pipeline
passes `skip_relevance=True` for articles sourced from
`get_articles_pending_analysis()` since their relevance is already confirmed.

**Affected files:** `analysis/analyzer.py`, `pipeline.py`.

---

## P3 — Low priority / post-MVP

### Xinhua Military scraper (JS-rendered)

**Still open, and still a stub.** It has contributed zero records for the life
of the project and is reported as `not_implemented` rather than hidden.

`xinhua_mil` is implemented as a stub.  `xinhuanet.com/mil/` renders
article listings entirely via JavaScript API calls and returns only stale
2020-era HTML to requests-based clients.  Three options are documented in
`scraper/sources/xinhua_mil.py`: headless browser (Playwright/Selenium),
reverse-engineering the `xhpfmapi.zhongguowangshi.com` API, or substituting
a different Chinese-language military source.

### Static site generator — **DELIVERED**
Shipped and since superseded twice: the legacy generator is now the rollback
path and `site/render.py` selects the production record renderer. See
`docs/ARCHITECTURE_AND_PUBLISHING.md` §2 and `docs/SITE_MODES.md`.

### GitHub Actions deployment — **DELIVERED**
`.github/workflows/daily_update.yml` runs on five scheduled windows with a
one-per-New-York-day guard, commits `pla_watch.db` and `output/` to `main`, and
deploys `output/` to `gh-pages` with `cname: indopacificrecord.org`. The
single 06:00 UTC cron originally sketched here was never the shipped schedule.

### Cross-source deduplication signal quality

**Partly superseded.** Cross-source canonical selection is now a five-part
total ordering (DECISION_LOG 2026-08-17), and corpus-wide *title* dedup is
explicitly blocked and pinned by tests (`FOLLOWUP.md`) because a recurring
official title names distinct events. What remains open is the
occurrence/provenance model — recording that two institutions carried the same
release — which is priority 7 in `docs/ROADMAP.md`.

Current deduplication uses URL and SHA-256 content hash.  Xinhua and China
Military Online frequently republish PLA Daily content with minor edits,
which will pass the content-hash check.  A fuzzy-match approach (e.g.,
MinHash or simple title similarity) would catch near-duplicates across sources.
