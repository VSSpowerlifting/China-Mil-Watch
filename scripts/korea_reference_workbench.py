"""Render private Korean source review workbench or signed-reference QA preview.

Never deploys, collects, writes an approval, or modifies a production artifact.
"""
import argparse
import json
from core.korea_reference_gate import (
    KoreaGateHold, approve, load_candidates, render, write_private,
)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", required=True, choices=("workbench", "release-preview"))
    p.add_argument("--out", required=True, help="new absolute private HTML path outside repo")
    p.add_argument("--approvals", help="external, reviewer/rights/owner-signed JSON file")
    p.add_argument("--explicit-private-preview", action="store_true",
                   help="acknowledge that approval artifacts are not independently authenticated")
    args = p.parse_args(argv)
    try:
        candidates = load_candidates()
        if args.mode == "release-preview":
            if not args.explicit_private_preview or args.approvals is None:
                raise KoreaGateHold("signed approvals and deliberate private-preview flag required")
        else:
            if args.approvals is not None or args.explicit_private_preview:
                raise KoreaGateHold("workbench must not import purported approvals")
        accepted = approve(candidates, args.approvals)
        if args.mode == "release-preview" and not accepted:
            raise KoreaGateHold("zero independently approved rows: release preview blocked")
        output = write_private(args.out, render(candidates, mode=args.mode,
                                                 accepted=accepted))
    except (OSError, KoreaGateHold, UnicodeError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "private_path": output, "mode": args.mode,
        "candidate_count": len(candidates), "approved_preview_count": len(accepted),
        "production_activated": False, "public_release_authorized": False,
        "no_publisher_requests": True, "source_state_commit": candidates[0] and
        "dcb43b9c4edb471d6def5876701ec4a2e39d5264",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
