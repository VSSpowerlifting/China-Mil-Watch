#!/usr/bin/env python3
"""Read-only IPR private-archive cutover exposure preflight.

Inspects DECLARED source-code/workflow paths, never source databases, captured
publisher bodies, original binary evidence, secrets, or network endpoints.
A clean static report is NOT authority to cut over: provider, rights and
verified restore are independent gates.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "ipr-private-archive-precutover-exposure/1"
MAX_CODE_BYTES = 1024 * 1024

CODE_PATHS = (
    ".github/workflows/daily_update.yml",
    ".github/workflows/indonesia_korea_shadow.yml",
    ".github/workflows/ph_afp_shadow.yml",
    ".github/workflows/vietnam_ministry_shadow.yml",
    "site/preview/templates/record.html",
)

def _source_file(root: Path, relative: str) -> str:
    path = root / relative
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_CODE_BYTES:
        raise ValueError("inspected_code_missing_or_unsafe")
    return path.read_text(encoding="utf-8")

def _upload_paths(workflow: str):
    """Recognize a bounded literal paths inventory in upload-artifact steps."""
    segments = re.split(r"(?m)^      - name: ", workflow)
    paths = []
    for segment in segments:
        if "uses: actions/upload-artifact@v4" not in segment:
            continue
        lines = segment.splitlines()
        in_paths = False
        for line in lines:
            if re.match(r"^          path: \|\s*$", line):
                in_paths = True
                continue
            if in_paths and re.match(r"^          [a-z][a-z-]*:", line):
                in_paths = False
            if in_paths and line.startswith("            "):
                paths.append(line.strip())
            # Single-path scalar syntax remains visible as well.
            if re.match(r"^          path: [^|]", line):
                paths.append(line.split("path:", 1)[1].strip())
    return paths

def audit(root: Path) -> dict:
    """Conservative source-code exposure inventory; emits fixed codes only."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("repository_root_invalid")
    sources = {name: _source_file(root, name) for name in CODE_PATHS}
    issues = []
    def note(code, path):
        issues.append({"code": code, "file": path})

    daily = sources[".github/workflows/daily_update.yml"]
    if re.search(r"(?m)^\s*git add pla_watch\.db(?:\s|$)", daily):
        note("public_daily_canonical_database_commit", ".github/workflows/daily_update.yml")
    if "publish_dir: ./output" in daily and "publish_branch: gh-pages" in daily:
        note("public_daily_static_output_deployment", ".github/workflows/daily_update.yml")

    page = sources["site/preview/templates/record.html"]
    if "record.text_original" in page:
        note("public_record_template_reads_full_original", "site/preview/templates/record.html")

    if (root / "pla_watch.db").is_file():
        # Presence in checkout, NOT proof of Git tracking, archive size or rights.
        note("canonical_database_present_in_worktree", "pla_watch.db")

    for name in (
        ".github/workflows/indonesia_korea_shadow.yml",
        ".github/workflows/ph_afp_shadow.yml",
        ".github/workflows/vietnam_ministry_shadow.yml",
    ):
        workflow = sources[name]
        for path in _upload_paths(workflow):
            # Any whole state directory or explicit raw capture/DB upload
            # duplicates third-party originals on Actions. Do not count
            # the narrow /state/ledger/*.json and /state/clock.json paths.
            whole_state = bool(re.search(r"/state/\s*$", path))
            raw = any(fragment in path for fragment in (
                "/state/shadow.db", "/state/captures", "/state/evidence/payloads",
                "/state/*.bin", "/state/**/*.bin",
            ))
            if whole_state or raw:
                note("actions_uploads_full_or_original_shadow_state", name)
                break

    # Presence of shadow branch refs, historic artifacts, the deployed
    # gh-pages tree, and real provider storage are NOT audited locally.
    # In particular, this does not assert a provider exists or is private.
    issues.sort(key=lambda row: (row["code"], row["file"]))
    return {
        "schema": SCHEMA,
        "inspection": "declared_code_paths_only",
        "finding_count": len(issues),
        "findings": issues,
        "remote_branch_or_artifact_custody_verified": False,
        "private_provider_connected_and_restore_verified": False,
        "publisher_source_use_rights_approved": False,
        "production_cutover_authorized": False,
        "cutover_ready": False,
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(args.repository)
    except (OSError, ValueError, UnicodeError):
        print(json.dumps({"schema": SCHEMA, "error": "preflight_input_invalid",
                          "cutover_ready": False}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    # No static outcome is a production authorization.
    return 2 if result["finding_count"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
