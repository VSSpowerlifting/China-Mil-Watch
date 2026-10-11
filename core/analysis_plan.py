"""Deterministic metadata-only analysis plans shared by Daily and private preview."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path
from zoneinfo import ZoneInfo

from processing.screening import profile_for_desk

SCHEMA = "ipr-analysis-plan/1"


def code_identity():
    root = Path(__file__).resolve().parents[1]
    paths = ("core/analysis_plan.py", "analysis/admission.py", "analysis/analyzer.py",
             "analysis/prompts.py", "analysis/pricing.py", "pipeline.py", "config.py",
             "storage/db.py", "processing/screening.py", "core/processing_state.py")
    return digest({p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Policy:
    evaluated_at: str
    cap: int = 55
    reserve: float = 0.3
    live_days: int = 14
    mode: str = "compatibility"
    timezone: str = "UTC"
    budget_usd: Optional[str] = None

    def validate(self):
        instant = datetime.fromisoformat(self.evaluated_at.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("plan evaluation requires an explicit timezone")
        ZoneInfo(self.timezone)
        if (type(self.cap) is not int or self.cap < 1 or
                type(self.live_days) is not int or self.live_days < 0 or
                isinstance(self.reserve, bool) or not 0 <= self.reserve <= 1 or
                self.mode not in ("compatibility", "age-aware")):
            raise ValueError("invalid analysis policy")
        if self.budget_usd is not None:
            from analysis.admission import money
            money(self.budget_usd)
        return instant.astimezone(timezone.utc)


@dataclass(frozen=True)
class Candidate:
    record_id: int
    source_slug: str
    desk_id: Optional[str]
    url: str
    lane: str
    title: str
    body: str
    scraped_at: Optional[str] = None
    processing_state: Optional[str] = None
    attempts: Optional[int] = None
    analyzed_at: Optional[str] = None
    passed_relevance: Optional[int] = None
    state_identity: Optional[str] = None

    def identity(self):
        """Bind malformed SQLite text BLOBs without serializing their bytes.

        Preserve the existing identity for ordinary text inputs. A separate
        reserved field makes BLOB storage distinct from NULL or text values;
        only the resulting digest is exported, never this payload.
        """
        payload = asdict(self)
        blobs = {}
        for field in ("title", "body"):
            value = payload[field]
            if isinstance(value, bytes):
                payload[field] = None
                blobs[field] = {"sha256": hashlib.sha256(value).hexdigest(),
                                "byte_length": len(value)}
        if blobs:
            payload["_sqlite_blob_fields"] = blobs
        return payload

    def safe(self):
        # No source text, title, URL, prompt or response is exported. Locators
        # may contain secrets; only a digest of the complete input leaves memory.
        return {k: v for k, v in asdict(self).items()
                if k not in ("title", "body", "url")}


def disposition(c):
    if c.analyzed_at:
        return "completed"
    if c.passed_relevance == 0:
        return "relevance-rejected"
    if c.processing_state in ("paused", "terminal"):
        return c.processing_state
    if c.processing_state not in (None, "", "retriable"):
        return "unknown-processing-state"
    if not profile_for_desk(c.desk_id).daily_queue:
        return "desk-policy-hold"
    if not isinstance(c.body, str) or not c.body.strip():
        return "blank-body"
    return None


def build_plan(candidates, policy, *, code_identity, pricing_identity,
               snapshot_kind="stored snapshot", snapshot_identity=None, execution_settings=None,
               capacity=None):
    instant = policy.validate()
    if snapshot_kind not in ("stored snapshot", "after collection", "simulation"):
        raise ValueError("invalid snapshot kind")
    ids = set()
    identities = set()
    for c in candidates:
        if (type(c.record_id) is not int or c.record_id <= 0 or not c.source_slug
                or not c.url or c.lane not in ("new", "pending", "unscored", "stored")):
            raise ValueError("invalid or missing candidate identity")
        key = (c.desk_id, c.source_slug, c.url)
        if c.record_id in ids or key in identities:
            raise ValueError("duplicate candidate identity")
        ids.add(c.record_id)
        identities.add(key)
    cutoff = (instant - timedelta(days=policy.live_days)).strftime("%Y-%m-%d")
    reasons = {c.record_id: disposition(c) for c in candidates}
    ready = [c for c in candidates if reasons[c.record_id] is None]
    new = [c for c in ready if c.lane == "new"]
    pending = sorted((c for c in ready if c.lane == "pending"), key=lambda c: c.record_id)
    unscored = sorted((c for c in ready if c.lane == "unscored"), key=lambda c: c.record_id)
    live = [c for c in unscored if (c.scraped_at or "")[:10] >= cutoff]
    archive = [c for c in unscored if (c.scraped_at or "")[:10] < cutoff]
    if any(c.lane == "stored" for c in ready):
        raise ValueError("dispatchable candidate missing queue lane")
    backlog = pending + live + archive
    # The alternative changes only backlog ordering, at the same reserve and
    # cap. Old archive records can displace live-window/pending work; new work
    # keeps its allocation. Missing waiting timestamps sort last, never as old.
    if policy.mode == "age-aware":
        backlog = sorted(backlog, key=lambda c: (not c.scraped_at,
                                                c.scraped_at or "", c.record_id))
    slots = min(len(backlog), max(1, round(policy.cap * policy.reserve))) if backlog else 0
    new_take = new[:policy.cap - slots]
    backlog_take = backlog[:policy.cap - len(new_take)]
    selected = new_take + backlog_take
    selected_ids = [c.record_id for c in selected]
    for c in ready:
        if c.record_id not in selected_ids:
            reasons[c.record_id] = ("allocation-deferral" if c.lane == "new" and slots
                                    else "cap-deferral")
    records = [{**c.safe(), "reason": reasons[c.record_id],
                "selected": c.record_id in selected_ids} for c in candidates]
    policy_record = asdict(policy)
    if policy.budget_usd is not None:
        from analysis.admission import canonical, money
        policy_record["budget_usd"] = canonical(money(policy.budget_usd))
    plan = {
        "schema": SCHEMA, "snapshot_kind": snapshot_kind,
        "snapshot_identity": snapshot_identity,
        "input_identity": digest([c.identity() for c in candidates]),
        "code_identity": code_identity, "pricing_identity": pricing_identity,
        "execution_settings": execution_settings or {}, "capacity": capacity,
        "policy": policy_record, "cutoff_utc_day": cutoff,
        "queue_age_measure": "scraped_at (stored UTC timestamp), not publication date",
        "selected_ids": selected_ids, "records": records,
        "counts": {"stored": len(candidates), "eligible": len(ready),
                   "planned": len(selected), "new_planned": len(new_take),
                   "backlog_planned": len(backlog_take),
                   "deferred": len(ready) - len(selected), "held": len(candidates) - len(ready)},
        "reasons": dict(sorted(Counter(r for r in reasons.values() if r).items())),
        "capacity_evidence": "request admission not evaluated",
        "origin_authenticated": False, "spend_authorized": False,
    }
    plan["plan_id"] = digest(plan)
    return plan


def revalidate(plan, candidates, policy, **identities):
    fresh = build_plan(candidates, policy, **identities)
    if fresh != plan:
        raise ValueError("stale or altered analysis plan")
    return fresh


def inventory(conn, new_ids=()):
    """Canonical DAO query; new IDs retain insertion order, all others ID order."""
    from storage.db import get_analysis_inventory
    rows = get_analysis_inventory(conn)
    by_id = {r["id"]: r for r in rows}
    if len(set(new_ids)) != len(new_ids) or any(i not in by_id for i in new_ids):
        raise ValueError("invalid new-lane identity")
    ordered = [by_id[i] for i in new_ids] + [r for r in rows if r["id"] not in set(new_ids)]
    return [Candidate(r["id"], r["source_slug"], r["desk_id"], r["url"],
                      "new" if r["id"] in new_ids else
                      "pending" if r["passed_relevance"] == 1 and not r["analyzed_at"] else
                      "unscored" if r["passed_relevance"] is None else "stored",
                      r["title_original"] or "",
                      r["text_original"] if r["text_original"] is not None else "",
                      r["scraped_at"], r["processing_state"], r["processing_attempts"],
                      r["analyzed_at"], r["passed_relevance"],
                      digest({k: r[k] for k in ("processing_reason", "processing_first_failed_at", "processing_last_failed_at")})) for r in ordered]

