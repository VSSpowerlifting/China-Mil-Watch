"""Render one source-verified Korean document and machine draft to private HTML.

No HTTP, LLM, SMTP, production SQLite, output/, gh-pages or public artifacts.
All publisher text/translation/source notes remain within the operator's
owner-only private paths. All decisions are PRIVATE_REVIEW_ONLY.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path

from core.korea_full_content_rehearsal import (
    ContentHold, check_candidate, render_private_html,
)
from scripts import stage_korea_production_candidates as stage

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON = 2_000_000


def private_file(path):
    p = Path(path).expanduser()
    if (not p.is_absolute() or p.is_symlink() or not p.is_file()
            or p.stat().st_size > MAX_JSON
            or stat.S_IMODE(p.stat().st_mode) & 0o077
            or ROOT == p.resolve() or ROOT in p.resolve().parents):
        raise ContentHold("private_input_must_be_owner_only_and_outside_repo")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise ContentHold("private_input_json_invalid") from None


def private_destination(path):
    p = Path(path).expanduser()
    if not p.is_absolute() or p.exists() or p.is_symlink():
        raise ContentHold("private_preview_must_be_a_new_absolute_file")
    parent = p.parent
    if (not parent.is_dir() or parent.is_symlink()
            or ROOT == parent.resolve() or ROOT in parent.resolve().parents
            or stat.S_IMODE(parent.stat().st_mode) & 0o077):
        raise ContentHold("private_preview_parent_must_be_owner_only_outside_repo")
    return p


def rehearse(source_checkout, identity, rights_path, draft_path, private_preview):
    out = private_destination(private_preview)
    rights = private_file(rights_path)
    draft = private_file(draft_path)
    packet = stage.build(source_checkout)
    stages = [r for r in packet["records"] if r["source_identity"] == identity]
    if len(stages) != 1:
        raise ContentHold("source_not_present_in_verified_shadow_capture")
    originals = [r for r in stage._rows(Path(source_checkout))
                 if r["source_identity"] == identity]
    if len(originals) != 1:
        raise ContentHold("original_not_unique_in_verified_shadow_capture")
    record = originals[0]
    receipt = check_candidate(stages[0], record, rights, draft)
    html = render_private_html(stages[0], record, rights, draft)
    # Re-read and verify the full captured original history before writing a
    # private preview, catching source checkout drift during review assembly.
    reread = stage.build(source_checkout)
    if (reread["source_git_commit"] != packet["source_git_commit"]
            or reread["source_db_sha256"] != packet["source_db_sha256"]
            or reread["records"] != packet["records"]):
        raise ContentHold("verified_shadow_source_changed_during_rehearsal")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(out, flags, 0o600), "w", encoding="utf-8") as stream:
        stream.write(html)
    receipt["private_preview_created"] = True
    receipt["private_preview_mode"] = "0600"
    return receipt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-checkout", required=True)
    p.add_argument("--source-identity", required=True)
    p.add_argument("--rights-observation", required=True)
    p.add_argument("--machine-draft", required=True)
    p.add_argument("--private-preview", required=True)
    p.add_argument("--explicit-private-no-publish", action="store_true")
    args = p.parse_args(argv)
    try:
        if not args.explicit_private_no_publish:
            raise ContentHold("explicit_private_rehearsal_acknowledgment_required")
        receipt = rehearse(
            args.source_checkout, args.source_identity, args.rights_observation,
            args.machine_draft, args.private_preview)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except (ContentHold, stage.IntakeHold, ValueError, OSError) as exc:
        reason = str(exc) if isinstance(exc, (ContentHold, stage.IntakeHold)) \
            else "private_source_or_input_unavailable"
        print(json.dumps({
            "status": "HOLD", "reason": reason,
            "public_files_written": 0, "production_records_written": 0,
            "original_document_redistribution_authorized": False,
            "translation_publication_authorized": False,
            "substantive_analysis_publication_authorized": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
