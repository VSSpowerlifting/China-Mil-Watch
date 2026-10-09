#!/usr/bin/env python3
"""Read-only, local IPR operations snapshot.

This is an observability view, NOT a collector, publishing gate, desk
qualification decision, live GitHub Actions monitor, or editorial approval.

The production source report is the existing authoritative offline health
view. Shadow manifests are configuration evidence only; no local manifest
proves that a scheduled Actions run succeeded or that a desk is qualified.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH  # noqa: E402
from core.desk_registry import load_registry  # noqa: E402
from scripts.source_health_report import build_report  # noqa: E402

SCHEMA = "ipr-operations-snapshot/1"
SHADOW_ROOT = ROOT / "shadow"
DAILY_MARKER = ROOT / ".github/state/last_daily_run_date.txt"
PROTECTED = ("output", "shadow", "desks", "briefs")


class SnapshotError(ValueError):
    pass


def exact_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise SnapshotError("expected exact YYYY-MM-DD date") from exc
    if parsed.isoformat() != value:
        raise SnapshotError("expected exact YYYY-MM-DD date")
    return parsed


def marker_evidence(path: Path, as_of: date) -> dict:
    """A marker is a dated repository observation, NOT evidence of live CI."""
    if not path.is_file():
        return {"date": None, "age_days": None, "state": "not_observed",
                "meaning": "No local daily-success marker was available."}
    value = path.read_text(encoding="utf-8").strip()
    observed = exact_date(value)
    if observed > as_of:
        raise SnapshotError("daily marker is in the future relative to --as-of")
    return {"date": value, "age_days": (as_of - observed).days,
            "state": "marker_observed",
            "meaning": "Local committed marker only; current Actions health not checked."}


def shadow_inventory(root: Path, registered: dict) -> list:
    """Discover manifest declarations, not shadow state branches or receipts."""
    if not root.is_dir():
        raise SnapshotError("shadow manifest directory unavailable")
    items = []
    for path in sorted(root.glob("*/manifest.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotError("invalid shadow manifest: %s" % path) from exc
        desk = raw.get("desk")
        sources = raw.get("sources")
        if not isinstance(desk, dict) or not isinstance(sources, list):
            raise SnapshotError("malformed shadow manifest: %s" % path)
        desk_id = desk.get("desk_id")
        if not isinstance(desk_id, str) or not desk_id:
            raise SnapshotError("shadow manifest missing desk_id: %s" % path)
        slugs = []
        for item in sources:
            if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
                raise SnapshotError("shadow manifest has malformed source: %s" % path)
            if not isinstance(item.get("enabled"), bool):
                raise SnapshotError("shadow source enabled flag not boolean: %s" % path)
            slugs.append(item["slug"])
        if len(slugs) != len(set(slugs)):
            raise SnapshotError("duplicate shadow source slug: %s" % path)
        declared = registered.get(desk_id)
        historical = bool(declared and declared.is_collecting)
        items.append({
            "manifest": path.relative_to(ROOT).as_posix()
                if path.is_relative_to(ROOT) else str(path),
            "desk_id": desk_id,
            "display_name": desk.get("display_name") or desk_id,
            "declared_source_count": len(slugs),
            "enabled_in_shadow_manifest": sum(s["enabled"] for s in sources),
            "registry_status": declared.status if declared else None,
            "inventory_role": ("historical_shadow_manifest" if historical
                               else "nonproduction_source_configuration"),
            "live_collection_verified": False,
            "source_rights_verified": False,
            "eligible_for_production": False,
            "observed_run_date": None,
            "collected_records": None,
            "reason": ("Production eligibility cannot be inferred from this "
                       "shadow manifest or its enabled flags."),
        })
    return items


def assemble(registry, production_report: dict, shadow_root: Path,
             marker_path: Path, as_of: date) -> dict:
    registered = {desk.slug: desk for desk in registry}
    if len(registered) != len(registry.entries):
        raise SnapshotError("duplicate registry desk")
    reported = production_report.get("sources")
    if not isinstance(reported, list):
        raise SnapshotError("production health report missing sources")
    observations = {}
    for source in reported:
        slug = source.get("source_slug")
        if not slug or slug in observations:
            raise SnapshotError("missing or duplicate source health identity")
        observations[slug] = source

    expected = {source.slug for desk in registry if desk.is_collecting
                for source in desk.sources}
    if set(observations) != expected:
        raise SnapshotError("production source health/registry mismatch: "
                            "missing=%s extra=%s" % (
                                sorted(expected - set(observations)),
                                sorted(set(observations) - expected)))

    desks = []
    alerts = []
    for desk in registry:
        live = desk.is_collecting
        sources = []
        if live:
            for src in desk.sources:
                obs = observations[src.slug]
                if obs.get("desk_id") != desk.slug:
                    raise SnapshotError("source assigned to wrong desk: %s" % src.slug)
                item = {
                    "slug": src.slug, "name": src.display_name,
                    "enabled": src.enabled, "archive_articles": obs["articles_total"],
                    "last_article_date": obs.get("last_article_date"),
                    "last_successful_collection_at":
                        obs.get("last_successful_collection_at"),
                    "silence_verdict": obs.get("silence_verdict") or "unknown",
                    "config_health": obs.get("config_health") or "unknown",
                    "latest_run_status": (
                        (obs.get("latest_run_result") or {}).get("status")
                    ),
                }
                sources.append(item)
                if src.enabled and (item["silence_verdict"] == "overdue"
                                    or item["config_health"] not in ("ok", "healthy")):
                    alerts.append({"desk_id": desk.slug, "source_slug": src.slug,
                                   "reason": "review_source_health"})
        desks.append({
            "slug": desk.slug, "name": desk.name,
            "registry_status": desk.status, "is_production": live,
            "declared_sources": desk.configured_source_count,
            "enabled_sources": desk.enabled_source_count,
            "source_health_observed": live,
            "production_source_articles": (
                sum(s["archive_articles"] for s in sources) if live else None
            ),
            "production_sources": sources,
            "shadow_health": "not_observed" if not live else "not_applicable",
            "production_eligible": live,
            "editorial_publication_authorized": False,
        })

    shadows = shadow_inventory(shadow_root, registered)
    return {
        "schema": SCHEMA,
        "as_of": as_of.isoformat(),
        "evidence": {
            "desk_registry": "desks/registry.json",
            "production_health": "scripts/source_health_report.py",
            "shadow_manifest_inventory": "shadow/*/manifest.json",
            "daily_marker": ".github/state/last_daily_run_date.txt",
        },
        "production_report_generated_at": production_report.get("generated_at"),
        "source_history_available":
            bool(production_report.get("per_source_history_available")),
        "daily_marker": marker_evidence(marker_path, as_of),
        "desks": desks,
        "shadow_source_manifests": shadows,
        "source_health_review_flags": alerts,
        "limits": [
            "No GitHub Actions API, state branch, shadow ledger or review receipt was inspected.",
            "Shadow manifest enabled=true is a configuration value, not proof of live collection.",
            "Some shadow programs do not appear in the public desk registry; manifests are "
            "source families, not additional promoted desk entries.",
            "No source-rights or human-review decision is made here.",
            "No Sunday manuscript, model output or editor-delivery readiness is certified.",
            "Counts are source-attributed production article counts, not estimates of completeness.",
        ],
        "publication_authorized": False,
        "shadow_promotion_authorized": False,
        "editor_delivery_authorized": False,
        "collection_performed": False,
    }


def render_html(snapshot: dict) -> str:
    """Standalone local file with no external assets or executable scripts."""
    def val(x):
        return escape("—" if x is None else str(x), quote=True)

    def table(headings, rows):
        top = "".join("<th scope='col'>%s</th>" % val(v) for v in headings)
        body = "".join("<tr>%s</tr>" % "".join(
            "<td>%s</td>" % val(value) for value in row) for row in rows)
        return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (
            top, body or "<tr><td colspan='%d'>No observations</td></tr>" % len(headings))

    desks = table(
        ("Desk", "Declared status", "Production", "Configured / enabled",
         "Source-attributed records", "Observation"),
        [(d["name"], d["registry_status"], "yes" if d["is_production"] else "no",
          "%s / %s" % (d["declared_sources"], d["enabled_sources"]),
          d["production_source_articles"],
          "production source report" if d["source_health_observed"]
          else "shadow runs not inspected") for d in snapshot["desks"]])
    sources = table(
        ("Source", "Desk", "Records", "Latest article", "Silence",
         "Adapter", "Last successful source run"),
        [(s["name"], d["name"], s["archive_articles"], s["last_article_date"],
          s["silence_verdict"], s["config_health"],
          s["last_successful_collection_at"])
         for d in snapshot["desks"] for s in d["production_sources"]])
    shadows = table(
        ("Source family", "Manifest", "Desk identifier", "Enabled / declared", "Classification",
         "Live run evidence"),
        [(s["display_name"], s["manifest"], s["desk_id"],
          "%s / %s" % (s["enabled_in_shadow_manifest"], s["declared_source_count"]),
          s["inventory_role"], "not inspected")
         for s in snapshot["shadow_source_manifests"]])
    notes = "".join("<li>%s</li>" % val(note) for note in snapshot["limits"])
    css = """
    :root{color-scheme:light;--navy:#142a38;--teal:#247e7d;--paper:#f7f5f0}
    *{box-sizing:border-box}body{margin:0;background:var(--paper);color:#202f38;
    font:15px/1.55 system-ui,-apple-system,sans-serif}main{max-width:1150px;margin:auto;
    padding:42px 22px 70px}header{border-bottom:2px solid var(--navy);padding-bottom:20px}
    .eyebrow{font:700 12px/1.5 ui-monospace,monospace;letter-spacing:.12em;
    text-transform:uppercase;color:var(--teal)}h1{font:normal 42px/1.1 Georgia,serif;
    margin:9px 0}h2{font:normal 26px/1.2 Georgia,serif;margin:34px 0 12px}
    p{max-width:800px}small{color:#52626c}section{overflow-x:auto}
    table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}
    th,td{padding:11px 12px;border-bottom:1px solid #d8dddf;text-align:left;
    vertical-align:top}th{background:#e8edf0;color:var(--navy);font-weight:700}
    tr:nth-child(even) td{background:#fafbf9}.meta{margin-top:12px;color:#52626c}
    .notice{border-left:3px solid var(--teal);padding:8px 15px;background:#eaf0ee}
    @media(max-width:650px){main{padding:26px 12px}h1{font-size:32px}table{min-width:700px}}
    """
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>IPR Operations Center — offline snapshot</title><style>%s</style>"
            "</head><body><main><header><span class='eyebrow'>Internal / offline evidence</span>"
            "<h1>Operations Center</h1><p>Read-only inspection, not a green light for "
            "production promotion, rights reuse, editorial delivery, or publication.</p>"
            "<p class='meta'>As of %s · Daily marker: %s (%s) · %s source flags</p>"
            "</header><section><h2>Declared desks</h2>%s</section>"
            "<section><h2>Production source health</h2>%s</section>"
            "<section><h2>Shadow source inventory</h2>"
            "<p class='notice'>Configurations only. No live shadow Actions, ledgers, "
            "source-rights reviews, or qualification receipts were checked.</p>%s</section>"
            "<section><h2>Evidence limits</h2><ul>%s</ul></section>"
            "</main></body></html>") % (
                css, val(snapshot["as_of"]), val(snapshot["daily_marker"]["date"]),
                val(snapshot["daily_marker"]["state"]),
                val(len(snapshot["source_health_review_flags"])),
                desks, sources, shadows, notes)


def safe_destination(path: Path) -> Path:
    target = path.resolve()
    for name in PROTECTED:
        protected = (ROOT / name).resolve()
        if target == protected or protected in target.parents:
            raise SnapshotError("refusing report write inside protected %s/" % name)
    if target == (ROOT / "pla_watch.db").resolve():
        raise SnapshotError("refusing to overwrite the production database")
    if path.exists():
        raise SnapshotError("refusing to overwrite an existing report: %s" % path)
    if not path.parent.is_dir():
        raise SnapshotError("report parent directory does not exist: %s" % path.parent)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(DB_PATH))
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--json", type=Path, help="write a new JSON snapshot")
    parser.add_argument("--html", type=Path, help="write a new standalone HTML snapshot")
    args = parser.parse_args(argv)
    try:
        today = exact_date(args.as_of)
        destinations = [safe_destination(x) for x in (args.json, args.html) if x]
        if len({x.resolve() for x in destinations}) != len(destinations):
            raise SnapshotError("JSON and HTML destinations must differ")
        snapshot = assemble(
            load_registry(), build_report(args.db),
            SHADOW_ROOT, DAILY_MARKER, today)
        outputs = ((args.json, json.dumps(snapshot, ensure_ascii=False,
                        indent=2, sort_keys=True) + "\n"),
                   (args.html, render_html(snapshot)))
        for path, content in outputs:
            if path:
                with path.open("x", encoding="utf-8") as stream:
                    stream.write(content)
        if not destinations:
            print(json.dumps(snapshot, ensure_ascii=False, indent=2,
                             sort_keys=True))
        else:
            print("Generated read-only operations snapshot: " +
                  ", ".join(str(x) for x in destinations))
    except (SnapshotError, OSError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
