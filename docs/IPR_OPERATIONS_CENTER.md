# Internal Operations Center — offline evidence snapshot

Status: Phase 1, read-only local reporting. **Not a public site page, live
Actions dashboard, source admission decision, or editorial release gate.**

## Run

From the repository root, with the normal Python environment installed:

    python scripts/operations_center.py --html /tmp/ipr-operations.html --json /tmp/ipr-operations.json

Open the HTML file locally. Or omit both output flags to print JSON to stdout:

    python scripts/operations_center.py

A reproducible historical display date can be supplied as
`--as-of YYYY-MM-DD`. It does not time-travel the database or shadow
sources: the database remains whatever was available in the checkout, and
`production_report_generated_at` identifies the report's creation. This
flag exists for deterministic interpretation of the committed daily marker.

The tool refuses to overwrite an existing report or write anywhere inside
the repository (including `output/`, source code or workflows). Write HTML/JSON
to `/tmp` or another existing directory outside the checkout. It does not access the
network, start a collector, publish a Brief, send email, import shadow rows,
or write the tracked database. Production DB reads use
`scripts.reconcile_db.read_only` through the existing
`scripts.source_health_report.build_report`, avoiding WAL sidecars.

## What the display actually means

**Declared desks:** sourced from `desks/registry.json` via
`core.desk_registry.load_registry()`. Their statuses are not
inferred from PRs, source counts, or completed workflow checks. Only collecting
desks have production counts.

**Production source health:** reuse the existing per-source report computed
from the tracked production SQLite and its source manifests. A silence verdict
is a cadence-relative observation, not a proof that a ministry stopped
publishing. Each count is source-attributed, not a claim of country-wide
coverage, uniqueness across publishers, or editorial publication readiness.
The most recent per-source attempt's recorded `is_failure` flag is shown
separately from the latest article and last success, because a recent article
must never hide a failed latest attempt. Missing run history is `not observed`,
not a successful run. Failed latest attempts, overdue silence and unusable
adapters generate independent review reasons; none qualifies a desk for promotion.

**Source review flags in HTML:** a front-of-page table presents every
recorded warning with its desk, source and reason, including an unsuccessful
latest source attempt even when its most recent article is recent. A separate
table lists enabled production sources with **no latest-run evidence**. That
unknown condition is *not* labeled a failed run or a successful run. A zero
warning count never proves completeness, collection continuity, source reuse
rights, or editorial readiness. Both tables derive from the same read-only
JSON snapshot; no new data authority is introduced.

**Shadow source families:** a deterministic inventory of
`shadow/*/manifest.json` files. These are source-family configurations,
not independently validated running desks. A manifest with
`enabled: true` only expresses shadow-runner configuration; it never
certifies scheduled GitHub Actions success, state-branch continuity, ingestion,
source permissions, human checkpoint reviews, or production admission. A
historical Singapore shadow manifest remains visible but is explicitly labeled
historical rather than a second collecting desk. A source family outside the
public registry is not silently added as a promoted desk; its public-roster
status is shown explicitly as `not in public roster`. Source-family identifiers
are never guessed into the nearest similarly named country desk.

**Daily marker:** reads the committed
`.github/state/last_daily_run_date.txt` if present. This local marker is
not a live GitHub Actions health check, and cannot certify same-Sunday Briefs
readiness or the completeness of an archive run.

**Editorial/rights safety:** every snapshot expressly denies publication,
promotion and editor-delivery authorization. No source text, draft manuscript,
human-review attestation or shadow record payload is included.

## Verification

    python -m unittest tests.test_operations_center -v

The tests cover missing/misassigned source observations, duplicate source
identity, untrusted shadow flags, malformed manifests, HTML text escaping,
marker semantics, protected output directories, and the tracked DB's read-only
sidecar contract. The full repository suite and rendered-output validator
remain the merge gate.

## Phase 2 (deliberately not included)

A **separate, owner-reviewed** phase can join official GitHub Actions API
run/job status to immutable state-branch and checkpoint receipts. It must
distinguish scheduled success, skipped/no-op jobs, manual recovery, stale
branches, and cross-source publication gaps. That requires explicitly
versioned provenance evidence, time-zone-aware collection slots, and new
fixtures; no generic green icon should appear merely because a workflow
completed. Only after this can an internal alert digest be considered.
