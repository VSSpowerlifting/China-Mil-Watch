"""C2-C: persist immutable fictional source-selection intent BEFORE collection.

A selected source set cannot be narrowed at checkpoint time to hide a missing
source. No real registry or owner authorization is implied: the hypothetical
selection itself must be approved and sourced by a separate C2 runtime gate.
No collectors, model/provider calls, public output, workflows or deployments.
"""
from __future__ import annotations

import json

from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, digest_bytes, require,
)
from storage import db
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_lifecycle import FictionalCollectionBarrier

SCHEMA = "ipr-fictional-source-plan/1"
ALLOWED = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"


def _sources(values):
    require(type(values) in (list, tuple),
            "c2_source_plan_invalid")
    require(all(type(item) is str and 0 < len(item) <= 128 and
                all(char in ALLOWED for char in item) for item in values),
            "c2_source_plan_invalid")
    require(len(values) == len(set(values)),
            "c2_source_plan_duplicate")
    return tuple(sorted(values))


class FictionalSourcePlan:
    """An immutable per-execution source plan stored in C1's fake object store.

    Freeze precedes *source collection*, not merely the final checkpoint.
    A false/missing acknowledgement may leave a durable plan, but cannot
    authorize a different selection. No permission for private execution.
    """

    def __init__(self, session):
        require(isinstance(session, RehearsalCustodySession),
                "c2_source_plan_session_required")
        self.session = session
        self.store = session.coordinator.transport
        require(callable(getattr(self.store, "get", None)) and
                callable(getattr(self.store, "put_new", None)),
                "c2_source_plan_transport_required")
        self.key = (
            "c2/source-plan/" + digest_bytes(
                canonical_bytes({"execution_id": session.run_id})
            ) + ".json"
        )

    def _check_started(self):
        require(getattr(self.session, "_started", False),
                "custody_startup_required")
        require(not getattr(self.session, "_finished", False),
                "c2_source_plan_already_completed")

    def _read(self):
        obj = self.store.get(self.key)
        require(obj is not None, "c2_source_plan_missing")
        require(type(obj) in (tuple, list) and len(obj) == 2 and
                type(obj[0]) is bytes and type(obj[1]) is str and bool(obj[1]),
                "c2_source_plan_invalid")
        try:
            plan = json.loads(obj[0])
            require(type(plan) is dict and
                    set(plan) == {"schema", "execution_id", "logical_date",
                                  "sources", "source_set_sha256"} and
                    plan["schema"] == SCHEMA and
                    plan["execution_id"] == self.session.run_id and
                    plan["logical_date"] == self.session.logical_date and
                    type(plan["sources"]) is list and
                    tuple(plan["sources"]) == _sources(plan["sources"]) and
                    plan["source_set_sha256"] ==
                    digest_bytes(canonical_bytes(plan["sources"])) and
                    obj[0] == canonical_bytes(plan),
                    "c2_source_plan_invalid")
            return plan
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise EvidenceContractError("c2_source_plan_invalid") from None

    def freeze(self, expected_sources):
        """Store the complete selected set before any source-specific DB rows.

        Only a started fictional C1 session and an explicit native execution
        mapping can prepare a plan. This prevents a plan being retrofitted after
        a partial source collection. Empty is legitimate for backlog-only runs.
        """
        self._check_started()
        selected = _sources(expected_sources)
        require(getattr(self.session, "_collected", None) is None,
                "c2_source_plan_too_late")
        active, _ = self.session.coordinator.current()
        require(active is None or active["run_id"] != self.session.run_id,
                "c2_source_plan_too_late")
        with self.session.application(read_only=True), db.get_conn() as conn:
            rows = conn.execute(
                "SELECT native_run_id,logical_date FROM ipr_custody_execution "
                "WHERE execution_id=?", (self.session.run_id,)
            ).fetchall()
            require(len(rows) == 1 and
                    rows[0][1] == self.session.logical_date and
                    type(rows[0][0]) is int,
                    "c2_source_plan_native_run_missing")
            native = rows[0][0]
            require(conn.execute(
                "SELECT count(*) FROM source_run_results "
                "WHERE scrape_run_id=?", (native,)
            ).fetchone()[0] == 0 and
                conn.execute(
                    "SELECT count(*) FROM articles WHERE scrape_run_id=?",
                    (native,)
                ).fetchone()[0] == 0,
                "c2_source_plan_too_late")
        plan = {
            "schema": SCHEMA,
            "execution_id": self.session.run_id,
            "logical_date": self.session.logical_date,
            "sources": list(selected),
            "source_set_sha256": digest_bytes(canonical_bytes(selected)),
        }
        # A prepared plan is immutable, and a subsequent caller cannot shorten
        # it even if the transport acknowledged the write ambiguously.
        existing = self.store.get(self.key)
        if existing is not None:
            prior = self._read()
            require(prior == plan, "c2_source_plan_conflict")
            return self._report(prior, already_frozen=True)
        created = self.store.put_new(self.key, canonical_bytes(plan))
        frozen = self._read()
        require(frozen == plan, "c2_source_plan_conflict")
        require(created is True, "c2_source_plan_race")
        return self._report(frozen, already_frozen=False)

    def load(self):
        """Verified source-selection replay after crash or a new process."""
        self._check_started()
        return self._read()

    def _report(self, plan, *, already_frozen=False):
        return {
            "schema": SCHEMA,
            "execution_id": plan["execution_id"],
            "logical_date": plan["logical_date"],
            "source_count": len(plan["sources"]),
            "source_set_sha256": plan["source_set_sha256"],
            "already_frozen": already_frozen,
            "eligible_for_publication": False,
            "production_selection_authorized": False,
        }

    def barrier(self):
        """Build C2-A from the frozen store, never caller-provided source args."""
        plan = self.load()
        return FictionalCollectionBarrier(self.session, plan["sources"])

    def seal_collection(self):
        """Do not allow an omitted source to be hidden by a narrower list."""
        plan = self.load()
        receipt = self.barrier().seal_collection()
        require(receipt["source_count"] == len(plan["sources"]),
                "c2_source_plan_incomplete")
        return {**receipt, "source_set_sha256": plan["source_set_sha256"]}

    def verify_before_analysis(self):
        """Freshly re-read the frozen plan before validating collected evidence."""
        plan = self.load()
        receipt = self.barrier().verify_before_analysis()
        return {**receipt, "source_set_sha256": plan["source_set_sha256"]}
