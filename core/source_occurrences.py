"""Private metadata contracts. Candidate relationships never assert shared events."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from urllib.parse import parse_qsl, urlsplit
from typing import Optional


class OccurrenceError(ValueError):
    """Fixed diagnostics only: never interpolate input or parser errors."""


def require(condition, code):
    if not condition:
        raise OccurrenceError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value):
    try:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    except (UnicodeError, AttributeError):
        raise OccurrenceError("invalid_digest_input") from None


def valid_digest(value, optional=False):
    return (optional and value is None) or (type(value) is str and
           re.fullmatch(r"[0-9a-f]{64}", value) is not None)


def locator(value):
    require(type(value) is str and len(value) <= 8192 and
            not any(ord(c) < 32 for c in value), "invalid_locator")
    try:
        value.encode("utf-8")
        p = urlsplit(value)
        require(p.scheme in ("http", "https") and p.hostname and
                p.username is None and p.password is None, "invalid_locator")
        require(not any(re.search(r"token|secret|password|key|auth|signature", k, re.I)
                        for k, _ in parse_qsl(p.query)), "secret_locator_refused")
        _ = p.port
    except ValueError:
        raise OccurrenceError("invalid_locator") from None
    return value


def actual_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except (ValueError, TypeError):
        return None


def actual_time(value):
    if not value or type(value) is not str:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


@dataclass(frozen=True)
class Metadata:
    url: str
    supplied_url: str
    source_slug: Optional[str]
    desk_id: Optional[str]
    institution_id: Optional[str]
    identity_state: str
    supplied_identity_sha256: str
    published_date: Optional[str]
    supplied_date_sha256: str
    scraped_at: Optional[str]
    producer_retrieved_at: Optional[str]
    producer_capture_sha256: Optional[str]
    saved_input_bytes_sha256: Optional[str]
    extracted_title_sha256: Optional[str]
    title_state: str
    extracted_text_sha256: Optional[str]
    extracted_document_sha256: str
    normalized_text_sha256: Optional[str]
    title_group_sha1: str
    legacy_title_text_sha256: str
    stored_legacy_title_text_sha256: Optional[str]
    stored_hash_state: str
    body_state: str
    body_kind: str


@dataclass(frozen=True)
class Observation:
    observation_id: str
    position: int
    origin: str
    metadata: Metadata
    title_reason: str
    title_representative: Optional[str]
    url_hash_reason: str
    url_hash_representative: Optional[str]
    native_ids: tuple[int, ...]
    decision_native_ids: tuple[int, ...]


@dataclass(frozen=True)
class NativeRecord:
    native_id: int
    metadata: Metadata


@dataclass(frozen=True)
class Relation:
    kind: str
    key: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class Batch:
    schema_version: int
    batch_key_sha256: str
    execution_sha256: str
    input_sha256: str
    snapshot_sha256: str
    code_sha256: str
    code_git_head: str
    mode: str
    observations: tuple[Observation, ...]
    records: tuple[NativeRecord, ...]
    relations: tuple[Relation, ...]

    def as_dict(self):
        return asdict(self)


TITLE_REASONS = {"existing_archive_row", "missing_title_passthrough",
                 "title_selected", "title_suppressed"}
URL_REASONS = {"historical_decision_unknown", "not_reached", "batch_url_match",
               "batch_legacy_hash_match", "stored_url_match",
               "stored_legacy_hash_match", "prospective_survivor"}
RELATIONS = {"same_title_group", "exact_url", "equal_normalized_text",
             "equal_normalized_title_text"}


def validate_metadata(m):
    locator(m.url)
    locator(m.supplied_url)
    require(m.identity_state in {"verified_source", "unknown_identity"}, "invalid_metadata")
    identity = (m.source_slug, m.desk_id, m.institution_id)
    require(all(x is None for x in identity) if m.identity_state == "unknown_identity"
            else all(type(x) is str and re.fullmatch(r"[a-z0-9_-]{1,100}", x)
                     for x in identity), "invalid_metadata")
    for name in ("supplied_identity_sha256", "supplied_date_sha256",
                 "extracted_document_sha256",
                 "legacy_title_text_sha256"):
        require(valid_digest(getattr(m, name)), "invalid_metadata")
    for name in ("extracted_title_sha256", "extracted_text_sha256", "normalized_text_sha256",
                 "stored_legacy_title_text_sha256", "producer_capture_sha256",
                 "saved_input_bytes_sha256"):
        require(valid_digest(getattr(m, name), True), "invalid_metadata")
    require(m.title_state in {"missing", "blank", "extracted_title"} and
            (m.extracted_title_sha256 is None) == (m.title_state == "missing"), "invalid_metadata")
    require(m.title_group_sha1 == "" or re.fullmatch(r"[0-9a-f]{40}", m.title_group_sha1),
            "invalid_metadata")
    require(m.published_date is None or (type(m.published_date) is str and
            actual_date(m.published_date) == m.published_date), "invalid_metadata")
    require(m.scraped_at is None or actual_time(m.scraped_at) == m.scraped_at, "invalid_metadata")
    require(m.producer_retrieved_at is None or
            actual_time(m.producer_retrieved_at) == m.producer_retrieved_at, "invalid_metadata")
    require(m.body_state in {"missing", "blank", "extracted_text"} and
            (m.normalized_text_sha256 is not None) == (m.body_state == "extracted_text"),
            "invalid_metadata")
    require(m.body_kind in {"text", "media_only", "unavailable"} and
            (m.body_kind != "media_only" or m.body_state != "extracted_text"), "invalid_metadata")
    require(m.stored_hash_state in {"not_stored", "missing", "agrees", "disagrees"},
            "invalid_metadata")
    require(m.stored_hash_state != "agrees" or
            m.stored_legacy_title_text_sha256 == m.legacy_title_text_sha256, "invalid_metadata")
    require(m.stored_hash_state != "disagrees" or
            (m.stored_legacy_title_text_sha256 is not None and
             m.stored_legacy_title_text_sha256 != m.legacy_title_text_sha256), "invalid_metadata")


def validate_batch(batch):
    require(type(batch) is Batch and type(batch.schema_version) is int and batch.schema_version == 1 and
            batch.mode in {"archive_inventory", "observed_replay"}, "invalid_batch")
    for name in ("batch_key_sha256", "execution_sha256", "input_sha256",
                 "snapshot_sha256", "code_sha256"):
        require(valid_digest(getattr(batch, name)), "invalid_batch")
    require(re.fullmatch(r"[0-9a-f]{40}", batch.code_git_head) is not None, "invalid_batch")
    require(batch.execution_sha256 == digest(canonical([
        batch.batch_key_sha256, batch.mode, batch.input_sha256,
        batch.snapshot_sha256, batch.code_sha256])), "invalid_batch")
    ids = {o.observation_id for o in batch.observations}
    require(len(ids) == len(batch.observations), "invalid_batch")
    native = {r.native_id for r in batch.records}
    require(len(native) == len(batch.records), "invalid_batch")
    for r in batch.records:
        require(type(r.native_id) is int and r.native_id > 0, "invalid_batch")
        validate_metadata(r.metadata)
    for i, o in enumerate(batch.observations):
        require(type(o.position) is int and o.position == i and valid_digest(o.observation_id) and
                o.observation_id == digest(batch.execution_sha256 + ":" + str(i)),
                "invalid_batch")
        validate_metadata(o.metadata)
        require(o.origin == ("existing_archive_row" if batch.mode == "archive_inventory"
                             else "supplied_local_document"), "invalid_batch")
        require(o.title_reason in TITLE_REASONS and o.url_hash_reason in URL_REASONS,
                "invalid_batch")
        for representative in (o.title_representative, o.url_hash_representative):
            require(representative is None or representative in ids, "invalid_batch")
        require(all(type(n) is int and n in native for n in
                    (*o.native_ids, *o.decision_native_ids)), "invalid_batch")
    nodes = {"o:" + i for i in ids} | {"n:" + str(n) for n in native}
    metadata = {"o:" + o.observation_id: o.metadata for o in batch.observations}
    metadata.update({"n:" + str(r.native_id): r.metadata for r in batch.records})
    for r in batch.relations:
        require(r.kind in RELATIONS and type(r.key) is str and
                re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", r.key) and
                len(r.members) >= 2 and tuple(sorted(set(r.members))) == r.members and
                set(r.members) <= nodes, "invalid_batch")
        for node in r.members:
            m = metadata[node]
            expected = {"same_title_group": m.title_group_sha1, "exact_url": digest(m.url),
                        "equal_normalized_text": m.normalized_text_sha256,
                        "equal_normalized_title_text": m.legacy_title_text_sha256
                            if m.normalized_text_sha256 else None}[r.kind]
            require(expected == r.key, "invalid_batch")
    require(tuple(sorted(batch.relations, key=lambda r: (r.kind, r.key))) == batch.relations,
            "invalid_batch")
    return batch


def batch_from_dict(data):
    """Exact fields only; corrupted/arbitrary JSON cannot become report content."""
    try:
        obs = tuple(Observation(**dict(o, metadata=Metadata(**o["metadata"]),
                    native_ids=tuple(o["native_ids"]),
                    decision_native_ids=tuple(o["decision_native_ids"])))
                    for o in data["observations"])
        records = tuple(NativeRecord(**dict(r, metadata=Metadata(**r["metadata"])))
                        for r in data["records"])
        relations = tuple(Relation(**dict(r, members=tuple(r["members"])))
                          for r in data["relations"])
        return validate_batch(Batch(**dict(data, observations=obs, records=records,
                                          relations=relations)))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise OccurrenceError("invalid_ledger_payload") from None
