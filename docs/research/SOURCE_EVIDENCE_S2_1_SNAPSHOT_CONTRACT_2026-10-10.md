# S2.1 — Offline SQLite evidence snapshot and recovery contract (2026-10-10)

Parent: [IPR source/publication architecture #332](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/332). Source-use decision still [#326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326). S1 synthetic public projection [PR #334](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/334) is **green but open** as of branch creation. This S2.1 work was independently based on main, with no S1 merge or imported code.

## Status and non-authorization

**Synthetic/offline infrastructure rehearsal only.** This code is **not** access-controlled storage, not a live archive backup, not an approved source-use or retention decision, and not a production migration. It does **not** read or modify `pla_watch.db`, `output/`, `pipeline.py`, `site/render.py`, `daily_update.yml`, `reconcile_db.py`, `.gitattributes`, Briefs, Timelines or Dossiers. It does not use cloud storage, secrets, remote/network calls, models or real original publisher text. All fake databases contain deliberately fictional strings.

### New isolated code

- `core/evidence_snapshot.py`: version `ipr-evidence-snapshot/1` manifest; `sqlite3.Connection.backup` for WAL-consistent snapshots; exact structural checks (`PRAGMA integrity_check`, foreign keys, positive stable article IDs, record count/max ID and user_version); SHA-256 file digest; parent generation and immutable generation digest; read-only restore verification.
- `storage/evidence_store.py`: POSIX **temporary-directory only** local rehearsal adapter. Content-addressed snapshots and immutable generation manifests, idempotent duplicate writes, locked conflicting run/stage rejection under racing writers, active pointer with OS file lock and atomic compare-and-swap, old-generation restore and safe non-clobbering destination handling. It is deliberately limited to 32 MiB artificial fixture snapshots, **not** a future production storage adapter.
- `scripts/rehearse_evidence_recovery.py`: only CLI mode `--synthetic-only`; creates and deletes its entire fake database/store in a new temporary directory, never accepts real inputs; emits `eligible_for_publication: false`.
- `tests/test_evidence_snapshot.py`, `tests/test_evidence_store.py`: 39 isolated fictional tests for committed WAL and uncommitted visibility, integrity/foreign keys, manifest tampering, ID continuity, immutable artifact semantics, pointer conflicts/stale writers, competing run identity, failed restore and historical snapshot recovery.

### Commands

```bash
python -m unittest tests.test_evidence_snapshot tests.test_evidence_store -v
python scripts/rehearse_evidence_recovery.py --synthetic-only
python -m compileall -q core/evidence_snapshot.py storage/evidence_store.py scripts/rehearse_evidence_recovery.py tests/test_evidence_snapshot.py tests/test_evidence_store.py
```

Local Python 3.13 run: **39/39 tests passed**, rehearsal returned passed=true with `eligible_for_publication=false`, and compileall passed. GitHub's exact-head full offline PR suite on Python 3.9 is still a required independent gate; do not claim green until the run finishes.

## Invariants and operational cautions

1. One immutable snapshot is stored under its full SHA-256 digest and an immutable manifest is named by the digest of its canonical metadata (the generation ID). The manifest contains no source text, original URL or editorial prose.
2. The latest pointer is separate from immutable evidence; it advances only after the manifest and snapshot are checked, and only if the caller's expected parent equals the current generation. Exact replays are no-ops; a changed snapshot for the same `(run_id, stage)` is rejected.
3. A successful collection capture, an analysis checkpoint and a completed published Daily run are **distinct** states. No Daily success marker is written here. Neither snapshots nor metadata are public publication grants.
4. `sqlite3.Connection.backup` captures committed WAL content at a coherent SQLite view. Byte-level stability of the *source* `-shm` file is not required; it is mutable coordination state. The target backup is verified as a self-contained SQLite DB.
5. The local adapter uses filesystem locks and atomic rename/hard-link operations available on the GitHub Linux runner. POSIX atomicity does **not** automatically transfer to S3, R2 or Windows. An actual object storage adapter must use provider-documented conditional writes, versioning and independent durability verification.
6. No authentication, encryption, access controls, provider retention semantics or off-site disaster recovery exist in this local rehearsal. An artificial tempdir prefix is a safety guard against accidental use, not a security property.
7. The existing Git-tracked production SQLite reconciler still resolves `origin/main` as the published identity authority; S2.1 does not replace it. No historical Git/Pages/full-body exposure is remediated by this module.

## Follow-up (NOT authorized by merging this PR)

S2.2 requires owner selection of private backend, budget, credential/identity architecture, versioning and audited storage policy. Implement one provider adapter with immutable upload, short-lived credentials and true service-side conditional head updates; run synthetic read-back/recovery trials. Real corpus backup or storage access requires separate rights/retention approval.

S2.3 must rehearse interrupted collection, mid-analysis failures, two-writer conflict resolution, disconnected private store, cleanup, backup restore, source hash parity and neither loss of collected records nor publication through existing public success/failure Git commits. It must review all current `daily_update.yml` persistence and the Git merge driver, but cannot change live pipeline behavior as part of S2.1.

S3 separately reconciles the public projection/legacy exports/record templates, and S4 requires an owner-authorized cutover. Never change public `main`/Pages with raw source material on the assumption that a new temp snapshot store already makes it private.

**Stop at this reviewable PR, its exact-head CI and owner/qualified review. No cascade into infrastructure, production, Git history rewriting, source-rights requests or publication.**
