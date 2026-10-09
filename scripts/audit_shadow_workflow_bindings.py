#!/usr/bin/env python3
"""Offline declaration drift check for shadow source families, not run attestation.

Reads source family declarations and repository-local GitHub workflow text.
Never runs collection, reaches GitHub, reads isolated state branches, promotes
sources, or authenticates scheduled run coverage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "ipr-shadow-source-workflow-bindings/1"
TRIGGERS = frozenset(("scheduled", "manual_only", "research_only"))
FIELDS = frozenset(("manifest", "source_slug", "state_branch", "workflow", "cron", "trigger"))
NAME = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")
CRON = re.compile(r"([0-9*,-/]+ ){4}[0-9*,-/]+\Z")


class BindingError(ValueError):
    pass


def require(ok, why):
    if not ok:
        raise BindingError(why)


def local_path(root, value, prefix, suffix):
    require(type(value) is str and value.startswith(prefix) and value.endswith(suffix),
            "invalid declared repository path")
    segments = Path(value).parts
    require(all(part not in (".", "..", "") for part in segments) and
            not Path(value).is_absolute(), "unsafe declared repository path")
    path = (root / value).resolve()
    require(root.resolve() in path.parents, "path escapes repository")
    return path


def workflow_crons(text):
    """Only extract on.schedule[].cron, ignoring comments and sample text.

    This is intentionally a minimal GitHub Actions YAML parser. Alternative
    schedule syntax fails closed rather than claiming a live schedule.
    """
    on = False
    on_indent = None
    schedule = False
    schedule_indent = None
    result = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        level = len(raw) - len(raw.lstrip(" "))
        clean = raw.split("#", 1)[0].rstrip()
        if on and level <= on_indent:
            on, schedule = False, False
        if re.fullmatch(r"on:\s*", clean) and level == 0:
            on = True
            on_indent = level
            schedule = False
            continue
        if not on:
            continue
        if schedule and level <= schedule_indent:
            schedule = False
        if re.fullmatch(r"\s+schedule:\s*", clean):
            require(level > on_indent, "schedule not nested under workflow trigger")
            schedule, schedule_indent = True, level
            continue
        if schedule:
            m = re.fullmatch(r"\s*-\s*cron:\s*['\"]?([^'\"]+)['\"]?\s*", clean)
            if m and level > schedule_indent:
                result.append(m.group(1).strip())
    return result


def uncommented_workflow_text(raw):
    """Keep actual YAML lines, not comments claiming a branch exists."""
    return "\n".join(line.split("#", 1)[0] for line in raw.splitlines()
                     if not line.lstrip().startswith("#"))


def contains_literal_branch(text, branch):
    """Match a branch token without matching another branch's prefix."""
    return bool(re.search(r"(?<![A-Za-z0-9_/-])" + re.escape(branch) +
                          r"(?![A-Za-z0-9_/-])", text))


def validate(root=ROOT, contract_path=None):
    root = Path(root).resolve()
    path = Path(contract_path) if contract_path else root / "config/shadow_source_workflow_bindings.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BindingError("binding document missing or invalid JSON") from exc
    require(type(config) is dict and
            set(config) == {"schema", "status", "sources"} and
            config["schema"] == SCHEMA and
            config["status"] == "declaration_only_not_live_evidence" and
            type(config["sources"]) is list,
            "binding document structure or non-live evidence label changed")
    shadow = root / "shadow"
    actual_manifests = sorted(p for p in shadow.glob("*/manifest.json"))
    require(bool(actual_manifests), "no shadow manifests in repository")
    expected = {}
    desk_by_manifest = {}
    for p in actual_manifests:
        require(not p.is_symlink() and p.resolve().is_relative_to(shadow.resolve()),
                "unsafe shadow manifest symlink")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BindingError("invalid shadow manifest: " + str(p)) from exc
        desk = data.get("desk")
        sources = data.get("sources")
        require(type(desk) is dict and type(sources) is list and bool(sources),
                "malformed shadow source declaration: " + str(p))
        require(desk.get("active") is False and
                desk.get("public_status") in ("shadow", "research"),
                "shadow manifest changed admission status; review map manually")
        desk_by_manifest[p] = desk.get("desk_id")
        require(type(desk.get("desk_id")) is str, "missing desk identity")
        for source in sources:
            require(type(source) is dict and type(source.get("slug")) is str and
                    bool(NAME.fullmatch(source["slug"])) and
                    type(source.get("enabled")) is bool,
                    "invalid shadow source declaration")
            identity = (p, source["slug"])
            require(identity not in expected, "duplicate shadow source slug within manifest")
            expected[identity] = source
    declared = {}
    workflow_cache = {}
    summaries = []
    for binding in config["sources"]:
        require(type(binding) is dict and set(binding) == FIELDS,
                "binding row has missing/unexpected fields")
        manifest = local_path(root, binding["manifest"], "shadow/", "/manifest.json")
        slug = binding["source_slug"]
        require(type(slug) is str and bool(NAME.fullmatch(slug)), "invalid source slug")
        identity = (manifest, slug)
        require(identity in expected, "binding references missing manifest/source")
        require(identity not in declared, "duplicate source-family binding")
        declared[identity] = binding
        workflow = binding["workflow"]
        branch = binding["state_branch"]
        cron = binding["cron"]
        trigger = binding["trigger"]
        require(trigger in TRIGGERS, "unknown source collection trigger")
        if trigger == "research_only":
            require(workflow is None and branch is None and cron is None,
                    "research-only source must not claim a workflow or branch")
            classification = "no_collection_workflow_declared"
        else:
            require(type(branch) is str and
                    re.fullmatch(r"shadow/[a-z0-9][a-z0-9_/-]*", branch),
                    "missing/invalid isolated shadow state branch")
            workflow_path = local_path(root, workflow, ".github/workflows/", ".yml")
            require(workflow_path.is_file() and not workflow_path.is_symlink(),
                    "missing or unsafe declared shadow workflow")
            if workflow_path not in workflow_cache:
                raw = workflow_path.read_text(encoding="utf-8")
                workflow_cache[workflow_path] = (
                    workflow_crons(raw), uncommented_workflow_text(raw)
                )
            active_crons, active_text = workflow_cache[workflow_path]
            require(contains_literal_branch(active_text, branch),
                    "declared shadow branch not in active workflow text: " + branch)
            # For multiplexed collectors, a branch appearing *somewhere* in
            # the YAML is insufficient: prove its explicit source routing.
            if workflow_path.name == "indonesia_korea_shadow.yml":
                desk_id = desk_by_manifest[manifest]
                hhmm = cron.split(" *", 1)[0].split(" ")
                require(len(hhmm) == 2 and
                        bool(re.search(
                            r"(?m)^\s*" + re.escape(desk_id) +
                            r"\)\s+state_branch=" + re.escape(branch) +
                            r";\s+cron_utc=" + re.escape(hhmm[1] + ":" + hhmm[0]) +
                            r"\s*;;\s*$", active_text)),
                        "shared Indonesia/Korea desk-to-state/cron routing mismatch")
            if workflow_path.name == "vietnam_ministry_shadow.yml":
                require(bool(re.search(
                    r"(?<![A-Za-z0-9_/-])" + re.escape(slug + ":" + branch) +
                    r"(?![A-Za-z0-9_/-])", active_text)),
                    "shared Vietnam ministry source-to-state routing mismatch")
            if trigger == "scheduled":
                require(type(cron) is str and bool(CRON.fullmatch(cron)),
                        "invalid declared UTC cron expression")
                require(cron in active_crons,
                        "expected active schedule not in workflow: " + cron)
                classification = "cron_and_branch_literals_found_not_run_verified"
            else:
                require(cron is None and not active_crons,
                        "manual-only binding has active schedule")
                require(re.search(r"(?m)^\s+workflow_dispatch:\s*$", active_text),
                        "manual-only workflow has no dispatch trigger")
                classification = "manual_only_workflow_literal_found_not_run_verified"
        summaries.append({
            "manifest": binding["manifest"], "source_slug": slug,
            "desk_id": desk_by_manifest[manifest],
            "state_branch": branch, "workflow": workflow, "cron": cron,
            "trigger": trigger, "evidence": classification,
            "shadow_source_enabled_declared": expected[identity]["enabled"],
            "production_eligible": False, "editorial_authorized": False,
            "run_attested": False,
        })
    require(set(expected) == set(declared),
            "shadow source-family coverage drift: missing=%s extra=%s" %
            (sorted((str(p.relative_to(root)), s) for p, s in set(expected) - set(declared)),
             sorted((str(p.relative_to(root)), s) for p, s in set(declared) - set(expected))))
    return {
        "schema": SCHEMA,
        "declaration_only": True,
        "manifests_checked": len(actual_manifests),
        "source_families_checked": len(expected),
        "workflows_with_binding": len(workflow_cache),
        "sources": sorted(summaries, key=lambda x: (x["manifest"], x["source_slug"])),
        "all_runs_attested": False, "production_eligible": False,
        "shadow_promotion_authorized": False,
        "editorial_publication_authorized": False,
        "writes": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--contract", type=Path)
    args = p.parse_args(argv)
    try:
        print(json.dumps(validate(args.root, args.contract),
                         indent=2, ensure_ascii=False, sort_keys=True))
    except (BindingError, OSError, ValueError) as exc:
        p.exit(1, "Shadow workflow binding drift: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
