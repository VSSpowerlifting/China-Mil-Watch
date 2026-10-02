# Philippines — National Security Council, Official Statements

**Isolated shadow collector prepared for review. Bounded live adapter rehearsal passed
2026-10-02; scheduled collection has not been activated by this change.**

| | |
|---|---|
| Adapter | `scraper/sources/ph_nsc.py` (`PHNscAdapter`) |
| Manifest | `shadow/ph_nsc/manifest.json` (`enabled: true` for shadow only, deliberately not under `desks/`) |
| Runner / workflow | `scripts/shadow_collect_ph_nsc.py` / `ph_nsc_shadow.yml` |
| Proposed state branch / schedule | `shadow/ph-nsc` / daily 10:10 UTC, plus manual dispatch; job hard-disabled |
| Tests | `tests/test_ph_nsc_adapter.py` (offline; a socket guard fails any real connection) |
| Fixtures | `tests/fixtures/ph_nsc/` (byte-exact copies, hash-pinned by the tests) |
| Review receipt | `docs/PH_NSC_ADAPTER_REVIEW_RECEIPT_2026-10-01.md` |

`desks/registry.json` declares no Philippines desk and
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

Those captures alone did **not** establish repository-client compatibility, reliable periodic
access, or permission to reuse the text. Repository-client compatibility was subsequently measured
successfully in the authorized 2026-10-02 live rehearsal. Periodic reliability and reuse
permission remain open.

## Live rehearsal — 2026-10-02

An authorized read-only rehearsal used the adapter's own `requests` transport from the owner's
Mac under `ChinaMilWatch-ShadowCollector/0.1`. It made no database, output, workflow, manifest or
production-state writes.

- `robots.txt`: HTTP 200, `text/plain`, 65 bytes.
- Official Statements category: HTTP 200, UTF-8 HTML, 149374 bytes.
- Discovery for 2026-06-16 through 2026-07-08: `ok`; six listed items and exactly two references.
- Post `3108` (2026-07-08): fetch `ok`, extraction `ok`, 1272 body characters.
- Post `2269` (2026-06-17): fetch `ok`, extraction `ok`, 1808 body characters.
- The sitemap returned HTTP 200 but advertised only `https://nsc.gov.ph/`.
- The author archive exposed 10 posts / 4 Official Statements on page 1 and 7 posts / 2 Official
  Statements on page 2. Those were the same six statements on the category page; page 3 was 404.
- The previously observed gambling-content anomaly did not reproduce during these bounded probes.

The raw page hashes changed from the October 1 captures while identities, dates, titles and
extracted body lengths remained stable, consistent with non-content page-shell drift.

## Open gates

1. **Repository-client compatibility: measured successfully for the owner's Mac environment.**
   GitHub Actions egress and other network environments remain unmeasured.
2. **Reliable periodic access: unmeasured.** One successful bounded session is not evidence of
   multi-day reliability, scheduled-run stability or rate-limit behaviour.
3. **Reuse permission: not reviewed.** robots.txt is an access signal, not a licence for the text.
4. **Discovery completeness: prospectively bounded; pre-2026-06-03 history remains unestablished.**
   The category exposes six statements from 2026-06-03 through 2026-07-08 and no pagination.
   The sitemap exposes only the homepage. The two-page author archive exposes the same six
   Official Statements and page 3 is 404. Windows reaching to 2026-06-03 or earlier continue
   to fail closed rather than claim historical completeness.
5. **Category anomaly: unresolved but not reproduced on 2026-10-02.** The earlier gambling-content
   observation is neither dismissed nor treated as proof of compromise.
6. **Collector identity: undecided for scheduled use.** The successful rehearsal used
   `ChinaMilWatch-ShadowCollector/0.1`. The runner retains that exact adapter identity,
   including its existing project URL and scope suffix. Recommendation: approve it unchanged
   for this evaluation; an explicit owner decision is still needed before activation.
   The exact unresolved decision is approval of
   `ChinaMilWatch-ShadowCollector/0.1 (+https://chinamilwatch.org; research archive; contact via site)`
   for periodic NSC collection under the repository's broader identity convention.
   No new contact details are proposed and no owner ruling is recorded here.
7. **Live remeasurement with the repository client: completed successfully on 2026-10-02.**
   This closes the original Mac-environment live-measurement gate, not the periodic-reliability
   or GitHub Actions egress gates.

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
- Only the dedicated shadow runner/workflow reads this manifest. State is outside the collector
  checkout, never in the production database or rendered output. Offline tests refuse real sockets.
- The fixtures are copies of the packet's bytes. `tests/fixtures/ph_nsc/.gitattributes` marks them
  `binary` because the HTML contains carriage returns that Git would otherwise normalise on some
  configurations; the tests pin each file's sha256 to the packet's own ledger. Do not re-encode,
  re-wrap or reformat them. Variants for failure cases are built in the tests from the real bytes
  and are named `derived_*`; they are never written back.

## Running the tests

```bash
.venv/bin/python -m unittest tests.test_ph_nsc_adapter tests.test_ph_nsc_shadow_runner -v
```

## Shadow operation and recovery

The runner uses the existing collection contract and `core/shadow_schedule.py`.
Its normal window is seven source publication dates (`lookback_days=6`). It
does not backfill the category's history. Coverage must be proven by an item
older than the requested start; a window reaching 2026-06-03 or earlier still
fails closed on the observed category. More than 40 candidates also fails
before fetching, with every candidate URL recorded, rather than sampling.

Successful runs store `state/shadow.db`, append-only `state/ledger/*.json`, a
write-once `state/clock.json`, and hash-addressed exact statement responses in
`state/captures/`. Records preserve `nsc:<id>`, canonical URL, publisher-local
and UTC publication times, hosting byline (not issuer), text and capture hashes,
retrieval time and HTTP provenance. Every run records target-date provenance,
collector commit and identity, adapter robots/listing/window evidence, counts
and failures. Repeated identities are deduplicated without overwriting the
first stored text; re-capture hashes and bytes remain evidence of any change.

The workflow clones or bootstraps only `shadow/ph-nsc` outside the checkout,
pushes without force, and fails on divergence. Network/authentication errors
are not treated as an absent branch. Failed collection pushes nothing; the
complete attempt state and console log are retained as Actions artifacts for
90 days, including failed ledgers and successful captures from a partial run.
The collector checkout must stay clean; existing ledgers and clock cannot
change. There is no analysis, rendering, Pages or promotion step.

Recovery is **Run workflow → target_date = the intended logical UTC date**.
An empty manual input uses the actual UTC date. A scheduled first attempt uses
the most recent 10:10 UTC slot. A UI re-run without an explicit date is refused.
Recovery writes a new ledger, never edits the failed attempt's evidence.

**Privacy limitation:** `VSSpowerlifting/China-Mil-Watch` is public (checked
2026-10-02), so `shadow/ph-nsc` here is publicly readable Git state. This
architecture is isolated from the public site, not confidential storage. If
the owner requires genuinely private evidence, activation must instead wait
for a private state remote and its credentials; none has been invented here.
No state branch, scheduled run, day zero or reliability interval is claimed
by these source changes. Identity and privacy decisions precede activation;
Actions egress, multi-day reliability and reuse review remain open afterwards.

**Hard activation guard:** `jobs.shadow.if: ${{ false }}` disables both scheduled
and manual collection, including after merge. Workflow defaults are read-only;
the disabled job alone declares the contents-write permission needed for future
state persistence. Removing the guard requires a separately reviewed owner
decision on identity and storage. The configured same-repository remote would
write a publicly readable branch and must be replaced before any confidential
collection. Neither state branches nor Actions artifacts are claimed to provide
confidentiality. No private remote or credentials have been created.
