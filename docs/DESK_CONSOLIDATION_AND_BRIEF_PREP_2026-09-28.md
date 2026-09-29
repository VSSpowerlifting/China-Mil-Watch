# Desk consolidation and first-brief preparation — 2026-09-28

A measured check of the existing desks before Indo-Pacific Record Briefs are
written, one bounded repair, and a research packet for the first brief. This is
evidence, not a ruling. No desk status, approval, review sign-off or
historical ledger changed. Decisions that belong to the owner are listed in
§6 and are not made here.

## 0. Provenance

| | |
|---|---|
| Repository HEAD measured | `b3821b9a1` (PR #81 merge), equal to `origin/main` on 2026-09-28 |
| Database | `pla_watch.db` as last committed by `d17646aef` ("Daily update: 2026-09-28"), blob `82dc83f9…`, sha256 `42f4e5a9…b501c` |
| How it was read | a pinned, read-only copy (`mode=ro&immutable=1`); the tracked file's hash was checked unchanged before and after the test runs |
| Shadow state | clones of `shadow/singapore-mindef` @ `66bb959de`, `shadow/jp-mod` @ `84edebfa6`, `shadow/us-indopacom` @ `a36f67aee`, `review/singapore-mindef` @ `e5cd42a5f` (all four unchanged on the remote at 21:38 UTC on 2026-09-28) |
| Run history | `gh run list` / `gh run view` for `daily_update.yml` and the three shadow workflows |
| Not done | no collection launched, no model call made, no workflow dispatched, no production database write, no `output/` regeneration, no request to `dvidshub.net` or any ministry site |

**Window.** The 14 most recent complete New York days: **2026-09-14 → 09-27**
(daily runs 139–151; run 152, 09-28, is outside it).

## 1. Measured desk assessment

Stages are kept separate, as `docs/DESK_STRENGTH_CRITERIA.md` requires:
*collecting* means stages 1–4 (discovery, retrieval, extraction, storage);
*functional* adds processing; *public* follows review.

### China — `live`

| Stage | Measured |
|---|---|
| Scheduled execution | **11 of 14 days** admitted a daily run. On 09-15, 09-18 and 09-19 all five windows failed at "Run offline test suite", **before collection started**. On 09-15 the cause was a frozen-count guard false positive (`test_identity_asset_builder.py`); on 09-18/19 it was the Xinhua tests in `test_preview_prototype.py`. The workflow reported failure, but a skipped collection is not a collection run. |
| Recovery | 09-18 and 09-19 were recovered by PR #66 (28 records, `--no-analysis`). **09-15 was never recovered.** `pla_daily`, `china_mil_online` and `global_times_mil` hold **0** records dated 09-15. `mod_china` (3) and `xinhua_mil` (11) have records for that date, consistent with their scrapers' own 7- and 3-date lookbacks. Whether the other three sources still list 09-15 was not checked (no requests were made). |
| Discovery → storage | 465 China-desk records dated in the window: `pla_daily` 289 (62% of the window), `china_mil_online` 62, `xinhua_mil` 56, `mod_china` 38, `global_times_mil` 20. `pla_daily` has records on 13 of 14 dates, `mod_china` on 11, `xinhua_mil` and `global_times_mil` on 9. No records on a date does not establish that a source was silent. |
| Extraction | 5 empty bodies in the window (`pla_daily` 4, `mod_china` 1); 58 across the corpus. One title/body mismatch was found by hand: record 3849 (`global_times_mil`, 09-04). Its title is a China–Singapore drill, but its body describes Chinese and Russian vessels and never names Singapore. It was not investigated further. |
| Processing | In the window, every China-desk record has been screened except one record marked `analysis_incomplete` (`pla_daily`). Across the corpus, 566 China-desk records await screening, none of them dated in the window. Terminal/paused/retriable states **are implemented** (commits `86aa3bceb`, `5fe7df933`): 7 records are `paused` (`retry_budget_exhausted`: ids 1103, 2678, 3432, 3708, 3946, 3948, 4137), 5 are `retriable` (1077, 3992 `analysis_failed`; 1178 `analysis_incomplete`; 1282, 4672 `empty_body_unconfirmed`), and 0 are `terminal`. Publicly, a paused record is shown as `analysis_incomplete`. |
| Xinhua | Stub in runs 139–140; `ok` from run 141 (09-17). 61 of its 63 records were rejected by the relevance screen. |
| Health reporting | `source_health_report.py` reports all sources within cadence and `check_source_liveness.py` reports all HEALTHY. Both are true of stored records. Neither sees a day on which the run never reached collection. |

### Singapore — `live` since 2026-09-21

| Stage | Measured |
|---|---|
| Held records | `15aug26-speech` and `16sep26-speech` are absent from production, as ruled. |
| Collection continuity | **Production missed 3 releases the shadow collector holds.** Of 8 shadow-observed releases dated 09-22 → 09-27, production captured 5. `22sep26-nr` and `22sep26-speech` were lost when run 146's Singapore collection crashed (`'SGMindefAdapter' object has no attribute 'collect'`, fixed by #69), because the next run looked only at 09-23. `23sep26-mq` was lost because the sitemap first listed it two days after its slug date. Cause: every adapter was handed a one-day window. **Fixed in this change, §2.** |
| Listing lag | Across the 37 releases the shadow collector saw published after it started: 33 were listed on their slug date, 3 one day late (runs that crossed midnight) and 1 two days late (`23sep26-mq`). |
| Processing | 64 records: 50 await screening, 14 were screened, and **all 14 were rejected**, their reasoning saying the text is not about the Chinese military. The relevance prompt (`analysis/prompts.py`) and keyword prefilter are China-scoped. The 7 promoted records dated 09-12 → 09-19 were screened on 09-24 and rejected, and every Singapore record screened since has been rejected too. No Singapore record is `analyzed`. This is a scope decision for the owner (§6); screening was not changed here. |
| Shadow after promotion | Still running daily: 40 ledgers; recent runs `ok`, health `ok`. Missing target dates 08-26 and 08-31 (already dispositioned in the Day 7/14 reviews); duplicate dates 08-29 and 09-01. |

### Japan — `shadow`

| | |
|---|---|
| Implemented | yes: `scraper/sources/jp_mod.py`, `scripts/shadow_collect_jp.py`, `japan_shadow.yml` |
| Scheduled | yes, daily |
| Collecting | **discovery only.** 34 ledgers. Every recent run is `ok_all_duplicates` with health `partial`. Only **4 bodies** have ever been stored, all PDFs dated 08-27/08-28. There are 84 unretrieved discovery records dated 08-27 → 09-17. HTML pages are served behind an interactive challenge, which is never to be bypassed. |
| Reporting defect | Selection is capped at 40 per source, oldest first. The 76 challenged items and 4 PDFs are re-selected every run, so newer items are **deferred and never recorded**: 42 were deferred on 09-27, and nothing published since about 09-18 has been captured. `ok_all_duplicates` hides this (criterion C7). |
| Rehearsed / reviewed | No review branch exists and no checkpoint review is on record. `shadow_day` is not quoted as progress (C13). |
| Public | no |
| Blocking condition | ministry access challenge, plus the owner's continue/pause ruling |
| Next bounded action | Owner rules continue/pause/stop. If continue, fix the selection order so each run reaches items it has not yet recorded, and report the deferral and challenge counts in the result label. Record-keeping only, no access change. |

### US Indo-Pacific — public desk `access_blocked`; DVIDS route in shadow

These are two routes, and they are kept distinct.

| | Command website (public desk) | DVIDS route (shadow) |
|---|---|---|
| Implemented | no collector | yes (`us_shadow.yml`, state branch `shadow/us-indopacom`) |
| Scheduled | — | daily, 08:40 UTC |
| Collecting | — | **no.** One successful manual dispatch (run 35476931301, 2026-09-19, 40 inserted), then **9 consecutive scheduled failures** (target dates 09-20 → 09-28), all `listing_failure`, `robots_status` unknown, robots.txt HTTP 504 once and 502 eight times |
| Public | no — `robots.txt` returns 403, so permission cannot be established | no |
| Blocking condition | permission | the cause of the 5xx responses is **not established**; it was not probed |

**All three shadow workflows share an evidence gap.** Collectors exit 1 when
health is not `ok`, and state is persisted only `if: success()`. So a failed
run's ledger exists only as a 90-day Actions artifact. The DVIDS state branch
holds 1 ledger; the other 9 are artifacts, the first expiring about 2026-12-19.

**AFP pilot (PR #79).** It remains a separate draft and was not touched. Its
files (`scraper/sources/ph_afp.py`, `scripts/shadow_collect_ph.py`,
`shadow/ph_afp/*`, tests) do not overlap this change's code. It edits
`PROJECT_STATE.md` too, so whichever merges second resolves a text conflict
there. Its shadow runner passes its own window, so it does not depend on §2.

## 2. Repair: Singapore's production window

**Failure.** `pipeline.py` built a single `CollectionWindow(target_date)` and
handed it to every adapter. Singapore's adapter discovers strictly by the
window it is given, so a release could be collected on its slug date and on no
other date. Three releases were lost in production's first week (§1).

**Fix.**
- `SourceAdapter.production_lookback_days` (default 0) declares how many prior
  dates a scheduled run asks an adapter to discover.
- `pipeline.production_window()` builds each adapter's window from it.
- `SGMindefAdapter` sets 6, giving seven slug dates: MOD China's span, chosen
  because the longest observed listing lag is 2 days, with room for a short
  run of failed days.
- Every China source is still handed exactly `CollectionWindow(date)`.
- The shadow collector passes its own window and is unaffected.
- A longer outage is still recovered once, on purpose, with
  `pipeline.py --date`. The window is not an outage remedy.

**Regression tests** (`tests/test_singapore_production_window.py`, 7 tests,
all offline): one per observed loss (a crashed day, a late-listed release),
plus:
- held records stay excluded;
- China windows are unchanged;
- the seven-date boundary;
- a re-discovered release, including one whose body changed, is dropped by
  `deduplicate` before the all-or-nothing insert and cannot roll back a new
  release.

Against the original code the file fails (10 errors), and with the fix it
passes.

**Residual risk.**
- Title-hash dedup (`processing/dedup.py`) can group two Singapore records with
  identical titles in one run. That can delay a record, but the tests show it
  does not lose one.
- Singapore's batch is all-or-nothing, so one page that keeps failing
  extraction inside the window withholds newer releases with it. They are
  delayed, not lost: when the failing page's date leaves the window, every
  newer date is still inside it. The delay is at most seven runs, against one
  day before.
- A run now re-fetches up to seven days of release pages, through the
  adapter's own rate-limited session. The shadow collector's daily 30-day
  lookback is already wider.
- Only `23sep26-mq` is within a future scheduled window: the 2026-09-29 run,
  if this change is on `main` and that day's test gate passes. The two
  `22sep26` releases are outside every future scheduled window.
- **One run recovers all three.** A single authorized
  `pipeline.py --date 2026-09-28 --source sg_mindef_releases --no-analysis`
  after merge has the window 09-22 → 09-28. It discovers `22sep26-nr`,
  `22sep26-speech` and `23sep26-mq`, and the held `16sep26-speech` stays
  out. This was checked offline with `production_window()` and the adapter's
  discovery over a synthetic sitemap. Any target date from 09-23 to 09-28
  also covers both dates (§6).

> **Corrected 2026-09-29 — this claim was false.** The authorized run failed and
> stored nothing. See §7.

## 3. Singapore Day 30 — the evidence needed to close the review gap

The 2026-09-21 sign-off proceeded **without** a distinct Day 30 human review
(`DECISION_LOG.md`). Nothing here marks one complete.

**The historical state.**

| Commit | Ledgers | Latest ledger | `shadow_day` | Finished | Tree |
|---|---|---|---|---|---|
| `338b2ef40fec…` | 31 | `20260918T231724+0000-35404990098.json` | 30 (first Day-30 state) | 2026-09-18T23:17:24Z | `44aa6d6d…` |
| **`be52cc1258b6…`** | **32** | `20260919T225952+0000-35474795590.json` | 30 | 2026-09-19T22:59:52Z | **`ad97f27d…`** |

The Day 30 threshold is a run finishing at or after 2026-09-18T23:03:09Z.
**`be52cc125` reproduces the recorded state tree `ad97f27d…` exactly**: 59
records, 2026-07-21 → 2026-09-19, chain coherent, 2 anomalies (no ledger for
08-26 or 08-31), `publishable: yes`. That is the state the 2026-09-19 packet
and the 59-record correction work were built on.

**The recorded package id `4ad9a838…` cannot be regenerated, and it need not
be.**
- The deterministic id hashes `--as-of`, `--state-ref` and the review mode, and
  the 2026-09-19 build recorded none of them. Ten combinations over those
  parameters (as-of 09-19/20/21, local or `origin/` ref, complete or focused)
  produced other ids.
- The historical claim ("same invocation twice → same id") is consistent with
  this and is left untouched.
- A sign-off binds to the packet the reviewer actually builds and reviews.

The invocations below were built from `be52cc125` on 2026-09-28 in scratch
space. Neither is signed or published.

```
.venv/bin/python scripts/review_shadow_state.py \
  --state-repo <clone> --state-ref shadow/singapore-mindef \
  --state-commit be52cc1258b6d858e7938a5a55605c014d106641 \
  --checkpoint day-30 --as-of <the actual review date> \
  --review-all --out <scratch>                     # 59 of 59; 2026-09-28 build: fc2b9db7…
  # or, instead of --review-all:
  --since-ledger 20260902T231841+0000-33694377692.json   # 32 of 59; 2026-09-28 build: 2619cb4b…
```

Rebuilding with another `--as-of` changes the id. The review must use the
actual review date. It must not be backdated, and its packet must not be
presented as contemporaneous.

**What the reviewer will meet.**

- **The packet shows the stored bytes as they were before the correction
  overlay.** Three titles show `&amp;` (`12sep26-speech`, `23jul26-speech`,
  `25jul26-nr`), and bodies carry the HTML-entity damage the overlay
  corrects. These are dispositioned in `shadow/singapore_mindef/CORRECTIONS.md`
  and are not new mismatches.
- **Live pages have drifted** for `29aug26-nr` and `9sep26-nr` (captions and
  photo credits), and the CJK passages of `15aug26-speech` and
  `16sep26-speech` are damaged. The corrected-view comparison already rated
  those four AMBIGUOUS.
- **Both anomalies are the known UTC-midnight attribution finding** from the
  Day 7 and Day 14 reviews.

**To close the gap (owner actions):**
1. Choose the scope: the complete corpus (59), or the queue since the Day 14
   ledger (32).
2. Build the packet with the actual review date.
3. Compare each queued record with its live MINDEF page and the Git-bound
   stored evidence.
4. Fill `review_report.md` and `signoff.json`: reviewer, start and completion
   times, verdict, per-record determinations and an attestation that states the
   review is retrospective.
5. Publish with `scripts/publish_shadow_review.py --checkpoint day-30 ...
   --publish`. It is a dry run without `--publish`, and it has no recency
   check that would refuse a retrospective Day 30.
6. Record the review in `DECISION_LOG.md`. It strengthens the record and does
   not change the desk's status or qualify it.

## 4. The Briefs authoring gate

`core/brief_contract.py` and `scripts/author_brief.py` enforce the mechanics:
- two live desks, or one desk with a recorded exception;
- per-record desk, language and processing state;
- a coordination claim must cite the record that states it;
- no number on a draft.

Human decisions still gate a *numbered, approved* brief:

1. **No. 14 is unreconciled** (`UNRECONCILED_ISSUES = {14}`).
   - Until the owner rules, `check` refuses any issue number and none is
     assigned.
   - The recommended path, already recorded, is an `EDITORIAL_QA_CHECKLIST.md`
     review of the page as served, then a `DECISION_LOG.md` ruling.
   - Clearing the set is a code change made after that ruling, never to unblock
     a build.
   - A brief can be drafted and checked before then.
2. **The w/e 2026-08-22 disposition.**
   - The 2026-09-03 ruling prepared it as a retrospective edition.
   - The 2026-09-23 ruling closed *The PLA Watch* to new issues.
   - Whether 08-22 becomes a retrospective brief or a disclosed gap is unruled.
   - Numbering is by approval order, so this does not block a first brief's
     number, but it does decide what the first brief is.
3. **The question, window and timing.** A brief on a window already closed is
   `--retrospective`.
4. **Chinese quotations need a human translation.** `title_english` is machine
   output and is labelled as such.
5. **Approval itself.** `editorial_status: approved` is the owner's.

## 5. Candidate brief questions

**Both candidates are China + Singapore.** Both desks are `live`, so neither
needs a single-desk exception.

**Scope rules.**
- Every record cited below is in production with a stored body unless marked.
- Titles are the stored originals. Where an English title appears, it is the
  machine-generated `title_english`.
- Processing states are the site's public codes.
- Scaffolds were built from a scratch copy of the snapshot, then discarded.

**Considered and not proposed.**
- The 2026-09-04 Asia-Pacific Chiefs of Defense Conference (3846, 3859): no
  MINDEF record in the corpus.
- The 09-27 Singapore–US Strategic Security Policy Dialogue (4680): single desk,
  and the US desk is `access_blocked`.
- The Huangyan Dao drills (4653, 4704): China only.
- Forcing any of them into a comparison would be the "forced cross-desk
  comparison" the brief rules forbid.

### Q1 (recommended). How did MINDEF and Chinese official outlets describe Exercise Maritime Cooperation 2026?

A bounded bilateral development: the RSN and PLA Navy exercise at Zhanjiang.
The window is publication dates **2026-09-03 → 09-14**. It scaffolds with
`--desks china,singapore --week-start 2026-09-03 --week-ending 2026-09-14
--retrospective`, which offers 11 Singapore and 207 China candidates without
`--include-not-selected`.

| id | Institution (source) | Published | State | Body | Attribution in body |
|---|---|---|---|---|---|
| 4466 | MINDEF Singapore (`sg_mindef_releases`, tier A) | 09-05 | awaiting_screening | 2,313 | MINDEF release |
| 4472 | MINDEF Singapore | 09-09 | awaiting_screening | 1,948 | MINDEF release |
| 4161 | MOD China (`mod_china`, tier A) | 09-14 | analyzed | 2,571 | spokesperson Jiang Bin, multi-topic briefing |
| 4164 | MOD China | 09-14 | analyzed | 313 | the same briefing's exercise answer, as its own item |
| 3816 | PLA Daily (`pla_daily`, tier B) | 09-03 | analyzed | 97 | none; a one-sentence notice, usable for the announcement only |
| 3924 | PLA Daily | 09-06 | analyzed | 363 | PLA Daily reporters, Zhanjiang 09-05 |
| 4102 | PLA Daily | 09-12 | analyzed | 1,159 | PLA Daily reporters, retrospective |
| 3902 | PLA Daily | 09-05 | analyzed | 457 | **Xinhua copy** (Guangzhou 09-05) |
| 4012 | PLA Daily | 09-09 | analyzed | 665 | **Xinhua copy** (Sanya 09-09) |
| 3983 | China Military Online (`china_mil_online`, tier B, mirror) | 09-09 | analyzed | 1,952 | **Xinhua copy** (Sanya 09-09) |
| 3810 | China Military Online | 09-03 | analyzed | 556 | **ECNS copy** |
| 3881 | China Military Online | 09-05 | analyzed | 1,264 | Zhanjiang dateline, no agency named |
| 3942 | China Military Online | 09-08 | analyzed | 1,028 | bylined, shore phase |
| 3909 | Global Times (`global_times_mil`, tier D) | 09-06 | analyzed | 397 | Global Times, with expert commentary |
| 3849 | Global Times | 09-04 | not_selected | 387 | **unusable**: title/body mismatch (§1) |
| 3938 | Global Times | 09-06 | not_selected | 0 | **unusable**: empty body |

Original titles and URLs:

- 4466 — "The Republic of Singapore Navy and People’s Liberation Army (Navy) Commence Bilateral Maritime Exercise" — <https://www.mindef.gov.sg/news-and-events/latest-releases/5sep26-nr2/>
- 4472 — "The Republic of Singapore Navy Successfully Concludes Exercise Maritime Cooperation with People’s Liberation Army (Navy)" — <https://www.mindef.gov.sg/news-and-events/latest-releases/9sep26-nr/>
- 4161 — 2026年9月中旬国防部例行新闻发布 — <http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/16486372.html>
- 4164 — 中新“海上合作－2026”联演促进双方务实合作 — <http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/16486365.html>
- 3816 — 中新将举行“海上合作-2026”联演 — <http://www.81.cn/yw_208727/16483257.html>
- 3902 — 中新“海上合作-2026”联合演习开幕 — <http://www.81.cn/yw_208727/16483790.html>
- 3924 — 中新“海上合作-2026”联合演习开幕 — <http://www.81.cn/yw_208727/16483866.html>
- 4012 — 中新“海上合作-2026”联合演习结束 — <http://www.81.cn/yw_208727/16484669.html>
- 4102 — 中新“海上合作-2026”联合演习回眸 — <http://www.81.cn/yw_208727/16485244.html>
- 3810 — "China, Singapore to hold Exercise Cooperation-2026 joint maritime exercise in September" — <http://eng.chinamil.com.cn/2025xb/H_251454/L_251456/16483343.html>
- 3881 — "China-Singapore Maritime Cooperation-2026 Joint Exercise Kicks Off" — <http://eng.chinamil.com.cn/2025xb/H_251454/L_251456/16483813.html>
- 3942 — "Shore Phase of China-Singapore \"Maritime Cooperation-2026\" Naval Exercise Concludes" — <http://eng.chinamil.com.cn/2025xb/C_251453/EC/16484467.html>
- 3983 — "China, Singapore conclude joint maritime exercise" — <http://eng.chinamil.com.cn/2025xb/H_251454/L_251456/16484731.html>
- 3909 — "China-Singapore ‘Maritime Cooperation-2026’ joint exercise opens, aiming to deepen mutual trust, boost joint response capability: expert" — <https://www.globaltimes.cn/page/202609/1369945.shtml>

After wire copies are collapsed, there are **five independent institutional
accounts**:
- MINDEF (A);
- MOD China (A);
- PLA Daily's own reporting (B);
- Xinhua (C, carried by PLA Daily and CMO);
- Global Times (D).

The Xinhua items are one account, not three.

**What the records state, side by side.** These are record contents, not
findings.

- **Dates.**
  - MINDEF: 5–9 September, with a shore phase on 5–7 and a sea phase on 8–9
    (4466, 4472).
  - MOD China's spokesperson: 9月3日至9日 (4161, 4164).
  - PLA Daily and CMO opening reports: opened 5 September (3881, 3902, 3924).
  - Xinhua: a "five-day" exercise (3983).
  - PLA Daily's own retrospective: `历时5天` (4102).
- **Place.**
  - MINDEF: Ma Xie Naval Base, Zhanjiang, and waters off Zhanjiang.
  - MOD China: waters and airspace near Zhanjiang.
  - The two Xinhua conclusion reports carry a **Sanya** dateline (3983, 4012).
- **Units.** MINDEF names RSS *Steadfast* and PLANS *Dali* (4466). MOD China
  names 大理舰 and 新加坡海军“坚定”号护卫舰 (4161). Each is quoted as
  stored, and no equivalence is asserted here.
- **Serials.**
  - MINDEF lists gunnery, communications and manoeuvring, search and rescue, and
    medical evacuation.
  - The string "replenish" appears in neither MINDEF release.
  - Replenishment (`补给`/"replenish") appears in 9 China-side records:
    3816, 3902, 3924, 3942, 3983, 4012, 4102, 4161 and 4164.
- **Name.** One CMO item, ECNS copy, titles it "Exercise Cooperation-2026"
  (3810). Every other record uses "Maritime Cooperation".
- **Series.**
  - MINDEF: the fifth edition, held since 2015.
  - Xinhua (3983): the fifth; the first bilateral maritime exercise was in 2015.

**Unknown, and not to be filled by inference:**
- why MOD China states 3 September;
- what the Sanya dateline signifies;
- whether replenishment was conducted.

**What the sources can and cannot support.**

- **Supported.** How each ministry publicly characterised the same exercise,
  and where their stated facts diverge.
- **Not supported:**
  - The purpose of either navy, or any claim of coordinated messaging. No
    record states coordination.
  - Anything about MINDEF's pre-announcement. There is no MINDEF release before
    09-05 in the corpus, and that does not show that none was published.
- **Screening.** The two MINDEF records are `awaiting_screening`, so there is no
  machine reading of either. Screening them would be a paid model call under a
  China-scoped prompt (§6).

### Q2. How did MINDEF and Chinese official outlets describe Minister Chan's meeting with Admiral Dong Jun at the 13th Beijing Xiangshan Forum?

The window is **2026-09-14 → 09-17**. Singapore's records are `not_selected`,
so the scaffold needs `--include-not-selected`. Without it, no Singapore
candidate is offered.

| id | Institution | Published | State | Body | Attribution in body |
|---|---|---|---|---|---|
| 4425 | MINDEF Singapore | 09-14 | not_selected | 1,156 | MINDEF release (visit announcement) |
| 4426 | MINDEF Singapore | 09-16 | not_selected | 3,904 | MINDEF release |
| 4211 | PLA Daily | 09-16 | analyzed | 559 | none named |
| 4198 | China Military Online | 09-16 | not_selected | 1,187 | Xinhua copy |
| 4253 | PLA Daily | 09-17 | not_selected | 1,867 | PLA Daily reporter (first plenary) |

Original titles and URLs:

- 4425 — "Minister for Defence to Visit China for the 13th Beijing Xiangshan Forum" — <https://www.mindef.gov.sg/news-and-events/latest-releases/14sep26-nr/>
- 4426 — "Minister for Defence Speaks at 13th Beijing Xiangshan Forum and Meets China Minister for National Defense" — <https://www.mindef.gov.sg/news-and-events/latest-releases/16sep26-nr/>
- 4211 — 董军同出席北京香山论坛客人举行会谈 — <http://www.81.cn/yw_208727/16486847.html>
- 4198 — "China's defense minister calls for joint efforts to safeguard peace, stability" — <http://eng.chinamil.com.cn/2025xb/H_251454/L_251456/16486874.html>
- 4253 — 循安全之道 守秩序之基——第十三届北京香山论坛第一次全体会议现场观察 — <http://www.81.cn/yw_208727/16486896.html>

**What the records state.**

- **4426 (MINDEF)** reports the meeting, the witnessed signing of an upgraded
  memorandum of cooperation between SAFTI MI and the PLA National Defense
  University, meetings with five ASEAN counterparts, and a visit to that
  university on 09-15.
- **4211 (PLA Daily) and 4198 (CMO)** report the minister's *separate*
  meetings with four defence chiefs as a group: Thailand, Mongolia, Cambodia and
  Singapore.
- **Memorandum and university terms** (Chinese and English) were searched
  across all 247 China-desk records dated 09-13 → 09-20. **None of the records
  that mention Singapore contains them.** That is a statement about preserved
  China-desk records, not about Chinese coverage.

**Limits that weaken Q2:**
- Chan's speech is held in `16sep26-speech`, which is shadow-only and damaged.
  It is excluded from production and cannot be cited as public coverage.
- The university visit fell on **09-15**, the day three China sources hold no
  records (§1).
- No MOD China record dated 09-13 → 09-20 names Minister Chan. MOD China's
  09-14 briefing mentions Singapore only for the exercise (Q1).
- Every Singapore record is `not_selected` under a China-scoped screen.

### Recommendation

**Q1.**
- It rests on two tier-A ministry accounts, one from each side, with full
  bodies.
- It has three further independent Chinese institutional accounts.
- It has a closed, dated window and checkable divergences of stated fact.
- It does not depend on held, shadow-only or not-selected material, or on the
  09-15 gap.

Q2 is a sound second brief if the owner accepts citing `not_selected` records
and the 09-15 gap is disclosed.

## 6. Decisions that require the owner

1. **Recovery of the three missed Singapore releases.** After this change
   merges, recover `22sep26-nr`, `22sep26-speech` and `23sep26-mq` with one
   bounded run:
   `pipeline.py --date 2026-09-28 --source sg_mindef_releases --no-analysis`.
   Its window is 09-22 → 09-28, and the held `16sep26-speech` stays out.

   The alternative is a governed promotion from the shadow corpus. Either
   writes to production and needs authorization.

   Without either, only `23sep26-mq` returns, through the 2026-09-29
   scheduled run, and only if this change is on `main` by then.
2. **Merge.** This change is a draft; the owner merges it.
3. **The 09-15 China gap.** Record it as a disclosed gap, or authorize a
   bounded `pipeline.py --date 2026-09-15` recovery for the three sources
   affected. Whether they still list that date is unknown.
4. **Singapore screening scope.** Whether Singapore records should pass through
   the China-scoped relevance prompt at all. Currently it rejects every one.
5. **Singapore Day 30.** Scope (59 or 32) and state commit (`be52cc125`,
   recommended because it reproduces the recorded tree, or `338b2ef40`, the
   first Day 30 state). Then the review itself (§3).
6. **Japan:** continue, pause or stop. If continue, authorize the
   selection-order and reporting fix (§1).
7. **DVIDS shadow.**
   - Whether to investigate the 5xx robots responses: a single, identified
     request, never a workaround.
   - Whether shadow workflows should persist failed-run ledgers to their state
     branches, a change that affects all three.
8. **The pre-collection test gate.** A test failure currently cancels the day's
   collection; it cost 09-15, 09-18 and 09-19. Whether collection should run
   independently of the test gate is an architecture decision.
9. **No. 14, w/e 08-22, the first brief's question, and its approval** (§4).

## 7. Correction, 2026-09-29: the recovery run failed

§2 and §6 item 1 said one run recovers all three releases. They were wrong.

**What ran.** After #82 merged (`89e48a2fe`), the authorized
`pipeline.py --date 2026-09-28 --source sg_mindef_releases --no-analysis` ran
locally at 02:12 UTC on 2026-09-29.
- The window was 09-22 → 09-28, as planned.
- Discovery returned **11** releases. All 11 were fetched and 10 extracted.
- `22sep26-infographic` extracted only 178 characters of text, which is
  under the adapter's 200-character `MIN_BODY_CHARS`. That counts as an
  extraction failure.
- Singapore's batch is all-or-nothing, so the adapter withheld the whole
  batch. Nothing was stored, including `22sep26-nr`, `22sep26-speech` and
  `23sep26-mq`.
- The run recorded itself as run 153, `degraded`, with
  `sg_mindef_releases` at `extraction_failure` (`discovered=11 fetched=11
  extracted=10`).

**The local run was not landed.** It lived only in the worktree copy of
`pla_watch.db`, which was restored to `main` (sha256 `42f4e5a9…b501c`). So
production has no run 153 from it. The evidence was kept outside the
repository: the post-run database copy and the run log.

**A second fetch was made to diagnose the failure.** It re-fetched the
sitemap and the same 11 pages through the adapter, with no database write.
- The ten other pages extract.
- The three missed releases match the shadow corpus's copies exactly, in body
  length and body SHA-256: `22sep26-nr` (4,165 chars, `10866200805d…`),
  `22sep26-speech` (13,417, `0c40feac8102…`) and `23sep26-mq` (391,
  `2d0e1a352cba…`).
- Both held records (`15aug26-speech`, `16sep26-speech`) fall outside the
  window, so the window excluded them before the adapter's
  `HELD_RELEASE_SLUGS` filter was reached. Neither is stored.

**Why the rehearsal missed it.** It compared production against
`shadow_records`, which holds only extractions that succeeded. The shadow
ledgers already showed the page: `extraction_failures: 1` on every run from
2026-09-22 onwards. Nobody read them. §2's residual-risk note named this
failure mode, where a page that keeps failing inside the window withholds
newer releases with it. It had already happened in the data.

**Consequence of #82.**
- Any Singapore production window that contains 09-22 withholds the whole
  batch.
- Scheduled runs are clear of it: the 2026-09-29 window is 09-23 → 09-29.
- More generally, the seven-date window widens the all-or-nothing rule's
  reach: one page that can never be extracted now blocks seven scheduled
  runs instead of one.
- `22sep26-nr` and `22sep26-speech` cannot be recovered by a production run
  until the owner decides how an image-only release is handled.
- `23sep26-mq` should return with the 2026-09-29 scheduled run, if that day's
  test gate passes. It will be screened there under the China-scoped rules
  (see `docs/SINGAPORE_SCREENING_REPAIR_2026-09-29.md`).

**Options for the owner** (none implemented):
1. **Record it as text-unavailable.** The adapter already has a sanctioned
   path for pages that parse but carry no usable text. It keeps the title,
   URL and date and counts them in `source_run_results.text_unavailable`. The
   infographic fails earlier, at `MIN_BODY_CHARS`, so it never reaches that
   path. Routing a short body there would keep one image-only page from
   blocking the batch, and would record that it exists.
2. **Exclude infographic slugs at discovery.** That is a change to desk scope.
3. **Return `production_lookback_days` to 0 until a ruling.** That brings back
   the single-day losses #82 fixed.

The Day-30 packet is bound to state from before 09-22 (latest ledger
2026-09-19), so it does not show this. The reviewer should know that every
shadow run since 09-22 records one extraction failure, and that it is this
page.

