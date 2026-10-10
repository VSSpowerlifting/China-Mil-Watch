"""C2-E: fictitious analysis-task order gate, with NO provider/collector execution.

A native, read-back verified collected C1 generation and a hash-pinned native
manifest source plan must exist before a synthetic task reservation is issued.
Reservations are write-once and have no API dispatch capability. The production
Analyzer and pipeline are intentionally not imported or patched here.
"""
from __future__ import annotations

from core.evidence_snapshot import require
from storage import db
from storage.evidence_manifest_policy import FictionalManifestSourcePolicy
from storage.evidence_spend import FictionalSpendIntentJournal, TASKS

SCHEMA = "ipr-fictional-task-dispatch/1"


class FictionalAnalysisTaskGate:
    """Rehearsal-only sequence: relevance -> translation -> summary/categories.

    A spend *measurement* is not proof that an LLM answer was semantically
    successful. Relevance passing can be checked against the native DAO; the
    translation and content/quality checks remain a later C2 integration gate.
    """

    def __init__(self, manifest_policy):
        require(isinstance(manifest_policy, FictionalManifestSourcePolicy),
                "c2_task_policy_required")
        self.policy = manifest_policy
        self.session = manifest_policy.session
        # Construction must not require a plan or collected checkpoint yet.
        # Resolve C2-C's verified frozen plan at task-use time, after preflight.

    @property
    def journal(self):
        return FictionalSpendIntentJournal(self.policy.plan.barrier())

    def _native_relevance_passed(self, article_id):
        with self.session.application(read_only=True):
            with db.get_conn() as conn:
                row = conn.execute(
                    "SELECT passed_relevance FROM articles WHERE id=?",
                    (article_id,)
                ).fetchone()
        return row is not None and row[0] == 1

    def _require_prior(self, article_id, prior_task):
        receipt = self.journal.inspect(article_id, prior_task)
        require(receipt["state"] == "measured_usage",
                "c2_task_prior_spend_unreconciled")

    def reserve(self, article_id, task, model):
        """Reserve a fictional charge before any *hypothetical* API call.

        No model invocation exists in this class. These checks cannot
        establish provider billing truth or approve actual model execution.
        """
        require(type(article_id) is int and article_id > 0 and
                type(task) is str and task in TASKS,
                "c2_task_identity_invalid")
        # Revalidate pinned manifest, source-run receipts and immutable C1
        # collected generation for each task, including each parallel worker.
        self.policy.verify_before_analysis()
        if task != "relevance":
            self._require_prior(article_id, "relevance")
            require(self._native_relevance_passed(article_id),
                    "c2_task_relevance_not_passed")
        if task in ("summary", "categorization"):
            self._require_prior(article_id, "translation")
        claimed = self.journal.reserve(article_id, task, model)
        require(claimed["provider_call_executed"] is False and
                claimed["eligible_for_publication"] is False,
                "c2_task_external_dispatch_forbidden")
        return {
            "schema": SCHEMA, "article_id": article_id,
            "task": task, "intent_id": claimed["intent_id"],
            "state": claimed["state"],
            "provider_call_executed": False,
            "automatic_retry_authorized": False,
            "eligible_for_publication": False,
        }

    def record_fictional_outcome(self, article_id, task, *, state, usage=None):
        """Record an offered fictional usage/unknown receipt, not provider truth."""
        self.policy.verify_before_analysis()
        return self.journal.record_outcome(
            article_id, task, state=state, usage=usage,
        )

    def inspect(self, article_id, task):
        """Do not turn an observed usage record into an execution permission."""
        return self.journal.inspect(article_id, task)
