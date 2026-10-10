# C2-C — Frozen fictional pre-collection source selection

**2026-10-10 | C2 engineering increment, not an activation or release approval**

## Why this is needed

C2-A (#359) correctly insists on a persisted native `source_run_results` record for every requested source, but its constructor accepts a caller-provided list. If a failing collector is simply *omitted from that list after the fact*, a partial run could be labeled complete. C2-B (#360) prevents silent paid-call replay but cannot repair a false upstream collection claim.

The new `storage/evidence_source_plan.py` establishes the *pre-collection* intent seam, wrapping the existing C2-A native barrier. A C1 fictional execution must already have a valid native scrape-run mapping, **but have no articles or source outcomes attributable to it**, before freezing the selected source list. The entire list (including an explicit empty list for backlog-only runs) is sorted, validated and committed through C1's immutable `put_new`/verified-readback transport under an execution-derived key. Reordered replay is idempotent; narrowing or expanding the selection is refused. A lost-ack write retains its stored plan, and a fresh process may reload it without trusting caller memory.

`FictionalSourcePlan.seal_collection()` constructs C2-A using only that frozen store record, not an editable caller argument. Therefore a missing initially selected source prevents collected-stage checkpoint promotion, even if the later caller wishes to omit it. Analysis readiness likewise re-reads the plan and checks the durable C1 collected generation.

## Important limitation

**This is an immutable selection record, not an independently authoritative selection policy or a production authorization.** A malicious caller that deliberately omits a source *before freezing* can still submit a smaller valid plan. Actual source selection must come from a separately reviewed, version-pinned desk manifest / explicit owner or schedule policy before any real collection or model call is ever enabled. The receipt states `production_selection_authorized=False`.

No real desk adapters are invoked, no sources are fetched, no APIs or models are called, no production DB or output is used, and no Daily, publishing, deployment or provider configuration is modified. Direct C2-A APIs remain fictional and are not security tokens. The future C2 runtime must make this frozen-plan facade the only eligible entrypoint, with independent identity/worker validation.

## Test contracts

- Missing or changed pre-collection selection is refused.
- A missing frozen source outcome blocks checkpoint promotion; a recorded collection failure remains explicit rather than masquerading as healthy silence.
- A plan cannot be retrofitted after native source rows/articles appear, or after a collected checkpoint.
- Lost-write acknowledgement does not permit rewriting the intent.
- Corrupted/canonical but inconsistent immutable source plans fail closed.
- Fresh application session replays the plan and verified immutable collected snapshot.
- Backlog-only execution with zero new sources is valid only with a frozen empty set.
- Source lists reject duplicate, malformed and path-like slugs.

**Dependency sequence:** #359 -> #360 -> this C2-C increment. Each is subject to Python 3.9 full offline CI, output validation and byte preservation, independent QA and explicit owner merge approval. No C2 complete/cutover assertion is authorized.

## Rehearsal commands

```bash
python -m unittest tests.test_evidence_source_plan -v
python -m unittest tests.test_evidence_lifecycle tests.test_evidence_spend -v
```
