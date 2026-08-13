#!/usr/bin/env python3
"""
Source health report — human and machine readable.

Answers, per source, the questions a green run cannot:

  * Did it publish nothing, or did collection fail?
  * When did it last successfully collect, and last deliver a new document?
  * Is the current silence within this source's own expected cadence?

Read-only. Performs no network I/O and no model calls, so it is safe to run
anywhere and cheap to run often.

Usage:
    .venv/bin/python scripts/source_health_report.py
    .venv/bin/python scripts/source_health_report.py --json report.json
    .venv/bin/python scripts/source_health_report.py --run 110
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import DB_PATH                                    # noqa: E402
from core.collection import status as st                      # noqa: E402
from core.collection.health import silence_verdict            # noqa: E402
from core.registry import get_registry                        # noqa: E402


def _days_since(value) -> int:
    if not value:
        return None
    text = str(value)[:10]
    try:
        then = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (date.today() - then).days


def build_report(db_path, run_id=None) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    registry = get_registry()
    have_srr = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_run_results'"
    ).fetchone() is not None

    if run_id is None:
        row = conn.execute("SELECT MAX(id) AS m FROM scrape_runs").fetchone()
        run_id = row["m"] if row else None

    sources = []
    for slug in registry.slugs:
        src = registry.get_source(slug)

        last_article = conn.execute(
            "SELECT MAX(published_date) AS d, COUNT(*) AS n FROM articles a "
            "JOIN sources s ON s.id = a.source_id WHERE s.slug = ?", (slug,)
        ).fetchone()
        days_silent = _days_since(last_article["d"])

        entry = {
            "source_slug": slug,
            "desk_id": src.desk_id,
            "display_name": src.display_name,
            "authority_tier": src.authority_tier,
            "originality": src.originality,
            "enabled": src.enabled,
            "expected_cadence_days": src.expected_cadence_days,
            "silence_threshold_days": src.silence_threshold_days,
            "articles_total": last_article["n"],
            "last_article_date": last_article["d"],
            "days_since_last_article": days_silent,
            "silence_verdict": silence_verdict(days_silent, src),
            "config_health": registry.get_adapter(slug).healthcheck().status,
        }

        if have_srr:
            latest = conn.execute(
                "SELECT * FROM source_run_results WHERE source_slug = ? "
                "ORDER BY scrape_run_id DESC LIMIT 1", (slug,)
            ).fetchone()
            entry["latest_run_result"] = dict(latest) if latest else None
            agg = conn.execute(
                "SELECT MAX(CASE WHEN new_documents > 0 THEN completed_at END) AS "
                "last_new, MAX(CASE WHEN is_failure = 0 THEN completed_at END) AS "
                "last_ok FROM source_run_results WHERE source_slug = ?", (slug,)
            ).fetchone()
            entry["last_new_document_at"] = agg["last_new"]
            entry["last_successful_collection_at"] = agg["last_ok"]
        else:
            entry["latest_run_result"] = None
            entry["note"] = (
                "no per-source history yet — source_run_results is populated "
                "from the first run after migration 0004"
            )
        sources.append(entry)

    conn.close()
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "latest_run_id": run_id,
        "per_source_history_available": have_srr,
        "sources": sources,
    }


def human(report: dict) -> str:
    lines = [
        "Source health — generated %s (latest run %s)"
        % (report["generated_at"], report["latest_run_id"]),
        "=" * 92,
        "%-18s %-6s %-5s %-8s %8s  %-12s %-14s %s"
        % ("SOURCE", "DESK", "TIER", "ORIG", "ARTICLES", "LAST ARTICLE",
           "SILENCE", "CONFIG"),
        "-" * 92,
    ]
    for s in report["sources"]:
        lines.append(
            "%-18s %-6s %-5s %-8s %8d  %-12s %-14s %s"
            % (s["source_slug"], s["desk_id"] or "-", s["authority_tier"],
               s["originality"][:8], s["articles_total"],
               s["last_article_date"] or "never",
               "%s (%sd)" % (s["silence_verdict"],
                             s["days_since_last_article"]
                             if s["days_since_last_article"] is not None else "?"),
               s["config_health"])
        )
    lines.append("-" * 92)

    overdue = [s for s in report["sources"] if s["silence_verdict"] == "overdue"]
    stubs = [s for s in report["sources"]
             if s["config_health"] == st.NOT_IMPLEMENTED]
    if overdue:
        lines.append(
            "OVERDUE: %s — silent past its own measured cadence."
            % ", ".join(s["source_slug"] for s in overdue)
        )
    if stubs:
        lines.append(
            "NOT IMPLEMENTED: %s — configured but has no working collection "
            "path; contributes nothing by design."
            % ", ".join(s["source_slug"] for s in stubs)
        )
    if not report["per_source_history_available"]:
        lines.append(
            "NOTE: per-source run history is empty until the first run after "
            "migration 0004. Counts above come from the article corpus."
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--run", type=int, default=None)
    ap.add_argument("--json", metavar="PATH", default=None,
                    help="also write the machine-readable report here")
    args = ap.parse_args()

    report = build_report(args.db, args.run)
    print(human(report))

    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("\nmachine-readable report written to %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
