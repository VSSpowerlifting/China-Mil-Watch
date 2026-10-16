"""Verify an exact owner-initiated Korean original-text release, read-only.

Production authentication comes from the GitHub workflow_dispatch actor and its
bound expected original SHA. This module performs independent frozen-source,
article KOGL, live standing-policy and exception checks for EVERY registered
public original; it never grants owner consent or writes files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone

from core.korea_archived_kogl_replay import KoreaArchivedMarkAdapter, MarkHold
from core.korea_current_policy_replay import CurrentKoreaPolicyReplay, PolicyHold
from core.korea_published_originals import PublishedKoreaHold, read_release_index
from core.korea_text_only_exception_replay import (
    ExceptionHold, KoreaTextOnlyExceptionReplay,
)
from core.standing_source_rights import (
    POLICIES, StandingLicenseHold, qualify_standing_text,
)
from scripts.stage_korea_production_candidates import IntakeHold

SCHEMA = "ipr-korea-original-text-publication-preflight/1"
SHA = re.compile(r"[0-9a-f]{64}\Z")
SOURCE = re.compile(r"korea-policy:[0-9]{9}\Z")
MAX_LIVE_ORIGINALS = 50


class ReleaseHold(ValueError):
    """Fixed reason codes, never publisher body or reviewer material."""


def require(ok, reason):
    if not ok:
        raise ReleaseHold(reason)


def validate_intent(records, identity, exact_original_sha):
    """No batch surprise: the explicitly named record must match exact bytes."""
    require(type(identity) is str and SOURCE.fullmatch(identity) is not None
            and type(exact_original_sha) is str
            and SHA.fullmatch(exact_original_sha) is not None,
            "owner_release_identity_or_sha_invalid")
    require(type(records) is list and 1 <= len(records) <= MAX_LIVE_ORIGINALS,
            "registered_original_count_out_of_bounds")
    selected = [r for r in records if r["source_identity"] == identity]
    require(len(selected) == 1 and
            selected[0]["original_text_sha256"] == exact_original_sha,
            "approved_identity_and_exact_text_sha_mismatch")
    return selected[0]


def verify(source_checkout, identity, expected_sha):
    entries = read_release_index()
    validate_intent(entries, identity, expected_sha)
    policy = POLICIES["kr_policy_mnd_releases"]
    # HTTPS policy observation must precede the issuance timestamp, not vice
    # versa. Treat the observed policy as one authenticated snapshot per run.
    live_terms = CurrentKoreaPolicyReplay()(policy)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def current_policy_replay(candidate):
        if candidate != policy:
            raise ReleaseHold("current_policy_family_changed")
        return live_terms

    results = []
    for record in entries:
        adapter = KoreaArchivedMarkAdapter(source_checkout,
                                           record["source_identity"])
        src = adapter.source
        proof = adapter.source_replay(src)
        require(src["official_url"] == record["official_url"]
                and src["publisher_posted_date"] == record["publisher_posted_date"]
                and src["source_git_commit"] == record["source_git_commit"]
                and src["source_capture_sha256"] == record["source_html_sha256"]
                and proof["entire_clean_original_text_sha256"] ==
                record["original_text_sha256"]
                and record["policy_sha256"] ==
                live_terms["publisher_policy_sha256"],
                "public_registry_source_or_policy_drift")
        raw = adapter.read_original_text_private()
        require(hashlib.sha256(raw).hexdigest() ==
                record["original_text_sha256"]
                and raw.decode("utf-8", "strict") == record["text_original"],
                "public_original_not_identical_to_archived_hwpx_text")
        exception = KoreaTextOnlyExceptionReplay(adapter)
        rights = qualify_standing_text(
            src, kind="original_text",
            proposed_sha256=record["original_text_sha256"],
            attribution=(
                "Republic of Korea Ministry of National Defense; "
                "published via Korea Policy Briefing. "
                "KOGL Type 1 (text only); original " + src["official_url"]
            ),
            now_utc=now,
            source_replay=adapter.source_replay,
            policy_replay=current_policy_replay,
            exception_replay=exception,
            item_license_replay=adapter.item_license_replay)
        require(rights["original_text_matches_authenticated_capture"] is True
                and exception.last_screen is not None
                and not any((
                    exception.last_screen["third_party_indicators_present"],
                    exception.last_screen["alternate_license_indicators_present"],
                    exception.last_screen[
                        "sensitive_personal_or_restricted_indicators_present"],
                )), "source_item_not_eligible_for_automatic_text_scope")
        results.append({
            "identity": record["source_identity"],
            "original_sha256": record["original_text_sha256"],
            "route": record["route"],
        })
    return {
        "schema": SCHEMA,
        "status": "EXACT_TEXT_RIGHTS_REVERIFIED_NOT_YET_DEPLOYED",
        "owner_approval_verified_by_this_script": False,
        "current_publisher_policy_sha256": live_terms["publisher_policy_sha256"],
        "source_count": len(results),
        "sources": results,
        "production_db_changed": False,
        "public_pages_changed": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-checkout", required=True)
    p.add_argument("--owner-dispatched-identity", required=True)
    p.add_argument("--owner-dispatched-original-sha256", required=True)
    args = p.parse_args(argv)
    try:
        data = verify(args.source_checkout, args.owner_dispatched_identity,
                      args.owner_dispatched_original_sha256)
    except (ReleaseHold, MarkHold, PolicyHold, PublishedKoreaHold,
            ExceptionHold, StandingLicenseHold, IntakeHold,
            ValueError, OSError, UnicodeError):
        print(json.dumps({
            "schema": SCHEMA, "status": "HOLD",
            "original_bodies_logged": False,
            "production_db_changed": False,
            "public_pages_changed": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(data, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
