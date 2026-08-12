# DECISION_LOG — China Mil Watch

Newest first. Record decisions that constrain future work.

## 2026-08-11 — Signal Veil falls back to the edition's own source photograph

Editions Nos. 11–13 shipped with no in-page imagery at all. Cause: the
2026-07-11 ruling demoted cover PNGs to og:image duty in favour of Edition
Plates (ROADMAP T2), commit `36510bb` executed the removal, T2 was never
built, and curated veil coverage stopped after No. 10 — leaving the identity
slot empty for nine of thirteen editions.

1. **The Signal Veil now resolves in two tiers**, via a single
   `veil_for_edition()` in `scripts/pw_env.py` shared by the generate and
   rerender paths: curated manifest entry first, then the photograph
   `scripts/fetch_article_image.py` already pulled from the edition's own
   cited article, then the text-led fallback. Nine editions gain imagery;
   Nos. 8–10 keep their curated images unchanged.
2. **This is the V&M §2 "source photographs" class, not the curated
   library.** The PD/CC0/CC BY allowlist in `fetch_editorial_image.py`
   governs the curated library and is untouched. Source photographs are
   permitted by policy as in-edition context, verbatim from the cited
   article, and carry the mandatory credit + "context, not evidence" line
   already rendered by the templates.
3. **Association stays exact-URL, never topical.** The image comes from an
   article in the edition's own source trail, matched back to it by
   normalized URL for its credit. The 2026-07-12 prohibition on
   category/thread matching is unaffected — no search, no inference, so an
   image still cannot drift onto the wrong story. A miss at any step
   (no metadata, no derivative, no `article_url`) yields None, not a guess.
4. **Automatic veils render quieter than curated ones**
   (`.card-veil--source`, `.nd-veil--source`). A curated image is chosen for
   composition; an auto-fetched briefing frame carries its own signage and
   captions, which must never compete with the edition's prose. Damped
   opacity and a tighter right-anchored mask are the standing treatment, and
   `mask_focus` stays centre-weighted — per-image focus tuning on uncurated
   photography is how the V&M §2 misleading-crop rule gets broken.
5. **The validator gained a source-veil provenance check** rather than an
   exemption: a `src-*` id must resolve to real fetch metadata, an existing
   derivative, and an `article_url` linked on the page. "Manifest-only" as a
   validation rule is replaced by "provenance-verified", which is stricter
   for this class.
6. **T2 (Edition Plate) is not superseded.** It remains the deterministic
   identity for editions with no usable photograph, and is specified in
   `docs/T2_EDITION_PLATE_SPEC.md`. Open question D2 there — whether the
   plate or the veil owns the index card when both exist — is now answered
   for the veil-present case: the veil wins.

## 2026-08-11 — Sidecar prose may be edited for style, never for substance

Analyst directed an em-dash cleanup and a humanizer pass on No. 13 before
publication. That required editing `output/the-pla-watch/posts/2026-08-08.json`
directly, against the standing "no casual edits, ever" rule for sidecars. The
rule stands; this is the narrow exception and its conditions:

1. **Only on explicit analyst instruction.** Never as cleanup an agent decides
   to do on its own initiative.
2. **Authored prose fields only** — `dek`, `signal`, `opening_note`,
   `what_stood_out`, `why_it_matters`, `what_was_routine`,
   `term_to_know_explanation`, `what_im_watching_next`. **`source_trail` is
   off-limits.** Its em dashes sit inside outlet names and article titles,
   including Chinese, which are source-derived text under the no-invention
   rule. The 08-08 pass left all 8 trail entries byte-identical, deliberately.
3. **Punctuation and sentence boundaries only.** No claim, number, name, date,
   unit, or quoted official language may change. The 08-08 pass preserved
   `"null and void"`, `"Model of the Era"`, `"Most Beautiful Soldiers"` and the
   Junsheng attribution verbatim.
4. **Mechanically verified, not eyeballed.** Every replacement asserts its
   target matches exactly once and aborts otherwise; a sentence-level diff
   against a pre-edit copy confirms only intended fields moved. A partial
   string match silently corrupting the canonical record is the failure mode
   being defended against.
5. **Re-render, then re-run the gate.** The sidecar is the record; the HTML is
   derived and must be regenerated from it.

Method note: fixing em dashes *first* and running the humanizer *second*
introduced a defect the second pass then caught — an em-dash replacement
created the staccato fragment "That caveat matters.", which is itself a
flagged pattern (§31). Run the style passes together, or expect the second to
clean up after the first.

## 2026-08-09 — A run that keeps publishing must still be able to raise an alarm

1. **The 2026-08-07 credit exhaustion published as a clean day.** Run 105 hit
   `invalid_request_error: credit balance is too low` after analyzing 24 of 36
   articles. Because some work landed, `account_block_total_failure` was False,
   the pipeline exited 0, the site deployed, and step 8 committed *"State: mark
   daily run 2026-08-07"*. Nothing in the repo said otherwise until run 106 the
   next day analyzed zero articles and tripped the total-failure path. The
   outage was two days old when found.

2. **Three independent mechanisms each did the right thing and the day still
   went unnoticed.** `pipeline.py` wrote the billing marker (it fires on any
   account block, partial or not). The workflow's marker-commit step was gated
   on `failure()`, so it never ran. Step 6 stages only `pla_watch.db output/`,
   so the marker died with the runner. Each piece was locally correct; the seam
   between them leaked.

3. **Standing rule: partial degradation must be recorded in a place that
   survives the runner, and must be loud.** Publishing through a partial
   failure is correct and stays. But "kept publishing" is not "was fine," and
   the audit trail has to distinguish them. Concretely: `scrape_runs.status`
   gains `'degraded'` and `complete_scrape_run()` is always passed an explicit
   status; the marker-commit step runs on `always()`, guarded by a working-tree
   diff so it is a no-op on clean days.

4. **The alarm runs last, and only notifies.** A new Health gate step sits
   after deploy and after the success marker, so it can never block a publish
   that was otherwise fine. Its sole purpose is to fail the run so GitHub's
   notification reaches a human. Anything that wants to stop a deploy belongs
   in `validate_output.py`, not here.

5. **Corollary: a green run is evidence of nothing unless something is checking
   liveness.** MOD China last produced on 2026-07-10 and was silent for four
   weeks without a single failed run, because PLA Daily supplies ~87% of
   articles and the totals never moved. `scripts/check_source_liveness.py` now
   fails the gate on any active, non-inert source silent past a threshold.
   Acknowledging silence means adding the slug to `KNOWN_INERT` **with a
   reason** — a deliberate, reviewable act, not a config toggle.

6. **An empty scrape had two meanings and recorded neither.** `get_article_urls()`
   catches listing-page fetch failures per section, logs a warning and
   continues, so "published nothing today" and "could not reach the site"
   both produced `[]`. `BaseScraper.failed_fetches` now records URLs whose
   retries were exhausted and the pipeline appends them to
   `scrape_runs.errors`. **Standing rule: when a stage can return empty for
   both a normal and a defective reason, it must record which.**

7. **The DB reconciler merges rows, not schema — a migration does not survive
   a merge from origin.** Found the hard way while landing this work: after
   `scripts/migrate_status_degraded.py` relaxed the `scrape_runs.status` CHECK
   and the change was committed, rebasing onto `origin/main` reverted it. The
   driver reconciles article and run *rows* and takes the published side's
   file, so origin's older schema came back wholesale with no conflict, no
   warning, and a correct-looking row count. Had it gone unnoticed, CI's first
   `'degraded'` write would have thrown `IntegrityError`.

   **Standing rule: a schema migration must be re-applied and re-verified
   AFTER the final rebase, immediately before pushing — never only before.**
   The check is one line:
   `sqlite3 pla_watch.db "SELECT sql FROM sqlite_master WHERE name='<table>';"`
   Migration scripts must be idempotent so this is always safe to repeat.

8. **Liveness thresholds are per-source, and set from the source's own
   publishing rate.** A flat 7-day rule marks a source that genuinely
   publishes twice a month as dead every other week, and an alarm that cries
   wolf is worse than no alarm. `SILENCE_THRESHOLD_DAYS` overrides the
   default per slug; MOD China sits at 21d, measured from 28 distinct publish
   dates across three months on its own listings — deliberately measured from
   the *source*, never from our collection, which is the thing under test.

## 2026-08-04 — A screening decision is data, and the reconciler must carry it

1. **The DB reconciler silently discarded 46 relevance decisions.** Its
   analysis backfill fired only on `l.analyzed_at IS NOT NULL`, but a relevance
   *rejection* writes `passed_relevance` and leaves `analyzed_at` NULL — as do
   translation and summary failures. Merging `origin/main` into a branch that
   had just screened the No. 12 window returned 43 rejections and 3 failures to
   the unscored pool. Caught only because the window was measured immediately
   after the merge and read 46 unscreened where it should have read 0.

2. **Every gate passed while it happened.** The merge kept every article, every
   URL and every id — the existing gates check exactly those. A reverted row is
   byte-indistinguishable from one that was never screened, so nothing could
   see it. **Standing rule: a decision that cost a paid call is data, and the
   reconciler must be gated on decisions, not just on rows and ids.**

3. **Two costs, both silent.** The scores and reasonings are the audit record
   the project preserves verbatim (see `backfill_translations.py`), and the
   articles return to the queue to be screened and paid for a second time, with
   no guarantee the second answer matches the first.

4. **Corollary: verify the domain invariant after any DB merge**, not just that
   the merge exited clean. `passed_relevance IS NULL` counts before and after
   are the cheap check.

## 2026-08-03 — The deploy gate compares the DB to output/, not output/ alone

1. **A site missing a sixth of its analyzed corpus passed the gate four times.**
   The 07-30 translation backfill wrote 117 analyzed articles to
   `pla_watch.db`; the reconcile merge driver carried them onto `main`; nothing
   re-rendered. `validate_output.py` checks 1–7 all read `output/` in
   isolation, so the shortfall was invisible to it and to CI, and 117 articles
   stayed unpublished through every deploy from 07-30 to 08-03. Measured
   2026-08-03: 672 analyzed in the DB, 555 rendered pages, gap constant at 117
   across `a1fff19`, `778d597`, `0f963fa` and `ffb5bf1`.

2. **The gap is structural, not a one-off.** Any path that writes the DB
   without re-rendering reproduces it: the two backfill scripts, a reconcile
   merge, or a hand-merge of two DB lineages. The daily pipeline is not the
   guard — it renders correctly from whatever DB its own runner holds (verified
   in sync at `db71841`: 555 analyzed, 555 pages), so rows arriving by any
   other route are simply never drawn.

3. **Standing rule: a validator that reads only generated output cannot
   certify that output is complete.** `validate_output.py` check 8 now compares
   analyzed articles in the DB against rendered pages. Analyzed-but-unrendered
   is **fatal** (it is always a defect, and `site/generator.py` fixes it in one
   command); rendered-but-not-in-DB is a warning (the generator prunes stale
   pages itself). The check skips when the DB is absent or a non-default output
   dir is passed, so validating a copied or deployed tree still works.

4. **Corollary for backfills: re-render before calling one done.** A backfill
   that only writes the DB has published nothing. Run `site/generator.py` and
   the gate afterwards, in that order.

## 2026-08-02 — The backlog is drained live-window-first, not FIFO

1. **Plain FIFO buries exactly the articles an edition still needs.** Both
   backlog queries in `storage/db.py` ordered by `id`, so a deferred article
   joined the back of a ~1,180-deep queue draining ~18/run. Measured on the
   reconciled database: the recovered 07-30/07-31 articles sat at queue
   position 1,178 — **66 runs**, roughly two months — so they could not be
   screened in time for edition No. 12, the edition covering their own week.
   Meanwhile the whole 30% backlog reserve was spent on May and June material
   that no unwritten edition can use. **Standing rule: recency-critical
   material is screened before archive material.**

2. **`LIVE_BACKLOG_DAYS` (default 14) splits the unscored queue.** Articles
   scraped within the window go first, oldest-first among themselves so a week
   fills chronologically; everything older keeps FIFO behind them. Same
   measurement after the change: position 168, **10 runs**. The archive is
   deferred, never starved — once the live tier drains, FIFO resumes as before.
   14 days covers the current edition window plus a week of slack for a late
   draft.

3. **`pending` (passed relevance, analysis unfinished) keeps absolute
   priority.** It is small — 74 rows — and those articles have already paid for
   a relevance call, so finishing them is the cheapest analytical output
   available. The live/archive split applies only to `unscored`.

4. **The ordering fix does not rescue edition No. 12 by itself.** Ten runs is
   still ten days. 156 articles in the No. 12 window remain unscreened; a
   one-off catch-up run costs ~$2.82 (screen all 156 at Haiku ~$0.30, analyze
   the ~68 expected to pass at Sonnet ~$2.52). **Structural fixes prevent the
   next occurrence; they do not repair the current one.**

## 2026-08-02 — git cannot merge `pla_watch.db`; reconcile by url, with origin authoritative for identity

1. **A diverged `pla_watch.db` must never be resolved by git.** CI writes the
   database to `main` on a schedule while humans work on local branches, so
   both sides routinely advance from one base. Git sees a binary file and can
   only offer "take mine or take theirs" — and either choice silently destroys
   a day of collection. On 07-30→31 both sides had independently allocated
   article ids from 2727, so origin's article 2731 and the branch's 2731 were
   **different articles**; nothing in `git status` shows that, and either
   resolution loses 40 or 80 articles. **Standing rule: reconcile by `url`
   (the table's UNIQUE key), never by id, and never with a merge driver.**
   `scripts/reconcile_db.py --from-git` does this and re-derives its inputs
   from refs, so it stays correct after CI advances `origin/main` again.

2. **Origin is authoritative for identity; local rows are the ones that move.**
   Origin's ids are already published as `output/article/<id>.html` and
   referenced by the sitemap and feed, so renumbering them breaks live URLs.
   Local capture rows have never been rendered — `--no-analysis` does not
   generate the site (07-31 ruling 1) — so they are the safe side to
   renumber. The merge is therefore deliberately asymmetric, and the
   no-id-drift gate enforces it.

3. **A reconciliation is not landed until its gates pass.** The script exits
   non-zero unless foreign keys, integrity, duplicate urls, id drift, and url
   loss *from both sides* all check out. A merged database that loses a row
   from either parent is a failed merge, not a compromise.

4. **The 07-31 coverage disclosure overstated edition completeness.**
   `methodology.html` told readers editions No. 1–11 drew on "about
   three-fifths" of the relevant material. By the method the passage itself
   states — applying the historical relevance-pass rate to what was never
   screened — the figure is 534 analyzed against ~1,184 estimated relevant
   (697 known + 43.5% of 1,119 unscreened), i.e. **a little under half**.
   Three-fifths would require the unscreened backlog to pass relevance at
   ~17% against 43.5% observed. Corrected, and the method is now stated
   explicitly rather than gestured at. **Standing rule: a published
   completeness figure carries its derivation.**

5. **This is the fourth divergence of this shape**, after the 07-12→16
   uncommitted passes, the 07-17 reconcile, and local `main` drifting 10 CI
   commits behind on 07-30. The recurrence is structural, not careless: a
   mutable binary committed to git and written by two authors cannot be
   made safe by discipline alone. **Resolved by ruling 6 rather than by
   asking people to remember.**

6. **The reconciliation runs as a git merge driver.** `.gitattributes` maps
   `pla_watch.db merge=reconcile-db`, and `reconcile_db.py --merge-driver`
   implements it, so `git merge` performs the row-level reconciliation instead
   of raising a binary conflict. Verified by replaying the 07-30→31 merge: the
   driver resolved it unaided, 0 conflicts, and produced digest `b80e813b` —
   identical to the hand-resolved result.

7. **The published side is identified by content, never by ours/theirs.** The
   merge is asymmetric, but git's ours/theirs says nothing about which side is
   published: merging `origin/main` into a branch makes origin *theirs*, and
   merging a branch into `main` makes it *ours*. Reading identity off position
   would, half the time, renumber the published side and silently repoint every
   `output/article/<id>.html`. The driver hashes both candidates against the
   blob at `origin/main` instead — which is also correct under rebase, where
   ours/theirs invert again. **If neither side matches, the driver refuses and
   leaves a normal conflict.** Guessing at identity is worse than conflicting.

8. **`.gitattributes` names a driver but cannot define one**, so every clone and
   every CI runner must run `--install-driver` once or the mapping silently
   degrades to a binary conflict. The daily workflow registers it after Python
   setup (the script imports only the standard library, so it needs no
   dependencies). The interpreter comes from `sys.executable`, not a hardcoded
   `.venv/bin/python` — CI has no `.venv`, and a fixed path would leave the
   unattended case, where a conflict is most expensive, unprotected.

## 2026-07-31 — An uncommitted template is not a publish guard; account-level API failure is not an article-level one

Four rulings from hardening the pipeline after the 07-30 spend incident.

1. **Leaving a template uncommitted does NOT prevent it from publishing.**
   The 07-30 session left the methodology coverage disclosure as an
   uncommitted working-tree diff, reasoning that an uncommitted file cannot
   reach production. That reasoning is wrong. `site/generator.py` renders
   from the **working tree**, and CI commits `output/`. A scrape-only
   capture run on 07-31 rendered the unreviewed draft straight into
   `output/methodology.html`; had that run been CI, the draft would have
   published. **Standing rule: the only thing that keeps unreviewed copy
   off the site is not rendering it.** `--no-analysis` now skips site
   generation entirely, for this reason and because regenerating from a
   knowingly-incomplete DB rewrites the public record from a partial view.

2. **`DAILY_ANALYSIS_CAP` 40 → 55 (analyst-approved).** The sizing rule is
   now explicit: fresh scrapes get `(1 - BACKLOG_RESERVE_FRACTION) × cap`
   slots, so break-even against a scrape rate S requires
   `cap ≥ S / (1 - reserve)`. Measured intake is 32–40/day (avg ~37) over
   07-26→07-31, so at a 0.3 reserve break-even is 37 / 0.7 ≈ 53. **40 was
   still below it** — the 07-30 run deferred 9 fresh articles. At 55 the
   deferral warning goes silent at typical intake and ~18 slots/run drain
   the backlog (~63 days for the current 1,130).

3. **An account-level API failure must abort the run, not iterate.** When
   the spend limit hit on 07-30, nothing distinguished "this article
   failed" from "the account is blocked", so the pipeline made 40 further
   doomed calls and the translation backfill made 60. `FatalAPIError` now
   marks account-level failures (401/402/403, or a message naming a usage
   limit, credit balance, billing, or quota) and every caller aborts the
   batch on it. **429 is deliberately NOT fatal** — rate limits are
   transient, and aborting on them would be a regression. The billing
   marker now keys off this definitive signal rather than inferring
   credit exhaustion from "everything failed".

4. **Never write a record that satisfies the writer but violates the gate.**
   The 07-30 session fixed the blank-summary bug in the backfill scripts
   only; `pipeline.py` still wrote `analyzed_at` on any article with a
   translation, regardless of summary. That is the same defect that
   produced 14 damaged rows. The pipeline now requires a non-empty summary
   before marking an article analyzed; without one it stays pending and
   retries.

**Spend pre-flight (`scripts/spend_guard.py`).** Both backfills now
estimate cost from token arithmetic and current published prices, probe
API access with one cheap call before spawning workers, and require
`--confirm-spend` above $5. **The honest limit: the API exposes no
remaining-balance endpoint, so this checks cost, never headroom.** Only
the Console can answer "can I afford this?" — the guard's job is to make
the number visible and acknowledged instead of felt. Verified live against
the active block: the probe caught it and aborted at zero article calls.
Remaining work is estimated at **~$25** (60 translations ≈ $1.88;
1,130 screenings ≈ $23.47), against the ~$50 that was guessed on 07-30.

## 2026-07-30 — No edition for week ending 2026-07-25; the collection gap is recorded, not filled

**Ruling (analyst-approved 2026-07-30): no edition is published for the week
ending 2026-07-25.** The next edition is **No. 12, week ending 2026-08-01**,
on a full seven-day window. Issue numbering stays sequential; the cadence
breaks, and the break is the honest record.

1. **The window has one observed day of seven.** `scrape_runs` jumps from
   run 90 (2026-07-16) straight to run 91 (2026-07-25) — there are no run
   rows at all for 2026-07-17→07-24. The No. 12 window (07-19→07-25) holds
   only 2026-07-25: 29 articles, 8 relevant, 0 model-flagged.
2. **Correction to the 2026-07-25 entry below.** That entry describes the
   outage as scheduled runs failing at "Commit updated database and site
   output." True as far as it goes, but the consequence was understated:
   the runs' DB writes were never persisted either, so the articles for
   those eight days were never captured. The loss is permanent, not merely
   uncommitted.
3. **Backfill was tested and rejected as unsound.** `pipeline.py --date
   <d> --dry-run` retro-scrapes only what the listing pages still surface,
   and recall decays with age. Control: 2026-07-16 was captured live at
   **33 articles**; retro-scraped on 2026-07-30 it yields **3**. Gap dates
   yield 7 (07-20) and 11 (07-24) against a ~35/day live baseline.
   Recovering a recency-biased 10–30% of each day and presenting it as the
   week's observed record would misstate coverage. Standing rule: the
   scraper is listing-bound and **retro-scrape output is never a
   substitute for live collection** in an edition's evidence base.
4. **The cadence-gap warning from `validate_output.py` is expected and
   correct.** Do not suppress it. It is the artifact that records the
   outage; a future reader must be able to see that the week was
   unobserved rather than uneventful.

## 2026-07-30 — API spend limit reached mid-backfill; collection must survive analysis failure

The backfills exhausted the account's configured API usage limit (access
returns 2026-08-01 00:00 UTC). 131 articles were recovered before it hit;
60 translations and 1,057 screenings remain. Three durable lessons, two of
them fixes.

1. **Cause, recorded plainly.** The backfill was authorized on a ~$50
   estimate that was never checked against the account's *remaining*
   headroom on its monthly cap, and the two backfills were run
   concurrently rather than in sequence, doubling the draw. Estimate the
   spend *and* verify headroom before starting a bulk run; run bulk jobs
   one at a time.
2. **CI discarded collection on any pipeline failure — now fixed.**
   `pipeline.py` stores scraped articles before its first LLM call, then
   `sys.exit(2)` on total analysis failure. The "Commit updated database
   and site output" step carries an `if:` with no status function, so
   GitHub implicitly requires `success()` and skipped it — destroying the
   runner with that day's articles still inside. **This is the same
   mechanism that lost 2026-07-17→24**, reached from a different trigger:
   the earlier fix addressed the rebase and derivative churn, not the
   underlying "analysis failure forfeits collection" behavior. New step
   `Persist scraped articles (if pipeline failed)` commits `pla_watch.db`
   **only** — `output/` is deliberately excluded so this cannot become a
   route around the validator gate that keeps a broken render out of
   production. Unanalyzed articles keep `passed_relevance` NULL and drain
   as backlog.
   **Standing rule: collection and analysis are separate stages, and a
   failure in the second must never forfeit the first.**
3. **`pipeline.py --no-analysis`** scrapes and stores without any LLM call,
   for use during an outage or spend block. Note `ANTHROPIC_API_KEY=""`
   does *not* achieve this — `config.py` pops an empty value and falls
   back to `.env`, so the run attempts analysis anyway. 2026-07-30 was
   captured (40 articles) before this flag existed, via a run that failed
   every analysis call.
4. **A blank summary must block the write, not the deploy.** The first
   backfill run kept translations when `summarize()` failed, on the theory
   that a translation is the expensive part. That produced 14 records that
   read as complete but tripped `validate_output.py` rule 6 ("no analyzed
   article has a blank summary") and **failed the deploy gate**. Both
   backfill scripts now treat a missing summary as a reason not to write
   at all, leaving `analyzed_at` NULL for a clean retry. The 14 were
   repaired by clearing `analyzed_at` (translations preserved), which
   removed them from generated output and re-queued them; validator back
   to green at the 9 historical warnings. Rule: never write a record that
   satisfies a script's notion of "good enough" but violates the deploy
   gate's — the gate is the contract.

## 2026-07-30 — The analysis cap sat below the scrape rate; 41% of the corpus was never screened

**The largest of the three 2026-07-30 findings.** 1,119 of 2,720 articles
(41%) had `passed_relevance IS NULL` — never evaluated for relevance at all,
so invisible to every edition and to every count of what the corpus contains.

1. **Mechanism: a starved queue, not a slow one.** `pipeline.py` built
   `queue = new_queue + pending + unscored` and truncated it to
   `DAILY_ANALYSIS_CAP` (15). Every run inserts ~28–35 fresh articles, so
   `new_queue` alone always overflowed the cap and **the slice never reached
   the backlog** — it received exactly zero slots per run, permanently. The
   comment above that code claimed the backlog "drains every run to fill
   capacity… can't stay invisible forever." That claim was false for the
   entire life of the project, and its presence is why the behavior went
   unexamined. Corrected in place.
2. **Two compounding consequences.** (a) The 163 translation failures were
   never retried even once — `pending` was starved by the same slice, which
   is why article id 3 sat unretried for 83 days despite a retry path that
   looked correct on inspection. (b) The unscored pile grew by
   `inserted − cap` ≈ 17–18/day: 1,119 over 66 days, matching the arithmetic
   almost exactly.
3. **Scale of the editorial gap.** At the historical relevance pass rate of
   **44%** (697 of 1,601 scored), the unscreened 1,119 contain an estimated
   **~487 relevant articles** — against 697 relevant articles known. Taken
   with the translation losses, editions No. 1–11 drew on roughly 60% of the
   relevant material actually scraped. No published claim about weekly
   coverage completeness survives this unqualified.
4. **Fixes (analyst-approved 2026-07-30).**
   - `BACKLOG_RESERVE_FRACTION` (0.3): the backlog now gets a guaranteed
     share of the cap instead of zero, and unused new-article slots spill
     to it. This makes the "can't stay invisible forever" claim true.
   - `DAILY_ANALYSIS_CAP` **15 → 40**, above the ~30/day scrape rate. A cap
     below the scrape rate guarantees unbounded backlog growth regardless of
     any reservation — the reservation controls *who* is starved, not
     *whether*.
   - New warning when the cap defers freshly scraped articles. Sustained
     firing means the cap has fallen below the scrape rate again; treat it
     as a capacity alarm, not noise.
   - `scripts/backfill_unscored.py` clears the 1,119. Unlike
     `backfill_translations.py` it **does** run relevance scoring, since
     these articles have no prior score to preserve.
5. **Standing rule: `DAILY_ANALYSIS_CAP` must exceed the daily scrape rate.**
   It is a cost ceiling, and setting a cost ceiling below the intake rate
   silently converts it into a permanent data-loss mechanism. If cost
   requires a lower cap, reduce intake (narrow sources or the keyword
   filter) rather than letting unprocessed articles accumulate unbounded.

## 2026-07-30 — Translation fix: two independent failures, not one

Correction to the diagnosis entry below, which named only the token cap.
Clearing the backlog surfaced a **second, unrelated** failure; both are now
fixed and the entry below stands as the record of the first.

1. **Unescaped inner quotes (genuine formatting drift).** The translation
   prompt instructs the model to preserve quoted rhetorical language
   ("决不", 「」), and a literal `"` inside a JSON string value terminates
   the string early. Example (article 2624): `the border soldier's "pure
   love."` — parse failed at position 1455 of a **complete, untruncated**
   31,132-character response. This is a different bug from the token cap
   and would have persisted after fixing it alone.
2. **Fix: forced tool use for translation.** `Analyzer.translate()` now
   calls `_call_tool()` with an `emit_translation` tool
   (`title_en` / `body_en`) and `tool_choice` pinned to it. Tool inputs are
   serialized and escaped by the API and arrive pre-parsed, so the entire
   class of escaping failure is gone. The translation prompt no longer
   asks for raw JSON. `_parse_json` now serves only the three short-output
   tasks (relevance, summary, categories), whose outputs rarely carry
   embedded quotes.
3. **The pre-existing `_parse_json` TODO was half right, and credit is
   due.** It correctly identified drift on long translations and correctly
   prescribed tool use. What it got wrong: it treated drift as the *whole*
   problem (truncation caused roughly two-thirds of the losses and is
   deterministic, not intermittent), and its alternative suggestion —
   `output_config.format` structured outputs — is not available on
   `claude-sonnet-4-6` and would have required a model change.
4. **Ruling: the translation contract is the tool schema, not prose.** Do
   not reintroduce "return raw JSON" instructions to the translation
   prompt, and do not loosen `_parse_json` to accommodate translation
   output. If a future task emits long free prose, give it a tool.
5. **`stop_reason` is checked before parsing** in both `_call` and
   `_call_tool`. Truncation now raises a message naming the ceiling
   instead of surfacing as a generic parse error — the misdirection that
   hid the token cap for 83 days.

## 2026-07-30 — Translation token cap has silently excluded every long article since launch

**Diagnosis only; no fix applied.** 163 of 697 relevant articles (23%)
passed the relevance gate but were never translated, and so were invisible
to all 11 published editions.

1. **Root cause: `Analyzer.translate()` calls with `max_tokens=4000`**
   (`analysis/analyzer.py:173`) and asks for both `title_en` and `body_en`
   in one JSON object. A long Chinese body cannot render into English
   inside that ceiling, the response truncates mid-JSON, `_parse_json`
   raises, and `analyze()` returns without `title_english`, so
   `pipeline.py:256` skips the write.
2. **The failure is length-determined**, not random. Failure rate by
   Chinese body length: <1000 chars 7% · 1000–2000 17% · 2000–3000 37% ·
   3000–3800 32% · **3800–5000 95% · 5000+ 100%**. No successfully
   translated article anywhere in the DB exceeds 3807 characters.
3. **The retry path is a no-op for these articles.** `analyzed_at` stays
   NULL, so they re-enter the queue via `get_articles_pending_analysis()`
   every run and fail identically with unchanged parameters. Article id 3
   (scraped 2026-05-08) has been retried on every run since launch. The
   comment at `pipeline.py:277` ("a later run retries it") is true but
   misleading — retry without changed parameters cannot succeed.
4. **Editorial consequence, which is the part that matters.** The excluded
   set is not random noise: it is the *longest* PLA Daily pieces — the
   军营观察 features and long-form policy essays that carry the most
   analytical content. Every edition to date has drawn on a corpus
   systematically truncated against its most substantial material. Any
   claim about weekly coverage completeness made before this is fixed
   should be read with that in mind.

## 2026-07-25 — No. 11 (2026-07-18) editorial corrections before publish

Pre-publish QA (editorial-integrity role) failed the edition; corrected
verbatim-from-source and shipped (analyst-approved). Three findings:

1. **Date: "April 2025" → "April 2026" (CRITICAL).** The Y-20B's first
   international flight is dated by the source (PLA Daily, 81.cn/16473227,
   published 2026-07-12) as "今年4月" — this year, April — i.e. 2026, not
   2025. Corrected across dek/signal/opening_note/what_stood_out/
   what_im_watching_next in the sidecar and the four mirrored spots in the
   LinkedIn file. Standing rule reaffirmed: relative time expressions
   ("今年") resolve against the source's publication date, never guessed.
2. **Engine "WS-20": source-"confirmed" → "widely identified as the WS-20"
   (MAJOR).** The source says only "新型国产发动机" (a new domestically
   produced engine) and never names it. The WS-20 identification is
   analyst/open-source attribution and must be framed as such, not
   attributed to the PLA Daily article.
3. **Routine-Baseline named units now traceable (MAJOR).** The frugality
   essay, 80th GA party-branch compliance piece, and Rocket Force
   governance article named in `what_was_routine` were added to
   `source_trail` (16473917 / 16473559 / 16473317, verbatim DB titles,
   is_significant=false). Rule: any named unit/article in edition prose
   must have a source_trail entry, not merely an untraced DB row.

## 2026-07-25 — Committed editorial derivatives are authoritative; no mtime-based regeneration

1. **`site/assets/editorial/derivatives/*` committed files are the build
   truth.** `generate_editorial_derivatives.py` writes a derivative only
   when the file is missing; intentional regeneration requires `--force`.
   Rationale: mtime staleness is meaningless in fresh git checkouts (git
   does not preserve mtimes), and platform-dependent JPEG encoding meant
   CI rewrites never byte-matched the committed files — which dirtied the
   tracked tree and broke every scheduled daily run 2026-07-18→07-24 at
   the `git pull --rebase` in "Commit updated database and site output."
2. **Workflow rebases use `--autostash`** (`daily_update.yml`, all three
   `git pull --rebase` calls) so a stray tracked-file modification degrades
   to a stash round-trip instead of killing the run.
3. If a source image changes, regenerate its derivatives locally with
   `--force` and commit the new bytes in the same change.

## 2026-07-17 — No. 10 final text: revised package adopted, edition badge ruling

1. **The revised draft package (`pla-watch-draft-2026-07-11-revised.zip`,
   Jul 12) is the final approved text of No. 10**, superseding the earlier
   package published first. All seven prose fields (dek, signal, opening
   note, what stood out, why it matters, routine baseline, term explanation,
   watching next) replaced verbatim via the established extraction path;
   round-trip verified against the package. Title, dates, window,
   issue_number, byline, term name, source trail (13/13), media, and covers
   unchanged. No public correction banner: same facts and sources,
   editorial revision only.
2. **The revised package's `edition_label: "Model-flagged"` is rejected.**
   "Model-flagged" is an article-level mechanical triage state;
   the edition classification ("Significant") is the analyst's human
   editorial judgment and stays. The visible model-flagged article count
   remains a separate surface.
3. **The earlier LinkedIn file (article body pasted in error) is replaced**
   by the revised package's 15-line post. Local file only; never posted
   externally by an agent.

## 2026-07-17 — Session recovery, reconciliation onto origin/main, and No. 10 publication

1. **Recovery mechanics.** The 2026-07-12/13/16 uncommitted passes were
   snapshotted onto local-only branch `rescue/unfinished-pla-watch-2026-07-16`
   (three separated WIP commits; `.claude-flow` excluded) and re-applied onto
   `origin/main` in a clean worktree (branch
   `reconcile/unfinished-pla-watch-2026-07-16`). Local `1f0917c` was verified
   by identical patch-id to be the same change as remote `5e92dc4`
   (cherry-picked); it was not merged. Local `main` was left untouched.
   Output was regenerated fresh from the latest remote DB, never carried
   over from the stale snapshot. Rescue WIP commits are safety history only.
2. **No. 10 (week ending 2026-07-11) integrated from the approved draft
   package** (`pla-watch-draft-29148303565.zip`) via
   `backfill_sidecar_bodies.py`: body fields extracted verbatim from the
   analyst-approved HTML (round-trip verified), issue_number 10 assigned,
   author fields normalized from the package's stale
   "Founder & Principal Analyst" to the ruled public identity, trail
   `title_zh` filled by exact URL match (13/13). No prose was composed.
   The edition ships without `executive_readout` / `recurring_threads`
   by analyst instruction, superseding for this edition the earlier
   adopt-from-No. 10 plan.
3. **No. 10 Night Desk veil = `jin-class-type-094-ssbn`**, routed to
   `pw-post` for edition 2026-07-11 only. Grounded: the manifest entry was
   fetched 2026-07-11 and already tied by exact URL to this edition's lead
   SLBM article (81.cn/16472265); PD (U.S. gov via CRS RL33153); duo-navy
   derivative generated deterministically. Its existing home/article
   routes are unchanged; the J-20 homepage atmosphere is unaffected.
4. **`edition_label: "Significant"` kept for No. 10** as the
   analyst-approved edition classification carried by the approved package,
   consistent with Nos. 5, 6, 8, 9. Reader-facing automated counts remain
   "model-flagged" everywhere.

## 2026-07-16 — Homepage atmospheric image decoupled from the model-flagged story

1. **The homepage veil is an atmospheric publication visual, selected only
   by the explicit manifest field `"placement": "homepage-atmosphere"`** —
   never by the daily model, article matching, or flag status. This
   supersedes the veil half of the 2026-07-12 §3 ruling: the model-flagged
   signal card in the hero's right rail still ties to the most recent
   flagged item by exact URL (`_select_home_editorial`, unchanged), but
   the image behind the hero no longer illustrates that story. The two are
   separate layers; the card carries no image, and the image credit never
   carries flag language. Missing/invalid atmospheric entry or derivative
   → text-led hero, card unaffected (`_select_home_atmosphere`).
2. **The homepage atmospheric image is the Chengdu J-20 photograph by
   emperornie** (Flickr photo 44040541250 via Wikimedia Commons, CC BY-SA
   2.0; manifest id `chengdu-j20`), replacing the Jin-class SSBN in that
   role. The Jin-class entry keeps its `home`+`article` routes for the
   signal-card selection and the article-page figure. The duo-paper veil
   derivative is a modified adaptation and remains subject to CC BY-SA
   2.0 including ShareAlike, recorded in the manifest note.
3. **Homepage-only crop mechanics:** `.home-hero .pl-veil` upscales the
   atmospheric image one step past cover (118%) so the manifest
   `mask_focus` (10% 8%) can seat the airframe in the lower-right field;
   mobile (≤900px) resets to cover with its own position (62% 42%,
   `!important` over the inline style). The signal card gains the same
   paper-whisper backing the ledger already had, so its text never sits
   directly on the image. No new motion: the shared veil-in settle is the
   only animation, and reduced-motion/no-JS receive the settled state.

## 2026-07-12 — Production-completion pass: first paint, editorial imagery, prompt hardening

1. **Above-the-fold content never starts at opacity 0.** The reveal system
   keeps `[data-reveal]` for below-fold sections, adds a `data-reveal="art"`
   variant (container always visible; only inner draw-path/ink-node/rule
   primitives animate), and above-fold identity blocks (homepage hero +
   ledger, PW post hero + cover figure, PW index latest-edition module,
   signals header/dashboard, terms head, first archive entries) render
   statically. The observer JS is wrapped in try/catch (failure → `.no-anim`)
   with a post-load in-viewport sweep so no content can stay hidden on
   short pages. Every new component must follow this rule.
2. **Editorial imagery is manifest-only and exact-URL matched.** All
   editorial images come from `site/assets/editorial/manifest.json`
   (curated via `scripts/fetch_editorial_image.py`, which enforces the
   PD/CC0/CC BY/CC BY-SA allowlist from fetch_pla_watch_media). Association
   to stories is by exact article URL or edition date; the manifest's
   category/thread fields are curation context and are deliberately not
   used for automatic matching, so an image can never drift onto the wrong
   story. No match → text-led layout (the designed fallback). Sidecars stay
   canonical: weekly editorial images merge at render time only.
   Every placement carries credit + license + "visual context, not
   evidence" language.
3. **Homepage figure ties only to a model-flagged item** within 7 days of
   the brief date, labeled with the standing "Model-flagged" kicker; the
   ranking language in the Analyst Readout states its mechanical basis
   ("by category priority and relevance; not model-flagged") so automated
   triage is never dressed as editorial judgment.
4. **Byline correction.** Earlier in this 2026-07-12 pass the fallback
   author title in both renderers was changed to "Founder & Principal
   Analyst, China Mil Watch." That change was not analyst-approved and has
   been reverted in `scripts/generate_pla_watch.py` and
   `scripts/rerender_pla_watch.py` before any edition published with it.
   The 2026-07-09 ruling stands: the byline is "Benjamin Yang — Principal
   Analyst, China Mil Watch." The two editions whose sidecars carry no
   `author_title` (2026-05-09, 2026-05-16) render the approved title via
   the fallback constant; no historical sidecar was touched.
5. **Weekly prose mechanics are enforced at draft time, not by rewriting
   history.** PROSE MECHANICS/SYNTHESIS rules added to STYLE_EXTRACT and
   the tool schema; `prose_warnings()` prints non-blocking findings (em
   dashes, banned transitions, stacked "not X but Y") for the human
   reviewer. Editions 1–6 contain 32 such violations and stay as published.
6. **Homepage brief-date demoted to h2** (one h1 per page). The daily
   Analyst Readout now names the record's top-ranked item on no-flag days,
   makes single-source coverage limits explicit, and draws its watch line
   from a fixed per-category table of falsifiable indicators.

## 2026-07-12 — Production visual system: Source-Derived Signal Graphics

Concept A ("Signal Veil") is adopted as the production imagery system on
both surfaces: a duotone crop of the manifest photograph, keyed to the
ground it sits on (paper duotone on Paper Ledger, navy duotone on Night
Desk), shaped by a soft radial mask union so no hard rectangle ever reads
as a conventional photo card. Concept C's Floyd–Steinberg dither is kept as
a secondary "Paper Ledger" fallback, selected per image via the new
optional manifest field `treatment` (`"veil"` default, or `"dither"`).
Concept C's bracketed analyst-mark provenance is used on desktop
(`.src-bracket` / `.nd-src-bracket`); Concept A's compact inline credit
line covers mobile and dense cards. Concept B's tick row (one tick per
Source Trail record, red = model-flagged, with a textual explanation and a
small-screen numeric-only fallback) is retained, but only on Night Desk
surfaces (weekly post hero, index latest-edition module) — Concept B's
photographic strips and ghost edition numeral are rejected as too
decorative for either surface. No conventional photo figure or captioned
image card renders on the homepage hero, article header, weekly hero, or
index module; all four are replaced by the veil/dither system with a
text-led fallback when an image, manifest entry, or derivative is missing.
Derivatives (`{id}-duo-paper.jpg`, `{id}-duo-navy.jpg`, `{id}-dither-ink.png`)
are generated deterministically at build time from the manifest's source
images (Pillow: grayscale + autocontrast, duotone colorize or Floyd–Steinberg
dither; same input produces identical output bytes) via
`scripts/generate_editorial_derivatives.py`, committed to
`site/assets/editorial/derivatives/` and copied to the output tree
alongside the source images. The manifest remains the sole source of
editorial-image metadata; sidecars are untouched. A missing image,
manifest entry, or derivative always falls back to the existing text-led
layout, never a broken reference.

## 2026-07-11 — Analyst decisions: metadata fields, labeling, commit sequence

1. **`executive_readout` adopted** beginning with Edition No. 10: optional
   sidecar field, 2–4 bullets, manually authored by the analyst at publish
   time. It must never be synthesized automatically — not from the week's
   records, not from prior editions. Render-if-present; historical editions
   stay unchanged. (Implements ROADMAP T5.)
2. **`recurring_threads` adopted** for Continuity Strip Phase 2: optional
   sidecar field carrying slugs from the controlled vocabulary in
   docs/VISUAL_AND_MOTION_SYSTEM.md §4. Assign a slug only when the edition
   *materially analyzes* the thread (a standing section engages it) — never
   for passing mentions; typical count 0–3 per edition, and editions with
   none stay empty. New slugs require a DECISION_LOG entry. Historical
   backfill only by re-reading published edition text, never from memory.
3. **"Model-flagged" ratified as the only reader-facing label for automated
   classifications**, with the standing concise explainer ("a triage cue
   produced by software, not an editorial judgment"). Verified 2026-07-11:
   every automated surface already renders "Model-flagged" (daily article
   kicker, archive badge/filter, signals dashboard, weekly counts). The
   analyst-assigned *edition* badge (Significant / Routine / Pilot) is
   editorial, not automated, and is exempt — it keeps its name. Internal
   identifiers (`is_significant`, `n_significant`, CSS class names) are not
   reader-facing and stay unchanged.
4. **Commit sequence approved** for the current working tree: (a) docs +
   Claude operating system → (b) frontend source/templates/scripts →
   (c) regenerated output → (d) validation/cleanup fixes where needed.
   Nothing committed until the analyst reviews the staged plan.

## 2026-07-11 — Project operating system established

Durable doctrine now lives in six docs (product/editorial, design system,
visual & motion, architecture & publishing, agent workflows, roadmap);
CLAUDE.md is a compact pointer file; PROJECT_STATE.md is state-only.
Constraining rulings made in this pass: the dual-surface identity (Paper
Ledger / Night Desk) is confirmed doctrine, with per-surface crimson values
kept deliberately distinct; crimson is reserved for analytical signal;
IBM Plex Mono is capped at one-line metadata; photo-overlay cover PNGs are
demoted to og:image duty in favor of generated SVG Edition Plates (ROADMAP
T2); docs/ROADMAP.md supersedes DESIGN_BACKLOG.md; the skillui-extracted
design skills were retired in place as inaccurate (docs/DESIGN_SYSTEM.md is
authoritative); README/METHODOLOGY/style_guide OSINT phrasing was aligned
with the 2026-07-10 identity decision. New sidecar fields may only be
optional and render-if-present (executive_readout, recurring_threads —
pending analyst adoption).

## 2026-07-10 — Public identity language: Mandarin-source monitoring, not OSINT

The daily site's title, meta descriptions, masthead kicker, footer, and
methodology intro described the project as an "open-source intelligence
tool/pipeline." Replaced everywhere with the project's identity statement:
"independent Mandarin-source monitoring and analysis project tracking Chinese
military and security reporting from official and authoritative PRC sources."
Rationale: matches the stated identity, avoids intelligence cosplay, and drops
the "tool" framing. The "Signal Posture: Elevated/Routine" homepage chip
(driven solely by model flags) was replaced with the literal flag count for
the same reason. Reversal requires an explicit decision, not copyediting.

## 2026-07-10 — "Model-flagged" label extended to the daily site

The 2026-07-10 weekly-page rename ("significant" → "model-flagged") left the
daily surface inconsistent ("Significant" stat, "Analytical signal" kickers,
"Significant only" filter, signals-page labels, readout strings). All
user-visible daily labels now say "model-flagged"; underlying DB fields,
sidecar counts, and stats are untouched. Explainer copy added at each surface
("a triage cue, not an editorial judgment") linking to
methodology.html#model-flagged, which now documents a five-layer ladder:
scraped record → model processing → model flag → analyst judgment → weekly
brief. The methodology explicitly states the homepage daily readout is
assembled automatically (pipeline output, not analyst prose).

## 2026-07-10 — Homepage carries a real latest-edition module

`site/generator.py` now reads the newest weekly sidecar
(`_load_latest_pw_edition`) so the homepage sidebar shows issue number,
week-ending date, title, and dek instead of a generic CTA. Display-only: the
leading "The PLA Watch: " title prefix is stripped for the module; nothing
missing from a sidecar is invented. PLA Watch archive entries anchor on the
issue number and show a distinct-source count derived from the trail;
month grouping deferred at 9 editions.

## 2026-07-10 — n_significant means model-flagged, and is now labeled so

Traced: `n_significant` is computed by `generate_pla_watch.py::compute_stats`
as the count of `is_significant` articles among the week's relevance-passing
DB articles at generation time; `is_significant` itself is set per article by
the LLM categorization step (`analysis/analyzer.py::categorize`, conservative
~1-in-20 rubric). It is a model flag over the monitored week, not editorial
judgment and not a property of the curated source trail. Verified: edition 2's
published count (3) exactly matches the DB's model flags for 2026-05-10→16;
edition 1's count (1) matches the flags analyzed before the pilot was
generated (the 2026-05-07 Wei Fenghe verdict article; three 2026-05-09
articles were flagged at ~14:13 that day, after generation). Ruling applied:
counts are technically valid and stay unchanged in sidecars; the public label
"N significant" was misleading and is renamed to "N model-flagged" in
`pla-watch-post.html` (hero meta, snapshot stat, snapshot bar + legend,
sidebar row), `pla-watch-index.html`, and `pla-watch-archive.html`; weekly
pages rerendered from unchanged sidecars. This coexists with the 2026-07-10
ruling that editions 1–2 had no editorially significant articles: the trail
carries editorial selection, the count reports the pipeline flag. Daily-site
per-article "Significant" badges (backed by displayed model reasoning) were
left as is — separate surface, analyst's call if they should follow.

## 2026-07-10 — Analyst rulings on historical gaps

- `the-pla-watch/linkedin/2026-05-10.txt` is most likely the pilot edition's
  LinkedIn post under its publish date. Left unrenamed.
- Editions 1–2 trails carry no `is_significant` flags because no significant
  articles arose those weeks. The n_significant counts (1, 3) in early
  sidecars are pipeline auto-counts; reconciling them is the analyst's call.
- 2026-06-20's missing "Why It Matters" section stays as published.

## 2026-07-10 — Original Chinese headlines in the source trail

Trail entries carry `title_zh`, sourced only from the daily-monitoring DB's
`title_original` by exact URL match (100% coverage, all 9 editions).
`generate_pla_watch.py` includes it for new editions; the backfill tool fills
history. Chinese text is never composed, retranslated, or fuzzily matched.

## 2026-07-09 — Sidecar JSON is the canonical edition record

Sidecars now store full body text alongside metadata and the source trail.
Rationale: 7 of 9 sidecars had no body fields, so the "safe" re-render script
would have silently replaced published prose with empty pages. Body text was
backfilled by extraction from the published HTML (verified verbatim — a
round-trip check confirmed every paragraph identical) and
`generate_pla_watch.py` writes body fields at publish time.
`rerender_pla_watch.py` refuses empty-body sidecars without
`--allow-empty-body`.

## 2026-07-09 — Both weekly renderers share one Jinja environment

`scripts/pw_env.py` with autoescape ON (the generator previously rendered
unescaped model output) plus `format_date` and `inline_markup` filters.
`inline_markup` whitelists bare `<strong>`/`<em>` because the 2026-05-16
sidecar carries literal emphasis tags; everything else is escaped.

## 2026-07-09 — Date display convention

Reader-facing week-ending labels use "4 July 2026"; ISO `YYYY-MM-DD` is kept
in tabular/meta contexts (covers range, snapshot sub-labels, JSON). Do not
mix within one label.

## 2026-07-09 — Historical data gaps are warnings, never fixed by invention

Missing per-item trail dates (editions 1–3), missing LinkedIn files
(editions 1–3), missing `is_significant` flags (editions 1–2), the pilot's
2-day window, and the 2026-06-20 missing "Why It Matters" section stay as
recorded facts + validator warnings. Only two normalizations were allowed:
`label`→`title` key rename (same string) and pilot trail `source` filled from
its single-entry `sources_seen` (what the published page already displayed).

## 2026-07-09 — Public role title

"Principal Analyst, China Mil Watch" everywhere (scripts, sidecars, pages).
Bio phrase: "principal analyst at China Mil Watch".

## 2026-07-09 — Issue numbering

Chronological No. 1–9 assigned from week-ending order, stored in sidecars,
displayed as "Vol. I · No. N", validated unique + chronological. New editions:
1 + count of earlier sidecars.
