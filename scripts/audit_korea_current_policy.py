"""Read-only current Korea reuse policy HTTP verification; logs hashes only."""
from __future__ import annotations

import json

from core.korea_current_policy_replay import CurrentKoreaPolicyReplay, PolicyHold
from core.standing_source_rights import POLICIES


def main():
    try:
        proof = CurrentKoreaPolicyReplay()(POLICIES["kr_policy_mnd_releases"])
    except (PolicyHold, ValueError, OSError):
        print(json.dumps({
            "status": "HOLD",
            "policy_authenticated": False,
            "production_records_written": 0,
            "public_files_written": 0,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "CURRENT_TEXT_TERMS_OBSERVED",
        "policy_id": proof["policy_id"],
        "observed_at_utc": proof["observed_at_utc"],
        "publisher_policy_sha256": proof["publisher_policy_sha256"],
        "original_source_mark_authenticated": False,
        "item_exception_review_complete": False,
        "public_release_authorized": False,
        "production_records_written": 0,
        "public_files_written": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
