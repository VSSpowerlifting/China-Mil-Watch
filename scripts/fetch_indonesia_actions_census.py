"""Authenticated, paginated Indonesia/Korea shared Actions attempt audit.

Queries only the repository's existing GitHub Actions workflow and stored
Git artifacts. Never contacts any government publisher, collects source
content, exports article bodies, or changes a production database.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts import audit_indonesia_actions_attempts as inventory
from scripts import audit_indonesia_shadow_provenance as provenance
from scripts.indonesia_operational_health import monitor_day

OWNER_REPO = "VSSpowerlifting/China-Mil-Watch"
WORKFLOW = provenance.WORKFLOW_ID
MAX_RUNS = 500
MAX_PAGES = 5
MAX_RESPONSE = 3_000_000
REPO_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class CensusError(ValueError):
    """Required authenticated Actions evidence is absent or ambiguous."""


def require(ok, reason):
    if not ok:
        raise CensusError(reason)


def endpoint(repo, route, query):
    require(repo == OWNER_REPO and REPO_PATTERN.fullmatch(repo),
            "unexpected repository scope")
    require(route.startswith("/actions/") and ".." not in route and
            "://" not in route and "#" not in route,
            "unsafe Actions API route")
    return ("https://api.github.com/repos/" + repo + route + "?" +
            urlencode(query))


def request_json(url, token):
    require(type(token) is str and 12 <= len(token) <= 512,
            "authenticated read-only GitHub token required")
    require(url.startswith("https://api.github.com/repos/" + OWNER_REPO + "/actions/"),
            "attempt to query outside repository Actions API")
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "IPR-Indonesia-ReadOnly-Actions-Census",
    })
    try:
        # Do not print exceptions: an unexpected URL or header could be embedded.
        with urlopen(request, timeout=30) as response:
            require(response.status == 200 and
                    response.geturl().startswith(
                        "https://api.github.com/repos/" + OWNER_REPO + "/actions/"),
                    "Actions API unexpectedly redirected or returned non-200")
            data = response.read(MAX_RESPONSE + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CensusError("GitHub Actions API request failed; audit cannot pass") from None
    require(len(data) <= MAX_RESPONSE, "Actions API response exceeds size cap")
    try:
        obj = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise CensusError("malformed Actions JSON response") from exc
    require(type(obj) is dict, "Actions API response not an object")
    return obj


def paginated(repo, route, query, collection, token, maximum):
    """Read every GitHub page and verify no cursor/total/ID was silently lost."""
    rows, expected = [], None
    for page in range(1, MAX_PAGES + 1):
        body = request_json(endpoint(repo, route, {
            **query, "per_page": 100, "page": page,
        }), token)
        count = body.get("total_count")
        chunk = body.get(collection)
        require(type(count) is int and 0 <= count <= maximum and
                type(chunk) is list and len(chunk) <= 100 and
                (expected is None or count == expected),
                "incomplete or unstable Actions API pagination")
        expected = count
        rows.extend(chunk)
        require(len(rows) <= expected, "Actions API returned more records than total")
        if len(rows) == expected:
            require(len({x.get("id") for x in rows if type(x) is dict}) ==
                    expected, "duplicate or malformed Actions row identity")
            return {"total_count": expected, collection: rows}
        require(len(chunk) == 100, "Actions API stopped before returning all pages")
    raise CensusError("bounded Actions pagination exhausted before completeness")


def export(repo, token, as_of, get_pages=paginated):
    """One inclusive Day 0..as_of+1 query (handles overnight queued runs)."""
    check = provenance.day(as_of)
    require(date(2026, 10, 6) <= check <= date.today() + timedelta(days=1),
            "historical or future audit date outside Indonesia's active window")
    end = check + timedelta(days=1)
    query = {"created": "2026-10-06.." + end.isoformat()}
    response = get_pages(
        repo, "/actions/workflows/%d/runs" % WORKFLOW, query,
        "workflow_runs", token, MAX_RUNS)
    runs = response["workflow_runs"]
    for row in runs:
        require(type(row) is dict and row.get("workflow_id") == WORKFLOW and
                row.get("name") == provenance.WORKFLOW_NAME and
                row.get("head_branch") == "main" and
                row.get("event") in ("schedule", "workflow_dispatch"),
                "unexpected workflow/branch/event in authenticated Actions inventory")
        created = provenance.utc(row.get("created_at")).date()
        require(date(2026, 10, 6) <= created <= end,
                "GitHub Actions created-date filter was incomplete")
    artifacts = {}
    for run in runs:
        run_id = run["id"]
        require(type(run_id) is int and run_id > 0, "malformed run identifier")
        data = get_pages(repo, "/actions/runs/%d/artifacts" % run_id, {},
                         "artifacts", token, 100)
        artifacts[str(run_id)] = data
    require(len(artifacts) == len(runs), "not all workflow artifacts checked")
    return [{"total_count": len(runs), "workflow_runs": runs}], artifacts


def audit(repo, token, state_repo, state_commit, as_of):
    pages, artifacts = export(repo, token, as_of)
    clock, ledgers, digest = provenance.pinned_state(state_repo, state_commit)
    # The generic pinned-state audit validates positive ledgers; the attempt
    # census separately checks missing or failed/cancelled/unattributed runs.
    bound = provenance.parse_actions_export(pages)
    positive = provenance.assess(clock, ledgers, digest, bound)
    counted = inventory.scan(pages, artifacts, ledgers, as_of=as_of)
    require(positive["pinned_db_sha256_checked"], "pinned database not verified")
    return {
        "schema": "ipr-indonesia-authenticated-actions-census/1",
        "as_of": as_of,
        "source_workflow_id": WORKFLOW,
        "pinned_state_commit": state_commit,
        "run_export_count": len(pages[0]["workflow_runs"]),
        "artifact_pages_verified": len(artifacts),
        "source": "authenticated_repository_GitHub_Actions_API",
        "result": counted,
        "independent_original_language_review": False,
        "rights_approved": False,
        "day7_human_review_completed": False,
        "production_eligible": False,
        "public_article_release_authorized": False,
        "mutation_count": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-repo", type=Path, required=True)
    parser.add_argument("--state-commit", required=True)
    parser.add_argument("--as-of", help="last nominal Indonesia UTC date to check")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    as_of = args.as_of or monitor_day().isoformat()
    report = None
    try:
        report = audit(OWNER_REPO, os.environ.get("GH_TOKEN", ""),
                       args.state_repo, args.state_commit, as_of)
        code = 0 if report["result"]["verdict"].startswith("CONSISTENT_") else 2
    except (CensusError, provenance.ProvenanceError, ValueError, KeyError,
            TypeError, OSError):
        # An exception cannot be promoted to a zero-defect audit. The error
        # code never includes request URL, token, publisher text, or raw rows.
        code = 2
        report = {
            "schema": "ipr-indonesia-authenticated-actions-census/1",
            "as_of": as_of,
            "verdict": "HOLD_UNVERIFIED_INPUTS",
            "production_eligible": False,
            "public_article_release_authorized": False,
            "mutation_count": 0,
        }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(report, ensure_ascii=False,
                                      indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
