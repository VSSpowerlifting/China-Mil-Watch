# S2.2a — Conditional object transport and failure rehearsal

Parent [#332](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/332). Stacked on [S2.1 PR #336](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/336); [S1 PR #334](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/334) remains an independent public projection review. Source-use and retention decision [#326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326) is open.

**Synthetic-only research implementation; no cloud deployment, credentials, live collector, source bodies or publication rights.** This PR does not select an infrastructure provider or declare S2.2 complete.

## Purpose

S2.1 established immutable SQLite snapshot files and a POSIX temporary-directory test store. Before attaching a provider, S2.2a exercises exactly which *remote object storage* operations would be necessary to preserve their semantics: immutable create-if-absent, immediately verified reads, and a **service-atomic conditional replacement** of the current pointer against an opaque object revision.

A last-writer-wins \`PUT\`, listing/scan of objects, unsafely cached pointer, or provider-side version history alone does not meet this contract.

## Files

- \`storage/evidence_object_protocol.py\`: Python 3.9 Protocol with \`get(key)\`, \`put_new(key, bytes)\`, \`cas(key, expected_revision, bytes)\`; a linearizable process-local \`InMemoryConditionalStore\` **test double** with controlled failure injection; and \`EvidenceObjectCoordinator\` for immutable snapshots, manifests, conditional run/stage claims, current pointer, verified temporary restore. No provider SDK or network imports.
- \`tests/test_evidence_object_protocol.py\`: synthetic SQLite/WAL fixtures, multiple generations, races and failure cases. Neither \`pla_watch.db\` nor \`output/\` is read or modified.
- This documentation.

### Publication-safe object layout (conceptual, never an actual public bucket)

\`\`\`
snapshots/<sha256>.sqlite           # immutable, content addressed
manifests/<generation>.json         # immutable, generation manifest
claims/<run-id>/<stage>.json        # one-generation-only, conditional create
refs/current.json                   # updated with atomic revision compare-and-swap
\`\`\`

The \`claims\` keys handle a case a simple content-addressed store cannot: two processes preparing *different* captures for the same run and stage. They first upload immutable objects; exactly one generation can claim that run/stage. A failed contender leaves unreferenced immutable data, which must be managed only by a later retention-approved garbage-collection policy. No claim is made before snapshot and manifest read-back; partial uploads cannot mark a new generation current.

The in-memory store explicitly simulates failures before and after a write ("acknowledgement lost"). Retrying after a successful-but-unacknowledged CAS must observe the new active generation and no-op. Two writers from the same parent cannot both advance the current pointer. Corrupt snapshots, claims, manifests and current references refuse promotion and restore.

### Run focused verification

\`\`\`sh
python -m unittest tests.test_evidence_snapshot tests.test_evidence_store tests.test_evidence_object_protocol -v
python -m compileall -q storage/evidence_object_protocol.py tests/test_evidence_object_protocol.py
\`\`\`

PR exact-head full Python 3.9 CI is required. Passing synthetic tests does *not* establish actual provider semantics, durable retention, permission to privately archive any publisher's text, or publisher authorization to redistribute any of it.

## Provider decision and safe next work

S2.2b, **not this PR**, requires an explicit owner choice of provider/account/budget and review of: conditional create and CAS at the chosen provider, raw object consistency, versioning, IAM/OIDC or other appropriately scoped credentials, verified deletion/restoration behavior, audit logs, rollback, encryption, backup recovery, size/limits, and expected service-failure modes. Develop one provider adapter and run a read-back/recovery rehearsal in a **separate authorized test environment**. PR-triggered jobs must not be granted production store credentials.

The test-only local protocol intentionally abstracts object revisions as opaque strings. A real implementation must demonstrate that its provider's conditional header/ETag generation and pointer update are service-atomic; a Python process mutex around a network PUT is **not sufficient**. Short-lived IAM sessions and encryption at rest do not themselves establish publisher-source retention permission. No production cutover can precede S3 public renderer/export boundaries and S4 authorized deployment.

### Hard stop

No merge, cloud provisioning, production SQLite reads or backup, AWS/R2 API call, credential change, collector/pipeline/Daily/reconciler/renderer edit, public-site output, history rewrite, or source permission request is authorized or implemented by this PR. Owner/reviewer accepts design and full CI before considering a provider-specific phase.
