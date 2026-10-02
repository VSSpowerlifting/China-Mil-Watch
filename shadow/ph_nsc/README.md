# Philippines — National Security Council, Official Statements

**Shadow adapter. Disabled. Built offline from captures. Never run against the live site.**

| | |
|---|---|
| Adapter | `scraper/sources/ph_nsc.py` (`PHNscAdapter`) |
| Manifest | `shadow/ph_nsc/manifest.json` (`enabled: false`, deliberately not under `desks/`) |
| Tests | `tests/test_ph_nsc_adapter.py` (offline; a socket guard fails any real connection) |
| Fixtures | `tests/fixtures/ph_nsc/` (byte-exact copies, hash-pinned by the tests) |
| Review receipt | `docs/PH_NSC_ADAPTER_REVIEW_RECEIPT_2026-10-01.md` |

There is no runner, workflow or schedule. `desks/registry.json` declares no Philippines desk and
`load_all_desks()` still returns only `china` and `singapore`. Nothing here qualifies this source:
no shadow collecting day has accrued, and none may be described as qualified (DECISION_LOG).

## What the captures establish, and what they do not

The evaluation packet `IPR-Philippines-Alternate-Source-Evaluation-2026-10-01.zip`
(sha256 `880e330b594709fe722d952abb2a6b7ce150b83dcd7cf5fbe8dbc4b06e237b54`, 420181 bytes)
holds ten captures. Four are NSC; the WPS Transparency and FSI captures in the
same packet are out of scope here and were not copied.

| Capture | Requested (UTC, 2026-10-01) | Status | Bytes | sha256 |
|---|---|---|---|---|
| `nsc-robots.bin` | 19:28:24 | 200 `text/plain` | 65 | `fe7fd4e93e9c7b899f2880248dd2092a3b7bb4b0113502ab2a3f10762dbc3f7b` |
| `nsc-listing.bin` | 19:28:33 | 200 `text/html; charset=UTF-8` | 149374 | `9e0a4208504317bcfbd8121ea76d728e87da607122c83b96f575e9cb4d0203a6` |
| `nsc-article-1.bin` (post 3108) | 19:28:41 | 200 `text/html; charset=UTF-8` | 143946 | `0fc3cfcfeb29a69720efd12438a3a17da8e733b5fc3c2d184f7b2017888c52a0` |
| `nsc-article-2.bin` (post 2269) | 19:28:50 | 200 `text/html; charset=UTF-8` | 144278 | `5601fa63d9ab920c4fd1846fefc0de006a79973b301483d218bebafe988ab8ad` |

They establish **bounded accessibility through a generic client**: a standalone urllib probe, one
worker, at least two seconds between requests, no redirects followed, no retries, default
environment proxy handling, identity `ChinaMilWatch-ShadowCollector/0.1 (…)`. All four returned
HTTP 200 with the expected structure.

They do **not** establish repository-client compatibility, reliable periodic access, or permission
to reuse the text. Those are the gates below. Nothing in this branch narrows them.

## Open gates

None of these is closed by this change. Each needs a decision or a measurement that this task did
not authorize (no live request, no schedule, no activation).

1. **Repository-client compatibility: unmeasured.** The adapter's `requests` transport has never
   made a request to nsc.gov.ph; the captures used urllib. The adapter narrows the difference
   (same User-Agent, `Accept-Encoding: identity` as urllib sent, no redirects, no cookie ever
   replayed) but `requests` still adds its own `Accept` and `Connection` defaults, and TLS,
   header order and connection reuse are unmeasured. The site sets a tracking cookie
   (`slimstat_tracking_code`) on listing and statement responses; the adapter clears its cookie
   jar after every response, so it is neither stored nor sent back.
2. **Reliable periodic access: unmeasured.** One session, four requests over twenty-six seconds,
   from one environment, through whatever proxy that environment applied (its identity is
   unmeasured). No repeat run, no CI-runner egress, no observation of rate limits or blocking.
3. **Reuse permission: not reviewed.** robots.txt is an access signal, not a licence for the text.
   No terms-of-use or copyright review has been done for storing or republishing statement text.
4. **Discovery completeness: unobserved.** The captured listing shows six items, date-descending,
   and **no pagination markup of any kind**. Whether older statements exist, and how a client
   reaches them, is not known. The adapter follows only links the listing itself publishes and
   never guesses a page URL. Consequence: with the captured listing (oldest item 2026-06-03),
   any window that reaches back to that date or earlier fails with `LISTING_FAILURE` and no
   references, because coverage cannot be proven. robots.txt declares a sitemap
   (`https://nsc.gov.ph/sitemap.xml`); it was not captured, is not used, and whether it
   enumerates the category with dates is unmeasured.
5. **Category anomaly: unresolved.** The packet records that one web-tool retrieval of the
   category URL returned gambling content, while a later retrieval and the urllib capture
   returned the expected page. This is not a finding that the site is compromised, and the
   observation is not discarded. The adapter's defence is positive: a page is accepted only with
   the expected title, body classes and each required element exactly once, and a known marker
   list is a tripwire only (it was named about a page that was never captured). Whether the
   anomaly reproduces for the repository client or under this identity can only be learned live.
6. **Collector identity: undecided.** The captures and this adapter present
   `ChinaMilWatch-ShadowCollector/0.1`. The October 1 AFP inquiry stated `ChinaMilWatch/1.0`, which
   is also the identity pinned by `tests/test_user_agent_identity.py`. Which one a live rehearsal
   uses is an owner decision. Changing it here is one line (`USER_AGENT` in the adapter), and
   the fixture test, which ties it to the ledger, will fail until that decision is recorded.
7. **Live remeasurement with the repository client: not performed.** The packet's engineering
   next action asks for it; the task brief forbade live requests, so it stays open. A first
   rehearsal should be one bounded run: robots, the listing, two statements, under the
   identity chosen in gate 6, with the window stated in advance.

Smaller items, none a blocker for review:

- `Crawl-delay` is not parsed; a fixed two-second spacing applies. Robots paths are compared as
  written, with no percent-decoding; general encoded-path conformance remains unverified.
- This adapter carries its own robots matcher (agent groups combined, longest match, Allow wins
  ties, `*` and `$`). PR #79 carries another. They should be unified after PR #79 lands; no
  shared helper was created here so that PR is not touched.
- The pages expose a publication time only. A statement edited after publication is not
  detectable except by a changed capture hash on re-capture.
- `production_lookback_days` keeps the base default of zero. A rehearsal window must be explicit.
- The category is quiet: the newest listed statement is dated 2026-07-08, almost three months
  before the capture. An empty window is the normal result and is reported as
  `OK_NO_PUBLICATIONS`, not as a fault.

## What is collected

The October 1 offline continuation adds public-contract regressions for legitimate challenge-like
titles and quoted statement text, malformed links and timestamps, spacing after slow or failed
body reads, and publisher-versus-issuer attribution. Required-page traversal now checks URL
overlap as well as post-ID overlap. Explicit challenge forms and active challenge configuration
scripts stop retrieval even when NSC theme classes remain. These tests do not establish live
access, site freshness or source-wide completeness.

The Official Statements category (`https://nsc.gov.ph/category/official-statements/`) and the
statement pages it links, at `https://nsc.gov.ph/YYYY/MM/DD/slug/`. Nothing else on the site is
requested. `evas.nsc.gov.ph` is a different host, appears in the listing's links, and is refused.
No relevance filter is applied.

| Field | Source on the page |
|---|---|
| identity | WordPress post id, stored as `nsc:<id>`; the listing item's `post-<id>` class, the article's `postid-<id>` body class, the shortlink and the canonical link must agree |
| canonical URL | the permalink; the page's canonical link must equal the URL requested |
| title | `h1.wp-block-post-title`, inside `<main>` only |
| publication date | `div.wp-block-post-date time[datetime]`, in the page's own offset; the UTC instant is stored beside it; a timestamp with no offset is refused |
| site byline | `div.wp-block-post-author-name a`, stored as `site_byline` |
| body | `div.entry-content` only; the "Latest Post" widget that follows it is excluded |

**Hosting is not issuing.** The category hosts statements by several offices (titles in the
capture name the National Security Adviser and the National Task Force for the West Philippine
Sea) under one byline, "National Security Council". The byline names the publisher that hosts the
page. No issuing office is derived from a title or a body, and the body's own dateline is part of
the text, not metadata.

**Recurring titles.** Three of the six captured items share one title and differ only by a `-2`
or `-3` slug suffix. Identity is the post id; titles and slugs are never an identity or a dedupe
key.

**The sidebar trap.** Each statement page is followed by a "Latest Post" list. In both captures it
holds four further `<time>` elements, the first dated weeks after the statement, and in the first
capture the list includes the statement itself. There is no fallback anywhere: a missing header
date, title or body is a refusal, never the first date or heading found elsewhere on the page.

The extracted text is a block-aware rendering of the entry-content (a block element or `<br>`
ends a line; inline markup does not). It reproduces the packet's body character counts and
boundaries for both samples. The preserved original is the response itself: the capture carries
its requested and final URL, status, retrieval time and SHA-256.

## Retrieval, in the order it happens

1. `robots.txt` is read once per `discover()`. A 404 means no restriction. A 401 or 403 means the
   host will not tell this client its rules, which is no permission basis, so nothing is
   collected. A 200 that is not a plain-text rules file (an HTML page, a challenge) is never read
   as allow-all.
2. Every request is checked against those rules before it is made. A disallowed URL is not
   requested, and the refusal is a status, not an exception.
3. The listing is read. Only links it publishes are followed. Collection stops as soon as the
   oldest item listed is older than the window start, which is the only way completeness is
   claimed. If the published pages run out first, or the listing repeats an item, loops, skips a
   page, links off-host, is not newest-first, or exceeds the page cap, the run fails whole with
   zero references. A partial listing is never returned.
4. Each statement is fetched with one request. No redirect is followed. There are no retries
   within a run.
5. Every page is screened before it can become anything: an access challenge (recognised on any
   status, including HTTP 200), a non-UTF-8 or non-HTML body, an oversized body, a truncated
   document, a page without the NSC fingerprint, or a known spam marker is refused with a status
   that names the reason, and no document is produced.

## Isolation

- The manifest is under `shadow/`, so `load_all_desks()` cannot find it, and no code in
  `pipeline.py`, `core/` or `desks/` imports the adapter.
- No database, `output/` path or workflow is touched. The tests assert no socket is opened.
- The fixtures are copies of the packet's bytes. `tests/fixtures/ph_nsc/.gitattributes` marks them
  `binary` because the HTML contains carriage returns that Git would otherwise normalise on some
  configurations; the tests pin each file's sha256 to the packet's own ledger. Do not re-encode,
  re-wrap or reformat them. Variants for failure cases are built in the tests from the real bytes
  and are named `derived_*`; they are never written back.

## Running the tests

```bash
.venv/bin/python -m unittest tests.test_ph_nsc_adapter -v
```
