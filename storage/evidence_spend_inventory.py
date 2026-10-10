"""C2-F fictional cross-article spend inventory, intentionally READ-ONLY.

This auditor MUST NOT be used to authorize analyzed checkpoint, retry, a
provider call, or publication: it has no exclusive reservation fence and no
attested billing receipts. It discovers outstanding fictional reservations for
every retained native article and all four recognized model tasks.
"""
from __future__ import annotations

from core.evidence_snapshot import require
from storage import db
from storage.evidence_manifest_policy import FictionalManifestSourcePolicy
from storage.evidence_spend import (
    FictionalSpendIntentJournal, COUNTERS, TASKS,
)

SCHEMA = "ipr-fictional-spend-inventory/1"
ORDERED_TASKS = ("relevance", "translation", "summary", "categorization")
assert set(ORDERED_TASKS) == TASKS


class FictionalSpendRecoveryInventory:
    """Inventory ALL four known task identities, never just reported results.

    It is a deterministic audit of the C1 native article universe currently
    covered by immutable collected evidence. The transport is not enumerable,
    so this is not a proof of all future provider attempts or actual spend.
    """

    def __init__(self, manifest_policy, *, max_articles=10000):
        require(isinstance(manifest_policy, FictionalManifestSourcePolicy),
                "c2_inventory_policy_required")
        require(type(max_articles) is int and 1 <= max_articles <= 100000,
                "c2_inventory_limit_invalid")
        self.policy = manifest_policy
        self.session = manifest_policy.session
        # A C2-F inventory can be constructed before source-plan freeze;
        # only its audit operation may demand collected-stage durability.
        self.max_articles = max_articles

    @property
    def journal(self):
        return FictionalSpendIntentJournal(self.policy.plan.barrier())

    def _native_article_ids(self):
        with self.session.application(read_only=True):
            with db.get_conn() as conn:
                # Query one more than the budget before materializing. A
                # truncated ID list would silently undercount unknown spend.
                rows = conn.execute(
                    "SELECT id FROM articles ORDER BY id "
                    "LIMIT ?", (self.max_articles + 1,)
                ).fetchall()
        require(len(rows) <= self.max_articles,
                "c2_inventory_capacity_exceeded")
        ids = [row[0] for row in rows]
        require(all(type(x) is int and x > 0 for x in ids) and
                len(ids) == len(set(ids)),
                "c2_inventory_native_ids_invalid")
        return ids

    def audit(self):
        """Return only aggregate results; never identify article/source texts.

        The manifest, frozen source plan, original document identity and
        immutable collected head are freshly verified before looking for
        intents. This cannot rule out a concurrent new reservation after the
        audit or arbitrary tasks outside the four-task fictional namespace.
        """
        source = self.policy.verify_before_analysis()
        ids = self._native_article_ids()
        measured = 0
        unknown = 0
        absent = 0
        token_totals = {counter: 0 for counter in COUNTERS}
        for article_id in ids:
            for task in ORDERED_TASKS:
                state = self.journal.inspect(article_id, task)
                if state["state"] == "measured_usage":
                    measured += 1
                    usage = state["usage"]
                    for counter in COUNTERS:
                        token_totals[counter] += usage[counter]
                elif state["state"] == "spend_unknown":
                    unknown += 1
                else:
                    require(state["state"] == "not_reserved",
                            "c2_inventory_state_invalid")
                    absent += 1
        return {
            "schema": SCHEMA,
            "execution_id": self.session.run_id,
            "collected_generation": source["collected_generation"],
            "article_count": len(ids),
            "expected_task_slots": len(ids) * len(ORDERED_TASKS),
            "measured_fictional_attempts": measured,
            "unknown_charge_attempts": unknown,
            "unreserved_task_slots": absent,
            "reported_fictional_tokens": token_totals,
            "billing_provider_attested": False,
            "all_analysis_tasks_complete": False,
            "analyzed_checkpoint_authorized": False,
            "automatic_retry_authorized": False,
            "eligible_for_publication": False,
        }

    def require_no_unknown(self):
        """Diagnose missing charge results; STILL do not authorize checkpoint.

        No transactional freeze prevents a concurrent spend reservation after
        this scan, nor does a reported measurement prove semantic success.
        """
        result = self.audit()
        require(result["unknown_charge_attempts"] == 0,
                "c2_inventory_unknown_charge")
        return result
