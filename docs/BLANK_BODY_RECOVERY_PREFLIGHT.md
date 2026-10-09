# Historical blank-body recovery preflight (no retrieval)

This private, read-only inventory is for human investigation of the blank
stored bodies identified in Issue #268, after the merged #280 queue audit and
the source-level #286 failure diagnosis. Its sole purpose is to separate
**stored historical extraction gaps** from plausible **current** adapter
regressions before anyone touches scraping code or models.

## Commands

Default: metadata-only article IDs and dates. No URLs or article bodies.

```sh
python scripts/audit_blank_body_recovery.py --db pla_watch.db \
  > /tmp/ipr-blank-body-preflight.json
```

A human reviewing source pages locally may **explicitly** opt into
URL locators, which have credentials, query and fragment stripped:

```sh
python scripts/audit_blank_body_recovery.py --db pla_watch.db \
  --include-review-urls > /tmp/ipr-blank-body-private-review.json
```

The second output contains publisher URLs and must remain on an
operator-controlled machine; **never log or commit it to GitHub Actions or
the public site.** Neither command makes a network request. The
script never retrieves articles or writes their content.

## What the date split means

The Global Times extractor's September 16, 2026 flow-template repair is
documented in `scraper/sources/global_times_mil.py` and
`tests/test_global_times_extraction.py`. The audit splits each stored,
China-Daily-eligible blank Global Times record into:

- `before_documented_fix_date` — scraped before September 16;
- `on_or_after_documented_fix_date` — scraped on/after September 16;
- `missing_scrape_date` — chronology cannot be established.

Non-Global-Times sources are `not_applicable`. This is merely a
**scrape date comparison**; it does not prove when a source page changed,
whether it can be retrieved today, whether a previous extractor bug caused
the blank field, or whether the existing stored row should be modified.
The audit also retains the original source slug, desk, published-date claim,
Daily queue category, processing reason and prior-attempt indicator. Entries
are capped at 100 to prevent an unbounded operator report.

For each candidate, a human should verify the source URL and original
publisher body, consider the appropriate source-use/provenance standards,
compare current adapter output against the old body and related-item rails,
then record an approved source-scoped recovery decision. **An empty stored
body is not an immutable media-only verdict.** Do not automatically restore
the body or reset retries in the production database.

The entire output is anchored to a local SHA-256 fingerprint of the
SQLite database and existing sidecars, checked before and after a
scratch-copy read. `publisher_page_rechecked=false`,
`extraction_recovery_validated=false`, `retry_authorized=false`,
`archive_rewrite_authorized=false`, and `model_calls=network_requests=writes=0`.
No live production state, source rights, model spending, Sunday Brief,
site deployment or editorial delivery is authorized by these receipts.

Dedicated CI runs synthetic tests, the unmodified #280 audit contracts,
and a read-only real-database report, reporting only source/date **counts**
without candidate URLs. Full repo CI/Chromium/output and DB-preservation
must pass before merging.
