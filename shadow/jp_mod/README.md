# Japan MOD / Joint Staff — shadow collection

Shadow evaluation. Nothing here is live, published, or counted in any public
figure. The Japan desk's public status is `shadow`; the two reachable Japanese
RSS sources are explicitly `enabled: true` for this shadow runner only; and
`desks/` deliberately does not contain a `japan/` directory, so
production desk discovery cannot see this manifest by accident.

The runner honors `enabled`: false or absent excludes a source, as does
`_not_collected: true` regardless of enabled state. `jp_joint_staff_en` and
`jp_mod_press_en` remain disabled, not collected and without adapters.

## What the two feeds actually are

Both declared feeds were categorised in full on 2026-08-26. The result corrected
the original scope claim, which called this source "Japan MOD / Joint Staff —
official releases" in languages `["ja", "en"]`. All three parts of that were
wrong.

### `/j/rss/news.xml` → `jp_mod_news_ja`

The ministry's Japanese-language news stream. **142 items**: `/j/press/` 105,
`/j/approach/` 37. **134 HTML, 8 PDF.**

### `/j/rss/update.xml` → `jp_mod_siteupdate_ja`

A **whole-site update stream, not a press-release feed**. It reports any page
the ministry publishes or revises. **391 items**: `/j/press/` 126,
`/j/budget/` 93, `/j/profile/` 76, `/j/approach/` 63, `/j/policy/` 21,
`/j/presiding/` 11, `/j/kids/` 1. **342 HTML, 0 PDF.**

### What neither feed carries

**Zero Joint Staff (`/js/`) items. Zero English (`/en/`) items.** Both are
declared in the manifest as separate, not-collected sources so they stay
distinguishable, and both are unreachable — their index pages are challenged.

### Why they are two sources and not one

They are objectively different streams. Collapsing them into one source called
"official releases" is what let the first manifest describe a budget table as an
official release. Each feed is now its own source, each with one endpoint, and
every stored record carries the source it came from.

Nothing is filtered. Keeping only the items that look like press releases would
be silent sampling, so every discovered item is kept and labelled by its URL
family — a budget page is stored as a budget document, a children's page as a
public education page, and an unrecognised family as "ministry page
(unclassified)" rather than vanishing.

## What access actually looks like

Qualified 2026-08-26 with one honest request per endpoint, using the project's
own user agent. `www.mod.go.jp` is behind Cloudflare, and the edge does **not**
treat every document the same way:

| Endpoint | Result |
|---|---|
| `/robots.txt` | 200 — disallows only `/a/` and `/sp/j/` |
| `/j/rss/news.xml` | 200 `application/xml` |
| `/j/rss/update.xml` | 200 `application/xml`, **304** on `If-None-Match` |
| `/j/press/news/2026/08/25a.pdf` | 200 `application/pdf` |
| `/j/press/news/2026/08/26b.html` | **403**, `Cf-Mitigated: challenge` |
| `/en/press-release/` | **403**, `Cf-Mitigated: challenge` |
| `/js/press/index-en.html` | **403**, `Cf-Mitigated: challenge` |

**XML and PDF are served. HTML is challenged.** Robots permits every path this
collector touches — the challenge is an edge policy, not a robots directive.

### How much of it can actually be read

Across `news.xml`, **8 of 142 items (6%) are PDF and carry full text**; **134 of
142 (94%) are HTML and are recorded as titled, dated discovery records with no
body**. `update.xml` carries no PDFs at all.

This is **partial retrieval, not coverage**, and it is not a qualified desk.
Most sampled bodies remain challenged.

## What the collector does with that

Current-policy enforcement is repaired in source on 2026-10-06. Before this
repair the runner's `robots_status: allowed` was hard-coded and the adapter's
policy checker was unused; historical ledger labels do not establish policy
compliance. The runner now shares one live policy observation across its two
same-host sources per run. It checks every requested feed/PDF path, records
policy text/hash/status/time, observes supported crawl delays and refuses
unsupported rules, unreadable policy and challenges. A refusal stops requests,
fails the run and cannot advance the successful-run clock. An observed 404/410
is `absent`, distinct from refusal. Redirects are not followed automatically.
No historical ledger is rewritten. This local repair has not run in Actions;
the measured scope, remaining gates and live evidence are in
`docs/JAPAN_PHILIPPINES_DESK_COMPLETION_2026-10-06.md`.

Discovery runs on the two official RSS feeds, which work. Bodies come from PDF
documents, which work, through the existing `processing/pdf_text.py` extractor —
the same one written for these releases, with its own status vocabulary for
scans, encrypted files, malformed files and size refusals. No OCR.

HTML items are discovered, titled, dated, and then **not fetched**. They are
recorded as `access_challenged` and stored as rows in `shadow_unretrieved`, so
the gap is a visible row rather than an absence. Nothing infers that a
challenged item does not exist.

The challenge is not solved. No browser user agent, no cookie replay, no
headless browser, no proxy, no retrying a 403. A challenge is a host telling
this client it is not welcome on that path; the honest response is to record
the refusal where a reader can see it.

## Why a challenged run is not a failed run

Singapore's runner treats an access refusal as a failed run, correctly: MINDEF
serves every release to this collector, so a 403 there means something broke.

Japan is not shaped like that. A *normal* Japan run has most of its discovered
items challenged and a minority retrievable as PDF. Reusing Singapore's
taxonomy would mark every Japan run `fail` forever — an alarm that is always on,
which is the same as no alarm.

So a challenged item is a **disclosed gap**, and the run reports `health:
partial` with the count and the URLs in the ledger. What would be a real
failure is the open routes closing: the feeds going down (`listing_failure`), or
the PDFs starting to be challenged too (`access_challenged`, `degraded`).

## Isolation

* `scripts/shadow_collect_japan.py` never opens the production database and
  never writes `output/`; it refuses any `--state-dir` inside the repository
* state lives on the `shadow/jp-mod` branch, checked out outside the working
  tree by `.github/workflows/japan_shadow.yml`
* the workflow holds `contents: write` and pushes exactly one ref,
  `shadow/jp-mod` — never `main`, never `gh-pages`, never with `--force`
* there is no Pages step, no deploy step, and no analysis call anywhere in the
  collector
* the workflow asserts its own checkout is still clean before publishing state

## Deduplication

By canonical URL, with extracted-text content hashes retained for provenance.
**Never by title.**
Japanese ministry releases reuse titles legitimately — 「日米合同委員会合意に
ついて」 recurs whenever the Joint Committee agrees anything — and title-level
deduplication would collapse a year of distinct agreements into one record.

## Post-merge operational measurement — 2026-10-02

[Run 37033909330](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37033909330),
collector `30b7169c892a48049efe538f02f8fcc2aff6d481`, explicitly targeted
2026-10-02 after PR #95 merged. It persisted
[state commit 138c4e20b7b06ba766bab063cc544c2d132e7791](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/138c4e20b7b06ba766bab063cc544c2d132e7791).
**54 previously unrecorded URLs received cap space** (31 news, 23 site updates),
including September 29–October 2 items. **Zero new usable bodies** were inserted;
the four previously stored PDFs remain unchanged. Result `ok_all_duplicates`
was accompanied by health `partial` and **140 outstanding gaps**: 68 news,
71 site updates and one historical source-unassigned challenge. Globally these
are 137 challenges, one oversized response and two PDFs without a text layer.

All 86 prior gap rows retained their original title/date/reason/first-seen
provenance; old ledgers, clock and bootstrap were unchanged. The collector
checkout stayed clean and production DB/output were unchanged against the
**7,209-file** baseline used for the earlier verification. The later NSC run's
**7,254-file** snapshot is a separate baseline, not a shadow-created increase.
No challenge bypass or retrieval-limit change was made.

This run had zero deferred or carried-pending URLs. Feed-eviction persistence
and deferred priority over retries/revalidation are demonstrated by regression
tests, **not this live run**. Observed selection recovery does not establish
complete document coverage or recover URL identities missing from old deferral
counts. Review admission, backlog/gaps and usable-body yield around
**2026-10-09** after ordinary scheduled runs; this is an evidence review date,
not a qualification threshold. No checkpoint review is on record.

## Selection and recorded backlog

The 40-item per-source cap remains a rate ceiling. Previously it was applied
oldest first before checking state, repeatedly selecting old challenges and
stored PDFs while newer items waited indefinitely. The runner now processes
never-processed URLs (including deferred URLs) first, oldest first within that
group. Previously failed retrievals follow, then stored PDF revalidation with
the existing HTTP validators uses only spare capacity. A known challenge is
counted as `known_challenged` and its observation is updated without calling
fetch again. `challenged` counts newly selected refusals; neither is hidden by
an `ok_all_duplicates` result, and health remains partial or degraded.

Overflow is stored in the existing `shadow_unretrieved` table with reason
`deferred_cap`, source slug, original feed title and date. It remains queued
even after it leaves the RSS feed. The table receives a nullable source-slug
column forward-only; old gap identities, titles, dates and first-seen runs
are preserved. Recovered rows remain as historical gap provenance, excluded
from the current unretrieved total when a body is stored. Old ledgers and the
bootstrap cutoff are untouched. The ledger names deferred URLs and counts
off-feed pending items and postponed revalidation separately.

Health is based on the entire outstanding gap table, not just today's feed.
An off-feed challenge still contributes to `outstanding_challenged` and cannot
turn into a healthy empty run. Mixed feed/fetch/extraction failures remain
partial even when some PDFs succeed; an open PDF route failure is not masked
by a new HTML challenge. A 304 counts as a duplicate only if a stored body
exists, and orphan validators are not loaded.

Historical gap rows without a source slug remain unassigned until an actual
feed observation supplies it. Off-feed legacy rows are retained and named in
`unassigned_gap_urls`, contribute to unhealthy coverage, and are not assigned
to a feed from URL shape. Their dates, titles and first-seen provenance are not
rewritten. This preserves the migration limitation rather than hiding it.

Keeping 40 is appropriate for this repair: new work now gets that entire
budget before revalidation. Raising it would increase requests without fixing
selection fairness. Sustained arrivals above the ceiling would still grow a
visible backlog and require a later human rate decision; nothing is sampled.
No historical deferred item absent from today's feeds can be reconstructed
from an old count alone. The repair makes future deferrals durable, not a
claim that the old loss was recovered. No checkpoint review is on record.

The workflow now preserves completed failed attempts as state evidence before
reporting job failure. It requires one ledger for the exact run/attempt, the
actual collector commit and a matching closed-database hash, and refuses
changes to old ledgers, clock or bootstrap. A crash has no completed ledger
and cannot push. This distinction matters: discarding every all-fetch-failure
attempt discarded its gap rows too, allowing the same failures to monopolize
the next run. The workflow remains failed when collection fails; preserving
evidence does not change the result or advance the clock.

## What this does not establish

That the Japan desk is ready. It is not. This is qualification and evidence
collection, on a source whose HTML estate this project cannot read. Whether a
PDF-and-metadata record is a good enough basis for a Japan desk is a separate,
later, human decision.
