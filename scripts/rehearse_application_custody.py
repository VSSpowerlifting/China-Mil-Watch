"""Explicitly enabled fictional custody exercise; no collection/model/publication."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.evidence_snapshot import EvidenceContractError
from storage import db
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_streaming import FictionalFileStore, StreamingEvidenceCoordinator
from tests.custody_fixtures import initialize_application, insert_fictional


class LostAcknowledgementStore(FictionalFileStore):
    """One fictional transport fault AFTER a real persistent pointer update."""
    lose_ack = False

    def cas(self, *args):
        advanced = super().cas(*args)
        if self.lose_ack:
            self.lose_ack = False
            raise EvidenceContractError("custody_store_unavailable")
        return advanced


def rehearse():
    with tempfile.TemporaryDirectory(prefix="ipr-custody-store-") as store_root, \
            tempfile.TemporaryDirectory(prefix="ipr-custody-application-") as root:
        store = LostAcknowledgementStore(store_root, enabled=True)
        coordinator = StreamingEvidenceCoordinator(store)
        session = RehearsalCustodySession(coordinator, root, enabled=True)
        session.bootstrap(allow_empty=True)
        initialize_application(session.database_path)
        insert_fictional(session.database_path)
        collected = session.checkpoint("collected")
        with session.application():
            article = db.get_articles_unscored()[0]
            db.update_relevance(article["id"], 0.8, "Fictional relevance", True)
        store.lose_ack = True
        try:
            session.checkpoint("analyzed")
        except EvidenceContractError as exc:
            if str(exc) != "custody_store_unavailable":
                raise
        # Recreate transport AND application session; runner memory is not proof.
        fresh = StreamingEvidenceCoordinator(FictionalFileStore(store_root, enabled=True))
        with tempfile.TemporaryDirectory(prefix="ipr-custody-restart-") as restart:
            restored = RehearsalCustodySession(fresh, restart, run_id=session.run_id,
                                              logical_date=session.logical_date, enabled=True)
            boot = restored.bootstrap()
            analyzed = restored.checkpoint("analyzed")
            with restored.application():
                if len(db.get_articles_pending_analysis()) != 1:
                    raise EvidenceContractError("rehearsal_pending_parity_failed")
            restored.restore(Path(restart) / "collected.sqlite", collected["generation"])
        return {"schema": "ipr-application-custody-rehearsal/1",
                "collected": collected, "analyzed": analyzed,
                "completed_restart": boot["completed"],
                "native_pending_restored": True, "historical_restore_verified": True,
                "eligible_for_publication": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    parser.parse_args()
    try:
        print(json.dumps(rehearse(), sort_keys=True))
    except Exception:
        print('{"error":"application_custody_rehearsal_failed"}', file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
