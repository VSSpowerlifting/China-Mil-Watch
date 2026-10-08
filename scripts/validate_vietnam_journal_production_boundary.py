"""Prevent direct, unauthorized Vietnam-journal production/CI activation wiring.

Read-only static boundary for the current *disabled research candidate*.
Composes the merged source-readiness hold with production manifests, public
desk registry, and the names and contents of workflow definitions. This is
not a crawler authorization, a full code-flow audit, or a legal rights grant.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_vietnam_journal_readiness import (
    SOURCE, ReadinessRefused, validate_research_hold,
)

JOURNAL_BINDINGS = (
    SOURCE,
    "vn_journal_",
    "vn_defence_journal",
    "vietnam_journal",
    "tapchiqptd.vn",
)
PRODUCTION_MANIFEST_GLOB = "desks/*/manifest.json"
WORKFLOW_GLOBS = (".github/workflows/*.yml", ".github/workflows/*.yaml")


class BoundaryRefused(ReadinessRefused):
    """Journal source crossed a reviewed research/production boundary."""


def _source_mentions(obj):
    """Only for production manifests, where ANY journal reference is unsafe."""
    text = json.dumps(obj, ensure_ascii=True, sort_keys=True).lower()
    return [token for token in JOURNAL_BINDINGS if token in text]


def validate_boundary(manifest, readiness, registry, production_manifests, workflows):
    """Verify the current research hold across *direct* repository entrypoints.

    Caller supplies parsed JSON plus a complete set of manifest/workflow files.
    This does not inspect dynamic imports or indirect Python code invocation.
    """
    validate_research_hold(manifest, readiness)

    if not isinstance(registry, dict) or registry.get("registry_version") != 1:
        raise BoundaryRefused("invalid authoritative desk registry")
    desks = registry.get("desks")
    if not isinstance(desks, list):
        raise BoundaryRefused("registry desks must be a list")
    vietnam = [d for d in desks if isinstance(d, dict) and d.get("slug") == "vietnam"]
    if len(vietnam) != 1:
        raise BoundaryRefused("Vietnam desk must be declared exactly once")
    entry = vietnam[0]
    if (entry.get("status") != "research"
            or entry.get("manifest") is not None
            or entry.get("has_production_records") is not False
            or entry.get("public") is not True):
        raise BoundaryRefused("journal's Vietnam desk is no longer research-only")

    if not isinstance(production_manifests, dict):
        raise BoundaryRefused("invalid production manifest inventory")
    if not production_manifests:
        raise BoundaryRefused("production manifest scan returned no files")
    for path, payload in production_manifests.items():
        if (not isinstance(path, str) or not path.startswith("desks/")
                or not path.endswith("/manifest.json")
                or path.count("/") != 2):
            raise BoundaryRefused("production manifest location outside allowed tree")
        if not isinstance(payload, dict):
            raise BoundaryRefused("production manifest is not JSON object")
        if _source_mentions(payload):
            raise BoundaryRefused("journal wired into production manifest: " + path)

    if not isinstance(workflows, dict) or not workflows:
        raise BoundaryRefused("workflow definitions absent")
    for path, body in workflows.items():
        if (not isinstance(path, str) or not path.startswith(".github/workflows/")
                or path.count("/") != 2
                or not path.endswith((".yml", ".yaml"))
                or not isinstance(body, str)):
            raise BoundaryRefused("unexpected workflow location or type")
        # Direct source references from *any* workflow (scheduled OR manual)
        # must be reviewed, not just cron triggers. That prevents a new
        # workflow_dispatch from silently sidestepping the disabled manifest.
        lower = body.lower()
        matched = [token for token in JOURNAL_BINDINGS if token in lower]
        if matched:
            raise BoundaryRefused("journal source referenced by workflow: " + path)

    return {
        "schema": "ipr-vndj-production-boundary-check/1",
        "source_slug": SOURCE,
        "source_status": "disabled_research_only",
        "production_manifests_examined": len(production_manifests),
        "workflows_examined": len(workflows),
        "direct_workflow_bindings_found": 0,
        "direct_production_manifest_bindings_found": 0,
        "journal_day_zero_started": False,
        "authorized_collection": False,
        "authorized_source_text_retention": False,
        "historical_completeness_proven": False,
        "static_check_only": True,
    }


def check_repository(root=None):
    """Inspect only committed config files; no network or production DB I/O."""
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    journal = root / "shadow" / "vietnam_journal"
    manifest = json.loads((journal / "manifest.json").read_text(encoding="utf-8"))
    readiness = json.loads((journal / "readiness.v1.json").read_text(encoding="utf-8"))
    registry = json.loads((root / "desks" / "registry.json").read_text(encoding="utf-8"))
    prod = {
        path.relative_to(root).as_posix(): json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob(PRODUCTION_MANIFEST_GLOB))
    }
    workflows = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for pattern in WORKFLOW_GLOBS
        for path in sorted(root.glob(pattern))
    }
    return validate_boundary(manifest, readiness, registry, prod, workflows)


if __name__ == "__main__":
    print(json.dumps(check_repository(), sort_keys=True, indent=2))
