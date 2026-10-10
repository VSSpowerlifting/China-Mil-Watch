"""Persistent POSIX fictional transport, never a provider/security boundary.

Only explicitly enabled dedicated temporary roots are accepted. Objects survive
new coordinator instances/processes while that root exists. File streaming is
bounded; metadata uses the existing conditional-object protocol. A real provider
must independently implement these semantics, permissions and retention.
"""
from __future__ import annotations

import fcntl
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, digest_bytes, parse_manifest,
    require, validate_manifest, verify_snapshot,
)
from storage.evidence_object_protocol import EvidenceObjectCoordinator, ConditionalObjectStore

CHUNK_BYTES = 256 * 1024
METADATA_BYTES = 64 * 1024
DEFAULT_CAPACITY = 256 * 1024 * 1024


class StreamingConditionalStore(ConditionalObjectStore, Protocol):
    """File methods supplement get/put_new/cas for bounded-memory snapshots."""

    capacity: int

    def put_file(self, key: str, source: Path) -> bool: ...
    def get_file(self, key: str, destination: Path) -> None: ...
    def is_empty(self) -> bool: ...


def sync_directory(path):
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class FictionalFileStore:
    """Atomic create, opaque-revision CAS and durable streaming under flock.

    One lock serializes cooperating writers across processes. A UUID revision
    stored WITH each payload prevents ABA across restarts. Link/replace occurs
    only after fsync; failures may leave unreferenced staging files, never a
    partial visible object. No cleanup of ambiguous interrupted state is implicit.
    """

    def __init__(self, root, *, enabled=False, capacity=DEFAULT_CAPACITY):
        require(enabled is True, "custody_disabled")
        require(type(capacity) is int and 0 < capacity <= 1024 * 1024 * 1024,
                "custody_capacity_invalid")
        self.root = Path(root).absolute()
        self.capacity = capacity
        self._validate_root()

    def _validate_root(self):
        temp = Path(tempfile.gettempdir()).resolve()
        require(self.root.is_dir() and not self.root.is_symlink() and
                temp in self.root.resolve().parents and
                self.root.name.startswith("ipr-custody-"), "custody_store_root")
        probe = self.root
        while probe.resolve() != temp:
            require(not probe.is_symlink(), "custody_store_root")
            probe = probe.parent

    @contextmanager
    def _locked(self):
        self._validate_root()
        try:
            fd = os.open(str(self.root / ".objects.lock"),
                         os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        except OSError:
            raise EvidenceContractError("custody_store_unavailable") from None

    def _path(self, key):
        require(type(key) is str and 0 < len(key) <= 200 and key.isascii(),
                "custody_object_key")
        path = self.root / (digest_bytes(key.encode("ascii")) + ".object")
        require(not path.is_symlink(), "custody_object_unsafe")
        return path

    @staticmethod
    def _open(path):
        require(path.is_file() and path.stat().st_nlink == 1,
                "custody_object_unsafe")
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
        return os.fdopen(fd, "rb")

    @staticmethod
    def _revision(stream):
        header = stream.read(33)
        require(len(header) == 33 and header[-1:] == b"\n" and
                all(c in b"0123456789abcdef" for c in header[:32]),
                "custody_object_header")
        return header[:32].decode("ascii")

    def _metadata(self, path):
        if not path.exists():
            return None
        with self._open(path) as stream:
            revision = self._revision(stream)
            data = stream.read(METADATA_BYTES + 1)
        require(len(data) <= METADATA_BYTES, "custody_metadata_capacity")
        return data, revision

    def get(self, key):
        with self._locked():
            return self._metadata(self._path(key))

    def is_empty(self):
        with self._locked():
            return not any(self.root.glob("*.object"))

    def _write(self, path, chunks, *, replace=False, limit=METADATA_BYTES):
        fd, staging = tempfile.mkstemp(prefix=".object-stage-", dir=str(self.root))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(uuid.uuid4().hex.encode("ascii") + b"\n")
                size = 0
                for chunk in chunks:
                    size += len(chunk)
                    require(size <= limit, "custody_object_capacity")
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if replace:
                os.replace(staging, path)
            else:
                os.link(staging, path)
                Path(staging).unlink()
            sync_directory(self.root)
        finally:
            Path(staging).unlink(missing_ok=True)

    def put_new(self, key, payload):
        require(type(payload) is bytes and len(payload) <= METADATA_BYTES,
                "custody_metadata_capacity")
        with self._locked():
            path = self._path(key)
            if path.exists():
                return False
            self._write(path, [payload])
            return True

    def cas(self, key, expected_revision, payload):
        require(key == EvidenceObjectCoordinator.REF_KEY, "custody_cas_key")
        require(type(payload) is bytes and len(payload) <= METADATA_BYTES,
                "custody_metadata_capacity")
        with self._locked():
            path = self._path(key)
            current = self._metadata(path)
            actual = current[1] if current else None
            if actual != expected_revision:
                return False
            self._write(path, [payload], replace=True)
            return True

    def put_file(self, key, source):
        require(key.startswith("snapshots/"), "custody_stream_key")
        with self._locked():
            path = self._path(key)
            if path.exists():
                return False
            with Path(source).open("rb") as stream:
                self._write(path, iter(lambda: stream.read(CHUNK_BYTES), b""),
                            limit=self.capacity)
            return True

    def get_file(self, key, destination):
        require(key.startswith("snapshots/"), "custody_stream_key")
        with self._locked():
            source = self._path(key)
            require(source.exists(), "snapshot_missing")
            with self._open(source) as incoming:
                self._revision(incoming)
                fd = os.open(str(destination), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    with os.fdopen(fd, "wb") as outgoing:
                        size = 0
                        for chunk in iter(lambda: incoming.read(CHUNK_BYTES), b""):
                            size += len(chunk)
                            require(size <= self.capacity, "custody_object_capacity")
                            outgoing.write(chunk)
                        outgoing.flush()
                        os.fsync(outgoing.fileno())
                except BaseException:
                    Path(destination).unlink(missing_ok=True)
                    raise


class StreamingEvidenceCoordinator(EvidenceObjectCoordinator):
    """Same manifests/CAS/claims as S2, with file transport and fresh readback.

    Integrity is rechecked, never inferred from an ETag/cache. This conservative
    implementation rereads full files on current/advance; memory is bounded but
    I/O grows with corpus and lineage. Provider performance is a later gate.
    """

    INITIALIZED_KEY = "custody/initialized.json"

    def __init__(self, transport: StreamingConditionalStore):
        require(type(getattr(transport, "capacity", None)) is int and transport.capacity > 0 and
                all(callable(getattr(transport, name, None)) for name in
                    ("get", "put_new", "cas", "get_file", "put_file", "is_empty")),
                "custody_streaming_transport_required")
        super().__init__(transport)

    def validate_initialized(self):
        data, _ = self._read(self.INITIALIZED_KEY, "custody_store_not_initialized")
        require(data == canonical_bytes({"schema": "ipr-fictional-store/1"}),
                "custody_store_format")

    def initialize_empty(self):
        require(self.transport.get(self.INITIALIZED_KEY) is None,
                "custody_initialized_pointer_missing")
        require(self.transport.is_empty(), "custody_uninitialized_objects")
        self._put_verified(self.INITIALIZED_KEY,
                           canonical_bytes({"schema": "ipr-fictional-store/1"}))

    def _manifest(self, generation):
        encoded, _ = self._read(self._manifest_key(generation), "manifest_missing")
        manifest = parse_manifest(encoded)
        require(manifest["generation"] == generation, "manifest_wrong_generation")
        claim, _ = self._read(self._claim_key(manifest), "run_claim_missing")
        require(claim == canonical_bytes({"generation": generation}), "run_stage_conflict")
        return manifest, encoded

    def prepare(self, snapshot, manifest):
        validate_manifest(manifest)
        require(manifest["snapshot_bytes"] <= self.transport.capacity,
                "custody_object_capacity")
        verify_snapshot(snapshot, manifest)
        self.transport.put_file(self._snapshot_key(manifest["snapshot_sha256"]), snapshot)
        with tempfile.TemporaryDirectory(prefix="ipr-custody-readback-") as root:
            copied = Path(root) / "snapshot.sqlite"
            self.transport.get_file(self._snapshot_key(manifest["snapshot_sha256"]), copied)
            verify_snapshot(copied, manifest)
        self._put_verified(self._manifest_key(manifest["generation"]), canonical_bytes(manifest))
        self._put_verified(self._claim_key(manifest),
                           canonical_bytes({"generation": manifest["generation"]}))
        return manifest["generation"]

    def _registered(self, generation):
        manifest, encoded = self._manifest(generation)
        with tempfile.TemporaryDirectory(prefix="ipr-custody-verify-") as root:
            copied = Path(root) / "snapshot.sqlite"
            self.transport.get_file(self._snapshot_key(manifest["snapshot_sha256"]), copied)
            verify_snapshot(copied, manifest)
        return manifest, encoded, None

    def restore_to_temp(self, destination, generation=None):
        dest = Path(destination)
        temp = Path(tempfile.gettempdir()).resolve()
        require(dest.parent.is_dir() and not dest.parent.is_symlink() and
                temp in dest.parent.resolve().parents and not dest.exists() and
                not dest.is_symlink(), "restore_destination_not_temporary")
        if generation is None:
            current, _ = self.current()
            require(current is not None, "no_current_generation")
            generation = current["generation"]
        manifest, _ = self._manifest(generation)
        staging = dest.parent / (".ipr-recover-" + uuid.uuid4().hex)
        created = False
        try:
            self.transport.get_file(self._snapshot_key(manifest["snapshot_sha256"]), staging)
            verify_snapshot(staging, manifest)
            os.link(staging, dest)
            created = True
            sync_directory(dest.parent)
        except FileExistsError:
            raise EvidenceContractError("restore_destination_exists") from None
        except BaseException as exc:
            if created:
                dest.unlink(missing_ok=True)
            if isinstance(exc, OSError):
                raise EvidenceContractError("custody_restore_io") from None
            raise
        finally:
            staging.unlink(missing_ok=True)
        return manifest
