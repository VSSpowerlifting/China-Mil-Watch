# PROJECT_STATE — Indo-Pacific Record

**Current operational snapshot and handoff. Desk statuses checked 2026-09-28
against `desks/registry.json` and the owner rulings in `DECISION_LOG.md`.
Production and corpus figures below carry their own measurement dates. The
2026-09-28 desk measurements, the Singapore Day-30 packet check and the
first-brief research packet are in
`docs/DESK_CONSOLIDATION_AND_BRIEF_PREP_2026-09-28.md` (its §7 corrects the
Singapore recovery claim). The Singapore screening repair and re-screening
plan are in `docs/SINGAPORE_SCREENING_REPAIR_2026-09-29.md` (merged, PR #84).
The image-only-release repair is in
`docs/SINGAPORE_IMAGE_ONLY_RELEASES_2026-09-29.md`. The authorized September 22
recovery is prepared for review (three inserts, eight duplicates; no analysis
or rendering), with evidence in
`docs/SINGAPORE_SEPT22_RECOVERY_2026-10-07.md`.**

Brief release approval was received 2026-10-05; its candidate,
authorization recovery and QA evidence are in
`docs/BRIEF_RELEASE_REVIEW_2026-10-04.md`. The older desk measurements below
have not been refreshed by that work.

Vietnam is declared at `research`; PR #107 merged on 2026-10-07 as
`5ccc20ff9` and PR #114 merged the remote ministry path as `2c21b0d09`.
Actions run `37656171920`, attempt 2 established durable Day 0 on 2026-10-07
for MPS foreign affairs and the two MOIT families after attempt 1 stopped on a
transient MOIT robots HTTP 502 without publication. State heads are
`9098f48e` (MPS), `e4e97954` (MOIT energy), and `4da050e4` (MOIT
foundational industry). A separate reliability-cadence PR proposes daily
18:17 UTC collection with six-day lookback/cap 40 and explicit-date manual
recovery, leading to human Day 7/14/30 checkpoints on 2026-10-14,
2026-10-21, and 2026-11-06. Government News remains unapproved for remote
dispatch or public capture retention; no production admission or automatic
promotion is authorized.

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
| `docs/REGIONAL_TOPIC_TAXONOMY.md` | cross-desk topic vocabulary, assignment provenance, and storage contract |
| `docs/DESK_CONSOLIDATION_AND_BRIEF_PREP_2026-09-28.md` | 14-day desk measurement, Day-30 packet evidence, first-brief candidate questions; §7 the failed Singapore recovery |
| `docs/SINGAPORE_SCREENING_REPAIR_2026-09-29.md` | Singapore screening defect, desk-scoped fix, re-screening plan (ids, cost, review path) |
| `docs/SINGAPORE_IMAGE_ONLY_RELEASES_2026-09-29.md` | Why `22sep26-infographic` blocked the batch, the structural rule that fixes it, what stays fail-closed, residual risks |
| `docs/VIETNAM_DESK_FEASIBILITY_2026-10-05.md` | Vietnam source measurements, source decision, rehearsal evidence, activation and review commands |

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
| Singapore | `live` | Promoted 2026-09-21 (DECISION_LOG). One source, MINDEF releases. Measured 2026-09-28: 64 records, none analyzed; 14 screened, all rejected by the China-scoped relevance screen; 50 await screening. Desk-scoped screening is in source (2026-09-29); Singapore is held out of the daily model queue until the owner rules. |
| Japan | `shadow` | Isolated evaluation. No production records, no public counts. |
| US Indo-Pacific | `access_blocked` | Declared scope only; the command website's `robots.txt` returns 403, so permission cannot be established. A separate DVIDS route runs in shadow only (§5); it is not public coverage. |

The site also publishes the record archive, per-record pages, coverage,
methodology, and the legacy `/article/<id>.html` compatibility namespace.

**Regional Topic Taxonomy v1 is now a separate classification layer.**
`taxonomy/regional_topics.v1.json` defines 19 cross-desk subjects in six
groups; `core/topics.py` validates the vocabulary and a storage-neutral
`(desk_id, source_slug, canonical_url)` assignment identity. Migration
`0008` adds an empty `record_topics` table only. The China Desk's 14 legacy
`article_categories` remain byte-for-byte unchanged and are not automatically
mapped. No record has been assigned a regional topic, no classifier or UI uses
the vocabulary, and no shadow state is changed. The next gate is a small
human-reviewed multi-desk classification pilot; see
`docs/REGIONAL_TOPIC_TAXONOMY.md`.

## 3. Data and pipeline condition

Measured 2026-09-28 from a pinned read-only copy of `pla_watch.db` as
committed by `d17646aef` (sha256 `42f4e5a9…b501c`):

* **4,715 stored records**, 4,715 distinct URLs, max record id 4,721.
  The latest source-stated publication date is 2026-09-28.
* **152 scrape runs.** Run 152 completed 2026-09-28 20:29 UTC with status
  `completed`: 49 scraped / 38 new / 23 analyzed. Its four analysis errors
  remain in the run record. Run 146 (2026-09-22) is `degraded`: Singapore
  collection crashed (fixed by #69).
* Records by source: `pla_daily` 3,845; `china_mil_online` 498;
  `global_times_mil` 140; `mod_china` 105; `sg_mindef_releases` 64;
  `xinhua_mil` 63. Xinhua has returned `ok` since run 141 (2026-09-17);
  61 of its 63 records were rejected by the relevance screen.
* **616 records await relevance screening** (China desk 566, Singapore 50);
  10 passed screening without a completed analysis. **58 records hold an
  empty body capture.** Processing states: 7 `paused`
  (`retry_budget_exhausted`), 5 `retriable`, 0 `terminal`.
* **Collection continuity, 2026-09-14 → 09-27:** 11 of 14 New York days had
  an admitted daily run. On 09-15, 09-18 and 09-19 every window failed in
  "Run offline test suite", before collection. 09-18/19 were recovered by
  PR #66. **09-15 was not recovered:** `pla_daily`, `china_mil_online` and
  `global_times_mil` hold no records dated 09-15. Health and liveness reports
  measure stored records and do not see a day that never reached collection.
* **Singapore's production window is fixed in source (2026-09-28).** A
  scheduled run used to give every adapter a single-day window. Singapore
  therefore lost `22sep26-nr` and `22sep26-speech` after run 146's crash, and
  `23sep26-mq`, which was listed two days late. It is now handed seven slug
  dates (`production_lookback_days = 6`), and China's windows are unchanged.
* **The authorized recovery run failed (2026-09-29 02:12 UTC) and stored
  nothing.** Its window (09-22 → 09-28) contains `22sep26-infographic`, a page
  whose article is one image; its 178 characters of "text" are page furniture,
  under `MIN_BODY_CHARS`, so the all-or-nothing batch was withheld. The local
  run was not landed. `22sep26-nr` and `22sep26-speech` stay unrecovered;
  the 2026-10-06 refresh confirms `23sep26-mq` is stored as id 4759.
* **Image-only releases: PR #85 refreshed 2026-10-06, not yet merged.** On the
  scheduled path only, a short body whose article container holds an image and
  no prose is stored as a text-unavailable record (official title, URL, date;
  empty body), and no longer withholds the batch. Short prose is kept as text;
  an unreadable layout still fails the whole batch; the two held records are
  still excluded; the shadow collector is unchanged. The recovery for 09-22 is
  **not** run: it waits for an owner merge decision and separate recovery scope.
  Against main `d0c6dbb27`, a fresh September sitemap/database comparison finds
  only `22sep26-infographic`, `22sep26-nr` and `22sep26-speech` missing among
  32 eligible references (29 stored); `16sep26-speech` remains held. The
  proposed 09-22 → 09-28 window is three inserts and eight duplicates.
  Current main still reproduces the fixture blocker. Focused checks pass;
  production DB/output are unchanged. Evidence and remaining tradeoffs are in
  `docs/SINGAPORE_IMAGE_ONLY_RELEASES_2026-09-29.md` §§7–9.

Coverage is heavily concentrated in one source and every public surface must
show that honestly. The 2026-07-17 → 07-24 collection outage is permanent,
disclosed, and never backfilled.

## 4. Analytical publication status

* **First native Brief: No. 15 published and verified live on 2026-10-05.**
  `briefs/maritime-cooperation-2026.json` recovers the five-record host draft
  and finishes its prose, source comparison and native presentation. It
  covers 2026-09-03 → 09-19, selecting statements dated 09-05 → 09-14.
  Source parity, editorial integrity and rendered desktop/mobile review pass;
  Benjamin Yang approved this exact five-source version at commit
  `4bf960c4614b80289a1e3c1db2814f220d3201f1` on 2026-10-05, with Benjamin Yang
  as editor, and authorized numbering, PR #100 merge, deployment and live
  verification. The command assigned No. 15; public output now includes the
  article, homepage/Analysis lead, native feed and sitemap. This supersedes
  the missing-approval gate without claiming recovery of the older fourteen-source
  cloud draft. PR #100 merged at `0e21083d6510c28e8f02daeca64e3a3d074ac8bd`;
  output-only deployment 37273065804 passed. Article, homepage, Analysis,
  feed, sitemap, both stylesheets and photograph returned HTTP 200 and matched
  committed bytes (2026-10-05 07:11 UTC). Required CI passed 3,156 tests,
  two skipped, and validation with ten historical warnings. Desktop/mobile
  live review passed. See the release review and DECISION_LOG for authorization.
* **Brief publication commands are complete.** `scripts/author_brief.py`
  distinguishes `check` (schema), `ready` (finished prose/citations and stored
  source parity), and `approve` (actual human authorization and whole-collection
  numbering). Identical repeated approval is unchanged. The production renderer
  supports private unnumbered review outside `output/`, then approved article,
  Analysis, home, native Atom feed and sitemap integration. The deploy validator
  checks those surfaces; the governed historical baseline remains 10 warnings.
  Existing PR/deploy workflows apply, with no paid API call for publication.
  Native and predecessor catalog/feed ordering follows the coverage endpoint.
  `scripts/generate_pla_watch.py` still authors no new issue. The whole-background
  topographic treatment is a separate, owner-authorized frontend release in
  PR #101; its final `.12` opacity, measured review and release receipts are
  documented in `docs/HOMEPAGE_TOPOGRAPHIC_REVIEW_2026-10-05.md` and PR #101.
  A follow-up requested by Ben on 2026-10-05 is in source on
  `codex/topographic-subpages-20261005`: shared blue contours replace page
  grids, addresses select subtle profile variations, and decorative layers
  move slowly, including on the dark Analysis band. The motion exception and
  fallbacks are in `docs/VISUAL_AND_MOTION_SYSTEM.md`. Private preview only;
  production output has not been regenerated, committed or deployed for this
  follow-up. Final homepage suite: 107 checks, 106 passed and one skipped;
  preview, veil and historical identity suites also ran. Private review:
  63 page/width combinations, 18 glyph-contrast samples, no browser errors
  or local asset failures; historical byline regression clears 5:1. The
  complete private tree validates with the same 10 historical warnings.
  Review at `http://127.0.0.1:8773/analysis.html`; evidence is in
  `/private/tmp/ipr-topographic-subpages-review/report.json`. Ben approved
  the private preview and authorized source/docs commit and push on 2026-10-05.
  The branch is now synced with main at `efee36fe2`, preserving the Desks map
  and homepage opening. Integration review passed: 193 tests with one skip,
  plus 485 preview tests with one skip. The opening composition helper finishes
  only overlay animations, leaving ambient background loops intact. The full
  integration group passed on rerun after that fix. The refreshed private
  preview passed 63 page/width checks and 18 glyph samples; unchanged production
  output still validates with 10 historical warnings. Ben authorized the branch
  sync and pull request in this chat. PR #105 merged as `a0dd1aa95`. Ben
  authorized its release with #106 on 2026-10-05 (DECISION_LOG): output
  `d8289a143`, deploy run 37404728604; live on every page, including the 17
  PLA Watch pages, with no overflow or console errors at 1280/375.
* **One analysis publication (source ruling 2026-09-30; render authorized
  with No. 14 corrections on 2026-10-03).**
  The PLA Watch has been absorbed into Indo-Pacific Record Briefs as the
  historical portion of one unified analysis publication. Historical
  publication metadata and URLs are preserved for provenance and
  compatibility, but the site does not present The PLA Watch as a separate
  archive product (DECISION_LOG 2026-09-30). Analysis opens on the Briefs
  masthead and the latest Brief, which is the newest item of the whole
  collection by publication date (week ending), never by issue number.
  No. 15 now leads the public site. The catalog, "All Briefs", lists every
  item newest first (number then slug only break ties), the earlier issues
  among them with "From the former series The PLA Watch · published under/by
  <masthead>" as a secondary line; there is no
  legacy-archive section. The labeling key follows, then the Collections and
  Series tables as closing reference (every desk row kept). The home band
  leads with the same item and links into Analysis. "Briefs in development"
  appears only when the collection holds no item at all. `/pla-watch.html`
  still resolves as a compatibility bridge ("The PLA Watch is now part of
  Indo-Pacific Record Briefs": a pointer to Analysis, the preservation notice
  and a collapsed block of citation text under the original anchors, no issue
  list). No page, navigation or footer links to it. The historical issue pages' shared
  footer (`site/templates/pla-watch-base.html`) now calls each an earlier
  Brief in Indo-Pacific Record Briefs; these source changes are included in the
  authorized correction render. No. 14 retains the owner approval recorded
  on 2026-10-03. Briefs are marked turquoise on the band and compass blue on
  paper (DESIGN_SYSTEM §3).
* **No. 1 (2026-05-09 pilot) through No. 13 (week ending 2026-08-08) are
  published.** No. 14 is approved with corrections (below).
* **The cadence lapsed after No. 13, and its recovery is ruled.** No edition
  exists for the weeks ending 2026-08-22 or 08-29; w/e 2026-08-15 is No. 14
  (below). The owner ruling of 2026-09-03 (`DECISION_LOG.md`) prepares
  **08-15 and 08-22 as retrospective
  editions**, rules **08-29 a disclosed gap** (36% of that window was never
  relevance-screened), and **resumes normal cadence at 09-05**. Restoring
  cadence remains the first priority in `docs/ROADMAP.md`.
* **No. 14 approved with corrections (owner ruling 2026-10-03).** The
  reviewed draft and correction packet are approved for publication with the
  visible correction date 3 October 2026; see DECISION_LOG and
  `docs/NO14_CORRECTION_PREPARATION_2026-10-03.md`. It retains number 14,
  existing URL, week ending 2026-08-15 and retrospective identity. Its earlier
  unapproved service since 2026-09-05 remains historical provenance; approval
  is not backdated. The numbering gate is cleared; 15 is available but has
  not been assigned. Publication verification belongs in the release record.
* **14 editions now exist in the tree, all publicly served** (No. 14 now
  approved with corrections, above). No. 14 is the first
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

**Indonesia and South Korea — merged; bounded Actions collection verified
(2026-10-06).** Ben authorized commit/PR and durable shadow collection, then
reported the merge. PR #110 merged at `a8e6d5a26`; its exact-head full CI passed
3,478 tests with two skipped, the ten-warning validator and DB/output preservation.
Manifests remain outside `desks/`; neither desk enters production discovery or
the public registry. Indonesia's scope is Kemhan Berita institutional news.
South Korea's is the separately governed Policy Briefing portal's MND-labeled
republications and linked HWPX; MND publication paths remain unrequested.
One manual main-hosted run per desk traversed 2026-09-30 through 10-06, reread
robots and retrieved/extracted all 14 Indonesia records and four Korean releases.
All were duplicates: zero inserts, updates or fetch/extraction/access failures.
Both runs published append-only state successfully. Current pinned heads:
`shadow/indonesia-kemhan` (`9fe9f6fd`) and `shadow/korea-policy-briefing`
(`a1088ea1`). Artifacts exactly match clean remote clones; all historical rows,
captures, ledgers and first-success clocks remain unchanged. Machine packets have
zero findings and supply no human sign-off. Each desk still has only one successful
logical date, October 6: two same-day runs do not establish periodic reliability.
The main tree remained unchanged by collection. Human checkpoints, source reuse
terms, completeness and cadence/silence review remain open. Nothing is promoted
or qualified. Ben authorized daily shadow collection at 17:17 UTC for Indonesia
and 17:47 UTC for South Korea, with the existing six-day lookback and 40-record cap.
The cadence branch is synced to main `ba5885c30` (PR #112), without workflow or
schedule conflicts. Main remains manual-only for these candidates until separate
owner authorization and merge of the cadence PR. This phase stops at a clean,
mergeable, CI-verified draft PR; no dispatch or activation is authorized.
Reviewable scope and activation sequence:
`docs/INDONESIA_KOREA_CADENCE_PROPOSAL_2026-10-06.md`. Actions receipt:
`docs/INDONESIA_KOREA_ACTIONS_VERIFICATION_2026-10-06.md`. Initial native launch
and CI/conflict history: `docs/INDONESIA_KOREA_SHADOW_LAUNCH_2026-10-06.md`.
Initial research and reusable prompt:
`docs/INDONESIA_KOREA_DESK_EXECUTION_2026-10-06.md` and
`docs/INDONESIA_KOREA_DESK_EXECUTION_PROMPT.md`.

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

**The Day 30 packet was verified on 2026-09-28 and has not been reviewed.**
- Built formally from state commit `be52cc125` (32 ledgers, latest
  `shadow_day` 30), it reproduces the recorded state tree `ad97f27d…`
  exactly: 59 records, `publishable: yes`.
- The recorded package id `4ad9a838…` cannot be regenerated, because its
  `--as-of` and `--state-ref` were not recorded. A review binds to the packet
  it actually builds.
- The packet shows pre-overlay stored bytes, so the dispositioned entity
  damage will be visible to the reviewer.
- The exact invocations, scope options (59 complete, or 32 since Day 14) and
  owner steps are in `docs/DESK_CONSOLIDATION_AND_BRIEF_PREP_2026-09-28.md` §3.

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

**Philippines AFP — scheduled shadow reliability evaluation; activation PR pending,
2026-10-06.** PR #109 merged with exact-head guard on
`31719bed3d5b4c5de0b248a8d2b9b1be06e66e2c` as
`cc8d36646af1e2eb6026a17eaefd20378585faac`. Fresh Actions CI `37524618783`
passed 3,436 tests (two skips), output validation with ten governed warnings,
and tracked DB/output immutability. The earlier `0ab1eccf5` failure compared
nominal CSS line-height 28.272px against Chromium's actual 28.265625px line.
The test-only repair measures a natural rendered line without tolerance; its
regression still rejects one-pixel viewport/element clipping. Product CSS and
all nine AFP-specific source hashes were unchanged at that merge.

**One live GitHub-hosted rehearsal completed successfully:** Actions
`37527985057`, attempt 1, collector commit `cc8d36646`, dispatched manually with
`publish_state=false` and no target-date override. Retained evidence reconciles
1,090 unique rows across 11 pages ending in `next:null`; 13 recent eligible
items, two body requests/retrievals (`afp:1398`, `afp:1397`), 11 explicitly
unselected samples. All 15 requests stayed on direct official AFP hosts.
Fresh www robots returned 200/Allow; API robots returned the reviewed 404 with
`X-Robots-Tag: noindex, nofollow`; both payload hashes matched policy. No access,
fetch, extraction or identity failure was recorded. IDs/slugs, listing/detail
publication timestamps and original capture hashes were independently checked.
The two additional rows explain growth from the historical 1,088-row replay;
no prior identity/date metadata changed. Nine same-title/date groups remain
visible and are not merged. Artifact `ph-afp-shadow-37527985057-1`
(ID `11442459154`, 90-day retention) contains the ledger, request receipts,
robots/listing originals, closed shadow DB with original detail captures, and log.

**Scheduled shadow collection owner-authorized; no live AFP cron until separate
PR merge.** Scheduling branch `codex/ph-afp-scheduled-shadow-20261006` starts
from current main `a8e6d5a26`, including #108, #109 and subsequent #110. It proposes
one daily cron at 06:40 UTC, normal 14-day/cap-100 collection with cron-aware
logical dates and automatic successful isolated state publication. The manual
path remains a two-body rehearsal, artifact-only by default, optional explicit
publication and no clock start. Failed/partial attempts retain artifacts and do
not publish state; non-force append-only publication rejects divergent writers.
The AFP shadow manifest is enabled outside production discovery with desk
`active: false`; AFP remains an anchor candidate and NSC supplemental. The current
default-branch workflow remains manual-only until merge; the proposed event
distinction is documented above. During the rehearsal, state publication was
skipped; no `shadow/ph-afp`
branch or reliability clock was created. Main, gh-pages and every shadow ref
were unchanged across the rehearsal. Actual merge DB/output/desks object IDs
match pre-merge main. No production DB/output generation or deployment occurred.
Direct first-party API evaluation and honest IPR About-contact identity remain
owner-approved (DECISION_LOG 2026-10-06); no proxy or alternate egress is allowed.
Policy changes stop for review. This single bounded success does not establish
ongoing reliability, full-window body coverage or qualification. Ben reviewed the
live evidence and authorized recurring AFP shadow collection
and isolated durable state. The scheduling PR still requires clean exact-head
CI, final review and separate merge authorization. After activation, require
seven consecutive terminal-successful scheduled days plus durable human review
of every new record when five or fewer are inserted, otherwise at least five
representative new records. Then assess reliability, review results, NSC
supplementation, source breadth and historical backfill; never graduate
automatically. Standing qualification gates remain. Focused AFP validation: 238
tests pass; local validator passes with ten governed warnings and tracked
DB/output/desks unchanged. Full offline suite and validator remain the PR gate.
Full evidence and remaining gates:
`docs/AFP_ACTIONS_GATE_2026-10-06.md`; historical preparation receipt:
`docs/AFP_SHADOW_INTEGRATION_2026-10-06.md`.

Japan's policy correctness repair merged in PR #108 at
`ef89d5f3d11bf5a8ebb7e6be2c73785c6f10fb5c` after exact-head offline CI passed.
Japan's 1.49% full-text coverage limitation remains unresolved. PR #79 is closed
as superseded by #109. This current integration status supersedes the AFP PR
status in the earlier Japan/Philippines completion assessment. The accurate post-run
checkpoint is carried into the scheduling branch for commit, preserving later
current-main work. No production or broader Philippine source is authorized.

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

**Japan/Philippines completion assessment — 2026-10-06.** Neither desk may
graduate. Evidence, the per-gate checklist and immutable state/PR locators:
`docs/JAPAN_PHILIPPINES_DESK_COMPLETION_2026-10-06.md`. Latest Japan state
`e890112` has 5 usable PDF bodies and 149 outstanding gaps (146 challenges,
one size refusal, two PDFs without a text layer). The September 22–October 5
RSS-date window has one stored body among 67 distinct URLs (1.49%); this is
not all-MOD publication coverage. Dates and broader HTML discovery remain
blocked. A bounded GitHub Actions re-probe on 2026-10-07 (run
`37678838045`) found readable/allowing robots policy, then HTTP 403 with
`Cf-Mitigated: challenge` on Joint Staff Japanese, Joint Staff English,
JMSDF English and JASDF English indexes. Public crawler visibility therefore
does not change the collector boundary. No new Japan adapter or source is
authorized; see `docs/JAPAN_OFFICIAL_ROUTE_REPROBE_2026-10-07.md`.
**Policy defect repaired locally:** the old runner hard-coded `allowed` without
reading robots. Source now enforces current policy before requests and records
typed failed evidence on refusal; historical compliance remains unproven.
Correctness checkpoint in source; not run in Actions, activated or published.
AFP PR #79 remains draft at `b29e7edb0`, conflicting with current main.
Its existing adapter passed a bounded Mac rehearsal: 11 listing pages / 1,088
rows and two usable recent bodies; no state or production writes. AFP+NSC is
the proposed portfolio, not an approved desk. NSC has four healthy quiet runs
and no stored bodies; Coast Guard policy is challenged, DND policy unreadable
in the current probe. Existing AFP work was inspected, not replaced or modified.

**Japan MOD** — selection repair merged in PR #95; measured post-merge on
2026-10-02 in [run 37033909330](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37033909330),
collector `30b7169c892a48049efe538f02f8fcc2aff6d481`. State branch `shadow/jp-mod`:
[commit 138c4e20b7b06ba766bab063cc544c2d132e7791](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/138c4e20b7b06ba766bab063cc544c2d132e7791).
Day zero remains 2026-08-27T02:14:38Z.
- **Selection recovery observed; document coverage remains partial.** 54
  previously unrecorded URLs received cap space (31 news, 23 site updates),
  including September 29–October 2 items. Zero new usable bodies were inserted;
  the four previously stored PDFs remain unchanged. Result `ok_all_duplicates`
  accompanies health **`partial`**, not a full-coverage success.
- 140 outstanding gaps: 68 news, 71 site updates and one historical
  source-unassigned challenge. These comprise 137 challenges, one oversized
  response and two PDFs without a text layer. All 86 prior gap rows and their
  original title/date/reason/first-seen provenance remain preserved.
- The two reachable Japanese RSS sources are explicitly enabled for shadow;
  disabled and `_not_collected` entries are excluded. Known challenges consume
  no fetch slot; new/deferred URLs precede retries and PDF revalidation under
  the unchanged 40-item per-source ceiling. Challenges are never bypassed.
- This run had zero deferred or carried-pending URLs. Persistence across feed
  eviction and priority over retries/revalidation are **regression-test
  guarantees, not live observations from this run**. Sustained arrivals above
  the ceiling would grow a visible backlog. Historical evidence remains:
  42 items were deferred on 09-27 and nothing since about 09-18 had been captured;
  old counts cannot reconstruct the missing deferred URLs. No historical loss
  recovery is claimed. Old ledgers, cutoff and date-misattribution evidence
  are untouched; legacy gaps remain unassigned unless observed in a feed.
- No checkpoint review is on record; Japan remains shadow and unqualified.

**All nine Japan ledgers inspected on 2026-09-03 carried an execution
date, not a slot date.** Japan's cron sits at 22:40 UTC; the inspected
scheduled runs started late enough to cross UTC midnight — observed lateness 1h50m to 7h38m.
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

**US Indo-Pacific, DVIDS route — paused 2026-10-07.** State branch
`shadow/us-indopacom` remains at `a36f67aee`, containing the only successful
remote collection: manual run 35476931301 on 2026-09-19, which inserted 40
records. Scheduled collection then failed on **18 consecutive logical days,
2026-09-20 through 2026-10-07**, every time before feed discovery because
`robots.txt` returned HTTP 502 or 504; the first failure was run 35512831659
(HTTP 504) and the latest was run 37646622735 (HTTP 502). No failed run
published state.

The source remains publicly present and DVIDS continues to advertise RSS as a
supported product, but this repository has not established why its GitHub-hosted
policy request fails. That is an egress/access-reliability finding, **not** a
claim that DVIDS has disallowed the collector. The daily 08:40 UTC cron is
removed in the pause PR; `us_shadow.yml` remains manual-only for a separately
owner-authorized re-probe. No alternate host, browser identity, proxy, policy
bypass or automatic retry is authorized. The public US Indo-Pacific desk remains
`access_blocked` because the command website's own permission basis is still
unavailable. See `docs/US_DVIDS_EGRESS_PAUSE_2026-10-07.md`.

**Failure evidence is not a healthy-body claim.** Singapore and US
workflows push state only after successful collection; failed attempts
survive in 90-day Actions artifacts. Japan's workflow repair also persists
completed failure ledgers/gap rows after validating the collector commit,
closed-state hash and immutable history, then marks the job failed. Crashes
and incomplete attempts cannot push. This prevents an all-fetch-failure batch
from consuming the same first cap on every run. These changes merged in PR #95;
the successful post-merge run above did not exercise the failed-attempt path.

**Philippines NSC official statements: adapter merged in PR #93; isolated
runner/workflow merged in PR #94; activation merged in PR #96 (2026-10-02).**
`scripts/shadow_collect_ph_nsc.py`, `ph_nsc_shadow.yml`, prospective seven-date
windows, owner-approved public state branch `shadow/ph-nsc`, daily 10:10 UTC
plus explicit manual `target_date` recovery via `core/shadow_schedule.py`. The manifest is
now enabled only under `shadow/ph_nsc/`; no Philippines production manifest
or registry entry exists. State remains outside the checkout, captures retain
exact bytes and hashes, ledgers preserve adapter window/policy evidence and
post-ID provenance, and failed attempts push nothing. The dedicated adapter
suite remains 101 tests; additional runner/workflow tests exercise fixtures
and a local bare remote. Neither output nor the production database is changed.
[Run 37072106688](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37072106688)
used collector `302a74555a3503ea344351b1c99c64c128911104`, explicit target
2026-10-02 and the September 26–October 2 window. Result `ok_no_publications`,
health `ok`: robots/listing egress and initial public state persistence were
verified, with zero article requests and zero discovered/selected/retrieved/
inserted records. State branch `shadow/ph-nsc` was initialized at
[commit 2dd38f1bcfc598f1eca66082b626146023edf7e7](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/2dd38f1bcfc598f1eca66082b626146023edf7e7).
The artifact matched state hashes; the collector checkout stayed clean and
no SQLite sidecars remained. A quiet window establishes no article-body egress.

**Owner settings approved 2026-10-02:** public shadow state in the existing
repository, excluded from the published site and production collection, with
the unchanged full header `ChinaMilWatch-ShadowCollector/0.1
(+https://chinamilwatch.org; research archive; contact via site)`. “Private” was
planning wording, not a confidentiality requirement. No private remote, new
credentials or contact details are introduced. Ordinary 10:10 UTC scheduling
remains in place; one manual run establishes no multi-day reliability. The exact
bounded post-merge verification procedure is in `shadow/ph_nsc/README.md`.

An authorized 2026-10-02 rehearsal used the adapter's own `requests` transport:
robots.txt and the category returned HTTP 200; discovery for 2026-06-16 through
2026-07-08 returned exactly two expected references; both statement fetches and
extractions succeeded (`nsc:3108`, `nsc:2269`) with no database, output or
production writes. The live category exposes six statements from 2026-06-03
through 2026-07-08 and no pagination. The sitemap contains only the homepage;
the two-page author archive exposes those same six Official Statements and
page 3 is 404. **Still open:** multi-day access reliability, reuse permission,
pre-2026-06-03 historical completeness, the unresolved-but-not-reproduced
gambling-content anomaly, article-body egress/extraction/capture persistence in
Actions and human checkpoint review. Scheduled collector identity
and public state visibility are owner-approved; reuse/republishing remains open.
Two robots matchers will exist once draft PR #79 (AFP, untouched) lands; unify
them then. Gate wording and evidence:
`shadow/ph_nsc/README.md` and
`docs/PH_NSC_ADAPTER_REVIEW_RECEIPT_2026-10-01.md`.

**Vietnam Desk: built and rehearsed, not launched (PR #107 merged 2026-10-07).**
An owner-authorized exception to the
geographic deferral (DECISION_LOG 2026-10-05). The registry declares
`vietnam` at `research`, manifest null, `has_production_records: false`; no
count is shown. Pilot source: the English defense tag of Viet Nam Government
News, `vn_vgp_defense_en`, Tier B newsroom reporting. Adapter
`scraper/sources/vn_vgp.py`; runner `scripts/shadow_collect_vietnam.py`;
dispatch-only `vietnam_shadow.yml`; review kit
`scripts/review_vietnam_shadow_state.py`; manifest and scope in
`shadow/vietnam/`. The orphan state branch `shadow/vietnam` does not exist on
origin.

**Ministry continuation (2026-10-07, merged PR #107):** isolated adapters
now read Public Security's Vietnamese foreign-affairs RSS and Industry and
Trade's Vietnamese energy/foundational-industry first pages. All three passed
body, duplicate and quiet live rehearsals (28 capped requests, five reports),
with separate source state/clocks and deterministic local reviews. Both runners
pass the shared cross-process host gate. Defence (`bqp.vn`/`mod.gov.vn`) remains
at a robots script challenge; Finance (`www.mof.gov.vn`) at a robots app shell.
No ministry workflow or remote state was published. Registry remains research;
no activation or qualification. The continuation evidence is in
`docs/VIETNAM_MINISTRY_EXPANSION_2026-10-07.md`. The separate readiness draft
adds a main-only dispatch workflow for a serial ministry batch and source-bound
Day 7/14/30 packets. No rehearsal clock is transferred. Exact budgets, public
approved ministry retention/identity, publication failure boundaries and exact first
action: `docs/VIETNAM_REMOTE_ACTIVATION_PROPOSAL_2026-10-07.md`.

- **Measured 2026-10-06 UTC**, 26 requests under the full identity: the tag
  page lists 24 items, 2023-11-16 to 2026-09-09, with no published
  pagination, and 12 articles extracted from exact bytes. The tag is not a
  complete defense category (two observed counterexamples). The ministry's
  English site served a script page for `robots.txt`; the People's Army
  Newspaper redirected to the same address. Both are unmeasured, not refusals.
- **Rehearsed live, with state pushed only to a local bare remote:** a
  body-bearing run (2026-08-05, two articles), a duplicate re-run and a quiet
  seven-date window, with coherent state commits and a formal day-07 packet
  that reproduces deterministically (built at shadow day 0, before the
  checkpoint). This is persistence evidence, not Actions egress or
  reliability.
- **Open before the first dispatch (owner):** state location and visibility
  given the publisher's "All rights reserved" notice; remote Government News
  dispatch and scheduling remain unapproved. The shared transport now uses the
  owner-selected Indo-Pacific Record identity, verified offline only. Promotion
  would still need 30 collecting days and the Day 7/14/30 reviews.
- Evidence and criteria: `docs/VIETNAM_DESK_FEASIBILITY_2026-10-05.md`;
  procedure: `shadow/vietnam/README.md`.

**Production preservation uses separate baselines.** The earlier reviewed
branches/Japan verification used a 7,209-file production DB/output snapshot;
the later NSC run used its own 7,254-file before/after Git blob and file-list
snapshot. Each remained unchanged against its own baseline. These counts are
not a shared snapshot or a change caused by shadow collection.

**Next evidence review: around 2026-10-09**, after ordinary scheduled runs.
Review NSC logical-date continuity, robots/listing/refusal health and body
retrieval/capture evidence only if publications appear; review Japan admission,
backlog/gap persistence and usable-body yield separately. This is a human
review date, not a qualification threshold. Neither desk is promoted.

## 6. Known technical debt

* **PR offline-check draft efficiency (owner review pending, 2026-10-07).**
  `codex/pr-offline-efficiency-20261007` skips the heavyweight job while draft;
  ready/non-draft events keep the full exact-head suite, Chromium, validator and
  preservation gate. Skipped checks are never merge evidence. Accessible GitHub
  APIs report main unprotected and no rulesets; owner exact-head review remains
  necessary. Profiling and savings: `docs/PR_OFFLINE_CI_EFFICIENCY_2026-10-07.md`.
* **Governed validator baseline: exactly 10 warnings.** Three
  no-date-source-trail warnings (eds. 2026-05-09/05-16/05-23), two
  `n_significant` warnings with no marked trail entry, one pilot week-span
  warning, three missing LinkedIn files (eds. 1–3), and one cadence gap
  (2026-07-18 → 2026-08-01). Any **new** warning must be explained here before
  it is accepted; none is ever fixed by invention.
* **LLM usage is now recorded per run (2026-10-01), but no record exists
  yet.** `.github/state/llm_usage.jsonl` is appended by the workflow's own
  telemetry step on the first CI run after the telemetry lands (the pipeline
  writes only a runtime file, so local runs never touch it). It is operational
  accounting with estimated cost from a pinned price table
  (`analysis/pricing.py`), not an invoice. Two decisions wait on it: whether to
  merge summary and categorization into one call, and whether categorization
  can move to the relevance model. Neither is decided (DECISION_LOG 2026-10-01).
* **Processing states exist; paused records are not shown separately in
  public.**
  - The retry budget (5) and the `retriable`/`paused`/`terminal` states are
    implemented (`core/processing_state.py`, 2026-09-16).
  - `terminal` is reachable only through an adapter's content verdict, which
    only `global_times_mil` and `xinhua_mil` supply.
  - Measured 2026-09-28: 7 paused, 5 retriable, 0 terminal.
  - Publicly, paused records are shown as `analysis_incomplete`.
* **616 unscreened records** (China desk 566, Singapore 50). None of the China
  ones is dated in 2026-09-14 → 09-27. This is not urgent, since no edition
  cites them, but it is the defect class that previously stranded material.
  Drain only in scoped, windowed chunks.
* **Singapore was screened by China-scoped rules**, and all 14 of its screened
  records were rejected.
  - Fixed in source on 2026-09-29 (`processing/screening.py`): Singapore is
    judged against its registry scope.
  - Singapore records are held out of the daily queue and
    `backfill_unscored.py`, because post-relevance analysis is China-only.
  - No stored verdict changed.
  - Re-screening the 64 affected records costs about $0.27 at most, and needs
    authorization plus a human review of the proposal.
* **A pre-collection test failure cancels the day's collection.**
  `daily_update.yml` runs the offline suite before collecting. That cost
  09-15, 09-18 and 09-19, and 09-15 was not recovered.
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
* **The fix for the intermittent veil geometry test is included in the
  record-surface overhaul.**
  * **The cause.**
    `test_pla_watch_veil_contrast` · `test_no_box_moves_and_no_page_overflows`
    compared two separate page loads to 0.01px without waiting for the Google
    Fonts faces. A title set in a late-arriving face measured about 0.14px
    narrower, so the test failed intermittently, at HEAD `9aace937d` too.
  * **The fix.** It came from a separate task and was applied unchanged:
    patch sha256 `1d9addf8…0657849`, resulting blob `1e77235f6055…`. Every
    measurement now waits until the page's fonts have settled, and a font
    still loading after 30 s fails the test. The treatment is measured on and
    off in one page load, so both measurements use the same fonts. The
    tolerance and the assertions are unchanged.
  * **The evidence.**
    * Cloud: 20/20 fractional-width runs, 16/16 delayed-font runs.
    * This Mac: before the fix, the test failed in 2 of the 7 full-suite
      runs logged here, one of them at HEAD. After it, the geometry class
      passed 20 consecutive fresh-process runs and the full suite passed
      once. That shows no regression. The cloud's stress runs are the
      evidence that the cause is gone.

## 6a. Frontend source and public output

The reader interface uses Paper Ledger for the record and Night Desk for the
historical *The PLA Watch* issues. The Ocean Signal Veil remains a
desktop-only, credited public-domain image in the home page's two-column
opening; The PLA Watch keeps its own veil. The home "Latest analysis" band
carries a CSS-only Signal Veil in its empty right side (owner-approved
2026-10-01 as a narrow exception to the gradient rule; DECISION_LOG). Briefs
remain unpublished until
editorial approval; historical issues keep their original attribution.
Standing chart rules on the live pages: the Sources chart counts stored,
deduplicated records per source at the labeled snapshot and disclaims
institutional output and coverage; Coverage's per-source chart is Text read /
Parsed for one labeled run and draws no bar for an unmeasured source; desk
pages call the complement of analyzed records "Not analyzed" and say it is
not a queue. Faint ledger ruling appears only in wide outer margins.

**Desks map (2026-10-05, PR #104, owner-approved):**
`desks.html` is now a Natural Earth map of the Indo-Pacific (DECISION_LOG
2026-10-05). Each declared desk is a `section.desk` plate hung from its seat
by a fine leader; plates sit in open water from 1100px, in bands above and
below the frame from 760px, and become a list under the map below that.
Scope and status explanations moved to a "What each desk reads" register
under the map; the comparison and status tables are unchanged. Placement is in
`desks/geography.json`; geometry is rebuilt with
`python scripts/desk_map.py <countries-50m.json>`. `desks.html` grows from
about 13 KB to about 92 KB (69 KB of inline map geometry), inside the 120 KB
page budget. The custom-property guard
(`test_every_custom_property_used_is_declared`) now also allows the plates'
inline placement properties (`--w*`, `--m*`) and the page-set `--on`.
The Vietnam plate (`research`, seat Hanoi) makes five. From 760px to 1099px it
hangs beside the seat instead of into a band (`is-mid-side`, narrower), the
one exception, because Hanoi sits between Beijing and Singapore. A private
render measured `desks.html` at 98,442 bytes.

**Homepage atlas experiment (2026-10-01):**
`styles.css` replaces the home page's margin grid with a compact pale blue-gray
vector field: thirteen closely spaced abstract contours and two polygon fills.
The field is confined to paper margins at >=1200px; opaque hero and Briefs
backgrounds separate it from both Signal Veils. The Ocean Veil keeps its crop
at reduced opacity. Narrower screens keep plain paper. No content, layout,
database or `output/` change. Direction approved 2026-10-01; source
implementation complete. Production output has not been regenerated or
deployed.

**Homepage opening title (2026-10-05, merged and live):**
`site/preview/intro.js` adds a ~2.4s once-per-tab title over a procedural
WebGL ocean on the homepage only (V&M §1.1). Its exceptions to the motion
doctrine and the 10 KB JS budget are owner-approved for this component
only (DECISION_LOG 2026-10-05); it skips once the page has painted.
PR #103 merged as `a957aff`; output regenerated in `efee36fe2`
(`index.html` script tag + `intro.js` only; database untouched); deployed
by `deploy_output_only.yml` run 37383394581 (success). Verified live on
desktop and mobile: plays once, Skip/Escape restore the page, no replay on
reload or internal return.

**Titling register (2026-10-05, merged and live):** the opening title's
setting (Source Serif 4 600, letter-spaced capitals) is the identity register
for the wordmark, footer name and hub page names (`h1.page-name`); serif
display unifies on 600 (DESIGN_SYSTEM §4, DECISION_LOG 2026-10-05).
`intro.js`, record/source/Brief titles and PLA Watch type are unchanged.
PR #106 merged as `9bf842f2d` at head `c7b6d9bbb` (offline-checks passed on
that head). Output regenerated in `d8289a143` together with #105's
backgrounds (below): `site/render.py` + `rerender_pla_watch.py --no-covers`,
design-only diff, sidecars untouched, validator 10 governed warnings.
Deployed by `deploy_output_only.yml` run 37404728604 (success; live
2026-10-06 02:35 UTC). Verified live in Chromium and WebKit at 1280 and
375: computed wordmark/page-name/footer settings as built, record h1 in
source case, no CJK tracking, no overflow or console errors; live `intro.js`
hash equals source, and the intro plays once (~2.4s), then does not replay
on reload, at 1280 and 390.

**Record-surface overhaul (2026-09-27): "Almanac, with custody layers"**
(DECISION_LOG 2026-09-27). This change set covers source only —
templates, `styles.css` (rewritten, 161 KB → 90 KB), `browse.js`,
`citation.js`, `generate_preview.py`, tests and docs; no database, sidecar,
desk, approval or `output/` change.

* Records are grouped under the source-stated date, and every surface marks
  the source record (ink), machine output (rust) and analysis (crimson). A
  record page shows its custody (published, collected, machine reading,
  analysis) and the issues whose source trail holds its exact URL.
* Navigation: Records · Analysis · Desks · Sources · Coverage · Methodology ·
  About ("Records" was "Atlas"; every address unchanged). The masthead
  carries no search; the Records page does.
* The Records finder renders the newest 50 records on the server, loads its
  index on the first request (never on arrival), keeps its state in the
  address, and on a refused index keeps the rows and shows the approved
  message. It adds desk, order and "in a source trail" filters and removable
  filter chips.
* A week strip (records held per publication week, as links) heads Corpus by
  week and appears on Records, desk and week pages. The edition plate replaces
  the cover photograph on Home and Analysis.
* Kept exactly: both veils and the veil contract, the phone masthead
  geometry, the lead record in the first phone viewport, the approved
  caveats and messages, the three font families, the margin ruling.
* Not done here, deliberately: linking The PLA Watch source-trail entries to
  record pages. That changes `pla-watch-post.html`, which PR #70 also edits;
  it should follow that PR.
* **Owner-approved copy corrections (DECISION_LOG 2026-09-27, "Three public
  copy corrections"):**
  * The home register blurb now says "The latest analyzed records". The home
    page lists the 6 newest Analyzed records, and the Singapore Desk has none
    analyzed yet.
  * The 17–24 July outage note now reports the interruption without calling
    the window empty. It states, from the corpus, that later collection added
    9 Singapore Desk records dated 21–23 July 2026.
  * The home page describes analysis as "human-controlled".
  * Machine output is "published without human review" by the daily
    pipeline, not "never reviewed".
  * A desk's own week strip carries the outage hatch only if the desk was
    collecting at the time.

A source merge alone does not change the public site: the authorized
render-and-deploy workflow must regenerate and validate `output/` first. The
deploy gate's governed baseline is 10 warnings.

## 7. Immediate priorities

Full ordering and rationale in `docs/ROADMAP.md`. In short:

1. Restore the human analytical publication cadence. The first brief is
   ready for drafting after the No. 14 approval; it still needs its own
   editorial review and approval before number 15 is assigned. Candidate
   questions are prepared (`docs/DESK_CONSOLIDATION_AND_BRIEF_PREP_2026-09-28.md`).
2. Close Singapore's unrecorded Day 30 human-review evidence gap. The packet
   is verified; the human review is not done.
3. Scoped screening/backfill for publication-ready windows only. For
   Singapore: rule on the new rubric, authorize and review a re-screening
   proposal, and decide what analysis follows a Singapore pass.
4. Collection continuity:
   - recover or disclose the 09-15 China gap;
   - review the September 22 recovery PR (PR #85 repair merged; three records
     recovered with no analysis). Evidence: `docs/SINGAPORE_SEPT22_RECOVERY_2026-10-07.md`.
     Recovery is not yet on main or rendered; residual classification tradeoffs
     were reviewed before the authorized run;
   - decide whether collection should depend on the pre-collection test
     gate.
5. An explicit continue/pause decision on the Japan shadow desk, and its
   selection defect. Diagnose the DVIDS shadow failures without probing
   around them.

Further geographic promotion remains gated by research and review. The
Vietnam ministries have approval for narrow public retention and one exact
12-request batch after separate owner merge (DECISION_LOG 2026-10-07). Government
News remote dispatch and retention remain unapproved. Frontend
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
