#!/usr/bin/env python3
"""
Singapore MINDEF shadow collection run.

Reads `shadow/singapore_mindef/manifest.json`, collects into a shadow SQLite
database inside a state directory, and appends one ledger entry per run.

Isolation is the point. This script:

  * never opens `pla_watch.db` and never writes `output/`
  * writes only inside `--state-dir`, which the workflow checks out from the
    `shadow/singapore-mindef` branch and pushes back
  * refuses to run if `--state-dir` is inside the repository working tree,
    because a state file committed to `main` would be exactly the leak the
    isolation exists to prevent

The day counter is derived from the ledger, never hard-coded: day 0 is the
first run whose result is terminal-successful, recorded once in `clock.json`
and never rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                      # noqa: E402
from core.shadow_schedule import (                            # noqa: E402
    SOURCE_EXPLICIT, ScheduleError, resolve_target_date)
from core.collection.contract import CollectionWindow          # noqa: E402
from scraper.sources.sg_mindef import SGMindefAdapter          # noqa: E402

MANIFEST = REPO_ROOT / "shadow" / "singapore_mindef" / "manifest.json"
# Deliberately no constant for the production database or output directory.
# This module has no reason to name either, and a path it never spells is a
# path it cannot accidentally open.

SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_records (
    url              TEXT PRIMARY KEY,
    source_slug      TEXT NOT NULL,
    title_original   TEXT NOT NULL,
    text_original    TEXT NOT NULL,
    published_date   TEXT NOT NULL,
    language_tag     TEXT NOT NULL,
    publication_kind TEXT NOT NULL,
    content_sha256   TEXT NOT NULL,
    capture_sha256   TEXT,
    retrieved_at     TEXT,
    first_seen_run   TEXT
);
CREATE INDEX IF NOT EXISTS idx_shadow_published ON shadow_records(published_date);
"""


class ShadowSource:
    """Minimal source object; the adapter only needs slug and enabled."""

    def __init__(self, cfg):
        self.slug = cfg["slug"]
        self.enabled = cfg.get("enabled", False)
        self.base_url = cfg.get("base_url")
        self.language_tag = cfg.get("language_tag", "en")


def load_source():
    cfg = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return ShadowSource(cfg["sources"][0])


def assert_isolated(state_dir: Path) -> None:
    state_dir = state_dir.resolve()
    if REPO_ROOT in state_dir.parents or state_dir == REPO_ROOT:
        raise SystemExit(
            "refusing to write shadow state inside the repository working "
            "tree: %s\nShadow state belongs on the shadow/singapore-mindef "
            "branch, checked out elsewhere." % state_dir)


def file_sha256(path: Path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(state_dir: Path, target: date, lookback: int, cap: int,
        run_id: str, commit: str, adapter=None,
        target_source: str = SOURCE_EXPLICIT) -> dict:
    assert_isolated(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "ledger").mkdir(exist_ok=True)
    db_path = state_dir / "shadow.db"

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    before_hash = file_sha256(db_path)

    entry = {
        "run_id": run_id,
        "collector_commit": commit,
        "started_utc": started,
        "target_date": target.isoformat(),
        "target_date_source": target_source,
        "lookback_days": lookback,
        "cap": cap,
        "robots_status": None,
        "listing_status": None,
        "discovered": 0, "selected": 0, "retrieved": 0,
        "inserted": 0, "duplicates": 0, "filtered": 0,
        "fetch_failures": 0, "extraction_failures": 0,
        "access_failures": 0,
        "content_hashes": [],
        "state_sha256_before": before_hash,
        "state_sha256_after": None,
        "result": None,
        "health": None,
        "error_detail": None,
    }

    src = load_source()
    adapter = adapter or SGMindefAdapter(src, cap=cap)
    window = CollectionWindow(target_date=target, lookback_days=lookback)

    discovery = adapter.discover(window)
    entry["listing_status"] = discovery.status
    entry["robots_status"] = ("disallowed" if discovery.status == st.AUTH_FAILURE
                              else "allowed" if discovery.ok
                              or discovery.status == st.OK_NO_PUBLICATIONS
                              else "unknown")
    entry["discovered"] = len(discovery.references)

    if discovery.status == st.AUTH_FAILURE:
        entry.update(result=st.AUTH_FAILURE, health="fail",
                     error_detail=discovery.error_detail)
        return _finish(entry, state_dir, db_path)
    if not discovery.ok and discovery.status != st.OK_NO_PUBLICATIONS:
        entry.update(result=discovery.status, health="fail",
                     error_detail=discovery.error_detail)
        return _finish(entry, state_dir, db_path)
    if discovery.status == st.OK_NO_PUBLICATIONS:
        entry.update(result=st.OK_NO_PUBLICATIONS, health="ok")
        return _finish(entry, state_dir, db_path)

    entry["selected"] = len(discovery.references)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)

    for ref in discovery.references:
        capture = adapter.fetch(ref)
        if capture.status == st.AUTH_FAILURE:
            entry["access_failures"] += 1
            continue
        if not capture.ok:
            # A document that could not be retrieved is not a document that
            # failed to parse. Conflating them would hide a source going dark
            # behind a number that reads like a parser bug.
            entry["fetch_failures"] += 1
            continue
        entry["retrieved"] += 1
        result = adapter.extract(capture)
        if result.status != st.OK or not result.documents:
            entry["extraction_failures"] += 1
            continue
        for doc in result.documents:
            row = conn.execute("SELECT 1 FROM shadow_records WHERE url = ?",
                               (doc.url,)).fetchone()
            if row:
                entry["duplicates"] += 1
                continue
            conn.execute(
                "INSERT INTO shadow_records (url, source_slug, title_original,"
                " text_original, published_date, language_tag,"
                " publication_kind, content_sha256, capture_sha256,"
                " retrieved_at, first_seen_run) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (doc.url, doc.source_slug, doc.title_original,
                 doc.text_original, doc.published_date, doc.language_tag,
                 doc.extra["publication_kind"], doc.extra["content_sha256"],
                 doc.extra.get("capture_sha256"), doc.extra.get("retrieved_at"),
                 run_id))
            entry["inserted"] += 1
            entry["content_hashes"].append(doc.extra["content_sha256"])
    conn.commit()
    entry["stored_total"] = conn.execute(
        "SELECT COUNT(*) FROM shadow_records").fetchone()[0]
    rng = conn.execute("SELECT MIN(published_date), MAX(published_date) "
                       "FROM shadow_records").fetchone()
    entry["corpus_range"] = list(rng) if rng else [None, None]
    conn.close()

    # Result taxonomy — honest distinctions, not one "success".
    if entry["access_failures"]:
        entry.update(result=st.AUTH_FAILURE, health="fail",
                     error_detail="%d item(s) returned HTTP 403"
                                  % entry["access_failures"])
    elif entry["fetch_failures"] and not entry["inserted"] \
            and not entry["duplicates"]:
        entry.update(result=st.FETCH_FAILURE, health="fail",
                     error_detail="%d selected item(s) could not be retrieved"
                                  % entry["fetch_failures"])
    elif entry["extraction_failures"] and not entry["inserted"] \
            and not entry["duplicates"]:
        entry.update(result=st.EXTRACTION_FAILURE, health="fail",
                     error_detail="every selected item failed extraction")
    elif entry["inserted"]:
        entry.update(result=st.OK, health="ok")
    elif entry["duplicates"]:
        entry.update(result=st.OK_ALL_DUPLICATES, health="ok")
    else:
        entry.update(result=st.OK_NO_PUBLICATIONS, health="ok")
    return _finish(entry, state_dir, db_path)


def _finish(entry, state_dir: Path, db_path: Path) -> dict:
    entry["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry["state_sha256_after"] = file_sha256(db_path)

    # Day 0 is the first terminal-successful run, written once.
    clock_path = state_dir / "clock.json"
    terminal_ok = entry["result"] in (st.OK, st.OK_NO_PUBLICATIONS,
                                      st.OK_ALL_DUPLICATES, st.OK_ALL_FILTERED)
    if terminal_ok:
        if clock_path.exists():
            clock = json.loads(clock_path.read_text(encoding="utf-8"))
        else:
            clock = {"day_zero_utc": entry["finished_utc"],
                     "day_zero_run_id": entry["run_id"]}
            clock_path.write_text(json.dumps(clock, indent=1) + "\n",
                                  encoding="utf-8")
        entry["day_zero_utc"] = clock["day_zero_utc"]
        d0 = datetime.fromisoformat(clock["day_zero_utc"])
        entry["shadow_day"] = (datetime.fromisoformat(entry["finished_utc"])
                               - d0).days
    else:
        # A failed run neither starts nor advances the clock.
        if clock_path.exists():
            clock = json.loads(clock_path.read_text(encoding="utf-8"))
            entry["day_zero_utc"] = clock["day_zero_utc"]
        entry["shadow_day"] = None

    name = "%s-%s.json" % (entry["finished_utc"].replace(":", "").replace("-", ""),
                           entry["run_id"])
    (state_dir / "ledger" / name).write_text(
        json.dumps(entry, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--target-date", default=None)
    ap.add_argument("--lookback-days", type=int, default=30)
    ap.add_argument("--cap", type=int, default=40)
    ap.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    ap.add_argument("--commit", default=os.environ.get("GITHUB_SHA", "local"))
    ap.add_argument("--event-name",
                    default=os.environ.get("GITHUB_EVENT_NAME"),
                    help="the GitHub event that started this run. 'schedule' "
                         "resolves the logical date from --cron-utc; anything "
                         "else records the UTC date it actually ran on.")
    ap.add_argument("--cron-utc", default=None,
                    help="the workflow's cron time-of-day in UTC (HH:MM). "
                         "Required for a scheduled run: a job started after "
                         "midnight belongs to the previous day's slot.")
    ap.add_argument("--run-attempt",
                    default=os.environ.get("GITHUB_RUN_ATTEMPT") or "1",
                    help="GITHUB_RUN_ATTEMPT: 1 on a first attempt, higher on "
                         "a re-run. A re-run without --target-date is refused "
                         "rather than re-dated. Local calls default to 1.")
    args = ap.parse_args(argv)

    # The logical collection date, not the execution date. See
    # core/shadow_schedule.py for why those are not the same thing.
    try:
        target, target_source = resolve_target_date(
            datetime.now(timezone.utc), args.event_name, args.cron_utc,
            args.target_date, args.run_attempt)
    except ScheduleError as exc:
        print("collection refused: %s" % exc, file=sys.stderr)
        return 2
    entry = run(Path(args.state_dir), target, args.lookback_days, args.cap,
                args.run_id, args.commit, target_source=target_source)

    print(json.dumps({k: v for k, v in entry.items()
                      if k != "content_hashes"}, indent=1, sort_keys=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Singapore shadow run\n\n")
            fh.write("| field | value |\n|---|---|\n")
            for k in ("result", "health", "shadow_day", "discovered",
                      "selected", "retrieved", "inserted", "duplicates",
                      "fetch_failures", "extraction_failures",
                      "access_failures",
                      "stored_total", "robots_status"):
                fh.write("| %s | %s |\n" % (k, entry.get(k)))
    # A failing run must fail the job.
    return 0 if entry["health"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
