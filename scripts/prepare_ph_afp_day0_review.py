"""Unsigned, immutable AFP Day-0 original-source review queue (read-only).

No network, collector execution, database modification, reviewer impersonation,
classification, human approval or production admission. Requires exact locally
available Git objects from the successful October 7 shadow state snapshot.
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

ROOT = Path(__file__).resolve().parent.parent
STATE_COMMIT = "492001f34ba6176169b6acc96a237f05592a3395"
RUN_ID = "37631681338-1"
LEDGER_PATH = "state/ledger/20261007T135144+0000-37631681338-1.json"
SNAPSHOT_BLOBS = {
    "state/shadow.db": "e42f8f0dde480a99452d89bcfc7ee84b5aa55f13",
    LEDGER_PATH: "ee84c63ac69009fc8c59f787772e40045367f30e",
    "state/clock.json": "28ebaf7d201a6ad7d863dd8f85d65f602372b624",
}
SOURCE = "ph_afp_articles"
CHECKS = (
    "issuer_and_source_identity",
    "title_matches_original_capture",
    "publisher_date_and_timezone",
    "full_body_and_no_site_furniture",
    "canonical_and_requested_urls",
    "capture_bytes_and_provenance",
)
IDENTITY_FIELDS = (
    "source_identity", "source_url", "title_original", "published_date",
    "published_at_original", "published_at_utc", "source_slug",
    "text_sha256", "text_original", "text_status", "source_fingerprint",
    "capture_sha256", "capture_request_url", "capture_final_url",
    "capture_retrieved_at", "capture_http_status", "body_chars",
)


class AFPReviewError(ValueError):
    """An immutable source identity or human review contract failed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AFPReviewError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_objects(repo: Path, commit: str, blobs: dict[str, str]) -> dict[str, bytes]:
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "commit must be a full Git SHA")
    result = {}
    for path, expected_sha in blobs.items():
        require(bool(re.fullmatch(r"[0-9a-f]{40}", expected_sha)), "invalid pinned blob SHA")
        require(path in SNAPSHOT_BLOBS, "unexpected historical state file")
        try:
            actual = subprocess.run(
                ["git", "rev-parse", "--verify", commit + ":" + path],
                cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30, check=True,
            ).stdout.decode("ascii").strip()
            require(actual == expected_sha, "pinned state blob mismatch for " + path)
            raw = subprocess.run(
                ["git", "cat-file", "blob", expected_sha],
                cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30, check=True,
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            raise AFPReviewError(
                "historical Git object unavailable; no current-state or network fallback"
            ) from exc
        git_hash = hashlib.sha1(
            ("blob %d\0" % len(raw)).encode("ascii") + raw
        ).hexdigest()
        require(git_hash == expected_sha, "historical object payload failed SHA")
        result[path] = raw
    require(set(result) == set(SNAPSHOT_BLOBS), "must include all three pinned files")
    return result


def make_queue_from_objects(objects: dict[str, bytes], *,
                            commit: str = STATE_COMMIT, run: str = RUN_ID) -> dict:
    require(set(objects) == set(SNAPSHOT_BLOBS), "incomplete historical files")
    ledger = json.loads(objects[LEDGER_PATH])
    clock = json.loads(objects["state/clock.json"])
    db_bytes = objects["state/shadow.db"]
    require(
        ledger.get("run_id") == run and
        ledger.get("rehearsal") is False and
        ledger.get("target_date") == "2026-10-07" and
        ledger.get("target_date_source") == "schedule-slot" and
        ledger.get("result") == "ok" and ledger.get("health") == "ok" and
        ledger.get("shadow_day") == 0 and
        ledger.get("selected") == ledger.get("retrieved") ==
        ledger.get("inserted") == ledger.get("stored_with_text") == 13 and
        ledger.get("stored_total") == 13 and
        ledger.get("fetch_failures") == ledger.get("extraction_failures") == 0 and
        ledger.get("state_sha256_after") == sha256(db_bytes),
        "Day-0 run ledger, complete capture count or database digest mismatch"
    )
    require(clock.get("day_zero_run_id") == run and
            clock.get("day_zero_utc") == ledger.get("finished_utc"),
            "Day-0 clock does not match immutable ledger")
    require(db_bytes.startswith(b"SQLite format 3\x00"), "historical DB is not SQLite")

    with tempfile.TemporaryDirectory(prefix="ipr-ph-afp-review-") as tmp:
        dbfile = Path(tmp) / "shadow.db"
        dbfile.write_bytes(db_bytes)
        conn = sqlite3.connect(dbfile.as_uri() + "?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only=ON")
            require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                    "historical database failed integrity check")
            names = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )}
            require(names == {"shadow_records", "captures", "revisions"},
                    "unexpected AFP shadow database schema")
            rows = conn.execute(
                "SELECT * FROM shadow_records ORDER BY published_at_utc, url"
            ).fetchall()
            require(len(rows) == 13, "the frozen Day-0 body set is not thirteen")
            require(conn.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 13,
                    "Day-0 capture count differs")
            require(conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 0,
                    "unexpected Day-0 historical revisions")
            output_rows = []
            seen = set()
            for record in rows:
                rec = dict(record)
                source_id = rec["source_identity"]
                require(
                    source_id not in seen and
                    bool(re.fullmatch(r"afp:[0-9]+", source_id)) and
                    rec["source_slug"] == SOURCE and
                    rec["language_tag"] == "en" and
                    rec["text_status"] == "text" and
                    isinstance(rec["text_original"], str) and
                    bool(rec["text_original"].strip()) and
                    rec["first_seen_run"] == run and
                    str(rec["url"]).startswith("https://www.afp.mil.ph/news/"),
                    "unexpected source identity, missing body or changed collection run"
                )
                require(rec["content_sha256"] == sha256(rec["text_original"].encode("utf-8")),
                        source_id + ": stored source text digest mismatch")
                seen.add(source_id)
                captures = conn.execute(
                    "SELECT * FROM captures WHERE source_identity = ? AND run_id = ?",
                    (source_id, run),
                ).fetchall()
                require(len(captures) == 1,
                        source_id + ": one original request capture required")
                cap = dict(captures[0])
                require(
                    sha256(cap["payload"]) == cap["payload_sha256"] ==
                    rec["capture_sha256"] and
                    cap["source_fingerprint"] == rec["source_fingerprint"] and
                    cap["http_status"] == 200 and
                    str(cap["requested_url"]).startswith("https://api.afp.mil.ph/articles/") and
                    cap["final_url"] == cap["requested_url"],
                    source_id + ": original capture integrity or URL mismatch"
                )
                identity = {
                    "source_identity": source_id,
                    "source_url": rec["url"],
                    "title_original": rec["title_original"],
                    "published_date": rec["published_date"],
                    "published_at_original": rec["published_at_original"],
                    "published_at_utc": rec["published_at_utc"],
                    "source_slug": rec["source_slug"],
                    "text_sha256": sha256(rec["text_original"].encode("utf-8")),
                    "text_original": rec["text_original"],
                    "text_status": rec["text_status"],
                    "source_fingerprint": rec["source_fingerprint"],
                    "capture_sha256": rec["capture_sha256"],
                    "capture_request_url": cap["requested_url"],
                    "capture_final_url": cap["final_url"],
                    "capture_retrieved_at": cap["retrieved_at"],
                    "capture_http_status": cap["http_status"],
                    "body_chars": len(rec["text_original"]),
                }
                output_rows.append({
                    **identity,
                    "decision": "pending",
                    "checks": {check: None for check in CHECKS},
                    "reviewer_name": "",
                    "read_original_capture": False,
                    "reviewed_at_utc": None,
                    "rationale": "",
                })
        finally:
            conn.close()
    return {
        "protocol": "ipr_ph_afp_day0_unsigned_human_review_v1",
        "review_scope": "all_13_preserved_first_scheduled_run_bodies",
        "historical_state_commit": commit,
        "historical_git_blobs": dict(SNAPSHOT_BLOBS),
        "original_run_id": run,
        "source_kind": "AFP_first_party_shadow_not_production",
        "human_review_complete": False,
        "human_approval": False,
        "desk_qualified": False,
        "production_assignments": 0,
        "machine_verified_capture_count": 13,
        "records": output_rows,
    }


def validate_reviews(candidate: dict, exact: dict, *,
                     require_complete: bool = False) -> dict:
    require(isinstance(candidate, dict) and set(candidate) == set(exact),
            "changed review packet top-level fields")
    for key in exact:
        if key != "records":
            require(candidate[key] == exact[key], "changed review provenance: " + key)
    supplied, canonical = candidate["records"], exact["records"]
    require(isinstance(supplied, list) and len(supplied) == len(canonical),
            "changed record count")
    count = {"pending": 0, "verified": 0, "hold": 0}
    for row, expected in zip(supplied, canonical):
        require(isinstance(row, dict) and set(row) == set(expected),
                "review row schema altered")
        for field in IDENTITY_FIELDS:
            require(row[field] == expected[field],
                    str(expected["source_identity"]) + ": archived identity altered")
        require(row["decision"] in count, "unsupported reviewer decision")
        count[row["decision"]] += 1
        require(isinstance(row["checks"], dict) and
                set(row["checks"]) == set(CHECKS) and
                all(x is None or type(x) is bool for x in row["checks"].values()),
                "review checks missing or changed")
        require(type(row["reviewer_name"]) is str and
                type(row["read_original_capture"]) is bool and
                type(row["rationale"]) is str,
                "reviewer metadata invalid")
        if row["decision"] == "pending":
            require(row["checks"] == expected["checks"] and
                    row["reviewer_name"] == "" and
                    row["read_original_capture"] is False and
                    row["reviewed_at_utc"] is None and row["rationale"] == "",
                    "pending record falsely claims a human judgment")
            continue
        require(row["reviewer_name"].strip() and row["rationale"].strip() and
                row["read_original_capture"] is True and
                isinstance(row["reviewed_at_utc"], str) and
                bool(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",
                                  row["reviewed_at_utc"])),
                "named human original-capture review and UTC time required")
        require(all(v is not None for v in row["checks"].values()),
                "completed review must address all fidelity/provenance checks")
        if row["decision"] == "verified":
            require(all(row["checks"].values()),
                    "verified review cannot contain a failed source check")
        else:
            require(not all(row["checks"].values()),
                    "hold requires a documented failed source check")
    if require_complete:
        require(count["pending"] == 0, "incomplete independent human reviews")
    return {
        "source": SOURCE, "total": len(canonical), "decisions": count,
        "human_identity_authenticated": False,
        "editorial_approval": False,
        "production_writes": 0, "qualification": False,
    }


def generate(repo: Path = ROOT) -> dict:
    objects = git_objects(repo, STATE_COMMIT, SNAPSHOT_BLOBS)
    return make_queue_from_objects(objects)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("packet", "validate"))
    parser.add_argument("--state-repo", type=Path, default=ROOT,
                        help="local Git checkout containing exact Day-0 state objects")
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        original = generate(args.state_repo)
        if args.action == "packet":
            require(args.decisions is None and not args.require_complete,
                    "packet export accepts no review claims")
            print(json.dumps(original, ensure_ascii=False, indent=2))
        else:
            require(args.decisions is not None, "validate requires a decisions file")
            result = validate_reviews(
                json.loads(args.decisions.read_text(encoding="utf-8")),
                original, require_complete=args.require_complete
            )
            print(json.dumps(result, indent=2))
    except (ValueError, TypeError, OSError, KeyError, sqlite3.DatabaseError) as exc:
        parser.exit(1, "AFP source review queue: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
