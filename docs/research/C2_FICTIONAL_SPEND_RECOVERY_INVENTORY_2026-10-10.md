# C2-F — Read-only fictional spend recovery inventory

**2026-10-10 | Synthetic-only, not a transactional spending fence or analysis-closure approval.**

## Why an audit is necessary

The C2-B spend journal stores one write-once intent/outcome per **execution,
article ID, task**. C2-E establishes task ordering, but an owner cannot safely
read only successful outcomes and assume the missing ones never incurred costs.
A charged provider call may have been acknowledged late or not at all. A
failed or unreserved task is not automatically safe to retry.

`storage/evidence_spend_inventory.py` provides
`FictionalSpendRecoveryInventory`. After verifying the current pinned native
desk manifest, frozen precollection source plan, full source-results ledger,
native document identities and immutable C1 collected checkpoint, it enumerates
the **complete native article ID list** within an explicit nontruncating cap and
tests **all four** known task identities per article. It separates:

- `measured_fictional_attempts` — write-once attempts whose caller supplied
  a syntactically valid token receipt (not provider attestation);
- `unknown_charge_attempts` — reserved intents without durable measured
  outcomes, including explicit unknown, lost acknowledgements and crashes;
- `unreserved_task_slots` — no recorded attempt for that article/task;
- summed fictional token counters, without quoting text, titles, prompts,
  URLs, source names, provider secrets, or per-article identifiers.

`require_no_unknown()` refuses if an existing reservation is unresolved.
**It still never returns analyzed checkpoint authorization.** It also does
not call `checkpoint('analyzed')` or any provider.

## Recovery inventory can be instantiated before plan freeze

The auditor's constructor now records policy identity and limits only. Its
C2-B journal is initialized lazily after `audit()` calls the pinned-manifest
and durable collected-stage preflight. This avoids constructor-time
`c2_source_plan_missing` while **retaining the stronger audit-time refusal**
for a missing or incomplete source plan. No task or provider is called.

## Security and concurrency limits

This report is deliberately **not a proof of complete billing**. The fake
object store does not support listing all provider attempts, and a separate
unregistered task/key would evade a four-task namespace sweep. It is still
possible for another worker to reserve a new intent just after the read-only
scan; a genuine analyzed-stage commit gate requires an exclusive, durable
reservation-fence protocol respected by *all* workers, not a race-prone double
check. C2-F therefore reports
`analyzed_checkpoint_authorized=False`,
`billing_provider_attested=False`,
`all_analysis_tasks_complete=False`,
`automatic_retry_authorized=False`, and
`eligible_for_publication=False` even if its counts are clean.

The scan does not decide which articles deserved analysis, whether a
translation was valid, whether relevance met editorial standards, how much
money was spent, or whether a timeout might have been billed. Provider
request IDs/actual billing and independent owner-approved source policy are
future gates.

## CI retest and upstream fixture lineage

The exact-head full-suite run here includes the C2-D seed-source correction
(`pla_daily` already exists in the native scratch schema), with C2-E and
C2-F fixtures corrected identically. The previously triggered combined run
covers the superseded head and is **not** evidence for this head. A fresh
successful run, including output/DB preservation, is required.

## Combined CI staging

The exact-head full Python 3.9 workflow is launched while this stacked branch
is temporarily compared to `main`. Its pull request review base is restored
to C2-E immediately once Actions registers the run, retaining the three-file
incremental diff. A queued or in-progress CI job never constitutes passing
acceptance or release authorization.

## Test coverage / dependency

`tests/test_evidence_spend_inventory.py` uses native fictional C1 SQLite,
hash-pinned real **manifest metadata** but no real sources, and the existing
C2-B/E synthetic journal. Cases include absence of a collected checkpoint,
zero vs unreserved (not proof of completion), ambiguous charge state, measured
fictional token aggregation, lost-write acknowledgement, corrupt receipt,
post-collection document/source tampering, bounded article inventory, and
no real network/provider calls.

Stacked PR sequence: #359 (already merged to main), #360, #361, #362, #363,
then this C2-F increment. It must not be merged or enabled without exact-head
Python 3.9 offline CI, rendered-output checks, DB/output preservation,
independent review and owner approval. No changes to `pipeline.py`,
`analysis/analyzer.py`, scheduled workflow, deployment, tracked DB or output.

```bash
python -m unittest tests.test_evidence_spend_inventory -v
python -m unittest tests.test_evidence_task_gate tests.test_evidence_manifest_policy tests.test_evidence_source_plan tests.test_evidence_spend tests.test_evidence_lifecycle -v
```
