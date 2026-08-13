"""
0005 — remove the finite zh/en CHECK from the legacy `sources.language` column.

The original schema declared `language TEXT NOT NULL CHECK (language IN
('zh','en'))`. That made the persistence layer country-specific in a way the
domain layer is not: `core/manifests.py` validates any well-formed BCP 47 tag,
but a source with `language_tag: "ru"` could not be written at all, because the
compatibility value derived for the legacy column violated the constraint.

Review called this correctly — the foundation cannot be described as neutral
while persistence rejects valid tags. The previous behaviour (raise rather than
coerce) was the right *interim* choice: silently mapping `ru` to `en` would
corrupt the corpus in a way nothing downstream could detect. But refusing to
persist is not neutrality either.

What this changes and what it does not:

  * The CHECK is removed. The column stays, stays `NOT NULL`, and every current
    value is preserved byte-for-byte.
  * No new finite CHECK replaces it. Enumerating permitted languages in the
    database would recreate exactly this problem for the next desk, and would
    put a geopolitical list in a schema constraint. Validation belongs in the
    manifest layer, where the error message can name the file and the field.
  * `language_tag` (BCP 47) is the authoritative modern field. `language` is a
    deprecated compatibility mirror, written with the primary language subtag.

`sources.id` values are preserved exactly: `articles.source_id` references them,
and those articles are published at id-derived URLs.
"""

from __future__ import annotations

import sqlite3

VERSION = "0005"
NAME = "relax_source_language_check"

# The full post-0003 shape, minus the language CHECK. Stated explicitly rather
# than reflected off the live table so this migration is deterministic: 0003
# always precedes it, so these columns are always the ones present.
_NEW_TABLE = """
CREATE TABLE sources_migrated (
    id           INTEGER PRIMARY KEY,
    slug         TEXT    NOT NULL UNIQUE,
    display_name TEXT    NOT NULL,
    base_url     TEXT    NOT NULL,
    -- Deprecated compatibility mirror of language_tag. No CHECK: the permitted
    -- set of languages is not a property of the schema. See migration docstring.
    language     TEXT    NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),

    desk_id                TEXT,
    institution_id         TEXT,
    language_tag           TEXT,
    timezone               TEXT,
    calendar               TEXT,
    authority_tier         TEXT,
    source_type            TEXT,
    originality            TEXT,
    expected_cadence_days  REAL,
    silence_threshold_days INTEGER,
    access_method          TEXT,
    enabled                INTEGER,
    active_from            TEXT,
    active_to              TEXT,
    listing_endpoints      TEXT,
    article_url_patterns   TEXT,
    notes                  TEXT
)
"""

_COLUMNS = (
    "id, slug, display_name, base_url, language, is_active, created_at, "
    "desk_id, institution_id, language_tag, timezone, calendar, "
    "authority_tier, source_type, originality, expected_cadence_days, "
    "silence_threshold_days, access_method, enabled, active_from, active_to, "
    "listing_endpoints, article_url_patterns, notes"
)


def _language_check_is_finite(conn: sqlite3.Connection) -> bool:
    """
    True when the live table still constrains `language` to a finite set.

    Behavioural, not textual: probe the constraint by attempting a write the old
    CHECK would reject and rolling it back. A substring search over
    `sqlite_master` would be fooled by the word appearing in a comment.
    """
    savepoint = "probe_language_check"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        conn.execute(
            "INSERT INTO sources (slug, display_name, base_url, language) "
            "VALUES ('__probe__', 'probe', 'https://example.invalid', 'xx')"
        )
        return False          # accepted → no finite CHECK
    except sqlite3.IntegrityError:
        return True           # rejected → CHECK still present
    finally:
        conn.execute(f"ROLLBACK TO {savepoint}")
        conn.execute(f"RELEASE {savepoint}")


def is_already_applied(conn: sqlite3.Connection) -> bool:
    return not _language_check_is_finite(conn)


def up(conn: sqlite3.Connection) -> None:
    before = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    before_rows = conn.execute(
        "SELECT id, slug, display_name, base_url, language FROM sources ORDER BY id"
    ).fetchall()

    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute(_NEW_TABLE)
        conn.execute(
            "INSERT INTO sources_migrated (%s) SELECT %s FROM sources"
            % (_COLUMNS, _COLUMNS)
        )
        conn.execute("DROP TABLE sources")
        conn.execute("ALTER TABLE sources_migrated RENAME TO sources")
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")

    # 0003's index lived on the dropped table.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_desk ON sources(desk_id)")

    after = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    after_rows = conn.execute(
        "SELECT id, slug, display_name, base_url, language FROM sources ORDER BY id"
    ).fetchall()
    if after != before or after_rows != before_rows:
        raise RuntimeError(
            "sources identity changed during rebuild (%d -> %d rows); "
            "articles.source_id references these ids" % (before, after)
        )
