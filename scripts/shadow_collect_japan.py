#!/usr/bin/env python3
"""
Japan MOD / Joint Staff shadow collection run.

Reads `shadow/jp_mod/manifest.json`, collects into a shadow SQLite database
inside a state directory, and appends one ledger entry per run.

Isolation is the point. This script:

  * never opens `pla_watch.db` and never writes `output/`
  * writes only inside `--state-dir`, which the workflow checks out from the
    `shadow/jp-mod` branch and pushes back
  * refuses to run if `--state-dir` is inside the repository working tree,
    because a state file committed to `main` would be exactly the leak the
    isolation exists to prevent

Why this is not `shadow_collect.py` with a different adapter
------------------------------------------------------------
Singapore's runner treats an access refusal as a failed run, and it is right to:
MINDEF serves every release to this collector, so a 403 there means something
broke.

Japan is not shaped like that. `www.mod.go.jp` serves XML and PDF but puts every
HTML document behind a bot-mitigation challenge, so a *normal* Japan run has
most of its discovered items challenged and a minority retrievable as PDF.
Reusing Singapore's taxonomy would mark every single Japan run `fail` forever —
an alarm that is always on, which is the same as no alarm — while the run was in
fact doing exactly what it was designed to do.

So a challenged item here is a **disclosed gap, not an outage**. It is counted,
named, and carried into the ledger, and the run is judged on whether the routes
that *are* open behaved. What would be a real failure is the feeds going down,
or the PDFs starting to be challenged too.

The day counter is derived from the ledger, never hard-coded: day 0 is the first
run whose result is terminal-successful, recorded once in `clock.json` and never
rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
from scraper.sources.jp_mod import (                            # noqa: E402
    JPModAdapter, partition_refs, publication_kind)

MANIFEST = REPO_ROOT / "shadow" / "jp_mod" / "manifest.json"
# Deliberately no constant for the production database or output directory.
# This module has no reason to name either, and a path it never spells is a
# path it cannot accidentally open.

SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_records (
    url              TEXT PRIMARY KEY,
    source_slug      TEXT NOT NULL,
    title_original   TEXT NOT NULL,
    text_original    TEXT NOT NULL,
    published_date   TEXT,
    language_tag     TEXT NOT NULL,
    publication_kind TEXT NOT NULL,
    content_sha256   TEXT NOT NULL,
    capture_sha256   TEXT,
    retrieved_at     TEXT,
    first_seen_run   TEXT
);
CREATE INDEX IF NOT EXISTS idx_shadow_published ON shadow_records(published_date);
CREATE INDEX IF NOT EXISTS idx_shadow_content   ON shadow_records(content_sha256);

-- Items discovered but never retrievable, kept so the gap is a visible row
-- rather than an absence. Without this table a reader comparing Japan's stored
-- count against the ministry's output would have no way to see the difference
-- between "not published" and "published but not served to us".
CREATE TABLE IF NOT EXISTS shadow_unretrieved (
    url            TEXT PRIMARY KEY,
    title_original TEXT,
    published_date TEXT,
    reason         TEXT NOT NULL,
    first_seen_run TEXT,
    last_seen_run  TEXT,
    seen_count     INTEGER NOT NULL DEFAULT 1
);

-- Feed entries published before collection began. Recorded by URL, title and
-- date so the history this collector did not witness is countable rather than
-- invisible. No body is ever fetched for these: recording that a document
-- exists is not the same as collecting it, and treating them as collected
-- would overstate the corpus by the whole of the ministry's back catalogue.
CREATE TABLE IF NOT EXISTS shadow_pre_bootstrap (
    url            TEXT PRIMARY KEY,
    source_slug    TEXT NOT NULL,
    title_original TEXT,
    published_date TEXT,
    first_seen_run TEXT,
    last_seen_run  TEXT,
    seen_count     INTEGER NOT NULL DEFAULT 1
);

-- HTTP validators, so the next run revalidates instead of re-downloading.
CREATE TABLE IF NOT EXISTS shadow_validators (
    url           TEXT PRIMARY KEY,
    etag          TEXT,
    last_modified TEXT,
    updated_run   TEXT
);
"""

TERMINAL_OK = (st.OK, st.OK_NO_PUBLICATIONS, st.OK_ALL_DUPLICATES,
               st.OK_ALL_FILTERED)


def assert_isolated(state_dir: Path) -> None:
    state_dir = state_dir.resolve()
    if REPO_ROOT in state_dir.parents or state_dir == REPO_ROOT:
        raise SystemExit(
            "refusing to write shadow state inside the repository working "
            "tree: %s\nShadow state belongs on the shadow/jp-mod branch, "
            "checked out elsewhere." % state_dir)


def file_sha256(path: Path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sources():
    """
    Every declared source that is actually collected, in manifest order.

    Sources marked `_not_collected` are declared so the Joint Staff and the
    English estate stay visible and distinguishable — neither is reachable, and
    neither has an adapter. Returning them here would start collecting things
    this project has said it cannot reach.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = []
    for spec in manifest["sources"]:
        if spec.get("_not_collected"):
            continue

        class Source:
            slug = spec["slug"]
            display_name = spec["display_name"]
            base_url = spec["base_url"]
            discovery_endpoints = tuple(spec["discovery_endpoints"])

        out.append(Source())
    return out


def establish_cutoff(state_dir: Path, now: datetime, run_id: str) -> dict:
    """
    The date on and after which this collector is responsible for the record.

    Written once, on the first run, and never rewritten. Everything the feeds
    carry from before it is the ministry's history from before this collector
    existed: recorded as such, never fetched, never counted as collected.

    A persisted cutoff is what makes the corpus claim checkable. A rolling
    `today - N days` window cannot be audited, because the set it admits
    changes every day and no reader can tell which items were ever eligible.
    """
    path = state_dir / "bootstrap.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    record = {
        "cutoff_utc": now.isoformat(timespec="seconds"),
        "cutoff_date": now.date().isoformat(),
        "established_run": run_id,
        "note": ("Collection begins here. Feed entries dated before this are "
                 "recorded as pre-bootstrap history and are never fetched."),
    }
    path.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")
    return record


def record_pre_bootstrap(conn, refs, adapter, slug, run_id) -> None:
    """Metadata only. Never a fetch, and never counted as a collected record."""
    titles = getattr(adapter, "_titles", {}) or {}
    for ref in refs:
        row = conn.execute(
            "SELECT seen_count FROM shadow_pre_bootstrap WHERE url = ?",
            (ref.url,)).fetchone()
        if row:
            conn.execute(
                "UPDATE shadow_pre_bootstrap SET last_seen_run = ?,"
                " seen_count = seen_count + 1 WHERE url = ?", (run_id, ref.url))
        else:
            conn.execute(
                "INSERT INTO shadow_pre_bootstrap (url, source_slug,"
                " title_original, published_date, first_seen_run, last_seen_run,"
                " seen_count) VALUES (?,?,?,?,?,?,1)",
                (ref.url, slug, titles.get(ref.url), ref.hint_published_date,
                 run_id, run_id))


def load_validators(conn) -> dict:
    return {
        row[0]: {"etag": row[1], "last_modified": row[2]}
        for row in conn.execute(
            "SELECT url, etag, last_modified FROM shadow_validators")
    }



def _collect_source(conn, adapter, window, run_id, entry, bucket,
                    cutoff_date, cap) -> None:
    """
    Collect one declared feed into the shared shadow database.

    Counters land in two places on purpose: `bucket`, so each feed can be read
    on its own, and `entry`, so the run still has one honest total. A reader who
    sees only the total cannot tell whether the press feed went dark while the
    site-update feed carried on as usual.
    """
    def count(name):
        bucket[name] += 1
        entry[name] += 1

    discovery = adapter.discover(window)
    bucket["listing_status"] = discovery.status
    # `discovered` is now everything the feed carried, not everything that
    # survived a filter. The difference between it and `selected` is the whole
    # point: a reader can see how much of the feed this run was responsible for.
    bucket["discovered"] = len(discovery.references)
    entry["discovered"] += len(discovery.references)
    if discovery.status == st.LISTING_FAILURE:
        return

    in_scope, pre_bootstrap, deferred, undated = partition_refs(
        discovery.references, cutoff_date, cap)
    record_pre_bootstrap(conn, pre_bootstrap, adapter, bucket["source_slug"],
                         run_id)
    for name, n in (("pre_bootstrap", len(pre_bootstrap)),
                    ("deferred", len(deferred)),
                    ("undated", len(undated)),
                    ("selected", len(in_scope))):
        bucket[name] = n
        entry[name] += n

    for ref in in_scope:
        # Every discovered item is tallied by URL family whether or not its body
        # can be read. That is what makes the site-update feed's breadth visible
        # instead of hidden: a budget page counts as a budget page, and nothing
        # is dropped for not looking like a press release.
        kind = publication_kind(ref.url)
        bucket["kinds"][kind] = bucket["kinds"].get(kind, 0) + 1

        capture = adapter.fetch(ref)

        if capture.status == st.ACCESS_CHALLENGED:
            count("challenged")
            entry["challenged_urls"].append(ref.url)
            _record_unretrieved(conn, ref, adapter, "access_challenged", run_id)
            continue
        if capture.status == st.OK_ALL_DUPLICATES:
            count("duplicates")          # 304: unchanged since the stored validator
            continue
        if capture.status != st.OK:
            count("fetch_failures")
            _record_unretrieved(conn, ref, adapter, capture.status, run_id)
            continue

        count("retrieved")
        result = adapter.extract(capture)
        if result.status != st.OK or not result.documents:
            count("extraction_failures")
            _record_unretrieved(conn, ref, adapter,
                                result.error_detail or result.status, run_id)
            continue

        for doc in result.documents:
            _store_validator(conn, doc, run_id)
            if conn.execute("SELECT 1 FROM shadow_records WHERE url = ?",
                            (doc.url,)).fetchone():
                count("duplicates")
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
            count("inserted")
            entry["content_hashes"].append(doc.extra["content_sha256"])


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
        "inserted": 0, "duplicates": 0,
        "fetch_failures": 0, "extraction_failures": 0,
        # Japan-specific and deliberately its own number: an item the edge
        # refused to serve is not an item that failed to parse, and neither is
        # an outage. Reported separately so coverage can say so out loud.
        "challenged": 0,
        "pre_bootstrap": 0, "deferred": 0, "undated": 0,
        "challenged_urls": [],
        "content_hashes": [],
        "state_sha256_before": before_hash,
        "state_sha256_after": None,
        "result": None,
        "health": None,
        "error_detail": None,
    }

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)

    window = CollectionWindow(target_date=target, lookback_days=lookback)
    entry["robots_status"] = "allowed"     # robots.txt permits every path used

    bootstrap = establish_cutoff(state_dir, datetime.now(timezone.utc), run_id)
    entry["bootstrap_cutoff_utc"] = bootstrap["cutoff_utc"]
    entry["bootstrap_cutoff_date"] = bootstrap["cutoff_date"]
    entry["bootstrap_established_run"] = bootstrap["established_run"]
    entry["is_bootstrap_run"] = bootstrap["established_run"] == run_id

    # Each declared feed is collected as its own source. They are objectively
    # different streams — news.xml is the press stream, update.xml reports any
    # page on the site — and collapsing them into one "releases" source is what
    # let the first manifest describe a budget table as an official release.
    if adapter is not None:
        pairs = [(getattr(adapter, "slug", "jp_mod_news_ja"), adapter)]
    else:
        validators = load_validators(conn)
        pairs = [(src.slug, JPModAdapter(src, cap=cap, validators=validators))
                 for src in load_sources()]

    entry["sources"] = []
    listing_statuses = []
    for slug, source_adapter in pairs:
        bucket = {"source_slug": slug, "discovered": 0, "selected": 0,
                  "retrieved": 0, "inserted": 0, "duplicates": 0,
                  "challenged": 0, "fetch_failures": 0,
                  "extraction_failures": 0, "pre_bootstrap": 0,
                  "deferred": 0, "undated": 0, "listing_status": None,
                  "kinds": {}}
        _collect_source(conn, source_adapter, window, run_id, entry, bucket,
                        bootstrap["cutoff_date"], cap)
        entry["sources"].append(bucket)
        listing_statuses.append(bucket["listing_status"])

    entry["listing_status"] = (
        st.LISTING_FAILURE
        if listing_statuses and all(x == st.LISTING_FAILURE for x in listing_statuses)
        else st.OK)

    # Commit before any early return. Pre-bootstrap history is written during
    # collection, and a run that discovers nothing new still has that history
    # to record — closing without committing rolled all of it back, so the
    # ledger said "288 pre-bootstrap" while the table held nothing.
    def _close_out(**update):
        entry["pre_bootstrap_total"] = conn.execute(
            "SELECT COUNT(*) FROM shadow_pre_bootstrap").fetchone()[0]
        conn.commit()
        conn.close()
        entry.update(**update)
        return _finish(entry, state_dir, db_path)

    if entry["listing_status"] == st.LISTING_FAILURE:
        return _close_out(result=st.LISTING_FAILURE, health="fail",
                          error_detail="no declared feed returned a usable "
                                       "listing")

    if entry["selected"] == 0:
        # Not "nothing published": the feeds carried plenty. Nothing was in
        # scope, which on the bootstrap run is the expected state and on any
        # later run means the ministry has published nothing since.
        return _close_out(
            result=st.OK_NO_PUBLICATIONS,
            health="ok",
            error_detail=("%d feed entries were discovered and all predate the "
                          "collection cutoff of %s; recorded as history, none "
                          "fetched" % (entry["pre_bootstrap"],
                                       entry["bootstrap_cutoff_date"]))
            if entry["pre_bootstrap"] else None)
    conn.commit()
    entry["stored_total"] = conn.execute(
        "SELECT COUNT(*) FROM shadow_records").fetchone()[0]
    entry["unretrieved_total"] = conn.execute(
        "SELECT COUNT(*) FROM shadow_unretrieved").fetchone()[0]
    entry["pre_bootstrap_total"] = conn.execute(
        "SELECT COUNT(*) FROM shadow_pre_bootstrap").fetchone()[0]
    rng = conn.execute("SELECT MIN(published_date), MAX(published_date) "
                       "FROM shadow_records").fetchone()
    entry["corpus_range"] = list(rng) if rng else [None, None]
    conn.close()

    # Result taxonomy. A challenged item is a disclosed gap, not a failed run —
    # see the module docstring. What fails a run is the open routes closing.
    if entry["fetch_failures"] and not entry["inserted"] \
            and not entry["duplicates"] and not entry["challenged"]:
        entry.update(result=st.FETCH_FAILURE, health="fail",
                     error_detail="%d selected item(s) could not be retrieved"
                                  % entry["fetch_failures"])
    elif entry["challenged"] and not entry["retrieved"] \
            and not entry["duplicates"]:
        # Everything the feed offered was refused. The feed still worked, so
        # this is not a listing failure, but it is not a healthy day either.
        entry.update(result=st.ACCESS_CHALLENGED, health="degraded",
                     error_detail="every selected item was challenged at the "
                                  "edge; no document was served")
    elif entry["extraction_failures"] and not entry["inserted"] \
            and not entry["duplicates"]:
        entry.update(result=st.EXTRACTION_FAILURE, health="fail",
                     error_detail="every retrieved item failed extraction")
    elif entry["inserted"]:
        entry.update(result=st.OK,
                     health="ok" if not entry["challenged"] else "partial")
    elif entry["duplicates"]:
        entry.update(result=st.OK_ALL_DUPLICATES,
                     health="ok" if not entry["challenged"] else "partial")
    else:
        entry.update(result=st.OK_NO_PUBLICATIONS, health="ok")

    if entry["challenged"] and entry.get("error_detail") is None:
        entry["error_detail"] = (
            "%d of %d selected item(s) are HTML and are served behind an edge "
            "challenge; recorded, not fetched"
            % (entry["challenged"], entry["selected"]))
    return _finish(entry, state_dir, db_path)


def _record_unretrieved(conn, ref, adapter, reason, run_id) -> None:
    title = (getattr(adapter, "_titles", {}) or {}).get(ref.url)
    row = conn.execute("SELECT seen_count FROM shadow_unretrieved WHERE url = ?",
                       (ref.url,)).fetchone()
    if row:
        conn.execute(
            "UPDATE shadow_unretrieved SET last_seen_run = ?, reason = ?,"
            " seen_count = seen_count + 1 WHERE url = ?",
            (run_id, reason, ref.url))
    else:
        conn.execute(
            "INSERT INTO shadow_unretrieved (url, title_original,"
            " published_date, reason, first_seen_run, last_seen_run, seen_count)"
            " VALUES (?,?,?,?,?,?,1)",
            (ref.url, title, ref.hint_published_date, reason, run_id, run_id))


def _store_validator(conn, doc, run_id) -> None:
    etag = doc.extra.get("etag")
    last_modified = doc.extra.get("last_modified")
    if not etag and not last_modified:
        return
    conn.execute(
        "INSERT INTO shadow_validators (url, etag, last_modified, updated_run)"
        " VALUES (?,?,?,?) ON CONFLICT(url) DO UPDATE SET"
        " etag = excluded.etag, last_modified = excluded.last_modified,"
        " updated_run = excluded.updated_run",
        (doc.url, etag, last_modified, run_id))


def _finish(entry, state_dir: Path, db_path: Path) -> dict:
    entry["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry["state_sha256_after"] = file_sha256(db_path)

    clock_path = state_dir / "clock.json"
    if entry["result"] in TERMINAL_OK:
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
    ap.add_argument("--lookback-days", type=int, default=14)
    ap.add_argument("--cap", type=int, default=40)
    ap.add_argument("--run-id", default="local")
    ap.add_argument("--commit", default="unknown")
    ap.add_argument("--event-name",
                    default=os.environ.get("GITHUB_EVENT_NAME"),
                    help="the GitHub event that started this run. 'schedule' "
                         "resolves the logical date from --cron-utc; anything "
                         "else records the UTC date it actually ran on.")
    ap.add_argument("--cron-utc", default=None,
                    help="the workflow's cron time-of-day in UTC (HH:MM). "
                         "Required for a scheduled run: a job started after "
                         "midnight belongs to the previous day's slot.")
    args = ap.parse_args(argv)

    # The logical collection date, not the execution date. Japan's cron sits at
    # 22:40 UTC — eighty minutes from midnight — so it is more exposed to this
    # than Singapore, not less. See core/shadow_schedule.py.
    try:
        target, target_source = resolve_target_date(
            datetime.now(timezone.utc), args.event_name, args.cron_utc,
            args.target_date)
    except ScheduleError as exc:
        print("collection refused: %s" % exc, file=sys.stderr)
        return 2
    entry = run(Path(args.state_dir), target, args.lookback_days, args.cap,
                args.run_id, args.commit, target_source=target_source)

    print("result     : %s (%s)" % (entry["result"], entry["health"]))
    print("discovered : %d, selected %d" % (entry["discovered"], entry["selected"]))
    print("retrieved  : %d  inserted %d  duplicates %d"
          % (entry["retrieved"], entry["inserted"], entry["duplicates"]))
    print("challenged : %d  fetch-fail %d  extract-fail %d"
          % (entry["challenged"], entry["fetch_failures"],
             entry["extraction_failures"]))
    print("bootstrap  : cutoff %s (established by run %s)%s"
          % (entry["bootstrap_cutoff_date"], entry["bootstrap_established_run"],
             "  <- this run" if entry["is_bootstrap_run"] else ""))
    print("pre-boot   : %d feed entries predate the cutoff (recorded, never "
          "fetched); %d deferred to a later run; %d undated"
          % (entry["pre_bootstrap"], entry["deferred"], entry["undated"]))
    if entry.get("error_detail"):
        print("detail     : %s" % entry["error_detail"])
    return 0 if entry["result"] in TERMINAL_OK or entry["challenged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
