#!/usr/bin/env python3
"""
Vietnam shadow state review kit — read-only.

Builds the evidence packet for a Day 7 / 14 / 30 checkpoint of the Vietnam
shadow pilot: the English `defense` tag of Viet Nam Government News, a Tier B
government newsroom, collected by scripts/shadow_collect_vietnam.py onto the
orphan branch `shadow/vietnam`. The checkpoint is a person reading every stored
record against the live page. Nothing here substitutes for that, and nothing
here promotes the desk.

Provenance
----------
A formal packet is derived from `--state-commit` in `--state-repo`. The commit
must be reachable from `shadow/vietnam` (or `--state-ref`), and `state/` is
exported from its own tree with `git cat-file`. That tree may hold only
`clock.json`, `shadow.db`, `ledger/<stamp>-<run>.json` and
`captures/<sha256>.bin`, as regular files; every ledger must name this desk and
source. Anything else is unrelated state and is refused, not skipped.
`--state-dir` reads an ordinary directory as a rehearsal and says so.

Boundaries
----------
This is not scripts/review_shadow_state.py and does not redirect it: that kit
and its publisher are bound to Singapore by constants. The Git provenance
plumbing is imported from it because none of it is desk-specific (every desk
value is a parameter); every Vietnam rule — identity, dates, content hashing,
window coverage, late listing — is stated here. The adapter is not imported
(it pulls in requests and bs4); what this kit needs from it is re-declared
below and pinned to it by tests/test_vietnam_shadow_review.py.

There is no Vietnam review publisher and no Vietnam review branch.
`--check-signoff` checks a filled sign-off against its packet; preserving it is
a separate, owner-approved step.

Determinism
-----------
The same commit with the same `--as-of` produces byte-identical packet files.
Wall-clock time and local paths go to generation_context.json, which is not
part of the packet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                       # noqa: E402
from core.collection.vietnam_identity import USER_AGENT        # noqa: E402
# Desk-agnostic Git provenance, shared rather than copied.
from scripts.review_shadow_state import (                      # noqa: E402
    ReviewError, _git_bytes, resolve_state_repo, verify_state_commit)

TOOL_VERSION = "1.0.0"
QUEUE_ALGORITHM = "vietnam-complete-corpus/1"
SIGNOFF_SCHEMA = "vietnam-review-signoff/1"
DESK_IDENTITY = "vietnam"
STATE_BRANCH = "shadow/vietnam"
STATE_PREFIX = "state"
SOURCE_SLUG = "vn_vgp_defense_en"
CHECKPOINTS = {"day-07": 7, "day-14": 14, "day-30": 30}
#: Necessary for an owner to CONSIDER the desk, never sufficient.
REQUIRED_COLLECTING_DAYS = 30

FRAMING = (
    "Viet Nam Government News (English), the 'defense' tag only: a Tier B "
    "government newsroom, not the Ministry of National Defence and not the "
    "People's Army Newspaper. A tag is applied by editors, so what it omits is "
    "not observable here. English as published; nothing is translated. The "
    "public Vietnam Desk is not collecting, and no packet or review promotes it.")

#: Explicit booleans only; "yes" is not an answer a program can check.
CHECK_FIELDS = (
    "source_page_opened", "title_matches", "publication_date_matches",
    "canonical_url_matches", "body_appears_complete", "kind_is_reasonable",
    "attribution_matches", "no_denial_or_template_stored",
)
CHECK_LABELS = (
    "Source page opened", "Title matches the page",
    "Publication date matches the page", "Canonical URL is correct",
    "Stored body is the complete published English text",
    "Kind (newsroom report) is reasonable",
    "Byline and publisher stored as published; no author or issuer invented",
    "No access-denial or template text stored",
)
VERDICTS = ("pass", "pass_with_findings", "fail")

TERMINAL_OK = frozenset({st.OK, st.OK_NO_PUBLICATIONS, st.OK_ALL_DUPLICATES,
                         st.OK_ALL_FILTERED})
OUTCOMES = ("new", "unchanged", "changed", "reverted")
#: Mirrors core/shadow_schedule.SOURCES. Vietnam ledgers always carry it.
TARGET_DATE_SOURCES = ("explicit", "schedule-slot", "manual-utc-date")

#: Every key scripts/shadow_collect_vietnam.py writes on every exit path.
LEDGER_REQUIRED = (
    "run_id", "desk_id", "collector_commit", "collector_identity", "started_utc",
    "finished_utc", "target_date", "target_date_source", "window_start",
    "lookback_days", "cap", "request_ceiling", "content_hash_rule", "source_slug",
    "robots_status", "listing_status", "listing_report", "discovered", "selected",
    "retrieved", "new_records", "changed", "reverted", "unchanged",
    "fetch_failures", "extraction_failures", "access_failures", "challenged",
    "failures", "anomalies", "captures", "requests", "stored_total",
    "versions_total", "state_sha256_before", "state_sha256_after", "result",
    "health", "error_detail", "shadow_day",
)
#: Exactly the tables and columns the runner creates. Another shape is refused.
EXPECTED_COLUMNS = {
    "shadow_records": (
        "source_identity", "source_slug", "url", "canonical_url", "language_tag",
        "published_date", "published_at_original", "published_at_utc",
        "publication_kind", "current_content_sha256", "version_count",
        "first_seen_run", "last_seen_run"),
    "shadow_versions": (
        "source_identity", "content_sha256", "content_hash_rule", "title_original",
        "lead_original", "text_original", "blocks_json", "body_status",
        "first_capture_sha256", "first_seen_run"),
    "shadow_observations": (
        "run_id", "source_identity", "requested_url", "final_url", "canonical_url",
        "http_status", "content_type", "payload_bytes", "capture_sha256",
        "retrieved_at", "content_sha256", "outcome", "published_at_original",
        "published_at_utc", "modified_at_original", "modified_at_utc",
        "visible_published", "byline", "byline_jsonld", "publisher_jsonld",
        "category", "tags_json", "listing_title", "listing_local_time",
        "media_count", "related_boxes_excluded", "anomalies_json"),
}

# ── mirrored from scraper/sources/vn_vgp.py; equality is tested ─────────────
HOSTNAME = "en.baochinhphu.vn"
LISTING = "https://en.baochinhphu.vn/defense.html"
IDENTITY_PREFIX = "vgp-en:"
ARTICLE_PATH_RE = re.compile(r"^/(?:[a-z0-9]+-)+?(\d+)\.htm$")
CONTENT_HASH_RULE = "vgp-en-content-v1"
PUBLICATION_KIND = "newsroom report"
BODY_STATUSES = ("text", "media_only")
#: The tag page's wall clock: Ha Noi, UTC+07:00, the manifest's time zone.
HANOI = timezone(timedelta(hours=7))

#: Text meaning a refusal page was stored instead of an article. A flag for a
#: person, never a judgement by length: genuine short prose is legitimate.
STUB_MARKERS = (
    "access denied", "403 forbidden", "404 not found", "page not found",
    "just a moment", "attention required", "enable javascript",
    "checking your browser", "service unavailable",
)

LEDGER_NAME = re.compile(r"^ledger/\d{8}T\d{6}\+0000-[A-Za-z0-9_.-]{1,128}\.json$")
CAPTURE_NAME = re.compile(r"^captures/([0-9a-f]{64})\.bin$")
STATE_FILES = ("clock.json", "shadow.db")


def article_id(url):
    try:
        parts = urlparse(url or "")
    except ValueError:
        return None
    if (parts.scheme, parts.netloc) != ("https", HOSTNAME):
        return None
    if parts.query or parts.fragment or parts.params:
        return None
    match = ARTICLE_PATH_RE.match(parts.path)
    return match.group(1) if match else None


def content_sha256(title, lead, blocks):
    payload = json.dumps({"rule": CONTENT_HASH_RULE, "title": title, "lead": lead,
                          "blocks": [[k, t] for k, t in blocks]},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assembled_text(lead, blocks):
    return "\n".join(([lead] if lead else []) + [t for _, t in blocks])


def stamp_facts(raw):
    """(date in the stamp's own offset, UTC instant or None), or None."""
    try:
        dt = datetime.fromisoformat((raw or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.date().isoformat(), None
    return dt.date().isoformat(), dt.astimezone(timezone.utc).isoformat(timespec="seconds")


# ── the state tree ──────────────────────────────────────────────────────────

def check_tree(names) -> None:
    """The Vietnam state contract. Anything else is unrelated state."""
    missing = [f for f in STATE_FILES if f not in names]
    if missing:
        raise ReviewError(
            "the state tree has no %s: no successful run has started the shadow "
            "clock, so there is nothing to review" % ", ".join(missing))
    unexpected = sorted(n for n in names if n not in STATE_FILES
                        and not LEDGER_NAME.match(n) and not CAPTURE_NAME.match(n))
    if unexpected:
        raise ReviewError(
            "the state tree carries file(s) the Vietnam runner never writes: %s. "
            "Unrelated state is refused rather than skipped." % ", ".join(unexpected))
    if not any(LEDGER_NAME.match(n) for n in names):
        raise ReviewError("the state tree holds no ledger")


def export_state_tree(state_repo: Path, state_commit: str, dest: Path) -> Path:
    """`state/` from the commit's own objects; regular files only."""
    listing = _git_bytes(["ls-tree", "-r", "-z", "--full-tree", "--long",
                          "%s:%s" % (state_commit, STATE_PREFIX)], state_repo)
    entries = []
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        meta, _, name = raw.partition(b"\t")
        mode, kind, oid, _size = meta.decode("utf-8").split(None, 3)
        name = name.decode("utf-8")
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ReviewError("%s/%s is a %s with mode %s; a state tree carries regular "
                              "files only" % (STATE_PREFIX, name, kind, mode))
        entries.append((name, oid))
    check_tree([name for name, _ in entries])
    for name, oid in entries:
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(_git_bytes(["cat-file", "blob", oid], state_repo))
    return dest


def assert_safe_state_dir(state_dir: Path) -> None:
    resolved = state_dir.resolve()
    if not resolved.is_dir():
        raise ReviewError("state dir does not exist: %s" % resolved)
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise ReviewError("refusing a state dir inside the repository: %s" % resolved)
    for forbidden in ("pla_watch.db", "output"):
        if (resolved / forbidden).exists():
            raise ReviewError("refusing a state dir that contains %s: that is "
                              "production, not shadow state" % forbidden)
    files = [p for p in resolved.rglob("*") if p.is_symlink() or p.is_file()]
    if any(p.is_symlink() for p in files):
        raise ReviewError("refusing a state dir that contains a symlink")
    check_tree([p.relative_to(resolved).as_posix() for p in files])


def assert_safe_out_dir(out_dir: Path, allow_tracked: bool) -> None:
    resolved = out_dir.resolve()
    if not allow_tracked and (resolved == REPO_ROOT or REPO_ROOT in resolved.parents):
        raise ReviewError("refusing to write a review packet inside the repository: %s"
                          % resolved)


def hash_inputs(state_dir: Path) -> dict:
    return {p.relative_to(state_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(state_dir.rglob("*")) if p.is_file()}


def open_readonly(db_path: Path) -> sqlite3.Connection:
    """Immutable: no lock, no journal, and no sidecar can appear."""
    return sqlite3.connect("file://%s?mode=ro&immutable=1" % db_path.resolve(), uri=True)


LEDGER_TYPES = {
    str: ("run_id", "desk_id", "collector_commit", "collector_identity", "started_utc",
          "finished_utc", "target_date", "window_start", "content_hash_rule", "source_slug",
          "result", "health"),
    int: ("lookback_days", "cap", "request_ceiling", "discovered", "selected", "retrieved",
          "new_records", "changed", "reverted", "unchanged", "fetch_failures",
          "extraction_failures", "access_failures", "challenged", "stored_total",
          "versions_total"),
    list: ("failures", "anomalies", "captures", "requests"),
    dict: ("listing_report",),
}


def load_ledgers(state_dir: Path) -> list:
    """Every ledger, in committed (filename) order. A malformed one is refused."""
    entries = []
    for path in sorted((state_dir / "ledger").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ReviewError("ledger %s is not valid JSON: %s" % (path.name, exc))
        missing = [f for f in LEDGER_REQUIRED if not isinstance(data, dict) or f not in data]
        if missing:
            raise ReviewError("ledger %s lacks %s: not a Vietnam shadow ledger, and "
                              "unrelated state is refused" % (path.name, ", ".join(missing)))
        if (data["desk_id"], data["source_slug"]) != (DESK_IDENTITY, SOURCE_SLUG):
            raise ReviewError("ledger %s belongs to desk %r and source %r: unrelated "
                              "state is refused" % (path.name, data["desk_id"],
                                                    data["source_slug"]))
        wrong = [f for kind, fields in LEDGER_TYPES.items() for f in fields
                 if not isinstance(data[f], kind)]
        wrong += [f for f in ("shadow_day",) if not isinstance(data[f], (int, type(None)))]
        wrong += [f for f in ("state_sha256_before", "state_sha256_after")
                  if not isinstance(data[f], (str, type(None)))]
        try:
            for f in ("started_utc", "finished_utc"):
                if datetime.fromisoformat(data[f]).utcoffset() is None:
                    wrong.append(f)
            date.fromisoformat(data["target_date"])
            date.fromisoformat(data["window_start"])
        except (TypeError, ValueError):
            wrong.append("dates")
        if wrong:
            raise ReviewError("ledger %s has malformed %s; the Vietnam runner never "
                              "writes that" % (path.name, ", ".join(sorted(set(wrong)))))
        if data["target_date_source"] not in TARGET_DATE_SOURCES:
            raise ReviewError("ledger %s names target_date_source %r, which no rule in "
                              "this repository produces" % (path.name,
                                                            data["target_date_source"]))
        data["_filename"] = path.name
        entries.append(data)
    return entries


# ── checks ──────────────────────────────────────────────────────────────────

def expected_result(e):
    """The runner's own decision tree, for runs that reached storage."""
    if "corpus_range" not in e:
        return None
    if e["access_failures"] or e["fetch_failures"] or e["extraction_failures"]:
        return (st.ACCESS_CHALLENGED if e["challenged"] else
                st.AUTH_FAILURE if e["access_failures"] else
                st.FETCH_FAILURE if e["fetch_failures"] else st.EXTRACTION_FAILURE)
    if e["new_records"] or e["changed"] or e["reverted"]:
        return st.OK
    return st.OK_ALL_DUPLICATES if e["unchanged"] else st.OK_NO_PUBLICATIONS


def _days(start: date, end: date):
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def _ranges(days):
    """Sorted dates as [first, last] runs of consecutive dates."""
    out = []
    for d in sorted(days):
        if out and (d - out[-1][1]).days == 1:
            out[-1][1] = d
        else:
            out.append([d, d])
    return [[a.isoformat(), b.isoformat()] for a, b in out]


def validate_runs(state_dir: Path, ledgers: list, db_sha: str,
                  content_hash_rule: str = CONTENT_HASH_RULE) -> tuple:
    """Clock, ledger identity, results, chain, continuity and window coverage."""
    a, facts = [], {}
    try:
        clock = json.loads((state_dir / "clock.json").read_text(encoding="utf-8"))
        day_zero = datetime.fromisoformat(clock["day_zero_utc"])
        clock["day_zero_run_id"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ReviewError("clock.json is unreadable: %s" % exc)
    facts["clock"] = clock
    successes = [e for e in ledgers if e["result"] in TERMINAL_OK]
    if not successes:
        a.append("clock.json exists but no ledger records a successful run")
    elif (str(successes[0]["run_id"]), successes[0]["finished_utc"]) != (
            str(clock["day_zero_run_id"]), clock["day_zero_utc"]):
        a.append("the clock names run %s at %s, but the first successful run is %s at %s"
                 % (clock["day_zero_run_id"], clock["day_zero_utc"],
                    successes[0]["run_id"], successes[0]["finished_utc"]))

    seen, prev_finished, prev_after = {}, None, None
    for e in ledgers:
        name, rid = e["_filename"], str(e["run_id"])
        want_name = "%s-%s.json" % (e["finished_utc"].replace(":", "").replace("-", ""), rid)
        if name != want_name:
            a.append("ledger %s does not match its contents (expected %s)" % (name, want_name))
        if rid in seen:
            a.append("run id %s appears in %s and %s" % (rid, seen[rid], name))
        seen[rid] = name
        if e["result"] not in st.ALL_STATUSES:
            a.append("%s: unrecognised result %r" % (name, e["result"]))
        want_health = ("ok" if e["result"] in TERMINAL_OK else
                       "skipped" if e["result"] == st.SKIPPED_DISABLED else "fail")
        if e["health"] != want_health:
            a.append("%s: health %r disagrees with result %r" % (name, e["health"], e["result"]))
        if e["health"] == "fail":
            # Never pushed by the workflow; present only in a rehearsal or by hand.
            a.append("%s: run %s did not succeed: %s (%s)"
                     % (name, rid, e["result"], e["error_detail"]))
        want = expected_result(e)
        if want is not None and want != e["result"]:
            a.append("%s: counts imply %r but the ledger records %r" % (name, want, e["result"]))
        if e["collector_identity"] != USER_AGENT:
            a.append("%s: collector identity %r is not the declared one"
                     % (name, e["collector_identity"]))
        if e["content_hash_rule"] != content_hash_rule:
            a.append("%s: content hash rule %r is not %s" % (name, e["content_hash_rule"],
                                                             content_hash_rule))
        if e["request_ceiling"] != e["cap"] + 2 or len(e["requests"]) > e["request_ceiling"]:
            a.append("%s: %d request(s) against a ceiling of %r for cap %r"
                     % (name, len(e["requests"]), e["request_ceiling"], e["cap"]))
        target = date.fromisoformat(e["target_date"])
        if e["window_start"] != (target - timedelta(days=e["lookback_days"])).isoformat():
            a.append("%s: window start %s is not target %s minus %s day(s)"
                     % (name, e["window_start"], e["target_date"], e["lookback_days"]))
        finished = datetime.fromisoformat(e["finished_utc"])
        if e["result"] in TERMINAL_OK and (e["listing_report"] or {}).get("coverage") != "proven":
            a.append("%s: a successful run without proven window coverage" % name)
        if prev_finished and finished < prev_finished:
            a.append("%s: ledgers are not chronological" % name)
        prev_finished = finished
        if e["result"] in TERMINAL_OK:
            if e["shadow_day"] != (finished - day_zero).days:
                a.append("%s: shadow_day %r, but %d whole days have elapsed since day zero"
                         % (name, e["shadow_day"], (finished - day_zero).days))
        elif e["shadow_day"] is not None:
            a.append("%s: an unsuccessful run carries shadow_day %r" % (name, e["shadow_day"]))
        before, after = e["state_sha256_before"], e["state_sha256_after"]
        if before != prev_after:
            a.append("%s: state chain broken: declares before=%s, the previous run ended at %s"
                     % (name, (before or "none")[:12], (prev_after or "none")[:12]))
        # Measured: with no publication to record, the runner leaves an existing
        # database byte-identical. Duplicates add observations, so they may not.
        if e["result"] == st.OK_NO_PUBLICATIONS and before is not None and before != after:
            a.append("%s: a run with no publications changed the database" % name)
        prev_after = after
    facts["chain_final"] = prev_after
    if prev_after != db_sha:
        a.append("the database (%s) is not the last ledger's after-state (%s)"
                 % (db_sha[:12], (prev_after or "none")[:12]))

    days = sorted({e["finished_utc"][:10] for e in successes})
    missing = []
    for x, y in zip(days, days[1:]):
        missing += [d.isoformat() for d in _days(date.fromisoformat(x), date.fromisoformat(y))[1:-1]]
    for d in missing:
        a.append("no successful run finished on %s (UTC), inside the observed period" % d)
    streak = 0
    for d in reversed(days):
        if streak and (date.fromisoformat(days[len(days) - streak]) - date.fromisoformat(d)).days != 1:
            break
        streak += 1
    facts.update(collecting_days=days, missing_days=missing, consecutive_collecting_days=streak)

    covered = set()
    for e in successes:
        if (e["listing_report"] or {}).get("coverage") == "proven":
            covered.update(_days(date.fromisoformat(e["window_start"]),
                                 date.fromisoformat(e["target_date"])))
    # The shadow period runs from the first window of a run that targeted its
    # own day (a scheduled slot or an undated dispatch) to the latest target.
    # A dispatch naming an older date reads history: it adds coverage and
    # never opens a gap of its own.
    current = [e for e in successes if e["target_date_source"] != "explicit"]
    period, uncovered = None, []
    if current:
        period = (date.fromisoformat(min(e["window_start"] for e in current)),
                  max(date.fromisoformat(e["target_date"]) for e in successes))
        uncovered = sorted(set(_days(*period)) - covered)
    facts["shadow_period"] = [d.isoformat() for d in period] if period else None
    facts["window_coverage"] = _ranges(covered)
    facts["uncovered_dates"] = _ranges(uncovered)
    for first, last in facts["uncovered_dates"]:
        end, targets = date.fromisoformat(last), []
        while end >= date.fromisoformat(first):
            targets.append(end.isoformat())
            end -= timedelta(days=7)
        a.append("logical dates %s to %s, inside the shadow period, lie in no proven window; "
                 "recover by dispatching target_date %s (each covers that date and the six "
                 "before it)" % (first, last, ", ".join(targets)))
    return a, facts


def late_listings(ledgers: list, collected: set) -> list:
    """
    Items a later tag page listed inside an earlier run's window although that
    run's own copy of the page, read after the item's listed time, lacked them.
    """
    runs = [e for e in ledgers if e["result"] in TERMINAL_OK
            and (e["listing_report"] or {}).get("coverage") == "proven"
            and "listed" in e["listing_report"]]
    found = []
    for i, first in enumerate(runs):
        ids = {item for item, _ in first["listing_report"]["listed"]}
        opened = (datetime.fromisoformat(first["started_utc"]).astimezone(HANOI)
                  .strftime("%Y-%m-%dT%H:%M"))
        late = {}
        for later in runs[i + 1:]:
            for item, local in later["listing_report"]["listed"]:
                if item in ids or item in late:
                    continue
                if first["window_start"] <= local[:10] <= first["target_date"] and local < opened:
                    late[item] = (local, later["run_id"])
        for item, (local, seen_by) in sorted(late.items()):
            fate = ("collected by a later run" if IDENTITY_PREFIX + item in collected else
                    "inside no later window, so it was NOT collected")
            found.append("late listing: %s%s, listed %s (Ha Noi), was absent from run %s's tag "
                         "page although inside its window; first listed in run %s; %s"
                         % (IDENTITY_PREFIX, item, local, first["run_id"], seen_by, fate))
    return found


def validate_corpus(con: sqlite3.Connection, ledgers: list, captures: dict) -> tuple:
    """Record, version and observation rules, and their reconciliation."""
    a, collector = [], []
    tables = sorted(r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"))
    if tables != sorted(EXPECTED_COLUMNS):
        raise ReviewError("the database holds tables %s; the Vietnam runner creates exactly %s"
                          % (tables, sorted(EXPECTED_COLUMNS)))
    for table, cols in EXPECTED_COLUMNS.items():
        found = tuple(r[1] for r in con.execute("PRAGMA table_info(%s)" % table))
        if found != cols:
            raise ReviewError("unknown %s shape, refusing to review:\n  expected %s\n  found    %s"
                              % (table, list(cols), list(found)))
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        a.append("database integrity_check returned %r" % integrity)

    def rows(table):
        cols = EXPECTED_COLUMNS[table]
        return [dict(zip(cols, r)) for r in con.execute(
            "SELECT %s FROM %s" % (", ".join(cols), table))]
    # Run ids are not chronological strings; the committed ledger order is.
    order = {str(e["run_id"]): n for n, e in enumerate(ledgers)}
    late = len(order)
    records = sorted(rows("shadow_records"), key=lambda r: r["source_identity"])
    versions = sorted(rows("shadow_versions"), key=lambda v: (
        v["source_identity"], order.get(str(v["first_seen_run"]), late), v["content_sha256"]))
    observations = sorted(rows("shadow_observations"), key=lambda o: (
        order.get(str(o["run_id"]), late), o["source_identity"]))
    run_ids = set(order)
    by_ident = {}
    for v in versions:
        by_ident.setdefault(v["source_identity"], []).append(v)
        flags = v["_flags"] = []
        try:
            blocks = json.loads(v["blocks_json"])
            assert isinstance(blocks, list) and all(
                isinstance(b, list) and len(b) == 2 and all(isinstance(x, str) for x in b)
                for b in blocks)
        except (ValueError, AssertionError):
            blocks = None
            flags.append("blocks:unreadable")
        v["_blocks"] = blocks or []
        if v["content_hash_rule"] != CONTENT_HASH_RULE:
            flags.append("hash:rule-%s" % v["content_hash_rule"])
        elif blocks is not None and content_sha256(v["title_original"], v["lead_original"],
                                                   blocks) != v["content_sha256"]:
            flags.append("hash:mismatch")
        if blocks is not None and assembled_text(v["lead_original"], blocks) != v["text_original"]:
            flags.append("text:disagrees-with-blocks")
        if not (v["title_original"] or "").strip():
            flags.append("title:empty")
        if not (v["text_original"] or "").strip():
            flags.append("body:empty")
        if v["body_status"] not in BODY_STATUSES:
            flags.append("body:status-%s" % v["body_status"])
        elif v["body_status"] == "media_only":
            flags.append("body:media-only")
        marker = next((m for m in STUB_MARKERS if m in (v["text_original"] or "").lower()), None)
        if marker:
            flags.append("body:stub-marker:%s" % marker.replace(" ", "-"))
        if v["first_capture_sha256"] not in captures:
            flags.append("capture:missing-%s" % str(v["first_capture_sha256"])[:12])
        if str(v["first_seen_run"]) not in run_ids:
            flags.append("run:unknown-%s" % v["first_seen_run"])

    for r in records:
        ident, flags = r["source_identity"], []
        aid = article_id(r["url"])
        if aid is None:
            flags.append("url:not-an-article-url")
        elif ident != IDENTITY_PREFIX + aid:
            flags.append("identity:disagrees-with-url")
        if r["canonical_url"] != r["url"]:
            flags.append("canonical:differs-from-url")
        for field, want in (("source_slug", SOURCE_SLUG), ("language_tag", "en"),
                            ("publication_kind", PUBLICATION_KIND)):
            if r[field] != want:
                flags.append("%s:%s" % (field, r[field]))
        facts = stamp_facts(r["published_at_original"])
        if facts is None:
            flags.append("date:unreadable-stamp")
        else:
            if facts[0] != r["published_date"]:
                flags.append("date:stamp-says-%s" % facts[0])
            if facts[1] != r["published_at_utc"]:
                flags.append("date:utc-instant-disagrees")
        mine = by_ident.get(ident, [])
        if len(mine) != r["version_count"]:
            flags.append("versions:count-%d-not-%d" % (len(mine), r["version_count"]))
        if r["current_content_sha256"] not in {v["content_sha256"] for v in mine}:
            flags.append("versions:current-missing")
        if {str(r["first_seen_run"]), str(r["last_seen_run"])} - run_ids:
            flags.append("run:unknown")
        for v in mine:
            flags += ["v%s:%s" % (v["content_sha256"][:8], f) for f in v["_flags"]]
        r["_flags"], r["_versions"] = flags, mine
        r["_current"] = next((v for v in mine if v["content_sha256"]
                              == r["current_content_sha256"]), mine[-1] if mine else {})
        a += ["%s: %s" % (ident, f) for f in flags]
    orphans = sorted(set(by_ident) - {r["source_identity"] for r in records})
    a += ["%s: versions without a record" % o for o in orphans]

    known = {(v["source_identity"], v["content_sha256"]) for v in versions}
    per_run, anomalies_per_run = Counter(), Counter()
    for o in observations:
        where = "observation %s/%s" % (o["run_id"], o["source_identity"])
        per_run[(str(o["run_id"]), o["outcome"])] += 1
        if o["outcome"] not in OUTCOMES:
            a.append("%s: outcome %r" % (where, o["outcome"]))
        if str(o["run_id"]) not in run_ids:
            a.append("%s: no ledger for this run" % where)
        if o["capture_sha256"] not in captures:
            a.append("%s: capture %s is not in the state tree"
                     % (where, str(o["capture_sha256"])[:12]))
        if (o["source_identity"], o["content_sha256"]) not in known:
            a.append("%s: content is not a stored version" % where)
        try:
            noted = json.loads(o["anomalies_json"])
        except ValueError:
            noted = ["(unreadable anomalies_json)"]
        anomalies_per_run[str(o["run_id"])] += len(noted)
        collector += ["collector, run %s, %s: %s" % (o["run_id"], o["source_identity"], x)
                      for x in noted]

    new_total = version_total = 0
    for e in ledgers:
        rid, name = str(e["run_id"]), e["_filename"]
        for outcome, key in (("new", "new_records"), ("changed", "changed"),
                             ("reverted", "reverted"), ("unchanged", "unchanged")):
            if per_run[(rid, outcome)] != e[key]:
                a.append("%s: ledger counts %d %s, the database holds %d"
                         % (name, e[key], outcome, per_run[(rid, outcome)]))
        if anomalies_per_run[rid] != len(e["anomalies"]):
            a.append("%s: ledger lists %d collector anomalies, its observations %d"
                     % (name, len(e["anomalies"]), anomalies_per_run[rid]))
        new_total += e["new_records"]
        version_total += e["new_records"] + e["changed"]
        if "corpus_range" in e and (e["stored_total"], e["versions_total"]) != (new_total,
                                                                               version_total):
            a.append("%s: totals %d/%d, but the ledgers sum to %d/%d"
                     % (name, e["stored_total"], e["versions_total"], new_total, version_total))
    if (len(records), len(versions)) != (new_total, version_total):
        a.append("the database holds %d records and %d versions; the ledgers account for %d and %d"
                 % (len(records), len(versions), new_total, version_total))

    referenced = {}
    for e in ledgers:
        for c in e["captures"]:
            sha = c.get("payload_sha256")
            referenced.setdefault(sha, []).append(
                {"run_id": e["run_id"], "role": c.get("role"), "url": c.get("url")})
            if sha not in captures:
                a.append("%s: capture %s is not in the state tree" % (e["_filename"], str(sha)[:12]))
            elif c.get("payload_bytes") != captures[sha]["bytes"]:
                a.append("%s: capture %s size disagrees" % (e["_filename"], sha[:12]))
    for sha in sorted(captures):
        if not captures[sha]["hash_ok"]:
            a.append("capture %s does not hash to its own name" % sha[:12])
        if sha not in referenced:
            a.append("capture %s is referenced by no ledger" % sha[:12])
        captures[sha]["references"] = referenced.get(sha, [])

    by_title = {}
    for r in records:
        if r["_versions"]:
            by_title.setdefault(r["_current"]["title_original"], []).append(
                r["source_identity"])
    shared = {t: ids for t, ids in sorted(by_title.items()) if len(ids) > 1}
    return records, versions, observations, a, collector, shared


# ── the packet ──────────────────────────────────────────────────────────────

def _latest(observations, ident):
    mine = [o for o in observations if o["source_identity"] == ident]
    return mine[-1] if mine else {}


def signoff_template(manifest: dict) -> dict:
    """The structured form a person fills in. Nothing in it is pre-answered."""
    return {
        "signoff_schema": SIGNOFF_SCHEMA,
        "desk": DESK_IDENTITY,
        "checkpoint": manifest["checkpoint"],
        "automated_package_id": manifest["deterministic_sha256"],
        "state_commit": manifest["state_commit"],
        "state_tree": manifest["state_tree"],
        "latest_ledger_run_id": manifest["latest_run_id"],
        "latest_shadow_day": manifest["latest_shadow_day"],
        "queue_algorithm": QUEUE_ALGORITHM,
        "records_required": len(manifest["required_review_records"]),
        "allowed_verdicts": manifest["allowed_verdicts"],
        "reviewer": "",
        "review_started_utc": "",
        "review_completed_utc": "",
        "records": [dict({"identity": i}, **{f: None for f in CHECK_FIELDS}, note="")
                    for i in manifest["required_review_records"]],
        "anomalies": [{"anomaly": x, "disposition": ""} for x in manifest["anomalies"]],
        "verdict": "",
        "notes": "",
        "attestation": "",
    }


def validate_signoff(manifest: dict, signoff: dict) -> list:
    """What still stands between this sign-off and a completed review."""
    p = []
    for field in ("signoff_schema", "desk", "checkpoint", "state_commit", "state_tree"):
        want = SIGNOFF_SCHEMA if field == "signoff_schema" else (
            DESK_IDENTITY if field == "desk" else manifest[field])
        if signoff.get(field) != want:
            p.append("%s is %r, the packet says %r" % (field, signoff.get(field), want))
    if signoff.get("automated_package_id") != manifest["deterministic_sha256"]:
        p.append("automated_package_id does not name this packet")
    if not manifest["formal"]:
        p.append("the packet is a rehearsal; only a formal packet can be signed off")
    for field in ("reviewer", "attestation"):
        if not str(signoff.get(field) or "").strip():
            p.append("%s is empty" % field)
    try:
        started = datetime.fromisoformat(signoff.get("review_started_utc") or "")
        done = datetime.fromisoformat(signoff.get("review_completed_utc") or "")
        if started.utcoffset() is None or done.utcoffset() is None or done < started:
            p.append("review times must carry an offset and finish after they start")
    except (TypeError, ValueError):
        p.append("review_started_utc and review_completed_utc must be ISO 8601 times")
    got = {str(r.get("identity")): r for r in signoff.get("records") or []}
    if sorted(got) != sorted(manifest["required_review_records"]):
        p.append("records must be exactly the %d required identities"
                 % len(manifest["required_review_records"]))
    findings = False
    for ident in sorted(got):
        for field in CHECK_FIELDS:
            value = got[ident].get(field)
            if not isinstance(value, bool):
                p.append("%s: %s must be true or false, not %r" % (ident, field, value))
            findings = findings or value is False
        if not isinstance(got[ident].get("note"), str):
            p.append("%s: note must be a string" % ident)
    disposed = {x.get("anomaly"): x.get("disposition") for x in signoff.get("anomalies") or []}
    if sorted(disposed) != sorted(manifest["anomalies"]):
        p.append("anomalies must be exactly the packet's %d" % len(manifest["anomalies"]))
    p += ["anomaly has no disposition: %s" % x for x in manifest["anomalies"]
          if not str(disposed.get(x) or "").strip()]
    verdict = signoff.get("verdict")
    if verdict not in manifest["allowed_verdicts"]:
        p.append("verdict %r is not one of %s" % (verdict, manifest["allowed_verdicts"]))
    elif verdict == "pass" and findings:
        p.append("verdict pass with a check answered false; use pass_with_findings or fail")
    return p


def render_report(m: dict, ledgers: list, records: list, observations: list,
                  shared: dict, late: list) -> str:
    L = []
    w = L.append
    w("# Vietnam shadow review — %s" % (m["checkpoint"] or "rehearsal"))
    w("")
    w("> " + FRAMING)
    w("")
    if not m["formal"]:
        w("> ## REHEARSAL — not a checkpoint packet")
        w(">")
        w("> Read from a directory nothing verifies. It names no state commit, so it")
        w("> identifies a corpus but not a point in `%s`. Re-generate with" % STATE_BRANCH)
        w("> `--state-repo`, `--state-commit` and `--checkpoint`.")
        w("")
    elif not m["checkpoint_reached"]:
        w("> ## %s HAS NOT ARRIVED" % m["checkpoint"].upper())
        w(">")
        w("> It needs shadow_day >= %d; the latest successful run records %s."
          % (CHECKPOINTS[m["checkpoint"]], m["latest_shadow_day"]))
        w("")
    w("> **An unfilled report is not evidence of a completed review.** The automated")
    w("> checks establish internal consistency. Only a person comparing every record")
    w("> below with its live page, and a completed `signoff_template.json`, can")
    w("> establish that the stored records are what Government News published.")
    w("")
    w("| | |")
    w("|---|---|")
    w("| Package id | `%s` |" % m["deterministic_sha256"])
    w("| Tool | `%s` v%s |" % (m["tool"], m["tool_version"]))
    if m["formal"]:
        w("| State commit (verified) | `%s` |" % m["state_commit"])
        w("| State tree | `%s` |" % m["state_tree"])
        w("| Reachable from | `%s` |" % m["state_ref"])
    w("| Provenance | %s |" % m["provenance"])
    w("| Collector commit (latest ledger) | `%s` |" % m["latest_collector_commit"])
    w("| Day zero | `%s` (run `%s`) |" % (m["day_zero_utc"], m["day_zero_run_id"]))
    w("| Latest successful shadow_day | **%s** |" % m["latest_shadow_day"])
    w("| Collecting days | %d; latest consecutive run %d of %d required |"
      % (len(m["collecting_days"]), m["consecutive_collecting_days"], REQUIRED_COLLECTING_DAYS))
    w("| Ledgers | %d |" % m["ledger_count"])
    w("| Corpus | %d publication(s), %d version(s), %d observation(s), %d capture(s) |"
      % (m["corpus_count"], m["version_count"], m["observation_count"], m["capture_count"]))
    w("| Publication dates | %s |" % ("%s → %s" % tuple(m["corpus_range"])
                                         if m["corpus_count"] else "—"))
    w("| Database integrity | %s |" % m["database_integrity"])
    w("| State-hash chain | %s |" % m["state_chain_verdict"])
    w("| Anomalies to dispose | %d |" % m["anomaly_count"])
    w("")
    w("## Automated integrity")
    w("")
    if m["anomalies"]:
        w("Each anomaly needs a written disposition in the sign-off. Lines beginning "
          "`collector` were recorded by the runner as it stored the page; the rest "
          "were found by this kit.")
        w("")
        for x in m["anomalies"]:
            w("- %s" % x)
    else:
        w("None. Schema, clock, ledger identity, result taxonomy, request ceilings, "
          "state-hash chain, shadow_day arithmetic, window coverage, record identity, "
          "dates, content hashes, versions, observations and captures all reconcile.")
    w("")
    w("## Runs")
    w("")
    w("| Ledger | Run | Target (rule) | Window from | Finished (UTC) | Day | Result | "
      "Listed | Sel | New | Chg | Rev | Unch | Failed | Requests |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for e in ledgers:
        w("| `%s` | %s | %s (%s) | %s | %s | %s | `%s` | %s | %d | %d | %d | %d | %d | %d | %d |" % (
            e["_filename"], e["run_id"], e["target_date"], e["target_date_source"],
            e["window_start"], e["finished_utc"][:19],
            "—" if e["shadow_day"] is None else e["shadow_day"], e["result"],
            (e["listing_report"] or {}).get("items_listed", "—"), e["selected"],
            e["new_records"], e["changed"], e["reverted"], e["unchanged"],
            e["fetch_failures"] + e["extraction_failures"] + e["access_failures"],
            len(e["requests"])))
    w("")
    w("A failed run pushes nothing to `%s`. Its ledger, captures and log exist only "
      "in that Actions run's `vietnam-shadow-<run id>-<attempt>` artifact, kept 90 "
      "days, so a missing collecting day is where to look for one." % STATE_BRANCH)
    w("")
    w("## Window coverage")
    w("")
    w("Logical dates covered by a successful run whose tag page proved the window "
      "(its oldest listed item was older than the window start): %s."
      % (", ".join("%s → %s" % tuple(r) for r in m["window_coverage"]) or "none"))
    w("")
    if m["shadow_period"] is None:
        w("No successful run has targeted its own day yet; every window so far was a "
          "dispatch naming a date, so no shadow period is defined and no gap is computed.")
    elif m["uncovered_dates"]:
        w("Shadow period %s → %s. Inside no proven window: %s. See the anomalies for "
          "recovery dispatches." % (tuple(m["shadow_period"]) + (", ".join(
              "%s → %s" % tuple(r) for r in m["uncovered_dates"]),)))
    else:
        w("Shadow period %s → %s: every logical date in it lies inside a proven window."
          % tuple(m["shadow_period"]))
    w("")
    w("Coverage is of what the `defense` tag listed when each run read it. An article "
      "the editors never tagged is outside this source and leaves no trace here.")
    w("")
    w("## Late listing")
    w("")
    if late:
        for x in late:
            w("- %s" % x)
    else:
        w("No item appeared in a later tag page with a listed time inside an earlier "
          "run's window before that run read the page.")
    w("")
    w("## Records — %d of %d, the complete corpus" % (len(records), len(records)))
    w("")
    if not records:
        w("**No records to review.** No in-window item was listed in this period. That "
          "is evidence of listing access only: robots.txt and the tag page were read "
          "and each window was proven covered, but no article body was retrieved, so "
          "body access, extraction and dating are unexercised by this period. At the "
          "tag's measured cadence, silence cannot be calibrated as an outage signal. "
          "A plain `pass` is not available for an empty corpus.")
        w("")
    for r in records:
        current = r["_current"]
        o = _latest(observations, r["source_identity"])
        w("### `%s`" % r["source_identity"])
        w("")
        w("- **URL:** %s" % r["url"])
        w("- **Title:** %s" % (current.get("title_original") or "").replace("|", "\\|"))
        w("- **Published:** %s (stamp `%s`, UTC `%s`)" % (
            r["published_date"], r["published_at_original"], r["published_at_utc"]))
        w("- **Byline / JSON-LD publisher / section:** %s / %s / %s" % (
            o.get("byline"), o.get("publisher_jsonld"), o.get("category")))
        w("- **Versions:** %d; current `%s`; seen in runs %s → %s" % (
            r["version_count"], r["current_content_sha256"], r["first_seen_run"],
            r["last_seen_run"]))
        if len(r["_versions"]) > 1:
            w("- **Other stored versions:** %s — compare the live page with the current one."
              % ", ".join("`%s` (first seen in run %s)" % (v["content_sha256"][:12],
                                                          v["first_seen_run"])
                          for v in r["_versions"] if v is not current))
        w("- **Body:** %d block(s), %d character(s), status %s" % (
            len(current.get("_blocks") or []), len(current.get("text_original") or ""),
            current.get("body_status")))
        if r["_flags"]:
            w("- **Flags:** %s" % ", ".join(r["_flags"]))
        w("")
        w("| Check | Reviewer entry |")
        w("|---|---|")
        for label in CHECK_LABELS + ("Notes",):
            w("| %s | |" % label)
        w("")
    if shared:
        w("Shared titles, kept as distinct publications by identity: %s."
          % "; ".join("%r → %s" % (t[:60], ", ".join(ids)) for t, ids in shared.items()))
        w("")
    w("## Sign-off")
    w("")
    w("Fill `signoff_template.json`, not this file, then run `--check-signoff`. Allowed "
      "verdicts for this packet: %s. A completed checkpoint qualifies nothing on its "
      "own; consideration needs %d consecutive collecting days, the Day 7, 14 and 30 "
      "reviews, the desk-strength criteria and the owner's sign-off in DECISION_LOG.md. "
      "This kit does not promote the desk, and no result it prints is a promotion."
      % (", ".join(m["allowed_verdicts"]), REQUIRED_COLLECTING_DAYS))
    w("")
    return "\n".join(L) + "\n"


def build(state_dir, out_dir: Path, as_of: str, allow_tracked: bool = False,
          state_commit: str = None, checkpoint: str = None, state_repo: Path = None,
          state_ref: str = STATE_BRANCH) -> dict:
    if (state_commit is None) != (checkpoint is None):
        raise ReviewError("--state-commit and --checkpoint are given together or not at all")
    if checkpoint is not None and checkpoint not in CHECKPOINTS:
        raise ReviewError("unknown checkpoint %r" % checkpoint)
    try:
        date.fromisoformat(as_of)
    except (TypeError, ValueError):
        raise ReviewError("--as-of must be YYYY-MM-DD")
    provenance, export_root = None, None
    if state_commit is not None:
        if state_repo is None or state_dir is not None:
            raise ReviewError("a formal packet reads --state-repo and nothing else; "
                              "--state-dir is for rehearsals")
        repo = resolve_state_repo(state_repo)
        provenance = verify_state_commit(repo, state_commit, state_ref)
        export_root = Path(tempfile.mkdtemp(prefix="vietnam-state-"))
        state_dir = export_state_tree(repo, state_commit, export_root / STATE_PREFIX)
    elif state_dir is None:
        raise ReviewError("pass --state-repo with --state-commit and --checkpoint, or "
                          "--state-dir for a rehearsal")
    else:
        assert_safe_state_dir(Path(state_dir))
    try:
        return _build(Path(state_dir).resolve(), out_dir, as_of, allow_tracked,
                      state_commit, checkpoint, provenance)
    finally:
        if export_root is not None:
            shutil.rmtree(export_root, ignore_errors=True)


def _build(state_dir, out_dir, as_of, allow_tracked, state_commit, checkpoint, provenance):
    assert_safe_out_dir(out_dir, allow_tracked)
    before = hash_inputs(state_dir)
    captures = {}
    for name, digest in before.items():
        match = CAPTURE_NAME.match(name)
        if match:
            captures[match.group(1)] = {"bytes": (state_dir / name).stat().st_size,
                                        "hash_ok": digest == match.group(1)}
    ledgers = load_ledgers(state_dir)
    run_anomalies, facts = validate_runs(state_dir, ledgers, before["shadow.db"])
    con = open_readonly(state_dir / "shadow.db")
    try:
        records, versions, observations, corpus_anomalies, collector, shared = \
            validate_corpus(con, ledgers, captures)
    finally:
        con.close()
    late = late_listings(ledgers, {r["source_identity"] for r in records})
    anomalies = run_anomalies + corpus_anomalies + late + collector

    successes = [e for e in ledgers if e["result"] in TERMINAL_OK]
    latest_day = successes[-1]["shadow_day"] if successes else None
    dates = sorted(r["published_date"] for r in records)
    manifest = {
        "tool": "scripts/review_vietnam_shadow_state.py",
        "tool_version": TOOL_VERSION,
        "queue_algorithm": QUEUE_ALGORITHM,
        "signoff_schema": SIGNOFF_SCHEMA,
        "as_of": as_of,
        "desk": DESK_IDENTITY,
        "source_slug": SOURCE_SLUG,
        "state_branch": STATE_BRANCH,
        "checkpoint": checkpoint,
        "state_commit": state_commit,
        "state_tree": (provenance or {}).get("state_tree"),
        "state_ref": (provenance or {}).get("state_ref"),
        "provenance": "git-verified-tree/1" if provenance else "unverified-working-copy",
        "formal": provenance is not None,
        "checkpoint_reached": bool(provenance and latest_day is not None
                                   and latest_day >= CHECKPOINTS[checkpoint]),
        "review_mode": "complete-corpus",
        "input_sha256": before,
        "day_zero_utc": facts["clock"]["day_zero_utc"],
        "day_zero_run_id": facts["clock"]["day_zero_run_id"],
        "latest_ledger": ledgers[-1]["_filename"],
        "latest_run_id": ledgers[-1]["run_id"],
        "latest_collector_commit": ledgers[-1]["collector_commit"],
        "latest_shadow_day": latest_day,
        "ledger_count": len(ledgers),
        "collecting_days": facts["collecting_days"],
        "missing_collecting_days": facts["missing_days"],
        "consecutive_collecting_days": facts["consecutive_collecting_days"],
        "required_collecting_days": REQUIRED_COLLECTING_DAYS,
        "shadow_period": facts["shadow_period"],
        "window_coverage": facts["window_coverage"],
        "uncovered_dates": facts["uncovered_dates"],
        "corpus_count": len(records),
        "version_count": len(versions),
        "observation_count": len(observations),
        "capture_count": len(captures),
        "corpus_range": [dates[0], dates[-1]] if dates else [None, None],
        "database_integrity": ("ok" if not any("integrity_check" in x for x in anomalies)
                               else "FAILED"),
        "state_chain_verdict": ("coherent" if not any(
            "state chain broken" in x or "last ledger's after-state" in x
            for x in anomalies) else "BROKEN"),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "required_review_records": [r["source_identity"] for r in sorted(
            records, key=lambda r: (r["published_date"], r["source_identity"]))],
        # An empty corpus exercised the listing only. It is never a plain pass.
        "allowed_verdicts": list(VERDICTS if records else VERDICTS[1:]),
        "automated_checks_are_not_the_human_review": (
            "These checks establish internal consistency only. The checkpoint is "
            "complete only when a person has compared every record with its live "
            "page and completed the sign-off."),
    }

    inventory = []
    for r in records:
        o = _latest(observations, r["source_identity"])
        inventory.append({
            "identity": r["source_identity"], "url": r["url"],
            "canonical_url": r["canonical_url"],
            "title": r["_current"].get("title_original"),
            "published_date": r["published_date"],
            "published_at_original": r["published_at_original"],
            "published_at_utc": r["published_at_utc"],
            "publication_kind": r["publication_kind"],
            "byline": o.get("byline"), "publisher_jsonld": o.get("publisher_jsonld"),
            "category": o.get("category"),
            "current_content_sha256": r["current_content_sha256"],
            "versions": [{"content_sha256": v["content_sha256"],
                          "first_seen_run": v["first_seen_run"],
                          "first_capture_sha256": v["first_capture_sha256"],
                          "body_status": v["body_status"],
                          "blocks": len(v["_blocks"]),
                          "text_chars": len(v["text_original"] or "")}
                         for v in r["_versions"]],
            "first_seen_run": r["first_seen_run"], "last_seen_run": r["last_seen_run"],
            "observations": sum(1 for x in observations
                                if x["source_identity"] == r["source_identity"]),
            "flags": r["_flags"],
        })
    runs = [{k: e[k] for k in ("run_id", "target_date", "target_date_source", "window_start",
                               "lookback_days", "started_utc", "finished_utc", "result",
                               "health", "shadow_day", "discovered", "selected", "retrieved",
                               "new_records", "changed", "reverted", "unchanged",
                               "fetch_failures", "extraction_failures", "access_failures",
                               "collector_commit")}
            for e in ledgers]
    for row, e in zip(runs, ledgers):
        row.update(ledger=e["_filename"], requests=len(e["requests"]),
                   coverage=(e["listing_report"] or {}).get("coverage"),
                   items_listed=(e["listing_report"] or {}).get("items_listed"))
    capture_rows = [dict({"sha256": sha}, **captures[sha]) for sha in sorted(captures)]

    out_dir.mkdir(parents=True, exist_ok=True)
    texts = {
        "record_inventory.jsonl": "".join(json.dumps(x, sort_keys=True, ensure_ascii=False)
                                          + "\n" for x in inventory),
        "run_inventory.jsonl": "".join(json.dumps(x, sort_keys=True) + "\n" for x in runs),
        "capture_inventory.jsonl": "".join(json.dumps(x, sort_keys=True) + "\n"
                                           for x in capture_rows),
    }
    manifest["deterministic_sha256"] = package_sha256(manifest, texts)
    texts["signoff_template.json"] = json.dumps(signoff_template(manifest), indent=1,
                                                sort_keys=True, ensure_ascii=False) + "\n"
    texts["review_report.md"] = render_report(manifest, ledgers, records, observations,
                                              shared, late)
    for name, text in texts.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    manifest["artifact_sha256"] = {name: hashlib.sha256(text.encode("utf-8")).hexdigest()
                                   for name, text in sorted(texts.items())}
    (out_dir / "review_manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (out_dir / "generation_context.json").write_text(json.dumps({
        "deterministic_sha256": manifest["deterministic_sha256"],
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "state_dir": str(state_dir), "out_dir": str(out_dir.resolve()),
        "not_part_of_the_packet": True}, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    if hash_inputs(state_dir) != before:
        raise ReviewError("the input state changed during review; the packet is void")
    for sidecar in ("shadow.db-wal", "shadow.db-shm", "shadow.db-journal"):
        if (state_dir / sidecar).exists():
            raise ReviewError("a %s appeared beside the input database" % sidecar)
    return manifest


INVENTORIES = ("record_inventory.jsonl", "run_inventory.jsonl", "capture_inventory.jsonl")


def package_sha256(manifest: dict, inventories: dict) -> str:
    """The package id: the manifest's own facts plus the three inventories."""
    facts = {k: v for k, v in manifest.items()
             if k not in ("deterministic_sha256", "artifact_sha256")}
    return hashlib.sha256(json.dumps(
        {"manifest": facts, "inventories": {n: inventories[n] for n in INVENTORIES}},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def check_signoff(packet: Path, signoff_path: Path) -> list:
    """A filled sign-off against the packet it answers, which must be intact."""
    try:
        manifest = json.loads((packet / "review_manifest.json").read_text(encoding="utf-8"))
        signoff = json.loads(signoff_path.read_text(encoding="utf-8"))
        inventories = {n: (packet / n).read_text(encoding="utf-8") for n in INVENTORIES}
    except (OSError, ValueError) as exc:
        raise ReviewError("cannot read the packet or sign-off: %s" % exc)
    if package_sha256(manifest, inventories) != manifest.get("deterministic_sha256"):
        raise ReviewError("review_manifest.json or an inventory no longer matches the "
                          "package id; the packet was altered")
    for name, digest in sorted(manifest.get("artifact_sha256", {}).items()):
        path = packet / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ReviewError("packet file %s is missing or altered" % name)
    return validate_signoff(manifest, signoff)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--state-repo", default=None,
                   help="a clone of %s, with its .git (formal packet)" % STATE_BRANCH)
    p.add_argument("--state-commit", default=None, help="full 40-character state commit")
    p.add_argument("--checkpoint", default=None, choices=sorted(CHECKPOINTS))
    p.add_argument("--state-ref", default=STATE_BRANCH,
                   help="the ref --state-commit must be reachable from")
    p.add_argument("--state-dir", default=None, help="REHEARSAL ONLY: a copy of state/")
    p.add_argument("--out", default=None, help="packet destination, outside the repository")
    p.add_argument("--as-of", default=None, help="YYYY-MM-DD; pass it for reproducibility")
    p.add_argument("--check-signoff", default=None, metavar="SIGNOFF_JSON",
                   help="check a filled sign-off against the packet in --out")
    p.add_argument("--allow-tracked-destination", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    if not args.out:
        print("review refused: --out is required", file=sys.stderr)
        return 2
    try:
        if args.check_signoff:
            problems = check_signoff(Path(args.out), Path(args.check_signoff))
            for line in problems:
                print("incomplete: %s" % line)
            print("sign-off complete" if not problems else "%d problem(s)" % len(problems))
            return 1 if problems else 0
        m = build(Path(args.state_dir) if args.state_dir else None, Path(args.out),
                  args.as_of or datetime.now(timezone.utc).date().isoformat(),
                  args.allow_tracked_destination, args.state_commit, args.checkpoint,
                  Path(args.state_repo) if args.state_repo else None, args.state_ref)
    except ReviewError as exc:
        print("review refused: %s" % exc, file=sys.stderr)
        return 2
    print("corpus          : %d publication(s), %d version(s), %s → %s" % (
        m["corpus_count"], m["version_count"], m["corpus_range"][0], m["corpus_range"][1]))
    print("ledgers         : %d, latest %s (shadow_day %s)" % (
        m["ledger_count"], m["latest_ledger"], m["latest_shadow_day"]))
    print("collecting days : %d (latest consecutive run %d of %d)" % (
        len(m["collecting_days"]), m["consecutive_collecting_days"], REQUIRED_COLLECTING_DAYS))
    print("state chain     : %s" % m["state_chain_verdict"])
    print("anomalies       : %d" % m["anomaly_count"])
    print("package id      : %s" % m["deterministic_sha256"])
    print("provenance      : %s" % m["provenance"])
    print("checkpoint      : %s" % (
        "%s, %s" % (m["checkpoint"], "reached" if m["checkpoint_reached"] else "NOT reached")
        if m["formal"] else "— (rehearsal)"))
    print("\nThe automated checks are not the review. Fill signoff_template.json.")
    return 1 if m["anomaly_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
