# C2-B — fictional paid-analysis intent journal

**October 10, 2026. Work-in-progress stacked on C2-A #359, not a C2 acceptance receipt.**

## Purpose and scope

The existing application makes up to four paid model tasks for an article:
relevance, translation, summary and categorization (the last two can run
concurrently). A crash after a provider charge but before durable application
accounting makes actual spend unknowable and risks a double charge when the
record is replayed. An in-memory usage accumulator and best-effort end-of-run
append cannot eliminate that uncertainty.

`storage/evidence_spend.py` introduces a write-once, fictional-only **intent
reservation** to be committed before any future provider call. Each key is
derived from the C1 execution ID, native article ID and task, not the model
name. Switching a model therefore cannot silently bypass an ambiguous attempt.
A separate write-once outcome object records either *measured token counts* or
*unknown spend*, never an invented zero.

A missing outcome, a lost reservation acknowledgement or an explicit unknown
outcome all remain **spend_unknown**; they **never authorize automatic
resubmission**. When an outcome write acknowledgement is lost, its exact bytes
can be read and reconciled without another charge. Changing an already
acknowledged usage count is refused. Every recovery read also validates the
complete immutable intent/outcome field sets, token counter types/ranges,
unknown-spend null usage and the claimed run/task identity. A canonical but
malformed or tampered object cannot be promoted into a valid spend receipt. The journal returns no source body, title,
URL, prompt, key or billing credential.

Each reservation requires the C2-A native collection barrier and a fresh
verification of the persisted C1 collected generation. The target article
must have a nonblank original body and must not be paused or terminal.
The journal does not itself execute the provider call; `provider_call_executed`
is always false.

## Test coverage

The tests use native fictional C1 SQLite fixtures and the existing
fault-injectable immutable object transport. They exercise blocking before
collected durability, measurable/unknown spend, duplicate reservation
rejection after completion or uncertainty, lost acknowledgement before/after
write, immutable outcome mismatch, bad model/task/token data, source-content
tampering, and two threads racing on one task.

## Explicit limits — NOT a spend-protection deployment

- The journal is **not wired** to the real `analysis.analyzer.Analyzer`,
  `pipeline.run()`, the Daily workflow, or a provider. No model/network call
  or real paid usage occurs in this PR.
- A token receipt provided by a fictional caller is not independently
  authenticated provider telemetry and is **not a monetary cost**.
- No approved provider idempotency key, human resumption decision, retry
  budget/RPO, tariff/pricing audit or asynchronous worker propagation exists.
- Concurrent charge safety requires future callers to honor the intent
  protocol **before** every external request, including parallel summary and
  categorization workers. This is not currently enforced in production.
- The underlying fictional object-store root is not a production
  access-controlled evidence vault or independent backup.
- Publishing, private provider selection, source rights and the C3–C6
  release gates remain unapproved.

**Stack alignment:** This increment is rebased on the latest #359 native source-ledger gate, including status/counter coherence checks and text-unavailable bounds. No executable production pipeline or provider calls are introduced.

**Dependencies:** #359 must be reviewed and integrated before this stacked
increment can be considered for merge. Run exact-head Python 3.9 full CI,
output validation and DB/output byte-preservation, and obtain a separate
independent review for this PR. Never enable the live pipeline.

## Offline commands

```sh
python -m unittest tests.test_evidence_spend -v
python -m unittest tests.test_evidence_lifecycle tests.test_evidence_custody -v
```
