"""Owner-reviewed, exact-source English translation + analysis admission.

This is separate from standing permission to auto-publish Korean *original*
text. Neither model output nor an untrusted reviewer's JSON can authorize a
public translation or IPR analysis. Require authenticated owner workflow_dispatch
and the exact SHA of the reviewed editorial packet already on main.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from core.korea_english_publication import (
    REGISTER, INDEX, CONTENT_DIR, KoreaEnglishHold, SOURCE_RE,
    public_registry, verify_review,
)
from core.korea_published_originals import read_release_index

HASH = re.compile(r"[0-9a-f]{64}\Z")
RUN = re.compile(r"[0-9]{3,24}\Z")
REPOSITORY = "VSSpowerlifting/IndoPacificRecord"
OWNER = "VSSpowerlifting"


def need(ok, reason):
    if not ok:
        raise KoreaEnglishHold(reason)


def owner_event(env):
    need(env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
         and env.get("GITHUB_REPOSITORY") == REPOSITORY
         and env.get("GITHUB_REF") == "refs/heads/main"
         and env.get("GITHUB_ACTOR") == OWNER
         and type(env.get("GITHUB_RUN_ID")) is str
         and RUN.fullmatch(env["GITHUB_RUN_ID"]) is not None,
         "korea_english_owner_authenticated_dispatch_required")
    return env["GITHUB_RUN_ID"]


def admit(identity, approved_pack_sha256, run_id, *,
          index=INDEX, directory=CONTENT_DIR, source_index=None,
          source_dir=None):
    need(type(identity) is str and SOURCE_RE.fullmatch(identity) is not None
         and type(approved_pack_sha256) is str and
         HASH.fullmatch(approved_pack_sha256) is not None
         and type(run_id) is str and RUN.fullmatch(run_id) is not None,
         "korea_english_release_owner_input_invalid")
    index, directory = Path(index), Path(directory)
    existing = public_registry(index, directory,
                               source_index=source_index,source_dir=source_dir)
    selected = {row["source_identity"]: row for row, _, _ in existing}
    number = identity.partition(":")[2]
    path = directory / (number + ".json")
    need(path.is_file() and not path.is_symlink()
         and path.stat().st_size <= 1_000_000,
         "korea_english_reviewed_pack_missing")
    try:
        packet = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (ValueError, UnicodeError):
        raise KoreaEnglishHold("korea_english_reviewed_pack_invalid") from None
    origin_args = {}
    if source_index is not None:
        origin_args["index"] = source_index
    if source_dir is not None:
        origin_args["original_dir"] = source_dir
    originals = {r["source_identity"]: r for r in read_release_index(**origin_args)}
    need(identity in originals,
         "korea_english_source_original_not_yet_public")
    receipt = verify_review(packet, originals[identity])
    need(receipt["review_sha256"] == approved_pack_sha256,
         "korea_english_owner_approved_review_sha_mismatch")
    if identity in selected:
        existing_row = selected[identity]
        need(existing_row["review_sha256"] == approved_pack_sha256
             and existing_row["source_sha256"] == originals[identity]["original_text_sha256"],
             "korea_english_published_review_immutable")
        return {"status":"EXACT_REVIEW_ALREADY_PUBLISHED",
                "new_english_releases":0,"source_identity":identity}
    need(len(existing) < 50, "korea_english_publication_limit_exceeded")
    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise KoreaEnglishHold("korea_english_registry_invalid") from None
    next_row = {
        "source_identity": identity,
        "source_sha256": originals[identity]["original_text_sha256"],
        "review_sha256": approved_pack_sha256,
        "owner_run_id": run_id,
        "released_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    payload["releases"].append(next_row)
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")) + "\n").encode("utf-8")
    need(len(raw) <= 240000, "korea_english_registry_limit_exceeded")
    temp = index.with_name(index.name + ".new-release")
    need(not temp.exists() and not temp.is_symlink(),
         "korea_english_registry_temp_path_taken")
    flags = os.O_CREAT | os.O_WRONLY | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(temp, flags, 0o644), "wb") as stream:
        stream.write(raw)
    os.replace(temp, index)
    published = public_registry(index, directory,
                                source_index=source_index,source_dir=source_dir)
    need(len(published) == len(existing) + 1,
         "korea_english_published_registry_roundtrip_failed")
    return {"status":"REVIEWED_ENGLISH_AND_ANALYSIS_READY_FOR_PAGES",
            "new_english_releases":1,"source_identity":identity,
            "review_sha256":receipt["review_sha256"],
            "approved_paragraphs":receipt["paragraphs"],
            "approved_cited_analysis_claims":receipt["claims"]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-identity",required=True)
    p.add_argument("--review-sha256",required=True)
    p.add_argument("--owner-approves-reviewed-english-and-analysis",
                   action="store_true")
    args=p.parse_args(argv)
    try:
        need(args.owner_approves_reviewed_english_and_analysis,
             "korea_english_explicit_editorial_approval_missing")
        run_id=owner_event(os.environ)
        info=admit(args.source_identity,args.review_sha256,run_id)
        print(json.dumps(info,sort_keys=True))
        return 0
    except (KoreaEnglishHold,OSError,ValueError):
        print(json.dumps({"status":"HOLD","english_publication_authorized":False,
                          "public_pages_committed":False},sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
