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

It is also conservative about writing at all. Every upsert below is guarded by
a comparison against what is already stored, and a row whose values already
match is skipped rather than rewritten. That is not an optimisation: this
repository TRACKS its database file, and an unconditional upsert that writes
the values already present changes no data while changing the file — SQLite
bumps the header change counter on any committed write transaction. A daily
workflow that runs migrations would then produce a database diff on a run where
nothing was collected, which is a commit asserting the corpus moved when it did
not. `tests/test_migration_byte_stability.py` pins the property in bytes,
because a logical fingerprint cannot see it.
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
    Derive the legacy `sources.language` value from a BCP 47 tag.

    `language` is a deprecated compatibility mirror; `language_tag` is
    authoritative. The value written here is the tag's **primary language
    subtag** — `zh-Hans` → `zh`, `en` → `en`, `ru-RU` → `ru` — which is a
    defensible narrowing of the same fact, not a substitution of a different
    language.

    Until migration 0005 this raised for anything outside zh/en, because the
    column carried `CHECK (language IN ('zh','en'))` and silently coercing `ru`
    to `en` would have corrupted the corpus undetectably. 0005 removed that
    finite CHECK, so the honest narrowing is now writable and the refusal is
    gone. No new finite list replaces it — validation of the tag itself belongs
    in the manifest layer, which reports the file and field.
    """
    primary = (language_tag or "").split("-")[0].lower()
    if not primary or not primary.isalpha() or not (2 <= len(primary) <= 3):
        raise RegistryError(
            "cannot derive a legacy language value from tag %r: the primary "
            "subtag must be 2-3 ASCII letters. Manifest validation should have "
            "rejected this before persistence." % (language_tag,)
        )
    return primary


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
        # Rows examined and found already correct. Reported rather than
        # silently omitted: "nothing was written" and "nothing was checked"
        # are different facts, and only one of them is healthy.
        "desks_unchanged": 0, "institutions_unchanged": 0,
        "sources_unchanged": 0,
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

    # Atomic across ALL desks. Review found that a manifest whose source failed
    # validation still left that desk's `desks` and `institutions` rows behind:
    # each statement committed as it went, so a partial configuration survived a
    # failed sync. Configuration must be all-or-nothing — a desk row with no
    # sources is a state no manifest describes.
    savepoint = "desk_config_sync"
    conn.execute("SAVEPOINT %s" % savepoint)
    try:
        for cfg in configs.values():
            _sync_one_desk(conn, cfg, managed, report)
    except Exception:
        conn.execute("ROLLBACK TO %s" % savepoint)
        conn.execute("RELEASE %s" % savepoint)
        logger.error(
            "desk config sync failed — rolled back; the previous valid "
            "configuration is intact"
        )
        raise
    conn.execute("RELEASE %s" % savepoint)

    logger.info(
        "desk config synced: %d desk(s) written / %d already correct, "
        "%d institution(s) written / %d already correct, "
        "%d source(s) updated, %d inserted, %d already correct",
        report["desks"], report["desks_unchanged"],
        report["institutions"], report["institutions_unchanged"],
        report["sources_updated"], report["sources_inserted"],
        report["sources_unchanged"],
    )
    return report


def _unchanged(conn: sqlite3.Connection, table: str, key_column: str,
               key: str, columns: List[str], values: List[object]) -> bool:
    """
    True when the stored row already holds exactly these values.

    Compared through the same column order the write would use, so the
    comparison cannot drift from the statement it guards. A missing row is
    never "unchanged" — it has to be inserted.
    """
    row = conn.execute(
        "SELECT %s FROM %s WHERE %s = ?" % (", ".join(columns), table,
                                            key_column),
        (key,),
    ).fetchone()
    if row is None:
        return False
    return all(stored == wanted for stored, wanted in zip(row, values))


def _sync_one_desk(
    conn: sqlite3.Connection, cfg: DeskConfig, managed: List[str],
    report: Dict[str, int],
) -> None:
    d = cfg.desk
    desk_columns = ["display_name", "jurisdiction_code", "default_timezone",
                    "default_calendar", "supported_language_tags", "active",
                    "public_status"]
    desk_values = [
        d.display_name, d.jurisdiction_code, d.default_timezone,
        d.default_calendar,
        json.dumps(d.supported_language_tags, ensure_ascii=False),
        1 if d.active else 0, d.public_status,
    ]
    if _unchanged(conn, "desks", "desk_id", d.desk_id, desk_columns,
                  desk_values):
        report["desks_unchanged"] += 1
    else:
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
            [d.desk_id] + desk_values,
        )
        report["desks"] += 1

    inst_columns = ["desk_id", "display_name", "name_original",
                    "institution_type", "parent_institution_id",
                    "active_from", "active_to"]
    for inst in cfg.institutions:
        inst_values = [
            inst.desk_id, inst.display_name, inst.name_original,
            inst.institution_type, inst.parent_institution_id,
            inst.active_from, inst.active_to,
        ]
        if _unchanged(conn, "institutions", "institution_id",
                      inst.institution_id, inst_columns, inst_values):
            report["institutions_unchanged"] += 1
            continue
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
            [inst.institution_id] + inst_values,
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
            # production holds them — and even the managed columns are written
            # only when one of them actually differs.
            wanted = [values[c] for c in managed]
            if _unchanged(conn, "sources", "slug", src.slug, managed, wanted):
                report["sources_unchanged"] += 1
                continue
            conn.execute(
                "UPDATE sources SET %s WHERE slug = ?"
                % ", ".join("%s = ?" % c for c in managed),
                wanted + [src.slug],
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
