# US DVIDS shadow egress pause — 2026-10-07

## Decision

Pause scheduled collection for the DVIDS USINDOPACOM-tagged shadow route.
The source is not being declared disallowed, broken, or unavailable to the
public. The narrower finding is that Indo-Pacific Record has not been able to
retrieve DVIDS's policy file reliably from GitHub Actions since the one
successful remote collection on 2026-09-19.

The public US Indo-Pacific desk remains `access_blocked`. DVIDS is a separate
Tier B reference route and never became production or public desk coverage.

## Evidence boundary

The only successful durable DVIDS collection remains:

- Actions run `35476931301`, manual `workflow_dispatch`, 2026-09-19;
- collector commit `3382d50496d086856f6cece4e95160e702e80659`;
- result `ok`, health `ok`, robots `allowed`, listing `ok`;
- 40 records inserted;
- state branch `shadow/us-indopacom` at `a36f67aee80e7520fb9fb401f69ca7c0ce112ce5`.

The next scheduled run, `35512831659` on 2026-09-20, failed before feed
discovery with:

`robots.txt returned HTTP 504`

Every scheduled run through 2026-10-07 also failed. There are 18 consecutive
scheduled failures covering logical dates 2026-09-20 through 2026-10-07.
Representative exact-log checks across that span:

| Date | Run | Observed failure |
|---|---:|---|
| 2026-09-20 | `35512831659` | `robots.txt returned HTTP 504` |
| 2026-09-29 | `36587444333` | `robots.txt returned HTTP 502` |
| 2026-10-03 | `37127768632` | `robots.txt returned HTTP 502` |
| 2026-10-06 | `37487510189` | `robots.txt returned HTTP 502` |
| 2026-10-07 | `37646622735` | `robots.txt returned HTTP 502` |

The latest run reached the collector at 2026-10-07T15:46:32Z and returned the
502 immediately. It never requested the DVIDS RSS feed. Publication was skipped.
The durable state branch therefore never advanced beyond the September 19
success.

Failed-run ledgers survive only in their 90-day Actions artifacts. They are not
imported into the durable state branch and do not advance the shadow clock.

## What this does and does not establish

It establishes that the current GitHub-hosted collection path cannot reliably
establish policy permission, because the very first request repeatedly receives
an upstream 5xx.

It does **not** establish that DVIDS has refused Indo-Pacific Record. The
collector has not observed a robots disallow or HTTP 403 from DVIDS in this
failure period. DVIDS's public site remains indexed and reachable to ordinary
web crawlers, and DVIDS's current FAQ continues to advertise RSS as a supported
way to receive content updates:

<https://www.dvidshub.net/about/faq>

The difference between "the publisher disallowed collection" and "this runner
cannot reliably retrieve the publisher's rules" is preserved deliberately.

The repository also has no evidence that the adapter's feed parsing, body
extraction, identity logic, or state handling caused these failures. None of
those paths executes before the policy request succeeds.

## Disposition

The daily `08:40 UTC` cron is removed.

`.github/workflows/us_shadow.yml` remains available only through
`workflow_dispatch`. A manual run is gated by the boolean
`owner_authorized_reprobe`, default false. This preserves a bounded diagnostic
path without leaving a known-broken daily job running.

No automatic retry is added. No browser user agent, proxy, alternate host,
policy bypass, or request-shaping workaround is authorized. The existing
collector identity and adapter remain unchanged in this pause because changing
them without evidence would mix diagnosis with speculation.

## Restart criteria

Scheduled collection may be reconsidered only after a separately authorized
manual re-probe establishes all of the following on the GitHub-hosted runner:

1. `robots.txt` returns a readable policy response;
2. the policy permits the DVIDS RSS and article paths for the declared
   collector identity;
3. the RSS feed is retrieved and parsed through the existing adapter;
4. at least one bounded run completes without access, fetch, extraction, or
   state-integrity failure, or returns an honest quiet-window success;
5. the owner explicitly authorizes restoring a schedule.

A single success would re-establish technical reachability, not qualification
or production coverage. Reliability would need to be earned again from that
point.

## Out of scope

No production DB/output changes, public desk-status change, state rewrite,
backfill, new source, alternate DVIDS endpoint, PACOM request, deployment, or
promotion is part of this incident disposition.
