# China curation — 25-record diagnostic editorial intake (15 October 2026)

**Status: PRIVATE RESEARCH INTAKE, not a curated archive, not source-original
verification, and not an editorial decision.** This work advances [China public
archive design #605](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/605).
It complements [sampling #603](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/603),
[duplicate QA #612](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/612),
[unsigned review ledger #615](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/615),
and [source-original quality research #618](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/618).

## Why start this way?

The ~600-record corpus review sample is a **coverage and bias detection aid**;
it cannot be treated as 600 editorial inclusions. A smaller, bounded batch
forces attention to exactly what makes a record worth finding: original
publication, issuing institution vs syndication outlet, publication and
collection date, captured text completeness, translation, event uniqueness,
source rights, and relation to existing Briefs.

**This first batch is intentionally diagnostic rather than representative.**
It contains **25 records** with the following source distribution: **16
Global Times, 7 PLA Daily, 1 China Military Online, 1 Chinese MND**. Global
Times is overrepresented because the initial task is historical extraction
quality. No desk-level statistical conclusion, source ranking or proportional
archive target may be inferred from this pilot.

### Twenty-five stable records by research lane

| Lane | Record IDs | Research task |
|---|---|---|
| Screened-out primary source | **2849, 2391, 948** | Verify original foreign ministry/military statements that automated screening omitted |
| Historical capture quality | **2180, 2265, 946, 170, 419, 905, 793, 1246, 1954, 2753, 3180, 3181** | Investigate suspected missing/teaser-contaminated stored bodies; never restore text silently |
| Source fidelity unknown | **792** | Read direct original before certifying a plausible-looking stored article |
| Primary-source significance | **1630** | Separate what Chinese official media actually displayed from commentator inference |
| Syndication/republication | **4348/4346**, **3454/3465** | Establish original byline, issuer, body differences, republication and rights |
| Brief source-trail comparison | **2148/2189** | Protect cited July 6–7 missile-test records and examine differences |
| Media/photo rights and captions | **1675** | Assess South China Sea photographic evidence and reuse rights |
| Keyword false-positive control | **4104** | Distinguish **Middle East Gulf** from an East China Sea military event |

**The source-trail protection IDs included in this diagnostic pilot are
#2265, #2148 and #2189.** A protected record remains citable even if its body
has a documented historic extraction defect. Protected trail does **not**
automatically mean curated public prominence.

Compare relationships inside the private packet are symmetrical, but **do
not assert equivalence**: #3180/#3181 share an apparent bad capture, not
necessarily the same event; #2180/#2148/#2189 are reports about a related
missile test, potentially distinct publisher claims; #4346/#4348 and
#3454/#3465 are near-identical text/outlet candidates. All links survive
even if a representative is selected later.

## Generated read-only research packet

Input is `research/china/editorial-batch-01-2026-10-15.json` tied to
`output/corpus-index.json` (the frozen **October 14** 5,230-record snapshot).
Each item includes stable ID, exact source, original title, original stated
publication date, **one source-specific question**, and related IDs. Every
`editorial_decision`, `reviewer` and `reviewed_on` is **null**.

The offline command:

```sh
python3 -m unittest -v tests.test_china_editorial_batch

# Must be a NEW external directory; do not create it in advance.
python3 scripts/prepare_china_editorial_batch.py \
  --index output/corpus-index.json \
  --batch research/china/editorial-batch-01-2026-10-15.json \
  --records-dir output/record \
  --output-dir /private/tmp/ipr-china-review-batch01-20261015-new
```

Creates an ephemeral `review.html` and `summary.json` with 0700 directory
and 0600 file permissions, and refuses pre-existing, symlinked immediate
parent, repo-local or relative output paths. Choose a new path each run.
The HTML is readable without JavaScript, has a `noindex,nofollow,noarchive`
meta directive, contains no externally loaded assets, and links to
unchanged permanent IPR record and original publisher URLs.

The report also reads the historical `Collected at` timestamp, whether a
readable original-text block exists, rough stored body length and teaser-like
ellipsis cues. **Those are diagnostics, not source authenticity or editorial
significance judgments.** The packet does **not copy full article bodies**;
reviewers follow the preserved URL and the original publisher citation.

The validator freezes the original October 14 `baseline_snapshot` and
the three protected original Brief-trail IDs, while accepting **forward-only
new corpus snapshots** when the complete current index count matches its
records and every one of the 25 selected research IDs still has the *exact*
same source, title and publication date. New records remain preserved but
are never automatically inserted into this batch.

The validator fails closed if the index regresses in date/count, any
of those exact identities drifts, an ID is duplicated/non-China,
the frozen published Brief source-trail set is lost, a local rendered record lacks URL/capture provenance, any compare
reference is missing or asymmetrical, or any decision/owner approval is
invented. An actual source may be short, a photo story may legitimately
have no prose, and the original may have been republished without
independent corroboration. Each still requires independent editorial review.

The focused GitHub Actions workflow generates the two files into ephemeral
**runner scratch only**, checks 25 entries and zero approvals, and confirms
the canonical SQLite and generated public `output/` remain unchanged.
It does not upload a packet, re-run scrapers, call a model, access publisher
sites, create/repair source text, change site routes, merge or deploy.

## How the first reviewed batch advances curation

For each record an independent reviewer should return **one** proposed
disposition in PR #615's eventual versioned decision ledger:
`retain_primary`, `retain_context`, `group_secondary`,
`exclude_discovery`, or `hold_quality`; plus a specific evidence-based
rationale, independent original URL, captured publisher, true issuing
institution, article/event timing, text/translation completeness, and
recorded reviewer/date. Distinguish whether it proves *an official statement
was made* from independent proof that the underlying event occurred.

No future AI model result or teaser heuristic may populate an owner-approved
field. After a separate actual owner review, later work can build a frozen
selection manifest and curated-first public interface under guarded release.
Every unselected record, source URL, citation, historic capture and
full-corpus page remains available. New daily records remain unreviewed.
