#!/usr/bin/env python3
"""Gather real inputs and print the public desk source-provenance atlas.

Read-only. Reads the desk registry, the reviewed provenance bindings, the
shadow workflow declarations and manifests, the gated public reference
loaders and — unless ``--no-health`` — ``source_run_results`` through
``scripts.reconcile_db.read_only``. No network I/O, no model calls, no writes
except an explicit ``--json`` / ``--matrix`` output path.

Usage:
    .venv/bin/python scripts/desk_source_provenance.py --no-health
    .venv/bin/python scripts/desk_source_provenance.py --json atlas.json
    .venv/bin/python scripts/desk_source_provenance.py --no-health --matrix -
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core import desk_source_provenance as dsp                 # noqa: E402
from core.desk_registry import load_registry                   # noqa: E402

KOREA_SCHEMA = "ipr-korea-bibliography-only/1"


def _header(path: Path) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if isinstance(v, str)}


def _korea():
    from core.korea_public_bibliography import load_public_korea_links
    rows = load_public_korea_links()
    # The loader itself requires issuer 국방부 and publisher 대한민국 정책브리핑
    # on every row; nothing here is asserted beyond what it enforces.
    return dsp.LaneData(
        schema=KOREA_SCHEMA, publisher="대한민국 정책브리핑", issuer="국방부",
        editorial_status=None, snapshot_date=None,
        entries=tuple(dsp.PublicReference(
            id=r["source_identity"], url=r["source_url"],
            title_original=r["title_original"], published_date=r["published_date"],
            language="ko", document_distribution_date=r["document_distribution_date"])
            for r in rows))


def _indonesia_index(module):
    rows = module.load()
    head = _header(module.DEFAULT)
    return dsp.LaneData(
        schema=head["schema"], publisher=head.get("publisher"), issuer=None,
        editorial_status=head.get("editorial_status"), snapshot_date=head.get("snapshot_date"),
        index_url=head.get("category_url"),
        entries=tuple(dsp.PublicReference(
            id=r["id"], url=r["source_url"], title_original=r["title_original"],
            published_date=r["published_date"], language=r.get("language"),
            press_number=r.get("press_number")) for r in rows))


def _reviewed(desk):
    from core import reviewed_source_links as rsl
    rows = rsl.load_public_desk_references(desk)
    schema = {"vietnam": rsl.SCHEMA, "philippines": rsl.PHILIPPINES_SCHEMA,
              "indonesia": rsl.INDONESIA_SCHEMA}[desk]
    return dsp.LaneData(
        schema=schema, publisher=None, issuer=None,
        editorial_status="human_reviewed_links", snapshot_date=None,
        entries=tuple(dsp.PublicReference(
            id=r["id"], url=r["source_url"], title_original=r["title_original"],
            published_date=r["published_date"], language=r.get("language"),
            source_slug=r["source_slug"]) for r in rows))


def gather_lane_data(bindings: dsp.Bindings) -> dict:
    """Run each declared lane's gated loader. A loader that refuses its input
    yields ``None`` (the adapter records it); it is never replaced by a guess."""
    from core import indonesia_official_index, indonesia_press_index
    loaders = {
        "korea_public_bibliography": _korea,
        "indonesia_official_index": lambda: _indonesia_index(indonesia_official_index),
        "indonesia_press_index": lambda: _indonesia_index(indonesia_press_index),
        "reviewed_links_indonesia": lambda: _reviewed("indonesia"),
        "reviewed_links_philippines": lambda: _reviewed("philippines"),
        "reviewed_links_vietnam": lambda: _reviewed("vietnam"),
    }
    out = {}
    for lane_id, spec in sorted(bindings.lanes.items()):
        try:
            out[lane_id] = loaders[spec.loader]()
        except (ValueError, OSError, KeyError) as exc:
            print("reference lane %s withheld: %s" % (lane_id, exc), file=sys.stderr)
            out[lane_id] = None
    return out


def gather_health(db_path, slugs) -> dict:
    """Latest ``source_run_results`` row per production slug, read-only."""
    from scripts.reconcile_db import read_only
    with read_only(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return health_from_connection(conn, slugs)


def health_from_connection(conn, slugs) -> dict:
    have = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='source_run_results'").fetchone() is not None
    have_articles = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                                 "AND name IN ('articles','sources')").fetchone()[0] == 2
    out = {}
    for slug in sorted(slugs):
        count = None
        if have_articles:
            count = conn.execute("SELECT COUNT(*) FROM articles a JOIN sources s "
                                 "ON s.id = a.source_id WHERE s.slug = ?", (slug,)).fetchone()[0]
        if not have:
            out[slug] = dsp.HealthInput(False, None, record_count=count)
            continue
        row = conn.execute("SELECT status, is_failure, new_documents, scrape_run_id, completed_at "
                           "FROM source_run_results WHERE source_slug = ? "
                           "ORDER BY scrape_run_id DESC LIMIT 1", (slug,)).fetchone()
        agg = conn.execute("SELECT MAX(CASE WHEN new_documents > 0 THEN completed_at END), "
                           "MAX(CASE WHEN is_failure = 0 AND status IN (%s) THEN completed_at END) "
                           "FROM source_run_results WHERE source_slug = ?"
                           % ",".join("?" * len(dsp.st.SUCCESS_STATUSES)),
                           tuple(sorted(dsp.st.SUCCESS_STATUSES)) + (slug,)).fetchone()
        out[slug] = dsp.HealthInput(
            history_available=True,
            latest=dsp.RunRow(*tuple(row)) if row is not None else None,
            last_new_document_at=agg[0], last_successful_collection_at=agg[1],
            record_count=count)
    return out


def build(*, as_of: str, db_path=None, with_health=True) -> dsp.ProvenanceAtlas:
    registry = load_registry()
    bindings = dsp.load_bindings()
    shadow = dsp.load_shadow_declarations()
    lanes = gather_lane_data(bindings)
    health = None
    if with_health:
        from config import DB_PATH
        slugs = {s.slug for e in registry for s in e.sources if s.contract_validated}
        health = gather_health(db_path or DB_PATH, slugs)
    return dsp.build_desk_provenance(registry, bindings, shadow, lanes, health, as_of=as_of)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", default=None, help="ISO date stamped on the atlas (default: today)")
    ap.add_argument("--db", default=None)
    ap.add_argument("--no-health", action="store_true",
                    help="omit run health; production sources then report no_history")
    ap.add_argument("--json", metavar="PATH", default=None, help="write the atlas JSON ('-' for stdout)")
    ap.add_argument("--matrix", metavar="PATH", default=None, help="write the Markdown matrix ('-' for stdout)")
    args = ap.parse_args()

    atlas = build(as_of=args.as_of or date.today().isoformat(), db_path=args.db,
                  with_health=not args.no_health)
    for flag, text in ((args.json, dsp.atlas_to_json(atlas)), (args.matrix, dsp.render_matrix(atlas))):
        if flag == "-":
            sys.stdout.write(text)
        elif flag:
            Path(flag).write_text(text, encoding="utf-8")
    if not args.json and not args.matrix:
        sys.stdout.write(dsp.render_matrix(atlas))
    if atlas.conflicts:
        print("%d provenance conflict(s) recorded" % len(atlas.conflicts), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
