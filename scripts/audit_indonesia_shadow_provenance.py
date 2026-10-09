"""Offline, pinned Indonesia Kemhan shadow state + Actions evidence audit.

This is a research receipt only. It cannot qualify/publish a desk, perform
collection, attest human review/rights, or authenticate the caller's GitHub
Actions JSON export. It never fetches URLs or edits repository/state files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# The direct CLI must import the same date attribution contract as collectors.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.shadow_schedule import (SOURCE_EXPLICIT, SOURCE_MANUAL,
                                  SOURCE_SCHEDULE, scheduled_slot_date)

FAMILY = "id_kemhan_news"
DESK = "indonesia"
STATE_BRANCH = "shadow/indonesia-kemhan"
WORKFLOW_ID = 376840713
WORKFLOW_NAME = "Indonesia and South Korea Shadow Collection"
RUN_ID = re.compile(r"([1-9][0-9]*)-([1-9][0-9]*)\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GOOD_RESULTS = frozenset(("ok", "ok_all_duplicates", "ok_no_publications",
                          "ok_all_filtered"))
SCHEMA = "ipr-indonesia-shadow-pinned-provenance/1"


class ProvenanceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ProvenanceError(message)


def day(value):
    require(type(value) is str and bool(re.fullmatch(r"\d{4}-\d\d-\d\d", value)),
            "logical date must be exact YYYY-MM-DD")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ProvenanceError("invalid logical UTC date") from exc
    require(d.isoformat() == value, "noncanonical logical date")
    return d


def utc(value):
    require(type(value) is str, "UTC instant missing")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProvenanceError("invalid UTC instant") from exc
    require(stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0),
            "timestamp must be UTC")
    return stamp


def git(repo, *args):
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProvenanceError("required pinned Git object or local state branch missing") from exc


def pinned_state(repo, commit):
    """Return actual JSON ledger bytes and SQLite bytes from a fixed Git tree.

    No worktree checkout, remote access, branch movement or SQLite connection.
    The branch check prevents a caller-supplied unrelated Git commit from being
    described as Indonesia Kemhan history.
    """
    require(type(commit) is str and SHA.fullmatch(commit),
            "state commit must be literal 40-character SHA")
    branch = git(repo, "rev-parse", "--verify", "refs/heads/" + STATE_BRANCH).decode().strip()
    require(bool(SHA.fullmatch(branch)), "invalid local state branch")
    git(repo, "cat-file", "-e", commit + "^{commit}")
    try:
        subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor",
                        commit, branch], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProvenanceError("pinned commit not ancestor of explicit state branch") from exc

    names = git(repo, "ls-tree", "-r", "--name-only", commit, "state").decode().splitlines()
    require(len(names) == len(set(names)), "duplicate state path")
    require("state/clock.json" in names and "state/shadow.db" in names,
            "missing pinned clock/database")
    ledger_names = [n for n in names if n.startswith("state/ledger/") and
                    n.endswith(".json")]
    require(0 < len(ledger_names) <= 180, "missing or unbounded pinned ledger")
    require(all(n.startswith("state/") and ".." not in Path(n).parts for n in names),
            "unsafe pinned state path")

    def read(path):
        require(path in names, "missing pinned state file: " + path)
        # git cat-file validates the object. No path from untrusted JSON is read.
        raw = git(repo, "show", commit + ":" + path)
        require(len(raw) <= (60_000_000 if path.endswith(".db") else 1_000_000),
                "pinned state blob exceeds audit budget")
        return raw

    try:
        clock = json.loads(read("state/clock.json"))
        ledgers = [json.loads(read(n)) for n in ledger_names]
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProvenanceError("invalid pinned clock/ledger JSON") from exc
    require(type(clock) is dict and type(clock.get("day_zero_run_id")) is str,
            "missing pinned day-zero clock")
    require(type(clock.get("day_zero_utc")) is str,
            "missing pinned Day-0 UTC instant")
    utc(clock["day_zero_utc"])
    for name, ledger in zip(ledger_names, ledgers):
        require(type(ledger) is dict, "ledger is not object: " + name)
        ledger["_pinned_path"] = name
    return clock, ledgers, hashlib.sha256(read("state/shadow.db")).hexdigest()


def parse_actions_export(pages):
    """Explicitly complete pagination, but *not* authenticated network scope."""
    if type(pages) is dict:
        pages = [pages]
    require(type(pages) is list and 0 < len(pages) <= 100,
            "expected paginated Actions export")
    total, found = None, {}
    for page in pages:
        require(type(page) is dict and type(page.get("total_count")) is int and
                type(page.get("workflow_runs")) is list,
                "malformed Actions pagination")
        count = page["total_count"]
        require(0 <= count <= 10000 and (total is None or total == count),
                "inconsistent Actions pagination totals")
        total = count
        for action in page["workflow_runs"]:
            require(type(action) is dict and type(action.get("id")) is int and
                    action["id"] > 0 and action["id"] not in found,
                    "duplicate/malformed Actions run ID")
            found[action["id"]] = action
    require(len(found) == total, "incomplete Actions pagination")
    return found


def assess(clock, ledgers, actual_db_sha256, actions):
    """Strict source run and hash-chain consistency; never grant eligibility."""
    require(type(ledgers) is list and bool(ledgers), "no ledgers")
    require(type(actual_db_sha256) is str and SHA256.fullmatch(actual_db_sha256),
            "invalid pinned SQLite digest")
    seen_runs = set()
    observations = []
    scheduled = 0
    manual = 0
    local = 0
    prev = None
    prev_end = None
    slot_dates = set()
    for index, ledger in enumerate(ledgers):
        require(type(ledger) is dict, "ledger must be a dictionary")
        run = ledger.get("run_id")
        require(type(run) is str and run and run not in seen_runs,
                "missing or duplicate pinned run ID")
        seen_runs.add(run)
        require(ledger.get("desk") == DESK, "wrong shadow desk in pinned ledger")
        target = day(ledger.get("target_date"))
        started = utc(ledger.get("started_utc"))
        finished = utc(ledger.get("finished_utc"))
        require(started <= finished and (prev_end is None or started >= prev_end),
                "nonmonotonic or overlapping ledger run intervals")
        prev_end = finished
        before = ledger.get("state_sha256_before")
        after = ledger.get("state_sha256_after")
        require(type(after) is str and SHA256.fullmatch(after), "invalid after-state SHA256")
        if index == 0:
            require(before is None and run == clock["day_zero_run_id"],
                    "first ledger must match pinned Day-0 clock and have no previous state")
            require(started == utc(clock["day_zero_utc"]),
                    "first run clock must match Day-0 timestamp")
        else:
            require(type(before) is str and SHA256.fullmatch(before) and before == prev,
                    "broken adjacent ledger state SHA256 link")
        prev = after
        require(ledger.get("health") == "ok" and ledger.get("result") in GOOD_RESULTS,
                "ledger does not contain successful collection evidence")
        require(type(ledger.get("fetch_failures")) is int and
                type(ledger.get("extraction_failures")) is int and
                type(ledger.get("access_failures")) is int and
                all(ledger[k] == 0 for k in
                    ("fetch_failures", "extraction_failures", "access_failures")),
                "positive ledger has observed collection failure")
        commit = ledger.get("collector_commit")
        require(type(commit) is str and SHA.fullmatch(commit), "invalid collector commit")
        m = RUN_ID.fullmatch(run)
        if m is None:
            require(index == 0 and run.startswith("local-native-") and
                    ledger.get("target_date_source") == "manual-utc-date",
                    "unbound non-Actions run identity")
            local += 1
            kind = "local_day_zero"
        else:
            action_id, attempt = [int(v) for v in m.groups()]
            action = actions.get(action_id)
            require(action is not None, "Actions run missing from supplied export")
            require(type(action.get("run_attempt")) is int and
                    action["run_attempt"] == attempt,
                    "Actions run attempt mismatch")
            require(action.get("workflow_id") == WORKFLOW_ID and
                    action.get("name") == WORKFLOW_NAME,
                    "wrong workflow identity")
            require(action.get("head_branch") == "main" and
                    action.get("head_sha") == commit,
                    "wrong collector branch/commit")
            require(action.get("status") == "completed" and
                    action.get("conclusion") == "success",
                    "Actions run did not complete successfully")
            event = action.get("event")
            if event == "schedule":
                require(attempt == 1 and
                        ledger.get("target_date_source") == SOURCE_SCHEDULE,
                        "scheduled rerun or noncanonical schedule-slot target")
                # GitHub Actions can start after UTC midnight; use exactly the
                # same nominal slot date rule as the collector, never
                # action.created_at.date() or the first visible positive run.
                require(scheduled_slot_date(utc(action.get("created_at")),
                                            "17:17") == target,
                        "Actions scheduled event disagrees with logical slot date")
                require(scheduled_slot_date(started, "17:17") == target,
                        "collector start disagrees with logical slot date")
                require(target.isoformat() not in slot_dates,
                        "multiple scheduled successes for one logical date")
                slot_dates.add(target.isoformat())
                scheduled += 1
                kind = "scheduled"
            else:
                require(event == "workflow_dispatch" and
                        ledger.get("target_date_source") in
                        (SOURCE_MANUAL, SOURCE_EXPLICIT),
                        "manual run cannot count as scheduled slot")
                if ledger["target_date_source"] == SOURCE_MANUAL:
                    require(started.date() == target,
                            "implicit manual run cannot claim historical target")
                manual += 1
                kind = "manual"
        observations.append({"run_id": run, "target_date": target.isoformat(),
                             "kind": kind, "ledger_result": ledger["result"]})

    require(prev == actual_db_sha256,
            "pinned SQLite bytes do not match latest ledger's after-state digest")
    return {
        "schema": SCHEMA,
        "family": FAMILY,
        "state_branch": STATE_BRANCH,
        "ledgers_checked": len(ledgers),
        "adjacent_hash_links_checked": len(ledgers) - 1,
        "scheduled_run_matches": scheduled,
        "manual_run_matches": manual,
        "local_day_zero_runs": local,
        "observations": observations,
        "verdict": "pinned_state_and_supplied_actions_consistent_not_qualified",
        "pinned_db_sha256_checked": True,
        "actions_export_independently_authenticated": False,
        "all_scheduled_slots_exhaustively_audited": False,
        "source_rights_approved": False,
        "human_reviews_approved": False,
        "production_eligible": False,
        "weekly_ai_writer_eligible": False,
        "editor_delivery_authorized": False,
        "writes": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-repo", type=Path, required=True)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--actions-export", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        clock, ledgers, db_hash = pinned_state(args.state_repo, args.state_commit)
        actions = parse_actions_export(json.loads(
            args.actions_export.read_text(encoding="utf-8")))
        result = assess(clock, ledgers, db_hash, actions)
        result["pinned_state_commit"] = args.state_commit
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    except (ProvenanceError, OSError, ValueError, UnicodeDecodeError) as exc:
        p.exit(1, "Indonesia provenance: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
