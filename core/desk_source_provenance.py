"""Public-view source provenance for every desk: what may truthfully be shown.

One deterministic adapter joins four authorities without letting any of them
speak for another:

* ``desks/registry.json`` — desk status, scope, limits, research families;
* manifests — a source is *production* only when it is declared under
  ``desks/`` and validated by ``core.manifests`` (``contract_validated``);
* shadow declarations — ``config/shadow_source_workflow_bindings.json`` and
  the shadow manifests it names; declared, never production;
* public reference lanes — the existing gated loaders for official indexes,
  bibliographies and human-reviewed links. A reference is a link, never a
  collected record, and no lane is ever summed into a record count.

The classification of each research family into an evidence class is a
reviewed declaration in ``config/desk_source_provenance.json``, never inferred
from prose. Production run health attaches only to a contract-validated source
on a collecting desk, by exact slug.

``build_desk_provenance`` is pure: it reads no clock, file, network or
database. ``scripts/desk_source_provenance.py`` gathers the real inputs.
Malformed structure raises ``ProvenanceInputError``; disagreements between
authorities are recorded as ``conflicts`` and resolved toward the weaker
claim, so a conflict can hide a source but never promote one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from core.collection import status as st
from core.domain import COLLECTING_DESK_STATUSES

ROOT = Path(__file__).resolve().parents[1]
BINDINGS_PATH = ROOT / "config" / "desk_source_provenance.json"
SHADOW_BINDINGS_PATH = ROOT / "config" / "shadow_source_workflow_bindings.json"
BINDINGS_SCHEMA = "ipr-desk-source-provenance-bindings/1"
SHADOW_BINDINGS_SCHEMA = "ipr-shadow-source-workflow-bindings/1"
ATLAS_SCHEMA = "ipr-desk-source-provenance/1"


class ProvenanceInputError(ValueError):
    """An input is structurally malformed; nothing built from it is safe."""


class EvidenceClass(str, Enum):
    PRODUCTION = "production"
    SHADOW = "shadow"
    PUBLIC_REFERENCE = "public_reference"
    ACCESS_BLOCKED = "access_blocked"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


EVIDENCE_CLASS_LABELS = {
    EvidenceClass.PRODUCTION: "Production source — validated collection contract",
    EvidenceClass.SHADOW: "Shadow declaration — not admitted to production",
    EvidenceClass.PUBLIC_REFERENCE: "Official publisher index or approved reference — not collected",
    EvidenceClass.ACCESS_BLOCKED: "Access blocked or unavailable — not collected",
    EvidenceClass.INSUFFICIENT_EVIDENCE: "Insufficient public evidence",
}

#: Classes a reviewed family binding may assign. PRODUCTION is absent on
#: purpose: only a validated manifest under ``desks/`` confers it.
BINDABLE_CLASSES = frozenset(c for c in EvidenceClass if c is not EvidenceClass.PRODUCTION)


class RunState(str, Enum):
    COLLECTED_NEW = "collected_new"
    COLLECTED_NO_NEW = "collected_no_new"
    COLLECTION_FAILED = "collection_failed"
    #: A configured production source with no working collector, or one
    #: disabled by configuration. Neither a success nor a failure in the
    #: status taxonomy, and calling it "no new publications" would be false.
    NOT_ATTEMPTED = "not_attempted"
    NO_HISTORY = "no_history"


RUN_STATE_LABELS = {
    RunState.COLLECTED_NEW: "Latest run collected new publications",
    RunState.COLLECTED_NO_NEW: "Latest run succeeded; no new publications",
    RunState.COLLECTION_FAILED: "Latest run failed to collect",
    RunState.NOT_ATTEMPTED: "Configured, but not collected by the latest run",
    RunState.NO_HISTORY: "No run history available",
}

REFERENCE_KINDS = ("bibliography", "official_index", "reviewed_links")
REFERENCE_LOADERS = (
    "korea_public_bibliography", "indonesia_official_index",
    "indonesia_press_index", "reviewed_links_indonesia",
    "reviewed_links_philippines", "reviewed_links_vietnam",
)
_RUN_FIELDS = ("status", "is_failure", "new_documents", "scrape_run_id", "completed_at")


def _require(condition, message):
    if not condition:
        raise ProvenanceInputError(message)


def _opt_str(value, where):
    _require(value is None or isinstance(value, str), "%s must be a string or null" % where)
    return value


def _str_tuple(value, where):
    _require(isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value),
             "%s must be a list of strings" % where)
    return tuple(value)


def _pairs(value, where):
    _require(isinstance(value, (list, tuple)), "%s must be a list" % where)
    out = []
    for item in value:
        _require(isinstance(item, (list, tuple)) and len(item) == 2
                 and all(isinstance(v, str) for v in item),
                 "%s entries must be [title, text] string pairs" % where)
        out.append((item[0], item[1]))
    return tuple(out)


def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        _require(key not in out, "duplicate JSON key: %s" % key)
        out[key] = value
    return out


def _read_json(path: Path, limit: int = 262144):
    path = Path(path)
    _require(path.is_file() and not path.is_symlink(), "%s is absent or a symlink" % path.name)
    _require(path.stat().st_size <= limit, "%s is oversized" % path.name)
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProvenanceInputError("%s is not valid JSON" % path.name) from exc


# ── Input types ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FamilyBinding:
    name: str
    evidence_class: EvidenceClass
    source_slug: Optional[str]
    reference_lanes: Tuple[str, ...]
    basis: str


@dataclass(frozen=True)
class LaneSpec:
    lane_id: str
    loader: str
    kind: str
    filter_by_source_slug: bool


@dataclass(frozen=True)
class DeskBinding:
    shadow_desk_ids: Tuple[str, ...]
    families: Tuple[FamilyBinding, ...]


@dataclass(frozen=True)
class Bindings:
    lanes: Mapping[str, LaneSpec]
    desks: Mapping[str, DeskBinding]


@dataclass(frozen=True)
class ShadowDeclaration:
    """Public-safe fields of one declared shadow source. Workflow, branch and
    schedule identity are deliberately not carried."""
    slug: str
    manifest: str
    desk_id: str
    display_name: str
    base_url: Optional[str]
    language_tags: Tuple[str, ...]
    access_method: Optional[str]
    shadow_enabled: bool
    rights_statement: Optional[str]


@dataclass(frozen=True)
class PublicReference:
    id: str
    url: str
    title_original: str
    published_date: str
    language: Optional[str]
    source_slug: Optional[str] = None
    press_number: Optional[str] = None
    document_distribution_date: Optional[str] = None


@dataclass(frozen=True)
class LaneData:
    schema: str
    publisher: Optional[str]
    issuer: Optional[str]
    editorial_status: Optional[str]
    snapshot_date: Optional[str]
    entries: Tuple[PublicReference, ...]
    #: The publisher's own listing page, when the register declares one.
    index_url: Optional[str] = None


@dataclass(frozen=True)
class RunRow:
    status: object
    is_failure: object
    new_documents: object
    scrape_run_id: object
    completed_at: object


@dataclass(frozen=True)
class HealthInput:
    history_available: bool
    latest: Optional[RunRow]
    last_new_document_at: Optional[str] = None
    last_successful_collection_at: Optional[str] = None
    record_count: Optional[int] = None


# ── Output types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProductionHealth:
    state: RunState
    reason: Optional[str]
    raw_status: Optional[str]
    scrape_run_id: Optional[int]
    completed_at: Optional[str]
    new_documents: Optional[int]
    last_new_document_at: Optional[str]
    last_successful_collection_at: Optional[str]
    record_count: Optional[int]

    @property
    def label(self) -> str:
        return RUN_STATE_LABELS[self.state]


@dataclass(frozen=True)
class SourceProvenance:
    name: str
    evidence_class: EvidenceClass
    source_slug: Optional[str]
    publisher_url: Optional[str]
    declared_format: Optional[str]
    note: Optional[str]
    language_tags: Tuple[str, ...]
    access_method: Optional[str]
    authority_tier: Optional[str]
    production_enabled: Optional[bool]
    shadow_enabled: Optional[bool]
    rights_statement: Optional[str]
    basis: Optional[str]
    reference_lanes: Tuple[str, ...]
    health: Optional[ProductionHealth]

    @property
    def evidence_label(self) -> str:
        return EVIDENCE_CLASS_LABELS[self.evidence_class]


@dataclass(frozen=True)
class ReferenceGroup:
    lane_id: str
    kind: str
    family_name: str
    schema: str
    publisher: Optional[str]
    issuer: Optional[str]
    editorial_status: Optional[str]
    snapshot_date: Optional[str]
    index_url: Optional[str]
    entries: Tuple[PublicReference, ...]

    @property
    def link_count(self) -> int:
        """Outbound links, never a collection count."""
        return len(self.entries)


@dataclass(frozen=True)
class Qualification:
    required_consecutive_days: Optional[int]
    checkpoints: Optional[int]
    explanation: Optional[str]


@dataclass(frozen=True)
class DeskProvenance:
    slug: str
    name: str
    route: str
    scope: str
    status: str
    status_label: str
    status_explanation: str
    public: bool
    has_production_records: bool
    limits: Tuple[str, ...]
    blockers: Tuple[Tuple[str, str], ...]
    resolved: Tuple[Tuple[str, str], ...]
    observed_volume: Tuple[Tuple[str, str], ...]
    observed_volume_subject: Optional[str]
    volume_caveat: Optional[str]
    qualification: Optional[Qualification]
    sources: Tuple[SourceProvenance, ...]
    references: Tuple[ReferenceGroup, ...]
    conflicts: Tuple[str, ...]

    @property
    def evidence_classes(self) -> Tuple[EvidenceClass, ...]:
        seen = {s.evidence_class for s in self.sources}
        return tuple(c for c in EvidenceClass if c in seen)

    def sources_of(self, evidence_class: EvidenceClass) -> Tuple[SourceProvenance, ...]:
        return tuple(s for s in self.sources if s.evidence_class is evidence_class)


@dataclass(frozen=True)
class ProvenanceAtlas:
    as_of: str
    health_supplied: bool
    desks: Tuple[DeskProvenance, ...]
    undisplayed_shadow_declarations: Tuple[str, ...]
    unmatched_health_slugs: Tuple[str, ...]
    conflicts: Tuple[str, ...] = field(default=())

    def get(self, slug: str) -> Optional[DeskProvenance]:
        for desk in self.desks:
            if desk.slug == slug:
                return desk
        return None


# ── Loaders (deterministic file reads; no clock, network or DB) ──────────────

def parse_bindings(raw) -> Bindings:
    _require(isinstance(raw, dict), "bindings must be an object")
    _require(set(raw) <= {"schema", "_comment", "reference_lanes", "desks"}
             and {"schema", "reference_lanes", "desks"} <= set(raw),
             "bindings have missing or unexpected top-level fields")
    _require(raw["schema"] == BINDINGS_SCHEMA, "unknown bindings schema")
    lanes_raw = raw["reference_lanes"]
    _require(isinstance(lanes_raw, dict), "reference_lanes must be an object")
    lanes: Dict[str, LaneSpec] = {}
    for lane_id, spec in lanes_raw.items():
        _require(isinstance(spec, dict) and set(spec) == {"loader", "kind", "filter_by_source_slug"},
                 "reference lane %s has missing or unexpected fields" % lane_id)
        _require(spec["loader"] in REFERENCE_LOADERS, "reference lane %s: unknown loader" % lane_id)
        _require(spec["kind"] in REFERENCE_KINDS, "reference lane %s: unknown kind" % lane_id)
        _require(isinstance(spec["filter_by_source_slug"], bool),
                 "reference lane %s: filter_by_source_slug must be boolean" % lane_id)
        lanes[lane_id] = LaneSpec(lane_id, spec["loader"], spec["kind"], spec["filter_by_source_slug"])
    _require(len({s.loader for s in lanes.values()}) == len(lanes),
             "two reference lanes share one loader")

    desks_raw = raw["desks"]
    _require(isinstance(desks_raw, dict), "desks must be an object")
    desks: Dict[str, DeskBinding] = {}
    seen_slugs: Dict[str, str] = {}
    seen_shadow_ids: Dict[str, str] = {}
    for desk_slug, desk in desks_raw.items():
        where = "desk %s" % desk_slug
        _require(isinstance(desk, dict) and set(desk) == {"shadow_desk_ids", "families"},
                 "%s has missing or unexpected fields" % where)
        shadow_ids = _str_tuple(desk["shadow_desk_ids"], where + " shadow_desk_ids")
        for sid in shadow_ids:
            _require(sid not in seen_shadow_ids, "shadow desk id %s bound to two desks" % sid)
            seen_shadow_ids[sid] = desk_slug
        _require(isinstance(desk["families"], list), "%s families must be a list" % where)
        families: List[FamilyBinding] = []
        names = set()
        for item in desk["families"]:
            _require(isinstance(item, dict) and set(item) ==
                     {"name", "evidence_class", "source_slug", "reference_lanes", "basis"},
                     "%s family has missing or unexpected fields" % where)
            name = item["name"]
            _require(isinstance(name, str) and name.strip() == name and name,
                     "%s family name must be a non-empty trimmed string" % where)
            _require(name not in names, "%s binds family %r twice" % (where, name))
            names.add(name)
            try:
                cls = EvidenceClass(item["evidence_class"])
            except ValueError as exc:
                raise ProvenanceInputError("%s family %r: unknown evidence class" % (where, name)) from exc
            _require(cls in BINDABLE_CLASSES,
                     "%s family %r: production cannot be assigned by binding" % (where, name))
            slug = _opt_str(item["source_slug"], "%s family %r source_slug" % (where, name))
            if slug is not None:
                _require(slug not in seen_slugs, "source slug %s bound twice" % slug)
                seen_slugs[slug] = desk_slug
            lane_ids = _str_tuple(item["reference_lanes"], "%s family %r reference_lanes" % (where, name))
            _require(len(set(lane_ids)) == len(lane_ids), "%s family %r repeats a lane" % (where, name))
            for lane_id in lane_ids:
                _require(lane_id in lanes, "%s family %r: undeclared lane %s" % (where, name, lane_id))
                _require(not lanes[lane_id].filter_by_source_slug or slug is not None,
                         "%s family %r: slug-filtered lane needs a source slug" % (where, name))
            basis = item["basis"]
            _require(isinstance(basis, str) and basis.strip(), "%s family %r needs a basis" % (where, name))
            families.append(FamilyBinding(name, cls, slug, lane_ids, basis))
        desks[desk_slug] = DeskBinding(shadow_ids, tuple(families))
    return Bindings(lanes, desks)


def load_bindings(path: Path = BINDINGS_PATH) -> Bindings:
    return parse_bindings(_read_json(path))


def parse_shadow_manifest(slug: str, manifest_rel: str, raw) -> ShadowDeclaration:
    where = "%s (%s)" % (slug, manifest_rel)
    _require(isinstance(raw, dict) and raw.get("_shadow") is True,
             "%s: manifest is not marked _shadow" % where)
    desk = raw.get("desk")
    _require(isinstance(desk, dict) and isinstance(desk.get("desk_id"), str),
             "%s: manifest desk.desk_id missing" % where)
    sources = raw.get("sources")
    _require(isinstance(sources, list), "%s: manifest sources must be a list" % where)
    matches = [s for s in sources if isinstance(s, dict) and s.get("slug") == slug]
    _require(len(matches) == 1, "%s: manifest must declare the slug exactly once" % where)
    src = matches[0]
    _require(isinstance(src.get("enabled"), bool), "%s: enabled must be declared as a boolean" % where)
    _require(isinstance(src.get("display_name"), str) and src["display_name"],
             "%s: display_name missing" % where)
    _require(not ("language_tag" in src and "language_tags" in src),
             "%s: declares both language_tag and language_tags" % where)
    if "language_tags" in src:
        tags = _str_tuple(src["language_tags"], where + " language_tags")
    elif src.get("language_tag") is not None:
        _require(isinstance(src["language_tag"], str), "%s: language_tag must be a string" % where)
        tags = (src["language_tag"],)
    else:
        tags = ()
    rights = raw.get("rights")
    return ShadowDeclaration(
        slug=slug, manifest=manifest_rel, desk_id=desk["desk_id"],
        display_name=src["display_name"],
        base_url=_opt_str(src.get("base_url"), where + " base_url"),
        language_tags=tags,
        access_method=_opt_str(src.get("access_method"), where + " access_method"),
        shadow_enabled=src["enabled"],
        rights_statement=_opt_str(rights, where + " rights"),
    )


def load_shadow_declarations(bindings_path: Path = SHADOW_BINDINGS_PATH,
                             root: Path = ROOT) -> Dict[str, ShadowDeclaration]:
    """Every shadow source declared in the workflow bindings, keyed by slug."""
    raw = _read_json(bindings_path)
    _require(isinstance(raw, dict) and raw.get("schema") == SHADOW_BINDINGS_SCHEMA,
             "unknown shadow workflow bindings schema")
    entries = raw.get("sources")
    _require(isinstance(entries, list), "shadow workflow bindings sources must be a list")
    out: Dict[str, ShadowDeclaration] = {}
    cache: Dict[str, object] = {}
    for entry in entries:
        _require(isinstance(entry, dict) and isinstance(entry.get("source_slug"), str)
                 and isinstance(entry.get("manifest"), str),
                 "shadow workflow binding needs source_slug and manifest")
        slug, rel = entry["source_slug"], entry["manifest"]
        _require(slug not in out, "shadow source %s declared twice" % slug)
        _require(rel.startswith("shadow/") and ".." not in Path(rel).parts,
                 "shadow manifest %s must live under shadow/" % rel)
        if rel not in cache:
            cache[rel] = _read_json(Path(root) / rel)
        out[slug] = parse_shadow_manifest(slug, rel, cache[rel])
    return out


def health_inputs_from_report(report) -> Dict[str, HealthInput]:
    """Strictly parse a ``scripts/source_health_report.build_report`` dict."""
    _require(isinstance(report, dict), "health report must be an object")
    available = report.get("per_source_history_available")
    _require(isinstance(available, bool), "per_source_history_available must be boolean")
    sources = report.get("sources")
    _require(isinstance(sources, list), "health report sources must be a list")
    out: Dict[str, HealthInput] = {}
    for item in sources:
        _require(isinstance(item, dict) and isinstance(item.get("source_slug"), str),
                 "health report entry needs a source_slug")
        slug = item["source_slug"]
        _require(slug not in out, "health report repeats source %s" % slug)
        latest = item.get("latest_run_result")
        row = None
        if latest is not None:
            _require(isinstance(latest, dict), "%s latest_run_result must be an object" % slug)
            row = RunRow(*(latest.get(k) for k in _RUN_FIELDS))
        count = item.get("articles_total")
        out[slug] = HealthInput(
            history_available=available, latest=row,
            last_new_document_at=_opt_str(item.get("last_new_document_at"), slug + " last_new_document_at"),
            last_successful_collection_at=_opt_str(item.get("last_successful_collection_at"),
                                                   slug + " last_successful_collection_at"),
            record_count=count if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else None,
        )
    return out


# ── Classification ───────────────────────────────────────────────────────────

def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def classify_health(health: Optional[HealthInput]) -> ProductionHealth:
    """Map one production source's latest run to a RunState.

    Unknown stays unknown: malformed, unrecognized or self-contradicting rows
    become NO_HISTORY (or COLLECTION_FAILED when either signal says failure),
    never a success.
    """
    def out(state, reason=None, row=None):
        return ProductionHealth(
            state=state, reason=reason,
            raw_status=row.status if row is not None and isinstance(row.status, str) else None,
            scrape_run_id=row.scrape_run_id if row is not None and _is_int(row.scrape_run_id) else None,
            completed_at=row.completed_at if row is not None and isinstance(row.completed_at, str) else None,
            new_documents=row.new_documents if row is not None and _is_int(row.new_documents) else None,
            last_new_document_at=health.last_new_document_at if health else None,
            last_successful_collection_at=health.last_successful_collection_at if health else None,
            record_count=health.record_count if health else None,
        )

    if health is None:
        return out(RunState.NO_HISTORY, "no health input for this source")
    if not health.history_available:
        return out(RunState.NO_HISTORY, "per-source run history is not available")
    row = health.latest
    if row is None:
        return out(RunState.NO_HISTORY, "no recorded run for this source")
    if not (isinstance(row.status, str) and _is_int(row.is_failure) and row.is_failure in (0, 1)
            and _is_int(row.new_documents) and row.new_documents >= 0):
        return out(RunState.NO_HISTORY, "latest run row is malformed")
    if row.status not in st.ALL_STATUSES:
        return out(RunState.NO_HISTORY, "latest run status is not in the status taxonomy", row)
    stored_failure = row.is_failure == 1
    status_failure = row.status in st.FAILURE_STATUSES
    if stored_failure or status_failure:
        reason = None if stored_failure == status_failure else \
            "stored failure flag and status disagree; reported as failure"
        return out(RunState.COLLECTION_FAILED, reason, row)
    if row.status in (st.NOT_IMPLEMENTED, st.SKIPPED_DISABLED):
        return out(RunState.NOT_ATTEMPTED, None, row)
    if row.new_documents > 0:
        if row.status == st.OK:
            return out(RunState.COLLECTED_NEW, None, row)
        return out(RunState.NO_HISTORY, "status reports no new documents but a count was stored", row)
    return out(RunState.COLLECTED_NO_NEW, None, row)


# ── Builder ──────────────────────────────────────────────────────────────────

def _family_dicts(entry) -> List[dict]:
    research = entry.research or {}
    _require(isinstance(research, dict), "%s research must be an object" % entry.slug)
    fams = research.get("source_families", [])
    _require(isinstance(fams, list), "%s source_families must be a list" % entry.slug)
    for fam in fams:
        _require(isinstance(fam, dict) and isinstance(fam.get("name"), str) and fam["name"],
                 "%s source family needs a name" % entry.slug)
        for key in ("format", "note", "publisher_url"):
            _opt_str(fam.get(key), "%s family %s" % (entry.slug, key))
    return fams


def _research_text(entry, key):
    return _opt_str((entry.research or {}).get(key), "%s research %s" % (entry.slug, key))


def _qualification(entry) -> Optional[Qualification]:
    q = entry.qualification
    if q is None:
        return None
    _require(isinstance(q, dict), "%s qualification must be an object" % entry.slug)
    days, checks = q.get("required_consecutive_days"), q.get("checkpoints")
    return Qualification(days if _is_int(days) else None,
                         checks if _is_int(checks) else None,
                         _opt_str(q.get("explanation"), entry.slug + " qualification explanation"))


def _reference_groups(family: FamilyBinding, lanes: Mapping[str, LaneSpec],
                      lane_data: Mapping[str, Optional[LaneData]],
                      seen_urls: set, conflicts: List[str]) -> List[ReferenceGroup]:
    groups = []
    for lane_id in family.reference_lanes:
        spec = lanes[lane_id]
        data = lane_data.get(lane_id)
        if data is None:
            conflicts.append("reference lane %s is unavailable; no links shown for %r"
                             % (lane_id, family.name))
            continue
        _require(isinstance(data, LaneData), "lane %s data has the wrong type" % lane_id)
        entries = []
        for ref in data.entries:
            _require(isinstance(ref, PublicReference), "lane %s entry has the wrong type" % lane_id)
            if spec.filter_by_source_slug and ref.source_slug != family.source_slug:
                continue
            if ref.url in seen_urls:
                conflicts.append("reference %s repeats a URL already shown on this desk; dropped" % ref.id)
                continue
            seen_urls.add(ref.url)
            entries.append(ref)
        if entries:
            groups.append(ReferenceGroup(
                lane_id=lane_id, kind=spec.kind, family_name=family.name,
                schema=data.schema, publisher=data.publisher, issuer=data.issuer,
                editorial_status=data.editorial_status, snapshot_date=data.snapshot_date,
                index_url=data.index_url, entries=tuple(entries)))
    return groups


def _build_desk(entry, binding: DeskBinding, bindings: Bindings,
                shadow: Mapping[str, ShadowDeclaration], production_slugs: set,
                lane_data, health, matched_health: set) -> DeskProvenance:
    conflicts: List[str] = []
    sources: List[SourceProvenance] = []
    collecting = entry.status in COLLECTING_DESK_STATUSES

    # 1. Contract-validated production sources, in manifest order.
    for src in entry.sources:
        if not src.contract_validated:
            continue
        if collecting:
            cls = EvidenceClass.PRODUCTION
            if health is not None and src.slug in health:
                matched_health.add(src.slug)
            run = classify_health(health.get(src.slug) if health is not None else None)
        else:
            cls, run = EvidenceClass.INSUFFICIENT_EVIDENCE, None
            conflicts.append("validated source %s sits on a non-collecting desk; not shown as production"
                             % src.slug)
        sources.append(SourceProvenance(
            name=src.display_name, evidence_class=cls, source_slug=src.slug,
            publisher_url=src.base_url, declared_format=None, note=src.notes,
            language_tags=(src.language_tag,) if src.language_tag else (),
            access_method=src.access_method, authority_tier=src.authority_tier,
            production_enabled=src.enabled, shadow_enabled=None, rights_statement=None,
            basis="Validated production manifest %s" % entry.manifest_path,
            reference_lanes=(), health=run))

    # 2. Research families, in registry order, classified by reviewed binding.
    registry_families = _family_dicts(entry)
    bound = {f.name: f for f in binding.families}
    registry_names = [f["name"] for f in registry_families]
    if len(set(registry_names)) != len(registry_names):
        conflicts.append("registry declares a source family name twice; repeats shown once")
    for stale in sorted(set(bound) - set(registry_names)):
        conflicts.append("binding names family %r, which the registry does not declare; ignored" % stale)

    seen_urls: set = set()
    references: List[ReferenceGroup] = []
    shown_slugs = {s.source_slug for s in sources if s.source_slug}
    done_names = set()
    for fam in registry_families:
        name = fam["name"]
        if name in done_names:
            continue
        done_names.add(name)
        fb = bound.get(name)
        decl = None
        if fb is None:
            cls, slug, basis, lanes = EvidenceClass.INSUFFICIENT_EVIDENCE, None, None, ()
            conflicts.append("family %r has no reviewed binding; shown as insufficient evidence" % name)
        else:
            cls, slug, basis, lanes = fb.evidence_class, fb.source_slug, fb.basis, fb.reference_lanes
            if slug is not None:
                if slug in production_slugs:
                    conflicts.append("family %r binds %s, which is a production slug; downgraded"
                                     % (name, slug))
                    cls, slug = EvidenceClass.INSUFFICIENT_EVIDENCE, None
                elif slug in shown_slugs:
                    conflicts.append("source %s appears twice on this desk; downgraded" % slug)
                    cls, slug = EvidenceClass.INSUFFICIENT_EVIDENCE, None
                else:
                    decl = shadow.get(slug)
                    if decl is None:
                        conflicts.append("family %r binds %s, which has no shadow declaration; downgraded"
                                         % (name, slug))
                        cls, decl = EvidenceClass.INSUFFICIENT_EVIDENCE, None
                    elif decl.desk_id not in binding.shadow_desk_ids:
                        conflicts.append("shadow source %s belongs to desk id %s, not this desk; downgraded"
                                         % (slug, decl.desk_id))
                        cls, decl = EvidenceClass.INSUFFICIENT_EVIDENCE, None
            elif cls is EvidenceClass.SHADOW:
                conflicts.append("family %r is bound as shadow without a declared slug; downgraded" % name)
                cls = EvidenceClass.INSUFFICIENT_EVIDENCE
            if cls is EvidenceClass.PUBLIC_REFERENCE and not lanes and not fam.get("publisher_url"):
                conflicts.append("family %r is a public reference with no link or lane; downgraded" % name)
                cls = EvidenceClass.INSUFFICIENT_EVIDENCE
            if fb is not None and cls is not EvidenceClass.INSUFFICIENT_EVIDENCE:
                references.extend(_reference_groups(fb, bindings.lanes, lane_data, seen_urls, conflicts))
        if slug is not None:
            shown_slugs.add(slug)
        sources.append(SourceProvenance(
            name=name, evidence_class=cls, source_slug=slug if decl is not None else None,
            publisher_url=fam.get("publisher_url"), declared_format=fam.get("format"),
            note=fam.get("note"),
            language_tags=decl.language_tags if decl else (),
            access_method=decl.access_method if decl else None,
            authority_tier=None, production_enabled=None,
            shadow_enabled=decl.shadow_enabled if decl else None,
            rights_statement=decl.rights_statement if decl else None,
            basis=basis, reference_lanes=tuple(g.lane_id for g in references if g.family_name == name),
            health=None))

    # 3. Registry-declared non-validated sources must each be a bound family.
    for src in entry.sources:
        if not src.contract_validated and src.slug not in shown_slugs:
            conflicts.append("registry source %s is not bound to a research family; shown as insufficient evidence"
                             % src.slug)
            sources.append(SourceProvenance(
                name=src.display_name, evidence_class=EvidenceClass.INSUFFICIENT_EVIDENCE,
                source_slug=None, publisher_url=None, declared_format=None, note=None,
                language_tags=(), access_method=None, authority_tier=None,
                production_enabled=None, shadow_enabled=None, rights_statement=None,
                basis=None, reference_lanes=(), health=None))

    return DeskProvenance(
        slug=entry.slug, name=entry.name, route=entry.route, scope=entry.scope,
        status=entry.status, status_label=entry.status_label,
        status_explanation=entry.status_explanation, public=entry.public,
        has_production_records=entry.has_production_records,
        limits=tuple(entry.limits),
        blockers=_pairs((entry.research or {}).get("blockers", []), entry.slug + " blockers"),
        resolved=_pairs((entry.research or {}).get("resolved", []), entry.slug + " resolved"),
        observed_volume=_pairs((entry.research or {}).get("observed_volume", []),
                               entry.slug + " observed_volume"),
        observed_volume_subject=_research_text(entry, "observed_volume_subject"),
        volume_caveat=_research_text(entry, "volume_caveat"),
        qualification=_qualification(entry),
        sources=tuple(sources), references=tuple(references), conflicts=tuple(conflicts))


def build_desk_provenance(registry: Iterable, bindings: Bindings,
                          shadow: Mapping[str, ShadowDeclaration],
                          lane_data: Mapping[str, Optional[LaneData]],
                          health: Optional[Mapping[str, HealthInput]],
                          *, as_of: str) -> ProvenanceAtlas:
    """Build the public provenance atlas. Pure and deterministic.

    ``health=None`` means no health input was supplied: production sources
    then report NO_HISTORY, never an assumed success.
    """
    _require(isinstance(as_of, str) and len(as_of) == 10, "as_of must be an ISO date string")
    entries = list(registry)
    slugs = [e.slug for e in entries]
    _require(len(set(slugs)) == len(slugs), "registry repeats a desk slug")
    _require(set(bindings.desks) == set(slugs),
             "bindings must cover exactly the registry desks (missing: %s; extra: %s)"
             % (sorted(set(slugs) - set(bindings.desks)), sorted(set(bindings.desks) - set(slugs))))
    for slug, decl in shadow.items():
        _require(isinstance(decl, ShadowDeclaration) and decl.slug == slug,
                 "shadow declaration %s is malformed" % slug)
    production_slugs = {s.slug for e in entries for s in e.sources if s.contract_validated}
    matched: set = set()
    desks = tuple(_build_desk(e, bindings.desks[e.slug], bindings, shadow, production_slugs,
                              lane_data, health, matched) for e in entries)

    bound_slugs = {f.source_slug for d in bindings.desks.values() for f in d.families if f.source_slug}
    registry_slugs = {s.slug for e in entries for s in e.sources}
    undisplayed = tuple(sorted(
        "%s (%s, desk id %s, shadow %s)" % (s, d.manifest, d.desk_id,
                                            "enabled" if d.shadow_enabled else "disabled")
        for s, d in shadow.items()
        if s not in bound_slugs and (s not in registry_slugs or s in production_slugs)))
    unmatched = tuple(sorted(set(health or {}) - matched))
    return ProvenanceAtlas(as_of=as_of, health_supplied=health is not None, desks=desks,
                           undisplayed_shadow_declarations=undisplayed,
                           unmatched_health_slugs=unmatched,
                           conflicts=tuple("%s: %s" % (d.slug, c) for d in desks for c in d.conflicts))


# ── Serialization ────────────────────────────────────────────────────────────

def _jsonable(value):
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(getattr(value, k)) for k in value.__dataclass_fields__}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


# Explicit publishable projection. Do not serialize the entire dataclass: it
# includes shadow declaration paths, unmatched health slugs, conflict diagnostics,
# run IDs and private source-binding pointers for maintainers.
_PUBLIC_DESK_FIELDS = (
    "slug", "name", "route", "scope", "status", "status_label",
    "status_explanation", "public", "has_production_records", "limits",
    "blockers", "resolved", "observed_volume", "observed_volume_subject",
    "volume_caveat", "qualification",
)
_PUBLIC_SOURCE_FIELDS = (
    # Provenance.note can include private production operator notes; the
    # shadow-manifest rights_statement also contains internal fixture/issue
    # diagnostics. Neither is approved for direct public JSON serialization.
    # Public limits and pre-approved reference links remain on their own
    # independently reviewed surfaces.
    "name", "evidence_class", "publisher_url", "declared_format",
    "language_tags", "access_method", "authority_tier",
)
_PUBLIC_REFERENCE_FIELDS = (
    "kind", "family_name", "publisher", "issuer", "editorial_status",
    "snapshot_date", "index_url",
)
_PUBLIC_LINK_FIELDS = (
    "url", "title_original", "published_date", "language", "press_number",
    "document_distribution_date",
)


def atlas_to_dict(atlas: ProvenanceAtlas) -> dict:
    """Only owner-reviewed public desk fields. No internal diagnostics or
    shadow/production operational identifiers; never infer a source's status.

    This intentionally uses *allowlists*, not a recursive dataclass dump.
    Adding a future internal dataclass field cannot publish it by accident.
    A non-public desk is excluded even if accidentally passed by a caller.
    """
    desks = []
    for d in atlas.desks:
        if not d.public:
            continue
        row = {key: _jsonable(getattr(d, key)) for key in _PUBLIC_DESK_FIELDS}
        row["sources"] = [
            {key: _jsonable(getattr(s, key)) for key in _PUBLIC_SOURCE_FIELDS}
            for s in d.sources
        ]
        row["references"] = []
        for group in d.references:
            item = {key: _jsonable(getattr(group, key))
                    for key in _PUBLIC_REFERENCE_FIELDS}
            item["entries"] = [
                {key: _jsonable(getattr(link, key)) for key in _PUBLIC_LINK_FIELDS}
                for link in group.entries
            ]
            row["references"].append(item)
        desks.append(row)
    return {"schema": ATLAS_SCHEMA, "as_of": atlas.as_of, "desks": desks}


def atlas_to_json(atlas: ProvenanceAtlas) -> str:
    """Public Source Atlas JSON; a build timestamp is not a health metric."""
    return json.dumps(atlas_to_dict(atlas), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atlas_to_internal_dict(atlas: ProvenanceAtlas) -> dict:
    """Engineering diagnostics only. Never pass into rendered output/routes."""
    data = _jsonable(atlas)
    data["schema"] = "ipr-desk-source-provenance-internal/1"
    return data


def atlas_to_internal_json(atlas: ProvenanceAtlas) -> str:
    """Internal review export, deliberately not exposed by the gather CLI."""
    return json.dumps(atlas_to_internal_dict(atlas),
                      ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_matrix(atlas: ProvenanceAtlas) -> str:
    """Deterministic eight-desk evidence matrix (Markdown). Run health values
    are omitted: they change every run and belong to the live page."""
    lines = ["| Desk | Status | " + " | ".join(c.value for c in EvidenceClass)
             + " | Reference links | Limits | Conflicts |",
             "|---|---|" + "---:|" * len(EvidenceClass) + "---:|---:|---:|"]
    for d in atlas.desks:
        counts = [str(len(d.sources_of(c))) for c in EvidenceClass]
        links = sum(g.link_count for g in d.references)
        lines.append("| %s | `%s` | %s | %d | %d | %d |"
                     % (_cell(d.name), d.status, " | ".join(counts), links,
                        len(d.limits), len(d.conflicts)))
    out = ["\n".join(lines), ""]
    for d in atlas.desks:
        out.append("### %s (`%s`)" % (d.name, d.slug))
        out.append("")
        out.append("Status: %s." % d.status_label)
        out.append("")
        if d.sources:
            out.append("| Source | Class | Slug | Languages | Access | Publisher URL |")
            out.append("|---|---|---|---|---|---|")
            for s in d.sources:
                out.append("| %s | `%s` | %s | %s | %s | %s |" % (
                    _cell(s.name), s.evidence_class.value,
                    "`%s`" % s.source_slug if s.source_slug else "—",
                    ", ".join(s.language_tags) or "unknown",
                    _cell(s.access_method) if s.access_method else "unknown",
                    "declared" if s.publisher_url else "none declared"))
        else:
            out.append("No source is declared for this desk.")
        out.append("")
        for g in d.references:
            out.append("- Reference lane `%s` (%s) for %s: %d outbound link(s); schema `%s`%s."
                       % (g.lane_id, g.kind, _cell(g.family_name), g.link_count, g.schema,
                          "; editorial status `%s`" % g.editorial_status if g.editorial_status else ""))
        if any(s.health is not None for s in d.sources):
            out.append("- Production run health applies to %d source(s), matched by exact slug; "
                       "values are omitted here because they change every run."
                       % sum(1 for s in d.sources if s.health is not None))
        out.append("- Limits preserved verbatim: %d. Blockers preserved verbatim: %d."
                   % (len(d.limits), len(d.blockers)))
        for c in d.conflicts:
            out.append("- Conflict: %s" % _cell(c))
        out.append("")
    if atlas.undisplayed_shadow_declarations:
        out.append("### Shadow declarations not shown on any desk panel")
        out.append("")
        for s in atlas.undisplayed_shadow_declarations:
            out.append("- %s" % s)
        out.append("")
    return "\n".join(out).rstrip() + "\n"
