"""Inventory potential GitHub Pages publication writers without modifying GitHub.

This is a *source-static* audit, not a proof of a release's freshness or a
replacement for runtime compare-and-swap checks. The inventory reports obvious
publisher primitives, their job scopes and their concurrency groups so release
reviewers can reconcile the actual writer set before changing deployment logic.

Usage: python -m scripts.audit_pages_writers [--workflows-dir .github/workflows] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_JOB = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$")
_GROUP = re.compile(r"^\s*group:\s*(.*?)\s*(?:#.*)?$")
_PUBLISH_ACTION = re.compile(r"\buses:\s*(?:peaceiris/actions-gh-pages|JamesIves/github-pages-deploy-action)@", re.I)
_DEPLOY_PAGES = re.compile(r"\buses:\s*actions/deploy-pages@", re.I)
_GIT_PUSH = re.compile(r"\bgit\s+push\b[^\n]*(?:(?:refs/heads/)?gh-pages|gh[-_]pages)", re.I)
_GH_REF = re.compile(r"\bgh\s+api\b[^\n]*(?:refs/heads/gh-pages|git/refs/heads/gh-pages)", re.I)


@dataclass(frozen=True)
class Writer:
    workflow: str
    job: str
    line: int
    primitive: str
    workflow_group: str | None
    job_group: str | None
    disabled_job: bool

    @property
    def effective_group(self) -> str | None:
        return self.job_group or self.workflow_group

    def report(self) -> dict[str, object]:
        data = asdict(self)
        data["effective_group"] = self.effective_group
        # A distinct group is NOT itself proof of a harmful rollback: runtime
        # leases or content-addressed delivery may independently fence writes.
        data["requires_runtime_freshness_review"] = (
            not self.disabled_job and self.effective_group != "daily-update"
        )
        return data


def _noncomment(line: str) -> bool:
    return bool(line.strip()) and not line.lstrip().startswith("#")


def inventory_file(path: Path) -> list[Writer]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_jobs = False
    current_job = "(workflow)"
    workflow_group: str | None = None
    job_groups: dict[str, str] = {}
    disabled: set[str] = set()
    publisher_hits: list[tuple[str, int, str]] = []
    concurrency_at: tuple[str, int] | None = None

    for number, line in enumerate(lines, 1):
        if not _noncomment(line):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0 and stripped == "jobs:":
            in_jobs = True
            current_job = "(workflow)"
        elif indent == 0 and not stripped.startswith("-") and not stripped.startswith("#"):
            # Other top-level blocks cannot contain job definitions.
            if stripped.endswith(":") and stripped not in ("jobs:", "concurrency:"):
                in_jobs = False
                current_job = "(workflow)"
        if in_jobs and indent == 2:
            m = _JOB.match(line)
            if m:
                current_job = m.group(1)
        if stripped == "concurrency:" and indent in (0, 4):
            concurrency_at = (current_job if indent == 4 and in_jobs else "(workflow)", indent)
        elif concurrency_at and indent > concurrency_at[1]:
            group = _GROUP.match(line)
            if group and indent == concurrency_at[1] + 2:
                if concurrency_at[0] == "(workflow)":
                    workflow_group = group.group(1).strip('"\'')
                else:
                    job_groups[concurrency_at[0]] = group.group(1).strip('"\'')
        elif concurrency_at and indent <= concurrency_at[1]:
            concurrency_at = None
        if in_jobs and current_job != "(workflow)" and indent == 4 and re.match(r"if:\s*(?:false|\$\{\{\s*false\s*\}\})\s*$", stripped, re.I):
            disabled.add(current_job)
        primitive = None
        if _PUBLISH_ACTION.search(line):
            primitive = "git-pages-action"
        elif _DEPLOY_PAGES.search(line):
            primitive = "pages-artifact-action"
        elif _GIT_PUSH.search(line):
            primitive = "git-push-gh-pages"
        elif _GH_REF.search(line) and re.search(r"\b(?:-X|--method)\s+(?:PATCH|POST|PUT)\b", line, re.I):
            primitive = "github-api-pages-ref-write"
        if primitive:
            publisher_hits.append((current_job, number, primitive))

    return [Writer(path.name, job, number, kind, workflow_group,
                   job_groups.get(job), job in disabled)
            for job, number, kind in publisher_hits]


def inventory_directory(root: Path) -> list[Writer]:
    if not root.is_dir():
        raise ValueError(f"workflow directory does not exist: {root}")
    writers = []
    for path in sorted((*root.glob("*.yml"), *root.glob("*.yaml"))):
        writers.extend(inventory_file(path))
    return writers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflows-dir", type=Path, default=Path(".github/workflows"))
    parser.add_argument("--json", action="store_true", help="machine-readable static writer inventory")
    args = parser.parse_args()
    rows = [w.report() for w in inventory_directory(args.workflows_dir)]
    if args.json:
        print(json.dumps({"scope": "static_inventory_only", "writers": rows}, indent=2))
    else:
        print("STATIC Pages writer inventory (not proof of safe runtime ordering)")
        for w in rows:
            print(f"{w['workflow']}:{w['line']} job={w['job']} primitive={w['primitive']} "
                  f"group={w['effective_group'] or '(none)'} "
                  f"disabled={w['disabled_job']} review={w['requires_runtime_freshness_review']}")
        print(f"Total primitives: {len(rows)}; active: {sum(not w['disabled_job'] for w in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
