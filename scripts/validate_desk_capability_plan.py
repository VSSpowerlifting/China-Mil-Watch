"""Validate a desk-capability WORK PLAN, never an admission or release.

Reads tracked JSON declarations only; never connects to GitHub/network,
collects sources, reads databases, runs a model or touches a shadow branch.
Structural validity must NEVER be interpreted as operational readiness.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "config/desk_capability_execution_plan.json"
DEFAULT_BINDINGS = ROOT / "config/shadow_source_workflow_bindings.json"
DEFAULT_REGISTRY = ROOT / "desks/registry.json"
SCHEMA = "ipr-desk-capability-execution-plan/1"
STAGES = {"observe", "verify", "qualify", "decide", "integrate"}
SCOPES = {"vietnam": "vietnam", "japan": "japan", "korea": None, "regional": None}
FAMILY_PREFIXES = {"vietnam": "vn_", "japan": "jp_", "korea": "kr_"}
WORK_ID = re.compile(r"(?:REG|VN|JP|KR)-[0-9]{2}\Z")
FAMILY = re.compile(r"[a-z][a-z0-9_-]{3,79}\Z")
ROOT_FIELDS = {"schema", "as_of", "purpose", "waves", "tasks"}
TASK_FIELDS = {
    "id", "wave", "scope", "registry_desk", "gate", "title", "issue",
    "dependencies", "declared_source_slugs", "proposed_source_families",
    "acceptance", "stop_if", "human_decision_required", "executable_effect",
    "status",
}
WAVE_FIELDS = {"id", "name"}


class PlanInvalid(ValueError):
    pass


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fail(message):
    raise PlanInvalid(message)


def _list(value, message):
    if not isinstance(value, list):
        _fail(message)
    return value


def _unique(values, message):
    if len(values) != len(set(values)):
        _fail(message)


def validate(plan, *, bindings, registry):
    """Reject malformed, miswired or falsely activating planning declarations."""
    if not isinstance(plan, dict) or set(plan) != ROOT_FIELDS or plan["schema"] != SCHEMA:
        _fail("invalid desk execution plan schema/fields")
    try:
        date.fromisoformat(plan["as_of"])
    except (ValueError, TypeError):
        _fail("invalid as_of date")
    if not isinstance(plan["purpose"], str) or len(plan["purpose"]) < 50:
        _fail("missing non-operational purpose")

    if (not isinstance(registry, dict) or not isinstance(registry.get("desks"), list)
            or not isinstance(bindings, dict) or
            bindings.get("schema") != "ipr-shadow-source-workflow-bindings/1" or
            bindings.get("status") != "declaration_only_not_live_evidence"):
        _fail("registry or source bindings contract unavailable")
    declared_desks = {x["slug"] for x in registry["desks"]}
    declared = [x["source_slug"] for x in bindings["sources"]]
    _unique(declared, "duplicate authoritative shadow source declaration")
    bound_sources = set(declared)

    waves = _list(plan["waves"], "missing work waves")
    if not waves or any(not isinstance(x, dict) or set(x) != WAVE_FIELDS or
                        type(x["id"]) is not int or x["id"] < 0 or
                        not isinstance(x["name"], str) or len(x["name"]) < 8 for x in waves):
        _fail("invalid phase wave")
    wave_ids = [x["id"] for x in waves]
    _unique(wave_ids, "duplicate wave id")
    if wave_ids != list(range(len(waves))):
        _fail("waves must be ordered 0..N")

    tasks = _list(plan["tasks"], "missing work packages")
    if not tasks or len(tasks) > 50:
        _fail("work-package list empty or unbounded")
    found = {}
    for x in tasks:
        if not isinstance(x, dict) or set(x) != TASK_FIELDS:
            _fail("unknown or missing work-package fields")
        ident = x["id"]
        if not isinstance(ident, str) or not WORK_ID.fullmatch(ident) or ident in found:
            _fail("duplicate or malformed work-package identity")
        if type(x["wave"]) is not int or x["wave"] not in wave_ids:
            _fail("unknown phase wave " + ident)
        scope = x["scope"]
        if scope not in SCOPES or x["registry_desk"] != SCOPES[scope]:
            _fail("scope not consistent with declared registry reference " + ident)
        if x["registry_desk"] is not None and x["registry_desk"] not in declared_desks:
            _fail("unknown registry desk " + ident)
        expected_prefix = {"vietnam": "VN-", "japan": "JP-",
                           "korea": "KR-", "regional": "REG-"}[scope]
        if not ident.startswith(expected_prefix):
            _fail("task id claims wrong scope " + ident)
        if x["gate"] not in STAGES:
            _fail("unknown acceptance stage " + ident)
        if type(x["issue"]) is not int or x["issue"] < 1:
            _fail("work package needs real issue number " + ident)
        if (not isinstance(x["title"], str) or len(x["title"]) < 16 or
            any(not isinstance(x[k], str) or len(x[k]) < 75 for k in ("acceptance", "stop_if"))):
            _fail("insufficient bounded evidence/stop criteria " + ident)
        if type(x["human_decision_required"]) is not bool or (
            x["gate"] in {"qualify", "decide", "verify"} and
            not x["human_decision_required"]
        ):
            _fail("required human-review flag missing " + ident)
        if x["status"] != "planned_not_verified" or x["executable_effect"] != "none":
            _fail("plan may neither assert qualification nor enable actions " + ident)
        deps = _list(x["dependencies"], "dependencies not a list " + ident)
        sources = _list(x["declared_source_slugs"], "source identities not a list " + ident)
        proposed = _list(x["proposed_source_families"], "proposed source list invalid " + ident)
        for key, vals in [("dependencies", deps), ("sources", sources), ("proposed", proposed)]:
            if any(not isinstance(v, str) for v in vals):
                _fail("invalid " + key + " entry " + ident)
            _unique(vals, "duplicate " + key + " " + ident)
        if ident in deps:
            _fail("self-dependent work package " + ident)
        if any(x not in bound_sources for x in sources):
            _fail("unknown or falsely admitted shadow source family " + ident)
        if scope in FAMILY_PREFIXES and any(not s.startswith(FAMILY_PREFIXES[scope]) for s in sources):
            _fail("shadow source claimed by wrong desk " + ident)
        if any(not FAMILY.fullmatch(s) or s in bound_sources for s in proposed):
            _fail("proposed source must not masquerade as admitted " + ident)
        if scope in FAMILY_PREFIXES and any(not s.startswith(FAMILY_PREFIXES[scope].rstrip("_")) for s in proposed if s != "mod-en-defence-relations"):
            _fail("proposed source assigned outside its scope " + ident)
        found[ident] = x

    for ident, node in found.items():
        for dep in node["dependencies"]:
            if dep not in found:
                _fail("undeclared prerequisite " + ident + " -> " + dep)
            if found[dep]["wave"] > node["wave"]:
                _fail("dependency runs in a later wave " + ident + " -> " + dep)

    visited, visiting, order = set(), set(), []
    def walk(ident):
        if ident in visiting:
            _fail("dependency cycle at " + ident)
        if ident in visited:
            return
        visiting.add(ident)
        for dep in found[ident]["dependencies"]:
            walk(dep)
        visiting.remove(ident)
        visited.add(ident)
        order.append(ident)
    for ident in found:
        walk(ident)

    # Not a pass/fail or "ready" claim: the output is only a validated DAG.
    return {
        "schema": SCHEMA,
        "state": "structure_valid_only_not_operational_evidence",
        "as_of": plan["as_of"],
        "work_packages": len(tasks),
        "wave_counts": {str(w): sum(x["wave"] == w for x in tasks) for w in wave_ids},
        "execution_permitted": False,
        "source_admission_permitted": False,
        "desk_promotion_permitted": False,
        "publishing_permitted": False,
        "topological_order": order,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="emit plan structure, NOT source readiness")
    args = p.parse_args(argv)
    report = validate(
        _load_json(DEFAULT_PLAN),
        bindings=_load_json(DEFAULT_BINDINGS),
        registry=_load_json(DEFAULT_REGISTRY),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Desk plan structure valid only: {} work packages across {} waves; "
              "collection, approval, publication and promotion remain disabled.".format(
                  report["work_packages"], len(report["wave_counts"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
