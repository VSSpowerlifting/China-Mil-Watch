# PROJECT_STATE — Indo-Pacific Record

**Current operational snapshot and handoff. Shadow-desk state, protected refs
and repository scope verified 2026-09-03 against `origin/main` `d10c6c4a`.
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

Measured 2026-09-16 from a read-only copy of the tracked `pla_watch.db`:

* **4,229 records**, 4,229 distinct URLs, max record id 4,235.
* **140 scrape runs.** Run 140 completed 2026-09-16 17:46 UTC, `completed`,
  72 scraped / 36 new / 20 analyzed.
* **Freshness through 2026-09-16** (latest `published_date`).
* Records by source: `pla_daily` 3,580; `china_mil_online` 445;
  `global_times_mil` 121; `mod_china` 83; `xinhua_mil` **0**.
* **Xinhua Military is still unimplemented, but no longer unimplementable.**
  The stub's stated reason — a JavaScript/API-rendered listing — was
  re-measured on 2026-09-16 and is **stale**: `https://www.news.cn/milpro/`
  serves 200 with a server-rendered listing carrying 106 distinct article URLs,
  and `robots.txt` reads `Allow: /`. It stays enabled and reporting
  `not_implemented` — honest, and now a repair rather than a dead end. See
  `docs/DESK_RELIABILITY_REVIEW_2026-09-16.md` §6.1.
* **676 never relevance-screened** (down from 903 on 2026-09-02).
* **87 records hold an empty or near-empty body** (up from 48); 5 of those
  passed relevance and are unanalyzed, so they re-enter the analysis queue on
  every run and can never clear. Record 2678 has now been retried on 28
  separate runs. Three of the seven repeat offenders are a Global Times
  **extraction defect**, not source silence — their pages serve 1,076–4,180
  characters of body text. See §6 and the review document §6.2.

Coverage is heavily concentrated in one source and every public surface must
show that honestly. The 2026-07-17 → 07-24 collection outage is permanent,
disclosed, and never backfilled.

## 4. Analytical publication status

* **Indo-Pacific Record Briefs: source-level foundation only** (2026-09-23). A
  brief can be scaffolded and checked (`scripts/author_brief.py`,
  `core/brief_contract.py`) but has no route, renderer or feed, and none is
  numbered while No. 14 is unreconciled: `check` refuses a hand-numbered brief
  and any number an existing issue holds. `scripts/generate_pla_watch.py`
  authors nothing new, so the 2026-09-03 plan for a w/e 2026-08-22
  retrospective cannot proceed as The PLA Watch: brief or disclosed gap is the
  owner's decision.
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

## 5. Shadow desks

**Singapore was promoted to `live` on 2026-09-21** (DECISION_LOG); what follows
about Singapore is its shadow-period record, kept as written. Japan remains in
shadow evaluation.

Neither desk is qualified, and neither may be described or promoted as
qualified. Doctrine in `docs/SHADOW_COLLECTION.md`; review procedure in
`docs/SHADOW_REVIEW.md`.

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

**Day 30 remains required, and Singapore remains unqualified.** Two completed
checkpoints qualify nothing: promotion still needs 30 consecutive collecting
days, the Day 30 review, and an owner sign-off recorded in `DECISION_LOG.md`.

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

## 6a. Frontend: the old China Mil Watch style revival (T3 Wake)

Branch `feat/ipr-cmw-revival-t3`, built on `origin/main` `53cc971c5`. Local
only: not pushed, no PR, `output/` and `pla_watch.db` untouched, deploy gate
still at its governed 10 warnings.

**What landed.** The home page recovers the historical China Mil Watch grammar
under the current identity: the light editorial nameplate with the navigation
on its own rail, the two-column opening with the dateline rendered as its
ledger, the lead record in the brief-header idiom, the register as hairline
rows with a context rail, desks as status rows, and the dark analysis band.
The `01`-`05` folio marks are gone. The site-wide palette is the p1
institutional set, derived from the canonical compass logo; the old semantic
names survive as aliases onto it so interior pages are recoloured without
being restructured.

**The Ocean Signal Veil is back, and measured.** A public-domain U.S. Navy
photograph (MC3 Nathan Burke, 17 U.S.C. § 105), duotoned offline against the
paper ground by `scripts/make_veil.py`, declared only inside
`@media (min-width: 901px)` so no narrow viewport can fetch it. The previous
veil was withdrawn because live type over it failed contrast; this one is
sampled at the pixels each glyph actually covers, because both a colour check
and a whole-box sample called a genuine 2.22:1 failure a pass. Mask lobe 1's
horizontal radius is load-bearing at 45% and the stylesheet says so.

**Verified locally.** 23/23 content parity against the current production
render from the same database; focus traversal 421 stops across 12 states with
0 WCAG 1.4.11 failures; 0 genuine target-size failures in 12 states; 0
horizontal overflow across 29 widths 320-2560; interaction 177/177; Space on
the disclosure 12/12; audit 80/86. Impeccable reports one finding
(`em-dash-overuse`, pre-existing production copy at the same count), down from
two on `main` — the `numbered-section-markers` finding went with the folios.

**Known and accepted.** Three audit assertions fail here and on pinned
production: the second record is below the first screen at 375 and 768, and
the shell uses 58.13% of a 1920 viewport against a 60% target. Three more are
parity assertions in the packet's own harness that pin its fixture's data
(Run 137, `record/4117`); this build renders live data, which is the
requirement. `HEADLINE_CEILING` in `tests/test_home_paired_records.py` was
raised from 700/560 to 830/730: the restored nameplate, nav rail and ledger
cost the lead headline about 130px at 1280, which is the accepted design. The
first-screen contract itself is unchanged and still passes.

**Not done here.** Not pushed, no PR, no deploy, no workflow dispatch.

## 7. Immediate priorities

Full ordering and rationale in `docs/ROADMAP.md`. In short:

1. Restore the human analytical publication cadence.
2. Complete Singapore's Day 7 / Day 14 human checkpoint reviews.
3. Scoped screening/backfill for publication-ready windows only.
4. Terminal processing states and retry budgets for poison and empty-body
   records.
5. An explicit continue/pause decision on the Japan shadow desk.

Further frontend polish and geographic promotion are deferred until the
research and review gates are healthy.

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
