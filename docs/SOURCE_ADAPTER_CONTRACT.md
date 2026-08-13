# Source adapter contract

Defined in `core/collection/contract.py`. Every source presents four operations:

```
discover(window) -> DiscoveryResult     candidate references in the window
fetch(reference) -> CaptureResult       bytes plus provenance
extract(capture) -> ExtractionResult    normalized documents
healthcheck()    -> SourceHealthResult  offline, configuration-level
```

`collect(window)` runs the three in order and returns
`(SourceRunResult, [ExtractedDocument])`.

## Rules

1. **Do not raise for expected failures.** A timeout, a 404 listing, a parser
   that finds nothing are *results* with a status naming them. Raising is for
   genuine programming errors, and even then the pipeline converts it to
   `adapter_error` rather than letting one source abort the run.
2. **No network in unit tests.** Nothing in the contract module performs I/O.
   Adapters take their dependencies by construction, so a contract test hands
   one saved fixture HTML and asserts on the structured outcome.
3. **`healthcheck()` is offline.** A healthcheck that hits the network cannot
   run in the suite, and one that cannot run in the suite does not get run.
4. **Stubs declare themselves.** A scraper class with `IS_STUB = True` reports
   `not_implemented`, never "published nothing today".
5. **Error detail is bounded and single-line.** Scraped pages are untrusted
   input and their content can reach exception messages. `_brief()` caps at 200
   characters and collapses whitespace. No stack traces on any public surface.

## Statuses

`core/collection/status.py`. Each value declares whether it is a failure.

**Success** — `ok`, `ok_no_publications`, `ok_all_duplicates`, `ok_all_filtered`.
**Neither** — `skipped_disabled`, `not_implemented`.
**Failure** — `listing_failure`, `auth_failure`, `timeout`,
`disallowed_redirect`, `unexpected_content_type`, `oversized_response`,
`fetch_failure`, `extraction_failure`, `analysis_failure`, `adapter_error`,
`unknown_source`.

The distinction that matters: **`ok_no_publications` is healthy; the failures
are not.** Both return zero documents. Before this existed they were the same
bare empty list, which is how MOD China went silent for four weeks without a
failed run.

`not_implemented` and `skipped_disabled` are excluded from failures on purpose.
Both are deliberate, acknowledged configuration states; treating them as
failures would make every run degraded for as long as Xinhua stays a stub.

Writing an unregistered status raises — `SourceRunResult.__post_init__` calls
`status.validate()`.

## Legacy wrapper

`adapters/legacy.py` wraps the existing `BaseScraper` subclasses. It calls the
same methods in the same order as `BaseScraper.scrape()`:

```
urls = get_article_urls()
for url in urls:
    html = fetch(url)
    if not html: continue
    article = parse_article(url, html)
    if article: keep it
```

The parsers are unchanged. `ExtractedDocument.raw` holds the parser's dict
verbatim and `as_article_dict()` returns a copy of it, so normalization, dedup
and the keyword filter receive byte-identical input to what they receive today —
including which keys are *absent*, which is not the same as present-and-`None`.

### How zero is classified

| Situation | Status |
|---|---|
| Listing returned URLs, documents extracted | `ok` |
| Listing reached, no URLs, no failed fetches | `ok_no_publications` |
| Listing reached, no URLs, failed fetches recorded | `listing_failure` |
| Listing raised | `listing_failure` |
| URLs found, none fetched | `fetch_failure` |
| Pages fetched, none parsed | `extraction_failure` |
| Adapter declares `IS_STUB` | `not_implemented` |
| `enabled: false` in the manifest | `skipped_disabled` |

After dedup and filtering the pipeline refines a successful-but-empty result to
`ok_all_duplicates` or `ok_all_filtered` — both healthy, both distinct from
silence.

## Aggregate run status

`core/collection/health.aggregate_status()`:

- any collectible source failed → **degraded**
- all collectible sources failed → **failed**
- no collectible sources at all → **degraded**
- otherwise → **completed**

One required source failing degrades the run even when every other source
succeeded. The pipeline maps this onto `scrape_runs.status`, alongside the
existing analysis-failure logic.

## Writing a new adapter

Subclass `SourceAdapter`, implement the four methods, return statuses rather
than raising, and add fixture-driven tests to `tests/test_adapter_contract.py`.
Register it in the desk manifest's `adapter` field — never by importing it into
`core/` or `pipeline.py`.
