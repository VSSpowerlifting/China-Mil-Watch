"""C2-A: fail-closed source-ledger and collected-before-analysis barrier.

This module operates ONLY on an already bootstrapped fictional C1 custody session.
It does not call collectors/models, trigger paid usage, render, or activate Daily.
C2 runtime wiring and billing recovery are separate, unapproved work.
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from core.collection import status as collection_status
from core.evidence_snapshot import (
    canonical_bytes, digest_bytes, require,
)
from storage import db
from storage.evidence_custody import (
    RehearsalCustodySession, application_identity,
)

SCHEMA = "ipr-c2-fictional-collection-barrier/1"
COUNTERS = (
    "references_discovered", "fetched", "extracted", "duplicates",
    "new_documents", "relevance_rejected", "failed_fetches",
)


class FictionalCollectionBarrier:
    """Require complete native source receipts before *any* model dispatch.

    This is a proof-only lifecycle seam over C1's real application DAO and
    immutable checkpoints, not an alternative collecting/analyzing pipeline.
    Source names and error details are never returned in a receipt.
    """

    def __init__(self, session, expected_sources):
        require(isinstance(session, RehearsalCustodySession),
                "c2_fictional_session_required")
        # Backlog-only runs legitimately request zero new source collections.
        # They still need an execution mapping and an empty source-run ledger.
        require(type(expected_sources) in (tuple, list),
                "c2_expected_sources_invalid")
        require(all(type(s) is str and s and len(s) <= 128 and
                    all(ch.isascii() and (ch.isalnum() or ch in "._:-")
                        for ch in s) for s in expected_sources),
                "c2_expected_sources_invalid")
        require(len(set(expected_sources)) == len(expected_sources),
                "c2_duplicate_source_request")
        self.session = session
        self.expected_sources = frozenset(expected_sources)

    def _native_receipts(self, conn):
        mapping = conn.execute(
            "SELECT native_run_id, logical_date FROM ipr_custody_execution "
            "WHERE execution_id=?", (self.session.run_id,)
        ).fetchall()
        require(len(mapping) == 1 and
                mapping[0][1] == self.session.logical_date,
                "c2_execution_mapping_missing")
        native_id = mapping[0][0]
        require(type(native_id) is int and native_id > 0,
                "c2_execution_mapping_missing")
        rows = conn.execute(
            "SELECT source_slug,status,is_failure,references_discovered,"
            "fetched,extracted,duplicates,new_documents,relevance_rejected,"
            "failed_fetches,text_unavailable FROM source_run_results "
            "WHERE scrape_run_id=? ORDER BY source_slug", (native_id,)
        ).fetchall()
        slugs = [row[0] for row in rows]
        require(len(rows) == len(self.expected_sources) and
                set(slugs) == self.expected_sources,
                "c2_source_ledger_incomplete")
        for row in rows:
            status, failure = row[1], row[2]
            require(status in collection_status.ALL_STATUSES and
                    failure in (0, 1) and
                    failure == int(collection_status.is_failure(status)),
                    "c2_source_status_invalid")
            require(all(type(row[i]) is int and row[i] >= 0
                        for i in range(3, 10)),
                    "c2_source_counters_invalid")
            require(row[10] is None or
                    (type(row[10]) is int and row[10] >= 0),
                    "c2_source_counters_invalid")
        actual = dict(conn.execute(
            "SELECT s.slug, COUNT(*) FROM articles a "
            "JOIN sources s ON a.source_id=s.id "
            "WHERE a.scrape_run_id=? GROUP BY s.slug", (native_id,)
        ).fetchall())
        require(set(actual).issubset(self.expected_sources) and
                all(row[7] <= actual.get(row[0], 0) for row in rows),
                "c2_collection_attribution_invalid")
        # The digest covers source status/counters; NEVER serialize URLs,
        # original text, publisher error detail, titles or API credentials.
        material = [list(row) for row in rows]
        return {
            "native_run_id": native_id,
            "source_count": len(rows),
            "failure_count": sum(row[2] for row in rows),
            "new_article_count": sum(actual.values()),
            "ledger_sha256": digest_bytes(canonical_bytes(material)),
        }

    def _working_receipts(self):
        # C1 owns the path/authority. Never construct a bare DatabaseContext.
        with self.session.application(read_only=True):
            with db.get_conn() as conn:
                identity = application_identity(conn)
                evidence = self._native_receipts(conn)
        return identity, evidence

    def _collected_head(self):
        require(getattr(self.session, "_started", False),
                "custody_startup_required")
        active, _ = self.session.coordinator.current()
        require(active is not None, "c2_collection_not_durable")
        manifest = self.session.coordinator.inspect_generation(
            active["generation"])
        require(manifest["stage"] == "collected" and
                manifest["run_id"] == self.session.run_id,
                "c2_collection_not_durable")
        require(getattr(self.session, "_collected", None) ==
                manifest["generation"],
                "c2_checkpoint_not_acknowledged")
        return manifest

    def seal_collection(self):
        """Seal ALL requested source statuses/counters before model work.

        Call only after the existing native storage/attribution stage has
        persisted its source_run_results (including failures/empty outcomes).
        A missing receipt prevents even the first model call.
        """
        _, evidence = self._working_receipts()
        receipt = self.session.checkpoint("collected")
        manifest = self._collected_head()
        require(manifest["generation"] == receipt["generation"],
                "c2_collection_not_durable")
        # The source ledger was checked before the snapshot; now compare the
        # actual sealed generation against the live copy. Never authorize
        # analysis on a pre-checkpoint observation that raced with a writer.
        durable = self.verify_before_analysis()
        require(durable["source_ledger_sha256"] == evidence["ledger_sha256"],
                "c2_source_ledger_changed")
        return {
            "schema": SCHEMA, "stage": "collected",
            "execution_id": self.session.run_id,
            "generation": manifest["generation"],
            "source_count": evidence["source_count"],
            "source_failure_count": evidence["failure_count"],
            "new_article_count": evidence["new_article_count"],
            "source_ledger_sha256": evidence["ledger_sha256"],
            "eligible_for_publication": False,
            "paid_dispatch_executed": False,
        }

    def verify_before_analysis(self):
        """Check durable collected head and preserved native evidence.

        This function is read-only and never makes a model/API call. Compare
        the local working copy against a fresh, verified *collected* snapshot:
        source receipts and original content cannot be altered after sealing.
        Relevance/analysis fields are allowed to change between dispatches.
        """
        manifest = self._collected_head()
        restored = self.session.root / (
            ".c2-collected-reference-" + uuid.uuid4().hex + ".sqlite")
        try:
            self.session.restore(restored, manifest["generation"])
            with sqlite3.connect(
                restored.resolve().as_uri() + "?mode=ro&immutable=1",
                uri=True,
            ) as parent:
                anchor_identity = application_identity(parent)
                anchor_evidence = self._native_receipts(parent)
            working_identity, working_evidence = self._working_receipts()
            for field in ("schema", "records", "record_runs", "native_runs",
                          "provenance"):
                require(working_identity[field] == anchor_identity[field],
                        "c2_working_copy_diverged")
            require(working_evidence == anchor_evidence,
                    "c2_source_ledger_changed")
        finally:
            restored.unlink(missing_ok=True)
        return {
            "schema": SCHEMA, "execution_id": self.session.run_id,
            "collected_generation": manifest["generation"],
            "source_ledger_sha256": anchor_evidence["ledger_sha256"],
            "eligible_for_publication": False,
            "paid_dispatch_executed": False,
            "analysis_dispatch_eligible_fictional_only": True,
        }

    def seal_analysis(self):
        """Persist post-analysis state; C2 usage receipts are NOT yet wired."""
        before = self.verify_before_analysis()
        result = self.session.checkpoint("analyzed")
        active, _ = self.session.coordinator.current()
        require(active is not None and
                active["generation"] == result["generation"],
                "c2_analysis_not_durable")
        return {
            "schema": SCHEMA, "stage": "analyzed",
            "execution_id": self.session.run_id,
            "collected_generation": before["collected_generation"],
            "analyzed_generation": result["generation"],
            "eligible_for_publication": False,
            "usage_receipt_durable": False,
        }
