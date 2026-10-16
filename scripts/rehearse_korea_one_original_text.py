"""One real preserved Korean original → authenticated private text-only preview.

No production DB, no Pages, no original attachments, no model, no editor email.
The owner may review private output locally; the CI run never uploads it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from core.korea_archived_kogl_replay import KoreaArchivedMarkAdapter, MarkHold
from core.korea_current_policy_replay import CurrentKoreaPolicyReplay, PolicyHold
from core.korea_text_only_exception_replay import (
    ExceptionHold, KoreaTextOnlyExceptionReplay,
)
from core.standing_source_rights import (
    StandingLicenseHold, stage_verified_original_text,
)
from scripts.stage_korea_production_candidates import IntakeHold

SCHEMA = "ipr-korea-real-original-private-stage/1"


def rehearse(checkout, identity, target):
    adapter = KoreaArchivedMarkAdapter(checkout, identity)
    screen = KoreaTextOnlyExceptionReplay(adapter)
    source = adapter.source
    raw = adapter.read_original_text_private()
    rights = CurrentKoreaPolicyReplay()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    attribution = (
        "Republic of Korea Ministry of National Defense, published through "
        "Korea Policy Briefing (Republic of Korea). KOGL Type 1 text only; "
        "source: " + source["official_url"]
    )
    receipt = stage_verified_original_text(
        source,
        original_utf8=raw,
        attribution=attribution,
        now_utc=stamp,
        target_dir=target,
        source_replay=adapter.source_replay,
        policy_replay=rights,
        exception_replay=screen,
        item_license_replay=adapter.item_license_replay,
    )
    dest = Path(target)
    text = (dest / "original.txt").read_bytes()
    page = (dest / "index.html").read_text(encoding="utf-8")
    if (hashlib.sha256(text).hexdigest() != receipt["staged_original_text_sha256"]
            or text != raw or "noindex" not in page
            or source["official_url"] not in page
            or screen.last_screen is None):
        raise ExceptionHold("private_original_staged_bytes_mismatch")
    return {
        "schema": SCHEMA,
        "status": "PRIVATE_REAL_SOURCE_REHEARSAL_ONLY",
        "source_identity": identity,
        "source_git_commit": source["source_git_commit"],
        "source_sha256": receipt["staged_original_text_sha256"],
        "policy_sha256": rights.last_policy_sha256,
        "official_license_mark_replayed": True,
        "screened_exceptions_present": False,
        "text_bytes_staged_private": len(text),
        "noindex_private_preview": True,
        "full_hwpx_or_media_written": False,
        "translation_or_analysis_generated": False,
        "public_release_authorized": False,
        "production_records_written": 0,
        "public_files_written": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Real original into private staging only")
    p.add_argument("--source-checkout", required=True)
    p.add_argument("--source-identity", required=True)
    p.add_argument("--private-output", required=True)
    p.add_argument("--explicit-private-no-publish", action="store_true")
    args = p.parse_args(argv)
    try:
        if not args.explicit_private_no_publish:
            raise ExceptionHold("private_rehearsal_acknowledgment_missing")
        result = rehearse(args.source_checkout, args.source_identity,
                          args.private_output)
    except (MarkHold, PolicyHold, ExceptionHold, StandingLicenseHold,
            IntakeHold, ValueError, OSError) as exc:
        # Only static, bounded machine-readable codes. Never source text, JSON,
        # publisher HTML, Korean original bodies or arbitrary OSError paths.
        code = str(exc) if type(exc) in (
            MarkHold, PolicyHold, ExceptionHold, StandingLicenseHold,
            IntakeHold) else ""
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,127}", code):
            code = "private_source_or_policy_unavailable"
        print(json.dumps({
            "schema": SCHEMA, "status": "HOLD", "reason_code": code,
            "production_records_written": 0,
            "public_files_written": 0,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
