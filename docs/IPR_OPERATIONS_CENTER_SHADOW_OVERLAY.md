# IPR Operations Center — optional Phase 2 evidence overlay

**Private/offline evidence only.** This is an integration layer for the *separately reviewed* Phase 1 Operations Center [PR #249](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/249), shadow source map [#257](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/257), and slot candidate report [#259](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/259). It is not a GitHub Actions API client or production health authority.

## Produce the two kinds of input

From an up-to-date local repository checkout:

```sh
python scripts/audit_shadow_workflow_bindings.py > /tmp/ipr-bindings-audit.json
```

The resulting JSON inventories **all** shadow source families, even those without scheduled collectors. It is a versioned *static declaration*; running it does not query shadow branches or verify Actions.

A separate review process may produce one or more JSON reports from `scripts/reconcile_shadow_slot_candidates.py`. These reports are optional, already source-scoped, and remain **operator-supplied candidates**. Never fabricate evidence, supply a family under another source's name, or treat an empty report as proof of publisher silence.

Generate a local combined snapshot and HTML:

```sh
python scripts/operations_center_shadow_overlay.py \
  --bindings /tmp/ipr-bindings-audit.json \
  --slot-report /tmp/ipr-indonesia-slot-candidates.json \
  --as-of 2026-10-08 \
  --html /tmp/ipr-ops-candidates.html \
  --json /tmp/ipr-ops-candidates.json
```

Omit `--slot-report` if there are no independently reviewed run observations. Both paths must be *new* and **outside the repository**. The base snapshot reads `pla_watch.db` through the existing scratch-copy method, never direct writable SQLite access.

## What the overlay actually proves

The integration reads the Phase 1 snapshot and local source manifests, verifies exact source-family coverage against the supplied `ipr-shadow-source-workflow-bindings/1` report, and pairs optional `ipr-shadow-slot-candidates/1` reports to the exact source slug, isolated state branch, and declared daily UTC cron. It rejects duplicate, missing, unrecognized and incorrectly routed families; contradictory candidate counts; future-dated observations; and any upstream report that claims rights, publication, authenticated run history or editor-delivery approval.

The HTML includes a **Shadow collection evidence candidates** table with per-family entries labeled **Not supplied** or **Operator-supplied, unauthenticated**. It is intentionally not a green/red live monitoring widget. Even an apparent `scheduled_success...` value remains a candidate until its full Actions and pinned state receipts are independently authenticated and checked for complete coverage.

The resulting snapshot explicitly sets `input_origin_authenticated=false`, `collection_verified=false`, `publisher_silence_established=false`, `publication_authorized=false`, and `editor_delivery_authorized=false`. It does not convert unverified reports into a production source health score.

**Non-goals:** no new scheduled jobs, fetches, archived state modifications, public page changes, source-rights determinations, automated recovery, Claude calls or editor emails. The Phase 1 command remains unchanged and works with no overlay.

## Merge and future activation

Developed against the Phase 1 branch to keep dependencies isolated while #249 is awaiting its full CI. Do not merge this into main before Phase 1 is merged and retested; also require the independently reviewed #257 and #259 report schema contracts to be stable. The overlay's next step, **not part of this PR**, is to authenticate Actions query scope, attempts and source-specific pinned state receipts before ever showing live collection status.

```sh
python -m unittest tests.test_operations_center_shadow_overlay -v
```

Require the repository-wide offline suite, Chromium launch, output validator, and tracked DB/output preservation before merge.
