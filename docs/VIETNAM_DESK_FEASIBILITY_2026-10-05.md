# Vietnam Desk — source feasibility and shadow pilot

**Brief:** the owner's Vietnam Desk engineering brief of 2026-10-05.
**Measured:** 2026-10-06 UTC, the evening of 2026-10-05 in the owner's time zone.
**Status:** collector built and rehearsed outside production; **not launched**.
The desk is public at `research` status with no manifest and no record count.
Nothing here is coverage, and nothing here qualifies the desk.

## 1. Outcome

- **Chosen surface: the English `defense` tag page of Viet Nam Government News**
  (`https://en.baochinhphu.vn/defense.html`) and the articles it lists. Source
  `vn_vgp_defense_en`, adapter `scraper/sources/vn_vgp.py`, Tier B: the
  Government's newsroom, not a ministry.
- **It passed for a bounded pilot.** robots.txt permits collection; the tag page
  and 13 article pages returned HTTP 200 under the full collector identity;
  dates, bylines, captions and bodies extract under written rules; a
  repository-client rehearsal stored, re-read and preserved two articles on a
  local bare remote.
- **It is narrow.** It is a tag that editors apply. It lists 24 items reaching
  back to 2023-11-16, with no published pagination and nothing like a daily
  cadence. Two defense-relevant items carried no `defense` tag. The desk
  collects what the tag lists and claims nothing about anything else.
- **Not reached:** the Ministry of National Defence, whose robots.txt returned
  a script page twice, and the People's Army Newspaper, whose homepage and both
  candidate listings redirected to themselves while setting a cookie. Neither is
  labelled `access_blocked`; both are recorded as measured and left alone.
- **Open before activation:** an owner decision on keeping full article captures
  from an "All rights reserved" source on a public state branch (§6); Actions
  egress; multi-day reliability.

## 2. Authorization and bounds

The brief authorized source research, implementation, bounded nonproduction
rehearsals, commits of source, docs and tests, a pushed feature branch and a
draft PR, for this bounded Vietnam work despite the older geographic-expansion
deferral. It did not authorize merging, production collection, production
output regeneration, deployment, or launching a scheduled collector, and it
left the promotion requirements unchanged (DECISION_LOG 2026-10-05).

## 3. Method

One capped probe, 01:43:26–01:49:47 UTC, then two capped rehearsal sessions
(§9). The probe's written cap, recorded before its first request: 60 requests
for the session, 34 for the survey phase and 26 for the deep phase. It used
26: 18 to en.baochinhphu.vn, 2 to chinhphu.vn, 4 to en.qdnd.vn and 2 to
mod.gov.vn; 11 survey and 15 deep.

- Identity: the repository's full collector identity, unchanged:
  `ChinaMilWatch-ShadowCollector/0.1 (+https://chinamilwatch.org; research archive; contact via site)`,
  with `Accept-Encoding: identity` and no other header.
- Transport: `requests` 2.32.5, one worker, a fresh session per request, no
  cookie ever sent, no redirect followed, no retries, 30-second timeouts, a
  3 MB ceiling, raw bytes read with `decode_content=False`, and at least two
  seconds between requests. No host published a `Crawl-delay`.
- robots.txt was read on each host before any other path on it. A host whose
  robots.txt could not be read as a policy received no further requests.
- Only the brief's URLs and links published on fetched pages were requested.
  No numeric article id, feed, API or portal address was guessed.
- Every response kept its exact bytes, requested and final URL, status, content
  type, UTC request and completion times and SHA-256.

The full log, with complete hashes and headers (server cookie values
redacted), is `tests/fixtures/vn_vgp/requests.json`. Bytes are committed as
fixtures for robots.txt, the tag page, the untagged strategy summary, the
ministry's robots response and six articles; the rest are recorded by hash.

## 4. Request log (2026-10-06 UTC)

| # | Time | URL | Status | Type | Bytes | sha256 |
|---|---|---|---|---|---|---|
| 1 | 01:43:26 | `en.baochinhphu.vn/robots.txt` | 200 | text/plain | 25 | `164c4c73142d…` |
| 2 | 01:43:29 | `chinhphu.vn/robots.txt` | 200 | text/plain | 23 | `eaeaa8d3511d…` |
| 3 | 01:43:33 | `mod.gov.vn/robots.txt` | 200 | text/html; charset=utf-8,gbk | 177 | `c906022e23f9…` |
| 4 | 01:43:36 | `en.qdnd.vn/robots.txt` | 200 | text/plain | 904 | `f5058c9f209f…` |
| 5 | 01:44:04 | `en.baochinhphu.vn/` | 200 | text/html | 151,438 | `5ab808eb1f42…` |
| 6 | 01:44:08 | `en.baochinhphu.vn/defense.html` | 200 | text/html | 100,070 | `dce5f0209341…` |
| 7 | 01:44:50 | `en.qdnd.vn/` | 302 → itself | text/html | 0 | `e3b0c44298fc…` |
| 8 | 01:45:00 | `en.qdnd.vn/military/news` | 302 → itself | text/html | 0 | `e3b0c44298fc…` |
| 9 | 01:45:04 | `en.qdnd.vn/military/intl-relations-and-cooperation` | 302 → itself | text/html | 0 | `e3b0c44298fc…` |
| 10 | 01:45:17 | `chinhphu.vn/` | 200 | text/html | 194,258 | `c5a47ce0132e…` |
| 11–22 | 01:46:39–01:48:06 | twelve articles the tag page lists (§5.1) | 200 | text/html | 66,132–68,255 | per article |
| 23 | 01:48:09 | the national security strategy summary (untagged) | 200 | text/html | 87,409 | `abdeaae2d173…` |
| 24 | 01:48:13 | `en.baochinhphu.vn/politics.htm` | 200 | text/html | 98,121 | `7a98dcc5b02e…` |
| 25 | 01:48:17 | `en.baochinhphu.vn/defense.html`, again | 200 | text/html | 100,070 | `dce5f0209341…` |
| 26 | 01:49:47 | `mod.gov.vn/robots.txt`, again | 200 | text/html; charset=utf-8,gbk | 177 | `c906022e23f9…` |

`e3b0c44298fc…` is the hash of an empty body.

## 5. Findings by candidate

### 5.1 Government News, English `defense` tag — PASS for a bounded pilot

**robots.txt** (#1): `User-agent: *` / `Allow: /`, preceded by a UTF-8 byte
order mark that the adapter's parser tolerates. Nothing is disallowed.

**How the tag page is reached.** Its address came from the brief. The English
homepage (#5) does not link it. Every tagged article links it from its own tag
list (`<a href="/defense.html" title="defense">defense</a>`), so it is a link
the site publishes. The page labels itself "Tags: defense", and its own
`#hdCatUrl` value is `defense`.

**Listing.** One stream (`div.timeline > div.box-stream`) of 24 items. The
newest is dated 2026-09-09 and the oldest 2023-11-16: 10 in 2026, 7 in 2025, 6 in
2024 and 1 in 2023. Every item carries the category label "Politics". Each shows
its local time twice: day-first as text (`05/08/2026 20:35`) and month-first in
a title attribute (`8/5/2026 8:35:00 PM`). Neither carries an offset. Five more
article links sit in sidebar widgets and are not part of the stream. No title
repeats. Three dates carry two items each (2026-08-05, 2026-06-30 and
2025-12-25). Ids have 18 digits (22 items) or 17 (2).

**Pagination: none published.** Older items load by script from a
`/timelinetags/…` address that the page never publishes as a link. It was not
requested. The reach is the 24 items.

**Stability.** Reads at 01:44:08 and 01:48:17 were byte-identical. From
03:00:09 the same page arrived 30 bytes longer (`3017fb98934b…`, 100,100
bytes): the earlier bytes plus `<!--u: 10/6/2026 9:59:55 AM-->` after
`</html>`. The end-of-document guard first refused it as possible truncation;
commit `8278c695c` accepts whitespace and complete comments after `</html>`
and still refuses anything else (§9).

**Tag completeness: FAIL.** The tag lists what editors chose to tag, and two
measured counterexamples sit outside it:

- *"Major contents of Viet Nam's National Security Strategy"* (#23; id
  `111260804150254797`), published `2026-08-04T15:02:00+07:00` and modified
  `2026-08-06T16:32:00+07:00`, category "Policies". Its tag list is empty. Its
  title begins with a soft hyphen (U+00AD), kept as published.
- The Politics page (#24) lists *"To Lam meets Acting U.S. Navy Secretary Hung
  Cao in New York"* (id `111260923085014588`, 2026-09-23), which is not on the
  tag page.

The desk therefore collects every item the tag lists and nothing else. It
fills no gap with keywords, topics, other sections or a model, and it claims
nothing about untagged items.

**Cadence.** 24 items over almost three years, and none since 2026-09-09 when
measured. Most days will list nothing new. A daily cadence is not established.

**Articles.** Twelve items the tag page lists, spread across its whole reach and including
both items of two same-day pairs (2026-08-05 and 2025-12-25). All twelve
returned HTTP 200 and extracted cleanly with the adapter's parser:

| # | id | `article:published_time` | modified | byline | words | blocks |
|---|---|---|---|---|---|---|
| 11 | `111260909103625767` | 2026-09-09T09:33+07:00 | 11:19 | Kim Loan | 325 | 8 p, 1 caption |
| 12 | `111260805182734508` | 2026-08-05T20:35+07:00 | 20:39 | Thuy Dung | 371 | 9 p, 1 caption |
| 13 | `111260805144909723` | 2026-08-05T15:09+07:00 | 15:13 | Thuy Dung | 443 | 10 p, 1 caption |
| 17 | `111260630152215966` | 2026-06-30T16:23+07:00 | 16:27 | Thuy Dung | 323 | 8 p, 1 caption |
| 14 | `11126060215325338` | 2026-06-02T15:53+07:00 | 15:57 | Thuy Dung | 321 | 9 p, 1 caption |
| 15 | `111260523144123151` | 2026-05-24T15:38+07:00 | 15:41 | Thuy Dung | 283 | 7 p, 1 caption |
| 16 | `111260521151722925` | 2026-05-21T16:40+07:00 | 16:44 | Thuy Dung | 375 | 9 p, 1 caption |
| 18 | `111251225153329896` | 2025-12-25T15:50+07:00 | 15:55 | Thuy Dung | 188 | 5 p, 1 caption |
| 19 | `111251225101319657` | 2025-12-25T10:31+07:00 | 10:34 | Thuy Dung | 177 | 4 p, 1 caption |
| 20 | `11125070509002706` | 2025-07-05T19:41+07:00 | 19:44 | Thuy Dung | 431 | 10 p, 1 caption |
| 21 | `111241112103823427` | 2024-11-12T11:06+07:00 | 11:09 | Thuy Dung | 336 | 8 p, 1 caption |
| 22 | `111231116101259413` | 2023-11-16T21:17+07:00 | 21:24 | Thuy Dung | 230 | 7 p, 2 captions |

The untagged strategy summary (#23, byline Huong Giang) extracted to 3,155
words in 58 paragraphs, an `h3` and an `h4`.

What the captures show, and the rules that follow from them:

- **Dates.** Every article declares `article:published_time` with `+07:00`,
  shows a visible header such as "September 09, 2026 9:33 AM GMT+7", and
  carries a separate `article:modified_time`. The header and JSON-LD are
  cross-checks; dates in the related-stories box and the CMS comment are never
  read. A stamp without an offset keeps its date and gets no UTC instant.
- **Identity.** `vgp-en:<id>`, the trailing digit run of the path, must agree
  between the listing item's `data-id`, the URL and the article's canonical
  link. The id is never read as a date: #15's id reads like 2026-05-23, but the
  article was published on 2026-05-24.
- **Titles.** Never an identity or a dedupe key. #18's slug
  (`viet-nam-azerbaijan-strengthen-defense-industry-cooperation`) and its
  published title ("Vietnamese, Azerbaijani defense ministers hold talks in Ha
  Noi") differ, and both are kept.
- **Characters.** Text seen beyond ASCII includes `é` (attaché), `’`, `–`, a
  no-break space (#16) and the soft hyphen above. All are kept as published:
  only the ASCII whitespace that HTML collapses is collapsed, and no Unicode
  normalization is applied. Vietnamese names appear unaccented in this English
  text (for example "Phan Van Giang"), so accented names were not observed live.
- **Body.** The single `div.detail-content[data-role=content]`, in page order,
  each block labelled with its element. The related-stories box, CMS comments,
  scripts, images and the tag list are excluded. A body is accepted on
  structure, never on length.
- **Attribution.** The byline is stored as the page's byline, not as an author,
  writer or issuer. Photo credits stay inside captions (for example "Photo:
  VNA"). No translator credit appears in any of the 13 captures.

### 5.2 Ministry of National Defence (`mod.gov.vn/en`) — not reached

Both robots.txt requests (#3 and #26, 6 minutes 14 seconds apart) returned the
same 177-byte HTML page, labelled `text/html; charset=utf-8,gbk`. Its only
content is a script that sets a cookie and reloads the page. That is not a
robots policy, so it gives no permission basis, and no ministry page was
requested. It is recorded as **not reached**, not as `access_blocked`: no
collection path was refused, because none was tried. Reading the ministry needs
an official route, such as a published feed, a readable robots policy or
permission. It would be Tier A, a separate institution and a separate source
identity.

### 5.3 People's Army Newspaper (`en.qdnd.vn`) — not reached

Its robots.txt (#4, 904 bytes) allows `/` and disallows only `/preview/`,
`/services/`, `/api/`, `/search/`, `/tim-kiem/` and administrative paths.
Nothing disallowed covers `/military`. The homepage and both candidate
listings, `/military/news` and `/military/intl-relations-and-cooperation`,
each answered HTTP 302 with a `Location` equal to the requested URL, a
`Set-Cookie: muid_mly=…` and `Cache-Control: private`, and an empty body. The
collector sends no cookies and follows no redirects, and a cookie-and-reload
gate is not passed. Each was measured once and not retried. So the category
boundaries the brief asked about are **unmeasured**. The newspaper would be
Tier B official military media, a separate institution from the ministry.

### 5.4 Government portal (`chinhphu.vn`) — read once

robots.txt (#2) allows everything. The homepage (#10) served its full content.
It carries a `document.cookie` script, which does not gate the page. It links
the Government News estate as "Báo điện tử chính phủ" (→
`https://baochinhphu.vn`) and links the Government's document system,
`vanban.chinhphu.vn`, 22 times. Formal documents there would be a separate
Tier A family. They are not part of this desk and were not requested. The
Vietnamese Government News edition was not evaluated.

## 6. Rights

Government News pages carry the footer "© Copyright Viet Nam Government News -
Department of Government Information and Communications. All rights
reserved." and a `copyright` meta tag "© Viet Nam Government Portal". None of
the captured pages links to terms of use; `/policies.htm` is a news section.
Under `CONTENT_AND_DATA_RIGHTS.md` §3 the articles stay under the originating
institution's terms, and this project acquires and sublicenses nothing.
robots.txt is an access signal, not a licence.

The shadow state stores exact article bytes. On a public state branch in this
public repository, those bytes are publicly readable. The Philippines ruling of
2026-10-02 approved public state for the NSC source only. **The owner must
decide where Vietnam state may live before activation** (§13): public as for
the Philippines, or somewhere not public. Reuse and republication remain
unreviewed whichever is chosen.

## 7. Criteria

| Criterion | Result | Evidence |
|---|---|---|
| robots.txt read first; permits the paths collected | PASS | #1 |
| Tag page reachable under the full identity | PASS | #6, #25; rehearsal (§9) |
| Published pagination | FAIL — none published | script-built `/timelinetags/`, not requested |
| Reach of the listing | 24 items, to 2023-11-16 | #6 |
| Window completeness proven only by an item older than the window | PASS, by construction | adapter rule; tested |
| Tag completeness as a defense category | FAIL | two counterexamples (§5.1) |
| Daily cadence | NOT ESTABLISHED | 24 items in about three years |
| Article retrieval | PASS (12 tagged + 1 untagged) | #11–#23 |
| Text extraction to written rules | PASS on all 13 | §5.1 |
| Dates: declared offset, modified time separate, widgets excluded | PASS | all 13 |
| Bylines and captions | PASS (observed) | 3 bylines; 1–2 captions |
| Varied date formats | PASS (observed) | ISO, header "GMT+7", day-first and month-first listing times |
| Recurring titles | NOT OBSERVED LIVE | none among the 24; derived tests |
| Accented Vietnamese names | NOT OBSERVED LIVE | English text is unaccented; derived NFC/NFD test |
| Short or image-only items | NOT OBSERVED LIVE | shortest 177 words; derived tests |
| Translator credits | NOT OBSERVED | none in 13 captures |
| Repository-client rehearsal with state persistence | PASS (bounded) | §9 |
| Actions egress | UNMEASURED | never dispatched |
| Multi-day reliability | UNMEASURED | one day |
| Reuse or republication permission | NOT REVIEWED | §6 |
| Ministry of National Defence | NOT REACHED | #3, #26 |
| People's Army Newspaper | NOT REACHED | #7–#9 |

"Derived" means the test builds a variant from real fixture bytes in memory;
derived variants are never written back as fixtures.

## 8. What was built

| | |
|---|---|
| Adapter | `scraper/sources/vn_vgp.py` (`VNVgpAdapter`): discover, fetch, extract, healthcheck |
| Manifest | `shadow/vietnam/manifest.json`: outside `desks/`, enabled for the shadow runner only |
| Runner | `scripts/shadow_collect_vietnam.py` |
| Workflow | `.github/workflows/vietnam_shadow.yml`: `workflow_dispatch` only |
| Review kit | `scripts/review_vietnam_shadow_state.py`: Day 7/14/30 packets from a named state commit |
| Desk page and map | `desks/registry.json`, `desks/geography.json`, `_desk_map_geo.svg`, `desk.html`, `desks.html`, `styles.css` |
| Fixtures | `tests/fixtures/vn_vgp/`: byte-exact, hash-pinned |
| Tests | `test_vn_vgp_adapter.py`, `test_vietnam_shadow_runner.py`, `test_vietnam_shadow_review.py`, plus registry/map/page tests |
| Operations | `shadow/vietnam/README.md` |

The adapter is the contract implementation: `desk_id=vietnam`,
`jurisdiction_code=VN`, `default_timezone=Asia/Ho_Chi_Minh`, language `en`,
Tier B. It sends the identity above with two-second spacing measured from the
end of the previous request. A longer published `Crawl-delay` wins, and one over
120 seconds stops collection rather than being shortened. It uses 30-second timeouts and a 2 MB body ceiling, follows no
redirects, makes no retries, clears cookies and refuses compressed replies, so
a capture is always the bytes that crossed the wire. A page that does not
positively look like a Government News page is refused, whether it is a
challenge, a cookie gate or a changed template. Refusals are statuses from
`core/collection/status.py`, never documents. Nothing is screened for relevance
or translated.

The runner keeps `state/shadow.db`, append-only ledgers, write-once
`clock.json` and hash-named exact captures on the orphan branch
`shadow/vietnam`, outside the collector checkout. It imports nothing that
writes production storage, and it derives logical dates through
`core/shadow_schedule.py`. Its default window is seven Ha Noi calendar dates,
with a cap of 40 articles and a ceiling of cap + 2 requests. A window the
listing cannot prove covered, or a listing that repeats, loops, truncates or
runs out of order, fails whole with no references. A proven window holding more
items than the cap fails before any article is fetched, with every candidate
URL kept for recovery. Silence,
duplicates, denials, fetch errors, extraction failures and partial results keep
distinct statuses.

The workflow follows the Philippines pattern: concurrency group
`vietnam-shadow`; read-only defaults with contents-write on the job; state
cloned or bootstrapped in `RUNNER_TEMP`; checks that the state checkout is not
the repository, that the branch holds only `state/`, that the collector checkout
stays clean, that the ledger is append-only and that no WAL or SHM file exists;
a push without force; 90-day attempt artifacts. Its schedule
(`35 17 * * *`, 00:35 in Ha Noi) appears only as a comment until activation.

The review kit builds deterministic packets from a named 40-hex state commit
reachable from `shadow/vietnam`. It refuses unrelated state and leaves the
human sign-off unfilled. It imports only the desk-agnostic Git provenance
helpers from `scripts/review_shadow_state.py`. It does not redirect
Singapore's reviewer or publisher, and there is no Vietnam publisher.

## 9. Rehearsal

Each rehearsal session's cap was written before its first request:
`en.baochinhphu.vn` only, at most cap + 2 = 6 requests per run, 18 for session
1 and 12 for session 2. No retries were made, and a failure stopped the session.
Each run used a fresh state checkout from a **local bare remote**, as the
workflow does, and nothing was pushed to origin.

| Run | UTC | Collector | Target / window | Requests | Result | Database hash after |
|---|---|---|---|---|---|---|
| 880001-1 (A1) | 02:59:51–03:00:01 | `e2313901d` | 2026-08-05 explicit, that date only, cap 4 | 4 | `ok`; 2 new records; day zero 03:00:01 | `d4948dc30077…` |
| 880002-1 (A2) | 03:00:06–03:00:10 | `e2313901d` | the same | 2 | `listing_failure`: possible truncation (cache stamp); nothing stored or pushed; session stopped | — |
| 880004-1 (A2b) | 03:02:43–03:02:52 | `8278c695c` | 2026-08-05 explicit | 4 | `ok_all_duplicates`; 2 unchanged | `871c35981d16…` |
| 880003-1 (C) | 03:02:53–03:02:57 | `8278c695c` | 2026-10-06 (manual UTC date), 2026-09-30 to 2026-10-06 | 2 | `ok_no_publications` | unchanged |

Twelve requests in total, all HTTP 200 and all to
en.baochinhphu.vn: 30 to that host for the day, counting the probe's 18. Both
article captures in A1 and A2b are byte-identical to the probe's #12 and #13.
The first database hash is A1's. The second follows A2b, which added
observations but no versions.

The bare remote's `shadow/vietnam` head is `31195d96220f275cb01d424a99661da5bc8646af`
(`state/` tree `29ed64e9366855c0486f947e49857401b0c50235`). It holds 5
captures, 3 ledgers, `clock.json` and `shadow.db`, with a coherent hash chain.
The A2 attempt left its ledger in the attempt directory only, as the workflow's
artifact path would. A formal day-07 packet built from that commit with
`--as-of 2026-10-06` has package id (`deterministic_sha256`)
`97c1df20e2fee7701252bff6029bfb4cf853eaa62986c11b372fe5b7fc781161`. It reports
`git-verified-tree/1` provenance, a `coherent` state chain, database integrity
`ok`, 2 publications, 2 versions, 4 observations and 5 captures, and says
"DAY-07 HAS NOT ARRIVED" (shadow day 0).

**One spacing lapse.** The harness started run C immediately after A2b. A2b's
last response is stamped 03:02:52 and C's robots.txt request 03:02:53, both in
whole seconds, so the gap between those two requests was under two seconds.
Spacing is enforced within a process: each run kept it, at about three seconds
per request. Two processes started back to back are not spaced. The workflow
cannot repeat this, because each run is a fresh job whose setup steps come
before its first request, and the concurrency group serializes runs. Local
rehearsals must leave a gap between runs (`shadow/vietnam/README.md`).

What the rehearsal shows: bounded repository-client access, body retrieval and
extraction, exact capture persistence, duplicate handling, the fail-closed path
and quiet-run stability on this machine, on this day. It does not show Actions
network access, sustained reliability or archive completeness. The quiet run C
shows listing access only.

## 10. Desk page and map

- **Registry.** `vietnam` sits between Japan and the US reference desk, with
  `route vietnam.html`, `public true`, `status research`, `manifest null` and
  `has_production_records false`. The page shows "None collected", 0 enabled
  sources and no collection statistic. The tag page's listing counts (10, 7, 6
  and 1 by year) appear labelled "Items the defense tag page listed", with the
  caveat that they are not a record count. Japan's volume rows keep their
  "Joint Staff press releases" label through the new `observed_volume_subject`
  field. The research legend now says that a collector may exist without having
  been launched.
- **Map.** Hanoi is the publisher's seat, at 105.8°E, 21.0°N, inside Vietnam's
  own polygon. It marks where the publishing institution sits, not territorial
  coverage. The geometry was rebuilt with
  `python scripts/desk_map.py countries-50m.json` from world-atlas 2.0.2
  (Natural Earth 1:50m, sha256 `04342cdc1e3016bcd7db1630de95684d67b79fe3c8c460321e87aef469502394`).
  The rebuild reproduced every existing path byte for byte and added
  `dm-geo-vietnam`: 1,918 bytes, 8 rings, 102.13–109.45°E. The source draws
  neither the Paracel nor the Spratly Islands for any country, and the map's
  existing note already says it makes no boundary claim.
- **Tablet exception.** From 760 to 1099px, plates normally hang into bands above
  and below the frame. Hanoi sits within a plate's width of Beijing's and
  Singapore's meridians, so its plate hangs left over open map, narrowed by
  `is-mid-side` to `min(14.25rem, 25%)`. Only a side-hung plate at that layout
  is narrowed, and a test pins that set to `{vietnam}`.
- **Collision sweep.** A private render was checked at 375, 600, 760, 820, 880,
  900, 901, 1000, 1099, 1100, 1180, 1280 and 1440px. No plates intersect, no
  plate covers another desk's dot, no leader crosses another plate, nothing
  leaves the viewport and the page never scrolls sideways. The closest
  approaches are Vietnam's plate to Singapore's dot (15.4px at 760, 22.7px at
  1100) and to Singapore's plate (27.8px at 1100). Below 760 the plates become
  the list.
- **Page weight.** `desks.html` grows from 93,279 to 98,442 bytes, inside the
  120 KB page budget.
- **Agreement.** The private render changed `vietnam.html` (new) and `desks`,
  `index`, `coverage`, `methodology`, `archive`, `analysis`, `sources` and
  `sitemap`. It now reads "2 collecting desks of 5 declared". The china, japan,
  singapore and us-indopacific pages are unchanged.

## 11. Production untouched

The render went to a private directory. No command wrote `output/`, the
sidecars or a database.

- Worktree `pla_watch.db`: `4e130411e7b6…` before and after.
- Main checkout's `pla_watch.db`: `24e17b90c1a3…` before and after.
- Worktree `output/`: all 7,409 files byte-identical before the merge of main.
  The merge brought `origin/main`'s own regeneration (7,410 files). All 7,410
  were byte-identical again after every later check, and the branch's
  `output/` and database equal `origin/main`'s.
- A final private render on the merged head was byte-identical to the render
  checked in §10 and left the database hash unchanged.
- The Vietnam runner and review kit import no production storage, and the
  manifest is invisible to `load_all_desks()`. Tests assert both, plus an empty
  production query for `desk_id='vietnam'` or `vn*` sources.

## 12. Tests and checks

Run on 2026-10-06 UTC on the branch with `origin/main` (`a259ee6d2`) merged.

| Check | Result |
|---|---|
| Vietnam suites: `test_vn_vgp_adapter`, `test_vietnam_shadow_runner`, `test_vietnam_shadow_review` | 58 + 36 + 42 = 136 tests, OK |
| Map and registry: `test_desk_map`, `test_desk_rollout_contract`, `test_site_mode_contract` | 7 + 46 + 29 = 82 tests, OK |
| Those six plus nine modules that read the edited documents or share their contracts (`test_us_source_scope`, `test_license_and_rights_scope`, `test_readme_operational_claims`, `test_ph_nsc_adapter`, `test_pdf_text`, `test_cover_origin_rebasing`, `test_shadow_logical_target_date`, `test_singapore_scheduled_production`, `test_shadow_review_publisher`), after the final document edits | 575 tests, OK |
| `test_preview_prototype`, after the final document edits | 485 tests, OK, 1 skipped |
| Full offline suite, the PR check's own command (`unittest discover -s tests -t .`), 14:04–14:22Z | 3,335 tests, OK, 2 skipped |
| `scripts/validate_output.py` | passed with 10 warnings, identical to the governed baseline |
| Production preservation | §11 |

The full suite started before the last edits to the governing documents, this
report and the README; no code changed after it started. Every module that
reads those documents was run again afterwards: the 575-test run and
`test_preview_prototype` above.

## 13. Commands

Offline tests (real sockets refused):

```bash
.venv/bin/python -m unittest tests.test_vn_vgp_adapter tests.test_vietnam_shadow_runner tests.test_vietnam_shadow_review tests.test_desk_map tests.test_desk_rollout_contract -v
```

The local rehearsal, persistence check, post-merge dispatch, activation and
review commands are in `shadow/vietnam/README.md`. In short:

```bash
gh workflow run vietnam_shadow.yml --repo VSSpowerlifting/China-Mil-Watch --ref main -f target_date=YYYY-MM-DD
```

```bash
.venv/bin/python scripts/review_vietnam_shadow_state.py --state-repo <clone> --state-commit <40-hex> --checkpoint day-07 --as-of YYYY-MM-DD --out <directory outside the repository>
```

Activation needs owner approval first (§6). Then it takes a PR that adds the
commented schedule, and the registry moves to `shadow` only once collection is
actually running.

## 14. Remaining limits and next actions

**October 7 continuation:** the requested ministry pass is implemented and
bounded local live rehearsals passed for Public Security foreign affairs and
MOIT energy/foundational industry. Defence and Finance remain unreached. The
original Government News pilot and historical evidence below are retained;
current scope, new request hashes, source-specific clocks, transport fix and
activation limits are in `VIETNAM_MINISTRY_EXPANSION_2026-10-07.md`.

- One tag on one newsroom's English edition. It is not comprehensive Vietnamese
  defense publication and not a ministry voice.
- The reach is 24 items. An item tagged after its window was read is reported
  as a late listing by the review, not silently absorbed. No archive
  completeness is claimed.
- Actions egress, multi-day reliability, reuse permission, and the ministry and
  newspaper routes remain open.
- Promotion requirements are unchanged: 30 consecutive collecting days, Day 7,
  14 and 30 human reviews, the applicable desk-strength criteria and a recorded
  owner sign-off.

**Next action (owner):** review the draft PR. Then decide whether Vietnam state
may be public (§6), and whether to merge, which publishes `vietnam.html` and
the map entry at `research` with the next site render.
