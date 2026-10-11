"""Application-aware custody session; opt-in, fictional temporary SQLite only.

Uses S2's backup/manifest/conditional object protocol and the application's
actual schema, migration receipts and original-content hash. No provider,
publication permission, production binding or public-Git fallback exists.
"""
from __future__ import annotations

import sqlite3
import tempfile
import os
import json
import uuid
from datetime import datetime, timezone, date
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Protocol, ContextManager

from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, capture_backup, digest_bytes,
    manifest_for_backup, inspect_database, require,
    verify_snapshot,
)
from migrations.runner import discover, apply_all
from processing.metadata import compute_content_hash
from storage.evidence_object_protocol import EvidenceObjectCoordinator

FIXTURE_TOKEN = "IPR_CUSTODY_FICTIONAL_ONLY_V1"
REPORT_SCHEMA = "ipr-custody-rehearsal/1"
EXECUTION_SQL = ("CREATE TABLE ipr_custody_execution (execution_id TEXT PRIMARY KEY, "
                 "logical_date TEXT NOT NULL, native_run_id INTEGER NOT NULL UNIQUE "
                 "REFERENCES scrape_runs(id))")


def execution_identity(root, run_id=None, logical_date=None):
    """Durable execution identity, independent of reusable SQLite row numbers.

    A retained scratch descriptor survives a local retry; a disposable runner
    must receive the same descriptor/identity from its future orchestration.
    Selecting a day alone never identifies an execution. No workflow is wired.
    """
    from core.evidence_snapshot import ID_PATTERN
    require(run_id is None or (type(run_id) is str and bool(ID_PATTERN.fullmatch(run_id))),
            "custody_run_id_invalid")
    path = root / "execution.json"
    require(not path.is_symlink(), "custody_execution_invalid")
    if not path.exists():
        value = {"schema": "ipr-custody-execution/1", "execution_id": run_id or uuid.uuid4().hex,
                 "logical_date": logical_date or datetime.now(timezone.utc).date().isoformat()}
        staging = root / (".execution-" + uuid.uuid4().hex)
        try:
            fd = os.open(str(staging), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(canonical_bytes(value)); stream.flush(); os.fsync(stream.fileno())
            try:
                os.link(staging, path)
            except FileExistsError:
                pass  # A racing creator is reconciled below, never overwritten.
            from storage.evidence_streaming import sync_directory
            sync_directory(root)
        finally:
            staging.unlink(missing_ok=True)
    try:
        require(path.stat().st_nlink == 1 and path.stat().st_size <= 4096,
                "custody_execution_invalid")
        raw = path.read_bytes()
        value = json.loads(raw)
        require(type(value) is dict and set(value) == {"schema", "execution_id", "logical_date"} and
                value["schema"] == "ipr-custody-execution/1" and
                type(value["execution_id"]) is str and
                bool(ID_PATTERN.fullmatch(value["execution_id"])), "custody_execution_invalid")
        require(raw == canonical_bytes(value), "custody_execution_invalid")
        date.fromisoformat(value["logical_date"])
        require((run_id is None or run_id == value["execution_id"]) and
                (logical_date is None or logical_date == value["logical_date"]),
                "custody_execution_conflict")
        return value
    except (ValueError, TypeError, OSError, RecursionError) as exc:
        if isinstance(exc, EvidenceContractError):
            raise
        raise EvidenceContractError("custody_execution_invalid") from None


class CustodySession(Protocol):
    """Lifecycle seam: verified startup, durable stages, verified restoration."""

    database_path: Path
    run_id: str
    logical_date: str

    def bootstrap(self, *, allow_empty: bool = False, recover_stage=None) -> dict: ...
    def checkpoint(self, stage: str) -> dict: ...
    def restore(self, destination: Path, generation: str = None) -> dict: ...
    def application(self, *, read_only: bool = False) -> ContextManager: ...


def _scratch_root(root):
    path = Path(root)
    temp = Path(tempfile.gettempdir()).resolve()
    require(path.is_dir() and not path.is_symlink() and
            temp in path.resolve().parents and
            path.name.startswith("ipr-custody-"), "custody_scratch_required")
    # Permit the OS's canonical temp alias, but no links inside that root.
    probe = path.absolute()
    while probe.resolve() != temp:
        require(not probe.is_symlink(), "custody_scratch_required")
        probe = probe.parent
    return path.resolve()


def _fictional(connection):
    try:
        marker = connection.execute("SELECT marker FROM ipr_custody_fixture").fetchall()
        require([tuple(r) for r in marker] == [(FIXTURE_TOKEN,)],
                "custody_fictional_required")
    except sqlite3.Error:
        raise EvidenceContractError("custody_fictional_required") from None


def application_identity(connection):
    """Private comparison material: exact IDs and preserved row/source digests.

    Hashes are mechanical integrity signals, never publication permissions.
    Read the frozen backup, so every query describes the same SQLite state.
    """
    _fictional(connection)
    inspect_database(connection)
    try:
        migrations = [tuple(r) for r in connection.execute(
            "SELECT version, checksum FROM schema_migrations ORDER BY version")]
        require(migrations == sorted((m.version, m.checksum) for m in discover()),
                "custody_schema_incompatible")
        schema = [tuple(r) for r in connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
        native_schema = [r for r in schema if r[1] != "ipr_custody_fixture"]
        require(native_schema == _expected_schema(), "custody_schema_incompatible")
        records = {}
        record_runs = {}
        for row in connection.execute(
                "SELECT a.id,a.url,a.content_hash,a.source_id,a.scrape_run_id,"
                "a.title_original,a.text_original,a.published_date,a.scraped_at,"
                "s.slug,s.desk_id,s.language,s.base_url,s.institution_id,"
                "s.language_tag,s.display_name FROM articles a "
                "JOIN sources s ON a.source_id=s.id ORDER BY a.id"):
            row = tuple(row)
            require(row[2] == compute_content_hash(row[5], row[6]),
                    "custody_source_hash_mismatch")
            require(all(type(row[i]) is str and bool(row[i]) for i in (9,10,11,12)),
                    "custody_source_identity_missing")
            records[row[0]] = digest_bytes(canonical_bytes(row))
            record_runs[row[0]] = row[4]
        require(len(records) == connection.execute(
            "SELECT count(*) FROM articles").fetchone()[0],
            "custody_source_identity_missing")
        provenance = {
            "source_rows": {r[0]: digest_bytes(canonical_bytes(tuple(r))) for r in
                            connection.execute("SELECT * FROM sources ORDER BY id")},
            "executions": {r[0]: digest_bytes(canonical_bytes(tuple(r))) for r in
                           connection.execute("SELECT * FROM ipr_custody_execution ORDER BY execution_id")},
            "runs": {r[0]: digest_bytes(canonical_bytes(tuple(r))) for r in
                     connection.execute("SELECT id,started_at FROM scrape_runs ORDER BY id")},
            "sources": {(r[1], r[2]): digest_bytes(canonical_bytes(tuple(r))) for r in
                        connection.execute("SELECT * FROM source_run_results ORDER BY id")},
        }
        native_runs = {}
        from core.evidence_snapshot import ID_PATTERN
        for execution, day, native in connection.execute("SELECT * FROM ipr_custody_execution"):
            require(type(execution) is str and bool(ID_PATTERN.fullmatch(execution)) and
                    type(day) is str and type(native) is int and native > 0,
                    "custody_execution_mapping_invalid")
            try:
                date.fromisoformat(day)
            except ValueError:
                raise EvidenceContractError("custody_execution_mapping_invalid") from None
            native_runs[execution] = native
        return {"records": records, "record_runs": record_runs, "native_runs": native_runs,
                "provenance": provenance,
                "schema": digest_bytes(canonical_bytes([migrations, schema])),
                "record_ids_sha256": digest_bytes(canonical_bytes(sorted(records))),
                "preserved_rows_sha256": digest_bytes(canonical_bytes(
                    sorted(records.items())))}
    except sqlite3.Error:
        raise EvidenceContractError("custody_application_schema_invalid") from None


@lru_cache(maxsize=1)
def _expected_schema():
    """Trusted layout from repository schema + actual migration code, no DB read.

    A database's own migration receipts do not prove that its columns, indexes
    or constraints survived intact. Build the independent expected layout once.
    """
    reference = sqlite3.connect(":memory:", isolation_level=None)
    try:
        reference.executescript((Path(__file__).parent / "schema.sql").read_text())
        apply_all(reference, sync_config=False)
        reference.execute(EXECUTION_SQL)
        return [tuple(r) for r in reference.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
    finally:
        reference.close()


def _read_identity(path):
    connection = sqlite3.connect(Path(path).as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        return application_identity(connection)
    finally:
        connection.close()


def _continuity(previous, candidate, stage, execution_id):
    require(previous["schema"] == candidate["schema"], "custody_schema_changed")
    before, after = previous["records"], candidate["records"]
    require(set(before).issubset(after), "custody_records_removed")
    require(all(after[aid] == digest for aid, digest in before.items()),
            "custody_preserved_record_changed")
    added = set(after) - set(before)
    if stage == "analyzed":
        require(not added, "custody_analysis_identity_changed")
    else:
        require(all(aid > max(before, default=0) for aid in added),
                "custody_nonmonotonic_ids")
        require(all(candidate["record_runs"][aid] == candidate["native_runs"].get(execution_id)
                    for aid in added), "custody_collection_run_mismatch")
    for family in ("runs", "sources", "executions", "source_rows"):
        before_prov = previous["provenance"][family]
        after_prov = candidate["provenance"][family]
        require(all(after_prov.get(key) == digest for key, digest in before_prov.items()),
                "custody_collection_provenance_changed")
        if stage == "analyzed":
            require(set(before_prov) == set(after_prov), "custody_analysis_provenance_changed")


def _verify_history(coordinator, manifest, identity):
    """Verify persisted stage/ancestry; bootstrap cannot trust our own writer."""
    seen = set()
    while True:
        require(manifest["generation"] not in seen and len(seen) < 1024,
                "custody_lineage_invalid")
        seen.add(manifest["generation"])
        require(manifest["stage"] in ("collected", "analyzed"), "custody_stage_invalid")
        parent = manifest["parent"]
        if parent is None:
            require(manifest["stage"] == "collected", "custody_collection_required")
        require(manifest["run_id"] in identity["provenance"]["executions"],
                "custody_execution_mapping_missing")
        if parent is None:
            return
        with tempfile.TemporaryDirectory(prefix="ipr-custody-history-") as root:
            path = Path(root) / "parent.sqlite"
            prior = coordinator.restore_to_temp(path, parent)
            previous = _read_identity(path)
        if manifest["stage"] == "analyzed":
            require(prior["stage"] == "collected" and prior["run_id"] == manifest["run_id"],
                    "custody_analysis_parent_mismatch")
        else:
            require(prior["run_id"] != manifest["run_id"], "custody_new_collection_run_required")
        _continuity(previous, identity, manifest["stage"], manifest["run_id"])
        manifest, identity = prior, previous


class RehearsalCustodySession:
    """Coordinator-backed application seam, intentionally restricted to fixtures.

    The transport owns immutable objects, run/stage claims and the CAS head.
    Local working files are disposable. An empty store needs explicit consent
    by the rehearsal caller; a missing pointer never creates a fallback DB.
    """

    def __init__(self, coordinator, root, *, run_id=None, logical_date=None, enabled=False):
        require(enabled is True, "custody_disabled")
        require(isinstance(coordinator, EvidenceObjectCoordinator),
                "custody_coordinator_required")
        self.root = _scratch_root(root)
        execution = execution_identity(self.root, run_id, logical_date)
        self._database_path = self.root / "working.sqlite"
        self.coordinator = coordinator
        self.run_id = execution["execution_id"]
        self.logical_date = execution["logical_date"]
        self._started = False
        self._parent = None
        self._collected = None
        self._completed = None
        self._finished = False

    def validate_runtime(self):
        self.validate_binding(self.database_path)
        require(self._started and self.database_path.is_file(), "custody_working_database_missing")
        if self._completed is not None:
            verify_snapshot(self.database_path, self._completed)
        connection = sqlite3.connect(self.database_path.as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("BEGIN")
            application_identity(connection)
        finally:
            connection.close()

    @contextmanager
    def application(self, *, read_only=False):
        """Bind actual DAO/atomic-batch paths to this verified working copy."""
        from storage import db
        context = db.DatabaseContext(self.database_path, self.validate_runtime,
                                     self.run_id, self.logical_date,
                                     read_only or self._finished or self._completed is not None)
        with db.use_database_context(context):
            yield context

    def validate_binding(self, database_path):
        _scratch_root(self.root)
        require((self.root / "execution.json").is_file(), "custody_execution_invalid")
        execution_identity(self.root, self.run_id, self.logical_date)
        require(self.database_path == self.root / "working.sqlite" and
                Path(database_path).absolute() == self.database_path and
                not self.database_path.is_symlink() and
                (not self.database_path.exists() or self.database_path.stat().st_nlink == 1),
                "custody_database_binding")

    @property
    def database_path(self):
        return self._database_path

    def _report(self, manifest=None, **extra):
        return {"schema": REPORT_SCHEMA, "run_id": self.run_id,
                "logical_date": self.logical_date,
                "generation": manifest["generation"] if manifest else None,
                "stage": manifest["stage"] if manifest else None,
                "eligible_for_publication": False, **extra}

    def bootstrap(self, *, allow_empty=False, recover_stage=None):
        """Restore a verified current generation into a NEW application DB."""
        self.validate_binding(self.database_path)
        require(not self._started and not self.database_path.exists(),
                "custody_bootstrap_target_exists")
        require(not any(Path(str(self.database_path) + suffix).exists()
                        for suffix in ("-wal", "-shm", "-journal")),
                "custody_bootstrap_sidecar_exists")
        active, _ = self.coordinator.current()
        validate_initialized = getattr(self.coordinator, "validate_initialized", None)
        if validate_initialized is not None and (active is not None or recover_stage is not None):
            validate_initialized()
        if recover_stage is not None:
            # Explicitly recover one durable prepared claim. Validate its full
            # history/mapping BEFORE CAS; an orphan or stale stage is not head.
            prepared = self.coordinator.claimed_generation(self.run_id, recover_stage)
            recovery = self.root / "recovery.sqlite"
            self.restore(recovery, prepared["generation"])
            recovery.unlink()
            self.coordinator.advance(prepared["generation"], prepared["parent"])
            active, _ = self.coordinator.current()
            require(active is not None and active["generation"] == prepared["generation"],
                    "custody_checkpoint_superseded")
        if active is None:
            require(allow_empty is True, "custody_current_required")
            initialize = getattr(self.coordinator, "initialize_empty", None)
            if initialize is not None:
                initialize()  # Initialized pointer disappearance never bootstraps.
            try:
                descriptor = os.open(str(self.database_path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                os.close(descriptor)
            except FileExistsError:
                raise EvidenceContractError("custody_bootstrap_target_exists") from None
            connection = sqlite3.connect(str(self.database_path))
            try:
                connection.execute("CREATE TABLE ipr_custody_fixture(marker TEXT NOT NULL)")
                connection.execute("INSERT INTO ipr_custody_fixture VALUES(?)", (FIXTURE_TOKEN,))
                connection.execute(EXECUTION_SQL)
                connection.commit()
            finally:
                connection.close()
            manifest = None
        else:
            staging = self.root / "bootstrap.sqlite"
            manifest = self.restore(staging, active["generation"])
            try:
                # A restarted attempt may resume its collection generation;
                # a completed run ID cannot silently acquire another payload.
                os.link(staging, self.database_path)
            except FileExistsError:
                raise EvidenceContractError("custody_bootstrap_target_exists") from None
            finally:
                staging.unlink(missing_ok=True)
            self._parent = manifest["generation"]
            if manifest["run_id"] == self.run_id:
                if manifest["stage"] == "collected":
                    self._collected = manifest["generation"]
                    self._parent = manifest["parent"]
                else:
                    self._completed = manifest
                    self._finished = True
                    self._collected = manifest["parent"]
        self._started = True
        return self._report(manifest, restored=manifest is not None,
                            completed=self._completed is not None)

    def restore(self, destination, generation=None):
        """Historical restore validates the native schema without advancing head."""
        _scratch_root(self.root)
        dest = Path(destination)
        require(dest.parent.resolve() == self.root and not dest.parent.is_symlink(),
                "custody_restore_destination")
        require(not any(Path(str(dest) + suffix).exists() or
                        Path(str(dest) + suffix).is_symlink()
                        for suffix in ("-wal", "-shm", "-journal")),
                "custody_restore_sidecar_exists")
        manifest = self.coordinator.restore_to_temp(dest, generation)
        try:
            identity = _read_identity(dest.resolve())
            _verify_history(self.coordinator, manifest, identity)
            connection = sqlite3.connect(dest.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
            try:
                row = connection.execute("SELECT native_run_id,logical_date FROM ipr_custody_execution "
                                         "WHERE execution_id=?", (manifest["run_id"],)).fetchone()
                require(row is not None and type(row[0]) is int and row[0] > 0,
                        "custody_execution_mapping_missing")
                if manifest["run_id"] == self.run_id:
                    require(row[1] == self.logical_date, "custody_execution_conflict")
            finally:
                connection.close()
        except EvidenceContractError:
            dest.unlink(missing_ok=True)
            raise
        except Exception:
            dest.unlink(missing_ok=True)
            raise EvidenceContractError("custody_restore_invalid") from None
        return manifest

    def checkpoint(self, stage):
        """Snapshot committed native rows, prove continuity, claim and CAS head."""
        require(self._started, "custody_startup_required")
        require(stage in ("collected", "analyzed"), "custody_stage_invalid")
        require(not self._finished or stage == "analyzed", "custody_run_already_analyzed")
        if self._completed is not None:
            require(stage == "analyzed", "custody_run_already_analyzed")
            # A completed restart is read-only and returns the durable claim.
            self.validate_runtime()
            return self._report(self._completed, advanced=False, completed=True)
        self.validate_binding(self.database_path)
        require(self.database_path.is_file(), "custody_working_database_missing")
        parent = self._parent if stage == "collected" else self._collected
        require(stage != "analyzed" or parent is not None,
                "custody_collection_required")
        with tempfile.TemporaryDirectory(prefix="ipr-custody-checkpoint-") as tmp:
            snapshot = Path(tmp) / "snapshot.sqlite"
            # A separate connection includes committed WAL data,
            # excludes another connection's uncommitted transaction, and does
            # not commit or roll back any application transaction.
            # mode=rw never creates a missing database and lets SQLite rebuild
            # WAL coordination files after a restore. No SQL writes here.
            connection = sqlite3.connect(self.database_path.as_uri() + "?mode=rw", uri=True)
            try:
                _fictional(connection)
                row = connection.execute("SELECT native_run_id,logical_date FROM ipr_custody_execution "
                                         "WHERE execution_id=?", (self.run_id,)).fetchone()
                require(row is not None and row[1] == self.logical_date,
                        "custody_execution_mapping_missing")
                capture_backup(connection, snapshot)
            finally:
                connection.close()
            identity = _read_identity(snapshot)
            if parent is not None:
                # Use a distinct temporary destination, not an old local cache.
                with tempfile.TemporaryDirectory(prefix="ipr-custody-parent-") as history:
                    prior_path = Path(history) / "parent.sqlite"
                    prior = self.coordinator.restore_to_temp(prior_path, parent)
                    if stage == "analyzed":
                        require(prior["stage"] == "collected" and
                                prior["run_id"] == self.run_id,
                                "custody_analysis_parent_mismatch")
                    else:
                        require(prior["run_id"] != self.run_id,
                                "custody_new_collection_run_required")
                    _continuity(_read_identity(prior_path), identity, stage, self.run_id)
            manifest = manifest_for_backup(snapshot, run_id=self.run_id,
                                           stage=stage, parent=parent)
            self.coordinator.prepare(snapshot, manifest)
            advanced = self.coordinator.advance(manifest["generation"], parent)
            # Read back even a successful CAS before acknowledging durability.
            active, _ = self.coordinator.current()
            require(active is not None and active["generation"] == manifest["generation"],
                    "custody_checkpoint_superseded")
        if stage == "collected":
            self._collected = manifest["generation"]
        else:
            self._finished = True
        return self._report(manifest, advanced=advanced,
                            native_run_id=row[0], schema_sha256=identity["schema"],
                            record_ids_sha256=identity["record_ids_sha256"],
                            preserved_rows_sha256=identity["preserved_rows_sha256"])
