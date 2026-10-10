"""S2.1 local scratch storage: immutable artifacts, CAS head, verified restores.

No cloud, authentication, production paths or deployment integration. The
adapter only accepts temporary-directory roots for synthetic rehearsals.
"""
from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from pathlib import Path

from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, digest_bytes, parse_manifest,
    parse_ref, require, validate_manifest, validate_ref, verify_snapshot,
    REF_SCHEMA,
)


class LocalEvidenceStore:
    """POSIX temp-directory rehearsal adapter, NOT a private security boundary."""

    def __init__(self, root):
        self.root = Path(root)
        temp_root = Path(tempfile.gettempdir()).resolve()
        require(self.root.is_dir() and not self.root.is_symlink() and
                self.root.resolve() != temp_root and
                temp_root in self.root.resolve().parents and
                self.root.name.startswith("ipr-s2-") and
                not any(p.is_symlink() for p in [self.root, *self.root.parents]),
                "unsafe_store_root")
        for sub in ("snapshots", "manifests", "refs"):
            child = self.root / sub
            child.mkdir(exist_ok=True)
            require(not child.is_symlink(), "unsafe_store_root")
        self.lock_path = self.root / ".pointer.lock"
        require(not self.lock_path.is_symlink(), "unsafe_store_root")

    @staticmethod
    def _persist_bytes(path, data):
        """Atomically create once; identical retries pass; collisions fail."""
        require(not path.is_symlink(), "symlink_artifact")
        if path.exists():
            require(path.is_file() and path.read_bytes() == data,
                    "immutable_artifact_conflict")
            return
        fd, tmp = tempfile.mkstemp(prefix=".stage-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                # Hard-link creates without clobbering an existing object.
                os.link(tmp, path)
            except FileExistsError:
                require(path.is_file() and not path.is_symlink() and
                        path.read_bytes() == data, "immutable_artifact_conflict")
            directory_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            Path(tmp).unlink(missing_ok=True)

    @staticmethod
    def _generation(generation):
        require(type(generation) is str and len(generation) == 64 and
                all(c in "0123456789abcdef" for c in generation),
                "generation_format")
        return generation

    def snapshot_path(self, sha):
        require(type(sha) is str and len(sha) == 64 and
                all(c in "0123456789abcdef" for c in sha),
                "snapshot_ref_invalid")
        return self.root / "snapshots" / (sha + ".sqlite")

    def manifest_path(self, generation):
        return self.root / "manifests" / (self._generation(generation) + ".json")

    def put_snapshot(self, source, manifest):
        validate_manifest(manifest)
        verify_snapshot(source, manifest)
        path = self.snapshot_path(manifest["snapshot_sha256"])
        require(not path.is_symlink(), "symlink_artifact")
        # Only small fictional databases are accepted during S2.1.
        require(manifest["snapshot_bytes"] <= 32 * 1024 * 1024,
                "synthetic_size_limit")
        self._persist_bytes(path, Path(source).read_bytes())
        return path

    def put_manifest(self, manifest):
        validate_manifest(manifest)
        snapshot = self.snapshot_path(manifest["snapshot_sha256"])
        verify_snapshot(snapshot, manifest)
        # Serialize run/stage uniqueness checks with other writers. An identical
        # run identity must not acquire competing snapshots under contention.
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                for prior_path in (self.root / "manifests").glob("*.json"):
                    require(not prior_path.is_symlink(), "symlink_artifact")
                    try:
                        previous = parse_manifest(prior_path.read_bytes())
                    except OSError:
                        raise EvidenceContractError("manifest_read_failed") from None
                    if (previous["run_id"], previous["stage"]) == (
                            manifest["run_id"], manifest["stage"]):
                        require(previous["generation"] == manifest["generation"],
                                "run_stage_conflict")
                path = self.manifest_path(manifest["generation"])
                self._persist_bytes(path, canonical_bytes(manifest))
                return path
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def current(self):
        path = self.root / "refs" / "current.json"
        require(not path.is_symlink(), "symlink_artifact")
        if not path.exists():
            return None
        try:
            return parse_ref(path.read_bytes())
        except OSError:
            raise EvidenceContractError("ref_read_failed") from None

    def _checked_generation(self, generation):
        path = self.manifest_path(generation)
        require(path.is_file() and not path.is_symlink(), "manifest_missing")
        try:
            data = path.read_bytes()
            manifest = parse_manifest(data)
            require(manifest["generation"] == generation, "generation_mismatch")
            verify_snapshot(self.snapshot_path(manifest["snapshot_sha256"]),
                            manifest)
            return manifest, digest_bytes(data)
        except OSError:
            raise EvidenceContractError("manifest_read_failed") from None

    def advance(self, generation, expected_parent=None):
        """Compare-and-swap the active ref after checking immutable evidence."""
        self._generation(generation)
        require(expected_parent is None or self._generation(expected_parent),
                "parent_format")
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                current = self.current()
                active = None if current is None else current["generation"]
                if current is not None:
                    _, active_digest = self._checked_generation(active)
                    require(active_digest == current["manifest_sha256"],
                            "active_manifest_digest_mismatch")
                manifest, manifest_digest = self._checked_generation(generation)
                if active == generation:
                    require(current["manifest_sha256"] == manifest_digest,
                            "ref_digest_mismatch")
                    return False
                require(active == expected_parent, "stale_generation")
                require(manifest["parent"] == expected_parent,
                        "parent_generation_mismatch")
                ref = validate_ref({"schema": REF_SCHEMA,
                                    "generation": generation,
                                    "manifest_sha256": manifest_digest})
                path = self.root / "refs" / "current.json"
                fd, tmp = tempfile.mkstemp(prefix=".new-pointer-",
                                            dir=str(path.parent))
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(canonical_bytes(ref))
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(tmp, path)
                    directory_fd = os.open(str(path.parent), os.O_RDONLY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                finally:
                    Path(tmp).unlink(missing_ok=True)
                return True
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def recover(self, destination, generation=None):
        """Verify and atomically recover an immutable generation to a new file."""
        if generation is None:
            active = self.current()
            require(active is not None, "no_current_generation")
            generation = active["generation"]
            manifest, manifest_digest = self._checked_generation(generation)
            require(manifest_digest == active["manifest_sha256"],
                    "active_manifest_digest_mismatch")
        else:
            manifest, _ = self._checked_generation(generation)
        dest = Path(destination)
        require(not dest.exists() and not dest.is_symlink() and
                dest.parent.is_dir() and not dest.parent.is_symlink() and
                self.root.resolve() not in dest.resolve().parents,
                "restore_target_invalid")
        fd, tmp = tempfile.mkstemp(prefix=".restore-", dir=str(dest.parent))
        try:
            with os.fdopen(fd, "wb") as target, self.snapshot_path(
                    manifest["snapshot_sha256"]).open("rb") as source:
                shutil.copyfileobj(source, target, length=1024 * 1024)
                target.flush()
                os.fsync(target.fileno())
            verify_snapshot(tmp, manifest)
            os.link(tmp, dest)
        except FileExistsError:
            raise EvidenceContractError("restore_target_invalid") from None
        finally:
            Path(tmp).unlink(missing_ok=True)
        return manifest
