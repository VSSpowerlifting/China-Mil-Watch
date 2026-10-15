"""Create/check ONLY local Korea Week-42 human review records, without any send.

Neither an apparently complete form nor this program establishes identity,
copyright permission, site/model access, or Sunday's editorial eligibility.
"""
import argparse
import json

from core.korea_week42_private_review import (
    check_private_review, create_private_template,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", help="new absolute local private JSON file")
    group.add_argument("--check", help="existing absolute local private JSON file")
    parser.add_argument("--explicit-local-only", action="store_true", required=True,
                        help="acknowledge nothing is sent or admitted for publication")
    opts = parser.parse_args(argv)
    if not opts.explicit_local_only:
        parser.error("--explicit-local-only is required")
    if opts.create:
        create_private_template(opts.create)
        receipt = {
            "action": "private_review_template_created",
            "candidate_count": 3,
            "human_approvals_claimed": False,
            "rights_approved": False,
            "model_use_authorized": False,
            "email_sent": False,
            "publication_authorized": False,
        }
    else:
        receipt = check_private_review(opts.check)
    # Never log names, notes, original Korean prose or absolute review paths.
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
