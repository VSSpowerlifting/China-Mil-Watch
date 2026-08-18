# PROJECT_STATE — China Mil Watch / The PLA Watch

Updated: 2026-08-17 (MOD China root-caused and fixed; foundation released and
validated in production; run-475 persistence defect fixed on a local branch).
State only — durable doctrine lives in CLAUDE.md and docs/ (see CLAUDE.md
table).

## Defense Discourse foundation — RELEASED and validated in production

`404f3be` is on `origin/main`. The first genuine scheduled run against it,
**#476 / `31807724411`**, completed: migrations, verification, the 221-test
offline suite, the 55 reconciliation tests, pipeline (scrape run 112), output
validation, database+output commit, push, Pages deploy and success marker all
passed. The only red was the notify-only health gate, on the already-known MOD
China alarm. Independent verdict: **EXPECTED DEGRADED SUCCESS**.

Production after run 476: 3,250 articles / 3,250 distinct URLs / max id 3,256 /
112 runs / 5 sources / 1 desk / 4 institutions / 5 `source_run_results` / 1,110
analyzed / 2,142 category links. Ledger `0001`–`0005`; integrity `ok`; foreign
keys clean. All 3,211 pre-release URLs kept their ids, source slugs, hashes,
run attribution and analysis.

**MOD China is not failing collection any more, and that changes the diagnosis
recorded under Next tasks below.** Run 112 stored `ok_all_duplicates`:
7 discovered, 7 fetched, 7 extracted, 7 duplicates, 0 new, no error. The
scraper reaches the listing and parses it; everything it finds is already in the
corpus. The 35-day health alarm is therefore about **publication recency**, not
a broken adapter — the open question is why the listing keeps serving items we
already hold rather than why the fetch fails. Do not add it to `KNOWN_INERT`.

**Answered, and fixed — see the section below.** The listing was not serving
items we already held. It was serving MOD's own copies, which cross-source
canonical selection then discarded in favour of PLA Daily's reprint.

## MOD China — root-caused and fixed

Rulings in DECISION_LOG 2026-08-17. Two defects, neither in the adapter:

1. **Cross-source canonical selection.** The survivor of a same-title group was
   chosen by first URL path segment against a map of 81.cn section names, so
   MOD's `/gfbw/…` scored below PLA Daily's 要闻 and the Tier A ministry lost
   every duplicate to a Tier B reprint. Canonical choice is now a five-part
   **total** ordering — authority tier → source identity → 81.cn section →
   shorter URL → the URL itself — of which only the first is an editorial
   judgement. Because identity is compared before section, the 81.cn section map
   can only ever separate candidates from the same source.
2. **Discovery.** A listing link was kept only if the run date appeared verbatim
   in its text, so backdated items were invisible when stamped and ignored
   afterwards. Discovery now accepts the seven calendar dates ending on
   `target_date`, and takes the publication date from the stamp element MOD
   marks up (`<small class="time hidden-xs">`, `YYYY-MM-DD HH:MM`) rather than
   from any date found in the headline.

`scripts/cleanup_duplicates.py` ranks through the same shared key, so the
destructive tool cannot disagree with what the pipeline stored, and it refuses
any duplicate group containing a row whose source identity cannot be resolved.
Its `--dry-run` reads through a copy and cannot write to its input.

**Measured 2026-08-17** — a dated measurement, not a standing fact. Of 52 MOD
items published after 2026-07-10 and still on page 1 of the six configured
sections: **0** stored under `mod_china`, **40** stored under `pla_daily` at
81.cn URLs, **12** absent from the corpus. Ten of the twelve fall inside a
contiguous 2026-07-17 → 07-24 window in which no run executed at all, wider than
the seven-date window; two are backdating losses the window now catches.

Deliberately **not** done: no re-attribution of the 40 existing rows, no backfill
of the 12 absent ones, no change to the 21-day threshold, no `KNOWN_INERT` entry.
No historical rewrite of any kind has occurred.

Still open: canonical selection keeps one copy and discards the losing copies'
URLs, so "both institutions carried this release" is recorded nowhere. That is a
provenance-model question, not a dedup fix.

## Run-475 persistence defect — FIXED on a local branch, not yet pushed

Branch `fix/run475-persistence-gate` off `origin/main` (`3534a07`). One commit;
**nothing pushed, merged or deployed.**

Run 475 failed the pre-pipeline cleanliness gate (the offline suite had dirtied
`pla_watch.db`), skipped the pipeline, and the persist-on-failure step still ran
and pushed the residue as `483d154` under a message announcing a collection that
never happened. Proven logically neutral — identical `.dump`, 39 bytes on one
page — so the release stood, but the path was unsafe.

Fixed: persistence now requires positive proof the pipeline executed
(`steps.pipeline.outcome`), the commit message reports what actually happened,
the offending test reads a scratch copy instead of opening the WAL-mode tracked
database read-write, the collection-health table is printed after attribution so
the log matches the database, and the contract parser strips trailing comments.
Rulings in DECISION_LOG 2026-08-14; 34 new tests, suite 221 → 255. The
read-write guard is AST-based: the first attempt matched the literal
`sqlite3.connect(` and missed the aliased call that caused run 475.

## Defense Discourse foundation — Phases 1–2 complete, UNCOMMITTED on a branch

Branch `refactor/defense-discourse-foundation`, off `main` at `92bfa82`.
**Nothing is committed, pushed or deployed.** Full rationale in
`docs/ADR_NEUTRAL_CORE.md`; rulings in DECISION_LOG 2026-08-13.

What now works: sources come from `desks/china/manifest.json` instead of
hardcoded imports; the five existing scrapers are wrapped, not rewritten; every
source produces a structured per-source result so "published nothing" and
"could not be reached" are different values; one failing source degrades the
run; `source_run_results` records discovered/fetched/extracted/duplicate/new/
rejected counts per source per run; migrations are versioned, idempotent, and
run inside `init_db()` so the reconciler can no longer silently revert the
schema.

**Verified:** 109 offline tests pass (no network, no model calls);
`validate_output.py` green at the same 10 warnings; `output/` **byte-identical**
after regeneration from the migrated DB; corpus unchanged at 3,182 articles /
3,182 distinct URLs / max id 3188 / 110 runs, with an identical id↔URL digest
before and after migration.

**Two things this made visible that were previously invisible:**
`scripts/source_health_report.py` reports MOD China **overdue at 34 days**
against its own 21-day threshold, and Xinhua Military as **`not_implemented`**
rather than as a healthy source that published nothing.

**Working-tree state:** `pla_watch.db` carries migrations 0002–0004 (0001 was
already applied by the pushed hotfix). Migrations are additive; a pre-migration
backup was taken. `output/` is clean.

**Known blocker for Phase 4:** a Russia desk cannot be synced until a migration
relaxes `CHECK (language IN ('zh','en'))` on the legacy `sources.language`
column. Sync raises rather than coercing `ru` to `en`.

**Not done, deliberately:** no capture storage, no document versioning, no
translation records, no claims model (all Phase 3); no CI/workflow change; no
`reconcile_db.py` change; no MOD scraper fix; no public rename. `graphify
update .` has not been run for the new packages.

## Repository rename (hosting only)

The GitHub repo is now `VSSpowerlifting/China-Mil-Watch`; the old path answers
via a 301. Local `origin` was repointed 2026-08-13. No public site name, domain,
canonical URL or branding changed.

## Database hotfix pushed 2026-08-13

`scrape_runs.status` accepts `'degraded'` again on `origin/main` (`92bfa82`).
The constraint had reverted a **second** time — the 2026-08-09 migration was
reverted by a rebase, re-applied, and found reverted again by the 2026-08-13
audit. Until the Phase 1 branch lands, CI still never applies migrations, so
this can decay again; that is the argument for landing the branch.

## Working tree (as of this update)

**The No. 12 screening and CI's 08-04 run are merged and pushed.** Local
`main` is in sync with `origin/main` and the working tree is clean. The
reconciliation described below landed earlier and remains accurate history.
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

`output/` was byte-identical to `origin/main` at that point — the branch
never regenerated it. That is no longer true: see the output/DB divergence
under Known issues, found and fixed 2026-08-03.

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

13 editions published, No. 1–13: 2026-05-09 (pilot, 2-day window) through
2026-08-08. Issue numbers stored in sidecars, validated unique +
chronological. One cadence gap, by ruling — see below.

**No. 12 and No. 13 generated and published 2026-08-11**, clearing the
catch-up backlog that opened when credit ran out on 08-07:
- **No. 12**, w/e 2026-08-01, "Army Day, Scarborough Shoal, and a Week of
  Deliberate Disclosure", Significant, 7/7 days, 154 articles / 25
  model-flagged.
- **No. 13**, w/e 2026-08-08, "Scarborough Shoal, Platform Disclosures, and
  the Limits of Anniversary Week", Significant, 7/7 days, 134 articles / 11
  model-flagged.

Prerequisites cleared the same day: a scoped
`backfill_unscored.py --since 2026-08-02 --until 2026-08-08` run (43
processed: 24 analyzed, 19 rejected, 0 errors) and a full
`backfill_translations.py` pass (21 of 22 cleared; two JSON-parse failures
succeeded on re-run). The global 1095-article unscreened backlog was
**deliberately not** drained — it is ~$32 of screening for articles no
edition cites. Scope backfills to the publication window.

**Both editions were published without the EDITORIAL_QA_CHECKLIST
source-to-claim trace and without a rendered-page visual review.** Analyst
directed publication; recorded here so the gap is visible, not implied.
No. 12's `linkedin/2026-08-01.txt` is the mechanical fallback (the model
returned no `linkedin_version`), so it is template-assembled, not authored
prose. Rewrite before posting.

**Next edition: No. 14, week ending 2026-08-15.** There is no edition for
the week ending 2026-07-25 — analyst-ruled 2026-07-30, DECISION_LOG. The
2026-07-17→07-24 collection outage left that window with one observed day
of seven (07-25 only: 29 articles, 8 relevant, 0 model-flagged), and
retro-scraping was tested and rejected as unsound (07-16 control: 33
articles captured live, 3 recoverable). Expect and keep a **cadence-gap
warning** from the validator for this break; it is the record of the
outage, not a defect to suppress.

Both published windows read **0 unscreened** at generation time. The
07-26→08-01 window observed a **72% pass rate, not the historical 44%** —
the estimate assumed 44%, so actual spend was ~$4.55 against a $2.86
pre-flight. Treat 44% as a floor for recent windows when estimating.

**`id=2678` (Sichuan-ship layout piece, 07-28, relevance 0.85) is
permanently untranslatable.** Its `text_original` is 0 chars: the body was
never captured at scrape time, so this is a collection defect, not a
translation failure, and re-running the backfill will never clear it. It
also means the article passed relevance screening on its title alone —
worth investigating as a scoring-path question.
The site has been re-rendered and merged with CI's 08-04 run — `output/`
and the DB are in sync at 825 analyzed articles, 0 unrendered, 0 orphans,
gate green at the 9-warning baseline.

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

`validate_output.py`: **passes, 10 warnings** — 9 historical, ruled on
2026-07-09/10 (missing LinkedIn files eds. 1–3; undated early trail
entries; related notes). Do not fix by invention; explain any NEW warning
here.

The 10th is **`cadence gap: 2026-07-18 → 2026-08-01 is 14 days`** — real
history, not a defect: no edition shipped for week ending 2026-07-25 during
the API-credit outage. It is a data fact and stays until an edition exists
or the check learns about publication gaps. Not introduced by the veil work
(that pass added no warnings).

## API credit exhausted — RESOLVED 2026-08-11

**Credit was restored in the Console on 08-11**; the backfills and both
edition generations ran clean with no account-level block. The 08-08 and
08-09 collections that CI recorded as billing failures were screened
retroactively as part of the No. 13 window. History below is kept as the
outage record.

The block ran 08-07 → 08-11. It was a credit balance exhaustion
(`invalid_request_error: "Your credit balance is too low to
access the Anthropic API"`), not the 07-30 configured usage limit — a monthly
reset would not have cleared it. Restoring credit in the Console is a manual
step nothing in the repo can do.

| run | date | new | analyzed | recorded as |
|---|---|---|---|---|
| 105 | 08-07 | 36 | 24 | `completed` + "mark daily run" — **wrong, see below** |
| 106 | 08-08 | 23 | 0 | `completed` + billing marker |
| 107 | 08-09 | 29 | 0 | `completed` + billing marker |

Run 105 exhausted credit mid-run and still exited 0, so 08-07 published as a
clean day and the marker never reached `origin/main`. Fixed 2026-08-09
(DECISION_LOG); the audit trail for 105 stays wrong as history.

**Verified still blocked 2026-08-09 14:5x UTC** via
`spend_guard.probe_api_access()` — same `invalid_request_error`, fresh
request_id. The key authenticates (a bad key returns 401
`authentication_error`, not this), so the credit has not reached the org or
workspace this key belongs to. **Note CI uses a repo secret, not `.env`** —
if those are different keys, funding one does not fix the other.

Re-test, free, no tokens billed:
```
.venv/bin/python -c "import sys; sys.path.insert(0,'.'); \
from scripts.spend_guard import probe_api_access; \
ok,msg=probe_api_access(); print('OK' if ok else 'BLOCKED'); print(msg)"
```

**To recover:** restore credit, then re-run the workflow via
`workflow_dispatch` — a manual run deliberately bypasses the marker guard.
The 52 articles collected across 08-08 and 08-09 are stored and unscreened;
they re-enter the queue as backlog.

## API spend limit — block lifted 2026-08-01 (superseded by the above)

The account's configured API usage limit was reached 2026-07-30 during the
backfills; all LLM calls returned 400 until the monthly reset. The block has
lifted and daily collection ran normally on 08-01, 08-02 and 08-03. Current
state and durable consequences:

- **Corpus as measured 2026-08-04 (after merging CI 08-04):** 2914
  articles, **1043 never screened** (36%), **61 relevant but untranslated**,
  0 translated-without-summary. The No. 12 window accounts for the drop from
  1199; the untranslated count rose by 3 because the scoped run produced 1
  translation-failure and 2 summary-failures, which stay unwritten by design
  and re-queue. Both backfill scripts are re-runnable and resume where they
  stopped — the DB is the checkpoint (`passed_relevance IS NULL`), there is
  no checkpoint file.
- **The unscored backlog drains at zero while translations are stuck
  (measured 2026-08-04).** `backlog = pending + unscored` puts every
  relevant-but-untranslated article ahead of every unscored one, so with 80
  pending against a ~21-slot reserve the 08-04 CI run screened 34 new articles,
  cleared 22 pending, and drained **0** of the 1,199 — the unscored count did
  not move. Self-clearing, not permanent: pending fell 80 → 58 in one run and
  empties in ~3 more, after which the reserve reaches the backlog at ~16-21/day.
  Running `backfill_translations.py` clears pending immediately and is the
  cheapest way to restart the drain — it also unblocks the No. 12 window.
- **The DB reconciler discarded 46 relevance decisions (fixed 2026-08-04).**
  Rejections and translation/summary failures leave `analyzed_at` NULL, and the
  backfill predicate tested that column instead of `passed_relevance`. Fixed,
  plus a new gate that fails the merge when either side's decision is missing.
  See DECISION_LOG 2026-08-04. **Check `passed_relevance IS NULL` counts before
  and after any DB merge.**
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
  `curl -sL "https://api.github.com/repos/VSSpowerlifting/China-Mil-Watch/actions/runs?per_page=8"`
  (The GitHub repository was renamed `PLA-Watch` → `China-Mil-Watch`. The old
  path still answers via a 301, so `-L` is required if you use it; the local
  `origin` remote was repointed at the new URL on 2026-08-13. This is a hosting
  rename only — no public site name, domain, or URL changed.)

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

0. **Automatic Signal Veil is live** (2026-08-11/12). Eight editions carry an
   automatic veil from their own cited article, three carry curated images,
   and 2026-05-30 is text-led because no image in its trail passes the
   provenance guard. Full-strength treatment for both classes.

   Open: whether a PRC state-media photograph belongs on-page as atmosphere
   at all (V&M §2 permits it; credit renders). The No. 13 briefing frame is
   the busiest of the set — route a curated manifest entry for any edition
   whose frame is too heavy; curated always wins over the automatic path.

   Covers for the four corrected editions were regenerated 2026-08-12; every
   cover background now comes from its own edition or the abstract gradient
   (2026-05-30). The cross-edition `media_dir_fallback` is retired.
0b. **Retro-QA No. 12 and No. 13.** Both shipped without the
   EDITORIAL_QA_CHECKLIST source-to-claim trace (analyst-directed). Run the
   trace against the live pages and correct by re-render, not hand-edit.
   Rewrite `linkedin/2026-08-01.txt`, which is the mechanical fallback.
1. **~1050 unscreened articles remain outside the published windows.**
   Not urgent — no edition cites them — but they are the same defect class
   that stranded 131 articles in July. Drain in scoped chunks when spend
   allows: `backfill_unscored.py --since X --until Y --confirm-spend`,
   sequentially, never concurrently (running two at once doubled the draw
   on 07-30). *Re-measure before estimating — these move every run.*
2. **MOD China (国防部) — collection is failing, the scraper is not.**
   Investigated 2026-08-09. Run by hand it works perfectly: `target_date`
   2026-07-26 returns 3 URLs, 2026-08-08 returns 1, all six sections fetch
   (~48KB each), `parse_article` yields correct titles, dates and bodies.
   **None of those articles are in the DB at all** — not even as
   keyword-rejected rows, which are stored with `passed_relevance=0`. So CI's
   scrape returned nothing on days when the articles were live and reachable.
   Not total: CI collected MOD successfully 11 times through 2026-07-10.
   Cause still unknown — candidates are transient reachability from Actions
   runners to a plain-`http://` host, or listing-CDN lag against the
   exact-date match. **Do not add it to `KNOWN_INERT`: the source is alive.**
   `failed_fetches` instrumentation now records exhausted retries into
   `scrape_runs.errors`, so the next CI run answers this directly. Check
   there first before changing scraper logic.

   If it turns out to be CDN lag, the fix is a lookback window (match
   `target_date` **and** the day before) rather than exact-date-only. That was
   deliberately **not** done now: it raises collection volume, and volume is
   spend. Diagnose first, then widen.

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
