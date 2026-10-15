"""Korea public-shadow legacy writer guard; NO private writer implemented.

This guard blocks Korea's existing public writer as soon as its pinned
legacy-only policy changes, including any future attempted private cutover.
A separate owner-authorized private writer must be implemented and verified
before deactivating the old collector. It cannot grant any authorization.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "ipr-korea-shadow-public-writer-hold/1"
STATE_BRANCH = "shadow/korea-policy-briefing"
INDONESIA_BRANCH = "shadow/indonesia-kemhan"
SEED_UTC = "2026-10-06T16:52:01.420713+00:00"
SEED_RUN = "local-native-20261006-korea"
EXPECTED = {
    "schema": SCHEMA,
    "mode": "legacy_public_shadow",
    "state_branch": STATE_BRANCH,
    "day_zero_utc": SEED_UTC,
    "day_zero_run_id": SEED_RUN,
    "private_writer_active": False,
    "private_copy_verified": False,
    "private_restore_verified": False,
    "private_cutover_authorized": False,
    "production_admission_authorized": False,
}


class WriterHold(ValueError):
    """Fixed reason codes; never print secrets, original bodies or paths."""


def require(ok, reason):
    if not ok:
        raise WriterHold(reason)


def assess(desk, branch, policy, *, stage):
    """Return a bounded PASS for *only* the pre-cutover legacy public writer.

    The input policy is repository configuration, not proof of real access,
    source retention authorization, backup, custody, or legitimate publication.
    """
    require(stage in ("pre_collect", "pre_public_push"),
            "invalid_writer_checkpoint")
    require(desk in ("indonesia", "korea"), "unknown_collector_desk")
    if desk == "indonesia":
        require(branch == INDONESIA_BRANCH, "indonesia_state_branch_changed")
        return {"schema": SCHEMA, "desk": "indonesia",
                "stage": stage, "indonesia_unchanged": True,
                "korea_cutover_authorized": False,
                "korea_public_writer_permitted_by_this_result": False}
    require(branch == STATE_BRANCH, "korea_public_branch_changed")
    require(type(policy) is dict, "korea_storage_policy_invalid")
    require(set(policy) == set(EXPECTED), "korea_storage_policy_extra_or_missing_fields")
    for key, expected in EXPECTED.items():
        require(type(policy[key]) is type(expected)
                and policy[key] == expected,
                "korea_legacy_public_writer_policy_changed")
    return {
        "schema": SCHEMA,
        "desk": "korea",
        "stage": stage,
        "legacy_public_state_branch": STATE_BRANCH,
        "legacy_public_writer_permitted": True,
        "private_repo_access_verified": False,
        "source_custody_migrated": False,
        "source_retention_rights_approved": False,
        "owner_cutover_authorized": False,
        "korea_production_admission_authorized": False,
        "sunday_ai_email_or_publication_authorized": False,
    }


def check_file(path, *, desk, branch, stage):
    require(type(path) is str and path != "", "missing_storage_policy")
    local = Path(path)
    require(local.is_file() and not local.is_symlink()
            and 0 < local.stat().st_size <= 4000, "korea_storage_policy_file_unavailable")
    try:
        payload = json.loads(local.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError):
        raise WriterHold("korea_storage_policy_json_invalid") from None
    return assess(desk, branch, payload, stage=stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--policy", required=True)
    parser.add_argument("--desk", required=True)
    parser.add_argument("--state-branch", required=True)
    parser.add_argument("--stage", choices=("pre_collect", "pre_public_push"),
                        required=True)
    args = parser.parse_args(argv)
    try:
        result = check_file(args.policy, desk=args.desk,
                            branch=args.state_branch, stage=args.stage)
    except WriterHold as exc:
        print(json.dumps({"schema": SCHEMA, "status": "HOLD",
                          "reason": str(exc),
                          "legacy_public_writer_permitted": False,
                          "korea_production_admission_authorized": False},
                         sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
