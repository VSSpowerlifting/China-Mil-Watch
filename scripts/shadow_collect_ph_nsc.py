#!/usr/bin/env python3
"""Philippines NSC isolated shadow runner; no production storage or rendering.

State belongs outside every collector checkout, on shadow/ph-nsc. The
workflow preserves failed attempts as artifacts and pushes successful state
only. Collector identity is the adapter's unchanged rehearsal identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st
from core.collection.contract import CollectionWindow
from core.shadow_schedule import SOURCE_EXPLICIT, ScheduleError, resolve_target_date
from scraper.sources.ph_nsc import PHNscAdapter, USER_AGENT

MANIFEST = REPO_ROOT / "shadow" / "ph_nsc" / "manifest.json"
SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_records (
    url TEXT PRIMARY KEY,
    source_identity TEXT NOT NULL UNIQUE,
    source_slug TEXT NOT NULL,
    title_original TEXT NOT NULL,
    text_original TEXT NOT NULL,
    published_date TEXT NOT NULL,
    published_at_original TEXT NOT NULL,
    published_at_utc TEXT NOT NULL,
    language_tag TEXT NOT NULL,
    site_byline TEXT NOT NULL,
    site_byline_url TEXT NOT NULL,
    publication_kind TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    capture_sha256 TEXT NOT NULL,
    requested_url TEXT NOT NULL,
    final_url TEXT NOT NULL,
    http_status INTEGER NOT NULL,
    retrieved_at TEXT NOT NULL,
    first_seen_run TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shadow_published ON shadow_records(published_date);
"""


def assert_isolated(state_dir: Path) -> None:
    resolved = state_dir.resolve()
    # Includes the primary checkout when this runner lives in a nested worktree.
    for root in (REPO_ROOT,) + tuple(REPO_ROOT.parents):
        if (root / ".git").exists() and (resolved == root or root in resolved.parents):
            raise ValueError("shadow state must be outside the repository: %s" % resolved)
    if state_dir.exists() and any(p.is_symlink() for p in state_dir.rglob("*")):
        raise ValueError("shadow state must not contain symlinks")


def load_source():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return SimpleNamespace(**manifest["sources"][0])


def file_sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _finish(entry, state_dir, db_path):
    entry["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry["state_sha256_after"] = file_sha256(db_path)
    clock_path = state_dir / "clock.json"
    if clock_path.exists():
        clock = json.loads(clock_path.read_text(encoding="utf-8"))
    elif st.is_success(entry["result"]):
        clock = {"day_zero_utc": entry["finished_utc"], "day_zero_run_id": entry["run_id"]}
        with clock_path.open("x", encoding="utf-8") as fh:
            fh.write(json.dumps(clock, indent=1, sort_keys=True) + "\n")
    else:
        clock = None
    entry["shadow_day"] = None
    if clock:
        entry["day_zero_utc"] = clock["day_zero_utc"]
        if st.is_success(entry["result"]):
            entry["shadow_day"] = (datetime.fromisoformat(entry["finished_utc"])
                                   - datetime.fromisoformat(clock["day_zero_utc"])).days
    stamp = entry["finished_utc"].replace(":", "").replace("-", "")
    with (state_dir / "ledger" / (stamp + "-" + entry["run_id"] + ".json")).open(
            "x", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, indent=1, sort_keys=True) + "\n")
    return entry


def run(state_dir: Path, target: date, lookback: int, cap: int,
        run_id: str, commit: str, adapter=None, target_source=SOURCE_EXPLICIT):
    assert_isolated(state_dir)
    if lookback < 0 or cap < 1 or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", run_id):
        raise ValueError("non-negative lookback, positive cap and safe run id required")
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "ledger").mkdir(exist_ok=True)
    db_path = state_dir / "shadow.db"
    entry = {
        "run_id": run_id, "collector_commit": commit, "collector_identity": USER_AGENT,
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target_date": target.isoformat(), "target_date_source": target_source,
        "window_start": (target - timedelta(days=lookback)).isoformat(),
        "lookback_days": lookback, "cap": cap,
        "robots_status": None, "listing_status": None, "listing_report": {},
        "discovered": 0, "selected": 0, "retrieved": 0, "inserted": 0,
        "duplicates": 0, "fetch_failures": 0, "extraction_failures": 0,
        "access_failures": 0, "challenged": 0, "failures": [],
        "content_hashes": [], "captures": [], "stored_total": 0,
        "state_sha256_before": file_sha256(db_path),
        "result": None, "health": None, "error_detail": None,
    }
    source = load_source()
    conn = None
    committed = False
    try:
        if source.enabled is not True:
            entry.update(result=st.SKIPPED_DISABLED, health="skipped")
            return _finish(entry, state_dir, db_path)
        adapter = adapter or PHNscAdapter(source)
        discovery = adapter.discover(CollectionWindow(target, lookback))
        entry.update(listing_status=discovery.status,
                     robots_status=adapter.robots_status,
                     listing_report=adapter.listing_report,
                     discovered=len(discovery.references))
        if not discovery.ok:
            entry.update(result=discovery.status, health="fail",
                         error_detail=discovery.error_detail,
                         failed_endpoints=discovery.failed_endpoints)
            if discovery.status == st.ACCESS_CHALLENGED:
                entry["challenged"] += 1
            if discovery.status in (st.AUTH_FAILURE, st.ACCESS_CHALLENGED):
                entry["access_failures"] += 1
            return _finish(entry, state_dir, db_path)
        # Never truncate a proven listing into a sample. An unexpectedly large
        # window is a failed run, with all candidate URLs retained for recovery.
        if len(discovery.references) > cap:
            entry.update(result=st.LISTING_FAILURE, health="fail",
                         error_detail="proven window exceeds cap; no items fetched",
                         deferred_urls=[ref.url for ref in discovery.references])
            return _finish(entry, state_dir, db_path)
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA)
        entry["selected"] = len(discovery.references)
        for ref in discovery.references:
            capture = adapter.fetch(ref)
            if capture.status != st.OK:
                key = "access_failures" if capture.status in (
                    st.AUTH_FAILURE, st.ACCESS_CHALLENGED) else "fetch_failures"
                entry[key] += 1
                entry["challenged"] += capture.status == st.ACCESS_CHALLENGED
                entry["failures"].append({"url": ref.url, "stage": "fetch",
                                           "status": capture.status,
                                           "detail": capture.error_detail})
                continue
            entry["retrieved"] += 1
            # The adapter accepts UTF-8 only, so this round trip preserves the
            # exact response bytes. Check the transport hash before persistence.
            payload = capture.body.encode("utf-8")
            if hashlib.sha256(payload).hexdigest() != capture.payload_sha256:
                raise ValueError("capture bytes disagree with transport hash")
            (state_dir / "captures").mkdir(exist_ok=True)
            capture_path = state_dir / "captures" / (capture.payload_sha256 + ".bin")
            if capture_path.exists():
                if file_sha256(capture_path) != capture.payload_sha256:
                    raise ValueError("stored capture hash disagrees with its filename")
            else:
                capture_path.write_bytes(payload)
            entry["captures"].append({
                "requested_url": capture.requested_url, "final_url": capture.final_url,
                "http_status": capture.http_status, "retrieved_at": capture.retrieved_at,
                "capture_sha256": capture.payload_sha256,
            })
            result = adapter.extract(capture)
            if result.status != st.OK or not result.documents:
                entry["extraction_failures"] += 1
                entry["failures"].append({"url": ref.url, "stage": "extract",
                                           "status": result.status,
                                           "detail": result.error_detail})
                continue
            for doc in result.documents:
                extra = doc.extra
                row = conn.execute("SELECT url, source_identity FROM shadow_records"
                                   " WHERE source_identity = ? OR url = ?",
                                   (extra["source_identity"], doc.url)).fetchone()
                entry["content_hashes"].append(extra["content_sha256"])
                entry["captures"][-1].update(source_identity=extra["source_identity"],
                                              content_sha256=extra["content_sha256"])
                if row:
                    if row != (doc.url, extra["source_identity"]):
                        raise ValueError("stored URL and post identity disagree")
                    entry["duplicates"] += 1
                    continue
                conn.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (doc.url, extra["source_identity"], doc.source_slug,
                              doc.title_original, doc.text_original, doc.published_date,
                              extra["published_at_original"], extra["published_at_utc"],
                              doc.language_tag, extra["site_byline"], extra["site_byline_url"],
                              extra["publication_kind"], extra["content_sha256"],
                              extra["capture_sha256"], capture.requested_url, capture.final_url,
                              capture.http_status, capture.retrieved_at, run_id))
                entry["inserted"] += 1
        conn.commit()
        committed = True
        entry["stored_total"] = conn.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0]
        entry["corpus_range"] = list(conn.execute(
            "SELECT MIN(published_date), MAX(published_date) FROM shadow_records").fetchone())
        if entry["access_failures"] or entry["fetch_failures"] or entry["extraction_failures"]:
            entry.update(result=(st.ACCESS_CHALLENGED if entry["challenged"] else
                                 st.AUTH_FAILURE if entry["access_failures"] else
                                 st.FETCH_FAILURE if entry["fetch_failures"] else
                                 st.EXTRACTION_FAILURE), health="fail",
                         error_detail="incomplete run; state must not be pushed")
        else:
            entry.update(result=(st.OK if entry["inserted"] else
                                 st.OK_ALL_DUPLICATES if entry["duplicates"] else
                                 st.OK_NO_PUBLICATIONS), health="ok")
    except Exception as exc:
        if conn:
            conn.rollback()
            if not committed:
                entry["inserted"] = 0
        entry.update(result=st.ADAPTER_ERROR, health="fail",
                     error_detail="%s: %s" % (type(exc).__name__, exc))
    finally:
        if conn:
            conn.close()
    return _finish(entry, state_dir, db_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--target-date", default=None)
    ap.add_argument("--lookback-days", type=int, default=6)
    ap.add_argument("--cap", type=int, default=40)
    ap.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    ap.add_argument("--commit", default="unknown")
    ap.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME"))
    ap.add_argument("--cron-utc", default=None)
    ap.add_argument("--run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT") or "1")
    args = ap.parse_args(argv)
    try:
        target, source = resolve_target_date(datetime.now(timezone.utc), args.event_name,
                                             args.cron_utc, args.target_date, args.run_attempt)
        entry = run(Path(args.state_dir), target, args.lookback_days, args.cap,
                    args.run_id, args.commit, target_source=source)
    except (ScheduleError, ValueError) as exc:
        print("collection refused: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(entry, indent=1, sort_keys=True))
    return 0 if entry["health"] in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
