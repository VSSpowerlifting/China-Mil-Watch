#!/usr/bin/env python3
"""Private-only dossier B1.3 validation and source-review handoff.

This command READS canonical Dossier JSON and the SQLite scratch-copy snapshot.
It WRITES only an explicitly requested, outside-repository, 0600 private
report; it never rewrites a Dossier, archive, Brief, Timeline, rendered output
or publisher text. A successful exit indicates no *mechanical* errors, not
source admission, legal permission, human approval or publish readiness.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow direct invocation from the repository root or an absolute script path.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.dossier_contract import (  # noqa: E402
    DOSSIERS_DIR, DossierValidationError, read_dossier,
)
from core.dossier_sources import reconcile_dossier_sources  # noqa: E402

REPORT_SCHEMA = "ipr-dossier-private-review/1"


class PrivateReportPathError(ValueError):
    """Unsafe report destination; never fall back to a repository path."""


def _private_destination(path):
    """Refuse root, symlink, relative path, missing parent and overwrites."""
    target = Path(path)
    if not target.is_absolute():
        raise PrivateReportPathError("absolute report path outside repository required")
    if not target.name.endswith(".json") or target.name in {".json", "..json"}:
        raise PrivateReportPathError("report must use a named .json file")
    if (target.is_symlink() or target.exists()
            or not target.parent.is_dir() or target.parent.is_symlink()
            or target.parent.resolve() != target.parent):
        raise PrivateReportPathError("existing, symlinked or missing report destination")
    repository = ROOT.resolve()
    resolved_parent = target.parent.resolve()
    if resolved_parent == repository or repository in resolved_parent.parents:
        raise PrivateReportPathError("private report must stay outside repository")
    return target


def _safe_error(code, record_id=None):
    """Only fixed internal codes and validated numeric IDs, never source prose."""
    issue = {"code": code}
    if type(record_id) is int and 0 < record_id <= (1 << 63) - 1:
        issue["record_id"] = record_id
    return issue


def _validate_one(path, source_dir, db_path, registry):
    """No user-authored prose or raw publisher body appears in the result."""
    entry = {
        "input": "sidecar",
        "structure_valid": False,
        "archive_reconciled": False,
        "eligible_for_publication": False,
        "status": "error",
        "errors": [],
        "holds": [],
    }
    try:
        sidecar = read_dossier(path, source_dir=source_dir)
    except (DossierValidationError, OSError, ValueError, TypeError, RecursionError):
        entry["errors"].append(_safe_error("invalid-dossier-json-or-contract"))
        return entry
    except Exception:  # Always report a closed failure without leaking private text.
        entry["errors"].append(_safe_error("internal-structure-check-failed"))
        return entry

    entry["structure_valid"] = True
    entry["slug"] = sidecar["slug"]  # Strictly validated ASCII slug.
    try:
        reviewed = reconcile_dossier_sources(sidecar, db_path, registry=registry)
    except Exception:
        entry["errors"].append(_safe_error("internal-source-check-failed"))
        return entry

    # Only deliberately whitelisted metadata; never serialize raw inputs.
    entry.update(
        archive_reconciled=reviewed["archive_reconciled"],
        content_sha256=reviewed["content_sha256"],
        selected_record_ids=reviewed["selected_record_ids"],
        errors=[_safe_error(it["code"], it.get("record_id"))
                for it in reviewed["errors"]],
        holds=[_safe_error(it["code"], it.get("record_id"))
               for it in reviewed["holds"]],
    )
    entry["status"] = "error" if entry["errors"] else "review_hold"
    # Do not inherit a permissive flag from an input or future API. B1.3 is
    # a private diagnostic tool only; no path here can authorize publication.
    entry["eligible_for_publication"] = False
    return entry


def review_directory(source_dir, db_path, registry=None):
    """Inspect canonical direct children; empty directory is *not* approval."""
    root = Path(source_dir)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        return {
            "schema": REPORT_SCHEMA, "status": "error",
            "eligible_for_publication": False, "dossier_count": 0,
            "mechanically_valid_count": 0, "error_count": 1, "hold_count": 0,
            "errors": [_safe_error("source-directory-not-canonical")],
            "dossiers": [],
        }
    # Missing/empty is a legitimate pre-launch state: no empty public library.
    paths = sorted(root.glob("*.json")) if root.is_dir() else []
    rows = [_validate_one(p, root, db_path, registry) for p in paths]
    errors = sum(len(r["errors"]) for r in rows)
    holds = sum(len(r["holds"]) for r in rows)
    return {
        "schema": REPORT_SCHEMA,
        "status": ("error" if errors else "review_hold" if rows else "no_dossiers"),
        "eligible_for_publication": False,
        "dossier_count": len(rows),
        "mechanically_valid_count": sum(bool(r["structure_valid"] and r["archive_reconciled"]) for r in rows),
        "error_count": errors, "hold_count": holds,
        "errors": [],
        "dossiers": rows,
    }


def write_private_report(report, destination):
    """Exclusive private file outside repo; no overwrite or public log output."""
    target = _private_destination(destination)
    encoded = (json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2,
                          allow_nan=False) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    # A user-owned review receipt, never an Actions artifact or site data.
    descriptor = os.open(str(target), flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as fp:
            fp.write(encoded)
            fp.flush()
            os.fsync(fp.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def main(argv=None, *, registry=None):
    parser = argparse.ArgumentParser(description="Private IPR Dossier mechanical review, never publish")
    parser.add_argument("--source-dir", type=Path, default=DOSSIERS_DIR)
    parser.add_argument("--db", type=Path, required=True,
                        help="SQLite archive; always accessed through scratch-copy read_only")
    parser.add_argument("--report", type=Path, required=True,
                        help="NEW private JSON report outside repository (no overwrite)")
    args = parser.parse_args(argv)
    try:
        # Validate the destination before touching the archive.
        _private_destination(args.report)
        report = review_directory(args.source_dir, args.db, registry=registry)
        write_private_report(report, args.report)
    except (PrivateReportPathError, OSError):
        print("IPR Dossier review: unsafe/unwritable private report destination", file=sys.stderr)
        return 2
    print("IPR Dossier review: %d input(s), %d error(s), %d review hold(s); "
          "publication not authorized" %
          (report["dossier_count"], report["error_count"], report["hold_count"]))
    return 1 if report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
