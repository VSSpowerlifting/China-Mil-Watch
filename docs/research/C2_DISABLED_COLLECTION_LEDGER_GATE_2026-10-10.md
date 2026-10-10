# C2-A — fictional collection durability and analysis-dispatch barrier

**October 10, 2026 | Engineering implementation increment; NOT C2 acceptance.**

Governing charter: [#342](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/342).
Prerequisite C1: [#356](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/356), merged as
`8cdc6b035762d7c04ee7fc266a5725388877a19f`. Rights #326, provider selection,
public projection, Daily activation, site deployment and source-retention decisions remain
separate and unresolved.

## What this increment actually changes

The **new** `storage/evidence_lifecycle.py` is a fail-closed *fictional-only* C2 stage
barrier over the **actual native schema and C1 DAO**, not a second scraper/LLM pipeline.
It is not hooked to `pipeline.run()`, which still refuses non-dry private execution.

- An explicit set of requested source slugs (including an empty set for backlog-only runs) determines the expected native
  `source_run_results` completeness contract; a missing, extra, wrong-status,
  misflagged or malformed receipt refuses collection promotion.
- Source receipts with `ok_no_publications`, disabled/stub or known failure outcomes
  remain separately represented. A collector outage is never silently converted to
  "no publication." Newly inserted records must be attributed to requested sources.
- The barrier asks **C1** to seal `collected`, then independently confirms the immutable
  current generation and its run identity before returning a redacted receipt.
- `verify_before_analysis()` requires that same acknowledged collected generation,
  restores a *fresh verified* snapshot and compares the native schema, original-content
  row identity, run attribution, source-run provenance and source ledger against the
  live fictional scratch DB. Analysis mutations may change **analysis fields**, not the
  preserved evidence/collection result. It does **not** itself call a model.
- `seal_analysis()` invokes the C1 analyzed generation checkpoint only after checking
  the durable collected parent and unmodified source ledger. Publication remains false,
  and the report states that a **usage receipt is not durable**.

Tests deliberately exercise C1's native initialized SQLite, `db.start_scrape_run()`,
`db.record_source_run_result()`, real DAO analysis writes, immutable C1 snapshots,
lost-CAS-ack restart and the existing non-dry private `pipeline.run()` refusal.
No publisher text, website, media, provider credentials, external requests or models.

## Exact negative tests targeted

1. No collected checkpoint => no analysis readiness.
2. A source requested but missing a persisted result => no checkpoint.
3. A declared adapter failure can be complete evidence, distinct from a healthy empty.
4. Unknown status/false success claim => reject.
5. Negative counters or new rows without requested source attribution => reject.
6. Mutated source status or replaced original content after collected checkpoint => reject.
7. Lost pointer acknowledgement => no same-process authorization; explicit C1 restart
   reconciles an actually committed immutable generation.
8. Analysis-only field changes => allowed; analyzed generation separately sealed.
9. No public URLs, bodies, titles, per-source errors or secrets in the handoff receipt.
10. Backlog-only runs may have zero new source outcomes while still sealing a native run.
11. Actual private `pipeline.run()` continues to refuse non-dry execution.

## Deliberately outside this PR

**C2 is not complete.** Existing Daily's Stage 7/8 write path is not wired to the
barrier. There is still **no paid-model dispatch gate in the production pipeline**,
no durable analysis-attempt/usage receipt, no LLM idempotency guarantee, no bounded
paid-call retry cost, no worker/process context propagation contract, and no
authoritative multi-reader renderer handoff. These need another review in this
C2 branch/PR or a separately approved work package before any C2 acceptance.

This file is a design/implementation receipt, not a provider security proof.
The first authored branch's CI outcome must be checked separately; no claim of
successful Python 3.9 tests is made until GitHub Actions actually finishes.

## Rehearsal test commands

```sh
python -m unittest tests.test_evidence_lifecycle -v
python -m unittest tests.test_evidence_custody tests.test_evidence_streaming -v
```

Full Python 3.9 offline CI, rendered-output validator and byte-preservation
checks must pass on the **exact PR head**, and an independent reviewer must
verify no real Daily/DB/output/workflow edits before integration.
