# Desk reliability review — 2026-09-16

A measured, evidence-first assessment of every declared desk against
`docs/DESK_STRENGTH_CRITERIA.md`. Read-only against production: no workflow was
dispatched, no state branch was written, no shadow record was merged, and the
tracked database was read from a copy.

Every figure here carries the date it was measured. Nothing is carried over
from an earlier document without re-measurement, and where an earlier figure
has gone stale this file says so.

---

## 1. Base and provenance

| | |
|---|---|
| Authoritative `origin/main` | `20bced6fdd2685025156ec84d1b0d761d9d2de76` — *State: mark daily run 2026-09-16*, committed 2026-09-16T17:46:50Z |
| Working branch | `ops/desk-reliability-20260916`, branched from that commit |
| Worktree | `/Users/benjaminyang/pla-watch-worktrees/wt-desk-reliability-20260916` |
| `origin/gh-pages` | `62e1bba894d7cb4da3a72900b126d2c7e6fb0959` |
| Tracked `pla_watch.db` | sha256 `dfce4fb5eb6490350d00b5ddc98ab83ab21db55023c6f418ed0368ba7cada19f`, 39,034,880 bytes |
| Tracked `output/` tree | `18a0c4a089a3ac83968a028253dc1d95a70379e4`, 6,250 files |

**Shadow state branches, at the moment of review:**

| Branch | Tip | Written by |
|---|---|---|
| `shadow/singapore-mindef` | `ce47ff5bf1e61ed2f6f1bc4af263e88e87ed1018` | run `35035996635`, finished 2026-09-15T23:32:16Z |
| `shadow/jp-mod` | `794ca4c7c2c434bc9d098f46a6e15ff1cf77b65d` | run `35041346248`, finished 2026-09-16T00:46:21Z |
| `review/singapore-mindef` | `e5cd42a5f3093604903d9244456b7b5562eb12ac` | Day-14 review, 2026-09-02 |

**Remote shadow collection continued uninterrupted.** Both workflows are
`active`; `Singapore Shadow Collection` (`338183736`, cron `10 21 * * *`) and
`Japan Shadow Collection` (`343223963`, cron `40 22 * * *`) each show an
unbroken run of scheduled `success` results through the review window. Neither
was dispatched, disabled, or edited here, and neither state branch was written.

**Production corpus, measured from a read-only copy 2026-09-16:** 4,229
records, 4,229 distinct URLs, max id 4,235; 140 scrape runs; freshness
2026-09-16. By source: `pla_daily` 3,580, `china_mil_online` 445,
`global_times_mil` 121, `mod_china` 83, `xinhua_mil` **0**.

> `PROJECT_STATE.md` §3 is stale: it reports 3,762 records, 127 runs, 903
> unscreened and 48 empty bodies, measured 2026-09-02. The current figures are
> 4,229 records, 140 runs, **676** unscreened and **87** empty or near-empty
> bodies. The unscreened backlog has fallen; the empty-body population has
> nearly doubled.

---

## 2. Method for the access probes

Every probe in §4–§7 was made with the project's own honest user agent, one
request per endpoint, at least two seconds apart, no retry on any 4xx. The
probe reads `robots.txt` **first** and does not request a path that `robots.txt`
disallows. No challenge was solved, no browser was impersonated, no proxy or
alternate identity was used, and no URL namespace was enumerated.

One distinction is load-bearing throughout and is recorded rather than averaged:

* **`robots.txt` → 404** means no file exists and no restriction is stated.
  This is the ordinary, permitted case (`www.81.cn`).
* **`robots.txt` → 403** means the host is refusing to tell this client what
  the rules are. Collection then has **no permission basis at all**,
  independent of whether some other endpoint happens to answer.

---

## 3. Singapore — Day-30 readiness

**Day 30 has not occurred. Do not prepare the Day-30 review yet.**

Built formally from the state branch with the existing kit:

```
scripts/review_shadow_state.py \
  --state-repo <clone> --state-ref origin/shadow/singapore-mindef \
  --state-commit ce47ff5bf1e61ed2f6f1bc4af263e88e87ed1018 \
  --checkpoint day-30 --as-of 2026-09-16 --review-all --out <scratch>
```

| | |
|---|---|
| corpus | 54 records, 2026-07-21 → 2026-09-14 |
| ledgers | 28, latest `20260915T233216+0000-35035996635.json` |
| latest `shadow_day` | **27** |
| state chain | **coherent** |
| anomalies | **2** — no ledger for 2026-08-26; no ledger for 2026-08-31 |
| publishable | **NO** — the checkpoint has not arrived |

The two anomalies are the already-disposed pair from the published Day-7 and
Day-14 reviews. **No new anomaly appeared** between Day 14 and Day 27.

**The exact remaining checkpoint date.** `shadow_day` is
`floor((finished_utc − day_zero) / 1 day)` against day zero
2026-08-19T23:03:09Z, so Day 30 requires a run finishing at or after
**2026-09-18T23:03:09Z**. Singapore's cron is 21:10 UTC but Actions lateness has
put recent finishes between 22:53 and 23:52 UTC, and five of the last fourteen
finished *before* 23:03:09 — on 2026-09-12 by 28 seconds. Therefore:

* **earliest:** the scheduled run of **2026-09-18**, and only if it finishes at
  or after 23:03:09 UTC;
* **guaranteed:** the scheduled run of **2026-09-19**.

Collection is preserved and nothing was dispatched to accelerate it.

### Health of the corpus at Day 27

Assessed across all 28 ledgers and all 54 records:

| Criterion | Verdict | Evidence |
|---|---|---|
| C1 listing | **PASS** | `listing_status == "ok"` on all 28 runs; no `listing_failure` |
| C2 robots | **PASS** | `robots_status == "allowed"` on all 28 runs |
| C4 retrieval | **PASS** | `retrieved == selected` on every run; 0 fetch failures across the whole window |
| C5 extraction | **PASS** | 0 extraction failures; **0 empty bodies** in 54 records; body length 608 – 19,766 chars, median 3,434 |
| C6 deduplication | **PASS** | 54 records, 54 distinct canonical URLs, 0 title collisions; duplicate-heavy runs are the expected steady state of a 30-day lookback |
| C7 taxonomy | **PASS** | every run terminal: 13 × `ok`, 14 × `ok_all_duplicates`, 1 × bootstrap `ok`; 0 access failures |
| C9 hash chain | **PASS** | kit reports `state chain: coherent` |
| C10 continuity | **FAIL (dispositioned)** | 2 nominal days with no ledger, both already reviewed and accepted |
| C11 health | **PASS** | `health == "ok"` on all 28 runs |
| C12 tooling | **PASS** | desk-specific kit; refuses to publish before the checkpoint; deterministic |
| C3 dates | **PASS** | 28 distinct publication days across 2026-07-21 → 2026-09-14 |
| C13 promotion | n/a | 27 days elapsed; nothing claimed |

**Is the 54-record corpus representative?** Qualified yes, with one stated
limit. It spans 28 distinct publication days over eight weeks (July 17,
August 22, September 15 records), every record carries a full body, and the
per-day maximum is 5. That is a plausible shape for a single ministry's release
stream. What it is **not** is a test of volume: at roughly two records per
publication day this desk has never been exercised against a surge, and no
statement about behaviour under one is available from inside the corpus.

**Recommendation: retain, continue collecting, prepare the Day-30 packet on or
after 2026-09-19.** Singapore is the only desk in the project that currently
passes every measurable strength criterion. Promotion still requires the Day-30
human review and an owner sign-off in `DECISION_LOG.md`, and neither elapsed
days nor this assessment substitutes for them.

---

## 4. Japan — source feasibility matrix

Probed 2026-09-16. `www.mod.go.jp/robots.txt` reads `200` and disallows only
`/a/` and `/sp/j/`; it declares no sitemap. Every path below is robots-permitted,
so each result is an **edge policy**, not a robots directive.

| # | Candidate route | Robots | Listing | Bodies | Verdict |
|---|---|---|---|---|---|
| 1 | `/j/rss/news.xml` (JA press stream) | allowed | **200**, 45,698 B, 127 items, conditional-request capable | 8 PDF / 119 HTML | **discovery only** |
| 2 | `/j/rss/update.xml` (JA site stream) | allowed | **200**, 120,216 B, 295 items | **0 PDF** / 295 HTML | **discovery only** |
| 3 | `/en/press-release/index.html` | allowed | **403** `Cf-Mitigated: challenge` | — | unusable |
| 4 | `/js/press/press.htm` (Joint Staff index) | allowed | **403** `Cf-Mitigated: challenge` | — | unusable |
| 5 | `/js/rss/news.xml` (Joint Staff feed) | allowed | **403** `Cf-Mitigated: challenge` | — | does not exist as an open route |
| 6 | `/en/rss/news.xml`, `/en/rss/update.xml` | allowed | **404** | — | do not exist |
| 7 | `/sitemap.xml`, `/j/sitemap.xml` | allowed | **403** `Cf-Mitigated: challenge` | — | unusable |
| 8 | `/j/press/news/2026/08/28f.pdf` (linked PDF) | allowed | n/a | **200**, `application/pdf`, 3.6 MB | **retrieval works** |
| 9 | `/js/pdf/2026/p20260915_01.pdf` (Joint Staff PDF) | allowed | n/a | **200**, `application/pdf`, 195,249 B | **retrieval works, no index** |

### What this actually shows

**The edge rule is not "HTML challenged, XML served."** It is narrower than the
adapter's docstring records: `/js/rss/news.xml` and `/sitemap.xml` are XML and
are both challenged. Only the two specific files `/j/rss/news.xml` and
`/j/rss/update.xml` are served. Japan has **two** open discovery routes in the
whole estate, and no more.

**Retrieval works, but only for a document family that is not the desk's scope.**
All eight PDF items in the news feed were inspected. **Seven of the eight are
the same recurring document type** — 「日米合同委員会合意について」, the
Japan–U.S. Joint Committee agreement notice — and the eighth is a Kumamoto
earthquake response item. The one retrievable family is a routine
administrative notice, not the ministry's defense publication. This is exactly
the C4 concentration failure: the ratio (6 %) and the concentration are
independent problems, and the concentration is the worse one.

**Joint Staff PDFs are served but cannot be discovered compliantly.** Route 9
returns a real document, and the Joint Staff stream is the operationally
significant one. Its index is challenged (route 4), no feed carries `/js/` items
(measured: zero in both feeds), and there is no sitemap. Reaching those PDFs
would mean guessing `p<YYYYMMDD>_<NN>.pdf` against a namespace the ministry has
not published to this project — enumeration, not discovery, and prohibited by
C1. **Recorded as a genuinely available document behind a genuinely absent
listing path, and left alone.**

**Publication dates are not reliable from the feed.** Across the 127 news-feed
items, the date encoded in the URL and the feed's `pubDate` **disagree on 38
(30 %)**. The lag is not a rounding artefact: `/j/approach/exchange/area/2026/
20260828_egy-j.html` is dated 2026-08-28 in its path and 2026-09-15 in the
feed — 18 days. `pubDate` is the ministry's site-registration time, not the
document's publication date. C3 therefore **FAILS** until a precedence rule is
written down and its disagreement rate published.

### Live collection, for comparison with the probe

Across 22 ledgers on `shadow/jp-mod`, day 0 (2026-08-27) to day 19 (2026-09-16):

* `health` is **`partial` on every single run since day 1** — 21 consecutive;
* `retrieved` is **0 on every run since day 2**;
* `stored_total` has been **4 records for eighteen consecutive days**;
* `corpus_range` is frozen at 2026-08-27 → 2026-08-28;
* `challenged` has grown monotonically to **72**, with `unretrieved_total` 74;
* fetch failures 0, extraction failures 0, robots `allowed` throughout.

The collector is behaving correctly and reporting honestly. The desk is not
collecting.

### Japan verdict

| Criterion | Verdict |
|---|---|
| C1 listing | PASS (two feeds) |
| C2 robots | PASS |
| C3 dates | **FAIL** — 30 % URL/feed disagreement, no ruled precedence |
| C4 retrieval | **FAIL** — 0 retrieved in 18 days; open-route yield 6 %, and 7 of 8 are one notice type |
| C5 extraction | UNMEASURED — too few bodies to measure |
| C6 dedup | PASS (URL + content hash, never title) |
| C7 taxonomy | PASS — `access_challenged` used correctly; not filed as fetch failure |
| C8 isolation | PASS |
| C9 hash chain | PASS |
| C10 continuity | PASS for slot-dated runs; the documented one-day historical defect is preserved, not rewritten |
| C11 health | PASS — reports `partial` honestly rather than claiming coverage |
| C12 tooling | **FAIL** — Japan has **no checkpoint-review tooling**. `scripts/review_shadow_state.py` is Singapore-specific: it re-derives Singapore's canonical URL shape, slug date and slug kind, and pointing it at Japan would validate Japanese records against Singaporean assumptions |
| C13 promotion | n/a |

**Recommendation: keep collecting, do not repair the adapter, and open a
written request for an official route.** Japan fails C3, C4 and C12. No
compliant adapter change can fix C4, because the constraint is not in the code:
the ministry's own open routes carry one retrievable notice family, and the
documents worth having sit behind an index the edge refuses. Building more
adapter surface against that would produce better-engineered emptiness.

The one action that can change the outcome is the one the doctrine already
names: **request an official route from the ministry.** Until that is answered,
Japan should stay `shadow` with its constraint stated exactly as
`desks/registry.json` states it now — discovery works, retrieval does not — and
should **not** be described as partially covering Japan. If the request is
refused or unanswered, take the replacement comparison in §7 to the owner.

---

## 5. United States — the desk can become a real shadow collector

### The currently declared target is still blocked

Probed 2026-09-16:

| Endpoint | Result |
|---|---|
| `https://www.pacom.mil/robots.txt` | **403** |
| `https://www.pacom.mil/` | not requested — no permission basis |
| `https://www.defense.gov/robots.txt` | **403** |
| `https://www.defense.gov/Newsroom/Releases/` | not requested — no permission basis |
| `https://www.usindopacom.mil/`, `https://pacom.mil/` | DNS does not resolve |

`desks/registry.json` is **correct and current**: `access_blocked` still
describes reality, and the reasoning it records — that an RSS endpoint
answering while `robots.txt` is refused gives no basis to say collection is
permitted — holds exactly as written.

### A compliant official route does exist

**DVIDS** (`www.dvidshub.net`) is the Defense Visual Information Distribution
Service, operated by Defense Media Activity, a DoD field activity. It is an
official DoD public distribution system, and unlike `pacom.mil` it states its
rules:

```
User-agent: *
Disallow: /mediarequest/ /hometownheroes/ /ajax/ /search/ /tags/
Disallow: /download/ /holiday/ecard/ /comment/ /map/
Allow: /
```

| Probe | Result |
|---|---|
| `robots.txt` | **200**, readable, permits `/rss/`, `/news/`, `/unit/` |
| `/rss/unit/USINDOPACOM` | **200**, `application/rss+xml`, 523,177 B, **413 items** |
| a `/news/…` article page | **200**, `text/html`, 69,140 B, full body present |

Measured on that feed, 2026-09-16:

* 413 items over 2026-07-14 → 2026-09-16, of which **170 are `/news/`** (the
  rest are audio 100, video 99, image 44 — not text);
* the news subset spans 2026-09-01 → 2026-09-16, **16 days, 10.6 items/day**;
* **`guid` is a stable identifier** (`news:574898`); all 170 guids unique, all
  170 links unique, **zero duplicate titles**;
* `pubDate` present on every item with a real per-item timestamp;
* `description` is a teaser (median 311 chars), so bodies require the article
  page — which retrieves.

### The honest caveat, which must be in the desk's scope text

This feed is **unit-tagged public-affairs output**, not a curated
"USINDOPACOM Press Releases and Readouts" wire. Inspected titles include
base-life and human-interest material — an Army medic at a crash scene, a
Korean War soldier's interment, a chief-petty-officer pinning. A desk built on
it would be collecting *public affairs associated with the command*, which is a
narrower and different thing from command releases, and the registry entry must
say so rather than implying the latter.

### Design, not built here

A US shadow desk on this route is feasible and should be built to the same four
barriers as the others:

* manifest at `shadow/us_indopacom/manifest.json` (**not** under `desks/`),
  source `enabled: false`;
* adapter `scraper/sources/us_dvids.py` — discovery from
  `/rss/unit/USINDOPACOM`, **filtered client-side to `/news/`** because the
  feed ignores `?type=news` (verified: the filtered and unfiltered responses
  are the same size); identity from `guid`; canonical URL from `link`; date
  from `pubDate`; body from the article page;
* runner `scripts/shadow_collect_us.py`, refusing to write inside the repo and
  never naming `pla_watch.db` or `output/`;
* state branch `shadow/us-indopacom`, own ledger, own clock, day zero derived;
* workflow `us_shadow.yml` on a cron clear of 21:10 and 22:40 UTC;
* **its own** checkpoint-review kit — not Singapore's;
* fixture-based tests only. The captured probe responses are the fixtures; no
  live-network probe becomes an offline-test dependency.

**Not implemented in this pass.** Building three collectors (this, Xinhua, and
a Japan rework) to the rehearsal depth this repository requires — isolated
multi-run idempotence, blocked and partial states, encoding, a fresh state
branch — is more than could be finished and honestly verified here, and a
half-rehearsed collector writing to a new durable branch is worse than none.
What is settled is the part that needed evidence: **the route is compliant,
open, stable, identified and retrievable.**

**Recommendation: repair — build the shadow collector on DVIDS, keep the desk
`access_blocked` until it collects.** The `access_blocked` status is about
`pacom.mil` and stays true until the desk has a source that is not `pacom.mil`.

---

## 6. China — source and backlog findings

### 6.1 `xinhua_mil` can be implemented compliantly

`PROJECT_STATE.md` records this source as an unimplementable stub because "the
listing is JavaScript/API-rendered". **That diagnosis is now stale.** Measured
2026-09-16:

| Probe | Result |
|---|---|
| `https://www.news.cn/robots.txt` | **200** — `User-Agent: *` / `Allow: /` |
| `https://www.news.cn/milpro/` | **200**, `text/html; charset=utf-8`, 59,193 B |
| links in that HTML | 198 hrefs, **186 article-shaped**, **106 distinct** article URLs |
| an article page | **200**, UTF-8, full Chinese body text extracted |

The listing is **server-rendered**. Article URLs are
`/milpro/YYYYMMDD/<32-hex>/c.html` — a deterministic canonical form carrying
the publication date in the path and a stable opaque identifier, which is
better shaped for C3 and C6 than either existing HTML source. Current volume on
the listing is 11 items for 2026-09-15 and 10 for 2026-09-16; the listing also
carries an archive rail reaching back to 2024-07-12.

**Recommendation: implement it, shadow-rehearse it, then enable it.** This is
the single highest-value source change available to the project: the China desk
is 85 % one source (`pla_daily` 3,580 of 4,229), and `xinhua_mil` is a distinct
institution at roughly ten items a day. Until it is implemented and rehearsed,
leave it enabled and reporting `not_implemented` — that is honest under C11 and
should not be reclassified to `inert` now that a working route is known.

### 6.2 The records that fail analysis on every run

Seven records appear in the error list of essentially every recent run. Their
recurrence, and their actual state in the corpus:

| id | source | in last 5 runs | stored body | live now? | class |
|---|---|---|---|---|---|
| 2678 | pla_daily | 5/5 (28 runs since 108) | **0 chars** | 200, chrome only | extraction |
| 3432 | global_times_mil | 5/5 (18 runs since 118) | **0 chars** | 200, **1,076 chars of real body** | **extraction defect** |
| 3708 | pla_daily | 5/5 (15 runs since 126) | **0 chars** | 200, chrome only | extraction |
| 3946 | global_times_mil | 5/5 | **0 chars** | 200, **4,180 chars of real body** | **extraction defect** |
| 3948 | global_times_mil | 5/5 | **0 chars** | 200, **2,340 chars of real body** | **extraction defect** |
| 3992 | pla_daily | 5/5 | 475 chars | 200, body + dateline present | **analysis-stage failure** |
| 3636 | pla_daily | 4/5 | 1,288 chars | — | **transient — cleared** |

**Evidence preserved, nothing dropped.** Every URL was re-fetched once with the
project user agent on 2026-09-16 and every one returned **200 with content**.
None of these is a dead link, and none of them is source silence.

Three findings follow:

1. **Global Times extraction is broken, not the source.** Records 3432, 3946
   and 3948 are stored with an empty body while their pages serve 1,076, 4,180
   and 2,340 characters of article text respectively. Under C5 an empty body for
   a live document is an extraction defect and must never be reported as an
   absence. This is deterministic and repairable.
2. **Two `pla_daily` records are probably not text articles at all.** 2678
   ("双舰岛搭配电磁弹射…", slideshow markers present) and 3708
   ("陆军某旅开展长途机动训练") yield ~930 characters that are entirely site
   navigation. These look like gallery or video pages with no prose body. The
   correct disposition is a **terminal "media item, no text body" state**, not
   another retry.
3. **3636 cleared itself**, analysed successfully at 2026-09-16 17:42:27 in run
   140. So the set is a mixture of a deterministic defect and genuine transient
   LLM failures, and treating all seven as one thing would be wrong.

**There is no established review mechanism to disposition them through.**
`PROJECT_STATE.md` §6 is accurate: there is no terminal processing state, no
retry budget and no poison-record disposition. Record 2678 has now been retried
on **28 separate runs** and can never clear. The mechanism has to be built
before the disposition can be recorded, which makes this the prerequisite, not
the follow-up.

**Recommendation: repair, in this order** — (i) a terminal processing state
with a retry budget, so a record stops re-entering the queue for ever and its
reason is recorded; (ii) the Global Times body extractor, with fixtures
captured from these three pages; (iii) disposition 2678 and 3708 as media items
once (i) exists.

**The July 2026-07-17 → 07-24 collection gap was not touched**, and no backfill
was attempted or prepared. It remains permanent and disclosed.

---

## 7. Replacement contingency — evidence, not a decision

**Nothing was deleted, renamed or replaced.** This section exists so the owner
can decide if Japan's official-route request is refused.

| Factor | Japan (incumbent) | Australia — Dept of Defence | Taiwan — MND |
|---|---|---|---|
| Strategic relevance | High — treaty ally, PLA-adjacent operations | High — AUKUS, Indo-Pacific posture | Very high — the central contingency |
| Official-source authority | Ministry + Joint Staff, first-party | Department + ministers, first-party | Ministry, first-party |
| **Robots / policy** | readable; permits all probed paths | **`robots.txt` unreadable from here** | **`User-agent: * → Disallow: /`** |
| Accessible-source count | **2** (both JA RSS) | **0 measured** | **0 permitted** |
| Listing accessibility | feeds served; every index challenged | not measurable | disallowed for every agent but Googlebot |
| Body retrieval | **~6 %, and 7/8 are one notice type** | not measurable | not permitted |
| Historical depth | feeds reach 2026-07-01 | not measurable | not permitted |
| Expected volume | ~127 news items / 2.5 months | unknown | unknown |
| Language / encoding | Japanese; PDF extraction needed | English; simplest | Traditional Chinese + English |
| Stable identifiers | canonical URL; date in path | unknown | unknown |
| Date quality | **30 % URL/feed disagreement** | unknown | unknown |
| Maintenance burden | low code, zero yield | unknown | n/a |
| **Verdict** | **retain, request route** | **re-probe required** | **ruled out on policy** |

**Taiwan is ruled out, and not on capability.** `www.mnd.gov.tw/robots.txt`
grants a narrow allowance to `Googlebot` and then states
`User-agent: *` / `Disallow: /`. The ministry has told every other crawler not
to collect anything. Under C2 that ends the question, whatever the site would
otherwise offer. It should not be re-examined without a change to that file or
an explicit permission from the ministry.

**Australia is unresolved, and the reason is probably local.** Every
`*.defence.gov.au` host — `www`, `news`, `minister` — sits behind the same
GovCMS/Akamai edge (`cdn.govcms.gov.au` → `e97003.dscg.akamaiedge.net`) and
from this environment returns `HTTP/2 INTERNAL_ERROR` immediately or times out
after 60 s on HTTP/1.1. That is an edge refusing this egress, and the honest
reading is *unreachable from here*, **not** *refuses this project*. The
distinction matters: no retain/replace decision should rest on it.
**Australia must be re-probed from the collection runner's own egress before
it is scored.** No browser user agent was tried and none should be.

So the primary fallback is currently **unmeasured**, the secondary is **ruled
out**, and the incumbent is failing. That is the real state of the option set,
and it is an argument for pursuing Japan's official route first rather than for
a replacement.

---

## 8. Per-desk recommendation

| Desk | Status now | Recommendation | Why |
|---|---|---|---|
| **China** | `live` | **Repair** | Functional and producing. Implement `xinhua_mil` on the now-open `news.cn/milpro/` route to break 85 % single-source concentration; build a terminal processing state; fix Global Times extraction. |
| **Singapore** | `shadow` | **Promote later** | Passes every measurable criterion. Day 30 falls on 2026-09-18 at the earliest, 2026-09-19 guaranteed. Prepare the packet then; promotion still needs the human review and an owner sign-off. |
| **Japan** | `shadow` | **Retain as declared-only, and request an official route** | Discovery works; retrieval does not and cannot be made to. 0 documents retrieved in 18 days, 4 records in 20. Do not replace on a first adapter failure; do not build more adapter against a closed estate. |
| **US Indo-Pacific** | `access_blocked` | **Repair** | `pacom.mil` is still 403 on `robots.txt` and the status stays true. DVIDS is an open, compliant, identified official route at ~10 news items/day — build the shadow collector there, with the public-affairs scope caveat stated. |

---

## 9. Remaining blockers

1. **Japan's official-route request is unwritten.** It is the only action that
   changes Japan's outcome, and no code substitutes for it.
2. **Japan has no checkpoint-review tooling** (C12), and must not borrow
   Singapore's.
3. **Australia is unmeasured** — re-probe from the runner's egress.
4. **No terminal processing state exists**, so the China backlog cannot be
   dispositioned yet and record 2678 keeps retrying after 28 runs.
5. **Three collectors are designed but unbuilt**: US/DVIDS, `xinhua_mil`, and
   any Japan rework.
6. **`PROJECT_STATE.md` §3 figures are stale** by two weeks.
