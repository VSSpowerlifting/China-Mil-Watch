"""S2.2a: conditional object-storage contract, with fictional in-memory backend.

NO CLOUD PROVIDER, credentials, live archive, publication or network I/O.
An in-memory implementation is a test double, not an access-controlled store.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import Optional, Protocol, Tuple

from core.evidence_snapshot import (
    EvidenceContractError, REF_SCHEMA, canonical_bytes, digest_bytes,
    parse_manifest, parse_ref, require, validate_manifest, validate_ref,
    verify_snapshot,
)

MAX_SYNTHETIC_BYTES = 32 * 1024 * 1024


class ConditionalObjectStore(Protocol):
    """Required semantics for a future independently reviewed provider adapter.

    get returns (bytes, opaque revision) or None. put_new never overwrites.
    cas atomically compares revision (None means absent) before replacing.
    A provider's ordinary last-writer-wins PUT DOES NOT implement cas.
    """

    def get(self, key: str) -> Optional[Tuple[bytes, str]]: ...
    def put_new(self, key: str, payload: bytes) -> bool: ...
    def cas(self, key: str, expected_revision: Optional[str],
            payload: bytes) -> bool: ...


class InMemoryConditionalStore:
    """Synthetic-only fault-injectable, linearizable process-local test double."""

    def __init__(self):
        self._objects = {}
        self._versions = {}
        self._guard = threading.RLock()
        self._faults = {}

    def fail_next(self, operation: str, *, after_write=False):
        require(operation in ("get", "put_new", "cas"), "fault_operation_invalid")
        self._faults[(operation, after_write)] = (
            self._faults.get((operation, after_write), 0) + 1)

    def _fault(self, operation, after_write):
        key = (operation, after_write)
        pending = self._faults.get(key, 0)
        if pending:
            self._faults[key] = pending - 1
            raise EvidenceContractError("synthetic_storage_unavailable")

    def get(self, key):
        with self._guard:
            self._fault("get", False)
            if key not in self._objects:
                return None
            return self._objects[key], str(self._versions[key])

    def put_new(self, key, payload):
        with self._guard:
            self._fault("put_new", False)
            if key in self._objects:
                return False
            self._objects[key] = bytes(payload)
            self._versions[key] = 1
            self._fault("put_new", True)  # simulate lost acknowledgement
            return True

    def cas(self, key, expected_revision, payload):
        with self._guard:
            self._fault("cas", False)
            actual = str(self._versions[key]) if key in self._objects else None
            if actual != expected_revision:
                return False
            self._objects[key] = bytes(payload)
            self._versions[key] = self._versions.get(key, 0) + 1
            self._fault("cas", True)  # update occurred, acknowledgement lost
            return True

    def damage_for_test(self, key, payload):
        """Test corruption, not a valid provider method or public write path."""
        with self._guard:
            require(key in self._objects, "missing_test_object")
            self._objects[key] = bytes(payload)
            self._versions[key] += 1


class EvidenceObjectCoordinator:
    """Immutable evidence preparation, CAS current ref, verified temp restore.

    The caller must hold or procure all source-use authorization separately.
    This layer only proves mechanical persistence with fake SQLite inputs.
    """

    REF_KEY = "refs/current.json"

    def __init__(self, transport: ConditionalObjectStore):
        self.transport = transport

    @staticmethod
    def _snapshot_key(sha):
        require(type(sha) is str and len(sha) == 64 and
                all(c in "0123456789abcdef" for c in sha),
                "snapshot_digest_format")
        return "snapshots/" + sha + ".sqlite"

    @staticmethod
    def _manifest_key(generation):
        require(type(generation) is str and len(generation) == 64 and
                all(c in "0123456789abcdef" for c in generation),
                "generation_format")
        return "manifests/" + generation + ".json"

    @staticmethod
    def _claim_key(manifest):
        # Both values are tightly checked in validate_manifest (no slashes).
        return "claims/" + manifest["run_id"] + "/" + manifest["stage"] + ".json"

    def _read(self, key, missing_code):
        obj = self.transport.get(key)
        require(obj is not None, missing_code)
        data, revision = obj
        require(type(data) is bytes and type(revision) is str and
                bool(revision), "invalid_transport_reply")
        return data, revision

    def _put_verified(self, key, data):
        self.transport.put_new(key, data)
        actual, _ = self._read(key, "object_missing_after_write")
        require(actual == data, "object_readback_mismatch")

    def prepare(self, snapshot, manifest):
        """Store verified immutable bytes, manifest and atomic run/stage claim."""
        validate_manifest(manifest)
        require(manifest["snapshot_bytes"] <= MAX_SYNTHETIC_BYTES,
                "synthetic_size_limit")
        path = Path(snapshot)
        verify_snapshot(path, manifest)
        source = path.read_bytes()
        require(len(source) == manifest["snapshot_bytes"] and
                digest_bytes(source) == manifest["snapshot_sha256"],
                "snapshot_changed_during_read")
        self._put_verified(self._snapshot_key(manifest["snapshot_sha256"]), source)
        encoded = canonical_bytes(manifest)
        self._put_verified(self._manifest_key(manifest["generation"]), encoded)

        # Claim only AFTER immutable objects pass read-back. If an upload fails,
        # orphan bytes are harmless: nothing points to a partial generation.
        claim = canonical_bytes({"generation": manifest["generation"]})
        self._put_verified(self._claim_key(manifest), claim)
        return manifest["generation"]

    def _registered(self, generation):
        encoded, _ = self._read(self._manifest_key(generation), "manifest_missing")
        manifest = parse_manifest(encoded)
        require(manifest["generation"] == generation, "manifest_wrong_generation")
        claim, _ = self._read(self._claim_key(manifest), "run_claim_missing")
        require(claim == canonical_bytes({"generation": generation}),
                "run_stage_conflict")
        data, _ = self._read(self._snapshot_key(manifest["snapshot_sha256"]),
                             "snapshot_missing")
        require(len(data) == manifest["snapshot_bytes"] and
                digest_bytes(data) == manifest["snapshot_sha256"],
                "snapshot_object_corrupt")
        return manifest, encoded, data

    def inspect_generation(self, generation):
        """Public verified manifest interface; payload remains transport-private."""
        return self._registered(generation)[0]

    def claimed_generation(self, run_id, stage):
        """Locate a prepared stage for explicit recovery, never promote it."""
        from core.evidence_snapshot import ID_PATTERN, SHA_PATTERN
        import json
        require(type(run_id) is str and bool(ID_PATTERN.fullmatch(run_id)) and
                stage in ("collected", "analyzed"), "snapshot_identity_invalid")
        data, _ = self._read("claims/" + run_id + "/" + stage + ".json",
                             "run_claim_missing")
        try:
            claim = json.loads(data)
            require(type(claim) is dict and set(claim) == {"generation"} and
                    type(claim["generation"]) is str and
                    bool(SHA_PATTERN.fullmatch(claim["generation"])), "run_claim_invalid")
            require(data == canonical_bytes(claim), "run_claim_invalid")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise EvidenceContractError("run_claim_invalid") from None
        manifest = self.inspect_generation(claim["generation"])
        require(manifest["run_id"] == run_id and manifest["stage"] == stage,
                "run_stage_conflict")
        return manifest

    def current(self):
        obj = self.transport.get(self.REF_KEY)
        if obj is None:
            return None, None
        encoded, revision = obj
        require(type(encoded) is bytes and type(revision) is str and bool(revision),
                "invalid_transport_reply")
        ref = parse_ref(encoded)
        manifest, raw, _ = self._registered(ref["generation"])
        require(digest_bytes(raw) == ref["manifest_sha256"],
                "active_manifest_digest_mismatch")
        return ref, revision

    def advance(self, generation, expected_parent=None):
        """Conditional head update: never publish evidence or update Git."""
        manifest, encoded, _ = self._registered(generation)
        current, revision = self.current()
        actual_parent = None if current is None else current["generation"]
        if actual_parent == generation:
            require(current["manifest_sha256"] == digest_bytes(encoded),
                    "active_manifest_digest_mismatch")
            return False
        require(actual_parent == expected_parent, "stale_generation")
        require(manifest["parent"] == expected_parent,
                "parent_generation_mismatch")
        ref = validate_ref({"schema": REF_SCHEMA, "generation": generation,
                            "manifest_sha256": digest_bytes(encoded)})
        if not self.transport.cas(self.REF_KEY, revision, canonical_bytes(ref)):
            raise EvidenceContractError("concurrent_pointer_update")
        return True

    def restore_to_temp(self, destination, generation=None):
        """Create a verified SQLite copy in a fresh temporary-directory path."""
        dest = Path(destination)
        temp_root = Path(tempfile.gettempdir()).resolve()
        require(dest.parent.is_dir() and not dest.parent.is_symlink() and
                temp_root in dest.parent.resolve().parents and
                not dest.exists() and not dest.is_symlink(),
                "restore_destination_not_temporary")
        if generation is None:
            active, _ = self.current()
            require(active is not None, "no_current_generation")
            generation = active["generation"]
        manifest, _, data = self._registered(generation)
        fd, tmp = tempfile.mkstemp(prefix=".ipr-recover-", dir=str(dest.parent))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            verify_snapshot(tmp, manifest)
            os.link(tmp, dest)  # no clobber, even under racing restores
        except FileExistsError:
            raise EvidenceContractError("restore_destination_exists") from None
        finally:
            Path(tmp).unlink(missing_ok=True)
        return manifest
