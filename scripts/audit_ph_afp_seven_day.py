"""Read-only seven-slot AFP shadow reliability evidence audit.

Reports ledger-backed *candidates* for seven successive scheduled logical dates.
Does not authenticate GitHub Actions event origins, successful failed-attempt
artifacts, reuse rights, source accuracy, human reviews, or desk qualification.
Requires literal historical state-branch Git commit; no network/fetch/writeback.
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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUCCESS = frozenset(("ok", "ok_no_publications", "ok_all_duplicates",
                     "ok_all_filtered"))
SOURCE_DESK = "ph-afp"
CRON_SOURCE = "schedule-slot"
DAYS = 7
ZERO_FAILURES = ("fetch_failures", "extraction_failures", "access_failures",
                 "redirect_refusals", "identity_collisions")
EXPECTED_DB_TABLES = frozenset(("shadow_records", "captures", "revisions"))


class AFPSevenDayError(ValueError):
    """Missing, contradictory, corrupt, or unpinned shadow evidence."""


def require(condition, why):
    if not condition:
        raise AFPSevenDayError(why)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def day(value):
    require(type(value) is str and bool(re.fullmatch(r"\d{4}-\d\d-\d\d", value)),
            "logical dates must be exact YYYY-MM-DD")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise AFPSevenDayError("invalid logical UTC date") from exc
    require(result.isoformat() == value, "noncanonical UTC date")
    return result


def utc(value):
    require(type(value) is str, "missing ISO UTC timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AFPSevenDayError("invalid ledger UTC timestamp") from exc
    require(result.tzinfo is not None and
            result.utcoffset() == timedelta(0),
            "ledger timestamp is not UTC")
    return result


def positive_integer(v, *, zero=True):
    return type(v) is int and (v >= 0 if zero else v > 0)


class FrozenState:
    """Reads only exact Git objects reachable from one literal commit."""

    def __init__(self, checkout, commit):
        require(type(commit) is str and re.fullmatch(r"[0-9a-f]{40}", commit),
                "state snapshot must be a literal 40-character Git commit")
        self.checkout = Path(checkout)
        self.commit = commit
        self.files = set(self._git("ls-tree", "-r", "--name-only",
                                   commit, "state").decode("utf-8").splitlines())
        require("state/clock.json" in self.files and
                "state/shadow.db" in self.files,
                "pinned AFP state lacks clock or database")
        require(all(x.startswith("state/") and ".." not in Path(x).parts
                    for x in self.files), "unsafe Git state path")
        self.cache = {}

    def _git(self, *args):
        try:
            return subprocess.run(
                ["git", *args], cwd=self.checkout, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, check=True, timeout=30,
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            raise AFPSevenDayError(
                "required historical Git object unavailable; no ref/network fallback"
            ) from exc

    def read(self, path, *, limit=50000000):
        require(path in self.files, "missing pinned state file: " + path)
        if path not in self.cache:
            sha = self._git("rev-parse", "--verify",
                            self.commit + ":" + path).decode("ascii").strip()
            require(bool(re.fullmatch(r"[0-9a-f]{40}", sha)),
                    "invalid historical Git blob for " + path)
            content = self._git("cat-file", "blob", sha)
            require(len(content) <= limit, "historical blob exceeds audit limit")
            calculated = hashlib.sha1(
                ("blob %d\0" % len(content)).encode("ascii") + content
            ).hexdigest()
            require(sha == calculated, "historical Git blob digest mismatch")
            self.cache[path] = content
        return self.cache[path]

    def read_json(self, path):
        try:
            data = json.loads(self.read(path))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AFPSevenDayError("malformed historical JSON: " + path) from exc
        require(type(data) is dict, "expected object in " + path)
        return data


def audit_database(db_bytes):
    """Read one immutable SQLite copy, inspect all persisted captures and rows."""
    require(db_bytes.startswith(b"SQLite format 3\x00"),
            "state/shadow.db is not SQLite")
    with tempfile.TemporaryDirectory(prefix="ipr-afp-seven-day-") as temp:
        file = Path(temp) / "shadow.db"
        file.write_bytes(db_bytes)
        cx = sqlite3.connect(file.as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            cx.execute("PRAGMA query_only=ON")
            require(cx.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                    "SQLite integrity failure")
            names = {r[0] for r in cx.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'")}
            require(names == EXPECTED_DB_TABLES,
                    "unexpected AFP SQLite tables")
            records = cx.execute(
                "SELECT source_identity, content_sha256, text_original, "
                "text_status, capture_sha256 FROM shadow_records").fetchall()
            captures = cx.execute(
                "SELECT source_identity, payload, payload_sha256 "
                "FROM captures").fetchall()
            revisions = cx.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
            for ident, sha, body, status, cap_sha in records:
                require(type(ident) is str and ident.startswith("afp:"),
                        "invalid stored AFP source identity")
                require(status in ("text", "no_text"),
                        "unknown body preservation status")
                require(type(body) is str and digest(body.encode("utf-8")) == sha,
                        "stored AFP extracted body hash mismatch")
                require(type(cap_sha) is str and re.fullmatch(r"[a-f0-9]{64}", cap_sha),
                        "stored AFP original-capture hash missing")
            by_identity = {}
            for ident, payload, sha in captures:
                require(type(payload) is bytes and digest(payload) == sha,
                        "stored original response capture hash mismatch")
                by_identity.setdefault(ident, []).append(sha)
            for ident, _, _, _, captured in records:
                require(captured in by_identity.get(ident, []),
                        "record has no matching original capture")
            return {"records": len(records), "captures": len(captures),
                    "revisions": revisions,
                    "body_text_records": sum(x[3] == "text" for x in records)}
        finally:
            cx.close()


def load_ledgers(state):
    paths = sorted(p for p in state.files
                   if re.fullmatch(r"state/ledger/[^/]+\.json", p))
    require(paths, "no durable completed attempt ledgers")
    rows = []
    run_ids = set()
    for path in paths:
        row = state.read_json(path)
        run = row.get("run_id")
        require(type(run) is str and
                bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", run)) and
                run not in run_ids, "duplicate or malformed run ID")
        run_ids.add(run)
        require(row.get("desk") == SOURCE_DESK, "non-AFP ledger in state")
        day(row.get("target_date"))
        utc(row.get("started_utc"))
        utc(row.get("finished_utc"))
        require(utc(row["finished_utc"]) >= utc(row["started_utc"]),
                "ledger completion precedes start")
        row["_ledger_path"] = path
        rows.append(row)
    return sorted(rows, key=lambda x: (utc(x["finished_utc"]), x["run_id"]))


def check_receipts(state, entry):
    evidence = entry.get("request_evidence")
    require(type(evidence) is dict, "missing request evidence manifest")
    path = evidence.get("path")
    expected = "evidence/" + entry["run_id"] + ".json"
    require(path == expected, "request receipts path differs from run ID")
    raw = state.read("state/" + path)
    require(digest(raw) == evidence.get("sha256"),
            "request-receipt hash mismatch")
    try:
        receipts = json.loads(raw)
    except ValueError as exc:
        raise AFPSevenDayError("malformed request receipts JSON") from exc
    require(type(receipts) is list and
            len(receipts) == evidence.get("requests"),
            "request receipts count differs from ledger")
    for receipt in receipts:
        require(type(receipt) is dict, "malformed request receipt entry")
        if receipt.get("payload_retained") is True:
            sha = receipt.get("payload_sha256")
            require(type(sha) is str and re.fullmatch(r"[a-f0-9]{64}", sha),
                    "retained request payload digest missing")
            payload_path = "state/evidence/payloads/" + sha + ".bin"
            require(digest(state.read(payload_path)) == sha,
                    "retained original policy/listing payload changed")
    return len(receipts)


def ledger_gate(entry, state):
    """Machine evidence only; NEVER confirms the actual GitHub Actions event."""
    issues = []
    def check(ok, label):
        if not ok:
            issues.append(label)
    check(entry.get("target_date_source") == CRON_SOURCE, "not_schedule_slot")
    check(entry.get("rehearsal") is False, "rehearsal_or_missing")
    check(entry.get("result") in SUCCESS and entry.get("health") == "ok",
          "nonterminal_or_unhealthy")
    check(entry.get("robots_status") == "allowed", "robots_not_allowed")
    check(entry.get("listing_status") in SUCCESS, "listing_incomplete")
    check(entry.get("aborted") is None, "collection_aborted")
    check(entry.get("failure_log") == [], "failure_log_not_empty")
    for key in ZERO_FAILURES:
        check(entry.get(key) == 0 and type(entry.get(key)) is int,
              "nonzero_" + key)
    check(entry.get("cap") == 100 and entry.get("lookback_days") == 14,
          "nonstandard_window")
    observed = entry.get("observed")
    check(type(observed) is dict and
          observed.get("count_mismatch") is False and
          observed.get("listing_end") == "next_null" and
          positive_integer(observed.get("list_pages"), zero=False) and
          observed.get("listed_items") == observed.get("api_reported_count"),
          "listing_not_reconciled")
    check(positive_integer(entry.get("selected")) and
          positive_integer(entry.get("retrieved")) and
          positive_integer(entry.get("inserted")) and
          positive_integer(entry.get("duplicates")) and
          positive_integer(entry.get("revisions")),
          "malformed_run_counts")
    check(type(entry.get("collector_commit")) is str and
          bool(re.fullmatch(r"[0-9a-f]{40}", entry["collector_commit"])),
          "collector_commit_not_pinned")
    check(type(entry.get("collector_identity")) is str and
          entry["collector_identity"].startswith("IndoPacificRecord-ShadowCollector/0.1"),
          "collector_identity_drift")
    check(entry.get("state_sha256_after") is not None and
          type(entry.get("state_sha256_after")) is str and
          bool(re.fullmatch(r"[a-f0-9]{64}", entry["state_sha256_after"])),
          "missing_state_digest")
    check(entry.get("shadow_day") is not None and
          positive_integer(entry.get("shadow_day")),
          "no_success_clock")
    check(entry.get("sample_unselected") == 0 and
          entry.get("sample_limit") is None,
          "sampling_or_truncation")
    # Even a ledger with malformed counts gets an explicit source-evidence failure,
    # never a silent pass or a substituted live-web response.
    try:
        check_receipts(state, entry)
    except (AFPSevenDayError, ValueError, TypeError) as exc:
        issues.append("request_evidence_invalid: " + str(exc))
    return issues


def assess(state, *, as_of, start=None):
    asof = day(as_of)
    clock = state.read_json("state/clock.json")
    dayzero_time = utc(clock.get("day_zero_utc"))
    dayzero = dayzero_time.date()
    first = day(start) if start is not None else dayzero
    require(first >= dayzero, "reliability window predates first successful AFP run")
    require(asof >= dayzero, "as-of predates AFP Day-0")
    rows = load_ledgers(state)
    dayzero_rows = [x for x in rows if x["run_id"] == clock.get("day_zero_run_id")]
    require(len(dayzero_rows) == 1 and
            dayzero_rows[0]["target_date"] == dayzero.isoformat() and
            dayzero_rows[0]["health"] == "ok" and
            dayzero_rows[0]["rehearsal"] is False,
            "Day-0 clock is not backed by an AFP successful ledger")
    db_bytes = state.read("state/shadow.db")
    stats = audit_database(db_bytes)
    # The most recently completed durable ledger must match the historical DB.
    last = rows[-1]
    require(last.get("state_sha256_after") == digest(db_bytes),
            "latest ledger state hash does not match immutable database")
    require(last.get("stored_total") == stats["records"],
            "latest ledger corpus total mismatches database rows")

    slots = []
    for i in range(DAYS):
        date_ = first + timedelta(days=i)
        matches = [x for x in rows if x["target_date"] == date_.isoformat()
                   and x.get("target_date_source") == CRON_SOURCE]
        slot = {"date": date_.isoformat(), "status": None,
                "scheduled_ledgers": [x["run_id"] for x in matches],
                "issues": [], "inserted": None, "required_human_reviews": None}
        if date_ > asof:
            slot["status"] = "future_not_due"
        elif len(matches) == 0:
            slot["status"] = "missing_scheduled_ledger"
        elif len(matches) != 1:
            slot["status"] = "ambiguous_multiple_scheduled_ledgers"
        else:
            entry = matches[0]
            issues = ledger_gate(entry, state)
            if issues:
                slot.update(status="invalid_ledger_evidence", issues=issues)
            else:
                new = entry["inserted"]
                slot.update(status="ledger_success_unverified_actions",
                            inserted=new,
                            required_human_reviews=new if new <= 5 else 5,
                            collector_commit=entry["collector_commit"],
                            run_id=entry["run_id"],
                            reported_result=entry["result"])
        slots.append(slot)
    supported = sum(s["status"] == "ledger_success_unverified_actions"
                    for s in slots)
    return {
        "protocol": "ipr_ph_afp_seven_day_shadow_evidence_v1",
        "immutable_state_commit": state.commit,
        "state_branch": "shadow/ph-afp",
        "day_zero": dayzero.isoformat(),
        "window_start": first.isoformat(),
        "window_end": (first + timedelta(days=DAYS - 1)).isoformat(),
        "as_of_utc_date": asof.isoformat(),
        "slots": slots,
        "successfully_supported_ledger_slots": supported,
        "all_seven_ledger_slots_supported": supported == DAYS,
        "required_human_review_records": sum(
            s["required_human_reviews"] or 0 for s in slots),
        "human_review_completed_or_verified": False,
        "github_actions_event_and_failure_artifacts_independently_verified": False,
        "source_reuse_rights_approved": False,
        "philippines_desk_qualified": False,
        "production_admission_authorized": False,
        "database": stats,
        "caveat": "A state branch only records published durable attempts; failed "
                  "Actions runs may leave artifacts without state commits. "
                  "Independent Actions/event and human evidence is mandatory.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-repo", type=Path, required=True)
    p.add_argument("--state-commit", required=True,
                   help="full literal SHA of an explicitly fetched shadow/ph-afp commit")
    p.add_argument("--as-of", required=True, help="UTC YYYY-MM-DD, never local clock")
    p.add_argument("--start-date", help="first of seven UTC logical collection days")
    args = p.parse_args()
    try:
        evidence = assess(
            FrozenState(args.state_repo, args.state_commit),
            as_of=args.as_of, start=args.start_date,
        )
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    except (AFPSevenDayError, OSError, TypeError, sqlite3.DatabaseError,
            UnicodeDecodeError) as exc:
        p.exit(1, "AFP seven-day source evidence: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
