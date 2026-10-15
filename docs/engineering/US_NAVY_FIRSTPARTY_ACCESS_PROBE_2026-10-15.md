# U.S. Desk: first-party Navy access feasibility — 15 October 2026

## Objective
Separate the U.S. Indo-Pacific Reference Desk from the paused DVIDS media-service family and test whether distinct **first-party U.S. institutional news listings** can supply independently sourced, regularly updated U.S. reference streams:

| Source family | Official institution | Exact research endpoint |
|---|---|---|
| Commander, U.S. Seventh Fleet | U.S. Navy, Seventh Fleet public affairs | https://www.c7f.navy.mil/Media/News/ |
| Commander, U.S. Pacific Fleet | U.S. Navy, Pacific Fleet | https://www.cpf.navy.mil/Newsroom/News/ |
| U.S.-China Economic and Security Review Commission | Congressional commission (not military-command reporting) | https://www.uscc.gov/press-releases |

The [Seventh Fleet institutional listing](https://www.c7f.navy.mil/Media/News/) publishes dated regional maritime and allied exercise releases; the [Pacific Fleet listing](https://www.cpf.navy.mil/Newsroom/News/) publishes its own naval news. They are **not** official statements of the separate U.S. Pacific Command headquarters, and a Seventh Fleet-hosted piece may be authored by a subordinate unit. No comprehensive DoD, State Department, White House or PACOM press-release feed is implied.

## Access problem
- `www.pacom.mil` direct project-runner robots access previously returned HTTP 403. The separate DVIDS USINDOPACOM-tagged feed was paused after 18 scheduled robots 502/504 failures following the one genuine September 19 remote collection. Neither is resolved by substituting a naval host.
- Before building another crawler, determine whether a **genuine GitHub Actions runner** can fetch readable `robots.txt` on each distinct official Navy host, interpret the rules for the declared agent, and retrieve the **one official listing page only if explicitly permitted**.
- A web-indexed government listing or a browser-readable page is not proof that GitHub Actions runners receive a permitted policy response.

## What this PR actually does
`scripts/probe_us_navy_first_party_access.py` is a strictly bounded, host-pinned, policy-first **diagnostic only**. It makes at most **four HTTP GET requests across three independent U.S. institutional domains**: one `robots.txt` per official host, followed by at most one news listing GET per host **only** when the obtained plain-text robots policy allows it. Strict user agent, 12-second timeout, no redirects, no proxy, no challenge/bypass, no retry, size bounds and fixed HTTPS paths. A 403, script-only response, unreadable robots, 5xx or timeout is a no-listing HOLD, not a publisher prohibition or an invented success.

The owning PR executes a one-off bounded diagnostic with a synthetic offline test suite; after merge, `workflow_dispatch` remains manual-only and requires `owner_authorized_readonly_probe=true`. No automatic cron, feed parsing, article collection, source body, Pages deployment, state Git ref, private Git transfer, database write, human approval, publication, or claimed Day 0.

The JSON receipt distinguishes `robots_policy` and `listing_reachable` from `collection_authorized=false` and `source_day_qualified=false` in every case. An accessible listing means **candidate technical reachability only**. Article extraction, publisher rights, exact source history, version retention, duplication against PACOM releases, day-by-day reliability and editorial publication scope must be separately implemented and tested before enabling a scheduled collector.

## Release sequence
1. Observe the actual policy/host results from this PR's single source-probe job, not a web search cache. If either host returns 403/5xx/unusable robots, do not fetch the listing or treat a site indexed by third parties as permission to scrape.
2. For any fully policy-allowed and reachable host, commission a distinct *shadow* adapter, first-party publisher/issuer attribution, exact article IDs/dates, no-silent-drop logs, and private original retention review. Keep the source authority Tier B unless an article is a genuine command-issued statement. DO NOT reuse DVIDS's historical day count.
3. After actual source verification, use the owner's narrow factual-metadata publication policy as a **template**, subject to explicit source-family scope review, for official URL/date/issuer-only reference updates. Do not automatically publish body text, photos, translations or analysis.
4. Leave all U.S. public corpus counts unchanged until the full production admission pipeline is proven. The separate nine-PACOM-link bounded public directory is developed under PR #671.

This avoids using a generic DVIDS tag as a substitute for original U.S. defense command publications.

## October 15 first genuine runner observation
The initial GitHub Actions source-policy probe on `www.c7f.navy.mil` and `www.cpf.navy.mil` returned HTTP **403 for both hosts' `robots.txt`**. Neither listing was requested; no shadow success day can be counted. A separate first-party USCC press-release listing is now added to the canary, as a distinct congressional commission source with China/economic security scope, not as a replacement host for previously blocked Navy content. The next run must report its own authentic robots result before any collector work.
