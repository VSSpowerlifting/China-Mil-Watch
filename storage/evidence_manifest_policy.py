"""C2-D: fictional source roster derived from a hash-pinned native desk manifest.

This module reads validated repository manifests but does NOT authorize a desk,
source, external fetch, cloud provider, model call, workflow or publication.
A caller still chooses the proposed desk/digest; owner-controlled scheduling
and policy provenance must be independently implemented before any activation.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, digest_bytes, digest_file, require,
)
from core.manifests import DESKS_DIR, ManifestError, load_manifest
from storage.evidence_source_plan import FictionalSourcePlan

SCHEMA = "ipr-fictional-manifest-policy/1"
HEX = frozenset("0123456789abcdef")


def _digest(value):
    return type(value) is str and len(value) == 64 and all(x in HEX for x in value)


def _desk_slug(value):
    return (type(value) is str and 0 < len(value) <= 64 and
            all(c.isascii() and (c.isalnum() or c in "_-") for c in value))


class FictionalManifestSourcePolicy:
    """Bounded, immutable policy *candidate* on C1's fake object transport.

    Every recovery revalidates the manifest bytes and compares manifest-derived
    enabled slugs to the separate C2-C frozen source plan. This prevents source
    omissions hidden through a caller-supplied list after plan selection.
    It is still NOT authorization to select or collect a desk in production.
    """

    def __init__(self, source_plan):
        require(isinstance(source_plan, FictionalSourcePlan),
                "c2_manifest_plan_required")
        self.plan = source_plan
        self.session = source_plan.session
        self.store = self.session.coordinator.transport
        self.key = (
            "c2/manifest-policy/" + digest_bytes(canonical_bytes({
                "execution_id": self.session.run_id,
            })) + ".json"
        )

    def _derive(self, desk_id, expected_digest):
        require(_desk_slug(desk_id) and _digest(expected_digest),
                "c2_manifest_selection_invalid")
        base = Path(DESKS_DIR)
        path = base / desk_id / "manifest.json"
        require(base.is_dir() and not base.is_symlink() and
                path.parent.is_dir() and not path.parent.is_symlink() and
                path.is_file() and not path.is_symlink() and
                path.resolve().parent == (base.resolve() / desk_id),
                "c2_manifest_out_of_scope")
        try:
            before = digest_file(path)
            require(before == expected_digest, "c2_manifest_digest_changed")
            config = load_manifest(path)
            after = digest_file(path)
            require(after == before, "c2_manifest_digest_changed")
            require(config.desk.desk_id == desk_id and config.desk.active,
                    "c2_manifest_selection_invalid")
            sources = sorted(src.slug for src in config.sources if src.enabled)
            require(len(sources) == len(set(sources)),
                    "c2_manifest_selection_invalid")
            return sources
        except EvidenceContractError:
            raise
        except (OSError, ValueError, TypeError):
            raise EvidenceContractError("c2_manifest_invalid") from None

    def _read(self):
        obj = self.store.get(self.key)
        require(obj is not None, "c2_manifest_policy_missing")
        require(type(obj) in (tuple, list) and len(obj) == 2 and
                type(obj[0]) is bytes and type(obj[1]) is str and bool(obj[1]),
                "c2_manifest_policy_invalid")
        try:
            raw = json.loads(obj[0])
            require(type(raw) is dict and set(raw) == {
                "schema", "execution_id", "logical_date",
                "desk_id", "manifest_sha256", "sources",
                "source_set_sha256",
            } and obj[0] == canonical_bytes(raw),
                    "c2_manifest_policy_invalid")
            require(raw["schema"] == SCHEMA and
                    raw["execution_id"] == self.session.run_id and
                    raw["logical_date"] == self.session.logical_date and
                    _desk_slug(raw["desk_id"]) and
                    _digest(raw["manifest_sha256"]) and
                    type(raw["sources"]) is list and
                    raw["sources"] == sorted(set(raw["sources"])) and
                    all(type(s) is str and s for s in raw["sources"]) and
                    raw["source_set_sha256"] ==
                    digest_bytes(canonical_bytes(raw["sources"])),
                    "c2_manifest_policy_invalid")
            return raw
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise EvidenceContractError("c2_manifest_policy_invalid") from None

    def freeze(self, desk_id, expected_manifest_sha256):
        """Freeze exactly all enabled manifest slugs before source collection."""
        sources = self._derive(desk_id, expected_manifest_sha256)
        candidate = {
            "schema": SCHEMA,
            "execution_id": self.session.run_id,
            "logical_date": self.session.logical_date,
            "desk_id": desk_id,
            "manifest_sha256": expected_manifest_sha256,
            "sources": sources,
            "source_set_sha256": digest_bytes(canonical_bytes(sources)),
        }
        already = self.store.get(self.key) is not None
        if already:
            require(self._read() == candidate, "c2_manifest_policy_conflict")
        else:
            self.store.put_new(self.key, canonical_bytes(candidate))
            require(self._read() == candidate, "c2_manifest_policy_conflict")
        # If the policy write ACK was lost, the persisted immutable policy can
        # be reconciled here on retry. The native plan retains its own strict
        # no-retroactive-source-row rule.
        plan_report = self.plan.freeze(sources)
        require(plan_report["source_set_sha256"] == candidate["source_set_sha256"],
                "c2_manifest_policy_conflict")
        return self._report(candidate)

    def load(self):
        """Recheck both pinned native manifest and immutable C2-C plan."""
        saved = self._read()
        derived = self._derive(saved["desk_id"], saved["manifest_sha256"])
        require(derived == saved["sources"], "c2_manifest_policy_changed")
        frozen = self.plan.load()
        require(frozen["sources"] == saved["sources"] and
                frozen["source_set_sha256"] == saved["source_set_sha256"],
                "c2_manifest_policy_conflict")
        return saved

    def _report(self, state):
        return {
            "schema": SCHEMA,
            "execution_id": self.session.run_id,
            "desk_id": state["desk_id"],
            "manifest_sha256": state["manifest_sha256"],
            "source_set_sha256": state["source_set_sha256"],
            "source_count": len(state["sources"]),
            "policy_owner_approved": False,
            "eligible_for_publication": False,
            "production_selection_authorized": False,
        }

    def seal_collection(self):
        policy = self.load()
        result = self.plan.seal_collection()
        require(result["source_set_sha256"] == policy["source_set_sha256"],
                "c2_manifest_policy_conflict")
        return {**result, "manifest_sha256": policy["manifest_sha256"],
                "production_selection_authorized": False}

    def verify_before_analysis(self):
        policy = self.load()
        result = self.plan.verify_before_analysis()
        require(result["source_set_sha256"] == policy["source_set_sha256"],
                "c2_manifest_policy_conflict")
        return {**result, "manifest_sha256": policy["manifest_sha256"],
                "production_selection_authorized": False}
