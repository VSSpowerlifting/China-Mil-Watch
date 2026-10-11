"""Private metadata-only editorial delivery ledger. NO email, models or publishing.

This is an R2 staging component, NOT connected to the live Sunday sender.
Use a durable, mode-0600 SQLite file OUTSIDE the repository. The stable
private HMAC key is essential: rotation or lost storage must stop the process.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import stat
import sys
from datetime import date, datetime, timezone
from email.utils import parseaddr
from pathlib import Path

SCHEMA = "ipr-editor-delivery-ledger/1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
KEY_LABEL = b"IPR Sunday editorial ledger key check v1"
RESERVED = "RESERVED_NO_SEND"
UNCERTAIN = "ATTEMPT_STARTED_DELIVERY_UNCERTAIN"
ACCEPTED = "SMTP_ACCEPTED_UNCONFIRMED"
ATTESTED = "SENT_ATTESTED_BY_OPERATOR"


class LedgerRefused(ValueError):
    """Unsafe or duplicative delivery transition."""


def _week(value):
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        raise LedgerRefused("week must use exact YYYY-MM-DD")
    try:
        actual = date.fromisoformat(value)
    except ValueError as exc:
        raise LedgerRefused("invalid reporting week") from exc
    if actual.weekday() != 5:
        raise LedgerRefused("reporting week must end on Saturday")
    return value


def _sha(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise LedgerRefused("attachment digest must be lowercase SHA-256")
    return value


def _key(value):
    if not isinstance(value, str) or not (32 <= len(value) <= 512):
        raise LedgerRefused("private stable IPR_DELIVERY_LEDGER_KEY (32+ chars) required")
    return value.encode("utf-8")


def _tag(address, key):
    if not isinstance(address, str) or not address or "\r" in address or "\n" in address:
        raise LedgerRefused("one editor mailbox required")
    name, parsed = parseaddr(address)
    if name or not parsed or parsed.casefold() != address.strip().casefold():
        raise LedgerRefused("editor recipient must be one bare address")
    mailbox, sep, domain = parsed.partition("@")
    if not sep or not mailbox or "." not in domain:
        raise LedgerRefused("malformed editor mailbox")
    return hmac.new(key, parsed.casefold().encode("utf-8"), hashlib.sha256).hexdigest()


def _open(path, *, allow_initialize=False):
    path = Path(path).absolute()
    repository = Path(__file__).resolve().parents[1]
    resolved = path.resolve(strict=False)
    if resolved == repository or repository in resolved.parents:
        raise LedgerRefused("private ledger must be outside Git repository")
    if path.suffix != ".sqlite3" or not path.parent.is_dir() or path.parent.is_symlink():
        raise LedgerRefused("private ledger requires an existing private directory and .sqlite3 file")
    if stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise LedgerRefused("private ledger parent directory must not be group/world accessible")
    if path.is_symlink():
        raise LedgerRefused("symlinked ledger is prohibited")
    if path.exists():
        if not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise LedgerRefused("ledger must be a regular file with mode 0600")
    else:
        if not allow_initialize:
            raise LedgerRefused("durable ledger missing: refuse a new reservation or send")
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError as exc:
            raise LedgerRefused("concurrent first creation: inspect before proceeding") from exc
    db = sqlite3.connect(str(path), timeout=5, isolation_level=None)
    try:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("CREATE TABLE IF NOT EXISTS ledger_meta (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("""CREATE TABLE IF NOT EXISTS editions(
            week TEXT NOT NULL, recipient_tag TEXT NOT NULL,
            attachment_sha256 TEXT NOT NULL, status TEXT NOT NULL,
            attempt_token TEXT, sent_evidence TEXT,
            created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL,
            PRIMARY KEY(week,recipient_tag))""")
        return db
    except Exception:
        db.close()
        raise


def _row(db, week, tag):
    return db.execute("""SELECT attachment_sha256,status,attempt_token,
        sent_evidence,created_utc,updated_utc FROM editions
        WHERE week=? AND recipient_tag=?""", (week,tag)).fetchone()


def _result(week, record):
    if record is None:
        return dict(schema=SCHEMA,week_ending=week,status="NO_LEDGER_ENTRY",
                    automatic_retry_authorized=False,gmail_sent_independently_verified=False)
    digest,status,token,evidence,created,updated=record
    return dict(schema=SCHEMA,week_ending=week,attachment_sha256=digest,
                status=status,attempt_token_present=bool(token),
                operator_evidence_present=bool(evidence),created_utc=created,
                updated_utc=updated,automatic_retry_authorized=False,
                gmail_sent_independently_verified=False)


def transition(path, *, secret, week, recipient, action,
               attachment_sha256=None,attempt_token=None,sent_evidence=None):
    """Perform an atomic local transition; never initiate an SMTP transaction.

    start commits UNCERTAIN before a separate external SMTP attempt. Once
    started, no automatic second attempt is possible, even after a crash.
    """
    if action not in ("initialize","inspect","reserve","start","smtp-accepted","sent-attested"):
        raise LedgerRefused("unsupported transition")
    key = _key(secret)
    _week(week)
    _tag(recipient,key)
    if action == "inspect" and not Path(path).exists():
        return {**_result(week,None), "status": "LEDGER_MISSING_STOP"}
    if action == "initialize" and Path(path).exists():
        raise LedgerRefused("ledger already exists: initializing again could hide earlier attempts")
    db = _open(path,allow_initialize=(action=="initialize"))
    try:
        db.execute("BEGIN IMMEDIATE")
        tag = _tag(recipient,key)
        key_digest = hmac.new(key,KEY_LABEL,hashlib.sha256).hexdigest()
        prior = db.execute("SELECT value FROM ledger_meta WHERE name='key_check'").fetchone()
        if prior and not hmac.compare_digest(prior[0],key_digest):
            raise LedgerRefused("ledger key changed; earlier recipient identities cannot be checked")
        if prior is None:
            db.execute("INSERT INTO ledger_meta(name,value) VALUES('key_check',?)",(key_digest,))
        old = _row(db,week,tag)
        stamp=datetime.now(timezone.utc).isoformat(timespec="seconds")
        if action in ("inspect","initialize"):
            pass
        elif action == "reserve":
            digest=_sha(attachment_sha256)
            if old:
                raise LedgerRefused("edition already reserved or attempted: duplicate blocked")
            db.execute("""INSERT INTO editions
                (week,recipient_tag,attachment_sha256,status,created_utc,updated_utc)
                VALUES (?,?,?,?,?,?)""",(week,tag,digest,RESERVED,stamp,stamp))
        elif old is None:
            raise LedgerRefused("edition has not been reserved")
        elif not hmac.compare_digest(old[0],_sha(attachment_sha256)):
            raise LedgerRefused("original attachment bytes differ from reserved digest")
        elif action == "start":
            if old[1] != RESERVED:
                raise LedgerRefused("previous SMTP attempt possible: inspect Gmail Sent before any retry")
            token=secrets.token_hex(16)
            db.execute("""UPDATE editions SET status=?,attempt_token=?,updated_utc=?
                          WHERE week=? AND recipient_tag=?""",
                       (UNCERTAIN,token,stamp,week,tag))
        elif action == "smtp-accepted":
            if old[1] != UNCERTAIN or not attempt_token or not hmac.compare_digest(attempt_token,old[2] or ""):
                raise LedgerRefused("SMTP acceptance requires matching original attempt token")
            db.execute("UPDATE editions SET status=?,updated_utc=? WHERE week=? AND recipient_tag=?",
                       (ACCEPTED,stamp,week,tag))
        elif action == "sent-attested":
            if old[1] not in (UNCERTAIN,ACCEPTED) or not attempt_token or not hmac.compare_digest(attempt_token,old[2] or ""):
                raise LedgerRefused("operator attestation must match an earlier attempt")
            if not isinstance(sent_evidence,str) or not re.fullmatch(r"[A-Za-z0-9_:-]{8,160}",sent_evidence):
                raise LedgerRefused("a safe observed Sent message identifier is required")
            db.execute("""UPDATE editions SET status=?,sent_evidence=?,updated_utc=?
                          WHERE week=? AND recipient_tag=?""",
                       (ATTESTED,sent_evidence,stamp,week,tag))
        fresh=_row(db,week,tag)
        db.execute("COMMIT")
        out=_result(week,fresh)
        if action == "initialize":
            out["status"]="LEDGER_INITIALIZED_NO_EDITION"
        if action == "start":
            out["attempt_token"]=fresh[2]  # private operator only; never public log
        return out
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize","inspect","reserve","start","smtp-accepted","sent-attested"))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--week-ending",required=True)
    parser.add_argument("--recipient",required=True)
    parser.add_argument("--attachment-sha256")
    parser.add_argument("--attempt-token")
    parser.add_argument("--sent-evidence")
    args=parser.parse_args(argv)
    try:
        result=transition(args.ledger,secret=os.environ.get("IPR_DELIVERY_LEDGER_KEY",""),
            week=args.week_ending,recipient=args.recipient,action=args.action,
            attachment_sha256=args.attachment_sha256,
            attempt_token=args.attempt_token,sent_evidence=args.sent_evidence)
    except (LedgerRefused,OSError,sqlite3.Error) as exc:
        parser.exit(2,"LEDGER REFUSED: "+str(exc)+"\n")
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
