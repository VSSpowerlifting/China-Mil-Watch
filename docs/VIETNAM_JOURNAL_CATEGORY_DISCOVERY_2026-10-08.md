# Vietnam National Defence Journal — English category discovery contract

**Status:** offline parser candidate only. No shadow source activation,
article-body capture/retention, public records, weekly cadence, or production
promotion authorized. This PR is stacked on the offline journal article
parser PR #138; both depend on disabled-source PR #129.

## Why the homepage is insufficient

A bounded source research run on October 8, 2026 UTC verified that the
journal has four *separate* English category pages, each accessible under
the existing declared IPR crawler identity and desktop robots policy.

[Actions 37716446432](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37716446432)
(job 113113870869, exact research head
`53c5a8136d3da2e5f88ac891ed040447eddaefdc`)
ran seven synthetic offline tests and performed five GETs: robots policy,
News (`/en/news-54.html`), Theory and Practice
(`/en/theory-and-practice-56.html`), Events and Comments
(`/en/events-and-comments-57.html`), and Research and Discussion
(`/en/research-and-discussion-58.html`). It followed no pagination
links, requested no article pages, and saved no article prose.

| Listing | Unique IDs visible on that entire fetched page | IDs with locally associated date hints |
| --- | ---: | ---: |
| News | 18 | 16 |
| Theory and Practice | 19 | 12 |
| Events and Comments | 18 | 14 |
| Research and Discussion | 19 | 16 |
| All pages combined | **74** | **58** |

These numbers are **observed candidates**, not a proof that all
records belong to the category used to discover them: recommendation
sidebars and highlights repeat article links across sections. Numeric
identities were deduplicated across all four pages. Original source
dates were inferred **only as local listing hints**, not verified
against complete article pages or guaranteed chronological coverage.

The old homepage probe saw only 26 distinct IDs. Scanning the four
category pages therefore exposes a substantially broader *observed*
candidate set without claiming collection completeness. The research
found **zero identifiable pagination controls using its bounded
HTML-control patterns**, which cannot establish that there is no
JavaScript, postback, parameterized, or other pagination mechanism.
Neither scrolling nor unapproved URL guessing nor offsite search
can substitute for an explicit, source-bounded pagination proof.

## Offline contract

`scraper/sources/vn_journal_listing.py` provides pure functions
for supplied HTML in memory, not HTTP collection:

- Exactly four fixed HTTPS English category URL shapes are accepted.
  A URL with an invented `page=2` query is refused.
- A candidate is a real canonical English article permalink on the
  desktop host with an exact `vndj-en:{numeric ID}` identity.
  Mobile URLs, foreign hosts, queries and site clocks are not aliases.
- Repeated same-ID links collapse to one candidate. Conflicting
  canonical URLs or contradictory listing dates fail closed.
- An article date may be a **hint** only when one printed date is
  co-located with one distinct article link in a bounded ancestor
  element. Uncertain articles have a null date; they are not dropped.
- Union across four pages validates stable identity and returns
  `full_date_bounded_completeness_proven: false` and
  `pagination_proven: false` unconditionally.
- No source body or HTML output is retained, and all generated
  metadata explicitly denies article-body reuse authorization.

The tests use **synthetic HTML**, not republished source material.
This offline parser has not yet been proven to recover all 74
observations identically from the live pages. That requires a separate
bounded, policy-gated in-memory evaluation after its tests pass.

## Next eligibility gates

1. Verify selectors/date-association across all four live categories,
   comparing exact candidate counts and overlap with the research
   observation. Review any discrepancy; do not 'fix' by inventing
   dates or dropping records.
2. Establish an explicit permitted pagination/discovery interface or
   record that the available first-page windows cannot support an
   exhaustive date-bounded source. Measure how quickly older items
   disappear and whether overlapping scans miss publications.
3. Validate body/title/date/author against the article-specific
   parser and handle revision/version identities. Preserve publisher
   attribution as military-journal commentary, **not** a MOD directive.
4. Resolve legal basis for storing full article bytes separately from
   limited factual metadata/citation, then get owner authorization
   before opening an isolated shadow source and a *new* Day 0 clock.

No dependency on the existing MPS/MOIT clocks or the MPS pilot
review queue is implied.


## Live parser parity proof — second bounded observation, October 8 UTC

The offline listing parser itself (not merely a research-only URL scanner)
was tested against four **live** desktop English category pages in
[Actions run 37721439408](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37721439408)
(job `113129755123`, proof branch
`research/vietnam-journal-listing-live-parity-20261008`).
The one-shot check first passed **32 offline source/article/listing tests**
and then made exactly **five** bounded GET requests: official desktop
robots.txt plus one permitted read of each named category. It followed no
pagination and did not fetch article bodies.

| English listing | Independently scanned article IDs | Offline parser IDs | Parser date hints | Missing/extra IDs |
| --- | ---: | ---: | ---: | ---: |
| News | 18 | 18 | 18 | 0 |
| Theory and Practice | 19 | 19 | 17 | 0 |
| Events and Comments | 15 | 15 | 15 | 0 |
| Research and Discussion | 19 | 19 | 18 | 0 |
| **All four** | **71** | **71** | **68** | **0** |

**All four section-level canonical-ID comparisons passed.** The independent
scanner and offline parser agreed on exact IDs and URLs, with no missing,
extra or conflicting canonical article link on the pages observed. Of
71 current candidates, **68** had locally attributable *date hints*;
these hints remain unverified publication dates, and the three undated
candidates are retained rather than silently dropped.

This differs from the earlier [research run 37716446432](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37716446432),
which saw 74 IDs across the same page set and 58 local date hints.
The **Events and Comments** page exposed 18 IDs in the earlier
observation, versus 15 in this one. The difference establishes that the
visible listing window may change; it does **not** establish that any
publisher article has been deleted or that the journal's historical record
is complete. The independent older hint heuristic was also not identical
to the current stricter parser, so differences in the two date-hint
counts are **not** evidence that ten formerly undated source articles
were newly published or independently verified.

The metadata-only evidence artifact
[11526017404](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37721439408/artifacts/11526017404)
has archive digest
`sha256:4bac4f7c0a0da98678758335300f2cf838a3e27697794bea2713b75f49b21c2d`
and expires November 7, 2026. It contains response hashes,
counts and verification booleans, **not journal HTML or prose**.

**Disposition:** identity discovery on the four observed category pages
has passed a real-host parity test. Date hints are provisional.
Historical pagination, date-window completeness, source-use rights and
collector activation remain separate **unpassed** gates; no shadow
state, public records, full text or production database has changed.
The disposable parity workflow remains in PR #151 and must be
closed **unmerged**, not promoted as a production job.
