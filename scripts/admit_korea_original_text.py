"""Admit one exact Korean official original text on an authenticated owner run.

Only the named source SHA is eligible. Verifies preserved Git/HWPX, article
KOGL mark, current official terms, and bounded exception flags before any
publication files are created. Does not mirror HWPX/media, generate model
content, change SQLite, or push branches. Workflow controls publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from core.korea_archived_kogl_replay import KoreaArchivedMarkAdapter, MarkHold
from core.korea_current_policy_replay import CurrentKoreaPolicyReplay, PolicyHold
from core.korea_published_originals import (
    INDEX, ORIGINAL_DIR, SCHEMA, PublishedKoreaHold, read_release_index,
)
from core.korea_text_only_exception_replay import (
    ExceptionHold, KoreaTextOnlyExceptionReplay,
)
from core.standing_source_rights import (
    POLICIES, StandingLicenseHold, qualify_standing_text,
)
from scripts.stage_korea_production_candidates import IntakeHold

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = re.compile(r"korea-policy:[0-9]{9}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
RECEIPT = "ipr-korea-owner-dispatched-original-text-admission/1"
OWNER = "VSSpowerlifting"
REPOSITORY = "VSSpowerlifting/IndoPacificRecord"


class OriginalAdmissionHold(ValueError):
    """Fixed reason codes only; never log source text or credentials."""


def need(value, reason):
    if not value:
        raise OriginalAdmissionHold(reason)


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def check_owner_dispatch(environ):
    """A CLI flag by itself cannot substitute for the GitHub owner identity."""
    need(environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
         and environ.get("GITHUB_ACTOR") == OWNER
         and environ.get("GITHUB_REPOSITORY") == REPOSITORY
         and environ.get("GITHUB_REF") == "refs/heads/main"
         and type(environ.get("GITHUB_RUN_ID")) is str
         and re.fullmatch(r"[0-9]{3,24}", environ["GITHUB_RUN_ID"]),
         "authenticated_owner_workflow_dispatch_required")
    return {
        "actor": environ["GITHUB_ACTOR"],
        "repository": environ["GITHUB_REPOSITORY"],
        "run_id": environ["GITHUB_RUN_ID"],
        "scope": "korea_kogl_type1_verbatim_text_only",
    }


def admit(source_checkout, identity, exact_sha, *, owner_event,
          index=INDEX, originals_dir=ORIGINAL_DIR):
    need(type(identity) is str and IDENTITY.fullmatch(identity) is not None
         and type(exact_sha) is str and SHA.fullmatch(exact_sha) is not None,
         "requested_original_identity_or_sha_invalid")
    need(type(owner_event) is dict
         and owner_event.get("actor") == OWNER
         and owner_event.get("repository") == REPOSITORY
         and owner_event.get("scope") == "korea_kogl_type1_verbatim_text_only"
         and type(owner_event.get("run_id")) is str
         and re.fullmatch(r"[0-9]{3,24}", owner_event["run_id"]),
         "owner_dispatch_scope_unverified")

    # Validating old rows also prevents quietly overwriting a previous source.
    prior = read_release_index(index, originals_dir)
    adapter = KoreaArchivedMarkAdapter(source_checkout, identity)
    source = adapter.source
    original = adapter.read_original_text_private()
    need(sha(original) == exact_sha, "owner_approved_original_sha_does_not_match")
    marked = adapter.item_license_replay(source, "KOGL_TYPE_1_TEXT")
    need(marked is True, "article_specific_text_license_not_verified")
    checker = KoreaTextOnlyExceptionReplay(adapter)
    live_policy = CurrentKoreaPolicyReplay()(POLICIES["kr_policy_mnd_releases"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def policy_replay(policy):
        need(policy == POLICIES["kr_policy_mnd_releases"],
             "standing_license_family_changed")
        return live_policy

    receipt = qualify_standing_text(
        source, kind="original_text", proposed_sha256=exact_sha,
        attribution=("Republic of Korea Ministry of National Defense via "
                     "Korea Policy Briefing; KOGL Type 1 source "
                     + source["official_url"]),
        now_utc=now, source_replay=adapter.source_replay,
        policy_replay=policy_replay, exception_replay=checker,
        item_license_replay=adapter.item_license_replay)
    need(receipt["original_text_matches_authenticated_capture"] is True
         and checker.last_screen is not None,
         "source_rights_and_exceptions_not_verified")

    # A retry may repair Pages without changing the previously approved public
    # source/version or manufacturing a second release decision.
    existing = [row for row in prior if row["source_identity"] == identity]
    if existing:
        old = existing[0]
        need(len(existing) == 1
             and old["original_text_sha256"] == exact_sha
             and old["source_git_commit"] == source["source_git_commit"]
             and old["source_html_sha256"] == source["source_capture_sha256"]
             and old["text_original"].encode("utf-8") == original,
             "existing_public_original_must_not_be_replaced")
        return {"schema": RECEIPT, "status": "EXISTING_EXACT_ORIGINAL_VERIFIED",
                "identity": identity, "original_sha256": exact_sha,
                "added_public_source_records": 0,
                "publisher_assets_included": False,
                "production_sqlite_changed": False}

    need(len(prior) < 50, "korea_public_original_roster_full")
    index = Path(index)
    originals_dir = Path(originals_dir)
    need(index.is_file() and not index.is_symlink()
         and originals_dir.parent.is_dir()
         and not originals_dir.is_symlink()
         and not index.parent.is_symlink(),
         "public_original_destination_invalid")
    ident_num = identity.partition(":")[2]
    dest = originals_dir / (ident_num + ".txt")
    need(not dest.exists() and not dest.is_symlink(),
         "public_original_source_path_already_exists")
    decision = sha(canonical({**owner_event, "identity": identity,
                             "text_sha256": exact_sha,
                             "source_git_commit": source["source_git_commit"],
                             "publisher_html_sha256": source["source_capture_sha256"]}))
    record = {
        "source_identity": identity,
        "official_url": source["official_url"],
        "publisher_posted_date": source["publisher_posted_date"],
        "source_git_commit": source["source_git_commit"],
        "original_text_sha256": exact_sha,
        "policy_sha256": live_policy["publisher_policy_sha256"],
        "source_html_sha256": source["source_capture_sha256"],
        "release_decision_sha256": decision,
        "released_at_utc": now,
    }
    next_rows = [{k: row[k] for k in record} for row in prior] + [record]
    proposed = canonical({"schema": SCHEMA, "records": next_rows}) + b"\n"
    need(len(proposed) <= 250000, "public_original_registry_budget_exceeded")

    originals_dir.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(dest, flags, 0o644), "wb") as out:
        out.write(original)
    try:
        # Output content is public by deliberate owner workflow approval.
        # Atomic single-file registry replacement occurs only after source
        # bytes are securely materialized; no git commits happen here.
        temporary = index.with_name(index.name + ".korea-new")
        need(not temporary.exists() and not temporary.is_symlink(),
             "temporary_public_index_path_taken")
        with os.fdopen(os.open(temporary, flags, 0o644), "wb") as out:
            out.write(proposed)
        os.replace(temporary, index)
        checked = read_release_index(index, originals_dir)
        need(len(checked) == len(prior) + 1 and
             any(row["source_identity"] == identity
                 and row["text_original"].encode("utf-8") == original
                 for row in checked),
             "public_original_exact_byte_roundtrip_failed")
    except Exception:
        # Failing workflow never commits. Preserve prior index; leave the
        # uncommitted file for runner teardown, never publish it.
        raise
    return {
        "schema": RECEIPT,
        "status": "OWNER_DISPATCHED_TEXT_ONLY_FILES_READY_FOR_RELEASE",
        "identity": identity,
        "original_sha256": exact_sha,
        "release_decision_sha256": decision,
        "publisher_policy_sha256": live_policy["publisher_policy_sha256"],
        "added_public_source_records": 1,
        "publisher_assets_included": False,
        "production_sqlite_changed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-checkout", required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--owner-approved-verbatim-korean-text-only",
                        action="store_true")
    args = parser.parse_args(argv)
    try:
        need(args.owner_approved_verbatim_korean_text_only,
             "explicit_public_text_only_approval_required")
        event = check_owner_dispatch(os.environ)
        out = admit(args.source_checkout, args.identity, args.expected_sha256,
                    owner_event=event)
    except (OriginalAdmissionHold, MarkHold, PolicyHold,
            PublishedKoreaHold, ExceptionHold, StandingLicenseHold,
            IntakeHold, UnicodeError, ValueError, OSError):
        print(json.dumps({"schema": RECEIPT, "status": "HOLD",
                          "production_sqlite_changed": False,
                          "public_files_committed": False}, sort_keys=True))
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
