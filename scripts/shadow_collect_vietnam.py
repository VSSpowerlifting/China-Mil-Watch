#!/usr/bin/env python3
"""Vietnam Desk isolated shadow runner; no production storage or rendering.

State belongs outside every collector checkout, on the orphan branch
shadow/vietnam. The workflow preserves failed attempts as artifacts and pushes
successful state only. Collector identity is the adapter's full identity.

What one successful run leaves in the state directory, all append-only:

  shadow.db             one row per publication (shadow_records), one per
                        distinct content of it (shadow_versions) and one per
                        run that fetched it (shadow_observations)
  captures/<sha>.bin    the exact bytes of robots.txt, the tag page and every
                        article fetched, named by SHA-256
  ledger/<stamp>-<run>  this run's evidence, opened exclusively, never rewritten
  clock.json            day zero, written once by the first successful run

A publication is identified by `vgp-en:<id>` and never by its title. Every
in-window item is re-fetched on every run, so a later edit of a title, lead or
body becomes a new version beside the old one; re-served pages whose only
changes are sidebars or the modification time are observations, not versions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st
from core.collection.contract import CollectionWindow
from core.collection.host_gate import HostGate
from core.collection.vietnam_sources import SOURCES as MINISTRY_SOURCES
from core.shadow_schedule import SOURCE_EXPLICIT, ScheduleError, resolve_target_date
from scraper.sources.vn_vgp import CONTENT_HASH_RULE, USER_AGENT, VNVgpAdapter

MANIFEST = REPO_ROOT / "shadow" / "vietnam" / "manifest.json"
DESK_ID = "vietnam"
#: Requests a run makes before any article: robots.txt and the one tag page.
FIXED_REQUESTS = 2
SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_records (
    source_identity TEXT PRIMARY KEY,
    source_slug TEXT NOT NULL,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    language_tag TEXT NOT NULL,
    published_date TEXT NOT NULL,
    published_at_original TEXT NOT NULL,
    published_at_utc TEXT,
    publication_kind TEXT NOT NULL,
    current_content_sha256 TEXT NOT NULL,
    version_count INTEGER NOT NULL,
    first_seen_run TEXT NOT NULL,
    last_seen_run TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shadow_versions (
    source_identity TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    content_hash_rule TEXT NOT NULL,
    title_original TEXT NOT NULL,
    lead_original TEXT NOT NULL,
    text_original TEXT NOT NULL,
    blocks_json TEXT NOT NULL,
    body_status TEXT NOT NULL,
    first_capture_sha256 TEXT NOT NULL,
    first_seen_run TEXT NOT NULL,
    PRIMARY KEY (source_identity, content_sha256)
);
CREATE TABLE IF NOT EXISTS shadow_observations (
    run_id TEXT NOT NULL,
    source_identity TEXT NOT NULL,
    requested_url TEXT NOT NULL,
    final_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    http_status INTEGER NOT NULL,
    content_type TEXT,
    payload_bytes INTEGER NOT NULL,
    capture_sha256 TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    outcome TEXT NOT NULL,
    published_at_original TEXT NOT NULL,
    published_at_utc TEXT,
    modified_at_original TEXT,
    modified_at_utc TEXT,
    visible_published TEXT,
    byline TEXT,
    byline_jsonld TEXT,
    publisher_jsonld TEXT,
    category TEXT,
    tags_json TEXT NOT NULL,
    listing_title TEXT,
    listing_local_time TEXT,
    media_count INTEGER NOT NULL,
    related_boxes_excluded INTEGER NOT NULL,
    anomalies_json TEXT NOT NULL,
    PRIMARY KEY (run_id, source_identity)
);
CREATE INDEX IF NOT EXISTS idx_vn_published ON shadow_records(published_date);
"""

MINISTRY_METADATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_metadata (
    run_id TEXT NOT NULL,
    source_identity TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (run_id, source_identity)
);
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
    if manifest["desk"]["desk_id"] != DESK_ID or len(manifest["sources"]) != 1:
        raise ValueError("the Vietnam shadow manifest must declare one vietnam source")
    return SimpleNamespace(**manifest["sources"][0])


def file_sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def assert_source_state(state_dir, source_slug):
    """An existing clock/corpus cannot be borrowed by another source."""
    ledgers = []
    for path in sorted((state_dir / "ledger").glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        if (row.get("desk_id"), row.get("source_slug")) != (DESK_ID, source_slug):
            raise ValueError("state ledger belongs to another desk/source")
        ledgers.append(row)
    clock_path = state_dir / "clock.json"
    if clock_path.exists():
        clock = json.loads(clock_path.read_text(encoding="utf-8"))
        if not any(e.get("run_id") == clock.get("day_zero_run_id")
                   and st.is_success(e.get("result", "")) for e in ledgers):
            raise ValueError("clock is not bound to this source's successful ledger")
    db = state_dir / "shadow.db"
    if db.exists():
        with sqlite3.connect(db.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
            if any(slug != source_slug for (slug,) in conn.execute(
                    "SELECT DISTINCT source_slug FROM shadow_records")):
                raise ValueError("database belongs to another source")


def host_gate(state_dir, gate_dir=None):
    directory = Path(gate_dir) if gate_dir is not None else (
        Path(tempfile.gettempdir()) / "ipr-vietnam-host-gate")
    assert_isolated(directory)
    gate = HostGate(directory)
    # A fresh checkout can seed a new machine's gate from preserved request
    # completions. The local shared directory also covers failed local runs.
    for path in sorted((state_dir / "ledger").glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        for request in entry.get("requests", []):
            ended = request.get("ended_utc")
            if ended:
                from urllib.parse import urlparse
                host = urlparse(request["url"]).hostname
                stamp = datetime.fromisoformat(ended)
                if stamp.tzinfo is None:
                    raise ValueError("previous request completion has no UTC offset")
                gate.seed(host, stamp.timestamp(), request.get("gate_interval_s", 2.0))
    return gate


def _store_capture(state_dir: Path, payload: bytes, sha: str) -> None:
    if hashlib.sha256(payload).hexdigest() != sha:
        raise ValueError("capture bytes disagree with transport hash")
    (state_dir / "captures").mkdir(exist_ok=True)
    path = state_dir / "captures" / (sha + ".bin")
    if path.exists():
        if file_sha256(path) != sha:
            raise ValueError("stored capture hash disagrees with its filename")
    else:
        path.write_bytes(payload)


def _finish(entry, state_dir, db_path, adapter=None):
    # Copied here, before the ledger is written, so that every exit path
    # (refusals included) keeps the requests it actually made.
    if adapter is not None:
        entry["requests"] = list(getattr(adapter, "request_log", []))
        if getattr(adapter, "source_anomalies", None):
            entry["source_anomalies"] = list(adapter.source_anomalies)
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
        fh.write(json.dumps(entry, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return entry


def _record(conn, run_id, capture, doc, entry) -> str:
    """Store one extracted document; returns the observation's outcome."""
    x = doc.extra
    if doc.source_slug != entry["source_slug"]:
        raise ValueError("extracted document belongs to another source")
    ident, digest = x["source_identity"], x["content_sha256"]
    anomalies = list(x["anomalies"])
    row = conn.execute(
        "SELECT url, current_content_sha256, published_at_original FROM shadow_records"
        " WHERE source_identity = ?", (ident,)).fetchone()
    known = conn.execute(
        "SELECT 1 FROM shadow_versions WHERE source_identity = ? AND content_sha256 = ?",
        (ident, digest)).fetchone()
    if row is None:
        outcome = "new"
    elif row[1] == digest:
        outcome = "unchanged"
    else:
        outcome = "reverted" if known else "changed"
    if row is not None and row[0] != doc.url:
        anomalies.append("url_changed: first stored %s, now %s" % (row[0], doc.url))
    if row is not None and row[2] != x["published_at_original"]:
        anomalies.append("published_time_changed: first stored %s, now %s"
                         % (row[2], x["published_at_original"]))
    if not known:
        conn.execute("INSERT INTO shadow_versions VALUES (?,?,?,?,?,?,?,?,?,?)", (
            ident, digest, x["content_hash_rule"], doc.title_original, x["lead_original"],
            doc.text_original, json.dumps(x["blocks"], ensure_ascii=False),
            x["body_status"], capture.payload_sha256, run_id))
    if row is None:
        conn.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            ident, doc.source_slug, doc.url, x["canonical_url"], doc.language_tag,
            doc.published_date, x["published_at_original"], x["published_at_utc"],
            x["publication_kind"], digest, 1, run_id, run_id))
    else:
        conn.execute(
            "UPDATE shadow_records SET current_content_sha256 = ?, last_seen_run = ?,"
            " version_count = (SELECT COUNT(*) FROM shadow_versions WHERE source_identity = ?)"
            " WHERE source_identity = ?", (digest, run_id, ident, ident))
    conn.execute(
        "INSERT INTO shadow_observations VALUES"
        " (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            run_id, ident, capture.requested_url, capture.final_url, x["canonical_url"],
            capture.http_status, capture.content_type, capture.payload_bytes,
            capture.payload_sha256, capture.retrieved_at, digest, outcome,
            x["published_at_original"], x["published_at_utc"], x["modified_at_original"],
            x["modified_at_utc"], x["visible_published"], x["byline"], x["byline_jsonld"],
            x["publisher_jsonld"], x["category"], json.dumps(x["tags"], ensure_ascii=False),
            x["listing_title"], x["listing_local_time"], x["media_count"],
            x["related_boxes_excluded"], json.dumps(anomalies, ensure_ascii=False)))
    if "source_metadata" in x:
        conn.execute("INSERT INTO shadow_metadata VALUES (?,?,?)", (
            run_id, ident, json.dumps(x["source_metadata"], ensure_ascii=False, sort_keys=True)))
    for anomaly in anomalies:
        entry["anomalies"].append({"source_identity": ident, "url": doc.url, "anomaly": anomaly})
    return outcome


def run(state_dir: Path, target: date, lookback: int, cap: int,
        run_id: str, commit: str, adapter=None, target_source=SOURCE_EXPLICIT,
        source=None, content_hash_rule=CONTENT_HASH_RULE, gate_dir=None):
    assert_isolated(state_dir)
    if lookback < 0 or cap < 1 or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", run_id):
        raise ValueError("non-negative lookback, positive cap and safe run id required")
    source = source or load_source()
    assert_source_state(state_dir, source.slug)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "ledger").mkdir(exist_ok=True)
    db_path = state_dir / "shadow.db"
    entry = {
        "run_id": run_id, "desk_id": DESK_ID, "collector_commit": commit,
        "collector_identity": USER_AGENT,
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target_date": target.isoformat(), "target_date_source": target_source,
        "window_start": (target - timedelta(days=lookback)).isoformat(),
        "lookback_days": lookback, "cap": cap, "request_ceiling": cap + FIXED_REQUESTS,
        "content_hash_rule": content_hash_rule,
        "source_slug": None, "robots_status": None, "listing_status": None,
        "listing_report": {}, "discovered": 0, "selected": 0, "retrieved": 0,
        "new_records": 0, "changed": 0, "reverted": 0, "unchanged": 0,
        "fetch_failures": 0, "extraction_failures": 0, "access_failures": 0,
        "challenged": 0, "failures": [], "anomalies": [], "captures": [], "requests": [],
        "stored_total": 0, "versions_total": 0,
        "state_sha256_before": file_sha256(db_path),
        "result": None, "health": None, "error_detail": None,
    }
    entry["source_slug"] = source.slug
    conn = None
    committed = False
    try:
        if source.enabled is not True:
            entry.update(result=st.SKIPPED_DISABLED, health="skipped")
            return _finish(entry, state_dir, db_path, adapter)
        adapter = adapter or VNVgpAdapter(source, max_requests=cap + FIXED_REQUESTS,
                                         gate=host_gate(state_dir, gate_dir))
        discovery = adapter.discover(CollectionWindow(target, lookback))
        entry.update(listing_status=discovery.status, robots_status=adapter.robots_status,
                     listing_report=adapter.listing_report,
                     discovered=len(discovery.references))
        for kept in adapter.evidence:
            _store_capture(state_dir, kept["payload"], kept["payload_sha256"])
            entry["captures"].append({k: v for k, v in kept.items() if k != "payload"})
        if not discovery.ok:
            entry.update(result=discovery.status, health="fail",
                         error_detail=discovery.error_detail,
                         failed_endpoints=discovery.failed_endpoints)
            entry["challenged"] += discovery.status == st.ACCESS_CHALLENGED
            entry["access_failures"] += discovery.status in (st.AUTH_FAILURE,
                                                            st.ACCESS_CHALLENGED)
            return _finish(entry, state_dir, db_path, adapter)
        # Never truncate a proven window into a sample. A window larger than
        # the cap is a failed run, with every candidate URL kept for recovery.
        if len(discovery.references) > cap:
            entry.update(result=st.LISTING_FAILURE, health="fail",
                         error_detail="proven window holds %d items, more than the cap of %d;"
                                      " nothing fetched" % (len(discovery.references), cap),
                         deferred_urls=[ref.url for ref in discovery.references])
            return _finish(entry, state_dir, db_path, adapter)
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA)
        if source.slug in MINISTRY_SOURCES:
            conn.executescript(MINISTRY_METADATA_SCHEMA)
        entry["selected"] = len(discovery.references)
        for position, ref in enumerate(discovery.references):
            capture = adapter.fetch(ref)
            if capture.status != st.OK:
                key = "access_failures" if capture.status in (
                    st.AUTH_FAILURE, st.ACCESS_CHALLENGED) else "fetch_failures"
                entry[key] += 1
                entry["challenged"] += capture.status == st.ACCESS_CHALLENGED
                entry["failures"].append({"url": ref.url, "stage": "fetch",
                                          "status": capture.status,
                                          "http_status": capture.http_status,
                                          "detail": capture.error_detail})
                # A challenge or a 401/403 is the host refusing this collector.
                # The rest of the window is named for recovery, never probed.
                if (capture.status == st.ACCESS_CHALLENGED or
                        capture.http_status in (401, 403, 429, 503) or
                        any(r.get("stop_host") for r in adapter.request_log)):
                    entry["deferred_urls"] = [r.url for r in discovery.references[position + 1:]]
                    break
                continue
            entry["retrieved"] += 1
            # The adapter accepts strict UTF-8 only, so this round trip
            # reproduces the exact response bytes; the hash is checked first.
            _store_capture(state_dir, capture.body.encode("utf-8"), capture.payload_sha256)
            entry["captures"].append({
                "role": "article", "url": capture.requested_url, "final_url": capture.final_url,
                "http_status": capture.http_status, "content_type": capture.content_type,
                "payload_bytes": capture.payload_bytes,
                "payload_sha256": capture.payload_sha256, "retrieved_at": capture.retrieved_at,
            })
            result = adapter.extract(capture)
            if result.status != st.OK or len(result.documents) != 1:
                entry["extraction_failures"] += 1
                entry["failures"].append({"url": ref.url, "stage": "extract",
                                          "status": result.status,
                                          "detail": result.error_detail})
                continue
            doc = result.documents[0]
            outcome = _record(conn, run_id, capture, doc, entry)
            entry["captures"][-1].update(source_identity=doc.extra["source_identity"],
                                         content_sha256=doc.extra["content_sha256"],
                                         outcome=outcome)
            entry[{"new": "new_records"}.get(outcome, outcome)] += 1
        conn.commit()
        committed = True
        entry["stored_total"] = conn.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0]
        entry["versions_total"] = conn.execute(
            "SELECT COUNT(*) FROM shadow_versions").fetchone()[0]
        entry["corpus_range"] = list(conn.execute(
            "SELECT MIN(published_date), MAX(published_date) FROM shadow_records").fetchone())
        if entry["access_failures"] or entry["fetch_failures"] or entry["extraction_failures"]:
            entry.update(result=(st.ACCESS_CHALLENGED if entry["challenged"] else
                                 st.AUTH_FAILURE if entry["access_failures"] else
                                 st.FETCH_FAILURE if entry["fetch_failures"] else
                                 st.EXTRACTION_FAILURE), health="fail",
                         error_detail="incomplete run; state must not be pushed")
        else:
            entry.update(result=(st.OK if entry["new_records"] or entry["changed"]
                                 or entry["reverted"] else
                                 st.OK_ALL_DUPLICATES if entry["unchanged"] else
                                 st.OK_NO_PUBLICATIONS), health="ok")
    except Exception as exc:
        if conn:
            conn.rollback()
            if not committed:
                for key in ("new_records", "changed", "reverted", "unchanged"):
                    entry[key] = 0
        entry.update(result=st.ADAPTER_ERROR, health="fail",
                     error_detail="%s: %s" % (type(exc).__name__, exc))
    finally:
        if conn:
            conn.close()
    return _finish(entry, state_dir, db_path, adapter)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--target-date", default=None)
    ap.add_argument("--lookback-days", type=int, default=6)
    ap.add_argument("--cap", type=int, default=40,
                    help="most articles one run may fetch; requests stay within cap + 2")
    ap.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    ap.add_argument("--commit", default="unknown")
    ap.add_argument("--gate-dir", default=None,
                    help="shared external host-gate directory; defaults to the system temp directory")
    ap.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME"))
    ap.add_argument("--cron-utc", default=None)
    ap.add_argument("--run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT") or "1")
    args = ap.parse_args(argv)
    try:
        target, source = resolve_target_date(datetime.now(timezone.utc), args.event_name,
                                             args.cron_utc, args.target_date, args.run_attempt)
        entry = run(Path(args.state_dir), target, args.lookback_days, args.cap,
                    args.run_id, args.commit, target_source=source, gate_dir=args.gate_dir)
    except (ScheduleError, ValueError) as exc:
        print("collection refused: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(entry, indent=1, sort_keys=True, ensure_ascii=False))
    return 0 if entry["health"] in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
