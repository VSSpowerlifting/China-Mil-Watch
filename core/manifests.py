"""
Desk manifest loading and validation.

Manifests are JSON, not YAML, deliberately: the CI runner is Python 3.9 and
JSON needs no third-party parser. Adding PyYAML to buy nicer comment syntax
would put a new dependency on the daily collection path for a cosmetic gain.

Validation is strict and loud. A desk manifest that names an unknown authority
tier, omits an identifier, or reuses a slug must fail with a message that says
which file, which record, and what the permitted values are — never be silently
ignored, defaulted, or coerced. A silently-dropped source is exactly the class
of failure this project has already been bitten by (a configured Xinhua source
contributing zero rows while every run reported success).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from core.domain import (
    ACCESS_METHODS,
    AUTHORITY_TIERS,
    CALENDARS,
    INSTITUTION_TYPES,
    ORIGINALITY,
    PUBLIC_STATUSES,
    Desk,
    DeskConfig,
    Institution,
    Source,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DESKS_DIR = REPO_ROOT / "desks"


class ManifestError(ValueError):
    """Raised when a desk manifest is malformed. Never caught internally."""


def _require(mapping: dict, key: str, where: str):
    if key not in mapping or mapping[key] is None:
        raise ManifestError("%s: missing required field %r" % (where, key))
    value = mapping[key]
    if isinstance(value, str) and not value.strip():
        raise ManifestError("%s: required field %r is empty" % (where, key))
    return value


def _check_enum(value, permitted, key: str, where: str):
    if value not in permitted:
        raise ManifestError(
            "%s: %r is not a valid %s (permitted: %s)"
            % (where, value, key, ", ".join(map(str, permitted)))
        )
    return value


def _check_language_tag(tag: str, where: str) -> str:
    """
    Minimal BCP 47 shape check.

    Deliberately structural rather than a registry lookup: the point is to
    reject the legacy bare codes this project used ('zh' meaning "Chinese,
    script unspecified") drifting back in unnoticed, not to police every
    subtag. 'zh-Hans' and 'en' both pass; 'chinese' and 'zh_CN' do not.
    """
    if not tag or not isinstance(tag, str):
        raise ManifestError("%s: language tag must be a non-empty string" % where)
    parts = tag.split("-")
    if not all(p and p.isalnum() and p.isascii() for p in parts):
        raise ManifestError(
            "%s: %r is not a well-formed BCP 47 tag (use e.g. 'zh-Hans', "
            "'ru-RU', 'en'; underscores and spaces are not valid separators)"
            % (where, tag)
        )
    if not (2 <= len(parts[0]) <= 3) or not parts[0].isalpha():
        raise ManifestError(
            "%s: %r has an invalid primary language subtag" % (where, tag)
        )
    return tag


def _parse_desk(raw: dict, where: str) -> Desk:
    langs = _require(raw, "supported_language_tags", where)
    if not isinstance(langs, list) or not langs:
        raise ManifestError(
            "%s: supported_language_tags must be a non-empty list" % where
        )
    for tag in langs:
        _check_language_tag(tag, "%s.supported_language_tags" % where)

    return Desk(
        desk_id=_require(raw, "desk_id", where),
        display_name=_require(raw, "display_name", where),
        jurisdiction_code=_require(raw, "jurisdiction_code", where),
        default_timezone=_require(raw, "default_timezone", where),
        default_calendar=_check_enum(
            raw.get("default_calendar", "gregorian"), CALENDARS,
            "calendar", where,
        ),
        supported_language_tags=list(langs),
        public_status=_check_enum(
            _require(raw, "public_status", where), PUBLIC_STATUSES,
            "public_status", where,
        ),
        active=bool(raw.get("active", True)),
    )


def _parse_institution(raw: dict, desk_id: str, where: str) -> Institution:
    return Institution(
        institution_id=_require(raw, "institution_id", where),
        desk_id=desk_id,
        display_name=_require(raw, "display_name", where),
        institution_type=_check_enum(
            _require(raw, "institution_type", where), INSTITUTION_TYPES,
            "institution_type", where,
        ),
        name_original=raw.get("name_original"),
        parent_institution_id=raw.get("parent_institution_id"),
        active_from=raw.get("active_from"),
        active_to=raw.get("active_to"),
    )


def _parse_source(raw: dict, desk: Desk, where: str) -> Source:
    cadence = raw.get("expected_cadence_days")
    if cadence is not None:
        try:
            cadence = float(cadence)
        except (TypeError, ValueError):
            raise ManifestError(
                "%s: expected_cadence_days must be a number, got %r"
                % (where, raw.get("expected_cadence_days"))
            )
        if cadence <= 0:
            raise ManifestError(
                "%s: expected_cadence_days must be positive, got %r"
                % (where, cadence)
            )

    for list_field in ("listing_endpoints", "article_url_patterns"):
        if list_field in raw and not isinstance(raw[list_field], list):
            raise ManifestError("%s: %s must be a list" % (where, list_field))

    return Source(
        slug=_require(raw, "slug", where),
        desk_id=desk.desk_id,
        institution_id=_require(raw, "institution_id", where),
        display_name=_require(raw, "display_name", where),
        base_url=_require(raw, "base_url", where),
        language_tag=_check_language_tag(
            _require(raw, "language_tag", where), where
        ),
        timezone=raw.get("timezone") or desk.default_timezone,
        calendar=_check_enum(
            raw.get("calendar", desk.default_calendar), CALENDARS,
            "calendar", where,
        ),
        access_method=_check_enum(
            _require(raw, "access_method", where), ACCESS_METHODS,
            "access_method", where,
        ),
        authority_tier=_check_enum(
            _require(raw, "authority_tier", where), AUTHORITY_TIERS,
            "authority_tier", where,
        ),
        source_type=_require(raw, "source_type", where),
        originality=_check_enum(
            _require(raw, "originality", where), ORIGINALITY,
            "originality", where,
        ),
        expected_cadence_days=cadence,
        silence_threshold_days=(
            int(raw["silence_threshold_days"])
            if raw.get("silence_threshold_days") is not None else None
        ),
        adapter=raw.get("adapter"),
        enabled=bool(raw.get("enabled", True)),
        active_from=raw.get("active_from"),
        active_to=raw.get("active_to"),
        listing_endpoints=list(raw.get("listing_endpoints", [])),
        article_url_patterns=list(raw.get("article_url_patterns", [])),
        notes=raw.get("notes"),
    )


def load_manifest(path: Path) -> DeskConfig:
    """Load and validate one desk manifest. Raises ManifestError on any defect."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ManifestError("manifest not found: %s" % path)
    except json.JSONDecodeError as exc:
        raise ManifestError("%s: invalid JSON — %s" % (path.name, exc))

    if not isinstance(raw, dict):
        raise ManifestError("%s: manifest must be a JSON object" % path.name)

    where = path.name
    desk = _parse_desk(_require(raw, "desk", where), "%s:desk" % where)

    institutions: List[Institution] = []
    seen_institutions = set()
    for i, item in enumerate(raw.get("institutions", [])):
        loc = "%s:institutions[%d]" % (where, i)
        inst = _parse_institution(item, desk.desk_id, loc)
        if inst.institution_id in seen_institutions:
            raise ManifestError(
                "%s: duplicate institution_id %r" % (loc, inst.institution_id)
            )
        seen_institutions.add(inst.institution_id)
        institutions.append(inst)

    sources: List[Source] = []
    seen_slugs = set()
    for i, item in enumerate(raw.get("sources", [])):
        loc = "%s:sources[%d]" % (where, i)
        src = _parse_source(item, desk, loc)
        if src.slug in seen_slugs:
            raise ManifestError("%s: duplicate source slug %r" % (loc, src.slug))
        seen_slugs.add(src.slug)
        if src.institution_id not in seen_institutions:
            raise ManifestError(
                "%s: source %r references unknown institution_id %r "
                "(declared institutions: %s)"
                % (loc, src.slug, src.institution_id,
                   ", ".join(sorted(seen_institutions)) or "none")
            )
        if src.language_tag not in desk.supported_language_tags:
            raise ManifestError(
                "%s: source %r uses language tag %r which the desk does not "
                "declare in supported_language_tags (%s)"
                % (loc, src.slug, src.language_tag,
                   ", ".join(desk.supported_language_tags))
            )
        sources.append(src)

    for inst in institutions:
        if (inst.parent_institution_id
                and inst.parent_institution_id not in seen_institutions):
            raise ManifestError(
                "%s: institution %r names unknown parent_institution_id %r"
                % (where, inst.institution_id, inst.parent_institution_id)
            )

    return DeskConfig(desk=desk, institutions=institutions, sources=sources)


def load_all_desks(desks_dir: Optional[Path] = None) -> Dict[str, DeskConfig]:
    """
    Load every desk manifest under `desks/`.

    Raises on the first malformed manifest and on any desk_id or source slug
    reused across desks — a slug collision between desks would silently merge
    two countries' collection history into one row.
    """
    base = Path(desks_dir or DESKS_DIR)
    configs: Dict[str, DeskConfig] = {}
    slug_owner: Dict[str, str] = {}

    for manifest_path in sorted(base.glob("*/manifest.json")):
        cfg = load_manifest(manifest_path)
        if cfg.desk.desk_id in configs:
            raise ManifestError(
                "duplicate desk_id %r (second occurrence in %s)"
                % (cfg.desk.desk_id, manifest_path)
            )
        for src in cfg.sources:
            if src.slug in slug_owner:
                raise ManifestError(
                    "source slug %r is claimed by both desk %r and desk %r; "
                    "slugs must be unique across all desks"
                    % (src.slug, slug_owner[src.slug], cfg.desk.desk_id)
                )
            slug_owner[src.slug] = cfg.desk.desk_id
        configs[cfg.desk.desk_id] = cfg

    return configs
