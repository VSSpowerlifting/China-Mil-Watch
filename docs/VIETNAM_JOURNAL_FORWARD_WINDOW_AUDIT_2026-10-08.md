# Vietnam journal — forward listing-window audit (offline research contract)

**Status:** diagnostics only. Does not activate a source, schedule requests,
start Day 0, store article bodies, prove publisher rights, or establish a
complete history or forward feed. Supports [#154](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/154).
Source-use and retention review remains [#155](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/155).

## Why this is necessary

The now-merged [#161](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/161)
comparator reports which publisher *links* are visible, no longer visible,
or reappeared across genuine metadata-only snapshots. It does **not**
answer how much overlap survives between observed windows, whether a
measurement gap is long, or whether a journal's **provisional date hint**
changes between observations. These measurements are useful before
considering a forward observation cadence.

The separately bounded October 8 history study
([Actions 37729004599](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37729004599))
observed 72 current IDs on four English category first pages, including
68 local listing-date hints. Keyword-result navigation was **JavaScript
postback** pagination; no supported exhaustive dated catalogue was
established. That artifact retained aggregate counts, response hashes and
ID-set digests, not the individual IDs required here. **Do not fabricate
historical snapshots** or feed those aggregate findings into this tool.

## Inputs and design

The standalone module at scripts/vn_journal_forward_window_audit.py consumes
**two to 90 separately authorized, metadata-only observations** satisfying
the same strict ipr-vndj-listing-observation/1 contract as #161: four exact
category URLs, canonical numeric identity/permalink, unverified local date
hint or null, page response digests, UTC observation time and proof identity.

It calls the existing validator and set comparator before computing
anything. Wrong source, prose-bearing keys, duplicate run IDs, changed
canonical identities, out-of-order timestamps, unbounded listings and
fabricated completeness fail closed. No publisher HTTP or database I/O.
The command-line interface prints deterministic JSON to stdout.

For each sample, the audit reports visible distinct links, date-hint/null
counts, dates **after the journal's Vietnam-local observation day
(UTC+07:00)**, and same-observation-day hint clusters of three or more
links per listing for editorial spot-checking. Legitimate same-day articles
can create such a cluster: it is **not proof of clock contamination**.

For each adjacent pair, it calculates:

- Elapsed hours, optionally checked against an **analyst-supplied reference
  interval**. If omitted, no interval is assumed; the interval is neither
  a collection schedule nor a source reliability result.
- Per-listing and distinct four-page-union ID overlap, earlier-ID retention
  fraction, first-observed links, reappearing links and links no longer
  visible from the previously observed first-page windows.
- Exact ID references with conflicting **non-null listing date hints**
  in successive observations. Date drift is a review signal, not proof
  of a publisher revision or the correct publication date.
- Zero-overlap warnings when previously visible category/union links have
  completely turned over. This is not evidence that articles were deleted.

These observations can flag *risks* of missing new items, but **cannot
count or prove actual missed publications**. Recommendation/sidebar links
may repeat in unrelated categories; unchanged front pages do not prove
zero new releases; absent links do not mean deleted publisher articles.

## Offline use (only after genuine, separately permitted evidence exists)

~~~bash
python -m unittest tests.test_vn_journal_window_drift tests.test_vn_journal_forward_window_audit -v

python -m scripts.vn_journal_forward_window_audit \
  --reference-gap-hours 36 \
  /path/to/permitted-observation-01.json \
  /path/to/permitted-observation-02.json \
  /path/to/permitted-observation-03.json
~~~

Thirty-six hours is a **diagnostic comparison scenario only**, not an
approved fetch interval. No synthetic fixtures are treated as actual
journal observations.

Every audit report, **even with no warnings and 100% overlap**, explicitly
sets historical_completeness_proven, forward_capture_completeness_proven,
candidate_dates_verified, publisher_access_and_rights_validated_by_this_report,
eligible_for_shadow_activation and journal_day_zero_started to **false**.
It sets needs_independent_rights_review to **true**.

## Decisions still needed outside the tool

1. **Rights/access:** independent owner decision on factual metadata
   persistence, private source-text retention, quotations/translations,
   public use, robots/rate constraints and any publisher reply.
2. **Historical enumeration:** demonstrate permitted and supported dated
   category pagination or preserve the formal conclusion **bounded rolling
   window, historical completeness unproven**. Keyword-only postback
   navigation is not a complete historical interface.
3. **Forward trial:** after independent authorization, create an isolated
   journal-specific observation cadence with a missed-item audit, verified
   retrieval semantics, permissions checks and incident/refusal handling.
   This audit alone cannot justify or initiate that trial.
4. **Promotion:** a separately reviewed collector must enforce the rights
   and robots decisions at runtime and require an explicit owner activation.
   Only its own approved Day 0 may begin new 7/14/30 evaluations; no
   MPS/MOIT evidence clock can be inherited.

This change is independent of #163 (observation assembler), #166 (article
dates), #170 (disabled-source readiness) and #174 (site-clock defense).
No publisher requests, source bytes, collector activation, shadow writes,
production output, release publication or editorial approval were added.
