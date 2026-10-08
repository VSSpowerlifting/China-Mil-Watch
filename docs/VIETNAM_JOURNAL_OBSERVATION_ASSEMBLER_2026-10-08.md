# National Defence Journal: assemble an offline metadata-only observation

**Status:** standalone, pure-function engineering. No journal HTTP request,
source-content retention, shadow/production collector, Actions workflow,
publication, database write, or site output change.

This is the producer half of the **offline evidence contract** in
`docs/VIETNAM_JOURNAL_WINDOW_DRIFT_2026-10-08.md` (PR #161). It converts
four separately supplied `ListingObservation` values from
`scraper.sources.vn_journal_listing.parse_category_html` into a small
JSON-compatible packet suitable for
`scripts.vn_journal_window_drift.validate_observation` and
`compare_observations`. The script performs **no network or file I/O** and
does not supply the date, official HTTP response bytes or their digests.

## Explicit data flow

1. **Only after separate approval** of a bounded, robots-gated measurement,
   a trusted operator obtains the same four specifically allowed desktop
   category pages. This PR does not implement that operation.
2. In memory only, that authorized operator feeds each page to the already
   merged strict offline parser `parse_category_html`. Preserve the SHA-256
   digest of the **actual response bytes** and an externally measured UTC
   timestamp and run identifier. Do not log or retain publisher page bodies.
3. Call `make_observation(observations, response_sha256_by_category=...,
   observed_at=..., observation_id=...)` with the four parser values and
   their genuine response digests. No inputs are inferred from article IDs.
4. The output contains only `source_identity`, `canonical_url`, and
   `date_hint` per article, plus exact category URLs, source/run provenance,
   response hashes and explicit **false** declarations for body retention,
   pagination proof and historical completeness.
5. A separately approved retention decision can govern whether this
   **metadata-only** observation is persisted. The function itself writes
   nothing. Two or more such genuine snapshots can be compared by PR #161's
   offline comparator.

Do **not** use synthetic fixture IDs and digests as real findings. Neither
source metadata, successful parsing, nor working pagination permits
republishing journal prose or images. Full-text permission remains open in
[#155](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/155).
Historical-pagination evidence remains open in
[#154](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/154).

## Failure modes and guarantees

- Exactly four distinct, recognized English category observations and four
  caller-supplied SHA-256 digests must be supplied.
- Each candidate must retain its observed source category and an explicitly
  **unverified** article date. Disputed same-ID URLs and date hints fail
  closed in the shared validator.
- Unknown extra fields (including body, title, snippets and publisher HTML)
  cannot enter output; the serializer whitelists only three candidate fields.
- Incomplete/ambiguous source observation, stale or invented pagination
  claims, malformed dates/IDs, missing provenance and non-UTC times fail
  validation.
- Stable ordering is by the governed four-category order, independent of
  the list supplied by the caller.
- An observation remains a bounded listing **sample**, not a proven full
  historical catalogue, forward-cadence qualification, a source use-rights
  ruling, or authorization to collect.

## Offline tests

```bash
python -m unittest tests.test_vn_journal_window_drift tests.test_vn_journal_observation -v
```

Synthetic tests assert no leakage of tempting body/title fields, exact
provenance boundaries, deterministic round trips, strict digest and identity
validation, chronology semantics, and compatibility with the downstream
comparison contract.

This is intentionally a **stacked PR** based on the exact head of #161.
Once #161 is merged, retarget this PR to `main` and re-run full offline CI;
do not merge the producer before its validated downstream contract.
