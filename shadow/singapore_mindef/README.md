# Singapore Desk — shadow scope

Shadow evaluation only. This desk collects nothing into production, appears in
no public count, and is not rendered by either site mode.

## Institution

**Singapore Ministry of Defence (MINDEF)**, `https://www.mindef.gov.sg`.
MINDEF publishes on behalf of itself and the Singapore Armed Forces, so a single
institution covers both in this source family.

## Included

One publication family: **official releases** under
`/news-and-events/latest-releases/<slug>/`. In practice that path carries five
kinds, distinguished by the slug's trailing token and recorded per document:

| Token | Kind |
|---|---|
| `nr` | news release |
| `speech` | speech |
| `fs` | fact sheet |
| `mq` | ministerial question / media reply |
| `pq` | parliamentary question |

Anything else on that path is recorded as `other` rather than guessed at.

## Excluded

Deliberately, and this is what the desk page must say plainly if it is ever
published: **this is not whole-of-government, not armed-forces-wide, and not
comprehensive Singapore defence coverage.** Not collected here:

* other ministries, including Foreign Affairs and Home Affairs
* Parliament's own Hansard record
* SAF unit pages, recruitment, and career content
* `cyberpioneer` / `PIONEER` magazine features
* social media, image galleries, and video
* tenders, procurement notices, and corporate pages
* anything requiring a login

## Mechanisms

**Listing.** The ministry's own `sitemap.xml`, which carries `<lastmod>` for
every URL. No pagination and no year-walking is required. `robots.txt` permits
everything except `/search`, and the runner re-reads it every run.

**Full body.** The item page itself. Bodies are HTML; no PDF extraction stage is
required for this family.

**Identity.** The canonical URL. Not a listing position, not a title.

**Publication date.** Parsed from the ministry's own slug (`15aug26-speech`),
never from `<lastmod>`. `lastmod` is a CMS modification time: a page edited later
would otherwise silently acquire a new publication date.

**Canonical URL.** As published, `https` on `www.mindef.gov.sg`, trailing slash
preserved. No query strings, no fragments, no tracking parameters.

**Duplicates.** First-writer-wins on canonical URL. Two documents that share a
title but differ in URL are distinct publications and both are kept — the same
rule that makes the Japan Joint Staff listing hazardous, applied before it can
bite here.

**Cadence.** Several documents per week, sustained across the sampled period.

**Expected-empty days.** A day with no new publication is `ok_no_publications`,
which is a success. It is never reported as, and never conflated with, a listing
or extraction failure.

**Robots recheck.** Every run re-reads `robots.txt` before discovery. A policy
that no longer permits the release path is an immediate fail-closed result, not
a warning, and no fetch follows it.

**Authority tier.** A — the ministry's own authorized public position.

## Known limitations

* One source family. Broad Singapore defence activity is not covered.
* Institutional output (scholarships, awards, parliamentary replies) is a large
  share of the volume; this is not an operational record.
* No historical backfill. The initial window is bounded and recent; collecting
  the 2013–2026 archive is a separate future decision.
* No translation, classification, significance scoring, or editorial analysis.
  The shadow phase proves retrieval, identity, preservation and reliability
  first.
