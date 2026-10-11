"""Disabled, private-only SMTP attempt journal for one reviewed Sunday manuscript.

This module makes no network/model calls and is NOT invoked by Sunday workflows.
It records an externally validated owner's approval digest, but does not verify
that approval, source-use rights, or the manuscript. No claim of exactly-once
SMTP delivery is made: an ambiguous or crashed attempt cannot be retried.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
from datetime import date
from contextlib import closing
from pathlib import Path
from urllib.parse import quote


class DeliveryHold(ValueError):
    """A journal action lacks verified state or must be manually reconciled."""


_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_STATES = frozenset(("registered", "attempt_reserved", "smtp_accepted", "outcome_unknown", "held"))


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _digest(value, name):
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise DeliveryHold(name + " must be a lowercase SHA-256 digest")
    return value


def _recipient(value):
    if not isinstance(value, str) or "\r" in value or "\n" in value:
        raise DeliveryHold("invalid single recipient")
    value = value.strip().lower()
    if (not value or len(value) > 254 or value.count("@") != 1 or
            any((ord(c) < 33 or ord(c) == 127 or c in ",;<>") for c in value) or value.startswith("@") or
            value.endswith("@")):
        raise DeliveryHold("invalid single recipient")
    return _sha(value)


def intent_id(week, manuscript_sha256, recipient):
    """Stable identity does not incorporate approval renewal or source version."""
    try:
        day = date.fromisoformat(week)
    except (TypeError, ValueError) as exc:
        raise DeliveryHold("week must be an ISO reporting Saturday") from exc
    if day.weekday() != 5 or day.isoformat() != week:
        raise DeliveryHold("week must be an ISO reporting Saturday")
    body = _digest(manuscript_sha256, "manuscript_sha256")
    person = _recipient(recipient)
    return _sha("IPR-SUNDAY-v1\0" + week + "\0" + body + "\0" + person)


class DeliveryJournal:
    """SQLite reservation fence; no SMTP hooks, retries, or approval authority."""

    def __init__(self, db_path, *, initialize_new=False):
        """Explicit initialization only; missing/corrupt journal never resets history."""
        path = Path(db_path)
        if not path.is_absolute() or not path.name or path.name in (".", ".."):
            raise DeliveryHold("journal path must be an absolute private file")
        parent = path.parent
        if (parent.is_symlink() or not parent.is_dir() or
                stat.S_IMODE(parent.stat().st_mode) & 0o077):
            raise DeliveryHold("journal parent must exist and be owner-only (0700)")
        if parent.stat().st_uid != os.getuid():
            raise DeliveryHold("journal directory must be owned by caller")
        if path.is_symlink():
            raise DeliveryHold("journal symlink refused")
        if initialize_new:
            # A vanished prior journal is indistinguishable from a first install.
            # The caller must obtain separate owner authorization to initialize.
            # Never silently reuse this flag on normal application startup.
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(str(path), flags, 0o600)
            except FileExistsError as exc:
                raise DeliveryHold("refusing to reinitialize an existing journal") from exc
            else:
                os.close(fd)
        elif not path.exists():
            raise DeliveryHold("missing prior send journal; explicit recovery required")
        if (not path.is_file() or path.is_symlink() or
                stat.S_IMODE(path.stat().st_mode) & 0o077 or
                path.stat().st_uid != os.getuid() or
                path.stat().st_nlink != 1):
            raise DeliveryHold("journal must be caller-owned 0600 regular file without hardlinks")
        self.path = path
        with closing(self._connect()) as db, db:
            if not initialize_new:
                # SQLite treats an existing zero-byte file as a new empty store.
                # An absent schema is therefore a lost-history event, not a
                # permission to manufacture a fresh "no sends" journal.
                exists = db.execute("""SELECT 1 FROM sqlite_master
                    WHERE type='table' AND name='intents'""").fetchone()
                if exists is None:
                    raise DeliveryHold("send journal schema missing; recovery required")
            else:
                db.execute("""CREATE TABLE intents (
                identity TEXT PRIMARY KEY,
                reporting_week TEXT NOT NULL,
                manuscript_sha256 TEXT NOT NULL,
                source_receipt_sha256 TEXT NOT NULL,
                recipient_sha256 TEXT NOT NULL,
                owner_approval_sha256 TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN
                    ('registered','attempt_reserved','smtp_accepted','outcome_unknown','held')),
                revision INTEGER NOT NULL DEFAULT 0,
                smtp_receipt_sha256 TEXT,
                UNIQUE(reporting_week, recipient_sha256)
            )""")
            # A structural schema probe is not equivalent to authenticating
            # data. The private directory and independent backup are assumed.
            columns = [row[1] for row in db.execute("PRAGMA table_info(intents)")]
            expected = [
                "identity", "reporting_week", "manuscript_sha256",
                "source_receipt_sha256", "recipient_sha256",
                "owner_approval_sha256", "state", "revision", "smtp_receipt_sha256",
            ]
            if columns != expected:
                raise DeliveryHold("send journal schema mismatch; manual review required")
            # Old journals with identical columns but no per-week uniqueness
            # could silently allow a second draft. Refuse until a separately
            # governed migration/reconciliation is approved.
            protected = False
            for item in db.execute('PRAGMA index_list("intents")'):
                if not item[2]:
                    continue
                quoted = item[1].replace('"', '""')
                names = tuple(
                    row[2] for row in db.execute(
                        'PRAGMA index_info("' + quoted + '")'
                    )
                )
                if names == ("reporting_week", "recipient_sha256"):
                    protected = True
                    break
            if not protected:
                raise DeliveryHold("journal missing week-recipient uniqueness; recovery required")

    def _connect(self):
        # mode=rw forbids creating an alternate database through SQLite.
        uri = "file:" + quote(str(self.path), safe="/") + "?mode=rw"
        db = sqlite3.connect(uri, uri=True, timeout=15)
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def register(self, *, week, manuscript_sha256, source_receipt_sha256,
                 recipient, owner_approval_sha256):
        """Record verified-offline inputs. Caller must authenticate approval."""
        key = intent_id(week, manuscript_sha256, recipient)
        source = _digest(source_receipt_sha256, "source_receipt_sha256")
        approval = _digest(owner_approval_sha256, "owner_approval_sha256")
        person = _recipient(recipient)
        values = (key, week, manuscript_sha256, source, person, approval)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT reporting_week,manuscript_sha256,
                source_receipt_sha256,recipient_sha256,owner_approval_sha256
                FROM intents WHERE identity=?""", (key,)).fetchone()
            if row is not None:
                if row != values[1:]:
                    raise DeliveryHold("existing reviewed intent conflicts; do not replace")
                return key  # Exact repeat is a read, never resets a send state.
            # A different manuscript digest for the *same* Saturday and
            # recipient must not manufacture a second delivery allowance.
            # A correction/replacement needs an independently authorized
            # operator protocol; there is no reset method in this module.
            try:
                db.execute("""INSERT INTO intents(identity,reporting_week,
                    manuscript_sha256,source_receipt_sha256,recipient_sha256,
                    owner_approval_sha256,state) VALUES (?,?,?,?,?,?,'registered')""", values)
            except sqlite3.IntegrityError as exc:
                raise DeliveryHold(
                    "a different manuscript already claims this week/recipient; manual hold"
                ) from exc
        return key

    def _transition(self, key, old, new, receipt=None):
        if not isinstance(key, str) or not _DIGEST.fullmatch(key):
            raise DeliveryHold("invalid intent identity")
        if old not in _STATES or new not in _STATES:
            raise DeliveryHold("invalid journal state")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM intents WHERE identity=?", (key,)).fetchone()
            if row is None or row[0] != old:
                raise DeliveryHold("unknown, already attempted or held; manual review required")
            db.execute("""UPDATE intents SET state=?, revision=revision+1,
                smtp_receipt_sha256=? WHERE identity=? AND state=?""",
                       (new, receipt, key, old))
        return new

    def reserve_attempt(self, key):
        """Once reserved, never automatically re-arm—even after a crash."""
        return self._transition(key, "registered", "attempt_reserved")

    def record_smtp_acceptance(self, key, smtp_receipt_sha256):
        """Server acceptance only; not proof of delivery, human reading, or rights."""
        receipt = _digest(smtp_receipt_sha256, "smtp_receipt_sha256")
        return self._transition(key, "attempt_reserved", "smtp_accepted", receipt)

    def mark_unknown(self, key):
        """Uncertain network outcome is an irreversible automatic retry hold."""
        return self._transition(key, "attempt_reserved", "outcome_unknown")

    def hold_before_send(self, key):
        return self._transition(key, "registered", "held")

    def state(self, key):
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT state FROM intents WHERE identity=?", (key,)).fetchone()
        if row is None:
            raise DeliveryHold("unknown intent")
        return row[0]
