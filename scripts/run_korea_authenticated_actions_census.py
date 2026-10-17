"""Manual read-only GitHub Actions census; no publisher or source-body access.

Requires a scoped GitHub Actions token and a *separate pinned* sparse checkout
of the Korea shadow ledger directory. All GitHub API requests are authenticated
over HTTPS; the scan still cannot attest historical API retention or approve
human review, text reuse, source admission or a public release.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts import audit_korea_actions_attempts as census
from scripts import audit_indonesia_shadow_provenance as provenance

REPO = "VSSpowerlifting/IndoPacificRecord"
WORKFLOW = provenance.WORKFLOW_ID
API = "https://api.github.com/repos/" + REPO
MAX_WORKFLOW_RUNS = 2000
MAX_ARTIFACTS = 100
START = date(2026, 10, 6)
SHA = re.compile(r"[0-9a-f]{40}\Z")


def require(ok, message):
    if not ok:
        raise provenance.ProvenanceError(message)


def github_json(url, token):
    """One bounded, authenticated GitHub API JSON object; never print token."""
    require(type(token) is str and bool(token), "GitHub Actions token required")
    require(url.startswith(API + "/actions/"), "unrecognized GitHub API route")
    request = Request(
        url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ipr-korea-census",
        })
    try:
        with urlopen(request, timeout=20) as response:
            require(response.status == 200, "GitHub API non-success status")
            raw = response.read(8_000_001)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise provenance.ProvenanceError("GitHub API request failed") from exc
    require(len(raw) <= 8_000_000, "oversized GitHub API response")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise provenance.ProvenanceError("malformed GitHub API JSON") from exc
    require(type(payload) is dict, "GitHub API response was not an object")
    return payload


def fetch_authenticated(get, as_of_utc):
    """Load *all* retained runs for this exact workflow, then all scoped artifacts.

    get(url) is injectable so tests never access GitHub. A changing total,
    repeated run ID, pagination cap, expired artifact or malformed API response
    is an explicit HOLD. Date filtering occurs only *after* full pagination.
    """
    now = provenance.utc(as_of_utc)
    require(START <= now.date() <= date(2026, 11, 7),
            "Korea first-month census outside bounded window")
    runs = []
    total = None
    page_num = 1
    while True:
        url = (API + "/actions/workflows/%d/runs?per_page=100&page=%d" %
               (WORKFLOW, page_num))
        result = get(url)
        require(type(result) is dict and type(result.get("total_count")) is int
                and 0 <= result["total_count"] <= MAX_WORKFLOW_RUNS
                and type(result.get("workflow_runs")) is list
                and len(result["workflow_runs"]) <= 100,
                "malformed or oversized workflow-run response")
        if total is None:
            total = result["total_count"]
        require(result["total_count"] == total,
                "workflow history changed during pagination")
        runs.extend(result["workflow_runs"])
        require(len(runs) <= total, "workflow run pagination overrun")
        if len(runs) == total:
            break
        require(len(result["workflow_runs"]) == 100 and
                page_num < MAX_WORKFLOW_RUNS // 100,
                "incomplete workflow pagination")
        page_num += 1
    require(len({x.get("id") for x in runs if type(x) is dict}) == len(runs),
            "missing, duplicate or malformed workflow run identifier")
    selected = []
    for run in runs:
        require(type(run) is dict and
                run.get("workflow_id") == WORKFLOW and
                run.get("name") == provenance.WORKFLOW_NAME,
                "foreign run in authenticated workflow listing")
        created = provenance.utc(run.get("created_at"))
        if START <= created.date() and created <= now:
            selected.append(run)

    artifact_pages = {}
    for run in selected:
        ident = run["id"]
        require(type(ident) is int and ident > 0,
                "unrecognized workflow run identifier")
        path = API + "/actions/runs/%d/artifacts?per_page=100&page=1" % ident
        payload = get(path)
        require(type(payload) is dict and
                type(payload.get("total_count")) is int and
                type(payload.get("artifacts")) is list and
                0 <= payload["total_count"] <= MAX_ARTIFACTS and
                payload["total_count"] == len(payload["artifacts"]),
                "incomplete per-run artifact listing")
        require(all(type(item) is dict and item.get("expired") is False
                    for item in payload["artifacts"]),
                "expired or malformed Actions artifact")
        artifact_pages[str(ident)] = payload

    return {
        "pages": [{"total_count": len(selected), "workflow_runs": selected}],
        "artifacts": artifact_pages, "total_repository_workflow_runs": total,
        "api_pages_read": page_num, "scoped_runs": len(selected),
        "as_of_utc": now.isoformat().replace("+00:00", "Z"),
    }


def pinned_ledger_checkout(folder):
    """Read ledger JSON only from a separate exact-commit shadow checkout."""
    folder = Path(folder)
    require(folder.is_dir() and not folder.is_symlink(),
            "pinned shadow checkout absent or symlinked")
    process = subprocess.run(
        ["git", "-C", str(folder), "rev-parse", "--verify", "HEAD"],
        capture_output=True, text=True, check=False, timeout=10)
    require(process.returncode == 0 and
            bool(SHA.fullmatch(process.stdout.strip())),
            "unable to pin shadow Git commit")
    commit = process.stdout.strip()
    branch = subprocess.run(
        ["git", "-C", str(folder), "branch", "--show-current"],
        capture_output=True, text=True, check=False, timeout=10)
    require(branch.returncode == 0 and
            branch.stdout.strip() == "shadow/korea-policy-briefing",
            "checkout is not on the isolated Korea shadow branch")
    directory = folder / "state" / "ledger"
    require(directory.is_dir() and not directory.is_symlink(),
            "Korea state ledger directory absent or symlinked")
    paths = sorted(directory.glob("*.json"))
    require(1 <= len(paths) <= 70 and all(p.is_file() and not p.is_symlink()
                for p in paths), "missing or unsafe Korea state ledgers")
    ledgers = []
    for path in paths:
        require(path.stat().st_size <= 100_000, "oversized Korea ledger")
        ledgers.append(json.loads(path.read_text(encoding="utf-8")))
    return commit, ledgers


def produce(get, shadow_state, now):
    evidence = fetch_authenticated(get, now)
    commit, ledgers = pinned_ledger_checkout(shadow_state)
    result = census.scan(
        evidence["pages"], evidence["artifacts"], ledgers,
        as_of_utc=evidence["as_of_utc"])
    from scripts.korea_authenticated_prospective_seven import evaluate
    rolling = evaluate(evidence["pages"], evidence["artifacts"], ledgers,
                       as_of_utc=evidence["as_of_utc"])
    result.update({
        "observed_git_state_commit": commit,
        "api_workflow_history_total": evidence["total_repository_workflow_runs"],
        "api_workflow_pages_read": evidence["api_pages_read"],
        "github_api_request_authenticated": True,
        "api_scope": "exact_workflow_id_full_retained_history_and_each_run_artifact_list",
        "github_retention_completeness_certified": False,
        "independent_human_review_completed": False,
        "prospective_seven_slot_observation": rolling,
    })
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--shadow-checkout", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    require(os.environ.get("GITHUB_REPOSITORY") == REPO,
            "manual census must execute in exact repository")
    token = os.environ.get("GH_TOKEN")
    require(bool(token), "missing Actions read-only token")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = produce(lambda url: github_json(url, token), args.shadow_checkout, now)
    output = args.output.expanduser()
    require(output.is_absolute() and not output.exists() and
            output.parent.is_dir() and not output.parent.is_symlink() and
            not output.is_symlink(),
            "report path must be a new absolute safe file")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(output, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({
        "as_of_utc": report["as_of_utc"],
        "observed_git_state_commit": report["observed_git_state_commit"],
        "verdict": report["verdict"], "holds": report["holds"],
        "counts": report["counts"],
        "rolling_seven_candidate": report["prospective_seven_slot_observation"]["seven_day_actions_and_ledger_candidate"],
        "rolling_seven_missing_or_invalid_dates": report["prospective_seven_slot_observation"]["unqualified_dates"],
        "october_12_original_failure_remains_unrepaired": True,
        "human_day7_review_completed": False, "production_eligible": False,
    }, sort_keys=True))
    return 1 if report["holds"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
