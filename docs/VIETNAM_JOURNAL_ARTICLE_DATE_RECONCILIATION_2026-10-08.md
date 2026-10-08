# Vietnam National Defence Journal — offline date reconciliation

**Status:** parser-integrity candidate; does not capture, publish, archive,
activate, schedule, or authorize collection or reuse.

The journal source was registered **disabled** (#129). Offline desktop article
parsing (#138) and four-category listing discovery (#143) are merged, but they
measure different claims:

- A category page may contain a **provisional article date hint**. The hint
  might refer to a nearby displayed date, sidebar link, recommendation, or an
  older item; it is *not* verified against the linked article.
- The strict offline desktop article parser reads an **article-specific
  publication stamp** from its own verified DOM path. The parser result is
  stronger evidence of the publisher's current article date than a listing
  hint, but still requires editorial verification before making a public
  archival claim. It is not evidence of when the publisher *first* released
  an edited article.

`scraper/sources/vn_journal_reconcile.py` links these two evidence layers
without collapsing them or storing copyrighted prose.

## API

`reconcile_article(four_listing_observations, offline_article)`

Arguments must be results of `vn_journal_listing.parse_category_html` and
`vn_journal_article.parse_desktop_article`, respectively. Both operate on
already-supplied HTML in memory; **this module never accepts an HTTP URL to
fetch** or opens a database. The caller must independently authorize any
source access and must not persist any full-text bytes without a separate
rights decision.

For each matched numeric ID, the reconciliation validates:

1. The article-specific source identity, canonical desktop permalink, English
   language, exact journal publisher and source slug.
2. The article page's original printed timestamp against its day-precision
   parsed date (no UTC conversion, no inferred time of release).
3. The four known category observations, with no duplicates, fabricated
   pagination/completeness flags, ambiguous aliases, or accidental
   verified-date claims.
4. Exact URL and identity consistency across repeated discovery links
   (including recommendations/sidebar items from other category pages).
5. The article's date versus a listing hint, preserving **both** when they
   disagree and setting an explicit editorial-review flag.

Possible statuses:

| Status | Interpretation |
|---|---|
| `matches_article_date` | Locally observed hint agrees with article-specific stamp; machine-consistent, still not human-verified |
| `date_hint_disagrees` | Listing and article stamp differ; both dates disclosed, editorial review required |
| `no_listing_date_hint` | Article present in observed listing, but no attributable local date hint |
| `not_visible_in_observed_pages` | Article did not appear on the supplied four pages; **not** publisher deletion or proof of missing article |

The returned result is a fixed metadata-only dict: ID, canonical URL, source
classification, current article-page date and its basis, listing hint/status,
listing-page provenance, and explicit **false** rights/completeness/publication
flags. No headline, article prose, captions, author credit, page HTML, or
other source contents cross this interface.

## Run synthetic integration tests

```bash
python -m unittest tests.test_vn_journal_reconcile -v
```

The tests exercise both genuine *offline parser classes* on synthetic
publisher-layout HTML, including conflicting dates, null hints, missing
listing membership, inconsistent canonical IDs, false reuse claims, and
accidental source-content leakage.

## Exact operational limits

- A matching listing hint is **not independent corroboration**: both fields
  originate from the same publisher website.
- The source is a **military journal publication**, not a formal Vietnam
  Ministry of National Defence decree, directive, or announcement.
- A source article absent from four visible category pages might still
  exist; no historical completeness is established.
- Real page access, bounded robots-gated proofs, metadata retention rights
  and publication permissions are separate owner decisions in issues
  [#154](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/154)
  and [#155](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/155).
- This is intentionally independent of the metadata snapshot PRs #161/#163.
  It does not modify either comparator's schemas, producer, or evidence.

**Merge does not activate collection.** No new Day 0 / 7 / 14 / 30 clock
begins from implementing a parser or reconciliation helper.
