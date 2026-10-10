"""C2-G: fictional CAS admission fence for coordinated task reservations only.

All cooperating test workers must reserve through this facade. The underlying
C2-B journal remains separately callable, so this is NOT a security boundary,
billing proof, worker lease, or authorization for analyzed-stage checkpoint.
No model/provider, source fetch, pipeline runtime or publisher is wired.
"""
from __future__ import annotations

import json

from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, digest_bytes, require,
)
from storage.evidence_manifest_policy import FictionalManifestSourcePolicy
from storage.evidence_task_gate import FictionalAnalysisTaskGate
from storage.evidence_spend_inventory import FictionalSpendRecoveryInventory

SCHEMA = "ipr-fictional-spend-admission/1"
ALLOWED_SHA = frozenset("0123456789abcdef")


class FictionalSpendAdmissionFence:
    """CAS-backed, sticky closed-state and durable in-flight reservations.

    Safety model: every *cooperating* fictional worker registers its flight via
    CAS BEFORE any C2-E spend reservation, then CAS-decrements when finished.
    An ambiguous registration ACK deliberately leaves a durable unresolved
    flight. Closure is one-way, requires zero flights and never grants billing,
    analysis or publication permission. An uncooperative direct C2-B caller is
    outside this synthetic proof; production integration must eliminate it.
    """

    def __init__(self, manifest_policy, *, max_inflight=64):
        require(isinstance(manifest_policy, FictionalManifestSourcePolicy),
                "c2_admission_policy_required")
        require(type(max_inflight) is int and 1 <= max_inflight <= 1024,
                "c2_admission_capacity_invalid")
        self.policy = manifest_policy
        self.session = manifest_policy.session
        self.store = self.session.coordinator.transport
        require(all(callable(getattr(self.store, name, None))
                    for name in ("put_new", "get", "cas")),
                "c2_admission_transport_required")
        self.gate = FictionalAnalysisTaskGate(manifest_policy)
        self.inventory = FictionalSpendRecoveryInventory(manifest_policy)
        self.max_inflight = max_inflight
        self.key = ("c2/spend-admission/" + digest_bytes(canonical_bytes(
            {"execution_id": self.session.run_id}
        )) + ".json")

    def _read(self):
        obj = self.store.get(self.key)
        require(obj is not None, "c2_admission_not_open")
        require(type(obj) in (tuple, list) and len(obj) == 2 and
                type(obj[0]) is bytes and type(obj[1]) is str and
                bool(obj[1]), "c2_admission_state_invalid")
        try:
            state = json.loads(obj[0])
            require(type(state) is dict and set(state) == {
                "schema", "execution_id", "collected_generation", "phase",
                "inflight", "transition",
            } and obj[0] == canonical_bytes(state),
                    "c2_admission_state_invalid")
            require(state["schema"] == SCHEMA and
                    state["execution_id"] == self.session.run_id and
                    type(state["collected_generation"]) is str and
                    len(state["collected_generation"]) == 64 and
                    set(state["collected_generation"]) <= ALLOWED_SHA and
                    state["phase"] in ("open", "closed") and
                    type(state["inflight"]) is int and
                    0 <= state["inflight"] <= 1024 and
                    type(state["transition"]) is int and
                    state["transition"] >= 0 and
                    (state["phase"] != "closed" or state["inflight"] == 0),
                    "c2_admission_state_invalid")
            return state, obj[1]
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise EvidenceContractError("c2_admission_state_invalid") from None

    def open(self):
        """Create the one-way fictional gate after the collected checkpoint."""
        durable = self.policy.verify_before_analysis()
        desired = {
            "schema": SCHEMA,
            "execution_id": self.session.run_id,
            "collected_generation": durable["collected_generation"],
            "phase": "open", "inflight": 0, "transition": 0,
        }
        if self.store.get(self.key) is None:
            # On lost put_new ACK we refuse; retry may reconcile the existing
            # state, but never changes a closed or conflicted generation.
            self.store.put_new(self.key, canonical_bytes(desired))
        current, _ = self._read()
        require(current["collected_generation"] ==
                desired["collected_generation"],
                "c2_admission_generation_mismatch")
        require(current["phase"] == "open", "c2_admission_closed")
        return self.status()

    def _change(self, *, increment=0, close=False):
        """Bounded compare-and-swap; no 'last writer wins' fallbacks."""
        require((increment in (-1, 1) and not close) or
                (increment == 0 and close), "c2_admission_transition_invalid")
        for _ in range(48):
            state, revision = self._read()
            require(state["phase"] == "open", "c2_admission_closed")
            if close:
                require(state["inflight"] == 0,
                        "c2_admission_inflight")
            else:
                require(0 <= state["inflight"] + increment <=
                        self.max_inflight, "c2_admission_inflight")
            next_state = dict(state)
            next_state["transition"] += 1
            next_state["phase"] = "closed" if close else "open"
            next_state["inflight"] += increment
            # A fault after durable CAS may raise. Fail closed and leave the
            # state for independent inspection, never assume no side effect.
            if self.store.cas(self.key, revision,
                              canonical_bytes(next_state)):
                persisted, _ = self._read()
                require(persisted["transition"] >=
                        next_state["transition"],
                        "c2_admission_state_invalid")
                return persisted
        raise EvidenceContractError("c2_admission_contention")

    def reserve(self, article_id, task, model):
        """Enter flight before delegating a fictional C2-E task reservation."""
        self.policy.verify_before_analysis()
        self._change(increment=1)
        try:
            return self.gate.reserve(article_id, task, model)
        finally:
            # Crash between increment and decrement intentionally leaves
            # inflight > 0 until a separately reviewed recovery protocol.
            self._change(increment=-1)

    def close(self):
        """Refuse new cooperating tasks, but NEVER authorize analysis seal."""
        durable = self.policy.verify_before_analysis()
        state = self._change(close=True)
        require(state["collected_generation"] ==
                durable["collected_generation"],
                "c2_admission_generation_mismatch")
        # Audit is advisory even after closure: a direct C2-B caller is not
        # fenced, provider receipts are fake, and task semantics unverified.
        scanned = self.inventory.audit()
        return {
            "schema": SCHEMA,
            "phase": "closed",
            "execution_id": self.session.run_id,
            "collected_generation": state["collected_generation"],
            "unknown_charge_attempts": scanned["unknown_charge_attempts"],
            "unreserved_task_slots": scanned["unreserved_task_slots"],
            "measured_fictional_attempts": scanned["measured_fictional_attempts"],
            "billing_provider_attested": False,
            "analyzed_checkpoint_authorized": False,
            "automatic_retry_authorized": False,
            "eligible_for_publication": False,
        }

    def status(self):
        state, _ = self._read()
        return {
            "schema": SCHEMA,
            "phase": state["phase"],
            "inflight": state["inflight"],
            "execution_id": state["execution_id"],
            "collected_generation": state["collected_generation"],
            "analyzed_checkpoint_authorized": False,
            "automatic_retry_authorized": False,
            "eligible_for_publication": False,
        }
