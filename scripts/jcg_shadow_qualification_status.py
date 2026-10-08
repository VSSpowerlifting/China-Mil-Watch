"""Read-only JCG shadow *qualification evidence*, never promotion approval.

Evaluate actual immutable capture/ledger state at an explicitly pinned commit.
An archived document's publication date is not the day a collector operated.
A historic backfill may add original records, but MUST NOT fill collecting days.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

DAY_ZERO_RUN = "37828199188-1"
DESK = "japan_jcg"
REF = "shadow/japan-jcg"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SOURCES = {"explicit", "schedule-slot", "manual-utc-date"}
SUCCESSES = {"ok", "ok_no_publications", "ok_all_duplicates", "ok_all_filtered"}
BACKFILL = "jcg_2026_09_historical_backfill"
CHECKPOINTS = (7, 14, 30)


class EvidenceError(ValueError):
    """A structural issue means no defensible qualification report."""


def _date(text):
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        raise EvidenceError("strict ISO UTC date required")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceError("impossible calendar date") from exc


def _instant(text):
    try:
        value = datetime.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise EvidenceError("invalid ledger UTC instant") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise EvidenceError("ledger time must be offset-aware")
    return value


def _digest(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for part in iter(lambda: fp.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def _strict_state_tree(state):
    if state.is_symlink() or not state.is_dir():
        raise EvidenceError("state must be a real directory")
    known = {"shadow.db", "clock.json"}
    for item in state.rglob("*"):
        if item.is_symlink():
            raise EvidenceError("state contains symlink")
        if item.is_file():
            rel = item.relative_to(state).as_posix()
            if (rel not in known and
                    not re.fullmatch(r"ledger/[A-Za-z0-9_.+-]+\.json", rel) and
                    not re.fullmatch(r"captures/[0-9a-f]{64}\.bin", rel)):
                raise EvidenceError("unexpected file in immutable state")
    if not all((state / s).is_file() for s in known):
        raise EvidenceError("missing shadow DB or clock")


def _summarize(state, as_of, commit):
    if not SHA40.fullmatch(commit):
        raise EvidenceError("full immutable state commit required")
    _strict_state_tree(state)
    clock = json.loads((state / "clock.json").read_text(encoding="utf-8"))
    if clock.get("desk") != DESK or clock.get("day_zero_run_id") != DAY_ZERO_RUN:
        raise EvidenceError("clock does not identify verified JCG Day 0")
    day0_instant = _instant(clock.get("day_zero_utc"))
    day0 = day0_instant.date()
    if day0 != date(2026, 10, 8) or as_of < day0:
        raise EvidenceError("as-of precedes verified JCG day zero")
    if (as_of - day0).days > 365:
        raise EvidenceError("qualification reporting window exceeds one year")
    ledger_paths = sorted((state / "ledger").glob("*.json"))
    if not ledger_paths:
        raise EvidenceError("no immutable collection ledgers")
    seen_runs = set()
    day_results = {}
    anomalies = []
    backfill_runs = []
    previous = None
    original_anchor_seen = False
    source_days = 0
    failed_attempts = 0
    for i, path in enumerate(ledger_paths):
        item = json.loads(path.read_text(encoding="utf-8"))
        run = item.get("run_id")
        if not isinstance(run, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", run):
            raise EvidenceError("invalid ledger run id")
        if run in seen_runs or item.get("desk") != DESK:
            raise EvidenceError("duplicate run or wrong desk ledger")
        seen_runs.add(run)
        started = _instant(item.get("started_utc"))
        finished = _instant(item.get("finished_utc"))
        if started > finished or finished < day0_instant - timedelta(days=1):
            raise EvidenceError("ledger run timing impossible")
        if item.get("target_date_source") not in SOURCES:
            raise EvidenceError("unknown publisher logical-day date basis")
        target = _date(item.get("target_date"))
        if target < day0:
            raise EvidenceError("backdated collection day predates Day 0")
        before, after = item.get("state_sha256_before"), item.get("state_sha256_after")
        if (before is not None and not SHA256.fullmatch(str(before))) or not SHA256.fullmatch(str(after)):
            raise EvidenceError("invalid evidence chain SHA")
        if i == 0:
            if before is not None or run != DAY_ZERO_RUN or target != day0:
                raise EvidenceError("first ledger must be original Day 0 state creation")
            original_anchor_seen = True
        elif before != previous:
            raise EvidenceError("state SHA-256 chain discontinuity")
        previous = after
        if item.get("health") not in {"ok", "fail", "skipped"}:
            raise EvidenceError("unrecognized collection health")
        if item.get("result") is None:
            raise EvidenceError("missing terminal result")
        for request in item.get("requests", []):
            digest = request.get("capture_sha256")
            if not isinstance(digest, str) or not SHA256.fullmatch(digest):
                raise EvidenceError("invalid capture digest")
            capture = state / "captures" / (digest + ".bin")
            if not capture.is_file() or _digest(capture) != digest:
                raise EvidenceError("request capture altered or missing")
        operation = item.get("operation")
        if operation == BACKFILL:
            if (item.get("counts_as_qualifying_shadow_day") is not False or
                    item.get("shadow_day") is not None or
                    item.get("backfill_anchor_day_zero_run_id") != DAY_ZERO_RUN or
                    target != day0 or item.get("lookback_days") != 38 or
                    item.get("cap") != 5):
                raise EvidenceError("backfill marked as collection-day evidence")
            backfill_runs.append(run)
            if item.get("health") != "ok":
                anomalies.append({"run_id": run, "kind": "backfill_failed"})
            continue
        if operation is not None or item.get("counts_as_qualifying_shadow_day") is False:
            raise EvidenceError("unrecognized or misclassified historical operation")
        source_days += 1
        if run == DAY_ZERO_RUN and (target != day0 or item.get("shadow_day") != 0):
            raise EvidenceError("Day 0 collection anchor was altered")
        if target > as_of:
            # Future ledgers must not fill any currently evaluated day.
            continue
        successful = (item.get("health") == "ok" and item.get("result") in SUCCESSES and
                      item.get("listing_status") == "ok" and
                      item.get("robots_status") in {"allowed", "absent"} and
                      all(item.get(k, 0) == 0 for k in (
                          "fetch_failures", "extraction_failures", "access_failures")) and
                      item.get("retrieved", -1) == item.get("selected", -2) and
                      item.get("extracted", -1) == item.get("selected", -2))
        key = target.isoformat()
        day_results.setdefault(key, []).append({"run_id": run, "success": bool(successful)})
        if not successful:
            failed_attempts += 1
            anomalies.append({"run_id": run, "kind": "unhealthy_or_incomplete_collection", "logical_date": key})
    if not original_anchor_seen or previous != _digest(state / "shadow.db"):
        raise EvidenceError("last ledger hash does not match persistent SQLite state")
    if len(backfill_runs) > 1:
        raise EvidenceError("multiple one-time historical backfill entries")
    with sqlite3.connect((state / "shadow.db").as_uri() + "?mode=ro&immutable=1", uri=True) as db:
        count = db.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0]
        desks = db.execute("SELECT desk FROM shadow_meta").fetchall()
    if desks != [(DESK,)] or count < 3:
        raise EvidenceError("original JCG corpus count or identity changed")
    days = []
    for elapsed in range((as_of - day0).days + 1):
        day = (day0 + timedelta(days=elapsed)).isoformat()
        runs = day_results.get(day, [])
        healthy = any(x["success"] for x in runs)
        if len(runs) > 1:
            anomalies.append({"kind": "multiple_collection_attempts_same_day",
                              "logical_date": day, "attempts": len(runs)})
        days.append({"date": day, "day_offset": elapsed,
                     "status": "collected" if healthy else
                               "unhealthy" if runs else "missing",
                     "attempts": len(runs)})
    streak = 0
    for d in days:
        if d["status"] != "collected":
            break
        streak += 1
    missing = [d["date"] for d in days if d["status"] == "missing"]
    unhealthy = [d["date"] for d in days if d["status"] == "unhealthy"]
    checkpoints = []
    for offset in CHECKPOINTS:
        due = day0 + timedelta(days=offset)
        if as_of < due:
            verdict = "not_due"
        elif any(d["status"] != "collected" for d in days[:offset + 1]) or anomalies:
            verdict = "evidence_gaps_or_anomalies_require_disposition"
        else:
            verdict = "human_checkpoint_required_not_approved"
        checkpoints.append({"checkpoint": "day_plus_" + str(offset),
                            "due_utc_date": due.isoformat(), "machine_readiness": verdict,
                            "human_review_completed": False})
    return {
        "schema": "japan-jcg-shadow-qualification-evidence/1",
        "desk": DESK, "institution": "Japan Coast Guard", "scope": "english_html_only",
        "state_ref": REF, "state_commit": commit,
        "state_db_sha256": previous, "as_of": as_of.isoformat(),
        "day_zero_date": day0.isoformat(), "day_zero_run_id": DAY_ZERO_RUN,
        "archived_records": count, "ledger_count": len(ledger_paths),
        "qualifying_collection_attempts": source_days,
        "nonqualifying_historical_backfill_runs": backfill_runs,
        "unhealthy_attempts": failed_attempts,
        "collected_days_from_day_zero": sum(d["status"] == "collected" for d in days),
        "consecutive_collected_days_from_day_zero": streak,
        "missing_days": missing, "unhealthy_days": unhealthy,
        "anomalies_require_disposition": anomalies,
        "days": days, "checkpoints": checkpoints,
        "source_rights_human_review_completed": False,
        "source_pdf_completeness_human_review_completed": False,
        "human_checkpoint_reviews_completed": False,
        "owner_promotion_authorized": False,
        "production_eligible": False,
        "weekly_writer_eligible": False,
        "report_is_machine_only": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--state-commit", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("report already exists; overwrite refused")
    try:
        result = _summarize(args.state_dir, _date(args.as_of), args.state_commit)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "state_commit": result["state_commit"],
        "collected_days": result["collected_days_from_day_zero"],
        "missing_days": len(result["missing_days"]),
        "historic_imports": len(result["nonqualifying_historical_backfill_runs"]),
        "promotion_authorized": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
