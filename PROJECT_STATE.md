# PROJECT_STATE — China Mil Watch / The PLA Watch

Updated: 2026-08-02 (reconciliation built, unmerged; origin/main missing 07-30→07-31).
State only — durable doctrine lives in CLAUDE.md and docs/ (see CLAUDE.md
table).

## Working tree (as of this update)

**Unpushed work holds the only copy of 80 articles.** HEAD is
`fix/pipeline-data-loss-2026-07-30` (`25cdb7f`), 2 ahead / 4 behind
`origin/main`. Local `main` is stale at `32c16f5`.

`origin/main` advanced independently while the branch sat local: billing
markers for 07-30 and 07-31, then "Daily update: 2026-08-01" (`1f0444a`)
and its run marker (`3c57e7f`). CI recovered unaided — consistent with the
monthly spend cap resetting on 08-01, not with any repair.

Production therefore holds **no articles for 07-30 or 07-31** (40 each,
local-branch only). `pla_watch.db` diverged on both sides from the same
base and both allocated article ids from 2727, so the two new sets collide
by id: git sees a binary conflict, and a plain merge silently drops one
side.

Reconciled by row-level merge, not by git — origin authoritative for
identity (its ids 2727–2753 are already published in `output/article/*.html`
and the sitemap), branch rows renumbered from 2754, 3 scrape_runs remapped,
117 analyses backfilled onto rows still pending in origin. Result: 2827
rows / 658 analyzed, continuous 07-29→08-01 coverage, and gates pass for
fk, integrity, duplicate urls, id drift, and url loss from either side.
**Not merged or pushed — awaiting analyst approval.**

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

**No. 12 is not safe to write from `origin/main`.** Its window holds five
of seven days in production (07-26→07-29, 08-01 = 173 articles); 07-30 and
07-31 are absent and live only on the unpushed branch. Reconciled, the
window is 253 articles. The relevant-article count reads 42 either way only
because the 80 recovered rows are still unscreened — at the 43.5%
historical pass rate they should yield roughly 35 more. Unlike the
No. 11-week gap, nothing flags this: the cadence sequence is unbroken and
the validator stays quiet, so the edition would rest on two-thirds of its
week without any warning. Land the reconciliation before drafting No. 12.

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

## Blocked until 2026-08-01 00:00 UTC — API spend limit

The account's configured API usage limit was reached on 2026-07-30 during
the backfills; all LLM calls return 400 until access resets. Consequences
and current state:

- **Recovered before the block:** 131 articles translated. **Remaining:**
  60 untranslated, 1,057 never-screened. Both backfill scripts are
  re-runnable and resume where they stopped.
- **2026-07-30 and 2026-07-31 collection are both captured** (40 articles
  each, stored unanalyzed). 07-31 was taken at 21:58 UTC on 07-31 via
  `.venv/bin/python pipeline.py --no-analysis`, closing the last window in
  which permanent loss was still possible. Do NOT rely on
  `ANTHROPIC_API_KEY=""`; see DECISION_LOG.
- **`--no-analysis` no longer regenerates `output/`** (DECISION_LOG
  2026-07-31 §1). The 07-31 capture, under the old behaviour, rendered the
  unreviewed methodology draft into `output/` — that regeneration was
  reverted and the behaviour fixed.
- **CI will fail its analysis stage until 08-01** but now persists whatever
  it scraped (new workflow step), so no further collection is lost.
- **No. 12 (week ending 2026-08-01)** needs 07-30/07-31/08-01 analyzed
  before it can be written. 07-30 and 07-31 will be unanalyzed backlog
  until access returns; the backlog reserve drains them, but check the
  window is complete before drafting.
- **14 articles sit with a translation but no summary** (`analyzed_at`
  cleared, so excluded from output and re-queued). They will be redone by
  the normal backlog drain after 08-01, re-translating in the process.

## Known issues / gaps (recorded, not explained away)

- **Analysis cap starved the backlog (fixed 2026-07-30; backfill running).**
  `DAILY_ANALYSIS_CAP` was 15 while runs scrape ~30/day, and the queue was
  `new + pending + unscored` truncated to the cap — so the slice never
  reached the backlog and it drained at **zero per run, permanently**.
  Result: **1,119 of 2,720 articles (41%) were never relevance-screened**,
  growing ~18/day for 66 days, and the 163 translation failures were never
  retried once. At the historical 44% pass rate the unscreened pile holds
  an estimated **~487 relevant articles** — so editions No. 1–11 drew on
  roughly 60% of the relevant material actually scraped. Fixed by
  `BACKLOG_RESERVE_FRACTION` (0.3) plus raising the cap to 40, above the
  scrape rate; `scripts/backfill_unscored.py` is clearing the pile.
  **Standing rule: the cap must stay above the daily scrape rate** — below
  it, a cost ceiling becomes a silent data-loss mechanism. Watch for the
  "newly scraped article(s) deferred by the cap" warning.

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

**After 2026-08-01 00:00 UTC, in this order:**

1. Check remaining headroom in the Console — the guard estimates cost, not
   headroom, and cannot do this step for you.
2. Resume the backfills **sequentially, not concurrently** (running both at
   once doubled the draw on 07-30):
   `.venv/bin/python scripts/backfill_translations.py --confirm-spend`
   (60 articles, est. $1.88), then
   `.venv/bin/python scripts/backfill_unscored.py --confirm-spend`
   (1,130 articles, est. $23.47). Both abort immediately on an
   account-level block and resume cleanly on re-run.
3. Confirm the No. 12 window (07-26→08-01) is fully analyzed before
   drafting.

Then Sonnet tickets T1–T5 in docs/ROADMAP.md (archive month grouping;
Edition Plate v1; Signal Field v1; asset hygiene; executive readout). Fable
reviews rendered results of T2/T3 before regenerated output is committed.

## Recent completed work (compressed; details in DECISION_LOG.md)

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
