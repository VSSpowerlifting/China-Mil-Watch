#!/usr/bin/env python3
"""Issue #168: read-only, fail-closed P25-P36 frozen Singapore production replay.

Only the pinned historical commit's blob and frozen pilot ledger are admissible.
Temporary SQLite copy is immutable; no source bodies are logged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

COMMIT = "4efa9c086f70ae3fe4d24720754f323c8e393ebf"
DB_PATH = "pla_watch.db"
DB_BLOB = "4ad8cda873c5ed31b5ff009ac90271fd629f78ed"
LEDGER_BLOB = "a4af23d199550df81b7e8292afda2c6e330a8cc5"
IDS = tuple("P%d" % n for n in range(25, 37))
EMPTY_HASH = hashlib.sha256(b"").hexdigest()

class VerificationError(RuntimeError):
    pass

def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise VerificationError("git %s failed: %s" %
                                (" ".join(args), p.stderr.decode("utf-8", "replace").strip()))
    return p.stdout

def pinned_blob(repo, oid):
    if git(repo, "cat-file", "-t", oid).strip() != b"blob":
        raise VerificationError("pinned object is not a blob: " + oid)
    payload = git(repo, "cat-file", "blob", oid)
    actual = hashlib.sha1(b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload).hexdigest()
    if actual != oid:
        raise VerificationError("Git blob identity mismatch: " + oid)
    return payload

def load_pilot(source):
    ledger = json.loads(source.decode("utf-8"))
    origin = ledger.get("origins", {}).get("production")
    if not isinstance(origin, dict) or any((
        origin.get("commit") != COMMIT,
        origin.get("path") != DB_PATH,
        origin.get("blob") != DB_BLOB,
    )):
        raise VerificationError("frozen origin metadata differs from exact pinned object")
    selected = [p for p in ledger.get("records", []) if p.get("pilot_id") in IDS]
    if len(selected) != 12 or {p["pilot_id"] for p in selected} != set(IDS):
        raise VerificationError("missing or repeated P25-P36 frozen pilot ID")
    found = {p["pilot_id"]: p for p in selected}
    seen_urls = set()
    for ident in IDS:
        p = found[ident]
        url = p.get("canonical_url")
        if (p.get("origin") != "production" or p.get("storage_layer") != "production"
                or p.get("desk_id") != "singapore"
                or p.get("source_slug") != "sg_mindef_releases"
                or p.get("review_state") != "pending"
                or not isinstance(url, str) or not url.startswith("https://www.mindef.gov.sg/")
                or p.get("row_locator") != {"table": "articles", "url": url}
                or not isinstance(p.get("record_id"), str) or not p["record_id"]
                or url in seen_urls):
            raise VerificationError(ident + " frozen source identity drift")
        seen_urls.add(url)
        chars, hash_value, snippets = p.get("body_chars"), p.get("body_sha256"), p.get("evidence")
        if (type(chars) is not int or chars < 0 or not isinstance(hash_value, str)
                or len(hash_value) != 64 or not isinstance(snippets, list)):
            raise VerificationError(ident + " malformed frozen body/evidence fields")
        if ident == "P36":
            if chars != 0 or hash_value != EMPTY_HASH or snippets:
                raise VerificationError("P36: bodyless constraint violated")
        elif chars == 0 or not snippets:
            raise VerificationError(ident + " expected nonempty body and evidence")
    return [found[i] for i in IDS]

def check_db(db_file, pilot):
    uri = db_file.as_uri() + "?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA query_only = ON")
        integrity = [r[0] for r in con.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            raise VerificationError("SQLite integrity check not ok: " + repr(integrity[:2]))
        if not any(r[0] == "articles" for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")):
            raise VerificationError("missing articles table")
        cols = {r[1] for r in con.execute("PRAGMA table_info(articles)")}
        if not {"url", "text_original"}.issubset(cols):
            raise VerificationError("missing url/text_original columns")
        result, body_count, excerpts = [], 0, 0
        for p in pilot:
            pid = p["pilot_id"]
            rows = con.execute('SELECT * FROM "articles" WHERE "url"=?',
                               (p["canonical_url"],)).fetchall()
            if len(rows) != 1:
                raise VerificationError(pid + ": exact historical URL row count " + str(len(rows)))
            row = rows[0]
            body = row["text_original"]
            if pid == "P36":
                if body not in (None, ""):
                    raise VerificationError("P36 unexpectedly contains archived body")
                state = "bodyless_not_body_verified"
                span_count = 0
                sha = EMPTY_HASH
            else:
                if not isinstance(body, str) or not body:
                    raise VerificationError(pid + ": missing body")
                if len(body) != p["body_chars"]:
                    raise VerificationError(pid + ": original character count mismatch")
                sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
                if sha != p["body_sha256"]:
                    raise VerificationError(pid + ": original body SHA-256 mismatch")
                for excerpt in p["evidence"]:
                    start, end = excerpt.get("start"), excerpt.get("end")
                    if (excerpt.get("field") != "text_original"
                            or type(start) is not int or type(end) is not int
                            or not 0 <= start < end <= len(body)
                            or body[start:end] != excerpt.get("quote")):
                        raise VerificationError(pid + ": offset/quote mismatch " +
                                                str(excerpt.get("id")))
                span_count = len(p["evidence"])
                excerpts += span_count
                body_count += 1
                state = "full_original_body_and_excerpts_verified"
            identity = {}
            for col, ledger_key in (
                ("title_original", "title_original"),
                ("published_date", "published_date"),
                ("source_slug", "source_slug"),
                ("content_hash", "stored_content_hash"),
            ):
                if col not in cols:
                    identity[col] = "column_absent"
                elif row[col] != p.get(ledger_key):
                    raise VerificationError(pid + ": stored " + col + " mismatch")
                else:
                    identity[col] = "match"
            result.append({
                "pilot_id": pid, "source_url": p["canonical_url"],
                "record_id": p["record_id"], "status": state,
                "expected_body_chars": p["body_chars"],
                "checked_body_sha256": sha,
                "excerpt_count": span_count, "stored_identity": identity,
                "human_topic_approved": False,
            })
        if len(result) != 12 or body_count != 11 or excerpts != sum(
                len(p["evidence"]) for p in pilot):
            raise VerificationError("aggregate record/body/span count mismatch")
        return {"sqlite_integrity_check": "ok", "rows_verified": 12,
                "body_records_verified": 11, "bodyless_rows_confirmed": 1,
                "excerpts_verified": excerpts, "records": result,
                "human_review_complete": False, "topic_assignment_authorized": False}
    finally:
        con.close()

def replay(repo):
    if git(repo, "rev-parse", "--is-inside-work-tree").strip() != b"true":
        raise VerificationError("not in a Git worktree")
    oid = git(repo, "rev-parse", "--verify", COMMIT + "^{commit}").decode().strip()
    if oid != COMMIT:
        raise VerificationError("historical commit missing")
    ref = git(repo, "rev-parse", COMMIT + ":" + DB_PATH).decode().strip()
    if ref != DB_BLOB:
        raise VerificationError("pinned commit does not reference expected production DB blob")
    frozen = load_pilot(pinned_blob(repo, LEDGER_BLOB))
    data = pinned_blob(repo, DB_BLOB)
    if not data.startswith(b"SQLite format 3\x00"):
        raise VerificationError("historical DB is not SQLite3")
    with tempfile.TemporaryDirectory(prefix="ipr-168-sg-pilot-") as name:
        db_file = Path(name) / "pinned.sqlite"
        db_file.write_bytes(data)
        report = check_db(db_file, frozen)
    return {
        "scope": "read_only_historical_singapore_p25_p36",
        "historical_commit": COMMIT,
        "frozen_db_blob": DB_BLOB,
        "frozen_ledger_blob": LEDGER_BLOB,
        "historical_db_bytes": len(data),
        **report,
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True, type=Path)
    args = p.parse_args()
    try:
        print(json.dumps(replay(args.repo.resolve()), ensure_ascii=False, indent=2))
    except (VerificationError, sqlite3.Error, OSError, ValueError, KeyError, TypeError) as ex:
        print(json.dumps({"result": "FAIL_CLOSED", "error": str(ex)}, ensure_ascii=False))
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
