# Philippines — AFP shadow pilot

**Status: shadow evaluation of one source. Not scheduled, not enabled, not in
any production desk, not on any public page.** Nothing here collects unless
someone runs `scripts/shadow_collect_ph.py` by hand, and nothing it writes can
reach `pla_watch.db` or `output/`.

This is a pilot of one ingestion route. It is not a Philippines desk, it does
not declare one (`desks/registry.json` is untouched), and it makes no claim of
coverage beyond the measured figures below.

## What the source is

The article stream of **www.afp.mil.ph**, the official website of the Armed
Forces of the Philippines, published by its Public Affairs Office (byline
`pao afp`). Tier A: the institution speaking for itself.

It is **not** the Department of National Defense, the Philippine Coast Guard,
the National Security Council or the Philippine News Agency, and it is not
comprehensive Philippine defense coverage. It is what the AFP chose to publish
on its own site.

## How it is retrieved

`www.afp.mil.ph` is a single-page application. Its HTML is an empty shell and
its `sitemap.xml` returns that shell. Article text is served as JSON by the
site's own backend, `api.afp.mil.ph`, which every visitor's browser calls.

| Stage | Request | Notes |
|---|---|---|
| Discovery | `GET api.afp.mil.ph/articles/?page_size=100`, then the `next` links | Whole listing walked every run (~11 requests); window applied afterwards |
| Retrieval | `GET api.afp.mil.ph/articles/<slug>/` | One request per article, 2 s apart, single worker |
| Preserved original | the detail response's exact bytes, SHA-256, requested and final URL, HTTP status, retrieval time | `captures` table |
| Canonical URL | `https://www.afp.mil.ph/news/<slug>` | The SPA's own route (`news/:slug`), **reconstructed from the slug, not fetched** |

Identity is the API's integer id, `afp:<id>`, cross-checked against the slug
(the detail endpoint is keyed by slug and `/articles/<id>/` returns 404).
Dates are the publisher's own `published_at`, kept in the offset it states
(`+08:00` on all 1,076 listed items) with the UTC instant stored beside it.

## Robots position

Recorded on every run, from both hosts. This is a judgement, so it is written
out.

| Host | What was observed 2026-09-26 | How the adapter treats it |
|---|---|---|
| `www.afp.mil.ph/robots.txt` | 200, `User-agent: *` / `Allow: /` | Rules apply; permits collection |
| `api.afp.mil.ph/robots.txt` | 404 (no rules file) | No rules published. Under RFC 9309 an unavailable file is not a refusal |
| `api.afp.mil.ph` responses | `X-Robots-Tag: noindex, nofollow` | Recorded in every ledger; **not** treated as a crawl refusal |

The contrast with `pacom.mil` is deliberate. `pacom.mil` answers **403 for its
own robots.txt**, which is treated as no permission (`scraper/sources/us_dvids.py`).
Here the rules file is simply absent on the API host, and the institution's
own host states `Allow: /`. A 401/403 on either host is a hard failure, an
edge challenge is `access_challenged` and is never retried or solved, and a
disallow stops the run before any listing request.

**Open point for the owner.** `X-Robots-Tag: noindex, nofollow` is a search-
indexing directive, not an access rule, but it is a signal that the API was
built for the site's own front end rather than as a crawl surface. The
collector identifies itself honestly (`ChinaMilWatch-ShadowCollector/0.1`), so
the AFP can refuse it. The pilot ran as a full pass and a short retry, at 2-second spacing or slower. Before
any scheduled collection or promotion, the sound course is to ask the AFP
Public Affairs Office for an official route, exactly as recommended for Japan.
That request is not written here and this pilot does not presume its answer.

## Why this source, and what was ruled out

Chosen from the four named candidates plus the Philippine ministries, by
measured accessibility on 2026-09-26 from this project's egress, each probed
with the project's declared user agent and nothing else:

| Candidate | Observed | Disposition |
|---|---|---|
| Japan MOD (`mod.go.jp`) | Already a shadow desk (`shadow/jp_mod/`); on 2026-08-26, 134 of 142 news items had no body (`desks/registry.json`) | Not a new source; blocked on an official route, not on adapter work |
| Japan MOFA (`mofa.go.jp`) | `robots.txt` → 403 Access Denied at the edge | Blocked; not probed further |
| South Korea MND (`mnd.go.kr`), JCS (`jcs.mil.kr`) | `robots.txt`: `Disallow: /` with a few `Allow` lines for index pages | **Ruled out on policy**; should be re-examined only if that file changes or the ministry grants permission |
| Australia Defence, Navy, Army, DFAT (`*.gov.au`) | HTTP/2 `INTERNAL_ERROR` on every request to `www.defence.gov.au`, `news.defence.gov.au`, `www.minister.defence.gov.au`, `www.navy.gov.au`, `www.army.gov.au` and `www.dfat.gov.au`; `www.defence.gov.au` also timed out on HTTP/1.1 (the only host tried that way) | **Unmeasured, not refused.** Same result as `docs/DESK_RELIABILITY_REVIEW_2026-09-16.md`; needs a probe from the collection runner's egress. Not scored |
| Philippines DND (`dnd.gov.ph`), Coast Guard (`coastguard.gov.ph`), PCO, DFA | Cloudflare challenge on `robots.txt` itself (403) | **Blocked.** Never bypassed |
| Philippine News Agency (`pna.gov.ph`) | `robots.txt` allows all | Open, but a state news agency, not a defense institution; left for a later, separate decision |
| National Security Council (`nsc.gov.ph`) | `robots.txt` allows all (`Disallow:` empty) | Open; **not assessed further** (no listing, feed or article was requested). A candidate for a follow-up pilot |
| **AFP (`afp.mil.ph`)** | `robots.txt` allows all; JSON API answers without a challenge | **Chosen** |

The Philippines is a principal party to the South China Sea disputes and the
project holds no Philippine record. Of the candidates whose access could be
established, AFP was the one defense institution assessed end to end: its
listing, article retrieval, identity, dates and robots position were all
measured. That is a statement about what was examined, not a ranking of every
Philippine source: the National Security Council in particular was not assessed.

## Measured 2026-09-26

One full-history capture, run by hand from a checkout of this branch. The
state directory was in a session scratch area outside the repository, is **on
no state branch and is not retained**; nothing captured is committed. The
figures below are the durable record of it, and whether to keep or recreate the
state is the owner's decision. Requests were identified and single-worker, with
2 seconds between requests and a backoff no shorter than that on a transport
retry; roughly 1,100 in total.

| Measure | Value |
|---|---|
| Items the API reports (`count`) | 1,076 |
| Items actually listed, over 11 pages | 1,076 |
| Rejected as non-press categories | 2 (`afp-logos` 1, `transparency-seal-and-foi` 1) |
| **Records captured** | **1,074** |
| **Publication dates captured** | **2021-01-21 to 2026-09-15** (609 distinct dates) |
| Preserved original payloads | 1,074 (2.75 MiB), each with SHA-256, requested and final URL |
| Records with text | 1,049 |
| Metadata-only records (text not in the payload) | 25 (24 are an image alone) |
| Revisions observed | 0 |

The API's total is reported beside the captured count and is not a coverage
claim: it counts what the AFP's site chose to list, not what the AFP published.

| Year | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Records | 1 | 317 | 364 | 310 | **0** | 82 (from 2026-06-12) |

Recent monthly rate: June 8 (from the 12th), July 32, August 25, September 17
(to the 15th).

How the run went, including what did not work first time:

1. **First pass: 1,066 of 1,074 captured, 8 fetch failures** (ids 928, 935,
   936, 937, 938, 1003, 1004, 1005 — two tight clusters). This ran during a
   period when connects to `api.afp.mil.ph` took about 11 seconds. The cause of
   the 8 failures was **not recorded**: the ledger of that pass named only a
   count. That was a reporting gap in the runner, since fixed (`failure_log`).
   The timing is consistent with transient slowness and is not proven to be it.
2. **Second pass, 8 of 8 recovered.** The runner now skips held articles older
   than the revision-watch window (`--revision-days`, default 14), so the retry
   requested only the 8 missing items plus the 9 held items inside the window.
   Those 9 were re-read live and were unchanged: dedup and revision detection
   ran against real data and reported no revision.
3. **Late code changes were checked against the preserved data, and the
   scratch state was patched to match. Read this as a disclosure.** Three
   changes were made after the first pass began (slug added to the revision
   fingerprint, a paragraph-overlap rule in text assembly, the failure log).
   All 1,074 preserved payloads were replayed through the final extractor.
   Titles, dates, UTC instants, identities and text status were identical in
   every case. Text changed in exactly 5 records, each by the removal of one
   repeated paragraph (the intro carried a dateline the body omitted, so the
   opening paragraph had been stored twice; 5 of the 814 items composed from
   both fields), and every change is a pure paragraph removal.
   **The reported state is therefore not the untouched output of one run.** The
   fingerprints of all 1,074 records, and the text and content hash of those 5,
   were rewritten directly in the scratch SQLite database, offline, from the
   preserved payloads, to the final definitions. Without the fingerprint
   migration, the 9 held items re-read in the second pass would have been
   reported as revisions. The runner itself never overwrites a record. **A clean
   run of the final code from an empty state has not been done**, and the
   archive was deliberately not fetched a third time to do it.

Observations kept as observations:

* **40 groups (81 records) of distinct ids carry identical text** (groups of 2
  and 3). Nine of the groups share a publication date; the rest differ by days
  to weeks. They are reported on the ledger and **not merged**.
* **Nine title-and-date pairs on distinct ids** exist in the API, one of them a
  statement published twice as an image alone (ids 1330 and 1331).
* **All 992 items dated before 2024-11 carry `created_at` 2026-07-14**, the date
  of the site's migration, so their publication dates are the publisher's
  statement and not an independently verified original.
* Text composition across the 1,074 records: 814 combine an intro and a body
  (811 migrated items, of which 809 have complementary halves and 2 overlapped
  and were trimmed, plus 3 current-CMS items that all overlapped and were
  trimmed), 129 use the body alone, 106 the intro alone, and 25 have no text.

## Limits, stated plainly

* **Low and uneven volume.** 1,074 items over five years, and about 25 to 32 a
  month recently. This is a small, slow source, and no year-round record: 2021
  has one item and 2025 has none.
* **A 589-day hole with no items.** No item is dated between 2024-10-31 and
  2026-06-12, and there is a 345-day hole before 2022. The listing cannot say
  whether the AFP published nothing or the site rebuild lost it. It is recorded
  as a gap and is never backfilled or inferred.
* **308 of the ids from 1 to 1384 never appear in the listing.** They may be
  drafts, deletions or other content types. The adapter does not enumerate ids.
* **Some statements are an image only.** Text is not in the payload, so those
  records hold title, date and URL with empty text. Nothing is transcribed.
* **Site furniture sits among the articles.** `uncategorised` includes pages
  such as "Transparency Seal Page" and "TALK TO TROOPS". They are collected and
  flagged by category, and screened downstream, not at collection.
* **Duplicate-looking records are real.** Nine title-and-date pairs on distinct
  ids exist in the API. They are reported, not merged.
* **Dates are as stated.** All 992 items dated before 2024-11 were migrated on
  2026-07-14; their publication dates are the publisher's, not independently
  verified originals.
* **Language is declared, not detected.** `en` is the site's stated language.
* **Revisions are detected only for items re-read.** A held item is re-read
  only while it is within `--revision-days` (default 14) of the target date,
  so a correction made to an older article is not seen.
* **Cross-source and cross-id duplicates are not resolved.** Which of several
  identical records is canonical is an editorial decision.

## Running it

```bash
.venv/bin/python scripts/shadow_collect_ph.py \
  --state-dir /path/outside/the/repo --target-date YYYY-MM-DD \
  --lookback-days 4000 --cap 0        # one-time full history
```

The exit code is 0 for health `ok` and `partial` and 1 for `fail`, which is
deliberately more lenient than the DVIDS runner (any non-`ok` exits 1): a
partial run kept records and lost others. A zero exit is therefore **not**
evidence the run was clean. Read the ledger (`health`, `fetch_failures`,
`failure_log`). The first pass of the pilot exited 0 with 8 fetch failures.

A re-run with the same state directory requests only what is missing plus the
articles inside `--revision-days`; it does not fetch the archive again.

The state directory must be outside the repository; the runner refuses
otherwise. There is no workflow, on purpose: scheduling it would start
collection on merge and would need a state branch that does not exist.
