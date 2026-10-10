#!/usr/bin/env python3
"""S2.3a fictional checkpoint failure demo. No external database arguments."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.evidence_checkpoint_rehearsal import (  # noqa: E402
    FAKE_TOKEN, checkpoint_fictional, recovery_decision_fictional,
    restore_fictional,
)
from core.evidence_snapshot import EvidenceContractError  # noqa: E402
from storage.evidence_object_protocol import (  # noqa: E402
    EvidenceObjectCoordinator, InMemoryConditionalStore,
)


def run_fictional_matrix():
    with tempfile.TemporaryDirectory(prefix="ipr-s2-recovery-matrix-") as scratch:
        root = Path(scratch)
        db = sqlite3.connect(str(root / "fictional.sqlite"))
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE ipr_s2_fictional_gate(marker TEXT PRIMARY KEY)")
            db.execute("INSERT INTO ipr_s2_fictional_gate VALUES(?)", (FAKE_TOKEN,))
            db.execute("CREATE TABLE articles(id INTEGER PRIMARY KEY, text_original TEXT)")
            db.execute("INSERT INTO articles VALUES(501, 'FICTIONAL_PUBLISHER_BODY')")
            db.commit()
            transport = InMemoryConditionalStore()
            custody = EvidenceObjectCoordinator(transport)
            collected = checkpoint_fictional(
                db, custody, run_id="fictional-daily-one", stage="collected")
            db.execute("INSERT INTO articles VALUES(502, 'FICTIONAL_ANALYSIS_RESULT')")
            db.commit()
            transport.fail_next("cas")
            blocked = False
            try:
                checkpoint_fictional(
                    db, custody, run_id="fictional-daily-one", stage="analyzed",
                    parent=collected["generation"])
            except EvidenceContractError as exc:
                blocked = str(exc) == "synthetic_storage_unavailable"
            if not blocked or recovery_decision_fictional(custody)[
                    "next_rehearsal_step"] != "fictional_resume_analysis":
                raise EvidenceContractError("failure_did_not_preserve_checkpoint")
            analyzed = checkpoint_fictional(
                db, custody, run_id="fictional-daily-one", stage="analyzed",
                parent=collected["generation"])
            restored = root / "restored-fake-evidence.sqlite"
            restore_fictional(custody, restored, collected["generation"])
            with sqlite3.connect(str(restored)) as recovered:
                old_count = recovered.execute("SELECT count(*) FROM articles").fetchone()[0]
            if old_count != 1:
                raise EvidenceContractError("historical_recovery_failed")
            return {
                "schema": "ipr-s2-failure-matrix/1",
                "synthetic_only": True,
                "checkpoints_verified": 2,
                "analysis_failure_retained_collection": blocked,
                "historical_article_count": old_count,
                "current_stage": recovery_decision_fictional(custody)["stage"],
                "eligible_for_publication": False,
                "success": bool(analyzed["advanced"]),
            }
        finally:
            db.close()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args != ["--synthetic-only"]:
        print(json.dumps({"error": "synthetic_flag_required", "success": False}))
        return 2
    try:
        result = run_fictional_matrix()
    except Exception:
        print(json.dumps({"error": "fictional_matrix_failed", "success": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
