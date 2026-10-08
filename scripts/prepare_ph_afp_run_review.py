"""Unsigned original-capture review packets for any AFP shadow insertion run.

Read-only Git/SQLite; never executes collection, authenticates human reviewers,
approves content, assigns topics, accesses live URLs, or publishes data.
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
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.prepare_ph_afp_day0_review import (  # noqa: E402
    CHECKS, AFPReviewError, sha256, validate_reviews
)

MAX_BLOB_BYTES = 64_000_000
SUCCESS = frozenset(("ok", "ok_all_duplicates", "ok_all_filtered",
                     "ok_no_publications"))
EXTRA_PINNED_FIELDS = ("original_api_response_utf8", "byline", "first_seen_run")
RUN_ID_RE = re.compile(r"[A-Za-z0-9_.-]{1,128}")
SHA_RE = re.compile(r"[a-f0-9]{40}")


def require(ok: bool, why: str) -> None:
    if not ok:
        raise AFPReviewError(why)


class FrozenState:
    """A fixed commit, never a live branch or remote source."""

    def __init__(self, repo: Path, commit: str):
        require(type(commit) is str and SHA_RE.fullmatch(commit) is not None,
                "historical AFP state must use an exact 40-character commit SHA")
        self.repo = Path(repo)
        self.commit = commit
        self.cache = {}
        try:
            self.files = set(self._git(
                "ls-tree", "-r", "--name-only", commit, "state"
            ).decode("utf-8").splitlines())
        except UnicodeDecodeError as exc:
            raise AFPReviewError("non-UTF-8 Git file paths") from exc
        require("state/shadow.db" in self.files and
                "state/clock.json" in self.files,
                "required historical AFP shadow state is unavailable")

    def _git(self, *args) -> bytes:
        try:
            return subprocess.run(
                ["git", *args], cwd=self.repo, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            raise AFPReviewError(
                "pinned historical Git object unavailable; no network/ref fallback"
            ) from exc

    def read(self, path: str) -> bytes:
        require(path in self.files and path.startswith("state/") and
                ".." not in Path(path).parts, "unavailable state path: " + path)
        if path not in self.cache:
            blob = self._git(
                "rev-parse", "--verify", self.commit + ":" + path
            ).decode("ascii").strip()
            require(SHA_RE.fullmatch(blob) is not None,
                    "historical file lacks full blob SHA")
            size = self._git("cat-file", "-s", blob).decode("ascii").strip()
            require(size.isdecimal() and int(size) <= MAX_BLOB_BYTES,
                    "historical state blob too large")
            content = self._git("cat-file", "blob", blob)
            calculated = hashlib.sha1(
                ("blob %d\0" % len(content)).encode("ascii") + content
            ).hexdigest()
            require(calculated == blob, "pinned Git blob hash mismatch")
            self.cache[path] = (content, blob)
        return self.cache[path][0]

    def blob(self, path: str) -> str:
        self.read(path)
        return self.cache[path][1]

    def load_json(self, path: str) -> dict:
        try:
            result = json.loads(self.read(path))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AFPReviewError("invalid pinned JSON file: " + path) from exc
        require(type(result) is dict, "state JSON must be an object")
        return result


def _date_fields_match(api: dict, rec: dict) -> None:
    source_id = rec["source_identity"]
    require(re.fullmatch(r"afp:[0-9]+", source_id) is not None,
            "unrecognized AFP ID")
    ident = api.get("id")
    require(type(ident) is int and source_id == "afp:%d" % ident,
            "raw API article identity mismatch")
    require(api.get("title") == rec["title_original"],
            source_id + ": title differs from original response")
    require(api.get("published_at") == rec["published_at_original"],
            source_id + ": publisher timestamp differs from original response")
    slug = api.get("slug")
    require(type(slug) is str and
            re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) is not None,
            source_id + ": invalid original article slug")
    require(rec["url"] == "https://www.afp.mil.ph/news/" + slug,
            source_id + ": canonical URL differs from first-party slug")
    require(type(api.get("body_html")) is str and
            type(api.get("intro_html")) is str,
            source_id + ": missing original HTML source fields")


def make_packet(state: FrozenState, run_id: str) -> dict:
    require(type(run_id) is str and RUN_ID_RE.fullmatch(run_id) is not None,
            "invalid collector run ID")
    ledger_paths = [
        p for p in state.files
        if re.fullmatch(r"state/ledger/[^/]+\.json", p)
    ]
    matched = []
    for path in ledger_paths:
        row = state.load_json(path)
        if row.get("run_id") == run_id:
            matched.append((path, row))
    require(len(matched) == 1,
            "expected exactly one immutable ledger with that run ID")
    ledger_path, ledger = matched[0]
    require(
        ledger.get("desk") == "ph-afp" and
        ledger.get("health") == "ok" and
        ledger.get("result") in SUCCESS and
        ledger.get("rehearsal") is False and
        ledger.get("target_date_source") == "schedule-slot" and
        ledger.get("aborted") is None and
        type(ledger.get("inserted")) is int and ledger["inserted"] >= 0 and
        all(ledger.get(k) == 0 for k in (
            "fetch_failures", "extraction_failures", "access_failures",
            "identity_collisions", "redirect_refusals")) and
        ledger.get("failure_log") == [] and
        ledger.get("collector_identity", "").startswith(
            "IndoPacificRecord-ShadowCollector/0.1") and
        ledger.get("listing_status") in SUCCESS,
        "requested AFP run lacks complete successful scheduled provenance"
    )
    db_blob = state.read("state/shadow.db")
    require(ledger.get("state_sha256_after") == sha256(db_blob),
            "requested run is not the final state at this immutable commit")
    require(db_blob.startswith(b"SQLite format 3\x00"), "not a SQLite database")
    clock = state.load_json("state/clock.json")
    require(clock.get("day_zero_run_id") and
            clock.get("day_zero_utc") == ledger.get("day_zero_utc"),
            "AFP day-zero clock and requested run disagree")
    with tempfile.TemporaryDirectory(prefix="ipr-afp-review-") as temp:
        db_path = Path(temp) / "shadow.db"
        db_path.write_bytes(db_blob)
        cx = sqlite3.connect(db_path.as_uri() + "?mode=ro&immutable=1", uri=True)
        cx.row_factory = sqlite3.Row
        try:
            cx.execute("PRAGMA query_only=ON")
            require(cx.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                    "AFP source SQLite integrity check failed")
            total = cx.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0]
            require(total == ledger.get("stored_total"),
                    "run ledger disagrees with stored record count")
            records = cx.execute(
                "SELECT * FROM shadow_records WHERE first_seen_run=? "
                "ORDER BY published_at_utc, source_identity", (run_id,)
            ).fetchall()
            require(len(records) == ledger["inserted"],
                    "insertion count does not match first-seen archived records")
            output = []
            seen = set()
            for record in records:
                rec = dict(record)
                source_id = rec["source_identity"]
                require(source_id not in seen and
                        rec["source_slug"] == "ph_afp_articles" and
                        rec["language_tag"] == "en" and
                        rec["first_seen_run"] == run_id,
                        "unexpected or repeated source identity")
                seen.add(source_id)
                require(type(rec["text_original"]) is str and
                        sha256(rec["text_original"].encode("utf-8")) ==
                        rec["content_sha256"],
                        source_id + ": extracted text hash mismatch")
                require(rec["text_status"] in ("text", "no_text"),
                        source_id + ": unsupported body state")
                caps = cx.execute(
                    "SELECT * FROM captures WHERE source_identity = ? "
                    "AND run_id = ? ORDER BY capture_id",
                    (source_id, run_id)
                ).fetchall()
                require(len(caps) == 1,
                        source_id + ": exactly one original insertion capture required")
                cap = dict(caps[0])
                raw = cap["payload"]
                require(type(raw) is bytes and
                        sha256(raw) == cap["payload_sha256"] ==
                        rec["capture_sha256"] and
                        cap["source_fingerprint"] == rec["source_fingerprint"] and
                        cap["http_status"] == 200 and
                        type(cap["requested_url"]) is str and
                        cap["requested_url"].startswith(
                            "https://api.afp.mil.ph/articles/") and
                        cap["requested_url"] == cap["final_url"],
                        source_id + ": historical API response capture mismatch")
                try:
                    original = raw.decode("utf-8")
                    api = json.loads(original)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise AFPReviewError(
                        source_id + ": original API JSON invalid") from exc
                require(type(api) is dict, "original source response is not JSON object")
                _date_fields_match(api, rec)
                output.append({
                    "source_identity": source_id,
                    "source_url": rec["url"],
                    "title_original": rec["title_original"],
                    "published_date": rec["published_date"],
                    "published_at_original": rec["published_at_original"],
                    "published_at_utc": rec["published_at_utc"],
                    "source_slug": rec["source_slug"],
                    "text_sha256": rec["content_sha256"],
                    "text_original": rec["text_original"],
                    "text_status": rec["text_status"],
                    "source_fingerprint": rec["source_fingerprint"],
                    "capture_sha256": rec["capture_sha256"],
                    "capture_request_url": cap["requested_url"],
                    "capture_final_url": cap["final_url"],
                    "capture_retrieved_at": cap["retrieved_at"],
                    "capture_http_status": cap["http_status"],
                    "body_chars": len(rec["text_original"]),
                    "byline": rec["byline"],
                    "first_seen_run": rec["first_seen_run"],
                    "original_api_response_utf8": original,
                    "decision": "pending",
                    "checks": {check: None for check in CHECKS},
                    "reviewer_name": "",
                    "read_original_capture": False,
                    "reviewed_at_utc": None,
                    "rationale": "",
                })
        finally:
            cx.close()
    return {
        "protocol": "ipr_ph_afp_per_run_unsigned_review_v1",
        "review_scope": "all_new_records_from_exact_scheduled_shadow_run",
        "historical_state_commit": state.commit,
        "historical_git_blobs": {
            "state/shadow.db": state.blob("state/shadow.db"),
            ledger_path: state.blob(ledger_path),
            "state/clock.json": state.blob("state/clock.json"),
        },
        "original_run_id": run_id,
        "target_date": ledger["target_date"],
        "source_kind": "AFP_first_party_shadow_not_production",
        "human_review_complete": False,
        "human_approval": False,
        "desk_qualified": False,
        "production_assignments": 0,
        "machine_verified_capture_count": len(output),
        "records": output,
    }


def validate_packet(candidate: dict, expected: dict, *,
                    require_complete: bool = False) -> dict:
    require(type(candidate) is dict and set(candidate) == set(expected),
            "review document top-level fields changed")
    candidate_rows = candidate.get("records")
    source_rows = expected["records"]
    require(type(candidate_rows) is list and len(candidate_rows) == len(source_rows),
            "review record count changed")
    for submitted, original in zip(candidate_rows, source_rows):
        require(type(submitted) is dict and set(submitted) == set(original),
                "review record schema changed")
        for field in EXTRA_PINNED_FIELDS:
            require(submitted[field] == original[field],
                    original["source_identity"] + ": original captured evidence modified")
    # The merged Day-0 validator binds all other source identities and the
    # non-record run/commit fields, while only allowing human decision fields
    # to change. It never certifies a named human as genuine.
    result = validate_reviews(candidate, expected, require_complete=require_complete)
    result["original_run_id"] = expected["original_run_id"]
    result["target_date"] = expected["target_date"]
    result["machine_full_raw_capture_access_provided"] = True
    result["reviewer_actually_read_original_verified"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("packet", "validate"))
    parser.add_argument("--state-repo", required=True, type=Path)
    parser.add_argument("--state-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        original = make_packet(FrozenState(args.state_repo, args.state_commit),
                               args.run_id)
        if args.action == "packet":
            require(args.decisions is None and not args.require_complete,
                    "packet generation cannot assert review completeness")
            print(json.dumps(original, ensure_ascii=False, indent=2))
        else:
            require(args.decisions is not None, "validation requires review decisions")
            doc = json.loads(args.decisions.read_text(encoding="utf-8"))
            print(json.dumps(validate_packet(
                doc, original, require_complete=args.require_complete
            ), indent=2))
    except (AFPReviewError, sqlite3.DatabaseError, TypeError,
            ValueError, OSError, UnicodeDecodeError) as exc:
        parser.exit(1, "AFP per-run review: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
