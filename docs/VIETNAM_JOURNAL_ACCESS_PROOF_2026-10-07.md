# National Defence Journal — exact-head access and extraction feasibility

**Stage:** one-shot, disposable GitHub Actions research. This packet cannot
activate a collector, start a shadow clock or produce public records.

The new source itself is registered under
`shadow/vietnam_journal/manifest.json` by PR #129. This proof PR deliberately
targets that branch, not main. It can merge **only after** #129 has passed its
own CI and been integrated by the owner; either way the one-shot workflow must
be removed or disabled after review and should never become a scheduled job.

## Boundaries

Uses the repository's exact `IndoPacificRecord-ShadowCollector/0.1`
identity. One GitHub Actions runner, exact immutable PR head, no credentials
and no persisted checkout token. No redirects, browser impersonation, proxy,
cookies across requests, retries, forced access challenge, guessed article
URLs, PDF fetch or pagination.

Maximum six GET requests:

| Host | Gate 1 | Gate 2 | Gate 3 |
| --- | --- | --- | --- |
| `tapchiqptd.vn` | `/robots.txt` | `/en/default.html` | known desktop article 26936 |
| `m.tapchiqptd.vn` | `/robots.txt` | `/en` | same article 26936 in mobile URL form |

A host's later requests happen **only** when its own robots policy is
readable and explicitly permits both paths. Missing policy, HTML challenge,
invalid Crawl-delay, policy refusal, redirect, non-200 response or unknown
structure stops that host. A mobile response is *not* used to bypass a
desktop refusal. The sample article is fetched only if its identity actually
appears in that host's allowed listing. No other article is fetched.

Each response is capped at 512,000 bytes with a 20-second timeout; crawler
follows the maximum of two seconds or the site's Crawl-delay, up to 120
seconds. Response material is held in process memory only and dropped after
the probe. The retained 90-day artifact is **JSON metadata only**: HTTP
status/content type, payload hashes and lengths, robots gate results, number
of unique candidate article IDs, date candidate(s), headline hash and CSS
selector text-length diagnostics. It does NOT contain captured article text,
HTML, screenshots, response cookies or rendered excerpts.

The CSS selector diagnostics can help an engineer identify a candidate
article-body container, but they do **not** assert a valid extractor.
Likewise, matching title hashes and printed dates do not prove completeness
or legal permission to republish the bodies. Real fixture capture would need
a separate approved reuse/retention decision.

## Interpretation

| Probe result | Consequence |
| --- | --- |
| Robots unreadable or disallowing | Do not implement automated collection on that host |
| Listing blocked or cannot identify article 26936 | No verified discovery path; hold source disabled |
| Sample accessible, no plausible article-body selector | Can investigate publisher-supported HTML structure; not collectible yet |
| Both hosts accessible and metadata agrees | Good architecture evidence, not sufficient to activate shadow collection |
| Main accessible but mobile blocked (or reverse) | Treat each independently; no bypass/fallback authorization |

No production DB, output, desk status, source activation, existing Vietnam
ministry work, rights position or Day 7/14/30 checkpoint is changed.

Review the artifact for exact run/commit evidence, describe the measured
robots and article outcomes, and close the disposable probe PR unmerged once
findings have been copied to a **separate** reviewed research/collector PR.
Do not treat a workflow's green status as evidence that the website answered:
all blocked paths can produce an honest successful diagnostic run.
