"""Read-only exact-URL admission audit of an immutable Japan shadow snapshot.

This is a discovery audit, NOT a source retrieval, ingestion, human review,
classification, rights determination, or proof of exhaustive historical absence.
Requires the exact Git object locally; never fetches or substitutes state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CANDIDATES = ROOT / "research/topic_v2_japan_space/source_candidates.json"
PINNED_COMMIT = "d57f0a94b2134a68b9f13fb35a0a0b8c8a4ffe13"
PINNED_BLOB = "60f126db5a36369ade81f44f12c3a838cddbfb59"
STATE_PATH = "state/shadow.db"
PACKET_ID = "ipr_japan_space_v2_source_admission_20261008"
TABLES = (
    "shadow_records",
    "shadow_unretrieved",
    "shadow_pre_bootstrap",
    "shadow_validators",
)
EXPECTED_SOURCES = {
    "JSP01": "https://www.mod.go.jp/j/press/wp/wp2026/html/n310204000.html",
    "JSP02": "https://www.mod.go.jp/j/press/kisha/2026/0306a.html",
    "JSP03": "https://www.mod.go.jp/asdf/ssa/activities/report01/",
    "JSP04": "https://www.mofa.go.jp/mofaj/gaiko/bluebook/2026/html/chapter3_01_02.html",
    "JSP05": "https://www.jaxa.jp/press/2026/06/20260612-1_j.html",
    "JSP06": "https://www.jaxa.jp/press/2026/08/20260820-1_j.html"
}
EXPECTED_IDS = frozenset(EXPECTED_SOURCES)


class SnapshotAuditError(ValueError):
    """Refuse an unverifiable archive snapshot or admission input."""


def load_candidates(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("packet_id") != PACKET_ID:
        raise SnapshotAuditError("unexpected source-admission packet identity")
    if data.get("archive_status") != "not_pinned_not_verified_against_full_japan_shadow":
        raise SnapshotAuditError("candidate archive status was changed")
    if (data.get("collection_authorized") is not False or
            data.get("topic_assignments_authorized") is not False or
            data.get("human_review_complete") is not False):
        raise SnapshotAuditError("source admission or approvals cannot be asserted")
    rows = data.get("candidates")
    if not isinstance(rows, list) or len(rows) != 6:
        raise SnapshotAuditError("expected exactly six source candidates")
    ids, urls = set(), set()
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise SnapshotAuditError("invalid candidate entry")
        ident = candidate.get("id")
        url = candidate.get("url")
        if (not isinstance(ident, str) or ident not in EXPECTED_IDS or
                ident in ids or not isinstance(url, str) or
                not url.startswith("https://") or url in urls):
            raise SnapshotAuditError("duplicate, malformed or unexpected candidate identity")
        if url != EXPECTED_SOURCES[ident]:
            raise SnapshotAuditError("candidate URL changed from frozen source packet")
        if (candidate.get("archive_identity") is not None or
                candidate.get("body_sha256") is not None or
                candidate.get("owner_approval") is not None or
                candidate.get("review_state") != "awaiting_source_admission"):
            raise SnapshotAuditError("source falsely appears archived or approved")
        ids.add(ident)
        urls.add(url)
    if ids != EXPECTED_IDS:
        raise SnapshotAuditError("missing admission candidate")
    return rows


def read_pinned_git_blob(repo: Path, commit: str, expected_blob: str) -> bytes:
    """Only a locally present, exact SHA/commit:path blob is eligible."""
    if (not re.fullmatch(r"[0-9a-f]{40}", commit) or
            not re.fullmatch(r"[0-9a-f]{40}", expected_blob)):
        raise SnapshotAuditError("commit and blob must be full literal Git SHA-1 IDs")

    def git(*args: str) -> bytes:
        try:
            result = subprocess.run(
                ["git", *args], cwd=repo, capture_output=True, check=True,
                timeout=30,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise SnapshotAuditError(
                "pinned Git object is unavailable; no fallback to current or remote state"
            ) from exc
        return result.stdout

    # Resolve only the named commit's state/shadow.db, not a ref that can advance.
    actual_blob = git("rev-parse", "--verify", "%s:%s" % (commit, STATE_PATH)).decode(
        "ascii"
    ).strip()
    if actual_blob != expected_blob:
        raise SnapshotAuditError("historical state/shadow.db blob identity changed")
    body = git("cat-file", "blob", expected_blob)
    git_sha = hashlib.sha1(
        ("blob %d\0" % len(body)).encode("ascii") + body
    ).hexdigest()
    if git_sha != expected_blob:
        raise SnapshotAuditError("pinned Git blob payload failed checksum")
    if not body.startswith(b"SQLite format 3\x00"):
        raise SnapshotAuditError("pinned object is not a SQLite database")
    return body


def _frequency(db: sqlite3.Connection, table: str, column: str) -> dict[str, int]:
    rows = db.execute(
        "SELECT %s, COUNT(*) FROM %s GROUP BY %s" % (column, table, column)
    )
    return dict(sorted(((str(value) if value is not None else "unassigned", count)
                        for value, count in rows), key=lambda x: x[0]))


def audit_database(path: Path, candidates: list[dict]) -> dict:
    """SQL-row-level, exact-canonical-URL audit; opens SQLite immutable/read-only."""
    try:
        db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            db.execute("PRAGMA query_only=ON")
            result = db.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise SnapshotAuditError("snapshot failed SQLite integrity check")
            user_tables = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
            if user_tables != set(TABLES):
                raise SnapshotAuditError("unknown or missing shadow tables: %r" %
                                         sorted(user_tables))
            summary = {}
            for table in TABLES:
                cols = {row[1] for row in db.execute("PRAGMA table_info(%s)" % table)}
                if "url" not in cols:
                    raise SnapshotAuditError(table + " is missing URL identity")
                count = db.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
                entry = {"rows": count}
                if "source_slug" in cols:
                    entry["by_source"] = _frequency(db, table, "source_slug")
                if "reason" in cols:
                    entry["by_reason"] = _frequency(db, table, "reason")
                if "published_date" in cols:
                    dates = db.execute(
                        "SELECT MIN(published_date), MAX(published_date) "
                        "FROM %s" % table
                    ).fetchone()
                    entry["stored_date_range"] = list(dates)
                summary[table] = entry
            cases = []
            for candidate in candidates:
                matches = {}
                for table in TABLES:
                    # Strict URL equality; no network requests or guessing aliases.
                    n = db.execute(
                        "SELECT COUNT(*) FROM %s WHERE url=?" % table,
                        (candidate["url"],),
                    ).fetchone()[0]
                    if n:
                        matches[table] = n
                cases.append({
                    "id": candidate["id"],
                    "source_url": candidate["url"],
                    "exact_url_present": bool(matches),
                    "matched_tables": matches,
                })
        finally:
            db.close()
    except sqlite3.DatabaseError as exc:
        raise SnapshotAuditError("snapshot could not be read as SQLite") from exc
    return {
        "audit_kind": "historical_sqlite_exact_url_inventory",
        "archive_snapshot_is_complete_history": False,
        "source_issuer_webpage_fetched": False,
        "original_body_read_or_admitted": False,
        "human_classification_approved": False,
        "production_writes": 0,
        "tables": summary,
        "candidates": cases,
        "exact_url_matches": sum(case["exact_url_present"] for case in cases),
        "candidate_count": len(cases),
        "interpretation": (
            "Zero exact URL hits does NOT prove absence under alternate "
            "canonical URLs, in other snapshots or outside this shadow state."
        ),
    }


def audit_git_snapshot(
    repo: Path, commit: str, blob_sha: str, candidate_path: Path
) -> dict:
    candidates = load_candidates(candidate_path)
    body = read_pinned_git_blob(repo, commit, blob_sha)
    # SQLite's read-only URI requires a path; use a temporary snapshot outside
    # the checkout, never modify or checkpoint the tracked shadow database.
    with tempfile.TemporaryDirectory(prefix="ipr-japan-sqlite-audit-") as tmp:
        path = Path(tmp) / "shadow.db"
        path.write_bytes(body)
        result = audit_database(path, candidates)
    result["provenance"] = {
        "git_commit": commit,
        "git_path": STATE_PATH,
        "git_blob_sha1": blob_sha,
        "file_sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "candidate_packet": PACKET_ID,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES,
                        help="separately governed editor source-admission packet")
    parser.add_argument("--commit", default=PINNED_COMMIT,
                        help="exact Git commit containing the historical state")
    parser.add_argument("--blob", default=PINNED_BLOB,
                        help="expected exact state/shadow.db Git blob SHA-1")
    parser.add_argument("--repo", type=Path, default=ROOT,
                        help="local Git repository containing historical objects")
    args = parser.parse_args()
    try:
        output = audit_git_snapshot(args.repo, args.commit, args.blob, args.candidates)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    except (SnapshotAuditError, OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, "Japan shadow snapshot audit: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
