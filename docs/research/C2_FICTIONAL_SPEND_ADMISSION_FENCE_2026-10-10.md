# C2-G — Fictional CAS-based spend admission, with crash-sticky worker flights

**2026-10-10 | Standalone disabled test increment. No provider, collector, publishing, deployment or automatic merge.**

## What this adds

`storage/evidence_admission_fence.py` adds a **fictional** per-execution
admission record over C1's conditional object-store protocol. The record
includes the immutable collected-generation identity, a one-way
`open → closed` state, and a durable number of in-flight *cooperating* worker
operations, updated only through revision-checked `cas`.

Before a test worker may reserve a C2-E fictional analysis task, the facade
revalidates C2-D's pinned desk manifest and the C2-C/A source-plan and
collected-generation proofs, then CAS-increments the flight count. It delegates
to the C2-E task gate and C2-B write-once journal **without any model call**,
then CAS-decrements in a `finally` block. An ordinary failed preflight still
releases its flight. A process crash or ambiguous CAS write acknowledgement
can leave `inflight>0`; **that blocks closure by design**, instead of assuming
the charge did not happen.

`close()` is irreversible and requires `inflight=0` at a linearized CAS
point, so cooperating workers cannot begin new reservations afterward.
Closure then reads C2-F's **advisory** four-task unknown-charge inventory.
The result ALWAYS reports:
`billing_provider_attested=False`,
`analyzed_checkpoint_authorized=False`,
`automatic_retry_authorized=False`,
`eligible_for_publication=False`.

No code calls `checkpoint('analyzed')`, `Analyzer`, a provider, source
collector or public renderer.

## Tests

`tests/test_evidence_admission_fence.py` uses temporary native C1 SQLite,
repo-manifest metadata (read-only), fictional article/source outcomes,
`InMemoryConditionalStore`, and real Python worker threads to exercise:

- Refuse opening before source collection is durably verified
- CAS enrollment and exact one-way close; no reservations accepted after
- An active worker prevents closure until its flight is released
- Simulated CAS lost acknowledgement before task reservation leaves a
  **sticky in-flight blocker**; never silently counts the attempt as free
- Simulated lost close acknowledgement still leaves the gate closed
- Two concurrent summary/category reservations carry independent task keys
- Corrupted CAS state and invalid capacity refuse rather than downgrade
- Task failure releases a properly registered flight without authorizing
  anything external

## Security boundary — explicitly NOT production-safe

This is only a linearizable protocol **among cooperating callers**. The
existing C2-B journal and C2-E task gate remain separately callable and are
**not fenced by this module**. Therefore neither `close()` nor
`inflight=0` proves all possible reservations have stopped. An owner-
authenticated runtime would have to prohibit every bypass and bind all
providers/workers to the same durable admission coordinator.

Additional blockers: the in-memory store is not a real permissioned object
provider; no distributed lease or secure identity, no safe recovery of
crashed registrations, no provider-attested billing or model result truth;
task slots may not all be required for a given article. None of these are
supplied, asserted or implied by this increment. No real request id,
cost, prompt, article text, model response, source-use authorization or
publication output is stored.

## Dependency constructor fix incorporated

The preceding E/F modules now construct their facades without demanding a
source plan before it can be frozen. Each **operation** still resolves and
verifies the source plan and collected-generation snapshot before writes or
audits. This correction addresses eight old E constructor/setup errors and
must be revalidated together with the G fence at this new exact head.

## Exact-head combined-stack validation

Because the PR is stacked on five other C2 increments, its complete CI can
only be verified against all ancestral code. For one test run, the PR is
briefly compared with `main`, and this documentation change triggers the
standard offline Python 3.9 checks on that exact head. The PR base is then
restored to C2-F, leaving just the three C2-G files in the review diff.
All queued/running or canceled checks are unaccepted; only final successful
steps count as evidence.

## Review sequence

Dependencies: merged #359 → unmerged #360 → #361 → #362 → #363 → #364 →
this new C2-G. Each PR must pass exact-head Python 3.9 full offline CI,
output validation, and tracked DB/output preservation and receive independent
review plus *specific owner authorization* before any merge. Production
`pipeline.run()` non-dry private mode remains fail-closed.

```bash
python -m unittest tests.test_evidence_admission_fence -v
python -m unittest tests.test_evidence_spend_inventory tests.test_evidence_task_gate tests.test_evidence_manifest_policy -v
```
