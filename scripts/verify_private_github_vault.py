#!/usr/bin/env python3
"""Authenticated READ-ONLY check of a proposed separate private GitHub vault.

No Git pushes, creation, clone, source originals, secret printing, Actions
dispatch, account changes or public-archive migration. A clean check NEVER
authorizes transfer or publication. Run only in an owner's trusted shell.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

REPORT_SCHEMA = "ipr-private-github-vault-preflight/1"
GITHUB_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}\Z")


class VaultPreflightError(ValueError):
    """Safe fixed reason codes: never print API bodies or secret-bearing errors."""


def check_slug(slug):
    if type(slug) is not str or not GITHUB_REPO.fullmatch(slug):
        raise VaultPreflightError("repository_name_invalid")
    owner, repo = slug.split("/", 1)
    if repo in (".", "..") or repo.startswith("."):
        raise VaultPreflightError("repository_name_invalid")
    return owner, repo


def _api(endpoint):
    """Invoke GH CLI with argument array, not a shell interpolation."""
    env = dict(os.environ)
    env["GH_PAGER"] = ""
    env["NO_COLOR"] = "1"
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", "--hostname", "github.com", endpoint],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=30, check=False, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise VaultPreflightError("authenticated_api_unavailable") from None
    if result.returncode:
        raise VaultPreflightError("authenticated_api_refused") from None
    if len(result.stdout) > 512 * 1024:
        raise VaultPreflightError("authenticated_api_response_oversize")
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        raise VaultPreflightError("authenticated_api_response_invalid") from None


def evaluate(source, vault, *, api=_api):
    """Validate a *brand-new, empty* private destination; never run a transfer."""
    source_owner, _ = check_slug(source)
    vault_owner, _ = check_slug(vault)
    if source.lower() == vault.lower():
        raise VaultPreflightError("source_is_destination")
    if source_owner.lower() != vault_owner.lower():
        # Cross-owner vaults need a separately designed trust and backup policy.
        raise VaultPreflightError("vault_owner_mismatch")

    try:
        src = api("repos/" + source)
        dest = api("repos/" + vault)
        branches = api("repos/" + vault + "/branches?per_page=100")
    except VaultPreflightError:
        raise
    except (TypeError, KeyError, OSError, ValueError):
        raise VaultPreflightError("authenticated_api_unavailable") from None

    if type(src) is not dict or type(dest) is not dict or type(branches) is not list:
        raise VaultPreflightError("repository_api_shape")
    if type(src.get("full_name")) is not str or src["full_name"].lower() != source.lower():
        raise VaultPreflightError("source_identity_mismatch")
    if type(dest.get("full_name")) is not str or dest["full_name"].lower() != vault.lower():
        raise VaultPreflightError("vault_identity_mismatch")
    if src.get("private") is not False or src.get("visibility") != "public":
        raise VaultPreflightError("source_visibility_not_public")
    if dest.get("private") is not True or dest.get("visibility") != "private":
        raise VaultPreflightError("vault_not_private")
    if dest.get("fork") is not False or dest.get("archived") is not False or dest.get("disabled") is not False:
        raise VaultPreflightError("vault_state_unsafe")
    permissions = dest.get("permissions")
    if type(permissions) is not dict or permissions.get("admin") is not True:
        raise VaultPreflightError("vault_owner_access_unverified")
    if branches:
        raise VaultPreflightError("vault_not_empty")
    # Do NOT assume an accessible private repo grants Actions cross-repo write.
    # PR jobs and public source GITHUB_TOKEN may not see vault originals.
    return {
        "schema": REPORT_SCHEMA,
        "source_repo": source,
        "destination_repo": vault,
        "destination_visibility_verified": "private",
        "destination_identity_checked": True,
        "destination_initial_branches": 0,
        "operator_repo_admin_verified": True,
        "cross_repo_workflow_credential_verified": False,
        "independent_backup_and_restore_verified": False,
        "publisher_original_retention_rights_approved": False,
        "failed_attempt_capture_inventory_complete": False,
        "source_bodies_transferred": False,
        "production_cutover_authorized": False,
        "ready_to_transfer": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--vault", required=True)
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.source, args.vault)
    except VaultPreflightError as exc:
        print(json.dumps({
            "schema": REPORT_SCHEMA,
            "result": "HOLD",
            "reason": str(exc),
            "source_bodies_transferred": False,
            "ready_to_transfer": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
