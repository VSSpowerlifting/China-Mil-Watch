"""Korea collector -> normalized, HELD production-candidate bridge (offline).

This is a read-only, source-version-bound intake bridge, NOT promotion:
no production DB writes, no Korean originals in outputs, no model, email,
public articles, source-use grant or new collection. Run against an already
available, clean, frozen-ancestor Korea shadow Git checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
from datetime import date
from pathlib import Path

from scripts.verify_korea_private_custody_equivalence import (
    FROZEN_14, CustodyHold, inventory,
)
from scripts.audit_korea_source_fidelity import source_compare

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "shadow/kr_policy_briefing/manifest.json"
SCHEMA = "ipr-korea-versioned-production-candidates/1"
RECEIPT = "ipr-korea-production-intake-read-only-receipt/1"
SOURCE = "kr_policy_mnd_releases"
URL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId="
ARTICLE = re.compile(r"korea-policy:([0-9]{9})\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
RUN = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
ROWS = 5000
MAX_OUTPUT = 3_000_000


class IntakeHold(ValueError):
    """Safe error codes; never print original titles, Korean body or credentials."""


def need(ok, code):
    if not ok:
        raise IntakeHold(code)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def source_contract():
    try:
        m = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise IntakeHold("korea_source_manifest_unavailable") from None
    need(type(m) is dict and m.get("_shadow") is True
         and type(m.get("desk")) is dict
         and m["desk"].get("desk_id") == "korea"
         and m["desk"].get("public_status") == "shadow"
         and m["desk"].get("active") is False
         and type(m.get("sources")) is list
         and len(m["sources"]) == 1, "korea_not_shadow_only")
    src = m["sources"][0]
    need(src.get("slug") == SOURCE
         and src.get("authority_tier") == "B"
         and src.get("originality") == "syndicated"
         and src.get("language_tag") == "ko"
         and src.get("base_url") == "https://www.korea.kr"
         and src.get("institution_id") == "kr_policy_briefing",
         "korea_source_issuer_or_tier_changed")
    return src


def _date(value):
    need(type(value) is str and len(value) == 10, "invalid_portal_date")
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise IntakeHold("invalid_portal_date") from None
    need(day.isoformat() == value, "invalid_portal_date")
    return value


def _normalized(record):
    need(type(record) is dict, "invalid_shadow_row")
    ident = record.get("source_identity")
    matched = ARTICLE.fullmatch(ident) if type(ident) is str else None
    need(matched is not None, "non_korea_release_identity")
    sid = matched.group(1)
    page = record.get("capture_sha256")
    text_hash = record.get("content_sha256")
    meta = record.get("metadata_json")
    need(type(meta) is str and len(meta) <= 16000,
         "invalid_shadow_metadata")
    try:
        m = json.loads(meta)
    except ValueError:
        raise IntakeHold("invalid_shadow_metadata") from None
    need(type(m) is dict, "invalid_shadow_metadata")
    hwpx = m.get("document_capture_sha256")
    need(all(type(sha) is str and HASH.fullmatch(sha) is not None
             for sha in (page, text_hash, hwpx)),
         "missing_capture_or_text_hash")
    original = record.get("text_original")
    title = record.get("title_original")
    need(type(original) is str and original.strip()
         and len(original) <= 200000
         and digest(original.encode("utf-8")) == text_hash,
         "original_text_hash_mismatch")
    need(type(title) is str and 0 < len(title) <= 3000,
         "invalid_original_title")
    need(record.get("url") == URL + sid
         and record.get("source_slug") == SOURCE
         and record.get("language_tag") == "ko"
         and m.get("issuer") == "국방부"
         and m.get("publisher") == "대한민국 정책브리핑"
         and m.get("publication_kind") == "syndicated_press_release"
         and m.get("body_scope") == "published_hwpx_text"
         and m.get("attachments_collected") is True,
         "wrong_korea_publisher_or_content_scope")
    first_seen = record.get("first_seen_run")
    need(type(first_seen) is str and RUN.fullmatch(first_seen),
         "invalid_first_seen_run")
    day = _date(record.get("published_date"))
    version = digest(canonical({
        "source_identity": ident, "source_url": URL + sid,
        "published_date": day, "original_text_sha256": text_hash,
        "publisher_html_sha256": page, "original_hwpx_sha256": hwpx,
    }))
    return {
        "candidate_version_sha256": version,
        "desk_id": "korea",
        "source_identity": ident,
        "source_slug": SOURCE,
        "institution_id": "kr_mnd",
        "publisher_institution_id": "kr_policy_briefing",
        "authority_tier": "B",
        "originality": "syndicated",
        "language_tag": "ko",
        "canonical_source_url": URL + sid,
        "publisher_posted_date": day,
        "original_title_sha256": digest(title.encode("utf-8")),
        "original_text_sha256": text_hash,
        "publisher_html_sha256": page,
        "original_hwpx_sha256": hwpx,
        "first_seen_run": first_seen,
        "editorial_exception": ("unresolved_2025_2026_excavation_year_issue_601"
                                if sid == "156785161" else None),
        "disposition": "held_pending_exact_version_human_and_rights_review",
        "original_text_included": False,
        "original_title_included": False,
        "original_media_included": False,
        "approved_for_production": False,
        "approved_for_publication": False,
        "approved_for_model_or_email": False,
    }


def _rows(state):
    path = state / "state" / "shadow.db"
    need(path.is_file() and not path.is_symlink(),
         "korea_shadow_database_missing")
    try:
        conn = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            need(conn.execute("PRAGMA quick_check").fetchone()[0] == "ok",
                 "shadow_database_corrupted")
            rows = conn.execute(
                "SELECT source_identity,url,source_slug,title_original,"
                "text_original,published_date,language_tag,metadata_json,"
                "content_sha256,capture_sha256,first_seen_run "
                "FROM shadow_records ORDER BY source_identity"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        raise IntakeHold("incompatible_korea_shadow_schema") from None
    need(5 <= len(rows) <= ROWS, "korea_original_record_count_out_of_bounds")
    return [dict(row) for row in rows]


def build(source_checkout, *, frozen=FROZEN_14):
    source_contract()
    path = Path(source_checkout).expanduser()
    need(path.is_absolute() and path.is_dir() and not path.is_symlink(),
         "invalid_source_checkout")
    try:
        before = inventory(path, frozen_commit=frozen)
    except (CustodyHold, OSError, ValueError):
        raise IntakeHold("korea_source_archive_not_verified") from None
    source_rows = _rows(path)
    normalized = []
    for row in source_rows:
        # An SHA-named document is insufficient on its own: reparse the
        # preserved original HWPX and compare every Korean text paragraph
        # against the database's full source text before staging a candidate.
        try:
            raw = dict(row, metadata=json.loads(row["metadata_json"]))
            proof = source_compare(raw, path / "state")
        except (ValueError, OSError, UnicodeError):
            raise IntakeHold("korea_original_hwpx_replay_failed") from None
        need(proof["machine_fidelity"] == "PASS",
             "korea_original_hwpx_replay_failed")
        normalized.append(_normalized(row))
    need(len(normalized) == before["original_count"],
         "shadow_inventory_count_mismatch")
    ids = [r["source_identity"] for r in normalized]
    need(len(ids) == len(set(ids)), "duplicate_normalized_source_identity")
    # Rehash all captures and the Git state once more to detect a moving
    # checkout while staging. The output contains identities, not raw evidence.
    try:
        after = inventory(path, frozen_commit=frozen)
    except (CustodyHold, OSError, ValueError):
        raise IntakeHold("korea_source_changed_during_staging") from None
    need(before == after, "korea_source_changed_during_staging")
    packet = {
        "schema": SCHEMA,
        "source_git_commit": before["head"],
        "frozen_fourteen_ancestor": frozen,
        "source_db_sha256": before["files"]["shadow.db"],
        "source_original_count": len(normalized),
        "records": normalized,
        "candidate_count": len(normalized),
        "approved_count": 0,
        "public_body_count": 0,
        "production_import_enabled": False,
        "reviewer_identity_authenticated": False,
        "per_source_rights_granted": False,
        "private_custody_and_independent_restore_verified": False,
        "collection_window_qualified": False,
        "model_email_or_publication_authorized": False,
    }
    need(len(canonical(packet)) <= MAX_OUTPUT, "candidate_packet_too_large")
    return packet


def _path(dest):
    path = Path(dest).expanduser()
    root = ROOT.resolve()
    need(path.is_absolute() and not path.exists()
         and not path.is_symlink() and path.parent.is_dir()
         and not path.parent.is_symlink()
         and root != path.resolve(strict=False)
         and root not in path.resolve(strict=False).parents,
         "candidate_output_must_be_new_outside_repository")
    need(stat.S_IMODE(path.parent.stat().st_mode) & 0o077 == 0,
         "candidate_parent_must_be_owner_only")
    return path


def create(source, output, *, frozen=FROZEN_14):
    path = _path(output)
    data = build(source, frozen=frozen)
    result = canonical(data) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
        stream.write(result)
    return {
        "schema": RECEIPT,
        "source_git_commit": data["source_git_commit"],
        "source_original_count": data["source_original_count"],
        "held_production_candidate_count": data["candidate_count"],
        "packet_sha256": digest(result),
        "source_bodies_exported": False,
        "source_titles_exported": False,
        "production_rows_written": 0,
        "publication_or_model_use_authorized": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-checkout", required=True)
    p.add_argument("--private-output", required=True)
    p.add_argument("--explicit-no-send-or-promotion", action="store_true")
    args = p.parse_args(argv)
    try:
        need(args.explicit_no_send_or_promotion, "explicit_local_hold_required")
        print(json.dumps(create(args.source_checkout, args.private_output),
                         sort_keys=True))
        return 0
    except (IntakeHold, OSError, ValueError) as exc:
        print(json.dumps({"schema": RECEIPT, "status": "HOLD",
                          "reason": (str(exc) if isinstance(exc, IntakeHold)
                                     else "source_unavailable"),
                          "production_rows_written": 0,
                          "publication_or_model_use_authorized": False},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
