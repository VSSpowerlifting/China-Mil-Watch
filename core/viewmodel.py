"""
The public read-only view layer.

What it is for
--------------
Everything a reader-facing surface is allowed to say, as typed objects, derived
from exactly two authorities: the database (records, runs, per-source results)
and the desk registry (which desks exist and what they may claim). The renderer
asks this module for objects; it does not write SQL, and it does not decide from
a template whether a desk is allowed to show a number.

Why the objects are typed
-------------------------
The failure this replaces is a template reading `desks[0].state == 'live'` and a
different template reading a hard-coded id. A `DeskView` cannot be asked for a
record count it is not allowed to have: `record_count` is `None` for every desk
that does not collect into production, and `None` renders as an absence with an
explanation, never as `0`.

Read-only, and mechanically so
------------------------------
Every read goes through `scripts.reconcile_db._read_only`, which works on a
scratch copy. The tracked database is WAL-mode, so a plain `sqlite3.connect()`
would be a write even for a SELECT — that is the run-475 defect, and the rule
is enforced by tests elsewhere. Nothing here opens the tracked file directly.

What it deliberately does not do
--------------------------------
No wall clock. No network. No writes. No interpretation of an absence: a source
that returned nothing carries the run status that says *why*, and this layer
passes that status through rather than reducing it to a count of zero.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.desk_registry import (                                  # noqa: E402
    DeskEntry, DeskRegistry, get_desk_registry,
)
from scripts.reconcile_db import _read_only                       # noqa: E402


def _dict_row(cursor, row):
    return {d[0]: row[i] for i, d in enumerate(cursor.description)}


# ── Identity ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SiteIdentity:
    """
    Who is publishing, under what name, in which build.

    `mode` names the build that produced the page. It is carried so a candidate
    page can never be mistaken for the published site by reading it, which
    matters more than it sounds: both are static HTML in a directory.
    """

    name: str
    tagline: str
    corpus_eyebrow: str
    maintainer: Dict[str, str]
    mode: str
    snapshot_date: Optional[str] = None
    #: The name this record was published under before the umbrella changed.
    #: Present so archival surfaces can say so accurately; never a masthead.
    predecessor_name: Optional[str] = None


# ── Sources ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SourceView:
    """One publication surface, as a reader may see it."""

    slug: str
    display_name: str
    desk_slug: str
    enabled: bool
    contract_validated: bool
    institution: Optional[str] = None
    institution_original: Optional[str] = None
    institution_type: Optional[str] = None
    source_type: Optional[str] = None
    authority_tier: Optional[str] = None
    language_tag: Optional[str] = None
    base_url: Optional[str] = None
    notes: Optional[str] = None
    #: `None` when this source has never been part of a production run — which
    #: is different from a source that ran and stored nothing.
    record_count: Optional[int] = None
    first_published: Optional[str] = None
    last_published: Optional[str] = None
    #: Status of this source in the most recent run, or `None` if it was not in
    #: one. Never collapsed to a boolean: `listing_failure` and
    #: `ok_no_publications` both produce zero records and mean opposite things.
    latest_status: Optional[str] = None
    latest_error_detail: Optional[str] = None
    #: This source's records as a percentage of the whole stored record,
    #: rounded to one decimal. Derived, never declared: a share written into a
    #: manifest note goes stale silently, and this one cannot.
    share_of_record: Optional[float] = None

    @property
    def route(self) -> str:
        return "source/%s.html" % self.slug

    @property
    def in_production(self) -> bool:
        return self.record_count is not None


# ── Desks ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DeskView:
    """
    A registry entry joined to whatever the database can honestly add.

    The registry decides what may be claimed; the database supplies the numbers
    for the desks allowed to have them. Neither overrides the other, and the
    join is one-way: no database row can promote a desk the registry calls
    planned.
    """

    entry: DeskEntry
    sources: List[SourceView] = field(default_factory=list)
    record_count: Optional[int] = None
    #: Records this desk has stored with a completed model reading. `None`
    #: wherever `record_count` is None, for the same reason.
    analyzed_count: Optional[int] = None
    #: Distinct publishing institutions behind this desk's sources. Counted
    #: separately from sources on purpose: two sources can share one
    #: institution, and calling the source count an institution count was a
    #: real defect on the page this replaces.
    institution_count: int = 0
    first_published: Optional[str] = None
    last_published: Optional[str] = None
    last_successful_run: Optional[str] = None

    # Pass-throughs, so a template never reaches two levels deep for a label.
    @property
    def slug(self) -> str:
        return self.entry.slug

    @property
    def name(self) -> str:
        return self.entry.name

    @property
    def route(self) -> str:
        return self.entry.route

    @property
    def scope(self) -> str:
        return self.entry.scope

    @property
    def status(self) -> str:
        return self.entry.status

    @property
    def status_label(self) -> str:
        return self.entry.status_label

    @property
    def status_explanation(self) -> str:
        return self.entry.status_explanation

    @property
    def limits(self) -> List[str]:
        return self.entry.limits

    @property
    def research(self) -> Optional[dict]:
        return self.entry.research

    @property
    def qualification(self) -> Optional[dict]:
        return self.entry.qualification

    @property
    def is_collecting(self) -> bool:
        return self.entry.is_collecting

    @property
    def configured_source_count(self) -> int:
        return self.entry.configured_source_count

    @property
    def enabled_source_count(self) -> int:
        return self.entry.enabled_source_count


@dataclass(frozen=True)
class DeskDirectory:
    desks: List[DeskView]

    def __iter__(self):
        return iter(self.desks)

    def __len__(self) -> int:
        return len(self.desks)

    def get(self, slug: str) -> Optional[DeskView]:
        for desk in self.desks:
            if desk.slug == slug:
                return desk
        return None

    @property
    def collecting(self) -> List[DeskView]:
        return [d for d in self.desks if d.is_collecting]

    @property
    def collecting_count(self) -> int:
        return len(self.collecting)

    @property
    def declared_count(self) -> int:
        return len(self.desks)

    @property
    def not_collecting_count(self) -> int:
        return self.declared_count - self.collecting_count


# ── Coverage ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RunResultView:
    source_slug: str
    status: str
    is_failure: bool
    references_discovered: Optional[int] = None
    fetched: Optional[int] = None
    extracted: Optional[int] = None
    duplicates: Optional[int] = None
    new_documents: Optional[int] = None
    relevance_rejected: Optional[int] = None
    #: Parsed documents that carried no usable text. `None` means the run
    #: predates the measurement — not the same claim as zero.
    text_unavailable: Optional[int] = None
    error_detail: Optional[str] = None
    desk_slug: Optional[str] = None

    @property
    def usable_text(self) -> Optional[int]:
        """Documents that parsed AND yielded text. `None` when unmeasured."""
        if self.text_unavailable is None or self.extracted is None:
            return None
        return self.extracted - self.text_unavailable

    @property
    def extraction_measured(self) -> bool:
        return self.text_unavailable is not None

    @property
    def has_extraction_gap(self) -> bool:
        return bool(self.text_unavailable)


@dataclass(frozen=True)
class CoverageView:
    """The most recent run, per source, plus the recorded collection gaps."""

    run_id: Optional[int]
    run_date: Optional[str]
    results: List[RunResultView] = field(default_factory=list)
    run_days: List[str] = field(default_factory=list)
    #: Desks that actually executed a collector in this run, derived from the
    #: persisted source→desk mapping. Never from the registry: a desk is
    #: collecting because a run says so, not because a config file says so.
    collecting_desks: List[str] = field(default_factory=list)
    #: Executed sources whose desk cannot be established from stored data. When
    #: non-zero the desk count is withheld rather than guessed.
    unmapped_executed: int = 0

    @property
    def executed(self) -> int:
        return sum(1 for r in self.results
                   if r.status not in ("not_implemented", "skipped_disabled"))

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.is_failure)

    @property
    def unimplemented(self) -> int:
        return sum(1 for r in self.results if r.status == "not_implemented")

    @property
    def disabled(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped_disabled")

    @property
    def collecting_desk_count(self) -> Optional[int]:
        """`None` when an executed source cannot be attributed to a desk."""
        if self.unmapped_executed:
            return None
        return len(self.collecting_desks)


# ── Methodology ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MethodologyMetrics:
    """
    Corpus-level figures the methodology page may quote.

    Every one is a COUNT over stored rows. None is an estimate, a rate, or a
    projection, and none is written down anywhere but here.
    """

    records: int
    analyzed: int
    awaiting_screening: int
    not_selected: int
    analysis_incomplete: int
    with_original_text: int
    with_english_title: int
    with_english_summary: int
    runs: int
    sources_configured: int
    sources_enabled: int
    institutions: int
    desks_declared: int
    desks_collecting: int
    first_published: Optional[str]
    last_published: Optional[str]


# ── The view ──────────────────────────────────────────────────────────────────

_STATE_CASE_SQL = (
    "CASE WHEN a.passed_relevance IS NULL      THEN 'awaiting_screening' "
    "     WHEN a.passed_relevance = 0          THEN 'not_selected' "
    "     WHEN a.analyzed_at IS NOT NULL       THEN 'analyzed' "
    "     ELSE 'analysis_incomplete' END"
)


class PublicView:
    """
    One read of the database, exposed as the objects the site renders.

    Constructed with a database path and a desk registry. Nothing is lazy: the
    read happens once in `__init__` so a page cannot open a second connection
    halfway through a build and describe two different corpora.
    """

    def __init__(self, db_path, registry: Optional[DeskRegistry] = None) -> None:
        self.db_path = Path(db_path)
        self.registry = registry if registry is not None else get_desk_registry()
        self._read()

    # -- reading --------------------------------------------------------------

    def _read(self) -> None:
        with _read_only(str(self.db_path)) as con:
            con.row_factory = _dict_row

            self._sources = con.execute(
                "SELECT s.slug, s.display_name, s.desk_id, s.enabled, "
                "       s.is_active, s.institution_id, s.language_tag, "
                "       s.language, s.authority_tier, s.source_type, "
                "       s.base_url, s.notes, "
                "       i.display_name AS institution, i.name_original, "
                "       i.institution_type "
                "  FROM sources s "
                "  LEFT JOIN institutions i "
                "         ON i.institution_id = s.institution_id "
                " ORDER BY s.id").fetchall()

            self._source_stats = {r["slug"]: r for r in con.execute(
                "SELECT sr.slug, COUNT(a.id) AS n, "
                "       MIN(a.published_date) AS first_published, "
                "       MAX(a.published_date) AS last_published "
                "  FROM sources sr "
                "  LEFT JOIN articles a ON a.source_id = sr.id "
                " GROUP BY sr.slug").fetchall()}

            self._desk_stats = {r["desk_id"]: r for r in con.execute(
                "SELECT s.desk_id, COUNT(a.id) AS n, "
                "       SUM(CASE WHEN a.analyzed_at IS NOT NULL "
                "                THEN 1 ELSE 0 END) AS analyzed, "
                "       MIN(a.published_date) AS first_published, "
                "       MAX(a.published_date) AS last_published "
                "  FROM sources s "
                "  JOIN articles a ON a.source_id = s.id "
                " WHERE s.desk_id IS NOT NULL "
                " GROUP BY s.desk_id").fetchall()}

            self._desk_institutions = {
                r["desk_id"]: r["n"] for r in con.execute(
                    "SELECT desk_id, COUNT(DISTINCT institution_id) AS n "
                    "  FROM sources WHERE desk_id IS NOT NULL "
                    "   AND institution_id IS NOT NULL "
                    " GROUP BY desk_id").fetchall()}

            # The measurement column arrives with migration 0006. A database
            # that has not run it yet is not broken and must still render —
            # it simply has not measured usable text, which is exactly what
            # `text_unavailable IS NULL` already means everywhere else. Probing
            # rather than assuming keeps the renderer working against the
            # tracked database between the merge of this change and the first
            # production run that migrates.
            # `con.row_factory` is `_dict_row`, so PRAGMA rows arrive as dicts.
            self._has_text_unavailable = "text_unavailable" in {
                row["name"] for row in con.execute(
                    "PRAGMA table_info(source_run_results)")}

            self._latest_run = con.execute(
                "SELECT id, started_at, completed_at, status "
                "  FROM scrape_runs ORDER BY id DESC LIMIT 1").fetchone()

            run_id = self._latest_run["id"] if self._latest_run else None
            self._run_results = con.execute(
                "SELECT source_slug, desk_id, status, is_failure, "
                "       references_discovered, fetched, extracted, duplicates, "
                "       new_documents, relevance_rejected, "
                + ("text_unavailable, " if self._has_text_unavailable
                   else "NULL AS text_unavailable, ") +
                "       error_detail "
                "  FROM source_run_results WHERE scrape_run_id = ? "
                " ORDER BY source_slug", (run_id,)).fetchall() if run_id else []

            self._collecting_desks = [r["desk_id"] for r in con.execute(
                "SELECT DISTINCT s.desk_id AS desk_id "
                "  FROM source_run_results r "
                "  JOIN sources s ON s.slug = r.source_slug "
                " WHERE r.scrape_run_id = ? "
                "   AND r.status NOT IN ('not_implemented','skipped_disabled') "
                "   AND s.desk_id IS NOT NULL "
                " ORDER BY s.desk_id", (run_id,)).fetchall()] if run_id else []

            self._unmapped_executed = con.execute(
                "SELECT COUNT(*) AS n FROM source_run_results r "
                "  LEFT JOIN sources s ON s.slug = r.source_slug "
                " WHERE r.scrape_run_id = ? "
                "   AND r.status NOT IN ('not_implemented','skipped_disabled') "
                "   AND (s.slug IS NULL OR s.desk_id IS NULL)",
                (run_id,)).fetchone()["n"] if run_id else 0

            self._run_days = [r["d"] for r in con.execute(
                "SELECT DISTINCT substr(started_at,1,10) AS d "
                "  FROM scrape_runs ORDER BY d").fetchall()]

            self._last_successful_run_by_desk = {
                r["desk_id"]: r["d"] for r in con.execute(
                    "SELECT s.desk_id AS desk_id, "
                    "       MAX(substr(r.started_at,1,10)) AS d "
                    "  FROM source_run_results r "
                    "  JOIN sources s ON s.slug = r.source_slug "
                    "  JOIN scrape_runs sr ON sr.id = r.scrape_run_id "
                    " WHERE r.is_failure = 0 "
                    "   AND r.status NOT IN "
                    "       ('not_implemented','skipped_disabled') "
                    "   AND s.desk_id IS NOT NULL "
                    " GROUP BY s.desk_id").fetchall()}

            self._totals = con.execute(
                "SELECT (SELECT COUNT(*) FROM articles) AS records, "
                "       (SELECT COUNT(*) FROM scrape_runs) AS runs, "
                "       (SELECT MIN(published_date) FROM articles) "
                "            AS first_published, "
                "       (SELECT MAX(published_date) FROM articles) "
                "            AS last_published, "
                "       (SELECT COUNT(DISTINCT institution_id) FROM sources "
                "         WHERE institution_id IS NOT NULL) AS institutions"
            ).fetchone()

            self._state_counts = {r["state"]: r["n"] for r in con.execute(
                "SELECT " + _STATE_CASE_SQL + " AS state, COUNT(*) AS n "
                "  FROM articles a GROUP BY state").fetchall()}

            self._field_counts = con.execute(
                "SELECT SUM(CASE WHEN TRIM(COALESCE(text_original,'')) <> '' "
                "                THEN 1 ELSE 0 END) AS with_original_text, "
                "       SUM(CASE WHEN TRIM(COALESCE(title_english,'')) <> '' "
                "                THEN 1 ELSE 0 END) AS with_english_title, "
                "       SUM(CASE WHEN TRIM(COALESCE(summary_english,'')) <> '' "
                "                THEN 1 ELSE 0 END) AS with_english_summary "
                "  FROM articles").fetchone()

    # -- identity -------------------------------------------------------------

    @staticmethod
    def identity(name: str, tagline: str, corpus_eyebrow: str,
                 maintainer: dict, mode: str,
                 snapshot_date: Optional[str] = None,
                 predecessor_name: Optional[str] = None) -> SiteIdentity:
        return SiteIdentity(
            name=name, tagline=tagline, corpus_eyebrow=corpus_eyebrow,
            maintainer=dict(maintainer), mode=mode,
            snapshot_date=snapshot_date, predecessor_name=predecessor_name)

    # -- sources --------------------------------------------------------------

    def _share(self, n: int) -> Optional[float]:
        """
        A source's share of the whole stored record, to one decimal.

        `None` when the record is empty — a percentage of nothing is not zero
        percent, it is undefined, and rendering 0.0% would assert a measurement
        nobody could make.
        """
        total = self._totals["records"]
        if not total or not n:
            # A source that has stored nothing has no share to state. The
            # record count beside it already says zero; "0.0%" would dress the
            # same absence as a measurement.
            return None
        return round(100.0 * n / total, 1)

    def _latest_status_for(self, slug: str):
        for row in self._run_results:
            if row["source_slug"] == slug:
                return row["status"], row["error_detail"]
        return None, None

    def source_directory(self) -> List[SourceView]:
        """
        Every source any declared desk configures, production first.

        A source in the database is described from the database, because that
        is what actually collected. A source declared only in a manifest — the
        Singapore shadow source — is described from the manifest, and its
        record count stays `None` rather than becoming zero.
        """
        views: List[SourceView] = []
        seen = set()

        for row in self._sources:
            stats = self._source_stats.get(row["slug"], {})
            status, detail = self._latest_status_for(row["slug"])
            seen.add(row["slug"])
            views.append(SourceView(
                slug=row["slug"], display_name=row["display_name"],
                desk_slug=row["desk_id"] or "",
                enabled=bool(row["enabled"]),
                contract_validated=True,
                institution=row["institution"],
                institution_original=row["name_original"],
                institution_type=row["institution_type"],
                source_type=row["source_type"],
                authority_tier=row["authority_tier"],
                language_tag=row["language_tag"] or row["language"],
                base_url=row["base_url"], notes=row["notes"],
                record_count=stats.get("n", 0),
                first_published=stats.get("first_published"),
                last_published=stats.get("last_published"),
                latest_status=status, latest_error_detail=detail,
                share_of_record=self._share(stats.get("n", 0)),
            ))

        for entry in self.registry:
            for src in entry.sources:
                if src.slug in seen:
                    continue
                seen.add(src.slug)
                views.append(SourceView(
                    slug=src.slug, display_name=src.display_name,
                    desk_slug=entry.slug, enabled=src.enabled,
                    contract_validated=src.contract_validated,
                    institution=None, source_type=src.source_type,
                    authority_tier=src.authority_tier,
                    language_tag=src.language_tag, base_url=src.base_url,
                    notes=src.notes, record_count=None,
                ))
        return views

    def source_detail(self, slug: str) -> Optional[SourceView]:
        for view in self.source_directory():
            if view.slug == slug:
                return view
        return None

    # -- desks ----------------------------------------------------------------

    def desk_directory(self) -> DeskDirectory:
        by_desk: Dict[str, List[SourceView]] = {}
        for view in self.source_directory():
            by_desk.setdefault(view.desk_slug, []).append(view)

        desks: List[DeskView] = []
        for entry in self.registry.public_entries:
            stats = self._desk_stats.get(entry.slug, {})
            allowed = entry.may_show_record_count
            desks.append(DeskView(
                entry=entry,
                sources=by_desk.get(entry.slug, []),
                record_count=stats.get("n") if allowed else None,
                analyzed_count=(stats.get("analyzed") or 0) if allowed else None,
                institution_count=self._desk_institutions.get(entry.slug, 0),
                first_published=stats.get("first_published") if allowed else None,
                last_published=stats.get("last_published") if allowed else None,
                last_successful_run=(
                    self._last_successful_run_by_desk.get(entry.slug)
                    if allowed else None),
            ))
        return DeskDirectory(desks=desks)

    def desk_detail(self, slug: str) -> Optional[DeskView]:
        return self.desk_directory().get(slug)

    # -- coverage -------------------------------------------------------------

    def coverage(self) -> CoverageView:
        if not self._latest_run:
            return CoverageView(run_id=None, run_date=None,
                                run_days=list(self._run_days))
        return CoverageView(
            run_id=self._latest_run["id"],
            run_date=(self._latest_run["started_at"] or "")[:10] or None,
            results=[RunResultView(
                source_slug=r["source_slug"], status=r["status"],
                is_failure=bool(r["is_failure"]),
                references_discovered=r["references_discovered"],
                fetched=r["fetched"], extracted=r["extracted"],
                duplicates=r["duplicates"], new_documents=r["new_documents"],
                relevance_rejected=r["relevance_rejected"],
                text_unavailable=r["text_unavailable"],
                error_detail=r["error_detail"], desk_slug=r["desk_id"],
            ) for r in self._run_results],
            run_days=list(self._run_days),
            collecting_desks=list(self._collecting_desks),
            unmapped_executed=self._unmapped_executed,
        )

    # -- methodology ----------------------------------------------------------

    def methodology_metrics(self) -> MethodologyMetrics:
        directory = self.desk_directory()
        sources = self.source_directory()
        return MethodologyMetrics(
            records=self._totals["records"],
            analyzed=self._state_counts.get("analyzed", 0),
            awaiting_screening=self._state_counts.get("awaiting_screening", 0),
            not_selected=self._state_counts.get("not_selected", 0),
            analysis_incomplete=self._state_counts.get(
                "analysis_incomplete", 0),
            with_original_text=self._field_counts["with_original_text"] or 0,
            with_english_title=self._field_counts["with_english_title"] or 0,
            with_english_summary=(
                self._field_counts["with_english_summary"] or 0),
            runs=self._totals["runs"],
            sources_configured=len(sources),
            sources_enabled=sum(1 for s in sources if s.enabled),
            institutions=self._totals["institutions"],
            desks_declared=directory.declared_count,
            desks_collecting=directory.collecting_count,
            first_published=self._totals["first_published"],
            last_published=self._totals["last_published"],
        )
