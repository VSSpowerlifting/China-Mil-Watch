# USCC first-party official metadata collection — October 15, 2026

## Source and identity
The [U.S.-China Economic and Security Review Commission](https://www.uscc.gov/) is a **U.S. legislative-branch commission**, not U.S. Pacific Command, a military service, the Defense Department or an independent verification of its own assessments.

Its [first-party press-release listing](https://www.uscc.gov/press-releases) publishes dated announcements on China–U.S. security, technology, economics and Indo-Pacific policy. Examples displayed as of October 15, 2026 include the September 22 report announcement on threats to trans-Pacific undersea cables and a September 21 announcement of research on China–Russia military cooperation.

At 20:05 UTC October 15, a bounded GitHub Actions runner **actually fetched a readable robots policy permitting `/press-releases`**, and received the publisher's own listing HTML. In the same run, the distinct U.S. Seventh Fleet and Pacific Fleet hosts returned HTTP 403 for their robots files and were not fetched further. This independent permitted USCC host is the first eligible technical access path for a new U.S. family; it is **not** a workaround host for either Navy command.

## What is collected

`scripts/collect_uscc_press_metadata.py` reads the official `robots.txt` for a declared IPR user agent each attempt and contacts precisely the **one listing** if policy permits it. No navigation to individual article bodies, no pagination/backfill, no search, no tags, no proxies, redirects, retries, alternate identity or challenge-solving.

It extracts a bounded (1–75) set of dated first-party link **cards**. Each must provide a stable official `/press-releases/<slug>` URL, a valid independently associated `MM/DD/YYYY` (or `YYYY-MM-DD`) listing date, a unique identity, an authenticated official publisher host and exact fixed issuer. Missing dates, fabricated IDs, conflicting duplicate values, future-dated rows, changed layouts, disallowed robots or unavailable access produce a HOLD. Only these six fields are stored per row:

- `source_identity`, `canonical_official_url`, `publisher_posted_date`;
- `official_issuer`, `official_publisher`, `publisher_listing_url`.

The collection receipt additionally hashes the whole ephemeral listing HTML (`official_listing_sha256`), dates the genuine UTC observation, preserves the count of *visible dated listing cards*, and explicitly disclaims complete coverage, original content retention, publication, data-model approval or production admission. **The HTML itself, headlines, articles, photographs, documents, excerpts, translations, summaries and analysis are NOT copied.** A listing digest does not restore those original bytes if the government removes them.

## Genuine scheduled evidence
The minimal append-only public `shadow/uscc-press` branch contains only the scoped README and `observations/YYYY-MM-DD.json` metadata receipts. Scheduled collector calls run daily at 11:20 UTC; manual dispatch requires `owner_authorized_source_collection=true`. The workflow runs positive and negative synthetic tests, validates source access before any Git mutation, then writes **only** an observed UTC date's metadata JSON, refusing different bytes for an existing date and never force-pushing. It does not merge to `main`, modify `pla_watch.db`, touch public Pages or count a source success based solely on a green CI test.

The first actual post-merge run is the first possible remote collecting day and must be inspected for valid collection, observed rows, exact state-branch Git ref and no failed policy fetch. Passing one source-observation run doesn't establish complete listing history or every-day reliability. Scheduled gaps remain gaps.

## Next release boundary
When genuine observation history exists, build an **idempotent USCC source metadata importer**, separate from the command-derived PACOM static links, into a typed production-only metadata table. The owner's narrow standing principle of verified URL/date/issuer-only publication can then govern a separately tested U.S. congressional commission release path; any source-specific extensions require review. A guarded publisher should read only admitted official metadata and publish **only** `us-indopacific.html` after exact source-version and collision checks. Never silently classify USCC announcements as PACOM orders or count them as IPR-authored analysis.

The public U.S. Desk's existing nine PACOM official outbound URLs and the factual `access_blocked` status of direct PACOM collection must remain intact during USCC activation.
