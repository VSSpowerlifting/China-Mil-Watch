"""Private, read-only Dossier v1 archive reconciliation; no public admission.

Schema validation is B1.1 in core.dossier_contract. This B1.2 layer compares
a *synthetic fixture by default in tests* with read-only SQLite and an injected
desk registry. No issuer text, model reasoning, or third-party prose is returned.
An exact match is integrity evidence, NOT editorial, legal or release approval.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from core.desk_registry import load_registry
from core.dossier_contract import dossier_content_digest, validate_dossier_shape
from scripts.reconcile_db import read_only

# Stable machine codes; no free-form SQLite original text in logs or reports.
SCHEMA = "ipr-dossier-source-review/1"

def _issue(code, record_id=None):
    issue = {"code": code}
    if type(record_id) is int:
        issue["record_id"] = record_id
    return issue


def _declared_sources(registry):
    """Only manifest-validated, enabled sources in public collecting desks."""
    declared = {}
    for desk in registry:
        if not (desk.public and desk.is_collecting and desk.has_production_records):
            continue
        for source in desk.sources:
            if (source.enabled and source.contract_validated
                    and source.institution_id and source.language_tag):
                declared[(desk.slug, source.slug)] = source
    return declared


def reconcile_dossier_sources(sidecar, db_path, registry=None):
    """Reconcile archive IDs and stored original text; ALWAYS return private holds.

    Returned errors describe provable violations of the declared source
    identity/digest. Returned holds describe the human editorial, relevance,
    attribution, permissions, and publication decisions not established here.
    The function never changes any original DB, source sidecar, or file.
    """
    validate_dossier_shape(sidecar)
    registry = load_registry() if registry is None else registry
    eligible_sources = _declared_sources(registry)
    ids = [src["record_id"] for src in sidecar["sources"]]
    errors = []
    holds = []
    evidence = []
    db_path = Path(db_path)
    if not db_path.is_file() or db_path.is_symlink():
        errors.append(_issue("archive-unavailable"))
        return _report(sidecar, ids, errors, holds, evidence)

    try:
        with read_only(db_path) as con:
            con.row_factory = sqlite3.Row
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                errors.append(_issue("archive-integrity-failed"))
                return _report(sidecar, ids, errors, holds, evidence)
            if con.execute("PRAGMA foreign_key_check").fetchall():
                errors.append(_issue("archive-foreign-keys-failed"))
                return _report(sidecar, ids, errors, holds, evidence)
            sql = (
                "SELECT a.id, a.title_original, a.text_original, a.published_date, "
                "a.url, a.passed_relevance, s.slug AS source_id, "
                "s.desk_id AS desk, s.institution_id, s.language_tag AS language, "
                "s.enabled AS source_enabled "
                "FROM articles a JOIN sources s ON a.source_id=s.id "
                "WHERE a.id IN (%s) ORDER BY a.id"
                % ",".join("?" for _ in ids)
            )
            rows = {row["id"]: dict(row) for row in con.execute(sql, ids)}
    except (OSError, sqlite3.DatabaseError):
        errors.append(_issue("archive-query-failed"))
        return _report(sidecar, ids, errors, holds, evidence)

    for src in sidecar["sources"]:
        rid = src["record_id"]
        original = rows.get(rid)
        if original is None:
            errors.append(_issue("source-record-missing", rid))
            continue
        declared = eligible_sources.get((original["desk"], original["source_id"]))
        if (declared is None or not original["source_enabled"]
                or declared.institution_id != original["institution_id"]
                or declared.language_tag != original["language"]):
            errors.append(_issue("source-not-public-eligible", rid))
        for wanted, stored in (
            ("desk", "desk"), ("source_id", "source_id"),
            ("institution_id", "institution_id"),
            ("language", "language"), ("url", "url"),
            ("published_on", "published_date"),
        ):
            if src[wanted] != original[stored]:
                errors.append(_issue("source-" + wanted.replace("_", "-") + "-mismatch", rid))
        title = original["title_original"]
        body = original["text_original"]
        if not isinstance(title, str) or not title.strip():
            errors.append(_issue("source-original-title-missing", rid))
        if not isinstance(body, str) or not body.strip():
            errors.append(_issue("source-original-text-missing", rid))
        else:
            fingerprint = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if fingerprint != src["stored_original_sha256"]:
                errors.append(_issue("source-original-body-drift", rid))
        # Screening is model triage, NOT a third-party reuse or editorial receipt.
        relevance = original["passed_relevance"]
        if relevance == 0:
            holds.append(_issue("screening-not-selected-human-review", rid))
        elif relevance is None:
            holds.append(_issue("screening-pending-human-review", rid))
        elif relevance != 1:
            errors.append(_issue("invalid-screening-state", rid))
        # An author can insert any apparent receipt ID in JSON. Never grant
        # permission or source admission from its existence.
        holds.append(_issue("independent-source-admission-required", rid))
        holds.append(_issue("independent-source-use-decision-required", rid))
        evidence.append({
            "record_id": rid,
            "archive_identity_reconciled": not any(
                x.get("record_id") == rid for x in errors
            ),
            "model_screening": (
                "selected" if relevance == 1 else
                "not_selected" if relevance == 0 else
                "pending" if relevance is None else "invalid"
            ),
        })

    holds.append(_issue("human-claim-and-inference-review-required"))
    holds.append(_issue("independently-authenticated-editorial-approval-required"))
    holds.append(_issue("publication-renderer-not-authorized"))
    return _report(sidecar, ids, errors, holds, evidence)


def _report(sidecar, ids, errors, holds, evidence):
    """Deterministic metadata only; both genuine and forged receipts remain holds."""
    return {
        "schema": SCHEMA,
        "dossier_slug": sidecar["slug"],
        "editorial_status": sidecar["editorial_status"],
        "content_sha256": dossier_content_digest(sidecar),
        "selected_record_ids": list(ids),
        "archive_reconciled": not errors and len(evidence) == len(ids),
        "eligible_for_publication": False,
        "errors": errors,
        "holds": holds,
        "evidence": evidence,
    }
