"""Strict *private* regional editorial slate contract; not a publication gate.

This module validates the provenance vocabulary of a proposed weekly slate.
It cannot verify actual publisher contents, copyright permission, factual
interpretation, AI rankings, collector health or human editorial approval.
Those remain separate upstream/downstream human-reviewed checks.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urlsplit

SCHEMA = "ipr-regional-editorial-slate/1"
STATES = frozenset((
    "reviewable", "no_qualifying_evidence", "awaiting_validation",
    "collector_unavailable",
))
LANES = frozenset(("production_record", "private_research"))
ROLES = frozenset(("new_week", "historical_context"))
SCORE_KEYS = frozenset((
    "strategic_significance", "evidence_strength", "analytical_novelty",
    "cross_desk_connection", "timeliness",
))
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
EXTERNAL_ID = re.compile(r"[A-Z]{2,8}-[A-Z0-9-]{3,64}\Z")
WEIGHTS = {
    "strategic_significance": 30,
    "evidence_strength": 25,
    "analytical_novelty": 20,
    "cross_desk_connection": 15,
    "timeliness": 10,
}


class SlateError(ValueError):
    """Internal candidate lacks required bounds or provenance."""


def _require(condition, reason):
    if not condition:
        raise SlateError(reason)


def _fields(obj, required, label):
    _require(isinstance(obj, dict) and set(obj) == set(required),
             label + ": missing or unexpected keys")


def _text(value, label, limit=600):
    _require(isinstance(value, str) and 1 <= len(value.strip()) <= limit
             and value == value.strip() and
             not any(ord(ch) < 32 or ord(ch) == 127 for ch in value),
             label + ": invalid text")


def _slug(value, label):
    _require(isinstance(value, str) and len(value) <= 90 and
             bool(SLUG.fullmatch(value)), label + ": invalid slug")


def _day(value):
    _require(isinstance(value, str), "date must be a string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SlateError("invalid calendar date") from exc
    _require(parsed.isoformat() == value, "date must be YYYY-MM-DD")
    return parsed


def _url(value):
    _text(value, "source URL", 2048)
    try:
        parsed = urlsplit(value)
        safe_port = parsed.port is None
    except ValueError as exc:
        raise SlateError("invalid source URL") from exc
    _require(parsed.scheme == "https" and bool(parsed.hostname) and
             safe_port and not parsed.username and not parsed.password and
             not parsed.fragment, "source must have a valid HTTPS URL")


def _source_id(item):
    ident = item["id"]
    if item["lane"] == "production_record":
        _require(type(ident) is int and ident > 0,
                 "production record IDs must be positive integers")
        _require(item["scope"] == "production_evidence",
                 "production lane/scope mismatch")
    else:
        _require(isinstance(ident, str) and bool(EXTERNAL_ID.fullmatch(ident)),
                 "private research IDs must remain typed strings")
        _require(item["scope"] == "private_drafting_candidate",
                 "research is not publication-approved")


def validate_slate(slate, *, expected_desks=()):
    """Return an already-valid slate unchanged; never mutate or authorize it.

    expected_desks, when supplied, must come from an independently checked
    registry snapshot. A slate cannot decide which desks exist.
    """
    _fields(slate, (
        "schema", "week_start", "week_ending", "coverage", "evidence",
        "candidates", "provisional_lead", "lead_rationale",
    ), "slate")
    _require(slate["schema"] == SCHEMA, "unknown slate schema")
    start, end = _day(slate["week_start"]), _day(slate["week_ending"])
    _require(start.weekday() == 6 and end == start + timedelta(days=6),
             "slate must cover exactly Sunday through Saturday")

    coverage = slate["coverage"]
    _require(isinstance(coverage, list) and bool(coverage),
             "empty coverage cannot mean institutional silence")
    desks = set()
    coverage_state = {}
    for row in coverage:
        _fields(row, ("desk", "state", "reason"), "coverage row")
        _slug(row["desk"], "desk")
        _require(row["desk"] not in desks, "duplicate desk coverage")
        _require(isinstance(row["state"], str) and row["state"] in STATES,
                 "unknown coverage state")
        _text(row["reason"], "coverage reason")
        _require("no activity" not in row["reason"].lower() and
                 "institutional silence" not in row["reason"].lower(),
                 "unobserved activity cannot be treated as no activity")
        desks.add(row["desk"])
        coverage_state[row["desk"]] = row["state"]
    if expected_desks:
        _require(len(expected_desks) == len(set(expected_desks)) and
                 desks == set(expected_desks), "registry/coverage mismatch")

    evidence = slate["evidence"]
    _require(isinstance(evidence, list), "invalid evidence array")
    identities, usable = set(), set()
    new_ids = set()
    for item in evidence:
        _fields(item, (
            "id", "desk", "lane", "scope", "source_url", "published_date",
            "role", "topic_suggestions",
        ), "source")
        _require(item["desk"] in desks, "source from undeclared desk")
        _require(isinstance(item["lane"], str) and item["lane"] in LANES and
                 isinstance(item["role"], str) and item["role"] in ROLES,
                 "invalid source lane or time role")
        _source_id(item)
        ident = item["id"]
        _require(ident not in identities, "duplicate evidence identity")
        identities.add(ident)
        _url(item["source_url"])
        pub = _day(item["published_date"])
        _require(pub <= end and (item["role"] != "new_week" or pub >= start),
                 "out-of-window or future publication")
        topics = item["topic_suggestions"]
        _require(isinstance(topics, list) and len(topics) <= 12 and
                 all(isinstance(v, str) for v in topics) and
                 len(set(topics)) == len(topics), "invalid topic suggestions")
        for topic in topics:
            _slug(topic, "provisional topic")
        if item["role"] == "new_week":
            _require(coverage_state[item["desk"]] == "reviewable",
                     "unverified/blocked desk cannot supply lead evidence")
            new_ids.add(ident)
            usable.add(item["desk"])
    for desk in desks:
        if coverage_state[desk] == "reviewable":
            _require(desk in usable, "reviewable desk has no in-week evidence")

    candidates = slate["candidates"]
    _require(isinstance(candidates, list) and len(candidates) <= 3,
             "internal slate may present up to three grounded themes")
    slugs = set()
    for item in candidates:
        _fields(item, (
            "slug", "thesis", "why_now", "source_ids", "counterevidence",
            "limitations", "topic_threads", "scores",
        ), "candidate theme")
        _slug(item["slug"], "candidate")
        _require(item["slug"] not in slugs, "duplicate candidate")
        slugs.add(item["slug"])
        for key in ("thesis", "why_now", "counterevidence", "limitations"):
            _text(item[key], key, 1000)
        ids = item["source_ids"]
        _require(isinstance(ids, list) and bool(ids) and
                 all(type(i) is int or isinstance(i, str) for i in ids) and
                 len(ids) == len(set(ids)) and
                 set(ids).issubset(identities) and bool(set(ids) & new_ids),
                 "candidate needs distinct, manifested in-week evidence")
        topics = item["topic_threads"]
        _require(isinstance(topics, list) and len(topics) <= 12 and
                 all(isinstance(v, str) for v in topics) and
                 len(topics) == len(set(topics)), "invalid related topic threads")
        for topic in topics:
            _slug(topic, "related topic")
        scores = item["scores"]
        _fields(scores, SCORE_KEYS, "heuristic scores")
        _require(all(type(value) is int and 0 <= value <= 5
                     for value in scores.values()), "scores must be 0..5 integers")

    lead = slate["provisional_lead"]
    if candidates:
        _require(isinstance(lead, str) and lead in slugs,
                 "provisional lead must identify a presented candidate")
    else:
        _require(lead is None, "empty slate must explicitly abstain")
    _text(slate["lead_rationale"], "lead or abstention rationale", 1200)
    return slate


def heuristic_score(scores):
    """Nonbinding 0..5 weighted triage; never authorizes the lead or publication."""
    _fields(scores, SCORE_KEYS, "heuristic scores")
    _require(all(type(v) is int and 0 <= v <= 5 for v in scores.values()),
             "scores must be 0..5 integers")
    return sum(scores[key] * WEIGHTS[key] for key in WEIGHTS) / 100
