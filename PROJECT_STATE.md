# PROJECT_STATE — China Mil Watch / The PLA Watch

Updated: 2026-08-03 (reconciliation landed on local `main`; unpushed).
State only — durable doctrine lives in CLAUDE.md and docs/ (see CLAUDE.md
table).

## Working tree (as of this update)

**The reconciliation is landed and pushed.** `origin/main` is at `0f963fa`
as of 2026-08-04; local `main` is in sync and the working tree is clean.
`fix/pipeline-data-loss-2026-07-30` points at the same commit and is safe to
delete. The 80 recovered articles (07-30, 07-31) are **no longer
single-copy** — verified on the remote after the push: 2880 rows / 2880
distinct urls / 672 analyzed, 40 articles on each of the two days.

History: `origin/main` advanced independently while the branch sat local —
billing markers for 07-30/07-31, then daily updates for 08-01, 08-02 and
08-03. CI recovered unaided on 08-01, consistent with the monthly spend cap
resetting, not with any repair. Production never held 07-30 or 07-31.

`pla_watch.db` cannot be merged by git: both sides advance from the same
base and allocate ids from the same counter, so the two sets collide and a
plain merge silently drops one side. This is now handled automatically by a
**row-level merge driver** (`scripts/reconcile_db.py --merge-driver`, named
in `.gitattributes`, installed by CI before every `git pull --rebase`).
Origin is authoritative for identity; local-only rows are renumbered above
origin's maximum. The 2026-08-03 merge of origin's 08-03 collection ran
through this driver with no conflict: 80 new articles merged, 117 analysis
rows backfilled.

Reconciled state (measured 2026-08-03): **2880 rows / 2880 distinct urls /
672 analyzed**, continuous 07-26→08-03 coverage. All gates pass — 0 urls
lost from either side, **0 id drift on rows origin already had** (origin's
ids run to 2806, and those already rendered are live in
`output/article/*.html` and the sitemap, so renumbering them would break
published links), 0 duplicate urls, `foreign_key_check` and
`integrity_check` clean. `validate_output.py` green
at the 9-warning baseline.

`output/` is byte-identical to `origin/main` — the branch never regenerated
it — so landing this changes no rendered page. The next scheduled run
regenerates once the recovered articles are analyzed.

Pushed 2026-08-04 01:32 UTC, deliberately outside the drifted execution
window (last run 08-03 16:42 UTC; next cron 08-04 12:23 UTC). Time any
future manual push the same way — query the Actions API, never the cron
comments. See CI schedule drift under Known issues.

Historical note, still accurate: the previously uncommitted 2026-07-12 production-completion pass,
2026-07-13 Signal Veil pass, and 2026-07-16 J-20 atmospheric pass (see
DECISION_LOG entries of those dates) were reconciled onto `origin/main`
and committed on branch `reconcile/unfinished-pla-watch-2026-07-16`
(DECISION_LOG 2026-07-17 records the recovery mechanics). Local-only
safety branch `rescue/unfinished-pla-watch-2026-07-16` preserves the raw
WIP snapshots and must not be pushed or treated as production history.
The old local `main` (`1f0917c`, patch-id-identical to remote `5e92dc4`)
was intentionally left untouched in `~/pla-watch`.

## Publication state

11 editions published, No. 1–11, weekly without cadence gaps: 2026-05-09
(pilot, 2-day window) through 2026-07-18 ("Joint Sea-2026, the Y-20B
Abroad, and the Week's Quieter Signals", Significant, 34 articles /
3 model-flagged). Issue numbers stored in sidecars, validated unique +
chronological.

**Next edition: No. 12, week ending 2026-08-01.** There is no edition for
the week ending 2026-07-25 — analyst-ruled 2026-07-30, DECISION_LOG. The
2026-07-17→07-24 collection outage left that window with one observed day
of seven (07-25 only: 29 articles, 8 relevant, 0 model-flagged), and
retro-scraping was tested and rejected as unsound (07-16 control: 33
articles captured live, 3 recoverable). Expect and keep a **cadence-gap
warning** from the validator for this break; it is the record of the
outage, not a defect to suppress.

**No. 12's window is now fully screened (2026-08-03).** The 07-26→08-01
window holds all seven days and 253 articles (32 / 38 / 39 / 37 / 40 / 40 /
27). Its 156 unscreened articles were cleared by a scoped
`backfill_unscored.py --since 2026-07-26 --until 2026-08-01` run: 110
analyzed, 43 rejected, 1 translation-failed, 2 summary-failed, 0 errors.
Window now reads **0 unscreened, 155 passed relevance, 146 fully analyzed,
24 model-flagged, 9 relevant-but-untranslated**. The observed pass rate was
**72%, not the historical 44%** — the estimate assumed 44%, so actual spend
was ~$4.55 against a $2.86 pre-flight. Treat 44% as a floor for recent
windows when estimating.

Before drafting No. 12: clear the 9 untranslated (they carry no English
title/summary, so no edition can cite them) via
`scripts/backfill_translations.py`, then re-render and run the deploy gate.
The site has been re-rendered — `output/` and the DB are in sync at 782
analyzed articles, 0 unrendered, 0 orphans, gate green at the 9-warning
baseline.

No. 11 shipped after correcting three editorial-integrity findings caught
by QA before publish (analyst-approved 2026-07-25, DECISION_LOG): the
Y-20B first-international-flight date "April 2025" → **April 2026** (the
cited source 81.cn/16473227, published 2026-07-12, says "今年4月");
engine "WS-20" downgraded from source-"confirmed" to "widely identified
as" (source says only "新型国产发动机"); and three Routine-Baseline
articles (Strong Military Forum frugality 16473917, 80th GA compliance
16473559, RF governance 16473317) added to the source trail so the named
units trace. Trail now 16 entries; validator green at the 9 historical
warnings.

## Validation status

`validate_output.py`: **passes, 9 warnings** — all historical, ruled on
2026-07-09/10 (missing LinkedIn files eds. 1–3; undated early trail
entries; related notes). Do not fix by invention; explain any NEW warning
here.

## API spend limit — block lifted 2026-08-01

The account's configured API usage limit was reached 2026-07-30 during the
backfills; all LLM calls returned 400 until the monthly reset. The block has
lifted and daily collection ran normally on 08-01, 08-02 and 08-03. Current
state and durable consequences:

- **Corpus as measured 2026-08-03 (after the No. 12-window backfill):** 2880
  articles, **1043 never screened** (36%), **83 relevant but untranslated**,
  0 translated-without-summary. The No. 12 window accounts for the drop from
  1199; the untranslated count rose by 3 because the scoped run produced 1
  translation-failure and 2 summary-failures, which stay unwritten by design
  and re-queue. Both backfill scripts are re-runnable and resume where they
  stopped — the DB is the checkpoint (`passed_relevance IS NULL`), there is
  no checkpoint file.
- **Output silently lagged the DB by 117 articles for four deploys
  (found and fixed 2026-08-03).** The 07-30 backfill's articles reached `main`
  via the reconcile merge driver and were never rendered; the deploy gate read
  `output/` in isolation and could not see it. Re-rendered (227 pages written,
  including this session's 110), and `validate_output.py` **check 8** now fails
  the gate on any analyzed-but-unrendered article. See DECISION_LOG 2026-08-03.
  **Any DB-writing path must re-render before it counts as done.**
- **`backfill_unscored.py` now takes `--since` / `--until`** (inclusive,
  `published_date`, YYYY-MM-DD). `--limit` alone could not scope a run to a
  current edition: it slices oldest-id-first, and the No. 12 window sat at
  positions 1024–1199 of the 1199-item queue, so reaching it meant paying for
  the entire backlog. Default behaviour without the flags is unchanged.
- **2026-07-30 and 2026-07-31 collection are both captured** (40 articles
  each, still unanalyzed). 07-31 was taken at 21:58 UTC on 07-31 via
  `.venv/bin/python pipeline.py --no-analysis`, closing the last window in
  which permanent loss was still possible. Do NOT rely on
  `ANTHROPIC_API_KEY=""`; see DECISION_LOG.
- **`--no-analysis` no longer regenerates `output/`** (DECISION_LOG
  2026-07-31 §1). The 07-31 capture, under the old behaviour, rendered the
  unreviewed methodology draft into `output/` — that regeneration was
  reverted and the behaviour fixed.
- **CI persists whatever it scraped even when the analysis stage fails**
  (workflow step added 07-30), so an account-level block no longer costs
  collection.

## Known issues / gaps (recorded, not explained away)

- **Analysis cap starved the backlog (fixed 2026-07-30; pile still draining).**
  `DAILY_ANALYSIS_CAP` was 15 while runs scrape ~30/day, and the queue was
  `new + pending + unscored` truncated to the cap — so the slice never
  reached the backlog and it drained at **zero per run, permanently**.
  Result: **1,119 of 2,720 articles (41%) were never relevance-screened**,
  growing ~18/day for 66 days, and the 163 translation failures were never
  retried once. At the historical 44% pass rate the unscreened pile holds
  an estimated **~487 relevant articles** — so editions No. 1–11 drew on
  roughly 60% of the relevant material actually scraped. Fixed by
  `BACKLOG_RESERVE_FRACTION` (0.3) plus raising the cap to **55**, above the
  scrape rate; `scripts/backfill_unscored.py` clears the pile faster.
  **Standing rule: the cap must stay above the daily scrape rate** — below
  it, a cost ceiling becomes a silent data-loss mechanism. Watch for the
  "newly scraped article(s) deferred by the cap" warning.
  **Passive drain is too slow to rely on:** at cap 55 × 0.3 the reserve is
  ~16 backlog slots, and the scheduling guard allows one real run per NY
  day, so ~16/day against a 1199 pile is ~75 days. The pile shrinks only if
  the backfill script is run deliberately.

- **CI schedule drift, and green runs that did nothing.**
  Scheduled runs start well after their cron time, every window, and the lag
  is **not stable from day to day**. On 08-01 and 08-02 it was 60–100 min
  (cron 12:23 UTC executing 14:02 and 14:04). On **08-03 it was far worse**:
  the five runs started 15:21, 15:32, 15:58, 16:11 and 16:42 UTC against
  crons 12:23–14:23 — roughly **138–178 min late**. So the 08:23–10:23 NY in
  the old workflow comment is wrong, and the ~13:23–16:03 UTC replacement
  first recorded on 08-03 is itself too narrow. Treat the window as
  unpredictable: **always query the runs API before a manual push** instead
  of trusting any recorded range, including this one. The off-peak
  `:23`/`:53` minutes do not measurably help. Separately, a run whose
  scheduling guard returns
  `should_run=false` skips every step and still reports **success** — five
  green runs a day is the designed shape (one real, four no-ops), so a green
  check is **not** evidence the pipeline executed. Time any manual push
  against the runs API, which answers unauthenticated because the repo is
  public (`gh` is not installed here):
  `curl -s "https://api.github.com/repos/VSSpowerlifting/PLA-Watch/actions/runs?per_page=8"`

- **Translation losses (fixed 2026-07-30; backfill run).** 163 of 697
  relevant articles (23%) passed the relevance gate but were never
  translated, spanning 70 days since launch, and so were invisible to all
  11 published editions. **Two independent causes**, both fixed — see the
  two DECISION_LOG entries of 2026-07-30:
  1. *Token cap.* `translate()` was capped at `max_tokens=4000`; long
     bodies truncated mid-JSON. Length-determined: 95% failure above 3800
     Chinese chars, **100% above 5000**. Now `TRANSLATION_MAX_TOKENS`
     (32K, streamed), with `stop_reason=max_tokens` checked before parsing.
  2. *Unescaped inner quotes.* Preserved rhetorical quotation marks
     terminated JSON strings early in complete, untruncated responses.
     `translate()` now uses a forced `emit_translation` tool call, so the
     API handles escaping. Do not reintroduce raw-JSON instructions to the
     translation prompt.
  Editorial consequence, now remediated but true of editions No. 1–11:
  the excluded set was the longest, most analytically substantial PLA
  Daily material — it included the full China–Russia joint statement on
  comprehensive strategic coordination (article 476, 18,148 chars), which
  no edition ever saw.
  Backfill: `scripts/backfill_translations.py` (re-runnable; deliberately
  does **not** re-score relevance, preserving the audit record).
- **2026-07-17→07-24 collection outage (permanent).** No `scrape_runs`
  rows exist for those eight days; the failed CI runs never persisted
  their DB writes. Not recoverable — see the backfill ruling in
  DECISION_LOG 2026-07-30.
- Public-surface disclosure of the 07-17→07-24 outage is **not yet
  written** — archive/methodology still imply continuous collection.
- `output/archive.html` is 804 KB flat list (446 articles) — ROADMAP T1.
- Cover PNGs ~8.2 MB total; photo-overlay covers duplicate titles — ROADMAP
  T2 (Edition Plate) + T4 (asset hygiene).
- Source coverage is effectively PLA Daily only; other outlets remain
  "configured / expanding" — visuals must show this honestly.
- 2026-05-16 sidecar lacks `edition_label` (no badge, by design); its body
  carries literal `<strong>` handled by the `inline_markup` whitelist.
- `pla_watch.db` committed to main by the daily workflow — revisit if it
  grows.
- Homepage image-load-failure path: the `.src-bracket` credit still renders
  even when the `.pl-veil`/derivative fails to load, so the attribution
  bracket can appear with no image behind it. Accepted as a deferred minor
  issue 2026-07-16 (analyst-approved); pre-existing behavior of the Signal
  Veil system, not introduced by the J-20 swap. Not fixed by invention.
- No enforced review gate between weekly generation and publication;
  discipline is EDITORIAL_QA_CHECKLIST + validator.
- In-app Browser-pane screenshots go stale after scroll; use Playwright
  (in `.venv`) for full-page visual review at 1280 + 375.

## Outstanding decisions (analyst input needed)

None. The 2026-07-11 analyst rulings resolved the then-open items;
"Model-flagged" stays the only reader-facing label for automated
classifications (all surfaces verified). Note: `executive_readout` /
`recurring_threads` adoption was deferred by analyst instruction — No. 10
shipped without them (DECISION_LOG 2026-07-17 §2); adopt from a later
edition when the analyst authors one.

## Next tasks

**In this order:**

1. Check remaining headroom in the Console — the guard estimates cost, not
   headroom, and cannot do this step for you.
2. Run the backfills **sequentially, not concurrently** (running both at
   once doubled the draw on 07-30):
   `.venv/bin/python scripts/backfill_translations.py --confirm-spend`
   (80 relevant-untranslated), then
   `.venv/bin/python scripts/backfill_unscored.py --confirm-spend`
   (1199 unscreened). Each prints its own spend estimate before proceeding;
   both abort immediately on an account-level block and resume cleanly on
   re-run. If spend is constrained, screen the No. 12 window first — 156 of
   the 1199 sit inside 07-26→08-01.
3. Confirm the No. 12 window is fully screened and analyzed before drafting.

Then Sonnet tickets T1–T5 in docs/ROADMAP.md (archive month grouping;
Edition Plate v1; Signal Field v1; asset hygiene; executive readout). Fable
reviews rendered results of T2/T3 before regenerated output is committed.

## Recent completed work (compressed; details in DECISION_LOG.md)

- 2026-08-02/03: three data-loss defects fixed and 131 stranded articles
  recovered; 07-31 captured before its loss window closed; backlog drain
  reordered live-window-first; `scripts/reconcile_db.py` added and wired as
  a git merge driver so `pla_watch.db` reconciles by url instead of
  conflicting; CI schedule drift and no-op green runs measured and recorded.
  Landed and pushed as `0f963fa` on 2026-08-04.

- 2026-07-25: daily workflow outage diagnosed and fixed. Every scheduled
  run 2026-07-18→07-24 failed at "Commit updated database and site
  output": `ensure_editorial_derivatives()` used mtime staleness, but git
  checkouts don't preserve mtimes, so CI regenerated the five committed
  `site/assets/editorial/derivatives/*` files (different Pillow/platform
  bytes), dirtying tracked files and aborting `git pull --rebase`
  ("You have unstaged changes"). Fix: derivatives regenerate only when
  missing (`--force` to rewrite; committed files authoritative) and all
  workflow rebases use `--autostash`. First failing window was the first
  scheduled run after the 2026-07-17 reconciliation committed the
  derivatives. CI fix committed to main; No. 11 edition held separately
  (see Publication state).

- 2026-07-11: frontend pass (feed, Terms, Signals cross-promo, sitemap) and
  visual refinement pass (see Working tree above) — validation green, same
  9 historical warnings.
- 2026-07-10: identity language de-OSINT'd; "model-flagged" rename across
  all surfaces; methodology trust ladder; homepage latest-edition module;
  mobile header fix; focus-visible outlines.
- 2026-07-09: sidecar body backfill (sidecars canonical); shared Jinja env;
  issue numbering; date convention; print stylesheet; Chinese trail
  headlines; prev/next edition navigation.
