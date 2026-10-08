# Japan alternative official-source feasibility — 2026-10-08

**Status: candidate identification and bounded GitHub-runner egress test only. No
new source is approved, enabled, scheduled, archived or admitted to production.**

## Why this work matters

The Japan MOD shadow desk discovers dated ministry publications through the
official news and site-update RSS feeds but cannot fetch most HTML bodies using
the declared GitHub-hosted collector. The tracked 2026-08-26 assessment found
134 challenged HTML vs eight served PDF items within a 142-item news feed.
The independent Oct 7 Actions re-probe of Joint Staff/JMSDF/JASDF indexes also
observed Cloudflare challenges. Adding CSS selectors or raising the request
budget cannot repair an origin access restriction.

We should qualify other official **institutions**, without relabeling MOFA,
METI, or Cabinet material as MOD/Joint Staff reporting. A narrower legitimate
Japan Desk with independently declared institutional scopes is preferable to a
broad desk whose supposed coverage consists of unreadable links.

## Candidate A — Japan Ministry of Foreign Affairs (MOFA), English

- Official press-release archive:
  https://www.mofa.go.jp/press/release/202610_index.html
- Example dated original publication:
  https://www.mofa.go.jp/press/release/pressite_000001_02711.html
  (Oct 7, 2026, Japan–U.S. security and Indo-Pacific topics).
- Provenance: official MOFA publishing estate; an authorized diplomatic
  position, not a MOD or Joint Staff statement.
- Public web inspection: the October archive lists individually linked and
  dated English releases, and the example article has substantive English text.
  **This is not evidence of GitHub Actions collector reachability.**
- Source-use reference:
  https://www.mofa.go.jp/about/legalmatters.html (February 19, 2026).
  MOFA declares PDL1.0 for ordinary content unless otherwise indicated,
  requires URL/date attribution and disclosure of editing/translation, and
  identifies third-party material as a separate rights question.
- **Candidate verdict: prioritize a declared, read-only source-access pilot.**
  No permission to start bulk collection or republish images is inferred.

## Candidate B — Ministry of Economy, Trade and Industry (METI), English

- Official releases index:
  https://www.meti.go.jp/english/press/index.html
- Substantive sample:
  https://www.meti.go.jp/english/press/2026/0527_002.html
  (Japan–Italy economic security consultations, supply chain and critical
  mineral concerns).
- Source-use reference:
  https://www.meti.go.jp/english/other/terms_of_use.html (PDL1.0 default with
  provenance, edited-work and third-party-rights obligations; note that some
  English releases are provisional translations).
- Public web inspection: separate index and substantive article exist.
  Frequency and continuity of the English publishing stream are **unmeasured**;
  the homepage index examined in research displayed releases through July.
- **Candidate verdict: secondary bounded probe, not a production inclusion.**
  Separate economic-security scope from military operations.

## Excluded from this proof: Prime Minister's Office RSS

- Official note: https://japan.kantei.go.jp/rss.html
- Its RSS terms expressly disallow creating websites/email magazines from
  feed information and redistribution, even for noncommercial use.
- Do not use this RSS feed in the proposed collector. The site itself may have
  distinct terms, but those would need independent review; do not infer
  permission from public discoverability.

## Exact finite GitHub Actions probe

The workflow `japan_alternative_route_probe.yml` uses only
`scripts/probe_japan_alternative_official_routes.py` and Python stdlib.

1. Probe `/robots.txt` exactly once on `www.mofa.go.jp` and
   `www.meti.go.jp` using the real named IPR collector identity.
2. If a policy cannot be parsed, **make no article/index request** on that
   host. Obey disallows, do not follow redirects or solve challenges.
3. Make no more than one GET on each of four exact allowlisted pages; one
   worker, fixed delays, timeouts, zero retries and size ceilings.
4. Return only transport status, media type, body size, content SHA-256,
   visible character count and whether the expected headline marker is present.
   Do **not** print, archive, upload or publish page bodies.
5. Preserve a metadata-only, 90-day Actions artifact pinned by run ID.
   The probe does not import the scraper registry, open the production/shadow
   databases, alter configuration, authenticate, email or deploy.

**Success criterion for this stage:** both a listing and a linked original
article on a candidate host return permitted, directly served, substantive
HTML from the *same GitHub-hosted environment* the real collector will use.
This is an **access prerequisite**, not collection qualification. If one route
fails, leave that candidate disabled; do not seek alternate IPs, cookies,
headless challenge solvers, or re-hosted copies.

## After a positive observation (separate, future PR)

- Obtain real, bounded and properly attributed original-page fixtures from
  the approved route; review the robots/content-use terms again.
- Build a dedicated `SourceAdapter` with deterministic discovery, date
  provenance, canonical URL identity, full-body extraction and body/capture
  digests. Reject navigation-only excerpts and mutable revision ambiguity.
- Establish per-source publishing cadence and deduplication rules; maintain
  original English or Japanese text without inventing translations.
- Create the specific Japan shadow source declaration outside `desks/`,
  rather than prematurely changing `desks/registry.json` or writing a
  production manifest.
- Exercise the shadow runner and source-fidelity tests with append-only state;
  meet the existing review/owner promotion gates, then rehearse promotion on a
  disposable production DB and qualify native weekly-writer participation.

Until then, the Japan Desk remains access-constrained with limited MOD PDFs.
PR #202 (Japan AI research synthesis) is a **dated editorial bridge**, not an
ingestion or promotion path.

## Evidence provenance and open questions

Documentary public references were inspected on October 8, 2026. This review
records no GitHub-runner HTTP status for MOFA or METI until this PR's new
network-limited workflow executes successfully. If the workflow is skipped,
the correct reachability verdict remains **UNMEASURED**.

Open before source activation: first-party robots observations; actual 200
vs challenge status; date continuity from original articles rather than index
generation time; English translation status; source-use exclusions; official
publication frequency; change tracking; and extraction integrity.
