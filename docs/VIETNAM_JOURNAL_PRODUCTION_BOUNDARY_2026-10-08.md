# Vietnam National Defence Journal: direct activation boundary

**October 8, 2026 — research-only safeguard, not authorization.**

Merged PR #170 verifies that the Vietnam National Defence Journal English
candidate remains disabled in its own shadow manifest, with no source-use
permissions. One further risk remains: a future change might wire the
journal straight into a production source manifest or GitHub Actions
workflow without first updating that disabled-state policy.

The new read-only tool, scripts/validate_vietnam_journal_production_boundary.py,
extends the existing validator to protect those direct configuration paths.

## Checks

**Public desk registry.** Vietnam must appear exactly once and remain
in research status, without a production manifest or production records.
The source remains Tier B military-journal commentary, not a Vietnamese
Ministry of National Defence directive.

**Production source manifests.** Every file at desks/*/manifest.json is
examined; no journal source slug, direct journal parser import,
publisher host, or journal shadow-folder alias is allowed. Even a
disabled journal reference in production manifests requires separate
human review rather than silently drifting into production configuration.

**Workflow definitions.** Every .github/workflows/*.yml and *.yaml is
inspected for those exact journal-related identifiers. This covers
both scheduled and manually dispatched workflows. Existing Vietnam
ministry workflows are not implicated: generic terms such as Vietnam,
journal, ministry and defence are intentionally *not* blocked.

## Explicit limitations

This is a bounded, static, direct-reference check: it does not prove
the absence of indirect dynamic imports, encoded publisher URLs,
out-of-band processes, workflows in other branches or remote services.
It is not a security proof, a publisher permission grant or a crawler
runtime authorization. The deliberately strict token match can even
reject a harmless workflow comment that names a journal source import;
an owner-reviewed promotion may replace this blanket research hold
with a narrower governed activation contract.

The report states that direct workflow and production-manifest bindings
were absent, identifies how many files were checked and keeps explicit
denials on journal Day 0, authorized collection, text retention and
historical completeness. It calls the existing frozen source-rights
validator first.

## Run offline

~~~bash
python -m scripts.validate_vietnam_journal_production_boundary
python -m unittest tests.test_vietnam_journal_production_boundary -v
~~~

Synthetic mutation tests inject (a) duplicate or promoted Vietnam desk
registry declarations; (b) journal aliases in production manifests;
(c) manual and scheduled journal workflow references; (d) missing
workflow/manifest inventories; and (e) unauthorized source/rights flags.

No publisher requests, artifact persistence, network access,
production database/output changes, collector schedules or source
activation result.

Related: PR #170 disabled-source readiness; PR #174 historical
first-page-only verdict and live-clock hint protection; PR #166
article-specific date reconciliation. Independent PRs #163 and #176
add offline observation assembly and forward-window comparison.

Publisher-use decisions remain open in Issue #155 and historical
coverage remains incomplete as documented in Issue #154. A future
collector must have independently approved rights, request identity,
transport/robots gate, persistence policy, safety tests and explicit
owner activation.
