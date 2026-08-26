"""
The desk registry — one authoritative list of every declared desk.

Why this exists
---------------
Before this module the reader-facing desk roster was a Python constant inside
the renderer, and the collection roster was `desks/*/manifest.json`. Two lists,
no relationship, and the failure mode is obvious in hindsight: a desk could be
promoted on the page without a source existing, or a source could be enabled
without the page saying so. The registry is the seam that makes both derived
from one file.

What is authoritative where
---------------------------
  * `desks/registry.json` is authoritative for a desk's **status** and its
    public presentation.
  * The manifest a registry entry points at is authoritative for that desk's
    **sources**. Configured and enabled counts are read from it, never declared
    in the registry.
  * The database is authoritative for **records**. The registry never carries a
    record count, and `has_production_records` is a permission to look, not a
    number.

What this module deliberately cannot do
---------------------------------------
It cannot start collection. `core.manifests.load_all_desks()` discovers
`desks/*/manifest.json`; `desks/registry.json` is one level above that glob, so
adding a desk here writes nothing to the database and enables nothing. A
registry entry may point at a manifest that lives outside `desks/` entirely —
the Singapore shadow manifest does — and pointing at it does not make it
discoverable.

Validation is strict and loud, for the same reason manifest validation is: a
silently dropped desk, or a status typo that renders as something milder than
it is, is a claim about coverage nobody decided to make.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.domain import (
    COLLECTING_DESK_STATUSES,
    DESK_STATUSES,
    DESK_STATUS_LABELS,
)
from core.manifests import DESKS_DIR, ManifestError, load_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "desks" / "registry.json"

#: Keys a registry entry must carry. An omitted key is a malformed declaration,
#: never a default: "public" defaulting to True would publish a desk nobody
#: decided to publish, and "status_explanation" defaulting to "" would render an
#: unexplained status, which is the thing this file exists to prevent.
_REQUIRED = (
    "slug", "name", "route", "scope", "status", "status_explanation",
    "public", "manifest", "has_production_records",
)


class RegistryError(ValueError):
    """Raised when the desk registry is malformed. Never caught internally."""


@dataclass(frozen=True)
class RegistrySource:
    """
    A source as the registry needs to describe it.

    Deliberately looser than `core.domain.Source`. A production manifest under
    `desks/` satisfies the full collection contract and is validated against it
    before this is built; a shadow manifest is a different, looser contract read
    only by the shadow runner, and imposing the collection schema on it here
    would either fail the load or pressure someone into editing a file the
    shadow collector reads every night.

    So the fields the collection contract guarantees are optional here, and an
    absent one is `None` — unknown — never a default that reads as a fact.
    """

    slug: str
    display_name: str
    institution_id: Optional[str]
    base_url: Optional[str]
    language_tag: Optional[str]
    authority_tier: Optional[str]
    source_type: Optional[str]
    access_method: Optional[str]
    enabled: bool
    #: True when this source was validated against the full collection
    #: contract. False for a shadow manifest, which is not a collection
    #: declaration and must not be displayed as one.
    contract_validated: bool
    notes: Optional[str] = None


@dataclass(frozen=True)
class DeskEntry:
    """
    One declared desk, with everything a reader-facing surface may say about it.

    Every count on this object is derived. `configured_sources` and
    `enabled_sources` are read from the manifest; a desk with no manifest has
    zero of each, and zero here means "none configured", not "unknown".
    """

    slug: str
    name: str
    route: str
    scope: str
    status: str
    status_explanation: str
    public: bool
    manifest_path: Optional[str]
    has_production_records: bool
    limits: List[str] = field(default_factory=list)
    #: Manifest-derived. Empty when no manifest is declared.
    sources: List[RegistrySource] = field(default_factory=list)
    #: Free-form declared blocks, carried verbatim to the view layer. Used by
    #: the Japan research block and the Singapore qualification block. Never
    #: interpreted here — this module refuses to compute anything from prose.
    research: Optional[dict] = None
    qualification: Optional[dict] = None

    @property
    def status_label(self) -> str:
        return DESK_STATUS_LABELS[self.status]

    @property
    def is_collecting(self) -> bool:
        """True only for a desk whose records reach the public corpus."""
        return self.status in COLLECTING_DESK_STATUSES

    @property
    def configured_source_count(self) -> int:
        return len(self.sources)

    @property
    def enabled_source_count(self) -> int:
        return sum(1 for s in self.sources if s.enabled)

    @property
    def may_show_record_count(self) -> bool:
        """
        Whether a record count for this desk means anything.

        A desk that does not collect into production has no record count to
        show — not zero, which reads as "we looked and found none". The
        renderer asks this rather than testing the status itself, so the rule
        lives in one place.
        """
        return self.is_collecting and self.has_production_records


@dataclass(frozen=True)
class DeskRegistry:
    """Every declared desk, in declared order."""

    entries: List[DeskEntry]

    def __iter__(self):
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def slugs(self) -> List[str]:
        return [e.slug for e in self.entries]

    def get(self, slug: str) -> Optional[DeskEntry]:
        for entry in self.entries:
            if entry.slug == slug:
                return entry
        return None

    @property
    def public_entries(self) -> List[DeskEntry]:
        return [e for e in self.entries if e.public]

    @property
    def collecting(self) -> List[DeskEntry]:
        return [e for e in self.entries if e.is_collecting]

    def count_by_status(self) -> Dict[str, int]:
        counts = {s: 0 for s in DESK_STATUSES}
        for entry in self.entries:
            counts[entry.status] += 1
        return counts


def _require(raw: dict, key: str, where: str):
    if key not in raw:
        raise RegistryError("%s: missing required field %r" % (where, key))
    value = raw[key]
    if isinstance(value, str) and not value.strip():
        raise RegistryError("%s: required field %r is empty" % (where, key))
    return value


def _sources_for(manifest_path: Optional[str], where: str) -> List[RegistrySource]:
    """
    Read a desk's sources from the manifest it declares.

    A manifest under `desks/` is production collection configuration and is
    parsed through `core.manifests.load_manifest`, so the registry cannot
    describe a source the collection contract would reject. A manifest outside
    `desks/` — the Singapore shadow manifest — is read as JSON and mapped
    field-by-field, with anything it does not declare left unknown.

    A declared manifest that does not exist is an error, not an empty desk:
    silently rendering "no sources configured" for a desk whose manifest was
    moved would understate a desk that is in fact configured.
    """
    if manifest_path is None:
        return []
    path = REPO_ROOT / manifest_path
    if not path.is_file():
        raise RegistryError(
            "%s: declared manifest %s does not exist" % (where, manifest_path))

    if DESKS_DIR.resolve() in path.resolve().parents:
        try:
            config = load_manifest(path)
        except ManifestError as exc:
            raise RegistryError("%s: %s" % (where, exc))
        return [
            RegistrySource(
                slug=src.slug, display_name=src.display_name,
                institution_id=src.institution_id, base_url=src.base_url,
                language_tag=src.language_tag,
                authority_tier=src.authority_tier,
                source_type=src.source_type,
                access_method=src.access_method,
                enabled=bool(src.enabled), contract_validated=True,
                notes=src.notes,
            )
            for src in config.sources
        ]

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError("%s: invalid JSON in %s — %s"
                            % (where, manifest_path, exc))
    out: List[RegistrySource] = []
    for index, item in enumerate(raw.get("sources") or []):
        loc = "%s: %s sources[%d]" % (where, manifest_path, index)
        if not isinstance(item, dict):
            raise RegistryError("%s: source entry must be an object" % loc)
        for key in ("slug", "display_name"):
            if not item.get(key):
                raise RegistryError("%s: missing required field %r" % (loc, key))
        # `enabled` is read strictly. A shadow source that omitted it would
        # otherwise default to something, and the only safe default is the one
        # that hides a live source — so demand the declaration instead.
        if "enabled" not in item:
            raise RegistryError(
                "%s: shadow manifests must declare 'enabled' explicitly" % loc)
        out.append(RegistrySource(
            slug=item["slug"], display_name=item["display_name"],
            institution_id=item.get("institution_id"),
            base_url=item.get("base_url"),
            language_tag=item.get("language_tag"),
            authority_tier=item.get("authority_tier"),
            source_type=item.get("source_type"),
            access_method=item.get("access_method"),
            enabled=bool(item["enabled"]), contract_validated=False,
            notes=item.get("notes"),
        ))
    return out


def load_registry(path: Optional[Path] = None) -> DeskRegistry:
    """Load, validate and resolve the desk registry."""
    path = Path(path) if path is not None else REGISTRY_PATH
    if not path.is_file():
        raise RegistryError("desk registry not found: %s" % path)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError("%s: invalid JSON — %s" % (path, exc))

    if raw.get("registry_version") != 1:
        raise RegistryError(
            "%s: unsupported registry_version %r (this build reads version 1)"
            % (path, raw.get("registry_version")))

    desks = raw.get("desks")
    if not isinstance(desks, list) or not desks:
        raise RegistryError("%s: 'desks' must be a non-empty list" % path)

    entries: List[DeskEntry] = []
    seen = set()
    for index, item in enumerate(desks):
        where = "%s: desks[%d]" % (path.name, index)
        if not isinstance(item, dict):
            raise RegistryError("%s: entry must be an object" % where)

        for key in _REQUIRED:
            _require(item, key, where)

        slug = item["slug"]
        where = "%s: desk %r" % (path.name, slug)
        if slug in seen:
            raise RegistryError("%s: duplicate desk slug" % where)
        seen.add(slug)

        status = item["status"]
        if status not in DESK_STATUSES:
            raise RegistryError(
                "%s: %r is not a valid desk status (permitted: %s)"
                % (where, status, ", ".join(DESK_STATUSES)))

        manifest_path = item["manifest"]
        if manifest_path is not None and not isinstance(manifest_path, str):
            raise RegistryError(
                "%s: 'manifest' must be a path string or null" % where)

        sources = _sources_for(manifest_path, where)

        # A collecting desk with no enabled source would render a live label
        # over nothing. That is precisely the overstatement the registry
        # exists to make impossible, so it fails the load rather than the eye.
        if status in COLLECTING_DESK_STATUSES:
            if not any(s.enabled for s in sources):
                raise RegistryError(
                    "%s: status %r requires at least one enabled source in %s"
                    % (where, status, manifest_path))

        # The mirror of the rule above: a desk that does not collect may not
        # claim production records.
        if item["has_production_records"] and status not in COLLECTING_DESK_STATUSES:
            raise RegistryError(
                "%s: has_production_records is true but the desk status is %r; "
                "only a collecting desk holds production records"
                % (where, status))

        entries.append(DeskEntry(
            slug=slug,
            name=item["name"],
            route=item["route"],
            scope=item["scope"],
            status=status,
            status_explanation=item["status_explanation"],
            public=bool(item["public"]),
            manifest_path=manifest_path,
            has_production_records=bool(item["has_production_records"]),
            limits=list(item.get("limits") or []),
            sources=sources,
            research=item.get("research"),
            qualification=item.get("qualification"),
        ))

    return DeskRegistry(entries=entries)


_CACHE: Optional[DeskRegistry] = None


def get_desk_registry(refresh: bool = False) -> DeskRegistry:
    """Process-wide registry. `refresh=True` re-reads the file."""
    global _CACHE
    if _CACHE is None or refresh:
        _CACHE = load_registry()
    return _CACHE
