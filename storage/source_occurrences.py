"""Explicit owner-only local SQLite metadata ledger, never a production DAO."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from core.source_occurrences import (
    OccurrenceError, batch_from_dict, canonical, digest, require, validate_batch,
)

ROOT = Path(__file__).resolve().parents[1]
APPLICATION_ID = 0x4950524F


def private_path(path, *, existing=False):
    """Require an explicit external regular destination and private parent.

    Reject symlinks at every supplied path component, Git checkouts, hardlinked
    files and permissive parents. No chmod, permission grant or overwrite.
    """
    path = Path(os.path.abspath(path))
    require(not any(p.is_symlink() for p in (path, *path.parents)), "unsafe_private_path")
    require(path != ROOT and ROOT not in path.parents and
            not any((p / ".git").exists() for p in path.parents), "repository_destination_refused")
    require(path.parent.is_dir() and path.parent.stat().st_uid == os.getuid() and
            not path.parent.stat().st_mode & 0o077, "private_parent_required")
    if existing:
        require(path.is_file() and path.stat().st_uid == os.getuid() and
                not path.stat().st_mode & 0o077 and path.stat().st_nlink == 1,
                "private_file_required")
    else:
        require(not path.exists(), "destination_exists")
    for suffix in ("-wal", "-shm", "-journal"):
        require(not Path(str(path) + suffix).is_symlink(), "unsafe_private_path")
    return path


def write_report(path, text):
    path = private_path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(path), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        raise OccurrenceError("report_write_failed") from None


@contextmanager
def connection(path):
    path = private_path(path, existing=True)
    con = None
    try:
        con = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=15)
        con.execute("PRAGMA foreign_keys=ON")
        require(con.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID and
                con.execute("PRAGMA user_version").fetchone()[0] == 1,
                "not_occurrence_ledger")
        require(con.execute("PRAGMA quick_check").fetchone()[0] == "ok", "ledger_corrupt")
        yield con
    except sqlite3.Error:
        raise OccurrenceError("ledger_database_error") from None
    finally:
        if con is not None:
            con.close()


def initialize(path):
    path = private_path(path)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.close(fd)
    con = None
    try:
        con = sqlite3.connect(str(path))
        con.execute("PRAGMA journal_mode=DELETE")
        con.execute("PRAGMA application_id=%d" % APPLICATION_ID)
        con.execute("PRAGMA user_version=1")
        con.execute("""CREATE TABLE batches (
            batch_key_sha256 TEXT PRIMARY KEY,
            execution_sha256 TEXT NOT NULL UNIQUE,
            payload_sha256 TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            committed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        con.commit()
    except sqlite3.Error:
        raise OccurrenceError("ledger_initialize_failed") from None
    finally:
        if con is not None:
            con.close()


def commit_batch(path, batch):
    """Reserve one identity and atomically accept every observation or none.

    BEGIN IMMEDIATE and the unique key arbitrate real process races. Retry of
    exactly identical metadata is a no-op; changed inputs/code/snapshot need a
    new explicit batch identity. No volatile timestamp enters the fingerprint.
    """
    validate_batch(batch)
    payload = canonical(batch.as_dict())
    sha = digest(payload)
    with connection(path) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            prior = con.execute("SELECT payload_sha256, metadata_json FROM batches "
                                "WHERE batch_key_sha256=?", (batch.batch_key_sha256,)).fetchone()
            if prior:
                require(digest(prior[1]) == prior[0], "ledger_payload_corrupt")
                prior_batch = batch_from_dict(json.loads(prior[1]))
                old, new = prior_batch.as_dict(), batch.as_dict()
                # Content-bound code identity is authoritative. An unrelated
                # Git commit does not turn identical replay into a revision;
                # preserve the first execution's informational Git locator.
                old.pop("code_git_head")
                new.pop("code_git_head")
                require(canonical(old) == canonical(new), "batch_revision_conflict")
                con.rollback()
                return False
            con.execute("INSERT INTO batches(batch_key_sha256,execution_sha256,payload_sha256,"
                        "metadata_json) VALUES(?,?,?,?)",
                        (batch.batch_key_sha256, batch.execution_sha256, sha, payload))
            con.commit()
            return True
        except BaseException:
            con.rollback()
            raise


def read_batches(path):
    result = []
    with connection(path) as con:
        for key, execution, sha, payload in con.execute(
                "SELECT batch_key_sha256,execution_sha256,payload_sha256,metadata_json "
                "FROM batches ORDER BY batch_key_sha256"):
            require(digest(payload) == sha, "ledger_payload_corrupt")
            try:
                batch = batch_from_dict(json.loads(payload))
            except (ValueError, TypeError):
                raise OccurrenceError("ledger_payload_corrupt") from None
            require(batch.batch_key_sha256 == key and batch.execution_sha256 == execution,
                    "ledger_identity_corrupt")
            result.append(batch)
    return result
