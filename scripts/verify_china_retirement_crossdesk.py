"""Verify a China-only archive retirement preserves unrelated live desk data.

Compare exact SQLite source rows and DDL on the source database and the
throwaway retired database. The four U.S. first-party metadata tables are
independent of the article corpus: their observations and official-link rows
must stay byte-for-byte equivalent across a 4,400-row China deletion.

Read-only: the source uses the repository's read_only helper; the destination
uses immutable SQLite URI. This script neither publishes nor modifies a DB.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from scripts.reconcile_db import read_only

PRESERVED = (
    "sources",
    "uscc_official_source_records",
    "uscc_official_observations",
    "treasury_official_source_records",
    "treasury_official_observations",
)
SOURCE_FAMILIES = (
    ("uscc_official_source_records", "uscc_official_observations"),
    ("treasury_official_source_records", "treasury_official_observations"),
)


def _encode(v):
    """Preserve SQLite type differences, bytes, and exact float bit-equivalent text."""
    if v is None:
        return ["null"]
    if type(v) is int:
        return ["int", str(v)]
    if type(v) is float:
        return ["real", v.hex()]
    if type(v) is bytes:
        return ["blob", v.hex()]
    if type(v) is str:
        return ["text", v]
    raise ValueError("unknown SQLite column type")


def _snapshot(con, table):
    if not con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone():
        return None
    escaped = '"' + table.replace('"', '""') + '"'
    rows = [
        json.dumps([_encode(v) for v in row], ensure_ascii=False,
                   separators=(",", ":"), sort_keys=True)
        for row in con.execute("SELECT * FROM " + escaped)
    ]
    rows.sort()
    ddl = sorted(
        (str(typ), str(name), str(sql) if sql is not None else "")
        for typ, name, sql in con.execute(
            "SELECT type,name,sql FROM sqlite_master "
            "WHERE (name=? AND type='table') "
            "OR (tbl_name=? AND type IN ('index','trigger'))",
            (table, table),
        )
    )
    payload = json.dumps({"schema": ddl, "rows": rows}, ensure_ascii=False,
                         separators=(",", ":"), sort_keys=True).encode()
    return {"rows": len(rows), "sha256": sha256(payload).hexdigest(),
            "schema_sha256": sha256(
                json.dumps(ddl, separators=(",", ":")).encode()
            ).hexdigest()}


def validate(source_db, retired_db):
    source_db = Path(source_db).resolve(strict=True)
    retired_db = Path(retired_db).resolve(strict=True)
    if source_db == retired_db:
        raise ValueError("source and retired database must be distinct")
    with read_only(source_db) as original:
        with sqlite3.connect(retired_db.as_uri() + "?mode=ro&immutable=1",
                             uri=True) as reduced:
            before = {t: _snapshot(original, t) for t in PRESERVED}
            after = {t: _snapshot(reduced, t) for t in PRESERVED}
    if before["sources"] is None:
        raise ValueError("source registry table missing in original SQLite")
    for a, b in SOURCE_FAMILIES:
        if (before[a] is None) != (before[b] is None):
            raise ValueError("partial official metadata family in original SQLite: " + a)
    for table in PRESERVED:
        if before[table] != after[table]:
            raise ValueError(
                "Unrelated desk source table changed during China retirement: " + table
            )
    return {
        "preserved_tables": {
            table: snapshot for table, snapshot in before.items()
            if snapshot is not None
        },
        "official_source_rows": {
            table: before[table]["rows"] if before[table] is not None else None
            for table in (
                "uscc_official_source_records", "treasury_official_source_records"
            )
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--retired-db", type=Path, required=True)
    a = parser.parse_args()
    print(json.dumps(validate(a.source_db, a.retired_db),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
