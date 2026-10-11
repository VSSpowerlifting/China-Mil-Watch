# C1 application custody implementation receipt

Governing charter: [#342](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/342),
[manager scorecard](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/342#issuecomment-6099822544).
This is explicitly enabled fictional engineering under #332. Source-use #326,
provider selection/security, retention, deployment and production activation remain
owner gates. Existing public SQLite, Daily success/failure Git commits and all
publication surfaces remain active; this code does not make existing evidence private.

## C0 accepted integration

| Gate | Verified integration | Exact-head full CI |
| --- | --- | --- |
| C0-01 | S1 #334 and S2.1 #336 already on main | Prior isolated receipts |
| C0-02 / C0-04 | Reviewed #341 head `b6831990`; main merge `6d1c88f87`; exact three-file delta | [38063391028](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38063391028) |
| Fixture prerequisite | Reviewed #352 head `445f4286`; main merge `4952b049`; exact two files / six lines | [38079654370](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38079654370): 5,471 tests, nine skips |
| C0-03 / C0-05 | #340 refreshed at `ef5993d1`, no conflicts, original four file blobs unchanged; main merge `00a58b8b` | [38081600443](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38081600443): 5,494 tests, nine skips |

Both fresh prerequisite runs passed Python 3.9.25, output validation with the
10 governed warnings, and tracked database/output preservation without sidecars.
The earlier #340 seven-error receipt was superseded after independently reviewed
fixture isolation; production future-marker rejection remains intact. C0-04 and
C0-05 are PASS for these exact integrations. C1 remains independently reviewable,
not accepted by its producer. C2 has not begun.

## Architecture and enforced behavior

`RehearsalCustodySession` requires explicit enablement and a dedicated
`ipr-custody-*` temporary directory. Startup verifies the authoritative pointer,
immutable manifest/claim, streamed snapshot, exact native migration checksums and
schema, foreign keys, original-content hashes and complete ancestor identity
continuity before linking a new working SQLite file. There is no tracked-DB or
public-Git fallback. Restored copies never initialize/migrate automatically.

`FictionalFileStore` implements conditional metadata operations plus file upload
and download. Objects persist across new processes while the temporary root
exists. A cooperating-process flock serializes create/CAS; file payloads carry
opaque UUID revisions, avoiding ABA across restarts. Staged files are fsynced
before atomic link/replace and directory sync. Immutable collisions are verified
by fresh readback. SHA-256 and SQLite inspection use bounded chunks. Default
capacity is 256 MiB, configurable up to 1 GiB, with explicit failure on excess.
This POSIX adapter is a rehearsal, not access control, encryption, a cloud provider,
an authenticated archive or an operational backup/retention policy.

`StreamingEvidenceCoordinator` retains S2 manifest/ref formats and run/stage claim
semantics. Its public verified-generation and prepared-claim interfaces avoid
application dependence on private coordinator methods. Current/advance/restore
reread actual snapshot bytes rather than trust metadata or an ETag. An initialization
receipt distinguishes explicitly new stores from disappeared initialized pointers;
preexisting uninitialized objects are refused. Prepared objects are not current.
Explicit recovery verifies a claimed stage and its ancestry, then CAS-promotes only
against its expected parent. A stale prepared stage cannot overwrite a newer head.

A durable `execution.json` descriptor supplies a UUID by default, a logical date,
and stable retry identity. The fictional database extension maps each execution
to a unique native `scrape_runs.id`; creation and mapping share the actual DAO
transaction. Repeated creation for the same execution returns its native row.
Two restored writers may allocate the same numeric ID, but have different custody
identities/claims; only one can advance the shared pointer. Native IDs/FKs are
never rewritten. Orchestration must retain/provide the descriptor across disposable
runners; a calendar date or `str(native_id)` is insufficient.

Lineage preserves historical article IDs, URLs, original text/title/hash, dates,
source bindings, source rows, run starts, source-result receipts and execution
mappings. New collected IDs are monotonic and attributed to the current native
execution. Analysis may change analysis/accounting fields but cannot introduce
records or collection provenance. Schema transitions, purges and redactions need
separately reviewed exceptions; unknown migration/layout fails closed.

`DatabaseContext` is explicit, scoped with ContextVar and revalidated before each
DAO connection, including atomic batches. Working files use `mode=rw`, never
implicit SQLite create; completed restarts are read-only and reverify their sealed
bytes. `db.init_db` refuses a private context. The pipeline private-mode inspection
seam validates and returns on dry run before directories/init/collection/model work;
non-dry private execution is refused until C2. Legacy default behavior is unchanged.
No runtime context is installed by imports, config, environment or workflows.
ContextVar scopes do not implicitly bind newly spawned threads/processes; C2
must inject the verified context into each worker and explicitly bind other readers.

The general backup helper refuses an open caller transaction before creating a
file, never commits/rolls back it, and has a cooperative deadline checked through
SQLite progress callbacks. Interrupted owned artifacts are removed. A callback
deadline is not a hard OS I/O timeout. Successful backups are standalone DELETE
journal artifacts; immutable readers do not create WAL/SHM beside sealed snapshots.

## Verification and file ledger

Run fictional harness:
`TMPDIR=/private/tmp .venv/bin/python scripts/rehearse_application_custody.py --synthetic-only`.
It uses actual insert/relevance/queue interfaces, persistent transport recreation,
lost analyzed-CAS acknowledgement, completed restart and historical restore.
Reports contain identifiers/digests and publication-ineligible status, never source
prose. No collector, paid model, cloud, production database or public output is used.

The two earlier focused stage failures came from a broad restore exception wrapper.
Known contract errors now retain their fixed codes after owned-file cleanup;
unexpected exceptions remain redacted. Both negative stage cases pass unchanged.

Tests cover native schema/ledger negatives, source hash/ID replacement, lost rows,
wrong run attribution, collection/analyzed retries, interrupted pointer replacement,
lost acknowledgement, prepared/stale recovery, pointer disappearance, persistent
process restart, process-level CAS/ABA, scoped DAO/atomic paths, missing/outdated
private dry runs, migration refusal, native health verification and WAL write /
truncate interleaving. A 57,024,512-byte fictional native snapshot exceeds the
47,398,912-byte reviewed corpus baseline; measured Python checkpoint allocation
peak is approximately 2.6 MiB. This is tracemalloc evidence, not total RSS or a
provider throughput benchmark. Pre-commit Python 3.9 verification passed 292 focused/compatibility tests and
23 refreshed #340 contracts; the persistent CLI harness and local output
validator passed (10 governed warnings). All 7,652 protected local files are
unchanged, with no added output or sidecars. Full exact-head CI receipt is recorded
in the PR. The AST-only graphify update completed without model calls; its local
ignored graph is excluded from the PR.

| Files | Responsibility |
| --- | --- |
| `storage/evidence_custody.py` | Verified application startup, history, execution, binding, recovery and stages |
| `storage/evidence_streaming.py` | Persistent fictional streaming transport and coordinator |
| `storage/evidence_object_protocol.py` | Public verified manifest/prepared-claim API and strict revision type |
| `core/evidence_snapshot.py` | Transaction/deadline guard, standalone backup and immutable verification |
| `storage/db.py`, `pipeline.py` | Explicit DAO authority and private-mode validation-only seam |
| `scripts/rehearse_application_custody.py` | Disabled-by-default end-to-end fictional exercise |
| `tests/custody_fixtures.py`, `tests/test_evidence_custody.py`, `tests/test_evidence_streaming.py`, `tests/test_evidence_snapshot.py` | Fictional native fixtures and behavioral failure coverage |
| This receipt, `PROJECT_STATE.md` | C0 gates, implementation limits and review handoff |

## Remaining review gates and rollback

No C2 checkpoint hooks, collector/model execution, common renderer/health default
cutover, billing/telemetry durability or paid-call RPO is implemented. Explicit-path
native health tests prove the selected fixture only. Other readers still default to
the public archive; C2/C3 must bind one sealed generation before any release claims.
Schema validation currently pins exact repository migrations; no automatic upgrade
of an old private generation is allowed. Identity material uses memory proportional
to record count and individual row size; transport memory is independent of file
size. Startup verifies the full ancestor chain (bounded at 1,024); I/O grows with
history and requires later provider/capacity review. Unreferenced immutable objects
and crash staging files need a separately reviewed retention/recovery policy.

A POSIX process crash is tested at durable boundaries; power-loss/filesystem and
real service behavior are not proven. No IAM, encryption, credentials, provider
SDK, production material, rights approval, public projection, workflow changes or
deployment exists in this delta. The interface is for trusted application injection,
not hostile in-process callers or adversarial local filesystem access.

Rollback is a revert of this C1 commit while its feature remains off. No production
data or schema was migrated, so no evidence rollback is required. Retain any
fictional scratch state needed for diagnostic recovery; never promote a historical
restore automatically. Stop after the C1 PR and full offline CI for independent
engineering-manager review. Production activation and C2 require later authorization.
