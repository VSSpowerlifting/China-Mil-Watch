#!/usr/bin/env python3
"""Private read-only planning and one explicitly modeled offline comparison."""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.admission import (AdmissionController, AdmissionDeferred, SCHEMA as RUN_SCHEMA,
                                OUTCOMES, TOKEN_FIELDS, money, pricing_identity)
from analysis.admission import task_settings, capacity_estimate
from core.analysis_plan import (Candidate, Policy, SCHEMA as PLAN_SCHEMA,
                                build_plan, code_identity, digest, inventory)
from scripts import operations_center as ops
from scripts.audit_analysis_queue_by_source import _snapshot_file_hashes
from scripts.reconcile_db import read_only


def stored_plan(path, policy):
    path = Path(path)
    before = _snapshot_file_hashes(path)
    with read_only(path) as conn:
        candidates = inventory(conn)
        plan = build_plan(candidates, policy, code_identity=code_identity(),
                          pricing_identity=pricing_identity(), snapshot_identity=before,
                          execution_settings=task_settings(), capacity=capacity_estimate(task_settings(), policy.budget_usd))
    if _snapshot_file_hashes(path) != before:
        raise ValueError("database changed while planning")
    return plan


class PrivateRunJournal:
    """Owner-only write-ahead observations, never a recoverable allowance.

    Kept open on an exclusively created inode. Each complete line is fsynced
    before dispatch. A crash/truncated line means incomplete evidence; this
    writer never resumes an old file or transfers a previous run's allowance.
    """
    def __init__(self, path):
        self.path = ops.safe_destination(Path(path))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        self.fd = os.open(str(self.path), flags, 0o600)

    def __call__(self, packet):
        validate_packet(packet)
        data = (json.dumps(packet, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode()
        view = memoryview(data)
        while view:
            count = os.write(self.fd, view)
            if count <= 0:
                raise OSError("short private receipt write")
            view = view[count:]
        os.fsync(self.fd)

    def close(self):
        os.close(self.fd)


def _keys(obj, required):
    if type(obj) is not dict or set(obj) != set(required):
        raise ValueError("unsupported private receipt fields")


def validate_packet(packet):
    """Allowlisted export and accounting validation; never authenticate imports."""
    _keys(packet, ("plan", "run"))
    p, r = packet["plan"], packet["run"]
    _keys(p, ("schema", "snapshot_kind", "snapshot_identity", "input_identity", "code_identity",
              "pricing_identity", "policy", "cutoff_utc_day", "queue_age_measure", "selected_ids",
              "records", "counts", "reasons", "capacity_evidence", "origin_authenticated",
              "spend_authorized", "plan_id", "execution_settings", "capacity"))
    if p["schema"] != PLAN_SCHEMA or p["origin_authenticated"] is not False or p["spend_authorized"] is not False:
        raise ValueError("invalid planning authority")
    _keys(p["policy"], asdict(Policy("2026-10-11T00:00:00Z")))
    Policy(**p["policy"]).validate()
    identity = p["snapshot_identity"]
    if identity is not None:
        if p["snapshot_kind"] == "after collection":
            _keys(identity, ("native_run_id",))
            if type(identity["native_run_id"]) is not int or identity["native_run_id"] <= 0:
                raise ValueError("invalid native run identity")
        else:
            if type(identity) is not dict or not set(identity).issubset({"db", "wal", "shm"}) or "db" not in identity:
                raise ValueError("invalid snapshot identity fields")
            if any(not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v) for v in identity.values()):
                raise ValueError("invalid snapshot digest")
    if p["execution_settings"]:
        _keys(p["execution_settings"], ("tasks", "relevance_tool_enabled"))
        _keys(p["execution_settings"]["tasks"], ("relevance", "translation", "summary", "categorization"))
        for model, ceiling in p["execution_settings"]["tasks"].values():
            if not isinstance(model, str) or type(ceiling) is not int:
                raise ValueError("invalid execution settings")
        if type(p["execution_settings"]["relevance_tool_enabled"]) is not bool:
            raise ValueError("invalid tool setting")
    if p["capacity"] is not None:
        _keys(p["capacity"], ("evidence", "article_reservation_usd", "initial_articles_funded"))
        if p["capacity"]["evidence"] not in ("modeled-full-context-reservation", "unavailable-capacity-bound"):
            raise ValueError("invalid capacity evidence")
    if digest({k: v for k, v in p.items() if k != "plan_id"}) != p["plan_id"]:
        raise ValueError("altered plan digest")
    for row in p["records"]:
        _keys(row, ("record_id", "source_slug", "desk_id", "lane", "scraped_at", "processing_state",
                    "attempts", "analyzed_at", "passed_relevance", "state_identity", "reason", "selected"))
        if (type(row["record_id"]) is not int or type(row["selected"]) is not bool
                or not isinstance(row["source_slug"], str) or len(row["source_slug"]) > 128
                or row["desk_id"] is not None and not isinstance(row["desk_id"], str)):
            raise ValueError("invalid exported record identity")
    _keys(p["counts"], ("stored", "eligible", "planned", "new_planned", "backlog_planned", "deferred", "held"))
    if any(type(v) is not int or v < 0 for v in p["counts"].values()):
        raise ValueError("invalid planning counts")
    selected = p["selected_ids"]
    if (len(selected) != len(set(selected)) or p["counts"]["planned"] != len(selected)
            or len(p["records"]) != p["counts"]["stored"]
            or set(selected) != {row["record_id"] for row in p["records"] if row["selected"]}):
        raise ValueError("plan counts do not reconcile")
    c = p["counts"]
    if (c["eligible"] + c["held"] != c["stored"] or c["planned"] + c["deferred"] != c["eligible"]
            or c["new_planned"] + c["backlog_planned"] != c["planned"]
            or c["planned"] > p["policy"]["cap"]):
        raise ValueError("plan allocation does not reconcile")
    if r is None:
        return packet
    _keys(r, ("schema", "plan_id", "execution_id", "status", "pricing_identity", "budget_usd",
              "known_cost_usd", "pending_usd", "unresolved_usd", "unused_usd", "blocked",
              "calls", "articles", "origin_authenticated", "limits"))
    if (r["schema"] != RUN_SCHEMA or r["plan_id"] != p["plan_id"]
            or r["pricing_identity"] != p["pricing_identity"] or r["origin_authenticated"] is not False
            or r["status"] not in ("incomplete", "completed")
            or r["budget_usd"] != p["policy"]["budget_usd"]):
        raise ValueError("run/plan binding refused")
    amounts = [money(r[k]) for k in ("budget_usd", "known_cost_usd", "pending_usd", "unresolved_usd", "unused_usd")]
    budget, known, pending, unresolved, unused = amounts
    if known + pending + unresolved > budget and r["blocked"] != "exposure-breach":
        raise ValueError("unreported budget breach")
    if unused != max(money("0"), budget - known - pending - unresolved):
        raise ValueError("unused capacity does not reconcile")
    article_ids = set()
    for row in r["articles"]:
        _keys(row, ("record_id", "outcome", "admitted", "attempted", "deferral_reason"))
        if row["record_id"] not in selected or row["record_id"] in article_ids or row["outcome"] not in OUTCOMES:
            raise ValueError("invalid run outcome partition")
        article_ids.add(row["record_id"])
        if (type(row["admitted"]) is not bool or type(row["attempted"]) is not bool
                or row["attempted"] and not row["admitted"]
                or row["outcome"] in ("fully-analyzed", "relevance-rejected") and not row["attempted"]):
            raise ValueError("invalid article lifecycle")
    call_keys = set()
    measured, uncertain = money("0"), money("0")
    for call in r["calls"]:
        _keys(call, ("record_id", "task", "model", "request_identity", "reserved_usd", "known_cost_usd", "state", "tokens"))
        key = (call["record_id"], call["task"])
        if key in call_keys or call["record_id"] not in article_ids or call["task"] not in ("relevance", "translation", "summary", "categorization"):
            raise ValueError("invalid task receipt identity")
        call_keys.add(key)
        if call["state"] == "measured":
            _keys(call["tokens"], TOKEN_FIELDS)
            if any(type(v) is not int or v < 0 for v in call["tokens"].values()):
                raise ValueError("invalid token receipt")
            measured += money(call["known_cost_usd"])
        elif call["state"] == "unknown" and call["tokens"] is None and call["known_cost_usd"] is None:
            uncertain += money(call["reserved_usd"])
        else:
            raise ValueError("invalid call accounting state")
    if measured != known or uncertain != unresolved:
        raise ValueError("call costs do not reconcile")
    if r["status"] == "completed" and (article_ids != set(selected) or r["blocked"] or pending or unresolved
            or any(a["outcome"] in ("unknown", "incomplete", "unattempted") for a in r["articles"])):
        raise ValueError("incomplete run claimed completed")
    return packet


def validate_replay(report):
    _keys(report, ("schema", "evidence_class", "cap", "budget_usd", "scenario",
                   "historical_per_record_spend_available", "limits", "results"))
    if (report["schema"] != "ipr-analysis-replay/1" or report["evidence_class"] != "modeled"
            or report["historical_per_record_spend_available"] is not False
            or [r["policy"] for r in report["results"]] != ["compatibility", "age-aware"]):
        raise ValueError("unsupported replay evidence")
    for result in report["results"]:
        _keys(result, ("policy", "days", "remaining"))
        for day in result["days"]:
            _keys(day, ("evidence_class", "packet", "waiting_days", "source_desk_admissions"))
            validate_packet(day["packet"])
            p = day["packet"]["plan"]
            if (day["evidence_class"] != "modeled" or p["snapshot_kind"] != "simulation"
                    or p["policy"]["mode"] != result["policy"]
                    or p["policy"]["cap"] != report["cap"]
                    or p["policy"]["budget_usd"] != report["budget_usd"]):
                raise ValueError("unequal replay cap/envelope or unsupported evidence")
    return report


def read_packet(path):
    raw = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix == ".jsonl":
        if not raw.endswith("\n"):
            raise ValueError("interrupted private journal; no complete final receipt")
        packet = json.loads(raw.splitlines()[-1])
    else:
        packet = json.loads(raw)
    return validate_packet(packet)


def replay():
    """Identical fictional arrivals/outcomes, three days, equal cap/envelope.

    Uses the real planner/controller. Token values are declared synthetic
    assumptions, not historical measurements or invented aggregate allocation.
    Real analyzer/DAO execution is separately exercised by integration tests.
    """
    from config import ANALYSIS_MODEL, RELEVANCE_MODEL, TRANSLATION_MAX_TOKENS
    tasks = {"relevance": (RELEVANCE_MODEL, 500), "translation": (ANALYSIS_MODEL, TRANSLATION_MAX_TOKENS),
             "summary": (ANALYSIS_MODEL, 1000), "categorization": (ANALYSIS_MODEL, 500)}
    results = []
    for mode in ("compatibility", "age-aware"):
        queue = [Candidate(i, "fictional-a" if i % 2 else "fictional-b", "china",
                           "https://fictional.invalid/%d" % i, "unscored", "FICTIONAL", "FICTIONAL",
                           "2026-09-01T00:00:00+00:00" if i <= 4 else "2026-10-09T00:00:00+00:00")
                 for i in range(1, 9)]
        days = []
        for day in range(3):
            at = datetime(2026, 10, 11, tzinfo=timezone.utc) + timedelta(days=day)
            for i in range(20 + day * 4, 24 + day * 4):
                queue.append(Candidate(i, "fictional-a", "china", "https://fictional.invalid/%d" % i,
                                       "new", "FICTIONAL", "FICTIONAL", at.isoformat()))
            policy = Policy(at.isoformat(), cap=4, reserve=.5, mode=mode, budget_usd="24")
            plan = build_plan(queue, policy, code_identity=code_identity(), pricing_identity=pricing_identity(), snapshot_kind="simulation",
                              execution_settings=task_settings(), capacity=capacity_estimate(task_settings(), policy.budget_usd))
            guard = AdmissionController("24", plan_id=plan["plan_id"], execution_id="simulation:%s:%d" % (mode, day), sink=lambda x: None)
            done = set()
            for record_id in plan["selected_ids"]:
                try:
                    guard.prepare(record_id, tasks)
                    rejected = record_id % 3 == 0
                    for task, (model, ceiling) in tasks.items():
                        if rejected and task != "relevance": break
                        ticket = guard.dispatch(record_id, task, dict(model=model, messages=[{"role": "user", "content": "FICTIONAL"}], system=[], max_tokens=ceiling, temperature=0))
                        guard.response(ticket, SimpleNamespace(usage=SimpleNamespace(input_tokens=1000, output_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=0)))
                    guard.finish_article(record_id, "relevance-rejected" if rejected else "fully-analyzed")
                    done.add(record_id)
                except AdmissionDeferred:
                    guard.finish_article(record_id, "budget-deferred")
            guard.finish_run(plan["selected_ids"])
            packet = {"plan": plan, "run": guard.snapshot()}
            validate_packet(packet)
            waits = sorted((at - datetime.fromisoformat(c.scraped_at)).days for c in queue if c.record_id in done)
            exposure = Counter((c.source_slug, c.desk_id) for c in queue if c.record_id in done)
            days.append({"evidence_class": "modeled", "packet": packet, "waiting_days": waits,
                         "source_desk_admissions": [{"source_slug": s, "desk_id": d, "count": n} for (s, d), n in sorted(exposure.items())]})
            queue = [replace(c, lane="unscored") for c in queue if c.record_id not in done]
        results.append({"policy": mode, "days": days, "remaining": len(queue)})
    return {"schema": "ipr-analysis-replay/1", "evidence_class": "modeled", "cap": 4, "budget_usd": "24",
            "scenario": "Fictional two-source three-day arrivals; every third ID relevance-rejected; synthetic 1000 input/100 output tokens per call",
            "historical_per_record_spend_available": False,
            "limits": "Not measured throughput or editorial improvement; aggregate historical receipts are not per-record spend",
            "results": results}


def main(argv=None):
    from config import DB_PATH, DAILY_ANALYSIS_CAP, BACKLOG_RESERVE_FRACTION, LIVE_BACKLOG_DAYS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "replay"))
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--at", default="2026-10-11T00:00:00+00:00")
    parser.add_argument("--policy", choices=("compatibility", "age-aware"), default="compatibility")
    parser.add_argument("--budget-usd")
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        dest = ops.safe_destination(args.json)
        result = replay() if args.command == "replay" else {"plan": stored_plan(args.db, Policy(args.at, DAILY_ANALYSIS_CAP, BACKLOG_RESERVE_FRACTION, LIVE_BACKLOG_DAYS, args.policy, budget_usd=args.budget_usd)), "run": None}
        ops.write_private_reports(((dest, json.dumps(result, sort_keys=True, indent=2) + "\n"),))
    except (ValueError, OSError, ops.SnapshotError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
