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
# An owner-created README-only bootstrap has been verified on the live private
# destination. The pinned blob identifies our non-sensitive policy README.
# A branch name alone (or a random README file) must never imply safe custody.
BOOTSTRAP_README_BLOB_SHA = "b1a7c174d224f0d9e9245ab400a31bb19c6eab86"
PILOT_MAIN_SHA = "2d53f25a2a4c31b3d1b2a84b569a7f203fdad593"
# Current owner-selected private vault has added only vetted metadata inventory
# for the genuine Korea source and its failed October 12 Actions artifact.
# These blobs contain no source-original response bytes or reviewer identities.
METADATA_MAIN_SHA = "43a9ad7efec2731133f0e2e2fb9fee4747091c51"
METADATA_MAIN_TREE = {
    "README.md": ("blob", "0fc7181cb1941c8f1893c30b99caca18a3f87b14"),
    "manifests": ("tree", "9c5d77bdfe65c14f368e28cd60774df7813473e4"),
    "manifests/korea_mnd_custody_preflight_2026-10-15.json":
        ("blob", "8db0105180c02692763e050f18855f2ffc145aa7"),
    "manifests/korea_oct12_failed_actions_capture_audit_2026-10-15.json":
        ("blob", "3aac056afc0cb36bfc4767d406c59c270775cf56"),
}
# Exact owner-approved private GitHub-only storage policy, with the same
# already pinned metadata manifests and zero publisher-original bytes on main.
# Preserve the older exact metadata pin as a distinct historical baseline.
GITHUB_ONLY_MAIN_SHA = "90c8fcbb6ad736ca08ca272b38915b29ea4599fc"
GITHUB_ONLY_MAIN_TREE = {
    **METADATA_MAIN_TREE,
    "README.md": ("blob", "5ff54211535881882c66f8459ca1e6f33e34fbdb"),
}
PILOT_REFS = {
    "pilot/fictional-custody-20261015": "48c7746a1f3b94f76a6859ecd341122e3cdf4d31",
    "pilot/fictional-restore-20261015": "ca89f369bb947cdbe26ed98aa48e9792abea6fd8",
}
PILOT_EXPECTED_BLOBS = {
    "README.md": BOOTSTRAP_README_BLOB_SHA,
    "pilot/manifest.json": "897e6db3ec7f7d2cd3788680eb7d96518fc3d3ac",
    "pilot/source/successful-original.txt": "c659bae45a6a93b4c05000c0f755e3b0555a6e63",
    "pilot/source/failed-attempt-original.txt": "c3c9dbfd80646f1ad2d6ea405d200a0dd8d794f8",
}
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
    """Validate tightly pinned, metadata-only private vault states; never transfer."""
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
    if dest.get("has_pages") is not False:
        raise VaultPreflightError("vault_pages_not_disabled")
    # GitHub's API on the real new private vault currently reports
    # allow_forking=true. We report the hold rather than silently treating
    # the private label as sufficient exfiltration/access protection.
    forks_blocked = dest.get("allow_forking") is False
    permissions = dest.get("permissions")
    if type(permissions) is not dict or permissions.get("admin") is not True:
        raise VaultPreflightError("vault_owner_access_unverified")
    if not branches:
        bootstrap = "uninitialized_empty"
    elif len(branches) == 1 and type(branches[0]) is dict and branches[0].get("name") == "main":
        # Only this exact policy README is permitted in a newly initialized
        # destination. A populated archive requires a separate *readback*
        # auditor, not this one-time bootstrap entry test.
        if dest.get("default_branch") != "main":
            raise VaultPreflightError("vault_bootstrap_default_branch_invalid")
        try:
            tree = api("repos/" + vault + "/git/trees/main?recursive=1")
        except VaultPreflightError:
            raise
        except (TypeError, KeyError, OSError, ValueError):
            raise VaultPreflightError("authenticated_api_unavailable") from None
        if type(tree) is not dict or tree.get("truncated") is not False:
            raise VaultPreflightError("vault_bootstrap_tree_invalid")
        files = tree.get("tree")
        if type(files) is not list or len(files) != 1:
            raise VaultPreflightError("vault_bootstrap_tree_not_readme_only")
        leaf = files[0]
        if (type(leaf) is not dict or leaf.get("path") != "README.md"
                or leaf.get("type") != "blob"
                or leaf.get("sha") != BOOTSTRAP_README_BLOB_SHA):
            raise VaultPreflightError("vault_bootstrap_readme_unverified")
        bootstrap = "verified_readme_only"
    elif len(branches) == 3:
        # This is a frozen, FICTIONAL-ONLY synthetic private pilot. Once a
        # genuine source archive ref exists, preflight must refuse this
        # bootstrap state and require a separately authenticated migration
        # inventory/reconciliation; never silently broaden its allowlist.
        if any(type(item) is not dict or type(item.get("name")) is not str
               or type(item.get("commit")) is not dict for item in branches):
            raise VaultPreflightError("vault_pilot_branches_invalid")
        actual = {item["name"]: item["commit"].get("sha") for item in branches}
        if (len(actual) != 3 or
                actual not in ({"main": PILOT_MAIN_SHA, **PILOT_REFS},
                               {"main": METADATA_MAIN_SHA, **PILOT_REFS},
                               {"main": GITHUB_ONLY_MAIN_SHA, **PILOT_REFS})):
            raise VaultPreflightError("vault_pilot_branches_changed")
        if dest.get("default_branch") != "main":
            raise VaultPreflightError("vault_bootstrap_default_branch_invalid")
        try:
            main_tree = api("repos/" + vault + "/git/trees/main?recursive=1")
            trees = [api("repos/" + vault + "/git/trees/" + sha + "?recursive=1")
                     for sha in PILOT_REFS.values()]
        except VaultPreflightError:
            raise
        except (TypeError, KeyError, OSError, ValueError):
            raise VaultPreflightError("authenticated_api_unavailable") from None
        if (type(main_tree) is not dict or main_tree.get("truncated") is not False
                or type(main_tree.get("tree")) is not list):
            raise VaultPreflightError("vault_pilot_main_changed")
        main_rows = main_tree["tree"]
        if actual["main"] == PILOT_MAIN_SHA:
            permitted_main = {
                "README.md": ("blob", BOOTSTRAP_README_BLOB_SHA),
            }
        elif actual["main"] == METADATA_MAIN_SHA:
            permitted_main = METADATA_MAIN_TREE
        else:
            permitted_main = GITHUB_ONLY_MAIN_TREE
        if (len(main_rows) != len(permitted_main)
                or any(type(row) is not dict for row in main_rows)):
            raise VaultPreflightError("vault_pilot_main_changed")
        main_observed = {
            row.get("path"): (row.get("type"), row.get("sha"))
            for row in main_rows
        }
        if main_observed != permitted_main:
            raise VaultPreflightError("vault_pilot_main_changed")
        for tree in trees:
            if type(tree) is not dict or tree.get("truncated") is not False:
                raise VaultPreflightError("vault_pilot_tree_invalid")
            rows = tree.get("tree")
            if (type(rows) is not list or len(rows) != len(PILOT_EXPECTED_BLOBS)
                    or any(type(row) is not dict or row.get("type") != "blob"
                           for row in rows)):
                raise VaultPreflightError("vault_pilot_tree_unexpected")
            observed = {row.get("path"): row.get("sha") for row in rows}
            if len(observed) != len(PILOT_EXPECTED_BLOBS) or observed != PILOT_EXPECTED_BLOBS:
                raise VaultPreflightError("vault_pilot_tree_unexpected")
        bootstrap = (
            "verified_github_only_policy_plus_metadata_and_fictional_pilot"
            if actual["main"] == GITHUB_ONLY_MAIN_SHA else
            "verified_korea_metadata_only_plus_fictional_pilot"
            if actual["main"] == METADATA_MAIN_SHA else
            "verified_fictional_copy_and_restore_only"
        )
    else:
        raise VaultPreflightError("vault_not_bootstrap_only")
    # Do NOT assume an accessible private repo grants Actions cross-repo write.
    # PR jobs and public source GITHUB_TOKEN may not see vault originals.
    return {
        "schema": REPORT_SCHEMA,
        "source_repo": source,
        "destination_repo": vault,
        "destination_visibility_verified": "private",
        "destination_identity_checked": True,
        "destination_initial_branches": len(branches),
        "bootstrap_state": bootstrap,
        "fictional_pilot_git_blob_parity_verified": (
            bootstrap in ("verified_fictional_copy_and_restore_only",
                          "verified_korea_metadata_only_plus_fictional_pilot",
                          "verified_github_only_policy_plus_metadata_and_fictional_pilot")),
        "main_branch_protection_verified": False,
        "pages_disabled_verified": True,
        "private_forking_disabled_verified": forks_blocked,
        "vault_access_hardening_complete": False,
        "operator_repo_admin_verified": True,
        "cross_repo_workflow_credential_verified": False,
        # Owner permits GitHub-only V1 custody. This records only the exact
        # observed policy blob, NOT a permissions grant for publisher bytes.
        "github_only_storage_choice_verified": (
            bootstrap == "verified_github_only_policy_plus_metadata_and_fictional_pilot"),
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
