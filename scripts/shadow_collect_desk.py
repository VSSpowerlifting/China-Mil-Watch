#!/usr/bin/env python3
"""Collect the Indonesia or Korea candidate into isolated, explicitly named state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st
from core.collection.contract import CollectionWindow
from core.manifests import load_manifest
from core.shadow_schedule import resolve_target_date, ScheduleError, SOURCE_EXPLICIT
from scraper.sources.desk_shadow_http import USER_AGENT
from scraper.sources.id_kemhan import KemhanAdapter
from scraper.sources.kr_policy_briefing import KoreaPolicyAdapter
from scraper.sources.jp_jcg_en import JCGEnglishAdapter

DESKS = {
    "indonesia": ("id_kemhan", KemhanAdapter, "shadow/indonesia-kemhan"),
    "korea": ("kr_policy_briefing", KoreaPolicyAdapter, "shadow/korea-policy-briefing"),
    "japan_jcg": ("jp_jcg", JCGEnglishAdapter, "shadow/japan-jcg"),
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_meta (desk TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS shadow_records (
 source_identity TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE,
 source_slug TEXT NOT NULL, title_original TEXT NOT NULL,
 text_original TEXT NOT NULL, published_date TEXT NOT NULL,
 language_tag TEXT NOT NULL, metadata_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL, capture_sha256 TEXT NOT NULL,
 first_seen_run TEXT NOT NULL
);
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def assert_isolated(state_dir):
    resolved = state_dir.resolve()
    roots = [REPO_ROOT]
    marker = REPO_ROOT / ".git"
    if marker.is_file():
        common = marker.read_text().strip().removeprefix("gitdir: ")
        if "/.git/" in common:
            roots.append(Path(common.split("/.git/", 1)[0]))
    try:
        topology = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "worktree", "list", "--porcelain"],
            text=True, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("cannot verify collector worktree topology; state refused")
    roots.extend(Path(line[len("worktree "):]).resolve()
                 for line in topology.splitlines() if line.startswith("worktree "))
    if any(resolved == root or root in resolved.parents for root in roots):
        raise ValueError("state must be outside the collector and primary checkouts")
    if state_dir.is_symlink() or (state_dir.exists() and any(p.is_symlink() for p in state_dir.rglob("*"))):
        raise ValueError("state must not contain symlinks")


def check_existing(state_dir, desk):
    assert_isolated(state_dir)
    clock = state_dir / "clock.json"
    if clock.exists() and json.loads(clock.read_text()).get("desk") != desk:
        raise ValueError("clock belongs to another desk")
    path = state_dir / "shadow.db"
    if path.exists():
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
            if conn.execute("SELECT desk FROM shadow_meta").fetchall() != [(desk,)]:
                raise ValueError("database belongs to another desk")


def finish(entry, state_dir):
    entry["finished_utc"] = datetime.now(timezone.utc).isoformat()
    entry["state_sha256_after"] = sha(state_dir / "shadow.db")
    clock_path = state_dir / "clock.json"
    clock = json.loads(clock_path.read_text()) if clock_path.exists() else None
    if clock is None and st.is_success(entry["result"]):
        clock = {"desk": entry["desk"], "day_zero_utc": entry["finished_utc"],
                 "day_zero_run_id": entry["run_id"]}
        with clock_path.open("x", encoding="utf-8") as fh:
            fh.write(json.dumps(clock, indent=2) + "\n")
    entry["day_zero_utc"] = clock["day_zero_utc"] if clock else None
    entry["shadow_day"] = ((datetime.fromisoformat(entry["finished_utc"]) -
                            datetime.fromisoformat(clock["day_zero_utc"])).days
                           if clock and st.is_success(entry["result"]) and
                           entry.get("counts_as_qualifying_shadow_day") is not False else None)
    stamp = entry["finished_utc"].replace(":", "").replace("-", "")
    with (state_dir / "ledger" / (stamp + "-" + entry["run_id"] + ".json")).open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, indent=2, ensure_ascii=False) + "\n")
    return entry


def run(desk, state_dir, target, lookback=6, cap=40, run_id="local", commit="unknown",
        adapter=None, target_source=SOURCE_EXPLICIT, historical_backfill=False):
    if desk not in DESKS or not 1 <= cap <= 40:
        raise ValueError("known desk and 1–40 cap required")
    if historical_backfill:
        # One narrowly bounded historical *content* import. This is NOT a
        # backdated shadow collecting day and does not relax other desks.
        if (desk != "japan_jcg" or target != date(2026, 10, 8) or
                lookback != 38 or cap != 5 or target_source != SOURCE_EXPLICIT):
            raise ValueError("JCG historical backfill requires exact Oct 8 cutoff, 38-day window and cap 5")
        root = state_dir.resolve()
        clock = root / "clock.json"
        db = root / "shadow.db"
        if not clock.is_file() or not db.is_file():
            raise ValueError("historical backfill cannot bootstrap shadow state")
        saved = json.loads(clock.read_text())
        if (saved.get("desk") != "japan_jcg" or
                saved.get("day_zero_run_id") != "37828199188-1"):
            raise ValueError("JCG historical backfill requires verified original Day 0 clock")
        ledgers = list((root / "ledger").glob("*.json"))
        if not any(json.loads(p.read_text()).get("run_id") == "37828199188-1"
                   for p in ledgers):
            raise ValueError("pinned original JCG Day 0 ledger is missing")
        if any(json.loads(p.read_text()).get("operation") == "jcg_2026_09_historical_backfill"
               for p in ledgers):
            raise ValueError("one-time JCG historical backfill already recorded")
    elif not 0 <= lookback <= 30:
        raise ValueError("ordinary shadow collections allow 0–30 lookback days")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", run_id):
        raise ValueError("unsafe run identifier")
    state_dir = state_dir.absolute()
    check_existing(state_dir, desk)
    state_dir.mkdir(parents=True, exist_ok=True)
    for directory in ("ledger", "captures"):
        (state_dir / directory).mkdir(exist_ok=True)
    db_path = state_dir / "shadow.db"
    name, cls, _ = DESKS[desk]
    config = load_manifest(REPO_ROOT / "shadow" / name / "manifest.json")
    source = config.sources[0]
    entry = {"desk": desk, "run_id": run_id, "collector_commit": commit,
             "collector_identity": USER_AGENT, "started_utc": datetime.now(timezone.utc).isoformat(),
             "target_date": target.isoformat(), "target_date_source": target_source,
             "window_start": (target - timedelta(days=lookback)).isoformat(),
             "lookback_days": lookback, "cap": cap, "robots_status": None,
             "listing_status": None, "listing_report": {}, "requests": [],
             "discovered": 0, "selected": 0, "retrieved": 0, "extracted": 0,
             "inserted": 0, "updated": 0, "duplicates": 0, "fetch_failures": 0,
             "extraction_failures": 0, "access_failures": 0, "failures": [],
             "state_sha256_before": sha(db_path), "result": None, "health": "fail"}
    if historical_backfill:
        entry["operation"] = "jcg_2026_09_historical_backfill"
        entry["counts_as_qualifying_shadow_day"] = False
        entry["backfill_anchor_day_zero_run_id"] = "37828199188-1"
    conn = None
    try:
        if not source.enabled:
            entry.update(result=st.SKIPPED_DISABLED, health="skipped")
        else:
            adapter = adapter or cls(source)
            discovery = adapter.discover(CollectionWindow(target, lookback))
            entry.update(robots_status=adapter.robots_status, listing_status=discovery.status,
                         listing_report=adapter.listing_report, discovered=len(discovery.references))
            if not discovery.ok:
                entry.update(result=discovery.status, error_detail=discovery.error_detail)
                entry["access_failures"] += discovery.status in (st.AUTH_FAILURE, st.ACCESS_CHALLENGED)
            elif len(discovery.references) > cap:
                entry.update(result=st.LISTING_FAILURE, error_detail="window exceeds cap; no bodies fetched",
                             deferred_urls=[r.url for r in discovery.references])
            else:
                documents = []
                entry["selected"] = len(discovery.references)
                for ref in discovery.references:
                    capture = adapter.fetch(ref)
                    if capture.status != st.OK:
                        key = ("access_failures" if capture.status in (st.AUTH_FAILURE, st.ACCESS_CHALLENGED)
                               else "extraction_failures" if capture.status == st.EXTRACTION_FAILURE
                               else "fetch_failures")
                        entry[key] += 1
                        entry["failures"].append({"url": ref.url, "stage": "fetch",
                                                  "status": capture.status, "detail": capture.error_detail})
                        if key == "access_failures":
                            break  # the institution refused this client; stop the run
                        continue
                    entry["retrieved"] += 1
                    result = adapter.extract(capture)
                    if result.status != st.OK or len(result.documents) != 1:
                        entry["extraction_failures"] += 1
                        entry["failures"].append({"url": ref.url, "stage": "extract",
                                                  "status": result.status, "detail": result.error_detail})
                    else:
                        documents.extend(result.documents)
                entry["extracted"] = len(documents)
                if entry["failures"]:
                    entry.update(result=entry["failures"][0]["status"],
                                 error_detail="incomplete batch; no corpus write")
                else:
                    conn = sqlite3.connect(str(db_path))
                    conn.executescript(SCHEMA)
                    if not conn.execute("SELECT desk FROM shadow_meta").fetchone():
                        conn.execute("INSERT INTO shadow_meta VALUES (?)", (desk,))
                    for doc in documents:
                        extra = doc.extra
                        previous = conn.execute("SELECT source_identity, url, title_original, text_original, published_date"
                                                " FROM shadow_records WHERE source_identity=? OR url=?",
                                                (extra["source_identity"], doc.url)).fetchall()
                        identity = (extra["source_identity"], doc.url, doc.title_original, doc.text_original, doc.published_date)
                        if previous:
                            if previous != [identity]:
                                raise ValueError("stored identity or original record changed; human disposition required")
                            entry["duplicates"] += 1
                        else:
                            conn.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                                extra["source_identity"], doc.url, doc.source_slug, doc.title_original,
                                doc.text_original, doc.published_date, doc.language_tag,
                                json.dumps(extra, ensure_ascii=False, sort_keys=True), extra["content_sha256"],
                                extra["capture_sha256"], run_id))
                            entry["inserted"] += 1
                    conn.commit()
                    entry["stored_total"] = conn.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0]
                    entry.update(result=st.OK if entry["inserted"] else st.OK_ALL_DUPLICATES
                                 if entry["duplicates"] else st.OK_NO_PUBLICATIONS, health="ok")
    except Exception as exc:
        if conn:
            conn.rollback()
        entry.update(result=st.ADAPTER_ERROR, inserted=0, error_detail=type(exc).__name__ + ": " + str(exc))
    finally:
        if conn:
            conn.close()
        for evidence in getattr(adapter, "evidence", []):
            payload = evidence["payload"]
            digest = hashlib.sha256(payload).hexdigest()
            if digest != evidence["capture_sha256"]:
                raise ValueError("transport evidence hash mismatch")
            path = state_dir / "captures" / (digest + ".bin")
            if path.exists():
                if sha(path) != digest:
                    raise ValueError("preserved capture was modified")
            else:
                with path.open("xb") as fh:
                    fh.write(payload)
            request = {k: v for k, v in evidence.items() if k not in ("payload", "headers")}
            request["content_type"] = evidence["headers"].get("content-type")
            request["payload_bytes"] = len(payload)
            entry["requests"].append(request)
    return finish(entry, state_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desk", required=True, choices=DESKS)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--target-date")
    parser.add_argument("--lookback-days", type=int, default=6)
    parser.add_argument("--cap", type=int, default=40)
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME"))
    parser.add_argument("--cron-utc")
    parser.add_argument("--run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    parser.add_argument("--jcg-september-backfill", action="store_true",
                        help="one-time owner-approved JCG historical content backfill only")
    args = parser.parse_args(argv)
    try:
        target, provenance = resolve_target_date(datetime.now(timezone.utc), args.event_name,
                                                args.cron_utc, args.target_date, args.run_attempt)
        if args.jcg_september_backfill and args.event_name != "workflow_dispatch":
            raise ValueError("JCG historical backfill requires explicit owner manual dispatch")
        entry = run(args.desk, args.state_dir, target, args.lookback_days, args.cap,
                    args.run_id, args.commit, target_source=provenance,
                    historical_backfill=args.jcg_september_backfill)
    except (ValueError, ScheduleError, sqlite3.Error) as exc:
        print("collection refused: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0 if entry["health"] in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
