#!/usr/bin/env python3
"""Private, read-only dry run: a *mechanical* China archive visibility cut.

NOT editorial curation; NOT safe for production. It demonstrates where
model screening would hide important original records and keep suspect
captures. All source IDs, publication routes and Brief trails are preserved.
"""
import argparse
from collections import Counter
from html import escape
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "output" / "corpus-index.json"
POLICY = ROOT / "research/china/discovery-reduction-rehearsal-2026-10-15.json"
FIELDS = ["id", "date", "source", "state", "title_en", "title_orig"]
PURPOSE = "internal_machine_screened_discovery_rehearsal_not_editorial_selection"


def evaluate(index, policy):
    if index.get("fields") != FIELDS:
        raise ValueError("compact record fields changed")
    if not isinstance(policy, dict) or set(policy) != {
        "version", "purpose", "publication_enabled", "owner_approved",
        "baseline_snapshot", "baseline_max_id", "created_on",
        "expected_china_full", "expected_china_analyzed_cohort",
        "target_approved_china_discovery_min",
        "target_approved_china_discovery_max", "mechanical_only_rule",
        "protected_source_citation_must_remain_accessible", "exception_alerts",
        "editorial_selection_manifest",
    }:
        raise ValueError("rehearsal schema changed")
    if (policy["version"] != 1 or policy["purpose"] != PURPOSE
            or policy["publication_enabled"] is not False
            or policy["owner_approved"] is not False
            or policy["mechanical_only_rule"] != "analyzed_original_state"
            or policy["editorial_selection_manifest"] is not None
            or policy["protected_source_citation_must_remain_accessible"] is not True):
        raise ValueError("rehearsal is not owner approval or publication authority")
    if index.get("snapshot") != policy["baseline_snapshot"]:
        raise ValueError("frozen rehearsal snapshot changed; explicit new review required")
    sources, states = index["sources"], index["states"]
    ids, china, all_rows = set(), [], []
    by_id = {}
    for row in index["records"]:
        if not isinstance(row, list) or len(row) != 6:
            raise ValueError("record row shape changed")
        ident, pub, src, st, english, original = row
        if (type(ident) is not int or ident <= 0 or ident in ids
                or type(src) is not int or type(st) is not int
                or not 0 <= src < len(sources)
                or not 0 <= st < len(states)
                or not isinstance(english, str)
                or not isinstance(original, str)):
            raise ValueError("duplicate or invalid source record identity")
        ids.add(ident)
        s = sources[src]
        if not isinstance(s, dict) or not isinstance(states[st], dict):
            raise ValueError("invalid source/processing state")
        info = {
            "id": ident, "date": pub, "title": original or english,
            "source": s["code"], "state": states[st]["code"],
            "desk": (s.get("desk") or {}).get("code"),
        }
        by_id[ident] = info
        all_rows.append(info)
        if info["desk"] == "china":
            china.append(info)
    snapshot = index["snapshot"]
    if (type(snapshot.get("records")) is not int
            or snapshot["records"] != len(ids)
            or max(ids) != policy["baseline_max_id"]):
        raise ValueError("source counts or max stable record ID drift")
    trails = index.get("trail_ids")
    if (not isinstance(trails, list) or len(set(trails)) != len(trails)
            or not set(trails).issubset(ids)):
        raise ValueError("lost or malformed Brief trail source IDs")
    if not isinstance(policy["exception_alerts"], list) or len(policy["exception_alerts"]) < 4:
        raise ValueError("false-negative/quality exception review is missing")
    seen_alerts = set()
    alerts = []
    for warning in policy["exception_alerts"]:
        if not isinstance(warning, dict) or set(warning) != {
            "id", "source", "title", "date", "state",
            "protected_brief_trail", "reason",
        }:
            raise ValueError("invalid exception alert receipt")
        ident = warning["id"]
        if type(ident) is not int or ident in seen_alerts:
            raise ValueError("duplicate/invalid source-alert ID")
        seen_alerts.add(ident)
        existing = by_id.get(ident)
        if not existing or existing["desk"] != "china":
            raise ValueError("exception alert missing or outside China")
        if (warning["source"] != existing["source"]
                or warning["title"] != existing["title"]
                or warning["date"] != existing["date"]
                or warning["state"] != existing["state"]
                or warning["protected_brief_trail"] is not (ident in trails)
                or not isinstance(warning["reason"], str)
                or len(warning["reason"]) < 45):
            raise ValueError("source alert drift or missing quality reason")
        alerts.append({
            "id": ident, "state": existing["state"],
            "mechanical_visibility": existing["state"] == "analyzed",
            "brief_trail": ident in trails,
            "reason": warning["reason"],
        })
    if policy["expected_china_full"] != len(china):
        raise ValueError("China full holdings changed, cannot silently re-scope")
    cohort = [r for r in china if r["state"] == "analyzed"]
    if policy["expected_china_analyzed_cohort"] != len(cohort):
        raise ValueError("machine-reviewed subset changed; frozen rehearsal expired")
    lower = policy["target_approved_china_discovery_min"]
    upper = policy["target_approved_china_discovery_max"]
    if (type(lower) is not int or type(upper) is not int or lower < 1
            or upper < lower or upper >= len(china)):
        raise ValueError("invalid future editorial target range")
    if not ({2849, 2391}.issubset(seen_alerts)
            and by_id[2849]["state"] != "analyzed"
            and by_id[2391]["state"] != "analyzed"):
        raise ValueError("known screened-out issuing-ministry false negatives lost")
    if not set(trails).issubset(set(by_id)):
        raise ValueError("published citations cannot be removed")
    return {
        "status": "INTERNAL MACHINE COHORT NOT AN EDITORIAL ALLOWLIST",
        "publication_enabled": False,
        "owner_approved": False,
        "snapshot": snapshot,
        "all_preserved": len(all_rows),
        "china_preserved": len(china),
        "china_mechanical_visible": len(cohort),
        "china_mechanical_not_prominent": len(china) - len(cohort),
        "china_mechanical_reduction_percent":
            round(100 * (len(china)-len(cohort)) / len(china), 2),
        "china_editorially_approved": 0,
        "future_target_min": lower,
        "future_target_max": upper,
        "published_trail_ids_preserved": len(trails),
        "warning_count": len(alerts),
        "warnings": alerts,
        "source_breakdown": {
            code: {
                "full": sum(r["source"] == code for r in china),
                "machine_analyzed": sum(r["source"] == code for r in cohort)
            } for code in sorted(set(r["source"] for r in china))
        },
        "preserved": all_rows,
        "machine_cohort": cohort,
    }


def page(name, lead, rows, report):
    links = "".join(
        "<li><time>%s</time> · <a href='https://indopacificrecord.org/record/%d.html'>#%d %s</a>"
        " <small>(%s; %s)</small></li>" %
        (escape(r["date"], quote=True), r["id"], r["id"],
         escape(r["title"], quote=True),
         escape(r["source"], quote=True), escape(r["state"], quote=True))
        for r in rows)
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow,noarchive'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none';"
        "style-src 'unsafe-inline';base-uri 'none';form-action 'none'\">"
        "<title>Private China cut rehearsal</title><style>"
        "body{font-family:system-ui,sans-serif;background:#f8f8f5;color:#142b39;margin:0}"
        "header,main{padding:24px;max-width:960px;margin:auto}"
        "h1{font-size:2.2rem}a{color:#12677a}li{padding:8px 0;border-bottom:1px solid #ddd}"
        ".alert{padding:16px;border:3px solid #91573e;background:#f2eade}"
        "small{color:#53656a}</style></head><body>"
        "<header><p>INDO-PACIFIC RECORD · INTERNAL PRODUCT EXPERIMENT</p>"
        "<h1>%s</h1><div class='alert'><strong>PRIVATE, UNAPPROVED AND "
        "NOT A CURATED PUBLICATION.</strong> %s</div>"
        "<p><a href='screened.html'>Mechanical China slice</a> · "
        "<a href='preserved.html'>Full preserved corpus</a></p>"
        "<p>%d China records stored; %d machine-analyzed; "
        "%d not prominent in this hypothetical view; %d editorially approved."
        " All published source-trail IDs remain preserved.</p></header>"
        "<main><h2>%d linked source records in this private view</h2>"
        "<ol>%s</ol></main></body></html>" %
        (escape(name),escape(lead),report["china_preserved"],
         report["china_mechanical_visible"],
         report["china_mechanical_not_prominent"],
         report["china_editorially_approved"],
         len(rows),links)
    )


def create_private_report(out_dir, report):
    folder = Path(out_dir).expanduser()
    root = ROOT.resolve()
    resolved = folder.resolve()
    if (not folder.is_absolute() or folder.exists() or folder.is_symlink()
            or folder.parent.is_symlink() or not folder.parent.is_dir()
            or resolved == root or root in resolved.parents
            or resolved in root.parents):
        raise ValueError("private rehearsal requires a fresh external directory")
    folder.mkdir(mode=0o700)
    files = {
        "screened.html": page(
            "What a blunt machine-status cut would display",
            "The 2,461 analyzed items shown here are NOT editor-approved. "
            "Two screened-out Chinese MFA statements and known source-quality "
            "failures expose why this cannot safely be deployed as curated-first.",
            report["machine_cohort"], report),
        "preserved.html": page(
            "Every preserved source record",
            "All records and existing link targets remain discoverable here. "
            "No records are deleted or suppressed from this private view.",
            report["preserved"], report),
        "summary.json": json.dumps({
            k: v for k, v in report.items() if k not in
            ("machine_cohort", "preserved")
        }, ensure_ascii=False, indent=2) + "\n",
    }
    for name, contents in files.items():
        fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(contents)
    return folder


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=Path, default=INDEX)
    ap.add_argument("--policy", type=Path, default=POLICY)
    ap.add_argument("--private-dir", type=Path)
    args = ap.parse_args(argv)
    idx = json.loads(args.index.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    report = evaluate(idx, policy)
    if args.private_dir:
        path = create_private_report(args.private_dir, report)
        print("PRIVATE REVIEW ONLY: %s" % path)
    summary = {k: v for k, v in report.items()
               if k not in ("machine_cohort", "preserved", "warnings")}
    summary["warning_ids"] = [x["id"] for x in report["warnings"]]
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
