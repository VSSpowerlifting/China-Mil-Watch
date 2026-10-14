"""Immutable Japan MOD weekly source-candidate intake, metadata only.

This does NOT summarize full original text into an AI prompt or authorize
publication. The official collector's Japanese feed is incomplete: HTML is
challenged, PDF original bytes are not archived, Joint Staff/English are not
collected. Every report must expose those gaps, not hide them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "japan-mod-weekly-shadow-intake/1"
SOURCES = {"jp_mod_news_ja", "jp_mod_siteupdate_ja"}
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
DB_PATH = "state/shadow.db"
MAX_DB_BYTES = 5_000_000
MAX_INTAKE = 40


class IntakeError(ValueError):
    pass


def _day(value):
    if not isinstance(value, str):
        raise IntakeError("YYYY-MM-DD required")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise IntakeError("invalid reporting date") from exc
    if parsed.isoformat() != value:
        raise IntakeError("noncanonical reporting date")
    return parsed


def _git(repo, *args):
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args],
                                       stderr=subprocess.PIPE, timeout=25)
    except (OSError, subprocess.SubprocessError) as exc:
        raise IntakeError("immutable state Git object unavailable") from exc


def snapshot_bytes(repo, commit):
    """Access the precise state DB blob, not branch HEAD or mutable worktree."""
    if not isinstance(commit, str) or not SHA40.fullmatch(commit):
        raise IntakeError("exact lowercase 40-character commit required")
    repo = Path(repo)
    tree = _git(repo, "ls-tree", "--name-only", commit).decode("utf-8").strip()
    if tree != "state":
        raise IntakeError("Japan shadow root tree has unexpected files")
    sha = _git(repo, "rev-parse", "--verify", commit + ":" + DB_PATH).decode().strip()
    if not SHA40.fullmatch(sha):
        raise IntakeError("invalid pinned database object")
    length = _git(repo, "cat-file", "-s", sha).decode().strip()
    if not length.isdecimal() or not 0 < int(length) <= MAX_DB_BYTES:
        raise IntakeError("Japan state database exceeds bounded size")
    data = _git(repo, "cat-file", "blob", sha)
    calculated = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") +
                              b"\0" + data).hexdigest()
    if len(data) != int(length) or calculated != sha or not data.startswith(
            b"SQLite format 3\0"):
        raise IntakeError("pinned state SQLite Git object integrity failure")
    return data, sha


def summarize(db_bytes, *, state_commit, week_ending, as_of):
    if not isinstance(state_commit, str) or not SHA40.fullmatch(state_commit):
        raise IntakeError("immutable exact state commit required")
    saturday, cutoff = _day(week_ending), _day(as_of)
    start = saturday - timedelta(days=6)
    if saturday.weekday() != 5 or not start <= cutoff <= saturday:
        raise IntakeError("source cutoff must be inside the Saturday-ending reporting week")
    if not isinstance(db_bytes, bytes) or not db_bytes.startswith(b"SQLite format 3\0"):
        raise IntakeError("expected a real SQLite source snapshot")
    with tempfile.TemporaryDirectory(prefix="japan-shadow-weekly-") as tmp:
        path = Path(tmp) / "shadow.db"
        path.write_bytes(db_bytes)
        conn = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only=ON")
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise IntakeError("SQLite integrity check failed")
            total = conn.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0]
            selected = conn.execute(
                "SELECT url,source_slug,title_original,text_original,"
                " published_date,language_tag,publication_kind,"
                " content_sha256,capture_sha256,first_seen_run "
                " FROM shadow_records WHERE published_date BETWEEN ? AND ?"
                " ORDER BY published_date DESC,url ASC",
                (start.isoformat(), cutoff.isoformat())
            ).fetchall()
            unretrieved = conn.execute(
                "SELECT reason,COUNT(*) FROM shadow_unretrieved "
                "WHERE published_date BETWEEN ? AND ? GROUP BY reason",
                (start.isoformat(), cutoff.isoformat())).fetchall()
            missing_dates = conn.execute(
                "SELECT COUNT(*) FROM shadow_unretrieved WHERE published_date IS NULL"
            ).fetchone()[0]
        finally:
            conn.close()

    if len(selected) > MAX_INTAKE:
        raise IntakeError("weekly original records exceed fixed reporting cap; no silent truncation")
    candidates = []
    for row in selected:
        u = urlsplit(row["url"])
        if (u.scheme != "https" or u.hostname != "www.mod.go.jp" or
                u.port is not None or u.username or u.password or
                u.query or u.fragment or not u.path.startswith("/j/")):
            raise IntakeError("non-first-party Japan MOD source URL")
        if row["source_slug"] not in SOURCES or row["language_tag"] != "ja":
            raise IntakeError("unrecognized ministry feed or source language")
        original = row["text_original"]
        digest = row["content_sha256"]
        if (not isinstance(original, str) or not original.strip() or
                not isinstance(digest, str) or not SHA64.fullmatch(digest) or
                hashlib.sha256(original.encode("utf-8")).hexdigest() != digest):
            raise IntakeError("original Japanese text digest invalid")
        if (not row["first_seen_run"] or not isinstance(row["first_seen_run"], str) or
                not row["publication_kind"]):
            raise IntakeError("missing first-seen run or publication class")
        if row["capture_sha256"] and not SHA64.fullmatch(row["capture_sha256"]):
            raise IntakeError("malformed publisher capture digest")
        candidates.append({
            "source_url": row["url"],
            "source_slug": row["source_slug"],
            "title_original": row["title_original"],
            "published_date": row["published_date"],
            "publication_kind": row["publication_kind"],
            "language_tag": "ja",
            "text_sha256": digest,
            "text_chars": len(original),
            "capture_sha256_observed": row["capture_sha256"],
            "first_seen_run": row["first_seen_run"],
            "verification": "text_digest_verified_from_immutable_shadow_sqlite",
            "original_pdf_bytes_retained": False,
            "human_language_and_rights_review_complete": False,
            "eligible_for_automatic_model_drafting": False,
        })
    gaps = {row[0]: row[1] for row in unretrieved}
    return {
        "schema": SCHEMA, "desk": "japan",
        "issuer": "Japan Ministry of Defense",
        "state_branch": "shadow/jp-mod", "state_commit": state_commit,
        "reporting_week_start": start.isoformat(),
        "reporting_saturday": saturday.isoformat(),
        "source_cutoff": cutoff.isoformat(),
        "full_reporting_week_elapsed_at_cutoff": cutoff == saturday,
        "source_snapshot_completeness_attested": False,
        "archive_total_original_text_records": total,
        "current_week_text_records": len(candidates),
        "source_candidates": candidates,
        "unretrieved_counts_by_reason": gaps,
        "undated_unretrieved_count": missing_dates,
        "known_publication_coverage_incomplete": True,
        "english_press_collected": False,
        "joint_staff_collected": False,
        "original_pdf_bytes_retained": False,
        "candidate_human_review_completed": False,
        "source_rights_approved": False,
        "eligible_for_automatic_model_drafting": False,
        "production_eligible": False,
        "weekly_edition_approved": False,
        "state_or_production_writes": 0,
    }


def build(*, state_repo, state_commit, week_ending, as_of):
    data, db_sha = snapshot_bytes(state_repo, state_commit)
    result = summarize(data, state_commit=state_commit,
                       week_ending=week_ending, as_of=as_of)
    result["shadow_db_git_blob_sha1"] = db_sha
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-repo", required=True, type=Path)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--week-ending", required=True)
    p.add_argument("--as-of", required=True,
                   help="ISO date within reporting week; pre-Saturday is partial evidence")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    if args.output.exists():
        p.error("refusing to overwrite weekly source intake")
    try:
        report = build(state_repo=args.state_repo,
                       state_commit=args.state_commit,
                       week_ending=args.week_ending, as_of=args.as_of)
    except (IntakeError, OSError, sqlite3.Error, UnicodeError) as exc:
        p.error(str(exc))
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                      indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_week": report["reporting_saturday"],
        "shadow_records": report["current_week_text_records"],
        "unretrieved": report["unretrieved_counts_by_reason"],
        "automatic_model_drafting_allowed": False,
        "production_eligible": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
