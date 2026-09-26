# PROJECT_STATE — Indo-Pacific Record

**Current operational snapshot and handoff. Desk statuses checked 2026-09-25
against `desks/registry.json` and the owner rulings in `DECISION_LOG.md`.
Production and corpus figures below carry their own measurement dates.**

This file is state, not history. It is deliberately short and is rewritten
rather than appended to. Superseded state, incident narratives and the
reasoning behind past decisions live in Git history and in `DECISION_LOG.md`.

Durable documents, and what each one governs:

| Document | Governs |
|---|---|
| `README.md` | public and contributor overview |
| `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` | identity, editorial standard, provenance, publication principles |
| `docs/ARCHITECTURE_AND_PUBLISHING.md` | technical layer map, commands, publishing and deployment procedure |
| `docs/AGENT_WORKFLOWS.md` | agent operating constraints and model routing |
| `docs/ROADMAP.md` | current priority order |
| `docs/SHADOW_COLLECTION.md`, `docs/SHADOW_REVIEW.md` | shadow desk isolation and human review procedure |
| `DECISION_LOG.md` | durable decisions that constrain future work |
| `docs/DESK_STRENGTH_CRITERIA.md` | what a desk must prove before it is called strong |
| `docs/DESK_RELIABILITY_REVIEW_2026-09-16.md` | measured per-desk assessment and source-feasibility evidence |

---

## 1. Production state

* **Public identity: Indo-Pacific Record.** Live at
  `https://indopacificrecord.org` (verified 2026-09-02, HTTP 200, page title
  `Indo-Pacific Record`).
* **"China Mil Watch" is a legacy name only.** `chinamilwatch.org` is served by
  a separate redirect-only Pages site
  (`VSSpowerlifting/chinamilwatch-legacy-redirects`) that sends every address
  the predecessor published to its counterpart on the current domain.
* **Indo-Pacific Record Briefs is the continuing analytical collection**
  (DECISION_LOG 2026-09-23). "The PLA Watch" is predecessor attribution: the
  existing issues keep it, with their addresses, issue numbers and original
  masthead, and no new issue is authored or published under it.
* **Renderer:** `.venv/bin/python site/render.py`. `DEFAULT_SITE_MODE` is
  `indo-pacific-record`. `site/generator.py` is the `legacy` renderer and is
  the rollback path only — it is not the production renderer.
* **Validator / deploy gate:** `.venv/bin/python scripts/validate_output.py`.
* **Deployment:** `daily_update.yml` commits `pla_watch.db` and `output/` to
  `main`, then publishes `output/` to `gh-pages` via
  `peaceiris/actions-gh-pages@v3` with `cname: indopacificrecord.org`.
  `deploy_output_only.yml` is the manual equivalent for an already-committed
  `output/`. The action writes `.nojekyll` at the root of `gh-pages`; it is not
  tracked under `output/`.
* **Licensing is settled.** `LICENSE` is MIT for the software;
  `CONTENT_AND_DATA_RIGHTS.md` sets out editorial, source-document and
  public-fact terms separately. Any document still describing licensing as
  undecided is stale.

## 2. Public surfaces

Four desks are declared in `desks/registry.json`, which is authoritative for
desk **status and public presentation**; a desk's own manifest is authoritative
for its **sources**.

| Desk | Status | Public meaning |
|---|---|---|
| China | `live` | Collecting daily into the production corpus. The only mature collection. |
| Singapore | `live` | Promoted 2026-09-21 (DECISION_LOG). One source, MINDEF releases; its 57 promoted records had not been relevance-screened when measured 2026-09-23. |
| Japan | `shadow` | Isolated evaluation. No production records, no public counts. |
| US Indo-Pacific | `access_blocked` | Declared scope only; `robots.txt` returns 403, so permission cannot be established. |

The site also publishes the record archive, per-record pages, coverage,
methodology, and the legacy `/article/<id>.html` compatibility namespace.

## 3. Data and pipeline condition

Measured 2026-09-25 from the tracked `pla_watch.db` without writing to it:

* **4,625 stored records**, 4,625 distinct URLs, max record id 4,631.
  The latest source-stated publication date is 2026-09-25.
* **149 scrape runs.** Run 149 completed 2026-09-25 17:55 UTC with status
  `completed`: 48 scraped / 19 new / 26 analyzed. Its two analysis errors
  remain in the run record.
* Records by source: `pla_daily` 3,782; `china_mil_online` 491;
  `global_times_mil` 134; `mod_china` 103;
  `sg_mindef_releases` 60; `xinhua_mil` 55. Xinhua is implemented and returned
  an `ok` result in run 149; the 2026-09-16 feasibility note in
  `docs/DESK_RELIABILITY_REVIEW_2026-09-16.md` describes an earlier state.
* **689 records await relevance screening**; 8 passed screening without a
  completed analysis. **56 records hold an empty body capture.** These counts
  have different definitions from the older empty-or-near-empty review in §6.

Coverage is heavily concentrated in one source and every public surface must
show that honestly. The 2026-07-17 → 07-24 collection outage is permanent,
disclosed, and never backfilled.

## 4. Analytical publication status

* **Indo-Pacific Record Briefs: source foundation, no published brief.** A
  brief can be scaffolded and checked (`scripts/author_brief.py`,
  `core/brief_contract.py`); the collection and renderer use
  `core/brief_collection.py` and `site/preview/templates/brief.html`. Routes
  are `briefs/<slug>.html`, Analysis is the landing page, and
  `briefs/feed.xml` carries briefs only (DECISION_LOG 2026-09-23). The only
  brief data is a synthetic test fixture. No. 14 remains unreconciled, and
  `check` refuses a hand-numbered brief or an existing issue number. The
  predecessor pages' source chrome now identifies the series as historical
  and points to continuing Briefs; public `output/` still requires a separate
  authorized render and deploy. `scripts/generate_pla_watch.py` authors no
  new issue. The owner must decide how to handle the w/e 2026-08-22 gap.
* **No. 1 (2026-05-09 pilot) through No. 13 (week ending 2026-08-08) are
  published.** No. 14 is publicly served, with its status unreconciled (below).
* **The cadence lapsed after No. 13, and its recovery is ruled.** No edition
  exists for the weeks ending 2026-08-22 or 08-29; w/e 2026-08-15 is No. 14
  (below). The owner ruling of 2026-09-03 (`DECISION_LOG.md`) prepares
  **08-15 and 08-22 as retrospective
  editions**, rules **08-29 a disclosed gap** (36% of that window was never
  relevance-screened), and **resumes normal cadence at 09-05**. Restoring
  cadence remains the first priority in `docs/ROADMAP.md`.
* **No. 14's publication status is unreconciled** (verified 2026-09-23;
  DECISION_LOG 2026-09-23 point 9). Prepared as a draft for review (w/e
  2026-08-15), it merged with PR #43 and has been publicly served since an
  output-only deploy on 2026-09-05, linked from the series index, archive,
  sitemap and feed. No approval and no completed `EDITORIAL_QA_CHECKLIST.md`
  record exist. The 2026-09-04 ruling ("not published") is stale on
  publication. Its status and number are unchanged until the owner rules.
  Recommended path: an `EDITORIAL_QA_CHECKLIST.md` review of the page as
  served, then a DECISION_LOG entry recording what the review found and the
  owner's ruling. Approval is not recorded retroactively without that review,
  and withdrawal is one option open to the owner, not a requirement.
* **14 editions now exist in the tree, all publicly served** (No. 14 without
  recorded approval, above). No. 14 is the first
  edition under the Indo-Pacific Record masthead and the first marked
  `publication_timing: retrospective`. Editions 1–13 keep the China Mil Watch
  identity on their own pages; site chrome is current throughout.
* There is a ruled cadence gap for the week ending 2026-07-25 (analyst ruling,
  `DECISION_LOG.md` 2026-07-30). The validator warning that records it is
  history, not a defect to suppress.
* No. 12 and No. 13 shipped without the `EDITORIAL_QA_CHECKLIST.md`
  source-to-claim trace and without a rendered-page visual review, by analyst
  direction. That gap is recorded, not implied.

## 5. Desk evaluation and review status

**Singapore was promoted to `live` on 2026-09-21 by owner sign-off**
(`DECISION_LOG.md`). The Singapore observations below describe its earlier
shadow period, not its current desk status. Japan remains in shadow evaluation.

Neither desk is described as qualified: Singapore's live status is not a
qualification claim, and Japan remains in shadow. Doctrine is in
`docs/SHADOW_COLLECTION.md`; review procedure in `docs/SHADOW_REVIEW.md`.

**Singapore MINDEF** — state branch `shadow/singapore-mindef`. Day zero
2026-08-19T23:03:09Z. The 2026-09-02 run recorded `shadow_day` **14**, result
`ok_all_duplicates`, health `ok`, `robots_status=allowed`; 15 ledger entries,
40 records.

**Day 7 and Day 14 human checkpoint reviews are complete and published** to the
orphan branch `review/singapore-mindef`, both `pass_with_findings`, reviewer
Benjamin Yang:

| Checkpoint | State commit | Completed-review id | Scope |
|---|---|---|---|
| Day 7 (retrospective) | `f806335e` | `403df921…3c3d89` | complete corpus, 37 of 37 |
| Day 14 | `5fa49c81` | `10a28df1…e7b756` | focused queue, 16 of 40 |

**No distinct Day 30 human review is on record.** The 2026-09-21 owner decision
records 33 elapsed shadow days and explicitly proceeds with promotion after
the Day 7 and Day 14 reviews, without a separate Day 30 review. The two
completed checkpoints do not establish a qualification claim.

Both reviews disposed of the same class of finding — a scheduled run delayed
across UTC midnight was stamped with its execution date, leaving its nominal
day with no ledger (2026-08-26 and 2026-08-31).

**No collection loss is observable in the reviewed Singapore corpus.** The state-hash
chain stayed coherent, no fetch, extraction or access failure was recorded,
insertions continued in the runs that followed, and the overlapping 30-day
lookbacks covered both days. Those facts are about what the desk observed and
stored; they cannot establish that the ministry published nothing the desk
never observed, and no evidence reachable from inside the corpus could. Loss is
unobserved, which is a narrower claim than ruled out, and the limitation is
recorded rather than rounded off.

**Attribution is fixed at the source, forward-only.** Singapore and Japan
shadow runs derive their logical target date through `core/shadow_schedule.py`:
a scheduled first attempt takes the schedule-slot convention — the most recent
occurrence of the configured daily cron time at or before the run started,
boundary inclusive — an explicit `--target-date` is authoritative wherever it
is given, and a re-run without one is refused rather than re-dated. Each ledger
records which rule applied in `target_date_source`. Historical ledgers and both
published review findings are untouched: the fix changes no review evidence and
does not retroactively alter a single stored date, so historical missing-day
anomalies remain and still require disposition. Recovery from a failed
scheduled run is a manual dispatch naming the intended logical date, not a UI
re-run; the procedure is in `docs/SHADOW_REVIEW.md`.

**Japan MOD** — state branch `shadow/jp-mod`. Day zero
2026-08-27T02:14:38Z. The 2026-09-03 run recorded `shadow_day` **6**, result
`ok_all_duplicates`, health **`partial`**; 9 ledger entries. **Access-constrained:**
RSS discovery works and PDF documents are retrieved in full, but HTML documents
on the same host are returned behind an interactive challenge — 35 of 39
selected items were challenged in that run. Challenged items are stored as
titled, dated discovery records with no body and nothing inferred. The
challenge is **never** to be bypassed; resolving this means requesting an
official route.

**Every Japan ledger written so far carries an execution date, not a slot
date.** Japan's cron sits at 22:40 UTC and Actions has started every scheduled
Japan run late enough to cross UTC midnight — observed lateness 1h50m to 7h38m.
Verified 2026-09-03 against `shadow/jp-mod`: all 9 ledgers are stamped one day
after the slot they belong to, most recently run `33700195896` (started
2026-09-03T00:36:36Z, stamped 2026-09-03, nominal 2026-09-02). Japan's
mis-attribution is systemic, where Singapore's was occasional.

Two consequences of the source fix, both expected and neither retroactive:

* the first slot-dated Japan run records 2026-09-03, which the last
  execution-dated ledger already carries, so one duplicate-date pair appears at
  the changeover and nominal 2026-09-02 acquires no Japan ledger. Historical
  ledgers are not rewritten to smooth this;
* **the qualification clock is unaffected.** `shadow_day` is derived from
  `finished_utc` against day zero, never from `target_date`, so no day count
  moves.

## 6. Known technical debt

* **Governed validator baseline: exactly 10 warnings.** Three
  no-date-source-trail warnings (eds. 2026-05-09/05-16/05-23), two
  `n_significant` warnings with no marked trail entry, one pilot week-span
  warning, three missing LinkedIn files (eds. 1–3), and one cadence gap
  (2026-07-18 → 2026-08-01). Any **new** warning must be explained here before
  it is accepted; none is ever fixed by invention.
* **No terminal processing state.** A record with an empty body that passed
  relevance is retried indefinitely. 3 records are in this state now. There is
  no retry budget and no poison-record disposition.
* **903 unscreened records** outside any published window. Not urgent — no
  edition cites them — but this is the defect class that previously stranded
  material. Drain only in scoped, windowed chunks.
* **Rendering and preservation depend on LLM availability.** An analysis-stage
  billing or API failure has repeatedly degraded runs; collection now survives
  it, but the coupling is not fully removed.
* **Cross-source occurrence is not modelled.** Canonical selection keeps one
  copy and discards the losing copies' URLs, so "both institutions carried this
  release" is recorded nowhere.
* **Repository growth.** Measured 2026-09-02 on this checkout, and the three
  numbers are not interchangeable:
  * **Git objects, repeatable:** `git count-objects -vH` reports `size-pack`
    **296.28 MiB** across 18 packs, plus 30.11 MiB loose. Quote this with its
    date and pack count.
  * **Fresh clone (the portable figure):** an independently measured fresh
    clone repacks to ~167.50 MiB packed / ~169 MB `.git`. A long-lived
    checkout roughly doubles it through unconsolidated packs.
  * **Checkout-specific:** `du -sh .git` says 334 MB here. **This is not a
    property of the repository** and must not be quoted as one.
  * **Tracked content:** `output/` ~94 MB across 5,400 tracked files;
    `pla_watch.db` ~32 MB, committed on every daily run.

  No threshold or storage strategy is defined. When one is set, state it
  against the fresh-clone packed size — see `docs/ROADMAP.md` §8.
* **A green Actions run is not evidence the pipeline executed.** The daily
  workflow schedules five windows and a guard admits one per New York day; the
  other four exit successfully. Read the `Scheduling guard` step.
* **Stale in-code narration.** Behaviour is correct everywhere below; only the
  prose is wrong. Inventoried 2026-09-02; all of it needs a code PR, and none
  of it was touched by the documentation reset.

  `site/render.py`:
  * module docstring calls `site/generator.py` "the live China Mil Watch site"
    and `generate_preview.py` "the Indo-Pacific Record candidate … Tested,
    complete, and not public" — inverted since the launch;
  * the same docstring says `DEFAULT_SITE_MODE` "is `LEGACY` today", that
    "Candidate mode REQUIRES an explicit destination", and that "the scheduled
    workflow sets nothing, so it resolves to legacy";
  * the `INDO_PACIFIC_RECORD` constant comment still reads "Not public.
    Renders to a disposable destination", and two later comments still call the
    live mode a "candidate";
  * `render_site()`'s docstring says "The candidate has no default destination
    on purpose" — it defaults to `output/`;
  * **stale CLI help:** `--out` advertises "required for
    `indo-pacific-record`". It is optional; both modes default to `output/`.

  `pipeline.py`:
  * the render comment says the no-mode call "resolves to `DEFAULT_SITE_MODE` —
    legacy — exactly as before".

  `tests/test_site_mode_contract.py` (narration only — every assertion is
  current and passing):
  * module docstring describes the live renderer as publishing "under its
    historical China Mil Watch identity" and Indo-Pacific Record as "the
    candidate", and calls the mode rename "a candidate-side change with no
    public surface";
  * `test_the_pipeline_selects_no_mode_so_it_resolves_to_legacy` — the **name**
    is wrong (it resolves to `indo-pacific-record`); the assertions it makes,
    that `pipeline.py` selects no mode, remain correct;
  * `TestCandidateBuild`, its docstring, `test_the_build_reports_candidate_mode`
    and a later "candidate renderer" reference all name the live production
    mode as a candidate.

## 6a. Frontend source and public output

The reader interface uses Paper Ledger for the record and Night Desk for the
historical *The PLA Watch* issues. The source templates now give long record,
desk, source, coverage and methodology pages native section navigation;
Analysis presents the issue sequence as a chronological reading ledger. The
Sources chart measures stored, deduplicated records assigned to each source
at the labeled snapshot and explicitly disclaims institutional output and
coverage. Briefs remain unpublished until editorial approval. Historical
issues keep their original attribution and have a clearer route to continuing
analysis.

The Ocean Signal Veil remains a desktop-only, credited public-domain image;
the home page preserves its two-column opening and dated record ledger. The
shared navigation and reading layout are usable without scripted motion.

The Paper Ledger source pass loads the existing publication font trio on
record routes, gives interior headings an editorial serif hierarchy, and
compacts the repeated mobile dateline. Atlas adds a four-state chart sourced
from the exhaustive stored-record processing partition, with a dated
denominator, filter links, definitions, and a clear limit on what the counts
mean. Sources bars and the Analysis reading paths have a stronger printed
register treatment; Methodology presents its existing evidence labels as a
specimen sheet. Fine etched lines are confined to the Atlas plate.
Desk pages call the complement of analyzed records "Not analyzed" and explain
that it includes screened-out and unscreened items, rather than presenting the
whole group as an analysis queue.

This frontend pass changes templates and tests, not `pla_watch.db`, desk
configuration, canonical edition sidecars, or production `output/`. A source
merge alone does not show these changes on the public site: the authorized
render-and-deploy workflow must generate and validate `output/` first. The
deploy gate's governed baseline is 10 warnings.

## 7. Immediate priorities

Full ordering and rationale in `docs/ROADMAP.md`. In short:

1. Restore the human analytical publication cadence.
2. Close Singapore's unrecorded Day 30 human-review evidence gap.
3. Scoped screening/backfill for publication-ready windows only.
4. Terminal processing states and retry budgets for poison and empty-body
   records.
5. An explicit continue/pause decision on the Japan shadow desk.

Further geographic promotion remains gated by research and review. Frontend
work may proceed when explicitly authorized without changing desk status or
editorial records.

## 8. Prohibited shortcuts and human-review gates

* Never invent Chinese text, translations, titles, outlets, dates, units, ranks
  or claims. Historical gaps stay recorded as warnings.
* Never hand-edit `output/` — it is generated. Fix templates, scripts or
  sidecars and re-render. Sidecar JSON under `output/the-pla-watch/posts/*.json`
  is the canonical edition record.
* Never bypass a source's access challenge, impersonate a browser, or use a
  proxy to defeat one. An institution must be able to recognise this collector
  and refuse it.
* No shadow desk is promoted automatically. Promotion requires 30 consecutive
  collecting days, completed human checkpoint reviews, and a recorded owner
  sign-off in `DECISION_LOG.md`.
* Do not commit, push, deploy, publish, regenerate output, or run collection
  unless explicitly asked.
* An edition is published only after the `EDITORIAL_QA_CHECKLIST.md` gate and a
  rendered-page review; where that was skipped, it is recorded, not implied.
