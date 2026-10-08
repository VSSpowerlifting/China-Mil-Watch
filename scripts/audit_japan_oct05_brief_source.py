"""Read-only, exact-object audit of Oct 5 Japan shadow full-text PDF extraction.

The original PDF bytes are not stored in shadow_records. A stored capture
digest is NOT proof of retained original bytes or full-PDF fidelity.
No network requests, shadow writes, production DB access, approval, or email.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_COMMIT = "d57f0a94b2134a68b9f13fb35a0a0b8c8a4ffe13"
STATE_PATH = "state/shadow.db"
DB_BLOB_SHA1 = "60f126db5a36369ade81f44f12c3a838cddbfb59"
PDF_URL = "https://www.mod.go.jp/j/press/news/2026/10/05b.pdf"
SOURCE = "jp_mod_news_ja"
TITLE = "日米合同委員会合意について"
TEXT_SHA256 = "d8ec17263a4465f75f79e03d2096ce82b9094da649d2ee0d7f198778d0cd0eb8"
CAPTURE_SHA256 = "4788557ba554cd8af8211906174f44fc60eecaa53f46e2c1818b418c2d0d57bf"
EXPECTED_RUN = "37404326269-1"
EXPECTED_PHRASES = (
    "ＦＡＣ５１２１築城飛行場",
    "キーン・ソード２７",
    "令和８年９月１７日",
    "約２９，０００㎡",
    "約１１，０００㎡",
)
WINDOW_START = "2026-10-04"
CUTOFF = "2026-10-08"


class JapanShadowAuditError(ValueError):
    """A required immutable October 5 historical source proof failed."""


def require(ok, reason):
    if not ok:
        raise JapanShadowAuditError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_git_blob(repo, commit=STATE_COMMIT, expected_blob=DB_BLOB_SHA1):
    require(type(commit) is str and re.fullmatch(r"[0-9a-f]{40}", commit),
            "only exact historical commit SHA allowed")
    require(type(expected_blob) is str and
            re.fullmatch(r"[0-9a-f]{40}", expected_blob),
            "only exact expected Git blob SHA allowed")
    repo = Path(repo)
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--verify", commit + ":" + STATE_PATH],
            cwd=repo, check=True, capture_output=True, timeout=30,
        ).stdout.decode("ascii").strip()
        require(sha == expected_blob, "historical Git blob differs from fixed pin")
        byte_count = subprocess.run(
            ["git", "cat-file", "-s", sha], cwd=repo,
            check=True, capture_output=True, timeout=30
        ).stdout.decode("ascii").strip()
        require(byte_count.isdecimal() and int(byte_count) <= 5_000_000,
                "pinned shadow database unexpectedly large")
        raw = subprocess.run(
            ["git", "cat-file", "blob", sha], cwd=repo,
            check=True, capture_output=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise JapanShadowAuditError(
            "exact historical Git object unavailable; no branch or HTTP fallback"
        ) from exc
    content_sha1 = hashlib.sha1(
        ("blob %d\0" % len(raw)).encode("ascii") + raw
    ).hexdigest()
    require(content_sha1 == expected_blob,
            "source data did not match original Git blob")
    return raw


def validate_row(row):
    require(type(row) is dict and
            row.get("url") == PDF_URL and
            row.get("source_slug") == SOURCE and
            row.get("title_original") == TITLE and
            row.get("published_date") == "2026-10-05" and
            row.get("first_seen_run") == EXPECTED_RUN and
            row.get("publication_kind") == "press release" and
            row.get("language_tag") == "ja",
            "Japan Oct 5 original identity, language or publication date drifted")
    body = row.get("text_original")
    require(type(body) is str and len(body) == 580 and
            digest(body.encode("utf-8")) == TEXT_SHA256 and
            row.get("content_sha256") == TEXT_SHA256,
            "Japan extracted Japanese text or integrity hash differs")
    require(row.get("capture_sha256") == CAPTURE_SHA256,
            "historical PDF capture digest changed in archive")
    for phrase in EXPECTED_PHRASES:
        require(phrase in body, "Japan source text missing exact evidence: " + phrase)
    return {
        "state_commit": STATE_COMMIT,
        "state_db_blob_sha1": DB_BLOB_SHA1,
        "source_url": PDF_URL,
        "source_title_original": TITLE,
        "source_published_date": "2026-10-05",
        "source_language": "ja",
        "first_seen_run": EXPECTED_RUN,
        "archived_text_sha256_verified": True,
        "archived_original_pdf_bytes_verified": False,
        "full_pdf_human_fidelity_review_complete": False,
        "production_backed_citation_id": None,
        "eligible_for_automatic_friday_writer": False,
        "exercise_performed_verified": False,
        "editorial_inclusion_approved": False,
        "production_writes": 0,
    }


def inspect_snapshot(db_bytes):
    require(type(db_bytes) is bytes and
            db_bytes.startswith(b"SQLite format 3\x00"),
            "historical bytes are not valid SQLite header")
    with tempfile.TemporaryDirectory(prefix="ipr-japan-oct05-") as tmp:
        path = Path(tmp) / "shadow.db"
        path.write_bytes(db_bytes)
        cx = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        cx.row_factory = sqlite3.Row
        try:
            cx.execute("PRAGMA query_only=ON")
            require(cx.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                    "Japan shadow SQLite integrity check failed")
            items = cx.execute(
                "SELECT url,source_slug,title_original,text_original,"
                "published_date,language_tag,publication_kind,"
                "content_sha256,capture_sha256,first_seen_run "
                "FROM shadow_records WHERE published_date BETWEEN ? AND ?",
                (WINDOW_START, CUTOFF)
            ).fetchall()
            require(len(items) == 1,
                    "exactly one full-text Japan shadow record in this week through Oct 8")
            total = cx.execute(
                "SELECT COUNT(*) FROM shadow_records"
            ).fetchone()[0]
            require(total == 5,
                    "snapshot body-bearing records drifted from verified five")
            result = validate_row(dict(items[0]))
            result["archive_total_full_text_records"] = total
            result["archive_current_week_records_through_oct08"] = len(items)
            return result
        finally:
            cx.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-repo", required=True, type=Path,
                   help="local Git repository already containing exact orphan state commit")
    args = p.parse_args(argv)
    try:
        print(json.dumps(inspect_snapshot(read_git_blob(args.state_repo)),
                         ensure_ascii=False, indent=2))
    except (JapanShadowAuditError, sqlite3.DatabaseError, OSError, TypeError) as exc:
        p.exit(1, "Japan October 5 shadow source integrity: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
