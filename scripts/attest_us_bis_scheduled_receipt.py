"""Independent GitHub schedule -> Git receipt attestation for BIS shadow metadata.

A green collector or a commit message alone does not prove a scheduled source
observation. This verifier joins independently fetched GitHub Actions RUN JSON
with the immutable Git state and the exact publisher-metadata receipt.

An affirmative result attests that the SOURCE METADATA RECEIPT and scheduling
event agree. It does NOT independently rehash the publisher's live HTML,
qualify an ongoing clean-day streak, authorize source-content reuse, or admit
records to production SQLite or Pages.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from scripts.verify_us_bis_homepage_receipt import verify
from scripts.collect_us_bis_homepage_metadata import BISHold

REPO = "VSSpowerlifting/IndoPacificRecord"
WORKFLOW = ".github/workflows/us_bis_homepage_metadata_shadow.yml"
WORKFLOW_NAME = "BIS Official Homepage Press Metadata — Scheduled Shadow"
SHA = re.compile(r"[0-9a-f]{40}\Z")
DAY = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\Z")
MAX_HISTORY = 5000

class BISAttestationHold(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise BISAttestationHold(reason)

def git(state_dir, *args):
    try:
        return subprocess.check_output(
            ["git", "-C", str(state_dir), *args],
            stderr=subprocess.DEVNULL, timeout=15).decode("utf-8")
    except (OSError, UnicodeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired):
        raise BISAttestationHold("source_git_unverifiable") from None

def event_day(value):
    need(type(value) is str and value.endswith("Z"), "run_timestamp_missing")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise BISAttestationHold("run_timestamp_invalid") from None
    need(stamp.tzinfo is not None, "run_timestamp_timezone_absent")
    return stamp.astimezone(timezone.utc).date()

def assert_genuine_run(run):
    need(type(run) is dict, "run_metadata_missing")
    need(type(run.get("id")) is int and run["id"] > 0, "run_id_invalid")
    need(type(run.get("run_attempt")) is int and
         run["run_attempt"] >= 1, "run_attempt_invalid")
    need(run.get("event") == "schedule", "not_a_genuine_schedule_event")
    need(run.get("status") == "completed" and
         run.get("conclusion") == "success", "source_run_not_successful")
    need(run.get("head_branch") == "main" and
         isinstance(run.get("head_sha"), str) and
         SHA.fullmatch(run["head_sha"]), "source_run_wrong_code_branch")
    need(run.get("repository", {}).get("full_name") == REPO,
         "source_run_wrong_repository")
    need(run.get("name") == WORKFLOW_NAME and
         run.get("path") == WORKFLOW, "source_run_wrong_workflow")
    need(run.get("html_url") ==
         "https://github.com/" + REPO + "/actions/runs/" + str(run["id"]),
         "source_run_url_mismatch")
    created = event_day(run.get("created_at"))
    started = event_day(run.get("run_started_at"))
    need(abs((started - created).days) <= 1,
         "source_run_event_timestamp_inconsistent")
    return created, started

def attest(state_dir, run, *, expected_remote_head):
    """Join authentic run JSON with a clean, pinned Git source branch checkout.

    Trust boundary: caller MUST obtain run JSON from authenticated GitHub REST,
    not from the Git repository, and MUST separately pin remote branch SHA.
    """
    created, started = assert_genuine_run(run)
    need(type(expected_remote_head) is str and
         SHA.fullmatch(expected_remote_head), "source_remote_head_missing")
    state_dir = Path(state_dir).resolve(strict=True)
    need((state_dir / ".git").exists(), "source_checkout_missing_git")
    need(git(state_dir, "symbolic-ref", "--short", "HEAD").strip() ==
         "shadow/us-bis-homepage", "source_checkout_wrong_branch")
    head = git(state_dir, "rev-parse", "HEAD").strip()
    need(head == expected_remote_head, "source_remote_head_moved")
    need(not git(state_dir, "status", "--porcelain", "--untracked-files=all").strip(),
         "source_checkout_dirty")
    # Find the exact Actions run+attempt marker, not a date-only or "green" receipt.
    matching = []
    history = git(state_dir, "rev-list", "--max-count=" + str(MAX_HISTORY+1),
                  "HEAD").splitlines()
    need(1 <= len(history) <= MAX_HISTORY, "source_commit_history_unbounded")
    marker = ("Actions run: https://github.com/" + REPO +
              "/actions/runs/" + str(run["id"]) + "/attempts/" +
              str(run["run_attempt"]))
    for commit in history:
        need(SHA.fullmatch(commit) is not None, "invalid_git_commit_identity")
        message = git(state_dir, "show", "-s", "--format=%B", commit)
        if marker in message.splitlines():
            matching.append((commit, message))
    need(len(matching) == 1, "scheduled_run_commit_missing_or_replayed")
    commit, message = matching[0]
    title = "BIS: genuine scheduled homepage metadata "
    lines = message.splitlines()
    need(lines and lines[0].startswith(title), "source_commit_wrong_subject")
    day = lines[0][len(title):]
    need(DAY.fullmatch(day) is not None, "source_commit_invalid_day")
    try:
        d = date.fromisoformat(day)
    except ValueError:
        raise BISAttestationHold("source_commit_invalid_day") from None
    need(abs((d - started).days) <= 1 and
         abs((d - created).days) <= 1,
         "source_receipt_day_outside_run")
    need(lines.count("Actions event: schedule") == 1 and
         lines.count(marker) == 1, "source_commit_event_mismatch")
    digests = [line.removeprefix("Source listing SHA-256: ")
               for line in lines if line.startswith("Source listing SHA-256: ")]
    need(len(digests) == 1 and
         re.fullmatch(r"[0-9a-f]{64}", digests[0]) is not None,
         "source_commit_listing_digest_missing")
    file_path = "observations/" + day + ".json"
    delta = git(state_dir, "diff-tree", "--root", "--no-commit-id",
                "--name-status", "-r", commit).splitlines()
    allowed = {"A\t" + file_path, "A\tREADME.md"}
    need("A\t" + file_path in delta and
         len(delta) in (1,2) and set(delta).issubset(allowed),
         "source_commit_has_unapproved_mutation")
    # A later change or deletion of this once-written day is not admissible.
    touches = git(state_dir, "log", "--format=%H", "HEAD", "--",
                  file_path).splitlines()
    need(touches == [commit], "source_receipt_mutated_after_creation")
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(state_dir), "show", commit + ":" + file_path],
            stderr=subprocess.DEVNULL, timeout=15)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise BISAttestationHold("source_receipt_unreadable") from None
    need(0 < len(raw) <= 120000, "source_receipt_size_invalid")
    try:
        packet = json.loads(raw)
        count = verify(packet, expected_day=day)
    except (ValueError, UnicodeError, BISHold, TypeError, KeyError):
        raise BISAttestationHold("source_receipt_packet_untrusted") from None
    need(packet["official_listing_sha256"] == digests[0],
         "source_receipt_digest_disagrees_with_commit")
    # Return only metadata. The branch is unqualified, and no database is touched.
    return {
        "status": "PASS_GENUINE_SCHEDULED_SOURCE_METADATA_RECEIPT",
        "source_branch_head": head,
        "source_commit": commit,
        "source_run_id": run["id"],
        "source_run_attempt": run["run_attempt"],
        "receipt_day": day,
        "official_listing_sha256": digests[0],
        "verified_official_link_rows": count,
        "source_html_independently_rehashed": False,
        "qualified_clean_day_streak": False,
        "live_sqlite_admission_authorized": False,
        "public_site_publishing_authorized": False,
    }

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-checkout", required=True)
    ap.add_argument("--authenticated-run-json", required=True)
    ap.add_argument("--expected-remote-head", required=True)
    args = ap.parse_args(argv)
    try:
        path = Path(args.authenticated_run_json)
        need(path.is_file() and not path.is_symlink() and
             0 < path.stat().st_size <= 160000, "run_json_missing_or_unsafe")
        run = json.loads(path.read_text(encoding="utf-8"))
        report = attest(args.source_checkout, run,
                        expected_remote_head=args.expected_remote_head)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (BISAttestationHold, OSError, ValueError, TypeError,
            UnicodeError, KeyError) as exc:
        print(json.dumps({"status": "HOLD_SCHEDULED_SOURCE_ATTESTATION",
                          "reason": str(exc), "live_records_written": 0,
                          "site_modified": False}, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
