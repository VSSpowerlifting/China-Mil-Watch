# C2-E — Fictional per-model-task dispatch ordering and explicit worker binding

**2026-10-10 | Review-only synthetic engineering; no production authorization.**

This increment sits on the disabled C1 + C2-A through C2-D stack. It addresses a
specific gap in the eventual application pipeline: `Analyzer.analyze()` calls
relevance, then conditionally translation, then two concurrent calls (summary
and categorization). A single per-*article* spend receipt is insufficient,
because each of those operations can create a separate provider charge.

## Implementation contract

`storage/evidence_task_gate.py` introduces
`FictionalAnalysisTaskGate`, deliberately **without importing, constructing,
patching or calling `Analyzer` or `pipeline.run()`**. It binds a
`FictionalManifestSourcePolicy` to the existing C2-B spend journal.

Every rehearsal reservation:

1. Revalidates the exact pinned desk manifest, the C2-C frozen source plan,
   the complete C2-A native collection results, and the C1 immutable collected
   generation before touching its write-once fictional spend intent.
2. Requires relevance's *measured* usage before a translation task, and also
   requires the native SQLite relevance verdict to be explicitly passing.
   A measured token receipt alone **never implies the model's verdict passed**.
3. Requires measured translation usage before either summary or categorization
   may reserve a new intent. Summary and categorization are siblings and may
   reserve independently in parallel; each gets a distinct task ID.
4. Forbids automatic retry on previously reserved tasks, including timeout,
   unknown-charge, lost-ack and measured-usage outcomes.
5. Returns `provider_call_executed: false`,
   `automatic_retry_authorized: false`, and
   `eligible_for_publication: false`. No source bodies/prompts/secrets are
   returned.

Tests use the real fictional native C1 database and hash-pinned manifest
metadata without invoking network or source adapters. They cover missing
collected durability, unknown-charge blocking, relevance-vs-spend distinction,
translation-before-summary, two real Python worker threads reserving the
parallel tasks through explicit context binding, source-result tampering,
forbidden private `pipeline.run()`, and invalid/unrecognized articles.

## Constructor preflight / recovery ordering

The C2-E facade may be constructed before source-plan freeze, but the C2-B
journal is resolved **lazily only when a task is used**. Its constructor no
longer dereferences a nonexistent C2-C plan. Every actual reservation still
revalidates the pinned manifest, frozen plan, and durable collected checkpoint
before writing an intent. This repairs the eight test-setup errors seen on the
superseded full A+B+C+D+E run; tests must still pass at the corrected head.

## Explicit remaining blockers

- Measured model usage is caller-supplied fictional accounting, not provider-
  attested billing truth. The draft cannot adjudicate a potentially charged
  timeout or determine monetary cost.
- A measured **translation** is not proof that translated text exists, is
  provenance-linked, or is semantically valid; production must require a
  separate validated durable translation artifact before summary/category.
- The actual Analyzer has not been adapted to use this gate. Future work must
  integrate at `analysis/analyzer.py` request transport boundaries and carry
  verified run/session context explicitly across `ThreadPoolExecutor`
  workers, with fail-closed real-provider dispatch.
- This does not claim an authorized source-selection policy, committed
  model output, complete per-execution spend ledger/enumeration, recovery RPO,
  publisher isolation or production cloud security.
- C2-E tests alone do not approve or activate anything. The unchanged
  production pipeline continues to refuse non-dry private execution.

## Exact-head CI staging

For full **A+B+C+D+E** coverage, the branch is temporarily compared to `main`
while the offline-checks workflow starts on the exact combined head. The PR's
review base is then restored to C2-D, preserving its three-file incremental
diff. A queued/in-progress Actions job is **not** a passing receipt.

## Gates before integration

Require Python 3.9 exact-head full offline tests, rendered-output validation,
`pla_watch.db` / `output/` byte-preservation, and independent review of the
three-file diff. Merge only after the entire prerequisite C2-A/B/C/D stack is
accepted and integrated in sequence with explicit owner approval.

```sh
python -m unittest tests.test_evidence_task_gate -v
python -m unittest tests.test_evidence_manifest_policy tests.test_evidence_source_plan tests.test_evidence_spend tests.test_evidence_lifecycle -v
```
