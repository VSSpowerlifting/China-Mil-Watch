"""Standing-approved automatic Korea original *text* admission, source-only.

Owner standing approval: future newly collected, independently proven
Korea MND / Policy Briefing originals marked KOGL Type 1 *text only*.
No model output, English translation, attachments, photos or interpretation.

The frozen initial 14 are a historical baseline, not authorized for
retroactive wholesale full-text release. This writes files in a disposable
runner, never pushes git or touches production SQLite itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from core.korea_archived_kogl_replay import KoreaArchivedMarkAdapter, MarkHold
from core.korea_current_policy_replay import CurrentKoreaPolicyReplay, PolicyHold
from core.korea_published_originals import INDEX, ORIGINAL_DIR, SCHEMA, PublishedKoreaHold, read_release_index
from core.korea_public_bibliography import load_public_korea_links
from core.korea_additional_public_links import load_additional_korea_official_links
from core.korea_text_only_exception_replay import KoreaTextOnlyExceptionReplay, ExceptionHold
from core.standing_source_rights import POLICIES, qualify_standing_text, StandingLicenseHold
from scripts import stage_korea_production_candidates as stage

RECEIPT = "ipr-korea-standing-verbatim-original-text-auto-admission/1"
SCOPE = "future_kr_mnd_kogl1_verbatim_text_only_2026_10_15"
MAX_NEW_PER_RUN = 4
MAX_PUBLISHED = 50
HASH = re.compile(r"[0-9a-f]{64}\Z")
SAFE_RUN = re.compile(r"[0-9]{3,24}\Z")
FROZEN = "0595f0fd29b769cbab5dd57c2ef57af174237a67"


class AutoTextHold(ValueError):
    """Only fixed machine codes, never raw evidence or Korean content."""


def require(ok, reason):
    if not ok:
        raise AutoTextHold(reason)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def baseline():
    """Exactly the 14 already-frozen original references, not future records."""
    previous = load_public_korea_links() + load_additional_korea_official_links()
    ids = {x["source_identity"] for x in previous}
    require(len(previous) == len(ids) == 14,
            "historical_korea_original_frontier_drift")
    return ids


def source_ancestor(checkout, old, new):
    """An unchanged source is valid when collector Git head advances."""
    if not re.fullmatch(r"[0-9a-f]{40}", old) or not re.fullmatch(r"[0-9a-f]{40}", new):
        return False
    result = subprocess.run(
        ["git", "-C", str(checkout), "merge-base", "--is-ancestor", old, new],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=15, check=False,
    )
    return result.returncode == 0


def verify_existing(rows, checkout):
    """Fail entire batch if any previously published source has drifted."""
    for row in rows:
        adapter = KoreaArchivedMarkAdapter(checkout, row["source_identity"])
        src = adapter.source
        proof = adapter.source_replay(src)
        require(source_ancestor(checkout, row["source_git_commit"], src["source_git_commit"]),
                "previously_published_korea_git_ancestry_changed")
        require(src["official_url"] == row["official_url"] and
                src["source_capture_sha256"] == row["source_html_sha256"] and
                src["publisher_posted_date"] == row["publisher_posted_date"] and
                proof["entire_clean_original_text_sha256"] == row["original_text_sha256"] and
                adapter.item_license_replay(src, "KOGL_TYPE_1_TEXT") is True,
                "previously_published_korea_original_changed")
        require(digest(adapter.read_original_text_private()) ==
                row["original_text_sha256"],
                "previously_published_korea_original_changed")


def validate_standing_context(env):
    """Only this exact main-branch workflow, never untrusted PR forks."""
    require(env.get("GITHUB_REPOSITORY") == "VSSpowerlifting/IndoPacificRecord"
            and env.get("GITHUB_REF") == "refs/heads/main"
            and env.get("GITHUB_EVENT_NAME") in ("schedule", "workflow_dispatch", "workflow_run", "push")
            and type(env.get("GITHUB_RUN_ID")) is str
            and SAFE_RUN.fullmatch(env["GITHUB_RUN_ID"]) is not None,
            "automatic_korea_release_context_invalid")
    return {"scope": SCOPE, "run_id": env["GITHUB_RUN_ID"],
            "method": "standing_2026_10_15_owner_authorization"}


def admit_eligible(checkout, *, index=INDEX, original_dir=ORIGINAL_DIR, context,
                   max_new=MAX_NEW_PER_RUN, policy_replay=None,
                   adapter_type=KoreaArchivedMarkAdapter,
                   exception_type=KoreaTextOnlyExceptionReplay,
                   packet=None, historical_ids=None,
                   ancestor=source_ancestor):
    """Qualify each newly seen source; holds are not publication decisions."""
    require(type(context) is dict and context.get("scope") == SCOPE
            and SAFE_RUN.fullmatch(str(context.get("run_id", ""))) is not None
            and type(max_new) is int and 1 <= max_new <= MAX_NEW_PER_RUN,
            "automatic_korea_standing_context_invalid")
    historical = baseline() if historical_ids is None else historical_ids
    require(type(historical) is set and len(historical) == 14,
            "historical_korea_original_frontier_drift")
    current = read_release_index(index, original_dir)
    require(len(current) <= MAX_PUBLISHED, "published_original_roster_exceeds_budget")
    lookup = {r["source_identity"]: r for r in current}

    # Abort on source inventory/ancestor faults before writing ANY text.
    packet = stage.build(str(checkout)) if packet is None else packet
    require(packet["source_git_commit"] and
            packet["source_original_count"] == len(packet["records"]) and
            len(packet["records"]) >= len(historical) and
            len(set(r["source_identity"] for r in packet["records"])) ==
            len(packet["records"]),
            "korea_frozen_archive_changed_or_incomplete")
    require({r["source_identity"] for r in packet["records"]} >= historical,
            "korea_frozen_fourteen_not_preserved")
    for row in current:
        adapter = adapter_type(checkout, row["source_identity"])
        src = adapter.source
        proof = adapter.source_replay(src)
        require(ancestor(checkout, row["source_git_commit"], src["source_git_commit"])
                and src["official_url"] == row["official_url"]
                and src["source_capture_sha256"] == row["source_html_sha256"]
                and src["publisher_posted_date"] == row["publisher_posted_date"]
                and proof["entire_clean_original_text_sha256"] == row["original_text_sha256"]
                and digest(adapter.read_original_text_private()) ==
                row["original_text_sha256"],
                "previously_published_korea_original_changed")

    candidates = sorted(
        (r for r in packet["records"]
         if r["source_identity"] not in historical and
         r["source_identity"] not in lookup),
        key=lambda x: (x["publisher_posted_date"], x["source_identity"]),
    )
    # The new license is verified every run before ANY candidate is written.
    if not candidates:
        return {"schema": RECEIPT, "status": "NO_NEW_FUTURE_KOREA_ORIGINALS",
                "new_original_texts": 0, "held_candidates": 0,
                "historical_baseline_excluded": len(historical),
                "production_db_changed": False}
    policy = POLICIES["kr_policy_mnd_releases"]
    verified_policy = (CurrentKoreaPolicyReplay()(policy)
                       if policy_replay is None else policy_replay(policy))
    require(type(verified_policy) is dict and
            type(verified_policy.get("publisher_policy_sha256")) is str and
            HASH.fullmatch(verified_policy["publisher_policy_sha256"]) is not None,
            "korea_current_policy_unverified")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def replay(expected):
        require(expected == policy, "korea_standing_policy_family_changed")
        return verified_policy

    added, held = [], []
    for item in candidates:
        if len(added) >= max_new or len(current) + len(added) >= MAX_PUBLISHED:
            break
        identity = item["source_identity"]
        if item.get("editorial_exception") is not None:
            held.append(identity)
            continue
        try:
            adapter = adapter_type(checkout, identity)
            src = adapter.source
            raw = adapter.read_original_text_private()
            text_sha = digest(raw)
            require(text_sha == item["original_text_sha256"],
                    "candidate_original_text_mismatch")
            rights_checker = exception_type(adapter)
            proof = qualify_standing_text(
                src, kind="original_text", proposed_sha256=text_sha,
                attribution=("Republic of Korea Ministry of National Defense via "
                             "Korea Policy Briefing. KOGL Type 1 text only. Source: "
                             + src["official_url"]),
                now_utc=now, source_replay=adapter.source_replay,
                policy_replay=replay, exception_replay=rights_checker,
                item_license_replay=adapter.item_license_replay)
            require(proof["original_text_matches_authenticated_capture"] is True
                    and rights_checker.last_screen is not None,
                    "candidate_source_license_or_exception_failed")
        except (AutoTextHold, MarkHold, ExceptionHold, StandingLicenseHold,
                ValueError, UnicodeError, OSError):
            held.append(identity)
            continue
        decision = digest(canonical({
            "scope": SCOPE, "run": context["run_id"],
            "source_identity": identity, "original_text_sha256": text_sha,
            "source_capture_sha256": src["source_capture_sha256"],
            "source_git_commit": src["source_git_commit"],
            "current_policy_sha256": verified_policy["publisher_policy_sha256"],
        }))
        record = {
            "source_identity": identity,
            "official_url": src["official_url"],
            "publisher_posted_date": src["publisher_posted_date"],
            "source_git_commit": src["source_git_commit"],
            "original_text_sha256": text_sha,
            "source_html_sha256": src["source_capture_sha256"],
            "policy_sha256": verified_policy["publisher_policy_sha256"],
            "release_decision_sha256": decision,
            "released_at_utc": now,
        }
        added.append((record, raw))
    if not added:
        return {"schema": RECEIPT, "status": "FUTURE_KOREA_CANDIDATES_HELD",
                "new_original_texts": 0, "held_candidates": len(held),
                "historical_baseline_excluded": len(historical),
                "production_db_changed": False}

    original_dir = Path(original_dir)
    index = Path(index)
    require(index.is_file() and not index.is_symlink() and
            original_dir.parent.is_dir() and not original_dir.is_symlink(),
            "automatic_korea_original_destination_invalid")
    original_dir.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    for record, raw in added:
        dest = original_dir / (record["source_identity"].partition(":")[2] + ".txt")
        require(not dest.exists() and not dest.is_symlink(),
                "new_korea_original_path_collision")
        with os.fdopen(os.open(dest, flags, 0o644), "wb") as f:
            f.write(raw)
    proposed = [{k: r[k] for k in (
        "source_identity", "official_url", "publisher_posted_date", "source_git_commit",
        "original_text_sha256", "source_html_sha256", "policy_sha256",
        "release_decision_sha256", "released_at_utc"
    )} for r in current] + [r for r, _ in added]
    payload = canonical({"schema": SCHEMA, "records": proposed}) + b"\n"
    require(len(payload) <= 250000, "automatic_korea_index_limit_exceeded")
    temporary = index.with_name(index.name + ".auto-new")
    with os.fdopen(os.open(temporary, flags, 0o644), "wb") as f:
        f.write(payload)
    os.replace(temporary, index)
    parsed = read_release_index(index, original_dir)
    require(len(parsed) == len(current) + len(added),
            "automatic_korea_original_registry_roundtrip_failed")
    return {"schema": RECEIPT, "status": "STANDING_LICENSE_TEXT_READY_FOR_KOREA_PUBLIC_RELEASE",
            "new_original_texts": len(added), "held_candidates": len(held),
            "historical_baseline_excluded": len(historical),
            "production_db_changed": False,
            "source_identities": [r["source_identity"] for r, _ in added]}


def main(argv=None):
    p = argparse.ArgumentParser(description="Admit future KOGL-marked Korea original text")
    p.add_argument("--source-checkout", required=True)
    p.add_argument("--standing-owner-approval-original-text-only", action="store_true")
    args = p.parse_args(argv)
    try:
        require(args.standing_owner_approval_original_text_only,
                "automatic_korea_text_scope_not_authorized")
        ctx = validate_standing_context(os.environ)
        print(json.dumps(admit_eligible(args.source_checkout, context=ctx),
                         sort_keys=True))
        return 0
    except (AutoTextHold, MarkHold, PolicyHold, PublishedKoreaHold,
            ExceptionHold, StandingLicenseHold, stage.IntakeHold,
            UnicodeError, ValueError, OSError, subprocess.TimeoutExpired):
        print(json.dumps({"schema": RECEIPT, "status": "HOLD",
                          "production_db_changed": False,
                          "source_bodies_logged": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
