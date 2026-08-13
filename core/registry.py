"""
Source registry and desk-configuration sync.

Two jobs:

  1. `sync_desk_config(conn)` — write desk, institution and source metadata from
     `desks/*/manifest.json` into the database, idempotently. This is what makes
     the schema survive `reconcile_db.py`: everything it writes is derived from
     tracked config, so re-running it after a reconcile restores the state
     rather than requiring a hand repair.

  2. `SourceRegistry` — resolve slugs to adapters, entirely from configuration.
     `core/` names no scraper class anywhere; the dotted path comes from the
     manifest. This is the specific coupling Phase 2 was asked to remove.

Sync is deliberately conservative about legacy columns. For a source row that
already exists it writes ONLY the columns migration 0003 added, and never
touches `display_name`, `base_url`, `language` or `is_active`. A config sync
must not be able to rename a live source or re-point it at a different host.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from core.domain import DeskConfig, Source
from core.manifests import load_all_desks

logger = logging.getLogger("registry")

# Columns migration 0003 added. Sync owns exactly these on an existing row.
_MANAGED_SOURCE_COLUMNS = (
    "desk_id", "institution_id", "language_tag", "timezone", "calendar",
    "authority_tier", "source_type", "originality", "expected_cadence_days",
    "silence_threshold_days", "access_method", "enabled", "active_from",
    "active_to", "listing_endpoints", "article_url_patterns", "notes",
)


class RegistryError(RuntimeError):
    pass


def _legacy_language(language_tag: str) -> str:
    """
    Map a BCP 47 tag onto the legacy `sources.language` column.

    That column carries `CHECK (language IN ('zh','en'))` from the original
    schema. It is kept (nothing is dropped in Phase 1) and still written so the
    existing pipeline and site keep reading what they always have.

    This raises rather than guessing for any other language, and that is a real
    forward constraint worth stating plainly: **a Russia or Iran desk cannot be
    synced until a migration relaxes or retires that CHECK.** Silently coercing
    'ru' to 'en' would corrupt the corpus in a way nothing downstream could
    detect.
    """
    primary = (language_tag or "").split("-")[0].lower()
    if primary in ("zh", "en"):
        return primary
    raise RegistryError(
        "language tag %r maps to legacy language %r, which the existing "
        "sources.language CHECK constraint rejects (it permits only 'zh' and "
        "'en'). Relaxing that constraint is a prerequisite migration for any "
        "non-Chinese/English desk — see docs/SCHEMA_AND_MIGRATIONS.md."
        % (language_tag, primary)
    )


def _source_values(src: Source) -> Dict[str, object]:
    return {
        "desk_id": src.desk_id,
        "institution_id": src.institution_id,
        "language_tag": src.language_tag,
        "timezone": src.timezone,
        "calendar": src.calendar,
        "authority_tier": src.authority_tier,
        "source_type": src.source_type,
        "originality": src.originality,
        "expected_cadence_days": src.expected_cadence_days,
        "silence_threshold_days": src.silence_threshold_days,
        "access_method": src.access_method,
        "enabled": 1 if src.enabled else 0,
        "active_from": src.active_from,
        "active_to": src.active_to,
        "listing_endpoints": json.dumps(src.listing_endpoints, ensure_ascii=False),
        "article_url_patterns": json.dumps(
            src.article_url_patterns, ensure_ascii=False
        ),
        "notes": src.notes,
    }


def sync_desk_config(
    conn: sqlite3.Connection, desks_dir: Optional[Path] = None
) -> Dict[str, int]:
    """
    Upsert desks, institutions and source metadata from manifests.

    Idempotent: running twice changes nothing the second time. Returns a small
    report of what it touched.
    """
    configs = load_all_desks(desks_dir)
    report = {
        "desks": 0, "institutions": 0,
        "sources_updated": 0, "sources_inserted": 0,
    }

    have_tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if not {"desks", "institutions"} <= have_tables:
        raise RegistryError(
            "desks/institutions tables missing — run migrations before syncing"
        )

    source_cols = {r[1] for r in conn.execute("PRAGMA table_info(sources)")}
    managed = [c for c in _MANAGED_SOURCE_COLUMNS if c in source_cols]
    if not managed:
        raise RegistryError(
            "sources table has none of the desk metadata columns — "
            "migration 0003 has not been applied"
        )

    for cfg in configs.values():
        _sync_one_desk(conn, cfg, managed, report)

    logger.info(
        "desk config synced: %d desk(s), %d institution(s), "
        "%d source(s) updated, %d inserted",
        report["desks"], report["institutions"],
        report["sources_updated"], report["sources_inserted"],
    )
    return report


def _sync_one_desk(
    conn: sqlite3.Connection, cfg: DeskConfig, managed: List[str],
    report: Dict[str, int],
) -> None:
    d = cfg.desk
    conn.execute(
        """
        INSERT INTO desks (desk_id, display_name, jurisdiction_code,
                           default_timezone, default_calendar,
                           supported_language_tags, active, public_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(desk_id) DO UPDATE SET
            display_name            = excluded.display_name,
            jurisdiction_code       = excluded.jurisdiction_code,
            default_timezone        = excluded.default_timezone,
            default_calendar        = excluded.default_calendar,
            supported_language_tags = excluded.supported_language_tags,
            active                  = excluded.active,
            public_status           = excluded.public_status
        """,
        (d.desk_id, d.display_name, d.jurisdiction_code, d.default_timezone,
         d.default_calendar,
         json.dumps(d.supported_language_tags, ensure_ascii=False),
         1 if d.active else 0, d.public_status),
    )
    report["desks"] += 1

    for inst in cfg.institutions:
        conn.execute(
            """
            INSERT INTO institutions (institution_id, desk_id, display_name,
                                      name_original, institution_type,
                                      parent_institution_id, active_from, active_to)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(institution_id) DO UPDATE SET
                desk_id               = excluded.desk_id,
                display_name          = excluded.display_name,
                name_original         = excluded.name_original,
                institution_type      = excluded.institution_type,
                parent_institution_id = excluded.parent_institution_id,
                active_from           = excluded.active_from,
                active_to             = excluded.active_to
            """,
            (inst.institution_id, inst.desk_id, inst.display_name,
             inst.name_original, inst.institution_type,
             inst.parent_institution_id, inst.active_from, inst.active_to),
        )
        report["institutions"] += 1

    for src in cfg.sources:
        values = _source_values(src)
        exists = conn.execute(
            "SELECT 1 FROM sources WHERE slug = ?", (src.slug,)
        ).fetchone()

        if exists:
            # Existing, live source: touch only the managed metadata columns.
            # display_name / base_url / language / is_active are left exactly as
            # production holds them.
            conn.execute(
                "UPDATE sources SET %s WHERE slug = ?"
                % ", ".join("%s = ?" % c for c in managed),
                [values[c] for c in managed] + [src.slug],
            )
            report["sources_updated"] += 1
        else:
            cols = ["slug", "display_name", "base_url", "language", "is_active"] + managed
            vals = [
                src.slug, src.display_name, src.base_url,
                _legacy_language(src.language_tag), 1 if src.enabled else 0,
            ] + [values[c] for c in managed]
            conn.execute(
                "INSERT INTO sources (%s) VALUES (%s)"
                % (", ".join(cols), ", ".join("?" * len(cols))),
                vals,
            )
            report["sources_inserted"] += 1


# ── Registry ──────────────────────────────────────────────────────────────────

class SourceRegistry:
    """
    Slug → adapter, driven entirely by desk manifests.

    Construction performs no network I/O and no adapter instantiation, so it is
    safe to build in a test.
    """

    def __init__(self, desks_dir: Optional[Path] = None) -> None:
        self.configs: Dict[str, DeskConfig] = load_all_desks(desks_dir)
        self._sources: Dict[str, Source] = {}
        for cfg in self.configs.values():
            for src in cfg.sources:
                self._sources[src.slug] = src

    # -- lookup ---------------------------------------------------------------

    def __contains__(self, slug: str) -> bool:
        return slug in self._sources

    def get_source(self, slug: str) -> Optional[Source]:
        return self._sources.get(slug)

    @property
    def slugs(self) -> List[str]:
        return sorted(self._sources)

    def slugs_for_desk(self, desk_id: str) -> List[str]:
        return sorted(
            s.slug for s in self._sources.values() if s.desk_id == desk_id
        )

    def enabled_slugs(self, desk_id: Optional[str] = None) -> List[str]:
        return sorted(
            s.slug for s in self._sources.values()
            if s.enabled and (desk_id is None or s.desk_id == desk_id)
        )

    # -- adapters -------------------------------------------------------------

    def get_adapter(self, slug: str):
        """
        Build the adapter for one slug.

        Import happens here, at call time, from the manifest's dotted path —
        never at module scope in `core/`. That is what lets the core pipeline
        run with no knowledge of which country's scrapers exist.
        """
        src = self.get_source(slug)
        if src is None:
            raise RegistryError(
                "no desk manifest declares source %r (known: %s)"
                % (slug, ", ".join(self.slugs))
            )
        if not src.adapter:
            raise RegistryError(
                "source %r declares no adapter in its desk manifest" % slug
            )
        from adapters.legacy import LegacyScraperAdapter
        return LegacyScraperAdapter(src)

    def healthcheck_all(self) -> List:
        """Offline configuration healthcheck for every source."""
        from core.collection import status as st
        from core.collection.contract import SourceHealthResult

        out = []
        for slug in self.slugs:
            try:
                out.append(self.get_adapter(slug).healthcheck())
            except Exception as exc:
                out.append(
                    SourceHealthResult(slug, st.ADAPTER_ERROR, str(exc)[:200])
                )
        return out


_DEFAULT: Optional[SourceRegistry] = None


def get_registry(refresh: bool = False) -> SourceRegistry:
    """Process-wide registry. `refresh=True` reloads manifests from disk."""
    global _DEFAULT
    if _DEFAULT is None or refresh:
        _DEFAULT = SourceRegistry()
    return _DEFAULT
