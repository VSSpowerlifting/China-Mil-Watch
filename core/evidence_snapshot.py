"""IPR S2.1 immutable SQLite snapshot contract. OFFLINE, NO LIVE WIRING.

Manifests describe technical custody, not retention/publication permission.
Diagnostics use fixed codes only; no captured source prose is emitted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path

SCHEMA = "ipr-evidence-snapshot/1"
REF_SCHEMA = "ipr-evidence-current/1"
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
ID_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,95}\Z")
STAGES = frozenset({"collected", "analyzed", "rehearsal"})
FIELDS = frozenset({
    "schema", "generation", "parent", "run_id", "stage", "snapshot_sha256",
    "snapshot_bytes", "sqlite_user_version", "article_count", "max_article_id",
})
REF_FIELDS = frozenset({"schema", "generation", "manifest_sha256"})


class EvidenceContractError(ValueError):
    """Safe error codes, never caller-controlled content."""


def require(condition, code):
    if not condition:
        raise EvidenceContractError(code)


def digest_bytes(content):
    return hashlib.sha256(content).hexdigest()


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def _identifier(value):
    return type(value) is str and bool(ID_PATTERN.fullmatch(value))


def _sha(value):
    return type(value) is str and bool(SHA_PATTERN.fullmatch(value))


def validate_manifest(manifest):
    require(type(manifest) is dict and set(manifest) == FIELDS, "manifest_fields")
    require(manifest["schema"] == SCHEMA, "manifest_schema")
    require(_sha(manifest["generation"]), "generation_format")
    require(manifest["parent"] is None or _sha(manifest["parent"]), "parent_format")
    require(_identifier(manifest["run_id"]), "run_id_format")
    require(type(manifest["stage"]) is str and manifest["stage"] in STAGES,
            "stage_invalid")
    require(_sha(manifest["snapshot_sha256"]), "snapshot_digest_format")
    for key in ("snapshot_bytes", "sqlite_user_version", "article_count",
                "max_article_id"):
        require(type(manifest[key]) is int and manifest[key] >= 0, "manifest_numbers")
    require(manifest["snapshot_bytes"] > 0, "snapshot_empty")
    require((manifest["article_count"] == 0 and manifest["max_article_id"] == 0) or
            (manifest["article_count"] > 0 and
             manifest["max_article_id"] >= manifest["article_count"]),
            "article_metadata_invalid")
    unsigned = {key: value for key, value in manifest.items() if key != "generation"}
    require(manifest["generation"] == digest_bytes(
        b"IPR-S2-GENERATION-V1\0" + canonical_bytes(unsigned)),
        "generation_mismatch")
    require(manifest["parent"] != manifest["generation"], "self_parent")
    return manifest


def validate_ref(ref):
    require(type(ref) is dict and set(ref) == REF_FIELDS, "ref_fields")
    require(ref["schema"] == REF_SCHEMA and _sha(ref["generation"]) and
            _sha(ref["manifest_sha256"]), "ref_invalid")
    return ref


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def parse_manifest(content):
    try:
        obj = json.loads(content, object_pairs_hook=_unique_keys)
        return validate_manifest(obj)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, EvidenceContractError):
            raise
        raise EvidenceContractError("manifest_parse_invalid") from None


def parse_ref(content):
    try:
        obj = json.loads(content, object_pairs_hook=_unique_keys)
        return validate_ref(obj)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, EvidenceContractError):
            raise
        raise EvidenceContractError("ref_parse_invalid") from None


def inspect_database(database):
    """Read-only structural audit; requires stable positive article IDs."""
    try:
        integrity = database.execute("PRAGMA integrity_check").fetchone()
        require(integrity is not None and integrity[0] == "ok", "sqlite_integrity")
        require(database.execute("PRAGMA foreign_key_check").fetchone() is None,
                "sqlite_foreign_keys")
        columns = {r[1] for r in database.execute("PRAGMA table_info(articles)")}
        require("id" in columns, "articles_id_missing")
        count, min_id, max_id = database.execute(
            "SELECT count(*), min(id), max(id) FROM articles").fetchone()
        require(type(count) is int and type(max_id) in (type(None), int) and
                (count == 0 or (min_id > 0 and max_id >= count)),
                "articles_identity_invalid")
        version = database.execute("PRAGMA user_version").fetchone()[0]
        require(type(version) is int and version >= 0, "sqlite_version_invalid")
        return {"sqlite_user_version": version, "article_count": count,
                "max_article_id": max_id or 0}
    except sqlite3.DatabaseError:
        raise EvidenceContractError("sqlite_invalid") from None


def capture_backup(connection, destination):
    """WAL-consistent online backup. Source connection is caller-owned."""
    path = Path(destination)
    require(not path.exists() and not path.is_symlink(), "backup_target_exists")
    require(path.parent.is_dir() and not path.parent.is_symlink(),
            "backup_parent_invalid")
    target = None
    created = False
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(fd)
        created = True
        target = sqlite3.connect(str(path))
        connection.backup(target, pages=64, sleep=0.05)
        inspect_database(target)
        target.close()
        return path
    except (sqlite3.Error, EvidenceContractError, OSError):
        if target is not None:
            target.close()
        if created:
            path.unlink(missing_ok=True)
        raise EvidenceContractError("backup_failed") from None


def manifest_for_backup(snapshot, *, run_id, stage, parent=None):
    require(_identifier(run_id) and type(stage) is str and stage in STAGES,
            "snapshot_identity_invalid")
    require(parent is None or _sha(parent), "parent_format")
    path = Path(snapshot)
    require(path.is_file() and not path.is_symlink(), "snapshot_unavailable")
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path.as_posix(), uri=True)
        try:
            info = inspect_database(con)
        finally:
            con.close()
        unsigned = {"schema": SCHEMA, "parent": parent, "run_id": run_id,
                    "stage": stage, "snapshot_sha256": digest_file(path),
                    "snapshot_bytes": path.stat().st_size, **info}
    except (sqlite3.Error, OSError):
        raise EvidenceContractError("snapshot_unreadable") from None
    generation = digest_bytes(
        b"IPR-S2-GENERATION-V1\0" + canonical_bytes(unsigned))
    return validate_manifest({"generation": generation, **unsigned})


def verify_snapshot(snapshot, manifest):
    validate_manifest(manifest)
    path = Path(snapshot)
    require(path.is_file() and not path.is_symlink(), "snapshot_unavailable")
    try:
        require(path.stat().st_size == manifest["snapshot_bytes"] and
                digest_file(path) == manifest["snapshot_sha256"],
                "snapshot_digest_mismatch")
        con = sqlite3.connect("file:%s?mode=ro" % path.as_posix(), uri=True)
        try:
            values = inspect_database(con)
        finally:
            con.close()
        require(all(values[name] == manifest[name] for name in values),
                "snapshot_metadata_mismatch")
    except (sqlite3.Error, OSError):
        raise EvidenceContractError("snapshot_unreadable") from None
    return manifest
