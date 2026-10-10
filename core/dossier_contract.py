"""Offline, pure v1 contract for human-edited IPR Living Dossiers.

Only structural integrity and the self-consistency of an *asserted* approval
receipt are checked here. This module never admits an official source, checks
copyright permissions, authenticates a human editor, verifies real-world
events, or permits publication. Those are separate, independently trusted
gates in later phases. No source database or site renderer is imported.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DOSSIERS_DIR = ROOT / "dossiers"
SCHEMA = 1
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MARKUP = re.compile(r"<[^>]*>|[<{]%|{{|}}|!\[[^\]]*\]\([^)]+\)|\[[^\]]+\]\([^)]+\)")
KINDS = {"issuer_statement", "documented_publication", "editorial_interpretation"}
EVENT_BASES = {"planned", "reported", "retrospective", "uncertain"}
ROOT_FIELDS = {
    "dossier_schema", "slug", "title", "dek", "research_question",
    "editorial_status", "author_name", "editor_name", "prepared_on",
    "updated_on", "reviewed_on", "revision", "scope", "overview",
    "sources", "sections", "disagreements", "related_briefs",
    "related_timelines", "changes",
}
SCOPE_FIELDS = {
    "period_start", "period_end", "jurisdictions", "institutions",
    "included", "excluded", "method", "collection_limits",
}
SOURCE_FIELDS = {
    "record_id", "desk", "source_id", "institution_id", "language",
    "published_on", "url", "stored_original_sha256",
    "editorial_admission_ref", "source_use_decision_ref",
}
SECTION_FIELDS = {"id", "heading", "intro", "claims"}
CLAIM_FIELDS = {
    "id", "claim_kind", "text", "source_record_ids", "event_period",
    "limits", "counterevidence_ids",
}
EVENT_FIELDS = {"start", "end", "basis", "date_basis"}
DISAGREEMENT_FIELDS = {"id", "claim_ids", "status", "note"}
CHANGE_FIELDS = {"revision", "changed_on", "summary", "affected_claim_ids"}
APPROVAL_FIELDS = {"approved_by", "approved_on", "reference", "content_sha256"}


class DossierValidationError(ValueError):
    """A deterministic shape/parsing/approval-integrity failure; NOT a legal decision."""


def _fail(location, reason):
    raise DossierValidationError(f"{location}: {reason}")


def _object(value, fields, location, optional=frozenset()):
    if type(value) is not dict:
        _fail(location, "expected an object")
    if any(type(key) is not str for key in value):
        _fail(location, "all object keys must be strings")
    missing = set(fields) - set(value)
    unknown = set(value) - set(fields) - set(optional)
    if missing or unknown:
        _fail(location, f"missing {sorted(missing)}; unknown {sorted(unknown)}")
    return value


def _integer(value, location, *, minimum=0):
    if type(value) is not int or value < minimum:
        _fail(location, f"expected integer >= {minimum}")
    return value


def _text(value, location, *, limit=2500):
    if (type(value) is not str or not value or value != value.strip()
            or len(value) > limit):
        _fail(location, f"expected trimmed nonempty plain text <= {limit} characters")
    if unicodedata.normalize("NFC", value) != value:
        _fail(location, "text must use Unicode NFC")
    if any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value):
        _fail(location, "control characters not allowed")
    if MARKUP.search(value):
        _fail(location, "markup, links and template delimiters are not allowed")
    return value


def _slug(value, location):
    if type(value) is not str or len(value) > 80 or not SLUG.fullmatch(value):
        _fail(location, "unsafe stable slug")
    return value


def _day(value, location):
    if type(value) is not str or not DAY.fullmatch(value):
        _fail(location, "expected ISO YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(location, "invalid calendar date")


def _list(value, location, *, minimum=0, maximum=1000):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        _fail(location, f"expected list of length {minimum}..{maximum}")
    return value


def _unique(values, location):
    if len(values) != len(set(values)):
        _fail(location, "duplicate identifiers")


def _sorted_unique(values, location):
    _unique(values, location)
    if values != sorted(values):
        _fail(location, "must be in canonical ascending order")


def _slug_list(value, location, *, minimum=0):
    values = _list(value, location, minimum=minimum)
    for v in values:
        _slug(v, location)
    _sorted_unique(values, location)
    return values


def _record_ids(value, location, *, minimum=0):
    values = _list(value, location, minimum=minimum)
    for v in values:
        _integer(v, location, minimum=1)
    _sorted_unique(values, location)
    return values


def _sha(value, location):
    if type(value) is not str or not HEX64.fullmatch(value):
        _fail(location, "expected lowercase 64-hex digest")


def _url(value, location):
    _text(value, location, limit=2048)
    if any(c in value for c in ('\\', ' ', '\t')):
        _fail(location, "malformed original source URL")
    try:
        p = urlsplit(value)
        if (p.scheme not in {"http", "https"} or not p.netloc or not p.hostname
                or p.username is not None or p.password is not None or p.fragment):
            _fail(location, "requires safe original HTTP(S) URL")
        p.port  # Invalid ports fail as ValueError.
    except DossierValidationError:
        raise
    except ValueError:
        _fail(location, "malformed original source URL")


def _receipt(value, location):
    if value is None:
        return
    _text(value, location, limit=300)
    if re.search(r"\b(pending|unreviewed|tbd|unknown)\b", value, re.I):
        _fail(location, "placeholder is not a receipt")


def dossier_content_digest(sidecar):
    """SHA-256 of every authored field except approval; never a signature."""
    _object(sidecar, ROOT_FIELDS, "dossier", optional={"approval"})
    encoded = json.dumps(
        {k: v for k, v in sidecar.items() if k != "approval"},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_dossier_shape(sc):
    """Validate exact proposed v1 data shape, not admissibility or publication."""
    _object(sc, ROOT_FIELDS, "dossier", optional={"approval"})
    if type(sc["dossier_schema"]) is not int or sc["dossier_schema"] != SCHEMA:
        _fail("dossier_schema", "unsupported v1 contract")
    _slug(sc["slug"], "slug")
    for key in ("title", "dek", "research_question", "author_name",
                "editor_name", "overview"):
        _text(sc[key], key)
    for key in ("title", "dek", "research_question"):
        if len(sc[key]) > 500:
            _fail(key, "too long")
    if sc["editorial_status"] not in ("draft", "approved"):
        _fail("editorial_status", "must be draft or approved")
    prepared = _day(sc["prepared_on"], "prepared_on")
    updated = _day(sc["updated_on"], "updated_on")
    if prepared > updated:
        _fail("updated_on", "cannot precede preparation")
    reviewed = sc["reviewed_on"]
    if reviewed is not None:
        reviewed = _day(reviewed, "reviewed_on")
    revision = _integer(sc["revision"], "revision")

    scope = _object(sc["scope"], SCOPE_FIELDS, "scope")
    period_start = _day(scope["period_start"], "scope.period_start")
    period_end = _day(scope["period_end"], "scope.period_end")
    if period_start > period_end or period_end > updated:
        _fail("scope", "invalid or not-yet-observed scope period")
    _slug_list(scope["jurisdictions"], "scope.jurisdictions", minimum=1)
    _slug_list(scope["institutions"], "scope.institutions", minimum=1)
    for field in ("included", "excluded", "method", "collection_limits"):
        _text(scope[field], "scope." + field)

    sources = _list(sc["sources"], "sources", minimum=1, maximum=300)
    ledger_ids = []
    for i, source in enumerate(sources):
        at = f"sources[{i}]"
        _object(source, SOURCE_FIELDS, at)
        rid = _integer(source["record_id"], at + ".record_id", minimum=1)
        ledger_ids.append(rid)
        for key in ("desk", "source_id", "institution_id"):
            _slug(source[key], at + "." + key)
        _text(source["language"], at + ".language", limit=30)
        if _day(source["published_on"], at + ".published_on") > updated:
            _fail(at, "source publication date follows this version")
        _url(source["url"], at + ".url")
        _sha(source["stored_original_sha256"], at + ".stored_original_sha256")
        _receipt(source["editorial_admission_ref"], at + ".editorial_admission_ref")
        _receipt(source["source_use_decision_ref"], at + ".source_use_decision_ref")
    _sorted_unique(ledger_ids, "sources.record_ids")
    allowed_ids = set(ledger_ids)

    sections = _list(sc["sections"], "sections", minimum=2, maximum=30)
    section_ids = []
    all_claim_ids = []
    for i, section in enumerate(sections):
        at = f"sections[{i}]"
        _object(section, SECTION_FIELDS, at)
        section_ids.append(_slug(section["id"], at + ".id"))
        _text(section["heading"], at + ".heading", limit=180)
        _text(section["intro"], at + ".intro")
        claims = _list(section["claims"], at + ".claims", minimum=1, maximum=100)
        for j, claim in enumerate(claims):
            where = f"{at}.claims[{j}]"
            _object(claim, CLAIM_FIELDS, where)
            all_claim_ids.append(_slug(claim["id"], where + ".id"))
            if type(claim["claim_kind"]) is not str or claim["claim_kind"] not in KINDS:
                _fail(where + ".claim_kind", "invalid attribution class")
            _text(claim["text"], where + ".text")
            _text(claim["limits"], where + ".limits")
            positive = _record_ids(claim["source_record_ids"], where + ".source_record_ids", minimum=1)
            contrary = _record_ids(claim["counterevidence_ids"], where + ".counterevidence_ids")
            if not set(positive + contrary) <= allowed_ids:
                _fail(where, "claim cites a record absent from the source ledger")
            event = claim["event_period"]
            if event is not None:
                _object(event, EVENT_FIELDS, where + ".event_period")
                start = _day(event["start"], where + ".event_period.start")
                end = _day(event["end"], where + ".event_period.end")
                if start > end or start < period_start or end > period_end:
                    _fail(where + ".event_period", "out of selected scope or reversed interval")
                if type(event["basis"]) is not str or event["basis"] not in EVENT_BASES:
                    _fail(where + ".event_period.basis", "unsupported temporal basis")
                _text(event["date_basis"], where + ".event_period.date_basis")
    _unique(section_ids, "sections")
    _unique(all_claim_ids, "claims")
    known_claims = set(all_claim_ids)

    dispute_ids = []
    for i, dispute in enumerate(_list(sc["disagreements"], "disagreements", maximum=100)):
        at = f"disagreements[{i}]"
        _object(dispute, DISAGREEMENT_FIELDS, at)
        dispute_ids.append(_slug(dispute["id"], at + ".id"))
        claims = _slug_list(dispute["claim_ids"], at + ".claim_ids", minimum=2)
        if not set(claims) <= known_claims:
            _fail(at, "disagreement cites an orphan claim")
        if dispute["status"] not in ("unresolved", "reconciled"):
            _fail(at + ".status", "invalid comparison disposition")
        _text(dispute["note"], at + ".note")
    _unique(dispute_ids, "disagreements")
    _slug_list(sc["related_briefs"], "related_briefs")
    _slug_list(sc["related_timelines"], "related_timelines")

    changes = _list(sc["changes"], "changes", maximum=200)
    if len(changes) != revision:
        _fail("changes", "must provide one sequential revision note per released revision")
    prior = None
    for i, change in enumerate(changes):
        at = f"changes[{i}]"
        _object(change, CHANGE_FIELDS, at)
        if _integer(change["revision"], at + ".revision", minimum=1) != i + 1:
            _fail(at, "revisions must be 1..revision, without skips")
        d = _day(change["changed_on"], at + ".changed_on")
        if d < prepared or d > updated or (prior is not None and d < prior):
            _fail(at + ".changed_on", "reversed or out-of-range change history")
        prior = d
        _text(change["summary"], at + ".summary")
        ids = _slug_list(change["affected_claim_ids"], at + ".affected_claim_ids")
        if not set(ids) <= known_claims:
            _fail(at, "change note cites a noncurrent claim; explain removals in summary")
    if changes and prior != updated:
        _fail("changes", "latest change date must match updated_on")

    if sc["editorial_status"] == "draft":
        if "approval" in sc:
            _fail("approval", "draft cannot carry an approval")
    else:
        if revision < 1 or reviewed is None or reviewed < updated:
            _fail("approval", "approved revision requires human review of current content")
        _object(sc.get("approval"), APPROVAL_FIELDS, "approval")
        receipt = sc["approval"]
        _text(receipt["approved_by"], "approval.approved_by", limit=160)
        if receipt["reference"] is None:
            _fail("approval.reference", "a specific review receipt reference is required")
        _receipt(receipt["reference"], "approval.reference")
        if receipt["approved_by"] != sc["editor_name"] or re.search(
            r"\b(pending|unreviewed|codex|chatgpt|model|unknown)\b",
            receipt["approved_by"], re.I
        ):
            _fail("approval", "must name responsible human editor")
        if _day(receipt["approved_on"], "approval.approved_on") < reviewed:
            _fail("approval", "approval predates human review")
        _sha(receipt["content_sha256"], "approval.content_sha256")
        if receipt["content_sha256"] != dossier_content_digest(sc):
            _fail("approval", "exact editorial content digest no longer matches")
    return sc


def _unique_object_pairs(pairs):
    value = {}
    for key, member in pairs:
        if key in value:
            _fail("JSON", f"duplicate key: {key}")
        value[key] = member
    return value


def _nonfinite(value):
    _fail("JSON", f"non-finite numeric constant: {value}")


def read_dossier(path, source_dir=DOSSIERS_DIR):
    """Read only a direct canonical child; validate JSON and pure v1 shape."""
    path = Path(path)
    root = Path(source_dir)
    if (root.is_symlink() or path.is_symlink() or path.suffix != ".json"
            or path.parent.resolve() != root.resolve()
            or path.resolve().parent != root.resolve()):
        _fail("path", "must be a direct canonical JSON child, without symlinks")
    try:
        contents = path.read_text(encoding="utf-8")
        sc = json.loads(contents, object_pairs_hook=_unique_object_pairs,
                        parse_constant=_nonfinite)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail("JSON", type(exc).__name__ + ": unable to read valid UTF-8 JSON")
    validate_dossier_shape(sc)
    if sc["slug"] != path.stem:
        _fail("slug", "must match canonical filename")
    return sc
