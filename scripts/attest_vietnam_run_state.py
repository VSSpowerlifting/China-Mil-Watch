"""Read-only first Phase-0 Vietnam Actions/state-branch observation.

Manual operator command ONLY. A live invocation makes bounded GitHub REST GETs,
NOT ministry/publisher requests. It never runs the collector, writes source
bodies, changes state, signs checkpoint evidence, or approves publication.

Only verifies the *latest* immutable ledger against one Actions run attempt.
It does not prove complete attempt/slot history, publisher rights, source
coverage, original-language fidelity, or desk qualification.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

from core.shadow_schedule import scheduled_slot_date
from scripts.audit_shadow_workflow_bindings import validate as audit_bindings

ROOT = Path(__file__).resolve().parents[1]
REPO = "VSSpowerlifting/China-Mil-Watch"
PREFIX = "/repos/" + REPO
SOURCES = (
    "vn_mps_foreign_affairs_vi",
    "vn_moit_energy_vi",
    "vn_moit_foundational_industry_vi",
)
SCHEMA = "ipr-vietnam-actions-state-observation/1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
LEDGER = re.compile(r"[0-9]{8}T[0-9]{6}\+0000-[1-9][0-9]*-[1-9][0-9]*\.json\Z")
RUN_ID = re.compile(r"([1-9][0-9]*)-([1-9][0-9]*)\Z")
MAX_API_BYTES = 250000
MAX_LEDGER_FILES = 100


class AttestationHold(ValueError):
    """No affirmative observation is allowed after a contradiction."""


def require(condition, why):
    if not condition:
        raise AttestationHold(why)


def utc(value):
    require(isinstance(value, str), "missing run timestamp")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AttestationHold("invalid run timestamp") from exc
    require(d.tzinfo is not None and d.utcoffset().total_seconds() == 0,
            "run timestamp must have UTC offset")
    return d.astimezone(timezone.utc)


def sha_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


class GithubRead:
    """Fixed GitHub API domain, no redirect, auth token never logged."""
    def __init__(self, token=None):
        self.token = token

    def get(self, path):
        require(isinstance(path, str) and path.startswith(PREFIX + "/"),
                "non-repository API endpoint")
        require(".." not in path and "//" not in path, "malformed API path")
        url = "https://api.github.com" + path
        headers = {"Accept": "application/vnd.github+json",
                   "User-Agent": "IPR-Shadow-Observation/1",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(url, headers=headers, method="GET")

        class RejectRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, msg, h, redirected):
                return None
        try:
            with urllib.request.build_opener(RejectRedirect).open(req, timeout=15) as resp:
                require(resp.status == 200 and resp.geturl() == url, "GitHub API denied or redirected")
                payload = resp.read(MAX_API_BYTES + 1)
                require(len(payload) <= MAX_API_BYTES, "GitHub API response oversized")
                return json.loads(payload.decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, UnicodeError, ValueError):
            raise AttestationHold("GitHub API unavailable, denied or malformed") from None


def encoded_content(api, path, state_sha):
    obj = api.get(PREFIX + "/contents/" + path + "?ref=" + state_sha)
    require(isinstance(obj, dict) and obj.get("encoding") == "base64"
            and isinstance(obj.get("content"), str) and
            isinstance(obj.get("sha"), str),
            "pinned GitHub content envelope missing")
    try:
        raw = base64.b64decode(obj["content"], validate=False)
        # GitHub's multiline base64 is normal; reject non-canonical junk.
        require(base64.b64encode(raw).decode() ==
                "".join(obj["content"].split()), "non-canonical GitHub blob encoding")
    except (ValueError, base64.binascii.Error):
        raise AttestationHold("malformed content encoding") from None
    require(len(raw) <= MAX_API_BYTES and sha_blob(raw) == obj["sha"],
            "GitHub blob SHA or body bound mismatch")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise AttestationHold("pinned ledger/clock is not JSON") from None
    require(isinstance(data, dict), "pinned file is not a JSON object")
    return data


def pinned_head(api, branch):
    require(re.fullmatch(r"shadow/[a-z0-9_-]+", branch) is not None,
            "state branch not allowlisted")
    endpoint = PREFIX + "/git/ref/heads/" + branch
    r = api.get(endpoint)
    head = r.get("object", {}).get("sha") if isinstance(r, dict) else None
    require(isinstance(head, str) and SHA.fullmatch(head), "unverified state head")
    require(r.get("ref") == "refs/heads/" + branch, "state branch identity mismatch")
    return head


def exact_binding(source, bindings):
    rows = [x for x in bindings if x["source_slug"] == source]
    require(len(rows) == 1 and rows[0]["trigger"] == "scheduled" and
            rows[0]["state_branch"] and rows[0]["workflow"] and rows[0]["cron"],
            "source family is not an allowed scheduled binding")
    return rows[0]


def one_family(api, binding, as_of):
    """Return only GitHub-confirmed operational observation, NEVER full review."""
    branch = binding["state_branch"]
    head = pinned_head(api, branch)
    directory = api.get(PREFIX + "/contents/state/ledger?ref=" + head)
    require(isinstance(directory, list) and 1 <= len(directory) <= MAX_LEDGER_FILES,
            "missing or unbounded state ledger inventory")
    names = [x.get("name") for x in directory if isinstance(x, dict)]
    require(len(names) == len(directory) and len(names) == len(set(names)) and
            all(isinstance(n, str) and LEDGER.fullmatch(n) for n in names),
            "malformed or duplicate ledger inventory")
    latest = max(names)
    ledger = encoded_content(api, "state/ledger/" + latest, head)
    clock = encoded_content(api, "state/clock.json", head)
    require(ledger.get("source_slug") == binding["source_slug"] and
            ledger.get("desk_id") == "vietnam", "ledger source misbinding")
    date_str = ledger.get("target_date")
    try:
        logical = date.fromisoformat(date_str)
    except (TypeError, ValueError):
        raise AttestationHold("invalid logical source day") from None
    require(logical <= as_of and logical <= datetime.now(timezone.utc).date(),
            "latest source ledger is in the future")
    rid = ledger.get("run_id")
    match = RUN_ID.fullmatch(rid) if isinstance(rid, str) else None
    require(bool(match), "invalid source run/attempt identity")
    run_num, attempt_num = map(int, match.groups())
    run = api.get(PREFIX + "/actions/runs/" + str(run_num) +
                  "/attempts/" + str(attempt_num))
    require(isinstance(run, dict) and run.get("id") == run_num and
            run.get("run_attempt") == attempt_num and
            run.get("status") == "completed" and run.get("conclusion") == "success",
            "Actions attempt not an attested success")
    require(run.get("event") == "schedule" and
            isinstance(run.get("head_sha"), str) and SHA.fullmatch(run["head_sha"]),
            "not an identifiable scheduled Actions run")
    wf = run.get("path")
    require(isinstance(wf, str) and wf.split("@")[0] == binding["workflow"],
            "Actions workflow does not match source binding")
    started = utc(run.get("run_started_at"))
    # Binding map stores five-field GitHub cron; shared date resolver takes HH:MM.
    match_cron = re.fullmatch(r"([0-5]?[0-9]) (2[0-3]|1[0-9]|[0-9]) \\* \\* \\*",
                              binding["cron"])
    require(match_cron is not None, "unsupported source cron declaration")
    minute, hour = map(int, match_cron.groups())
    expected = scheduled_slot_date(started, "{:02d}:{:02d}".format(hour, minute))
    require(expected == logical, "scheduled-slot logical date mismatch")
    require(ledger.get("target_date_source") == "schedule-slot" and
            ledger.get("health") == "ok" and
            ledger.get("result") in ("ok", "ok_no_publications",
                                     "ok_all_duplicates", "ok_all_filtered"),
            "shadow ledger failed or has unsupported collection outcome")
    require(clock.get("day_zero_run_id") and clock.get("day_zero_utc") and
            utc(clock["day_zero_utc"]) <= started, "missing/invalid source-specific Day 0")
    require(ledger.get("day_zero_utc") == clock["day_zero_utc"],
            "source clock disagrees with signed ledger chronology")
    require(ledger.get("new_records") is not None and
            type(ledger["new_records"]) is int and ledger["new_records"] >= 0,
            "invalid source collection record count")
    anomalies = ledger.get("anomalies")
    source_anomalies = ledger.get("source_anomalies", [])
    require(isinstance(anomalies, list) and isinstance(source_anomalies, list),
            "invalid source anomaly evidence")
    # Prevent a branch ref moving mid-read from masquerading as a stable tip.
    require(pinned_head(api, branch) == head, "state branch moved during observation")
    review_flag = bool(anomalies or source_anomalies)
    return {
        "source_slug": binding["source_slug"],
        "state_branch": branch,
        "state_head_sha": head,
        "ledger_filename": latest,
        "run_id": rid,
        "actions_head_sha": run["head_sha"],
        "logical_date": date_str,
        "github_event": "schedule",
        "state_health": ledger["health"],
        "bounded_listing_result": ledger["result"],
        "new_records_in_observed_run": ledger["new_records"],
        "anomaly_count": len(anomalies) + len(source_anomalies),
        "observation_state": "needs_review" if review_flag else "verified_run_and_state_observation",
        "source_original_language_verified": False,
        "all_actions_attempts_audited": False,
        "state_hash_chain_fully_audited": False,
        "source_rights_verified": False,
        "human_checkpoint_signed": False,
        "eligible_for_production": False,
        "eligible_for_publication": False,
    }


def observe(api, *, as_of, binding_report=None):
    try:
        cutoff = date.fromisoformat(as_of)
    except (TypeError, ValueError):
        raise AttestationHold("invalid as-of date") from None
    require(cutoff <= datetime.now(timezone.utc).date(), "future as-of not allowed")
    report = binding_report if binding_report is not None else audit_bindings()
    require(report.get("schema") == "ipr-shadow-source-workflow-bindings/1" and
            report.get("declaration_only") is True and
            report.get("all_runs_attested") is False,
            "binding audit is not the accepted declaration report")
    binding_rows = report.get("sources")
    require(isinstance(binding_rows, list), "no source mapping")
    observations = [one_family(api, exact_binding(src, binding_rows), cutoff)
                    for src in SOURCES]
    runs = {r["run_id"] for r in observations}
    consistent = len(runs) == 1 and len({r["logical_date"] for r in observations}) == 1
    return {
        "schema": SCHEMA,
        "as_of": as_of,
        "scope": "three_existing_vietnam_ministry_shadow_families_only",
        "source_origin": "live_github_rest_read_only",
        "source_families_observed": len(observations),
        "shared_run_attempt_and_day": consistent,
        "cohort_state": "needs_review" if not consistent or
            any(r["observation_state"] == "needs_review" for r in observations)
            else "consistent_recent_observations_only",
        "sources": observations,
        "complete_action_attempt_history_verified": False,
        "full_30_day_continuity_verified": False,
        "human_source_review_verified": False,
        "private_source_use_approved": False,
        "public_collection_or_desk_promotion_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-github-read", action="store_true",
                        help="operator permits up to 18 fixed read-only GitHub API calls")
    parser.add_argument("--as-of", required=True, help="UTC YYYY-MM-DD cutoff")
    args = parser.parse_args(argv)
    if not args.approve_github_read:
        parser.error("No GitHub network calls without --approve-github-read")
    try:
        result = observe(GithubRead(token=os.environ.get("GITHUB_TOKEN")),
                         as_of=args.as_of)
    except AttestationHold as exc:
        print(json.dumps({"schema": SCHEMA, "observation_state": "blocked",
                          "reason": str(exc), "rights_or_collection_approved": False}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["cohort_state"] == "consistent_recent_observations_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
