"""
The source adapter contract.

Every source — an HTML scraper, an RSS feed, a Telegram channel, a manual
deposit — presents the same four operations to the pipeline:

    discover(window)  -> DiscoveryResult   (candidate references)
    fetch(reference)  -> CaptureResult     (bytes + provenance)
    extract(capture)  -> ExtractionResult  (normalized document)
    healthcheck()     -> SourceHealthResult

Two constraints shaped the design:

  * **Python 3.9.** An abstract base class rather than `typing.Protocol` with
    `runtime_checkable` generics, and `Optional[...]` rather than `X | None`.

  * **No network in unit tests.** Nothing here performs I/O. Adapters are
    constructed with their dependencies and every result type is a plain
    dataclass, so a contract test can hand an adapter saved fixture HTML and
    assert on the structured outcome without touching an official website.

The existing China scrapers are NOT rewritten to this shape. `adapters/legacy.py`
wraps them, which is what makes Phase 2 safe: the parsers that currently work
keep working, byte for byte, and only the reporting around them changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from core.collection import status as st


# ── Value types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CollectionWindow:
    """The period a run is collecting for. Dates are in the SOURCE's timezone."""

    target_date: date
    lookback_days: int = 0

    @property
    def is_single_day(self) -> bool:
        return self.lookback_days == 0


@dataclass(frozen=True)
class CandidateReference:
    """A URL the adapter believes may be a publication in the window."""

    url: str
    source_slug: str
    discovered_via: Optional[str] = None     # which listing endpoint produced it
    hint_published_date: Optional[str] = None


@dataclass
class CaptureResult:
    """
    The raw retrieval of one reference.

    The provenance fields are deliberately WARC-compatible (requested vs final
    URL, status, headers, payload hash) so that moving to real WARC storage in
    Phase 3 is a change of writer, not a change of what we know about a capture.
    Nothing here is persisted yet — Phase 3 owns capture storage.
    """

    reference: CandidateReference
    status: str
    requested_url: str
    final_url: Optional[str] = None
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    payload_bytes: Optional[int] = None
    payload_sha256: Optional[str] = None
    retrieved_at: Optional[str] = None
    body: Optional[str] = None               # decoded text, not persisted
    error_detail: Optional[str] = None

    @property
    def ok(self) -> bool:
        return st.is_success(self.status)


@dataclass
class ExtractedDocument:
    """
    Normalized document. Field names match what `storage.db.insert_article`
    already expects, so the legacy path consumes this unchanged.
    """

    url: str
    source_slug: str
    title_original: str
    text_original: str
    published_date: Optional[str] = None
    language_tag: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    #: The exact dict the legacy parser returned, when this document came from a
    #: legacy adapter. Preserved verbatim so `as_article_dict()` can hand
    #: downstream stages byte-identical input to what they receive today —
    #: including which keys are absent, which is not the same as present-and-None
    #: to code that uses `in` or `.get(k, default)`.
    raw: Optional[Dict[str, Any]] = None

    def as_article_dict(self) -> Dict[str, Any]:
        """
        Render to the dict shape the existing pipeline and storage layer use.

        When a raw parser dict is present it is returned as-is (copied). Building
        a fresh dict here would silently add `published_date: None` keys that the
        parser never emitted, changing what normalization and dedup see.
        """
        if self.raw is not None:
            return dict(self.raw)
        out = {
            "url": self.url,
            "source_slug": self.source_slug,
            "title_original": self.title_original,
            "text_original": self.text_original,
            "published_date": self.published_date,
        }
        out.update(self.extra)
        return out


@dataclass
class DiscoveryResult:
    """Outcome of listing traversal. `status` distinguishes silence from failure."""

    source_slug: str
    status: str
    references: List[CandidateReference] = field(default_factory=list)
    failed_endpoints: List[str] = field(default_factory=list)
    error_detail: Optional[str] = None

    @property
    def ok(self) -> bool:
        return st.is_success(self.status)


@dataclass
class ExtractionResult:
    """Outcome of parsing captures into documents."""

    source_slug: str
    status: str
    documents: List[ExtractedDocument] = field(default_factory=list)
    error_detail: Optional[str] = None


@dataclass
class SourceHealthResult:
    """A cheap, offline-answerable statement about whether a source is usable."""

    source_slug: str
    status: str
    detail: Optional[str] = None


@dataclass
class SourceRunResult:
    """
    Everything one source did in one run.

    This is the record the aggregate run is built from, and the row written to
    `source_run_results`. It answers, per source: discovered, fetched,
    extracted, duplicates, new, rejected — and whether zero meant silence or
    breakage.
    """

    source_slug: str
    status: str
    desk_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    references_discovered: int = 0
    fetched: int = 0
    extracted: int = 0
    duplicates: int = 0
    new_documents: int = 0
    relevance_rejected: int = 0
    failed_fetches: int = 0
    error_detail: Optional[str] = None

    def __post_init__(self) -> None:
        st.validate(self.status)

    @property
    def is_failure(self) -> bool:
        return st.is_failure(self.status)

    @property
    def is_success(self) -> bool:
        return st.is_success(self.status)

    def summary_line(self) -> str:
        """One human-readable line. No secrets, no stack traces."""
        counts = (
            "discovered=%d fetched=%d extracted=%d dup=%d new=%d rejected=%d"
            % (self.references_discovered, self.fetched, self.extracted,
               self.duplicates, self.new_documents, self.relevance_rejected)
        )
        line = "%-18s %-22s %s" % (self.source_slug, self.status, counts)
        if self.error_detail:
            line += "  | %s" % self.error_detail
        return line


# ── The adapter interface ─────────────────────────────────────────────────────

class SourceAdapter(ABC):
    """
    Base for every source adapter.

    Implementations must not raise for expected failure modes. A timeout, a
    404 listing, a parser that finds nothing — all of those are *results*, with
    a status naming them. Raising is reserved for genuine programming errors,
    and even then the registry converts it to ADAPTER_ERROR rather than letting
    one source abort the run.
    """

    #: Set False by adapters that are documented stubs.
    implemented: bool = True

    def __init__(self, source) -> None:
        self.source = source            # core.domain.Source
        self.slug = source.slug

    @abstractmethod
    def discover(self, window: CollectionWindow) -> DiscoveryResult:
        """Find candidate references published in the window."""

    @abstractmethod
    def fetch(self, reference: CandidateReference) -> CaptureResult:
        """Retrieve one reference."""

    @abstractmethod
    def extract(self, capture: CaptureResult) -> ExtractionResult:
        """Parse one capture into zero or more normalized documents."""

    def healthcheck(self) -> SourceHealthResult:
        """
        Default: report configuration state only. Deliberately offline — a
        healthcheck that hits the network cannot run in the test suite, and a
        healthcheck that cannot run in the test suite does not get run.
        """
        if not self.implemented:
            return SourceHealthResult(
                self.slug, st.NOT_IMPLEMENTED,
                "adapter is a documented stub",
            )
        if not getattr(self.source, "enabled", True):
            return SourceHealthResult(
                self.slug, st.SKIPPED_DISABLED, "disabled in desk manifest",
            )
        return SourceHealthResult(self.slug, st.OK, "configured")
