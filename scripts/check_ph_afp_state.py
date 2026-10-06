#!/usr/bin/env python3
"""Verify completed AFP attempts before publishing isolated shadow state."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection import status as st
from scripts.shadow_collect_ph import assert_isolated, USER_AGENT

TABLE_KEYS = {"shadow_records": "url", "captures": "capture_id", "revisions": "revision_id"}


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(state):
    assert_isolated(state)
    files = {}
    for path in state.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(state).as_posix()
        require(rel in ("shadow.db", "clock.json") or bool(re.fullmatch(
            r"ledger/[^/]+\.json|evidence/[A-Za-z0-9_.-]+\.json|evidence/payloads/[a-f0-9]{64}\.bin",
            rel)), "unexpected state file: " + rel)
        files[rel] = digest(path)
    tables = {}
    db = state / "shadow.db"
    if db.exists():
        conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            require(conn.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                    "database integrity check failed")
            for table, key in TABLE_KEYS.items():
                cursor = conn.execute("SELECT * FROM " + table)
                names = [column[0] for column in cursor.description]
                pos = names.index(key)
                tables[table] = {}
                for row in cursor:
                    values = [value.hex() if isinstance(value, bytes) else value for value in row]
                    blob = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    tables[table][str(row[pos])] = hashlib.sha256(blob).hexdigest()
            for payload, sha in conn.execute("SELECT payload, payload_sha256 FROM captures"):
                require(hashlib.sha256(payload).hexdigest() == sha, "capture hash mismatch")
        finally:
            conn.close()
    return {"files": files, "tables": tables}


def verify(state, before, run_id, commit):
    after = snapshot(state)
    for name, sha in before["files"].items():
        if name != "shadow.db":
            require(after["files"].get(name) == sha, "immutable history changed: " + name)
    for table, rows in before["tables"].items():
        for key, sha in rows.items():
            require(after["tables"].get(table, {}).get(key) == sha,
                    "historical database row changed: %s/%s" % (table, key))
    new_ledgers = [name for name in after["files"]
                   if name.startswith("ledger/") and name not in before["files"]]
    require(len(new_ledgers) == 1, "attempt needs exactly one new completed ledger")
    entry = json.loads((state / new_ledgers[0]).read_text(encoding="utf-8"))
    require(entry["run_id"] == run_id and entry["collector_commit"] == commit,
            "wrong attempt or collector provenance")
    require(entry["collector_identity"] == USER_AGENT, "wrong collector identity")
    require(entry.get("finished_utc") and entry.get("health") in ("ok", "partial", "fail")
            and (st.is_success(entry.get("result")) or st.is_failure(entry.get("result"))),
            "incomplete ledger")
    require(entry["state_sha256_before"] == before["files"].get("shadow.db"),
            "wrong prior database hash")
    require(entry["state_sha256_after"] == after["files"].get("shadow.db"),
            "incomplete or changed database")
    evidence = entry["request_evidence"]
    require(evidence["path"] == "evidence/" + run_id + ".json", "wrong request evidence path")
    require(after["files"].get(evidence["path"]) == evidence["sha256"], "request evidence changed")
    receipts = json.loads((state / evidence["path"]).read_text(encoding="utf-8"))
    require(len(receipts) == evidence["requests"], "request count differs")
    for receipt in receipts:
        if receipt.get("payload_retained"):
            sha = receipt["payload_sha256"]
            require(after["files"].get("evidence/payloads/" + sha + ".bin") == sha,
                    "missing or changed original request payload")
    if entry.get("rehearsal"):
        require(1 <= entry["sample_limit"] <= 2 and entry["lookback_days"] <= 14,
                "unbounded rehearsal")
        require(entry["selected"] <= entry["sample_limit"] and
                entry["discovered"] == entry["selected"] + entry["sample_unselected"],
                "unreconciled rehearsal sample")
        if entry["health"] == "ok":
            require(entry["selected"] > 0 and entry["retrieved"] == entry["selected"],
                    "incomplete rehearsal retrieval")
    clean = not entry.get("rehearsal") and entry["health"] == "ok" and st.is_success(entry["result"])
    if not clean:
        require(entry.get("shadow_day") is None, "failed/partial attempt advanced clock")
        require(after["files"].get("clock.json") == before["files"].get("clock.json"),
                "failed/partial attempt started clock")
    elif "clock.json" not in before["files"]:
        clock = json.loads((state / "clock.json").read_text(encoding="utf-8"))
        require(clock["day_zero_run_id"] == run_id and clock["day_zero_utc"] == entry["finished_utc"],
                "incorrect initial clock")
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("snapshot", "verify"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--commit")
    args = parser.parse_args(argv)
    if args.mode == "snapshot":
        # Baseline is external to the state that will be committed.
        state = args.state_dir.resolve()
        require(state not in args.baseline.resolve().parents, "baseline must be outside state")
        with args.baseline.open("x", encoding="utf-8") as fh:
            json.dump(snapshot(args.state_dir), fh, sort_keys=True)
    else:
        require(args.run_id and args.commit, "verification needs attempt and collector ids")
        verify(args.state_dir, json.loads(args.baseline.read_text()), args.run_id, args.commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
