# China archive: dated duplicate candidates and source-text fidelity (2026-10-15)

**Status:** Independent read-only audit proposal, not an editorial selection, deletion,
index filter, remediation or production release. Complements China curation PR #603
and Phase-2 issue #605. The current system already has a
**destructive** historical duplicate-cleanup utility
(scripts/cleanup_duplicates.py): **DO NOT call it** for archive curation.
Its source-tier canonical ordering is not a substitute for editorial issuer
verification, and it deletes evidence.

## Snapshot findings

Based on the published October 14, 2026 `output/corpus-index.json`:

- China stored records: **5,144**, across five China feeds.
- Exact titles after cautious Unicode/punctuation normalization repeat in
  **41 headline families comprising 91 stored records**. This includes
  *different events with recurring headlines* and cannot be described as
  50 duplicates.
- Splitting identical titles into **at-most-two-day dated windows** produces
  **25 potential same-event review groups, totaling 50 records**.
  **8 groups cross feed boundaries**, and the other 17 are within one feed.
- Even if manual review confirmed all 25 groups as duplicate publications,
  this addresses only **25 possible extra browse occurrences**. It cannot
  reduce 5,144 stored Chinese records to a suitable 500–700 *curated*
  discovery set. **Selection for public relevance remains the main job.**
- Identical coast-guard headlines recur weeks apart. For example, PLA Daily
  IDs **742, 1898, 2715, 3666, 4734** report identically titled routine
  law-enforcement patrols around Kinmen on dates ranging from May through
  September. These MUST NOT be silently grouped as one event. Other recurrent
  examples include Southern Theater Command patrols around Huangyan Dao.

The window is a conservative **review hypothesis**, not proof that two
articles are the same event: some launches, visits or exercises may have
different reporting dates; different institutions may use the same headline
for different things; translation and mirrored titles can differ. A
cross-outlet pair can also represent materially distinct claims or framing.

## Examples worth investigating

- **#3454 PLA Daily / #3465 MND China**, August 23: same Chinese headline
  concerning a 76th Group Army brigade's cross-service training. Check the
  actual issuing unit and original byline, not only the MOD China hostname.
- **#4346 China Military Online / #4348 Global Times**, September 18:
  near-identical English footage headline, both concerning a Philippine
  vessel and China Coast Guard; check footage provenance, source rights,
  date of incident vs date of publication, and any differences in attribution.
- **#2148 / #2189 PLA Daily**, July 6–7: same launch headline concerning
  a submarine-launched strategic missile. Compare the complete original
  texts and factual date/event before suggesting a single browse entry.
- **#2180 Global Times**, July 6: the stored text looks like a homepage feed
  composed of unrelated teaser titles. This needs *extraction-quality repair*
  review. It is not safe to cite the captured body as an authoritative report
  of the naval test. Preserve the imperfect historical capture and provenance
  under the governed correction workflow.

## Stored-text side-by-side spot audit

These are character 8-gram Jaccard overlap estimates on the **captured
`original-text` bodies**, with whitespace normalized. They are **not** factual,
provenance, event-equivalence, or publisher-authorship certifications.

| Record pair | Stored lengths (characters) | Approx. overlap | Investigation |
|---|---:|---:|---|
| #4346 / #4348 | 4,015 / 4,008 | 0.994 | Likely same distributed report; check author/origin and rights |
| #3454 / #3465 | 1,612 / 1,590 | 0.979 | Likely MND/PLA Daily republication; MND hostname does not confer authorship |
| #3294 / #3353 | 805 / 837 | 0.963 | Similar operational-training feature; check publication provenance |
| #3304 / #3352 | 1,647 / 1,618 | 0.969 | Near-identical border-unit feature; low likely discovery value |
| #3245 / #3354 | 838 / 813 | 0.969 | Near-identical naval aviation training feature |
| #3208 / #3358 | 857 / 847 | 0.973 | Near-identical naval joint-training feature |
| #2265 / #2294 | 321 / 4,725 | 0.013 | **Severely divergent capture:** one may contain an unrelated exercise teaser |
| #943 / #946 | 856 / 135 | 0.004 | **Severely divergent capture:** Global Times text looks unrelated to headline |
| #2148 / #2189 | 146 / 186 | 0.627 | Same missile-test topic, different concise official source messages |

**Critical insight:** Identical headlines with a near-zero body overlap can
indicate extractor pollution instead of duplicated reporting. Those cases
should be reviewed for **fidelity first**, not collapsed or excluded. In the
submarine test pair, substantive differences between the brief wire and
military press treatment may themselves be worth preserving. A high-overlap
pair is also not an instruction to remove a citation, URL or source version.

The new `--compare-record-html` option reproduces a stored-body similarity
measurement for an explicitly supplied pair of existing pages (without
fetching sources or writing to the repository):

```bash
python3 scripts/audit_china_duplicate_candidates.py \
  --compare-record-html output/record/3454.html output/record/3465.html
```

## Read-only investigator

```bash
python3 -m unittest tests.test_china_duplicate_candidates
python3 scripts/audit_china_duplicate_candidates.py
python3 scripts/audit_china_duplicate_candidates.py \
    --out /tmp/ipr-china-duplicate-review.json
python3 scripts/audit_china_duplicate_candidates.py \
    --record-html output/record/2180.html
```

The tool uses only the **compact existing index**, verifies published
source-trail ID protection and the index field schema, and does not open the
canonical SQLite database. The optional individual HTML check parses only the
record's stored original-text area, not its navigation/metadata. Five or more
ellipsis-style truncations suggest a feed-capture problem, but clean-looking
content could still be incomplete or misleading. Neither the title nor the
heuristic may automatically suppress, amend or promote a record.

It can export a reviewer docket **only outside the repository** and refuses
overwriting an existing report. It is safe to run without output regeneration,
collection, source requests, web browser access, model inference, merges or
deployment.

## Historical extractor caveat

The existing `scraper/sources/global_times_mil.py` and
`tests/test_global_times_extraction.py` explicitly document a **September
16, 2026 repair** for flow-body and related-article teaser pollution. The
recorded HTML fixture `flow_1365233_missile_test.html` tests the same missile
page as record #2180. Thus an older contaminated database capture **does not
prove the current adapter is broken**. The repair work is a historical
provenance/correction problem, not permission to rescrape or silently replace
the original. Track the bounded historical-quality audit in
[issue #613](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/613).

## What review of each pair requires

1. Verify each title, original text/caption, issuing institution, hosting
   publisher, publication/event date, source URL and source availability.
2. Classify the relationship: **same publication duplicated**,
   **same underlying event but materially different coverage**, **separate
   recurring event**, **uncertain**, or **quality hold**. Record why.
3. If the first two are verified, optionally choose ONE representative
   **for the curated browse display**. Do not delete either preserved record,
   change its ID or source URL, or break published Brief trails.
4. If the original source is incomplete, not independently legible, or the
   publisher is only syndicating another institution's statement, hold
   canonical/issuer attribution for human review rather than choose the
   highest-ranked configured source automatically.
5. Recheck representative choices with the 600-record reviewed selection
   draft in Phase 2. A recurring event may merit **both** separate records
   when its recurrence is itself the analytical signal.

**Stop condition:** vetted source pairs, explicit editorial decisions and a
separate owner-approved publication manifest. This PR does *not* choose
winners, edit the site, change source collection, repair extraction, or publish.
