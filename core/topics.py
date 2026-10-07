"""Cross-desk regional topic taxonomy and storage-neutral assignment API.

The production China corpus already has article_categories whose slugs are
China-desk analysis labels. This module does not reinterpret them. Regional
topics are a second, versioned layer intended to mean the same thing regardless
of desk.

Assignments are stored beside whatever SQLite corpus owns the record. The
table deliberately has no foreign key to articles or any shadow table:
production and shadow stores use different record schemas, but all preserve a
stable desk/source/URL identity. The API validates the taxonomy before writing
and never commits on the caller's behalf.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAXONOMY_PATH = REPO_ROOT / "taxonomy" / "regional_topics.v1.json"

TAXONOMY_ID = "ipr_regional_topics"
TAXONOMY_VERSION = 1
ASSIGNMENT_METHODS = ("human", "rule", "model")
_SLUG = re.compile(r"^[a-z][a-z0-9_]*$")
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class TopicTaxonomyError(ValueError):
    """The controlled vocabulary is malformed or an assignment is invalid."""


class TopicStoreError(RuntimeError):
    """The assignment store would lose or contradict provenance."""


@dataclass(frozen=True)
class TopicGroup:
    slug: str
    display_name: str
    description: str


@dataclass(frozen=True)
class RegionalTopic:
    slug: str
    display_name: str
    group: str
    description: str
    scope_note: str


@dataclass(frozen=True)
class TopicTaxonomy:
    taxonomy_id: str
    taxonomy_version: int
    groups: List[TopicGroup]
    topics: List[RegionalTopic]

    @property
    def topic_slugs(self) -> tuple:
        return tuple(topic.slug for topic in self.topics)

    def topic(self, slug: str) -> RegionalTopic:
        for topic in self.topics:
            if topic.slug == slug:
                return topic
        raise TopicTaxonomyError(
            "unknown regional topic %r (taxonomy v%d)" %
            (slug, self.taxonomy_version)
        )


@dataclass(frozen=True)
class RecordRef:
    """Storage-neutral identity of one preserved official record."""

    desk_id: str
    source_slug: str
    canonical_url: str

    def validate(self) -> None:
        for label, value in (
            ("desk_id", self.desk_id),
            ("source_slug", self.source_slug),
        ):
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise TopicTaxonomyError("%s is not a stable identifier: %r" %
                                         (label, value))
        parsed = urlparse(self.canonical_url or "")
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise TopicTaxonomyError(
                "canonical_url must be an absolute http(s) URL: %r" %
                self.canonical_url
            )
        if parsed.fragment:
            raise TopicTaxonomyError(
                "canonical_url must not contain a fragment: %r" %
                self.canonical_url
            )


@dataclass(frozen=True)
class TopicAssignment:
    record: RecordRef
    topic_slug: str
    assignment_method: str
    assigned_by: str
    assigned_at: str
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    taxonomy_version: int = TAXONOMY_VERSION

    def validate(self, taxonomy: Optional[TopicTaxonomy] = None) -> None:
        taxonomy = taxonomy or load_taxonomy()
        self.record.validate()
        if self.taxonomy_version != taxonomy.taxonomy_version:
            raise TopicTaxonomyError(
                "assignment taxonomy version %r does not match loaded version %r"
                % (self.taxonomy_version, taxonomy.taxonomy_version)
            )
        taxonomy.topic(self.topic_slug)
        if self.assignment_method not in ASSIGNMENT_METHODS:
            raise TopicTaxonomyError(
                "assignment_method %r is not one of %s" %
                (self.assignment_method, ", ".join(ASSIGNMENT_METHODS))
            )
        if not isinstance(self.assigned_by, str) or not self.assigned_by.strip():
            raise TopicTaxonomyError("assigned_by must be a non-empty provenance label")
        _parse_utc(self.assigned_at)
        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(
                    self.confidence, (int, float)):
                raise TopicTaxonomyError("confidence must be numeric or null")
            if not 0.0 <= float(self.confidence) <= 1.0:
                raise TopicTaxonomyError("confidence must be between 0 and 1")
            if self.assignment_method == "human":
                raise TopicTaxonomyError(
                    "human assignments do not carry synthetic confidence scores"
                )


def _require_text(raw: dict, key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TopicTaxonomyError("%s: %s must be non-empty text" % (where, key))
    return value.strip()


def load_taxonomy(path: Optional[Path] = None) -> TopicTaxonomy:
    path = Path(path or DEFAULT_TAXONOMY_PATH)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise TopicTaxonomyError("regional topic taxonomy not found: %s" % path)
    except json.JSONDecodeError as exc:
        raise TopicTaxonomyError("invalid regional topic JSON: %s" % exc)

    if not isinstance(raw, dict):
        raise TopicTaxonomyError("regional topic taxonomy must be a JSON object")
    if raw.get("taxonomy_id") != TAXONOMY_ID:
        raise TopicTaxonomyError(
            "taxonomy_id must be %r, got %r" %
            (TAXONOMY_ID, raw.get("taxonomy_id"))
        )
    if raw.get("taxonomy_version") != TAXONOMY_VERSION:
        raise TopicTaxonomyError(
            "unsupported taxonomy_version %r" % raw.get("taxonomy_version")
        )

    groups: List[TopicGroup] = []
    group_slugs = set()
    for i, item in enumerate(raw.get("groups", [])):
        where = "groups[%d]" % i
        if not isinstance(item, dict):
            raise TopicTaxonomyError("%s must be an object" % where)
        slug = _require_text(item, "slug", where)
        if not _SLUG.fullmatch(slug):
            raise TopicTaxonomyError("%s: invalid slug %r" % (where, slug))
        if slug in group_slugs:
            raise TopicTaxonomyError("%s: duplicate group slug %r" % (where, slug))
        group_slugs.add(slug)
        groups.append(TopicGroup(
            slug=slug,
            display_name=_require_text(item, "display_name", where),
            description=_require_text(item, "description", where),
        ))
    if not groups:
        raise TopicTaxonomyError("taxonomy declares no groups")

    topics: List[RegionalTopic] = []
    topic_slugs = set()
    for i, item in enumerate(raw.get("topics", [])):
        where = "topics[%d]" % i
        if not isinstance(item, dict):
            raise TopicTaxonomyError("%s must be an object" % where)
        slug = _require_text(item, "slug", where)
        if not _SLUG.fullmatch(slug):
            raise TopicTaxonomyError("%s: invalid slug %r" % (where, slug))
        if slug in topic_slugs:
            raise TopicTaxonomyError("%s: duplicate topic slug %r" % (where, slug))
        topic_slugs.add(slug)
        group = _require_text(item, "group", where)
        if group not in group_slugs:
            raise TopicTaxonomyError(
                "%s: topic references unknown group %r" % (where, group)
            )
        topics.append(RegionalTopic(
            slug=slug,
            display_name=_require_text(item, "display_name", where),
            group=group,
            description=_require_text(item, "description", where),
            scope_note=_require_text(item, "scope_note", where),
        ))
    if not topics:
        raise TopicTaxonomyError("taxonomy declares no topics")

    return TopicTaxonomy(
        taxonomy_id=TAXONOMY_ID,
        taxonomy_version=TAXONOMY_VERSION,
        groups=groups,
        topics=topics,
    )


RECORD_TOPICS_DDL = """
CREATE TABLE IF NOT EXISTS record_topics (
    desk_id            TEXT NOT NULL,
    source_slug        TEXT NOT NULL,
    record_url         TEXT NOT NULL,
    topic_slug         TEXT NOT NULL,
    taxonomy_version   INTEGER NOT NULL,
    assignment_method  TEXT NOT NULL
                       CHECK (assignment_method IN ('human','rule','model')),
    assigned_by        TEXT NOT NULL,
    assigned_at        TEXT NOT NULL,
    confidence         REAL,
    evidence           TEXT,
    PRIMARY KEY (
        desk_id, source_slug, record_url, topic_slug, taxonomy_version
    ),
    CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0))
)
"""

RECORD_TOPICS_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_record_topics_topic
ON record_topics (taxonomy_version, topic_slug, desk_id)
"""


def topic_store_exists(conn: sqlite3.Connection) -> bool:
    """Whether this database has opted into regional topic assignments."""
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='record_topics'"
    ).fetchone() is not None


def ensure_topic_store(conn: sqlite3.Connection) -> None:
    """Install the assignment table in any IPR SQLite state store."""
    conn.execute(RECORD_TOPICS_DDL)
    conn.execute(RECORD_TOPICS_INDEX_DDL)


def attach_topic(
    conn: sqlite3.Connection,
    assignment: TopicAssignment,
    taxonomy: Optional[TopicTaxonomy] = None,
) -> bool:
    """Attach one topic without overwriting prior provenance.

    Returns True when a row was inserted and False for an identical idempotent
    repeat. If the same record/topic key already exists with different
    provenance, raises instead of silently replacing evidence.
    """
    taxonomy = taxonomy or load_taxonomy()
    assignment.validate(taxonomy)
    ensure_topic_store(conn)

    key = (
        assignment.record.desk_id,
        assignment.record.source_slug,
        assignment.record.canonical_url,
        assignment.topic_slug,
        assignment.taxonomy_version,
    )
    row = conn.execute(
        """
        SELECT assignment_method, assigned_by, assigned_at, confidence, evidence
          FROM record_topics
         WHERE desk_id=? AND source_slug=? AND record_url=?
           AND topic_slug=? AND taxonomy_version=?
        """,
        key,
    ).fetchone()
    payload = (
        assignment.assignment_method,
        assignment.assigned_by.strip(),
        assignment.assigned_at,
        None if assignment.confidence is None else float(assignment.confidence),
        assignment.evidence,
    )
    if row is not None:
        if tuple(row) == payload:
            return False
        raise TopicStoreError(
            "topic assignment already exists with different provenance for %s %s"
            % (assignment.record.canonical_url, assignment.topic_slug)
        )

    conn.execute(
        """
        INSERT INTO record_topics (
            desk_id, source_slug, record_url, topic_slug, taxonomy_version,
            assignment_method, assigned_by, assigned_at, confidence, evidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        key + payload,
    )
    return True


def topics_for_record(
    conn: sqlite3.Connection,
    record: RecordRef,
    taxonomy_version: int = TAXONOMY_VERSION,
) -> List[TopicAssignment]:
    """Return deterministic assignments for one record without mutating schema."""
    record.validate()
    if not topic_store_exists(conn):
        return []
    taxonomy = load_taxonomy()
    if taxonomy_version != taxonomy.taxonomy_version:
        raise TopicTaxonomyError(
            "unsupported taxonomy_version %r" % taxonomy_version
        )
    rows = conn.execute(
        """
        SELECT topic_slug, assignment_method, assigned_by, assigned_at,
               confidence, evidence
          FROM record_topics
         WHERE desk_id=? AND source_slug=? AND record_url=?
           AND taxonomy_version=?
         ORDER BY topic_slug
        """,
        (record.desk_id, record.source_slug, record.canonical_url,
         taxonomy_version),
    ).fetchall()
    assignments = [
        TopicAssignment(
            record=record,
            topic_slug=row[0],
            assignment_method=row[1],
            assigned_by=row[2],
            assigned_at=row[3],
            confidence=row[4],
            evidence=row[5],
            taxonomy_version=taxonomy_version,
        )
        for row in rows
    ]
    for assignment in assignments:
        assignment.validate(taxonomy)
    return assignments


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise TopicTaxonomyError("assigned_at must be an ISO-8601 UTC timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise TopicTaxonomyError(
            "assigned_at must be an ISO-8601 UTC timestamp: %r" % value
        )
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise TopicTaxonomyError(
            "assigned_at must carry UTC offset +00:00 or Z: %r" % value
        )
    return parsed
