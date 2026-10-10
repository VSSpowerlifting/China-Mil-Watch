#!/usr/bin/env python3
"""S2.1 synthetic-only SQLite custody and recovery rehearsal.

Accepts no database path, storage credentials, publisher text or output path.
Every artifact lives in a fresh temporary directory and is then discarded.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.evidence_snapshot import capture_backup, manifest_for_backup, verify_snapshot
from storage.evidence_store import LocalEvidenceStore


def rehearse():
    with tempfile.TemporaryDirectory(prefix="ipr-s2-rehearsal-") as tmp:
        root = Path(tmp)
        db = sqlite3.connect(str(root / "fictional.sqlite"))
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE articles(id INTEGER PRIMARY KEY, text_original TEXT)")
            db.execute("INSERT INTO articles VALUES(777, 'FICTIONAL_DO_NOT_PUBLISH')")
            db.commit()
            snapshot = capture_backup(db, root / "capture.sqlite")
            manifest = manifest_for_backup(snapshot, run_id="fictional-rehearsal",
                                           stage="rehearsal")
            store_dir = root / "ipr-s2-local"
            store_dir.mkdir()
            store = LocalEvidenceStore(store_dir)
            store.put_snapshot(snapshot, manifest)
            store.put_manifest(manifest)
            store.advance(manifest["generation"])
            recovered = root / "restored.sqlite"
            saved = store.recover(recovered)
            verify_snapshot(recovered, saved)
        finally:
            db.close()
    return {"contract": "ipr-s2-synthetic-rehearsal/1", "passed": True,
            "record_count": saved["article_count"],
            "eligible_for_publication": False, "source": "synthetic_only"}


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv != ["--synthetic-only"]:
        print(json.dumps({"error": "synthetic_flag_required", "passed": False}))
        return 2
    try:
        result = rehearse()
    except Exception:
        print(json.dumps({"error": "rehearsal_failed", "passed": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
