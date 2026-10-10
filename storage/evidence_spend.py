"""C2-B: fictional write-ahead paid-analysis intents; no model/API calls.

The write-once reservation MUST precede a future chargeable operation.
An intent without a measured outcome is UNKNOWN spend, not zero spend.
No implicit retry is authorized, even when the caller lost an acknowledgement.
This module is deliberately not connected to any production execution path.
"""
from __future__ import annotations

import json

from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, digest_bytes, require,
)
from storage import db
from storage.evidence_lifecycle import FictionalCollectionBarrier

SCHEMA = "ipr-fictional-analysis-spend/1"
TASKS = frozenset(("relevance", "translation", "summary", "categorization"))
COUNTERS = ("input_tokens", "output_tokens", "cache_read_input_tokens",
            "cache_creation_input_tokens")


class FictionalSpendIntentJournal:
    """One immutable reservation per execution+article+task, no automatic replay.

    The store exposes C1's put_new/get API, and cannot be a real provider in
    this harness. Separate outcome objects allow lost-ack reconciliation without
    rewriting reservations; their hashes are checked on every read.
    """

    def __init__(self, barrier):
        require(isinstance(barrier, FictionalCollectionBarrier),
                "c2_analysis_barrier_required")
        self.barrier = barrier
        self.session = barrier.session
        self.store = self.session.coordinator.transport
        require(all(callable(getattr(self.store, name, None))
                    for name in ("put_new", "get")),
                "c2_spend_transport_required")

    def _identity(self, article_id, task):
        require(type(article_id) is int and article_id > 0 and
                type(task) is str and task in TASKS,
                "c2_spend_identity_invalid")
        identity = {
            "execution_id": self.session.run_id,
            "article_id": article_id,
            "task": task,
        }
        return digest_bytes(canonical_bytes(identity))

    @staticmethod
    def _valid_usage(usage):
        return (type(usage) is dict and set(usage) == set(COUNTERS)
                and all(type(usage[k]) is int and 0 <= usage[k] < 10 ** 10
                        for k in COUNTERS))

    @staticmethod
    def _valid_model(model):
        return (type(model) is str and 0 < len(model) <= 128 and
                model.isascii() and all(ch.isalnum() or ch in "._:-"
                                        for ch in model))

    @staticmethod
    def _read(store, key):
        result = store.get(key)
        if result is None:
            return None
        require(type(result) in (tuple, list) and len(result) == 2 and
                type(result[0]) is bytes and type(result[1]) is str and
                bool(result[1]), "c2_spend_store_invalid")
        try:
            object_value = json.loads(result[0])
            require(type(object_value) is dict and
                    canonical_bytes(object_value) == result[0],
                    "c2_spend_store_invalid")
            return object_value
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise EvidenceContractError("c2_spend_store_invalid") from None

    def _keys(self, article_id, task):
        token = self._identity(article_id, task)
        return ("c2/paid-intent/" + token + ".json",
                "c2/paid-outcome/" + token + ".json", token)

    def _write_once(self, key, payload):
        encoded = canonical_bytes(payload)
        # put_new can return False after another writer wins, or raise after a
        # durable write. Never interpret an ambiguous acknowledgement as zero.
        created = self.store.put_new(key, encoded)
        persisted = self._read(self.store, key)
        require(persisted is not None and canonical_bytes(persisted) == encoded,
                "c2_spend_write_conflict")
        return created

    def reserve(self, article_id, task, model):
        """Reserve BEFORE the future external call; NEVER actually call it.

        A duplicate reservation always fails, including after measured spend:
        retry policy/provider idempotency need separate owner approval.
        """
        require(self._valid_model(model), "c2_spend_model_invalid")
        key, outcome_key, token = self._keys(article_id, task)
        gate = self.barrier.verify_before_analysis()
        with self.session.application(read_only=True):
            with db.get_conn() as conn:
                row = conn.execute(
                    "SELECT (length(trim(coalesce(text_original,''))) > 0), "
                    "processing_state FROM articles WHERE id=?",
                    (article_id,),
                ).fetchone()
        require(row is not None and row[0] == 1,
                "c2_spend_article_not_dispatchable")
        require(row[1] not in ("terminal", "paused"),
                "c2_spend_article_not_dispatchable")
        require(self._read(self.store, key) is None,
                "c2_spend_attempt_already_reserved")
        require(self._read(self.store, outcome_key) is None,
                "c2_spend_outcome_without_intent")
        intent = {
            "schema": SCHEMA, "kind": "intent",
            "execution_id": self.session.run_id,
            "article_id": article_id, "task": task,
            "model": model, "collected_generation": gate["collected_generation"],
            "ledger_sha256": gate["source_ledger_sha256"],
        }
        require(self._write_once(key, intent),
                "c2_spend_attempt_already_reserved")
        return {
            "schema": SCHEMA, "intent_id": token,
            "article_id": article_id, "task": task,
            "state": "reserved_spend_unknown",
            "eligible_for_publication": False,
            "provider_call_executed": False,
        }

    def record_outcome(self, article_id, task, *, state, usage=None):
        """Write measured tokens or UNKNOWN outcome, never inferred zero-cost.

        A measured usage object is a caller-supplied receipt and must not be
        mistaken for independently verified provider spend or exact pricing.
        """
        key, outcome_key, token = self._keys(article_id, task)
        intent = self._read(self.store, key)
        require(intent is not None and intent.get("schema") == SCHEMA and
                intent.get("execution_id") == self.session.run_id and
                intent.get("article_id") == article_id and
                intent.get("task") == task, "c2_spend_intent_missing")
        require(state in ("measured", "unknown"),
                "c2_spend_outcome_invalid")
        if state == "unknown":
            require(usage is None, "c2_spend_outcome_invalid")
        else:
            require(self._valid_usage(usage), "c2_spend_usage_invalid")
        receipt = {
            "schema": SCHEMA, "kind": "outcome", "intent_id": token,
            "state": state,
            "usage": (dict(usage) if state == "measured" else None),
        }
        self._write_once(outcome_key, receipt)
        return self.inspect(article_id, task)

    def inspect(self, article_id, task):
        """Read-only recovery report: never authorizes an automatic paid retry."""
        key, outcome_key, token = self._keys(article_id, task)
        intent = self._read(self.store, key)
        outcome = self._read(self.store, outcome_key)
        require(not (outcome is not None and intent is None),
                "c2_spend_outcome_without_intent")
        if intent is not None:
            require(set(intent) == {
                "schema", "kind", "execution_id", "article_id", "task",
                "model", "collected_generation", "ledger_sha256",
            } and intent["schema"] == SCHEMA and intent["kind"] == "intent"
                    and intent["execution_id"] == self.session.run_id
                    and intent["article_id"] == article_id
                    and intent["task"] == task and self._valid_model(intent["model"])
                    and all(type(intent[key]) is str and len(intent[key]) == 64
                            and all(ch in "0123456789abcdef" for ch in intent[key])
                            for key in ("collected_generation", "ledger_sha256")),
                    "c2_spend_store_invalid")
        if outcome is not None:
            require(set(outcome) == {
                "schema", "kind", "intent_id", "state", "usage",
            } and outcome["schema"] == SCHEMA and
                    outcome["kind"] == "outcome" and
                    outcome["intent_id"] == token and
                    outcome["state"] in ("measured", "unknown") and
                    (self._valid_usage(outcome["usage"])
                     if outcome["state"] == "measured"
                     else outcome["usage"] is None),
                    "c2_spend_store_invalid")
        measured = outcome is not None and outcome["state"] == "measured"
        return {
            "schema": SCHEMA, "intent_id": token,
            "state": ("not_reserved" if intent is None else
                      "measured_usage" if measured else "spend_unknown"),
            "usage": outcome["usage"] if measured else None,
            "automatic_retry_authorized": False,
            "eligible_for_publication": False,
        }
