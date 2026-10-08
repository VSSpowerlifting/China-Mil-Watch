"""Governed evidence chronologies. No collection, DB writes or automatic approval.

Dates are source-attributed editorial assertions, never inferred from a timestamp.
Validation proves identity and preserved excerpt parity, not the truth of a claim
or the accuracy of its English paraphrase. Those remain a human approval gate.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from core.desk_registry import load_registry
from scripts.reconcile_db import read_only

ROOT = Path(__file__).resolve().parent.parent
TIMELINES_DIR = ROOT / "timelines"
TIMELINE_SCHEMA = 1
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TimelineError(ValueError):
    pass


def _fail(where, reason):
    raise TimelineError("%s: %s" % (where, reason))


def _object(value, required, optional=(), where="timeline"):
    if not isinstance(value, dict):
        _fail(where, "expected an object")
    missing = set(required) - set(value)
    extra = set(value) - set(required) - set(optional)
    if missing or extra:
        _fail(where, "missing fields %s; unknown fields %s" % (sorted(missing), sorted(extra)))


def _text(value, where):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail(where, "expected nonempty, trimmed text")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        _fail(where, "control characters are forbidden")


def _slug(value, where):
    if not isinstance(value, str) or len(value) > 80 or not SLUG.fullmatch(value):
        _fail(where, "unsafe or malformed stable identifier")


def _date(value, where):
    if not isinstance(value, str) or not DATE.fullmatch(value):
        _fail(where, "expected an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(where, "invalid date")


def _list(value, where):
    if not isinstance(value, list) or not value:
        _fail(where, "expected a nonempty list")


def _url(value, where):
    _text(value, where)
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ("https", "http") or not parsed.hostname
                or parsed.username or parsed.password or parsed.fragment
                or any(c.isspace() for c in value) or "\\" in value):
            _fail(where, "expected a safe original HTTP(S) URL")
        parsed.port
    except ValueError:
        _fail(where, "malformed URL")


def content_digest(sidecar):
    """Approval binds every editorial field, including source identity and dates."""
    body = {k: v for k, v in sidecar.items() if k != "approval"}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_timeline(sc):
    """Strict v1 shape/date/provenance contract. Raises on the first problem."""
    _object(sc, ("timeline_schema", "slug", "title", "dek", "editorial_status",
                 "scope", "methodology_note", "updated_on", "reviewed_on",
                 "author_name", "editor_name", "entries", "related_briefs"),
            ("approval", "reconciliation"))
    if type(sc["timeline_schema"]) is not int or sc["timeline_schema"] != TIMELINE_SCHEMA:
        _fail("timeline_schema", "unsupported version")
    _slug(sc["slug"], "slug")
    for key in ("title", "dek", "scope", "methodology_note", "author_name", "editor_name"):
        _text(sc[key], key)
    reviewed = _date(sc["reviewed_on"], "reviewed_on")
    updated = _date(sc["updated_on"], "updated_on")
    if reviewed > updated:
        _fail("reviewed_on", "cannot follow updated_on")
    if sc["editorial_status"] not in ("draft", "approved"):
        _fail("editorial_status", "must be draft or approved")
    if sc["editorial_status"] == "draft" and "approval" in sc:
        _fail("approval", "a draft cannot carry approval")
    if sc["editorial_status"] == "approved":
        approval = sc.get("approval")
        _object(approval, ("approved_by", "approved_on", "reference", "content_sha256"), where="approval")
        for key in ("approved_by", "reference"):
            _text(approval[key], "approval." + key)
        if _date(approval["approved_on"], "approval.approved_on") < updated:
            _fail("approval", "approval predates this editorial version")
        if approval["approved_by"] != sc["editor_name"] or re.search(r"pending|unreviewed", sc["editor_name"], re.I):
            _fail("approval", "must name the actual editor")
        if approval["content_sha256"] != content_digest(sc):
            _fail("approval", "editorial content changed since approval")

    _list(sc["related_briefs"], "related_briefs")
    for slug in sc["related_briefs"]:
        _slug(slug, "related_briefs")
    if len(set(sc["related_briefs"])) != len(sc["related_briefs"]):
        _fail("related_briefs", "duplicate slug")
    _list(sc["entries"], "entries")
    ids, prior = set(), None
    for entry in sc["entries"]:
        _object(entry, ("id", "headline", "event", "event_kind", "observation", "evidence", "contested"),
                ("disagreement_note",), "entry")
        _slug(entry["id"], "entry.id")
        if entry["id"] in ids:
            _fail("entry.id", "duplicate ID")
        ids.add(entry["id"])
        for key in ("headline", "observation"):
            _text(entry[key], "entry." + key)
        if entry["event_kind"] not in ("occurrence", "report", "claim"):
            _fail("event_kind", "unknown kind")
        event = entry["event"]
        _object(event, ("start", "end", "precision", "date_basis"), where="event")
        start, end = _date(event["start"], "event.start"), _date(event["end"], "event.end")
        if start > end or end > updated:
            _fail("event", "reversed interval or event after editorial update")
        if event["precision"] not in ("day", "interval", "uncertain_interval"):
            _fail("event.precision", "unknown precision")
        if (event["precision"] == "day") != (start == end):
            _fail("event.precision", "must agree with the interval")
        _text(event["date_basis"], "event.date_basis")
        order = (event["start"], event["end"], entry["id"])
        if prior is not None and order <= prior:
            _fail("entries", "must be in deterministic chronological order (start, end, id)")
        prior = order
        if type(entry["contested"]) is not bool:
            _fail("contested", "expected a boolean")
        if entry["contested"] or "disagreement_note" in entry:
            _text(entry.get("disagreement_note"), "disagreement_note")
        _list(entry["evidence"], "evidence")
        seen = set()
        for ev in entry["evidence"]:
            _object(ev, ("record_id", "desk", "source_id", "institution_id", "published_on",
                         "url", "basis", "claim", "excerpt"), where="evidence")
            if type(ev["record_id"]) is not int or ev["record_id"] < 1 or ev["record_id"] in seen:
                _fail("evidence.record_id", "invalid or duplicate citation within entry")
            seen.add(ev["record_id"])
            for key in ("desk", "source_id", "institution_id"):
                _text(ev[key], "evidence." + key)
            for key in ("claim", "excerpt"):
                _text(ev[key], "evidence." + key)
            if len(ev["excerpt"]) < 12:
                _fail("evidence.excerpt", "too short to establish an attributable basis")
            published = _date(ev["published_on"], "evidence.published_on")
            if entry["event_kind"] == "report" and not start <= published <= end:
                _fail("event_kind", "a report entry must describe its source publication interval")
            if published > updated:
                _fail("evidence.published_on", "postdates editorial update")
            if ev["basis"] not in ("reported", "planned", "retrospective"):
                _fail("evidence.basis", "unknown attributed basis")
            if ev["basis"] == "planned" and published > start:
                _fail("evidence.basis", "a plan cannot postdate the event start")
            if ev["basis"] != "planned" and published < start:
                _fail("evidence.basis", "future events must be labelled planned")
            if ev["basis"] == "retrospective" and published <= end:
                _fail("evidence.basis", "a retrospective must follow the event interval")
            _url(ev["url"], "evidence.url")
    if "reconciliation" in sc and not isinstance(sc["reconciliation"], list):
        _fail("reconciliation", "expected a list")
    for panel in sc.get("reconciliation", []):
        _object(panel, ("heading", "note", "entry_ids"), where="reconciliation")
        for key in ("heading", "note"):
            _text(panel[key], "reconciliation." + key)
        _list(panel["entry_ids"], "reconciliation.entry_ids")
        for ident in panel["entry_ids"]:
            _slug(ident, "reconciliation.entry_ids")
        if len(set(panel["entry_ids"])) != len(panel["entry_ids"]) or not set(panel["entry_ids"]) <= ids:
            _fail("reconciliation", "duplicate or orphan entry references")
        if not any(e["contested"] for e in sc["entries"] if e["id"] in panel["entry_ids"]):
            _fail("reconciliation", "must identify a contested account")
    covered = {ident for p in sc.get("reconciliation", []) for ident in p["entry_ids"]}
    if any(e["contested"] and e["id"] not in covered for e in sc["entries"]):
        _fail("reconciliation", "each contested account requires a comparison panel")
    return sc


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            _fail("JSON", "duplicate key: " + key)
        obj[key] = value
    return obj


def read_timeline(path, source_dir=TIMELINES_DIR):
    path, root = Path(path), Path(source_dir).resolve()
    if path.is_symlink() or path.resolve().parent != root or path.suffix != ".json":
        _fail("path", "read the canonical timelines/<slug>.json source; no symlinks")
    sc = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
    validate_timeline(sc)
    if path.stem != sc["slug"]:
        _fail("slug", "must match the canonical filename")
    return sc


def reconcile_sources(sc, db_path, registry=None):
    """Resolve exact ID/desk/source/institution/date/URL and verbatim claim basis."""
    validate_timeline(sc)
    registry = registry or load_registry()
    eligible = {d.slug: {s.slug: s for s in d.sources if s.enabled and s.contract_validated}
                for d in registry if d.public and d.is_collecting and d.has_production_records}
    refs = [ev for entry in sc["entries"] for ev in entry["evidence"]]
    ids = sorted({ev["record_id"] for ev in refs})
    with read_only(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT a.id, a.title_original, a.title_english, a.text_original, "
            "a.published_date, a.url, s.slug AS source_id, s.desk_id AS desk, "
            "s.institution_id, s.display_name AS source_name, s.language_tag AS lang, "
            "s.enabled, i.display_name AS institution_name FROM articles a "
            "JOIN sources s ON s.id=a.source_id LEFT JOIN institutions i "
            "ON i.institution_id=s.institution_id WHERE a.id IN (%s)" %
            ",".join("?" for _ in ids), ids).fetchall()
    records = {row["id"]: dict(row) for row in rows}
    for ev in refs:
        rec = records.get(ev["record_id"])
        if rec is None:
            _fail("citation", "orphan record %s" % ev["record_id"])
        declared = eligible.get(rec["desk"], {}).get(rec["source_id"])
        if (not declared or not rec["enabled"] or declared.institution_id != rec["institution_id"]
                or declared.language_tag != rec["lang"]):
            _fail("citation", "record %s has shadow, unapproved or ambiguous provenance" % rec["id"])
        for field, stored in (("desk", "desk"), ("source_id", "source_id"),
                              ("institution_id", "institution_id"), ("url", "url"),
                              ("published_on", "published_date")):
            if ev[field] != rec[stored]:
                _fail("citation", "record %s mismatches %s" % (rec["id"], field))
        if not rec["title_original"] or not rec["lang"] or not rec["institution_name"]:
            _fail("citation", "record %s has incomplete preserved metadata" % rec["id"])
        if ev["excerpt"] not in (rec["text_original"] or ""):
            _fail("citation", "record %s excerpt is absent from the preserved original" % rec["id"])
    return records


def timeline_view(sc, records, related, is_review=False):
    """Derived periods/counts and sorted deduplicated source ledger."""
    result = dict(sc, route="timeline/%s.html" % sc["slug"], is_review=is_review)
    result["entries"] = [dict(e, evidence=[dict(ev, record=records[ev["record_id"]])
                                          for ev in sorted(e["evidence"], key=lambda x: (x["published_on"], x["record_id"]))])
                         for e in sc["entries"]]
    ledger = sorted(records.values(), key=lambda r: (r["published_date"], r["id"]))
    result.update(ledger=ledger, source_count=len(ledger), desk_count=len({r["desk"] for r in ledger}),
                  event_start=min(e["event"]["start"] for e in sc["entries"]),
                  event_end=max(e["event"]["end"] for e in sc["entries"]),
                  publication_start=ledger[0]["published_date"], publication_end=ledger[-1]["published_date"],
                  related=[related[s] for s in sc["related_briefs"]])
    result["publication_groups"] = [dict(date=d, records=[r for r in ledger if r["published_date"] == d])
                                    for d in sorted({r["published_date"] for r in ledger})]
    result["reconciliation"] = [dict(p, entries=[e for e in result["entries"] if e["id"] in p["entry_ids"]])
                                for p in sc.get("reconciliation", [])]
    return result


def load_timelines(db_path, related, source_dir=TIMELINES_DIR, review_path=None, registry=None):
    """Public selection is approved-only; an explicit private review adds one draft."""
    root = Path(source_dir).resolve()
    review = Path(review_path).resolve() if review_path else None
    if review_path and (Path(review_path).is_symlink() or review.parent != root):
        _fail("review", "review the canonical timeline sidecar")
    views, withheld, found = [], [], False
    for path in sorted(root.glob("*.json")):
        sc = read_timeline(path, root)
        selected = review == path.resolve()
        if selected:
            found = True
            if sc["editorial_status"] != "draft":
                _fail("review", "only an unpublished draft may be reviewed")
        if sc["editorial_status"] == "draft" and not selected:
            withheld.append(sc["slug"])
            continue
        for slug in sc["related_briefs"]:
            if slug not in related or related[slug].get("is_review"):
                _fail("related_briefs", "must resolve to an approved native Brief: " + slug)
        records = reconcile_sources(sc, db_path, registry)
        views.append(timeline_view(sc, records, related, selected))
    if review and not found:
        _fail("review", "canonical source not found")
    return sorted(views, key=lambda t: (t["updated_on"], t["slug"]), reverse=True), withheld
