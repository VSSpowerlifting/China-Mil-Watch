"""S2.3a synthetic checkpoint/recovery rehearsal. NOT a production pipeline.

Requires a deliberately fictional SQLite fixture marker before ANY database
snapshot. Never points at the tracked archive or changes public artifacts.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from core.evidence_snapshot import (
    EvidenceContractError, capture_backup, manifest_for_backup, require,
)
from storage.evidence_object_protocol import EvidenceObjectCoordinator

REPORT_SCHEMA = "ipr-s2-synthetic-checkpoint/1"
FAKE_TABLE = "ipr_s2_fictional_gate"
FAKE_TOKEN = "IPR_S2_SYNTHETIC_FIXTURE_ONLY_20261010"


def _fictional_gate(connection):
    """Reject accidental reuse with a real archive even if it has articles."""
    require(isinstance(connection, sqlite3.Connection), "invalid_connection")
    try:
        rows = connection.execute(
            "SELECT marker FROM ipr_s2_fictional_gate").fetchall()
        require(rows == [(FAKE_TOKEN,)], "fictional_fixture_required")
        require(not connection.in_transaction, "uncommitted_fixture_changes")
    except sqlite3.DatabaseError:
        raise EvidenceContractError("fictional_fixture_required") from None


def _stage_parent(coordinator, run_id, stage, parent):
    require(stage in ("collected", "analyzed"), "unsupported_checkpoint_stage")
    if parent is None:
        require(stage == "collected", "analysis_requires_collected_parent")
        return
    # The offline coordinator revalidates the immutable parent snapshot/claim
    # before inspecting its provenance. Never trust a supplied parent string.
    prior, _, _ = coordinator._registered(parent)
    if stage == "analyzed":
        require(prior["stage"] == "collected" and prior["run_id"] == run_id,
                "analysis_parent_mismatch")
    else:
        require(prior["run_id"] != run_id, "new_collection_run_required")


def checkpoint_fictional(connection, coordinator, *, run_id, stage, parent=None):
    """Persist one fake collection/analysis generation before acknowledging it.

    A failed upload or CAS can leave verified orphan objects; they are never
    promoted by a fallback. The caller must explicitly retry from its durable
    parent, never silently rebase onto a concurrent writer.
    """
    require(isinstance(coordinator, EvidenceObjectCoordinator),
            "invalid_rehearsal_storage")
    _fictional_gate(connection)
    _stage_parent(coordinator, run_id, stage, parent)
    with tempfile.TemporaryDirectory(prefix="ipr-s2-checkpoint-") as scratch:
        path = Path(scratch) / "fictional-backup.sqlite"
        capture_backup(connection, path)
        manifest = manifest_for_backup(path, run_id=run_id, stage=stage,
                                       parent=parent)
        coordinator.prepare(path, manifest)
        advanced = coordinator.advance(manifest["generation"], parent)
    return {
        "schema": REPORT_SCHEMA,
        "run_id": manifest["run_id"],
        "stage": stage,
        "generation": manifest["generation"],
        "advanced": advanced,
        "eligible_for_publication": False,
    }


def recovery_decision_fictional(coordinator):
    """Read-only fail-closed decision; never issues real pipeline actions."""
    require(isinstance(coordinator, EvidenceObjectCoordinator),
            "invalid_rehearsal_storage")
    current, _ = coordinator.current()
    if current is None:
        return {"schema": REPORT_SCHEMA, "generation": None,
                "next_rehearsal_step": "fictional_initial_collection",
                "eligible_for_publication": False}
    manifest, _, _ = coordinator._registered(current["generation"])
    step = ("fictional_resume_analysis" if manifest["stage"] == "collected"
            else "fictional_private_validation" if manifest["stage"] == "analyzed"
            else "rehearsal_only")
    return {"schema": REPORT_SCHEMA, "generation": manifest["generation"],
            "run_id": manifest["run_id"], "stage": manifest["stage"],
            "next_rehearsal_step": step, "eligible_for_publication": False}


def restore_fictional(coordinator, destination, generation=None):
    """Restore verified fictional evidence, with no public/current modification."""
    require(isinstance(coordinator, EvidenceObjectCoordinator),
            "invalid_rehearsal_storage")
    path = Path(destination)
    # The lower layer rejects existing/non-temp paths and creates atomically.
    manifest = coordinator.restore_to_temp(path, generation)
    try:
        connection = sqlite3.connect(
            "file:%s?mode=ro" % path.resolve().as_posix(), uri=True)
        try:
            _fictional_gate(connection)
        finally:
            connection.close()
    except Exception:
        # This path was just created by restore_to_temp; never leave untrusted
        # or non-fictional evidence behind after validation fails.
        path.unlink(missing_ok=True)
        raise EvidenceContractError("restored_fixture_invalid") from None
    return {"schema": REPORT_SCHEMA, "generation": manifest["generation"],
            "restored": True, "eligible_for_publication": False}
