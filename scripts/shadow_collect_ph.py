#!/usr/bin/env python3
"""
Philippines (Armed Forces of the Philippines) shadow collection run.

Reads `shadow/ph_afp/manifest.json`, collects into a shadow SQLite database
inside a state directory, and appends one ledger entry per run.

Isolation is the point. This script:

  * never opens `pla_watch.db` and never writes `output/`
  * writes only inside `--state-dir`, which must be OUTSIDE the repository
    working tree: a state file committed to `main` is exactly the leak the
    isolation exists to prevent
  * is not called by `pipeline.py` and is not scheduled by any workflow

What it preserves, per article:

  * `shadow_records`  the normalized record, first-seen and never overwritten
  * `captures`        the exact response bytes of the detail request, with the
                      requested URL, final URL, HTTP status, retrieval time and
                      SHA-256. A new capture row is written only when the
                      article's content fingerprint changes
  * `revisions`       one row per observed change, linking the two captures

Identity is the API's integer id (`afp:<id>`). A held id is a duplicate, not a
new record; a held id whose content fingerprint differs is a revision, not a
duplicate. Two DIFFERENT ids with the same title and date are two records
(the API really does hold such pairs) and are reported, not merged.

See `shadow/ph_afp/README.md` for what this source is and is not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                      # noqa: E402
from core.collection.contract import CollectionWindow          # noqa: E402
from core.shadow_schedule import (                            # noqa: E402
    SOURCE_EXPLICIT, ScheduleError, resolve_target_date)
from scraper.sources.ph_afp import (                           # noqa: E402
    REJECTION_REASONS, PHAfpAdapter)

MANIFEST = REPO_ROOT / "shadow" / "ph_afp" / "manifest.json"
# Deliberately no constant for the production database or output directory.
# This module has no reason to name either, and a path it never spells is a
# path it cannot accidentally open.

#: Consecutive unretrievable items after which the run stops asking. A source
#: that has gone dark is not helped by 1,000 more requests.
MAX_CONSECUTIVE_FAILURES = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_records (
    url                   TEXT PRIMARY KEY,
    source_identity       TEXT NOT NULL UNIQUE,
    source_slug           TEXT NOT NULL,
    title_original        TEXT NOT NULL,
    text_original         TEXT NOT NULL,
    text_status           TEXT NOT NULL,
    text_composition      TEXT NOT NULL,
    published_date        TEXT NOT NULL,
    published_at_utc      TEXT NOT NULL,
    published_at_original TEXT NOT NULL,
    byline                TEXT,
    category_slug         TEXT NOT NULL,
    api_created_at        TEXT,
    api_updated_at        TEXT,
    featured_image_path   TEXT,
    language_tag          TEXT NOT NULL,
    publication_kind      TEXT NOT NULL,
    content_sha256        TEXT NOT NULL,
    source_fingerprint    TEXT NOT NULL,
    capture_sha256        TEXT NOT NULL,
    retrieved_at          TEXT,
    first_seen_run        TEXT
);
CREATE INDEX IF NOT EXISTS idx_ph_shadow_published
    ON shadow_records(published_date);

CREATE TABLE IF NOT EXISTS captures (
    capture_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_identity    TEXT NOT NULL,
    run_id             TEXT,
    requested_url      TEXT NOT NULL,
    final_url          TEXT,
    http_status        INTEGER,
    content_type       TEXT,
    retrieved_at       TEXT,
    source_fingerprint TEXT NOT NULL,
    payload_sha256     TEXT NOT NULL,
    payload            BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ph_captures_identity
    ON captures(source_identity, capture_id);

CREATE TABLE IF NOT EXISTS revisions (
    revision_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source_identity   TEXT NOT NULL,
    run_id            TEXT,
    observed_utc      TEXT NOT NULL,
    prior_fingerprint TEXT NOT NULL,
    new_fingerprint   TEXT NOT NULL,
    prior_capture_id  INTEGER NOT NULL,
    new_capture_id    INTEGER NOT NULL
);
"""
# `source_identity` is UNIQUE as well as `url` being the primary key. Two
# different URLs claiming the same AFP article id is a collision the database
# refuses rather than a duplicate the corpus absorbs quietly.


class ShadowSource:
    """Minimal source object; the adapter only needs slug and enabled."""

    def __init__(self, cfg):
        self.slug = cfg["slug"]
        self.enabled = cfg.get("enabled", False)
        self.base_url = cfg.get("base_url")
        self.language_tag = (cfg.get("language_tags") or ["en"])[0]


def load_source():
    cfg = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return ShadowSource(cfg["sources"][0])


def assert_isolated(state_dir: Path) -> None:
    state_dir = state_dir.resolve()
    if REPO_ROOT in state_dir.parents or state_dir == REPO_ROOT:
        raise SystemExit(
            "refusing to write shadow state inside the repository working "
            "tree: %s\nShadow state belongs on its own state branch or "
            "directory, checked out elsewhere." % state_dir)


def file_sha256(path: Path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _store(conn, doc, capture, run_id: str, entry: dict) -> None:
    """
    Apply one extracted document to the shadow database: insert, duplicate or
    revision. Exactly one of the three, and never an overwrite.
    """
    x = doc.extra
    identity = x["source_identity"]
    payload = capture.body.encode("utf-8")
    held = conn.execute(
        "SELECT url FROM shadow_records WHERE source_identity = ?",
        (identity,)).fetchone()

    if held is None:
        clash = conn.execute(
            "SELECT source_identity FROM shadow_records WHERE url = ?",
            (doc.url,)).fetchone()
        if clash:
            # Same URL, different id: the slug now belongs to another article.
            # Neither record is altered and the collision is on the ledger.
            entry["identity_collisions"] += 1
            return
        conn.execute(
            "INSERT INTO shadow_records (url, source_identity, source_slug,"
            " title_original, text_original, text_status, text_composition,"
            " published_date, published_at_utc, published_at_original,"
            " byline, category_slug, api_created_at, api_updated_at,"
            " featured_image_path, language_tag, publication_kind,"
            " content_sha256, source_fingerprint, capture_sha256,"
            " retrieved_at, first_seen_run)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc.url, identity, doc.source_slug, doc.title_original,
             doc.text_original, x["text_status"], x["text_composition"],
             doc.published_date, x["published_at_utc"],
             x["published_at_original"], x.get("byline"), x["category_slug"],
             x.get("api_created_at"), x.get("api_updated_at"),
             x.get("featured_image_path"), doc.language_tag,
             x["publication_kind"], x["content_sha256"],
             x["source_fingerprint"], x["capture_sha256"],
             x.get("retrieved_at"), run_id))
        _insert_capture(conn, identity, run_id, capture, x)
        entry["inserted"] += 1
        if x["text_status"] == "no_text":
            entry["inserted_no_text"] += 1
        if x["text_status"] == "text":
            entry["content_hashes"].append(x["content_sha256"])
        return

    latest = conn.execute(
        "SELECT capture_id, source_fingerprint FROM captures"
        " WHERE source_identity = ? ORDER BY capture_id DESC LIMIT 1",
        (identity,)).fetchone()
    if latest and latest[1] == x["source_fingerprint"]:
        entry["duplicates"] += 1
        return

    # Same identity, different content: a revision. The first-seen record is
    # left exactly as it was; the new payload is preserved beside the old one.
    new_id = _insert_capture(conn, identity, run_id, capture, x)
    conn.execute(
        "INSERT INTO revisions (source_identity, run_id, observed_utc,"
        " prior_fingerprint, new_fingerprint, prior_capture_id,"
        " new_capture_id) VALUES (?,?,?,?,?,?,?)",
        (identity, run_id, _now(), latest[1] if latest else "",
         x["source_fingerprint"], latest[0] if latest else 0, new_id))
    entry["revisions"] += 1


def _insert_capture(conn, identity, run_id, capture, x) -> int:
    cur = conn.execute(
        "INSERT INTO captures (source_identity, run_id, requested_url,"
        " final_url, http_status, content_type, retrieved_at,"
        " source_fingerprint, payload_sha256, payload)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (identity, run_id, capture.requested_url, capture.final_url,
         capture.http_status, capture.content_type, capture.retrieved_at,
         x["source_fingerprint"], capture.payload_sha256,
         capture.body.encode("utf-8")))
    return cur.lastrowid


#: A held article is re-read (to detect a revision) only while it is this many
#: days old. Older held articles are not requested again: a full-history
#: catch-up, or a retry of a run that partly failed, must not re-fetch a
#: thousand articles the archive already holds.
REVISION_WATCH_DAYS = 14

#: Failures listed individually on the ledger; the count is always complete.
MAX_FAILURE_LOG = 50


def run(state_dir: Path, target: date, lookback: int, cap: int,
        run_id: str, commit: str, adapter=None,
        target_source: str = SOURCE_EXPLICIT,
        revision_days: int = REVISION_WATCH_DAYS) -> dict:
    assert_isolated(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "ledger").mkdir(exist_ok=True)
    db_path = state_dir / "shadow.db"

    before_hash = file_sha256(db_path)
    entry = {
        "run_id": run_id,
        "desk": "ph-afp",
        "collector_commit": commit,
        "started_utc": _now(),
        "target_date": target.isoformat(),
        "target_date_source": target_source,
        "lookback_days": lookback,
        "cap": cap,
        "robots_status": None,
        "listing_status": None,
        "discovered": 0, "selected": 0, "retrieved": 0,
        "inserted": 0, "inserted_no_text": 0, "duplicates": 0, "revisions": 0,
        "identity_collisions": 0,
        "skipped_held": 0,
        "revision_watch_days": revision_days,
        "failure_log": [],
        "fetch_failures": 0, "extraction_failures": 0,
        "access_failures": 0, "redirect_refusals": 0,
        "aborted": None,
        # Every item the listing offered and this run did not keep, by reason.
        "rejections": {r: 0 for r in REJECTION_REASONS},
        "rejected_total": 0,
        "observed": {},
        "content_hashes": [],
        "state_sha256_before": before_hash,
        "state_sha256_after": None,
        "result": None,
        "health": None,
        "error_detail": None,
    }

    src = load_source()
    adapter = adapter or PHAfpAdapter(src, cap=cap)
    window = CollectionWindow(target_date=target, lookback_days=lookback)

    discovery = adapter.discover(window)
    entry["listing_status"] = discovery.status
    entry["robots_status"] = (
        "disallowed" if discovery.status in (st.AUTH_FAILURE,
                                             st.ACCESS_CHALLENGED)
        else "allowed" if discovery.ok
        or discovery.status == st.OK_NO_PUBLICATIONS else "unknown")
    entry["discovered"] = len(discovery.references)
    entry["rejections"] = dict(getattr(adapter, "rejections",
                                       entry["rejections"]))
    entry["rejected_total"] = sum(entry["rejections"].values())
    entry["observed"] = dict(getattr(adapter, "observed", {}))

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

    watch_from = (target - timedelta(days=revision_days)).isoformat()
    consecutive = 0
    for ref in discovery.references:
        if (ref.hint_published_date or "") < watch_from and conn.execute(
                "SELECT 1 FROM shadow_records WHERE url = ?",
                (ref.url,)).fetchone():
            # Held, and too old to be watched for revision: not requested.
            entry["skipped_held"] += 1
            continue
        capture = adapter.fetch(ref)
        if capture.status in (st.AUTH_FAILURE, st.ACCESS_CHALLENGED):
            # A refusal is an answer. Stop asking.
            entry["access_failures"] += 1
            entry["aborted"] = "access_refused"
            break
        if capture.status == st.DISALLOWED_REDIRECT:
            entry["redirect_refusals"] += 1
            continue
        if not capture.ok:
            # A document that could not be retrieved is not a document that
            # failed to parse. Conflating them would hide a source going dark
            # behind a number that reads like a parser bug.
            entry["fetch_failures"] += 1
            if len(entry["failure_log"]) < MAX_FAILURE_LOG:
                entry["failure_log"].append({
                    "url": ref.url, "status": capture.status,
                    "http_status": capture.http_status,
                    "detail": capture.error_detail})
            consecutive += 1
            if consecutive >= MAX_CONSECUTIVE_FAILURES:
                entry["aborted"] = "consecutive_failures"
                break
            continue
        consecutive = 0
        entry["retrieved"] += 1
        result = adapter.extract(capture)
        if result.status != st.OK or not result.documents:
            entry["extraction_failures"] += 1
            if len(entry["failure_log"]) < MAX_FAILURE_LOG:
                entry["failure_log"].append({
                    "url": ref.url, "status": result.status,
                    "http_status": capture.http_status,
                    "detail": result.error_detail})
            continue
        for doc in result.documents:
            _store(conn, doc, capture, run_id, entry)
        conn.commit()
    conn.commit()

    entry["stored_total"] = conn.execute(
        "SELECT COUNT(*) FROM shadow_records").fetchone()[0]
    entry["stored_with_text"] = conn.execute(
        "SELECT COUNT(*) FROM shadow_records WHERE text_status = 'text'"
    ).fetchone()[0]
    rng = conn.execute("SELECT MIN(published_date), MAX(published_date) "
                       "FROM shadow_records").fetchone()
    entry["corpus_range"] = list(rng) if rng else [None, None]
    # Distinct ids that carry identical text. Reported, never merged: which
    # copy is canonical is an editorial decision, not a collection one.
    entry["content_hash_shared_groups"] = conn.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM shadow_records"
        " WHERE text_status = 'text' GROUP BY content_sha256"
        " HAVING COUNT(*) > 1)").fetchone()[0]
    conn.close()
    entry["observed"] = dict(getattr(adapter, "observed", {}))
    entry["rejections"] = dict(getattr(adapter, "rejections",
                                       entry["rejections"]))
    entry["rejected_total"] = sum(entry["rejections"].values())

    # Result taxonomy — honest distinctions, not one "success".
    kept = (entry["inserted"] or entry["duplicates"] or entry["revisions"]
            or entry["skipped_held"])
    if entry["aborted"] == "access_refused":
        entry.update(result=st.AUTH_FAILURE, health="fail",
                     error_detail="an item request was refused or challenged; "
                                  "the run stopped rather than ask again")
    elif entry["aborted"] == "consecutive_failures":
        entry.update(result=st.FETCH_FAILURE, health="fail",
                     error_detail="%d consecutive items could not be "
                                  "retrieved; the run stopped"
                                  % MAX_CONSECUTIVE_FAILURES)
    elif entry["redirect_refusals"] and not kept:
        entry.update(result=st.DISALLOWED_REDIRECT, health="fail",
                     error_detail="%d item(s) left the permitted host"
                                  % entry["redirect_refusals"])
    elif entry["fetch_failures"] and not kept:
        entry.update(result=st.FETCH_FAILURE, health="fail",
                     error_detail="%d selected item(s) could not be retrieved"
                                  % entry["fetch_failures"])
    elif entry["extraction_failures"] and not kept:
        entry.update(result=st.EXTRACTION_FAILURE, health="fail",
                     error_detail="every selected item failed extraction")
    elif entry["inserted"] or entry["revisions"]:
        entry.update(result=st.OK, health="ok")
    elif entry["duplicates"] or entry["skipped_held"]:
        entry.update(result=st.OK_ALL_DUPLICATES, health="ok")
    else:
        entry.update(result=st.OK_NO_PUBLICATIONS, health="ok")

    if entry["health"] == "ok" and (
            entry["fetch_failures"] or entry["extraction_failures"]
            or entry["identity_collisions"] or entry["redirect_refusals"]):
        # Some items were kept and some were not. Say so.
        entry["health"] = "partial"
        entry["error_detail"] = (
            "%d fetch failure(s), %d extraction failure(s), %d identity "
            "collision(s), %d redirect refusal(s) alongside kept items"
            % (entry["fetch_failures"], entry["extraction_failures"],
               entry["identity_collisions"], entry["redirect_refusals"]))
    return _finish(entry, state_dir, db_path)


def _finish(entry, state_dir: Path, db_path: Path) -> dict:
    entry["finished_utc"] = _now()
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
    ap.add_argument("--lookback-days", type=int, default=14,
                    help="items published within this many days of the target "
                         "date are fetched, and held items in it are re-read "
                         "to detect revisions. Use a large value for a "
                         "one-time full-history capture.")
    ap.add_argument("--revision-days", type=int, default=REVISION_WATCH_DAYS,
                    help="held articles this many days old or newer are "
                         "re-read to detect revisions; older held articles "
                         "are not requested again")
    ap.add_argument("--cap", type=int, default=100,
                    help="most items fetched in one run; 0 means no cap")
    ap.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    ap.add_argument("--commit", default=os.environ.get("GITHUB_SHA", "local"))
    ap.add_argument("--event-name",
                    default=os.environ.get("GITHUB_EVENT_NAME"),
                    help="the GitHub event that started this run. 'schedule' "
                         "resolves the logical date from --cron-utc; anything "
                         "else records the UTC date it actually ran on.")
    ap.add_argument("--cron-utc", default=None,
                    help="the workflow's cron time-of-day in UTC (HH:MM). "
                         "Required for a scheduled run.")
    ap.add_argument("--run-attempt",
                    default=os.environ.get("GITHUB_RUN_ATTEMPT") or "1",
                    help="GITHUB_RUN_ATTEMPT: 1 on a first attempt, higher on "
                         "a re-run. A re-run without --target-date is refused "
                         "rather than re-dated.")
    args = ap.parse_args(argv)

    try:
        target, target_source = resolve_target_date(
            datetime.now(timezone.utc), args.event_name, args.cron_utc,
            args.target_date, args.run_attempt)
    except ScheduleError as exc:
        print("collection refused: %s" % exc, file=sys.stderr)
        return 2
    entry = run(Path(args.state_dir), target, args.lookback_days, args.cap,
                args.run_id, args.commit, target_source=target_source,
                revision_days=args.revision_days)

    print(json.dumps({k: v for k, v in entry.items()
                      if k != "content_hashes"}, indent=1, sort_keys=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Philippines shadow run (AFP)\n\n")
            fh.write("Official AFP website articles only; not DND, not the "
                     "Coast Guard, not comprehensive. See "
                     "shadow/ph_afp/README.md.\n\n")
            fh.write("| field | value |\n|---|---|\n")
            for k in ("result", "health", "shadow_day", "discovered",
                      "selected", "retrieved", "inserted", "inserted_no_text",
                      "duplicates", "skipped_held", "revisions",
                      "rejected_total",
                      "fetch_failures", "extraction_failures",
                      "access_failures", "redirect_refusals", "aborted",
                      "stored_total", "robots_status"):
                fh.write("| %s | %s |\n" % (k, entry.get(k)))
    # A failing run must fail the job.
    return 0 if entry["health"] in ("ok", "partial") else 1


if __name__ == "__main__":
    raise SystemExit(main())
