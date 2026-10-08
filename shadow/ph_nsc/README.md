# Philippines — National Security Council, Official Statements

**Public, nonproduction shadow settings approved by Ben on 2026-10-02.**
Activation merged in PR #96. The first bounded manual run on 2026-10-02
verified robots/listing egress and initial public state persistence in a quiet
window; it made zero article requests. Ordinary scheduling remains in place.

| | |
|---|---|
| Adapter | `scraper/sources/ph_nsc.py` (`PHNscAdapter`) |
| Manifest | `shadow/ph_nsc/manifest.json` (`enabled: true` for shadow only, deliberately not under `desks/`) |
| Runner / workflow | `scripts/shadow_collect_ph_nsc.py` / `ph_nsc_shadow.yml` |
| Public state branch / schedule | `shadow/ph-nsc` in this repository / daily 10:10 UTC, plus manual dispatch; active after PR #96 |
| Tests | `tests/test_ph_nsc_adapter.py` (offline; a socket guard fails any real connection) |
| Fixtures | `tests/fixtures/ph_nsc/` (byte-exact copies, hash-pinned by the tests) |
| Review receipt | `docs/PH_NSC_ADAPTER_REVIEW_RECEIPT_2026-10-01.md` |

`desks/registry.json` declares no Philippines desk and
`load_all_desks()` still returns only `china` and `singapore`. Nothing here qualifies this source:
one quiet manual run is not periodic reliability, and none may be described as qualified (DECISION_LOG).

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

## Post-merge operational measurement — 2026-10-02

[Run 37072106688](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37072106688)
used collector `302a74555a3503ea344351b1c99c64c128911104` and the unchanged
full approved identity below. Target `2026-10-02` was explicit
(`target_date_source=explicit`); the window was September 26–October 2.
Result `ok_no_publications`, health `ok`: one robots read and one successful
category listing, six older items, zero in-window references, zero article
requests and zero retrieved/inserted/duplicate/failure counts. The accepted
robots/listing paths require HTTP 200; request counts are derived from the
adapter path and ledger telemetry, not a separately preserved wire trace.

Public state was initialized at
[commit 2dd38f1bcfc598f1eca66082b626146023edf7e7](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/2dd38f1bcfc598f1eca66082b626146023edf7e7):
one ledger, clock and empty database. The
[attempt artifact](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37072106688/artifacts/11254829602)
matched all state bytes; the ledger's database hash matched the closed SQLite
file, integrity was `ok`, and no WAL/SHM/journal files remained. No article
capture hashes exist because no articles were requested. The workflow's clean
collector check passed. Production DB/output file lists and Git blob hashes
were unchanged against this run's own **7,254-file** baseline, distinct from
the earlier **7,209-file** reviewed-branch/Japan snapshot.

This verifies Actions robots/listing egress and initial state persistence only.
Article-body egress, extraction and capture preservation in Actions remain
unobserved. Review around **2026-10-09** after ordinary scheduled runs; this is
an evidence review date, not a qualification threshold. No checkpoint review
is on record.

## Evidence and remaining gates

1. **Repository-client compatibility: measured successfully for the owner's Mac environment.**
   Actions robots/listing egress is now measured; article-body egress in Actions
   and other network environments remain unmeasured.
2. **Reliable periodic access: unmeasured.** One successful bounded session is not evidence of
   multi-day reliability, scheduled-run stability or rate-limit behaviour, even
   with the subsequent successful quiet manual run.
3. **Reuse permission: not reviewed.** robots.txt is an access signal, not a licence for the text.
4. **Discovery completeness: prospectively bounded; pre-2026-06-03 history remains unestablished.**
   The category exposes six statements from 2026-06-03 through 2026-07-08 and no pagination.
   The sitemap exposes only the homepage. The two-page author archive exposes the same six
   Official Statements and page 3 is 404. Windows reaching to 2026-06-03 or earlier continue
   to fail closed rather than claim historical completeness.
   The pagination logic rests on three tiers of evidence. *Observed*: the 2026-10-01 capture
   (`tests/fixtures/ph_nsc/nsc-listing.bin`) is one listing page of six items and holds no
   pagination markup (no `rel=next`, `wp-block-query-pagination`, `next` class, `/page/N` link or
   `paged=` query; checked by text search), as the first sentence of this gate records. The only
   paginated NSC listing on record is the author archive above (two pages, page 3 is 404); its
   markup was not kept as a fixture and this adapter does not walk it. Scheduled runs since were
   not examined for this note. *Synthetic*: every multi-page walk (next link, numbered links,
   repeat, loop, skip, order, page cap) is tested only on pagination markup the tests build.
   *Assumed*: that a paginating category would publish links in the forms the parser reads
   (`rel=next`, `wp-block-query-pagination-next`, `/category/official-statements/page/N/`), and
   that a page lists the newest posts first (each page's order is checked; that it is the newest
   set is not). A pagination form the parser does not read is reported as `unsupported_pagination`
   and never counts as coverage, so a window the pages read cannot prove fails the run.
5. **Category anomaly: unresolved but not reproduced on 2026-10-02.** The earlier gambling-content
   observation is neither dismissed nor treated as proof of compromise.
6. **Collector identity: owner-approved unchanged for scheduled use (2026-10-02).**
   Ben chose the existing full rehearsed header:
   `ChinaMilWatch-ShadowCollector/0.1 (+https://chinamilwatch.org; research archive; contact via site)`.
   The runner and adapter retain it character for character. No contact details,
   private remote or new credentials are introduced (DECISION_LOG 2026-10-02).
7. **Live remeasurement with the repository client: completed successfully on 2026-10-02.**
   This closes the original Mac-environment live-measurement gate, not the periodic-reliability
   or Actions article-body egress gates. The later quiet Actions run establishes
   only robots/listing egress and initial state persistence.

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

**Chosen visibility:** Ben approved publicly readable `shadow/ph-nsc` state in
`VSSpowerlifting/China-Mil-Watch` on 2026-10-02. “Private” in earlier planning
meant nonproduction, not a confidentiality requirement. The state branch and
Actions artifacts are not confidential; they remain excluded from the published
site, production collection and public corpus counts. Use the existing repository
and workflow token, with no private remote or new credentials.

PR #96 removed the literal-false job guard. Workflow defaults stay read-only
and contents-write stays scoped to the collector job. Initial quiet state
persistence is measured above; periodic reliability, Actions article-body
retrieval/extraction/capture evidence, reuse/republishing, historical
completeness, the earlier anomaly and human checkpoint review remain open.
The October 1 adapter review receipt is historical evidence and is not rewritten.

## Pending parser-refusal correctness repair (#99, review-only)

A 2026-10-08 targeted repair narrows the HTML challenge-screen handling to
`bs4.builder.ParserRejectedMarkup`, caught only when BeautifulSoup is constructed.
A legitimately parser-refused HTML body must be processed through the existing
typed robots/body-failure paths; that refusal alone does not prove the site
presented an access challenge. Explicit `cf-mitigated: challenge` and recognized
challenge markup remain authoritative. Unexpected selector or programming errors
must **not** be silently converted to harmless HTML: unlike the older draft's
broad exception handler, they propagate for diagnosis.

This repair has **not** been merged or applied to running NSC schedules.
It adds two additional synthetic regression tests to the previous two PR #99
tests; tests/CI have to pass at the final exact head. No page retrieval,
source-policy change, collector identity change, credential change, production
data or shadow-state modification is part of this update.

## Bounded verification after activation merges

1. Fetch main and verify it contains the activation merge. Record its SHA, the
   current `shadow/ph-nsc` ref (or confirmed absence), and production DB/output
   hashes. Inspect recent `ph_nsc_shadow.yml` runs and ledgers first: use an
   existing post-merge scheduled run for the chosen logical date if available.
   If one is queued or running, wait; do not dispatch a duplicate.
2. Otherwise authorize one normal manual run on main, naming the current UTC
   date explicitly (replace `YYYY-MM-DD`, never request historical backfill):

   ```bash
   gh workflow run ph_nsc_shadow.yml --repo VSSpowerlifting/China-Mil-Watch \
     --ref main -f target_date=YYYY-MM-DD
   ```

   The unchanged runner uses seven publication dates (`lookback_days=6`) and a
   cap of 40. It reads robots and the Official Statements listing, follows only
   published pagination (at most 20 listing pages), and fetches only in-window
   statements: at most 61 NSC requests (one robots, 20 listings, 40 statements).
   More than 40 candidates or unprovable coverage fails before body
   fetches. Requests keep the full approved identity, fixed two-second spacing,
   no redirects, retries, challenge bypass or supplemental archive probing.
3. Record the run URL/attempt, actual collector SHA, logical target date/source,
   request/status counts and health. Verify robots/listing/window evidence,
   discovered/selected/retrieved/inserted/duplicate/failure counts, and exact
   capture/document hashes if bodies were collected. A quiet window may validly
   return `ok_no_publications`; that measures listing egress, not body egress,
   completeness before June 3, multi-day reliability or reuse permission.
4. On success, record the new public state commit and verify it changes only
   `state/`, binds to that run/collector, has no WAL/SHM files, preserves old
   ledgers/clock and matches ledger state hashes. Confirm the workflow's clean
   collector check and unchanged production DB/output. On collection failure,
   verify no state push occurred and download the complete attempt-state/log artifact
   (90-day retention). Preserve refusal/challenge evidence; do not retry to
   defeat it. If a later workflow step fails, inspect whether state was already
   published rather than assuming no commit. Divergence is a failure, never
   permission to force-push.
5. If recovery is needed, review the failure first and use a new manual run
   with its intended `target_date`, not an ambiguous UI re-run. Continue ordinary
   scheduled evidence gathering and human review; no automatic promotion or
   qualification follows from the first successful run.
