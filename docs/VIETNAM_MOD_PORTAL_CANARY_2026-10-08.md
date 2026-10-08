# Vietnam Ministry of National Defence — OFFLINE URL canary (October 8, 2026)

## Scope and actual observation

Issue #236 calls for source-first coverage of the Ministry of National Defence. This milestone implements only a fail-closed offline URL-identity gate for the English Defence Relations family of the official MOD portal, not an active collector.

Publicly indexed first-party article examples include:
- [General Phan Van Giang receives Japanese Ambassador to Vietnam](https://mod.gov.vn/en/detail?current=true&urile=wcm%3Apath%3A%2Fmod%2Fsa-mod-en%2Fsa-en-news%2Fsa-en-news-rela%2Fgeneral-phan-van-giang-receives-japanese-ambassador-to-vietnam-2026), portal-displayed label 15:18 | 07/10/2026.
- [Vietnam - Japan defense cooperation yields substantive results](https://mod.gov.vn/en/detail?current=true&urile=wcm%3Apath%3A%2Fmod%2Fsa-mod-en%2Fsa-en-news%2Fsa-en-news-rela%2Fvietnam-japan-defense-cooperation-yields-substantive-results), portal-displayed label 17:22 | 05/29/2026.

Those indexed URLs and timestamps are examples for deterministic offline tests, not independently downloaded article captures, official run receipts, or evidence for the October 4–10, 2026 reporting week.

Access attempts from the research environment on October 8 gave HTTP 403 for the ministry news listing, a timeout for one direct article and an empty fetched page for another. The site's robots/terms could not be established from those checks. A search excerpt does not substitute for direct publisher access or source-use authorization. None of the above justifies a live schedule.

## URL identity and failure behavior

The MOD English portal also uses WebSphere /en/news/!ut/p/... widget/navigation routes. These can carry mutable session, layout, encoded path, pagination and tracking information. Never hash a full widget link as an article identifier or silently remove parameters to manufacture a stable source ID.

The script scripts/review_vietnam_mod_portal_links.py accepts only HTTPS, the exact host mod.gov.vn, the exact route /en/detail, and exactly two query keys, current=true and a single urile WCM content path under:

    wcm:path:/mod/sa-mod-en/sa-en-news/sa-en-news-rela/<stable-slug>

Percent-encoded and unescaped equivalents of the same complete path yield the same provisional identity mod-en-defrel:<stable-slug>. Unknown query keys, doubled WCM keys, alternate hosts, fragments, changed source families, path traversal and nested encoding fail closed. These checks intentionally cover ONLY English Defence Relations. Vietnamese-language and other category surfaces need separate source-specific analysis.

The WCM path is an **identity hypothesis only**. Before capture/collector code is added, a reviewer must prove a first-party article actually resolves, that its identity remains stable across reloads, and that the page's title, visible publication date, issuing authority/byline and extracted content region match. A correctly shaped URL could still be stale, removed, syndicated, redirected or challenged.

## Local offline operator triage

Create a manually prepared JSON file with the following content (illustrative, NOT approved):

    {
      "schema": "vn-mod-en-manual-url-observations/1",
      "items": [{
        "article_url": "https://mod.gov.vn/en/detail?current=true&urile=wcm%3Apath%3A%2Fmod%2Fsa-mod-en%2Fsa-en-news%2Fsa-en-news-rela%2Fgeneral-phan-van-giang-receives-japanese-ambassador-to-vietnam-2026",
        "printed_title": "General Phan Van Giang receives Japanese Ambassador to Vietnam",
        "printed_timestamp": "15:18 | 07/10/2026"
      }]
    }

Execute locally with a trusted, manually prepared observation file:

    python -m scripts.review_vietnam_mod_portal_links --input /tmp/mod-observations.json --out /tmp/mod-unverified-canary.json

The output refuses overwrites and checkout writes. It contains no article text and explicitly marks each item as having NO verified first-party page, redirect chain, robots/terms review, verified article body, source-use authorization, model eligibility, publication approval, production admission or archive commit. Operator-supplied titles/dates are unverified observations. No ministry silence or current-week source coverage is asserted.

## Separate owner-approved follow-on gates

1. Manual access, rights and provenance review: inspect robots/terms, bounded first-party access, status codes and redirects. Do not bypass 403 or challenge pages. Distinguish ministry original text from credited news-agency reports.
2. Legally reusable local HTML truth table: confirm listing and article title/date/issuer/content region, denial/template/redirect/partial-body false positives, stable identity, pagination and late-arriving publication dates.
3. New isolated MOD shadow state only after gate 1–2: immutable source/capture chain with its own collection clock. Never reuse MPS or MOIT clocks, records or hashes.
4. Day 7/14/30 integrity review, exact-version private research synopsis and independent editorial/source-rights decisions before admitting any MOD input to the shared Sunday writer.

The verified October 5 MPS records remain this reporting week's only Vietnam private-model research candidates. This milestone adds **zero** eligible MOD records and performs no website fetches, GitHub Actions scheduled collection, model call, email or publication.
