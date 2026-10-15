#!/usr/bin/env python3
"""Bounded, read-only survey of historical China Global Times stored text.

Heuristics identify records needing *review*, not proven extraction defects.
The current Global Times adapter already has a later extraction repair.
"""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_china_original_source_notes import _original_record, FIELDS  # noqa: E402

CUTOFF = "2026-09-16"
INDEX = ROOT / "output" / "corpus-index.json"
RECORD_DIR = ROOT / "output" / "record"


def quality_cues(body):
    """Return non-decisional capture flags; short genuine articles may qualify."""
    length = len(" ".join(body.split()))
    # Both three-dot and Unicode ellipsis can occur in quotes. A repeated
    # pattern is only a possible page teaser/navigation capture.
    teaser_marks = len(re.findall(r"(?:\.\s*){3}|…", body))
    cues = []
    if length < 60:
        cues.append("very_short_capture")
    elif length < 180:
        cues.append("short_capture_review")
    if teaser_marks >= 3:
        cues.append("multiple_ellipsis_teaser_cues")
    return {"cues": cues, "char_count": length, "ellipsis_count": teaser_marks}


def scan(index, pages, cutoff=CUTOFF):
    if index.get("fields") != FIELDS:
        raise ValueError("compact index fields changed")
    sources = index["sources"]
    trail_ids = index.get("trail_ids")
    if not isinstance(trail_ids, list) or len(trail_ids) != len(set(trail_ids)):
        raise ValueError("published citation trail protection missing")
    seen = set()
    candidates = []
    all_ids = set()
    for r in index["records"]:
        if not isinstance(r, list) or len(r) != 6 or type(r[0]) is not int or r[0] in seen:
            raise ValueError("repeated or malformed source record")
        seen.add(r[0])
        all_ids.add(r[0])
        if type(r[2]) is not int or not 0 <= r[2] < len(sources):
            raise ValueError("invalid source index")
        source = sources[r[2]]
        if source["code"] != "global_times_mil" or (source.get("desk") or {}).get("code") != "china":
            continue
        try:
            date.fromisoformat(r[1])
        except (TypeError, ValueError):
            raise ValueError("invalid date in legacy source record") from None
        if r[1] >= cutoff:
            continue
        candidates.append(r)
    if not set(trail_ids).issubset(all_ids):
        raise ValueError("published Brief source trail points to unknown record")
    found, warnings = [], Counter()
    for r in candidates:
        ident = r[0]
        if ident not in pages:
            raise ValueError("legacy original record HTML missing")
        body, url = _original_record(pages[ident])
        info = quality_cues(body)
        for cue in info["cues"]:
            warnings[cue] += 1
        if info["cues"]:
            found.append({
                "id": ident, "date": r[1], "source": sources[r[2]]["code"],
                "title": r[5] or r[4], "preserved_source_url": url,
                "cues": info["cues"], "stored_characters": info["char_count"],
                "ellipsis_count": info["ellipsis_count"],
                "published_brief_trail": ident in trail_ids,
            })
    found.sort(key=lambda x: (
        -int("multiple_ellipsis_teaser_cues" in x["cues"]),
        -len(x["cues"]), -x["ellipsis_count"], x["id"]))
    return {
        "purpose": "private_historical_capture_triage_no_changes",
        "source_snapshot": index.get("snapshot"),
        "source": "global_times_mil",
        "legacy_publication_dates_before": cutoff,
        "legacy_records_scanned": len(candidates),
        "flagged_for_manual_quality_review": len(found),
        "cue_counts_not_proven_defects": dict(sorted(warnings.items())),
        "all_source_records_preserved": len(index["records"]),
        "publication_authorized": False,
        "original_capture_repair_authorized": False,
        "candidates": found,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=Path, default=INDEX)
    ap.add_argument("--records-dir", type=Path, default=RECORD_DIR)
    ap.add_argument("--out", type=Path, help="new private JSON report outside repository")
    args = ap.parse_args(argv)
    if args.out:
        p = args.out.expanduser()
        path = p.resolve()
        if (not p.is_absolute() or p.exists() or p.is_symlink()
                or path == ROOT.resolve() or ROOT.resolve() in path.parents):
            ap.error("--out must be a new absolute report path outside the repository")
    index = json.loads(args.index.read_text(encoding="utf-8"))
    pages = {}
    for r in index["records"]:
        if (0 <= r[2] < len(index["sources"])
                and index["sources"][r[2]]["code"] == "global_times_mil"
                and r[1] < CUTOFF):
            pages[r[0]] = (args.records_dir / ("%d.html" % r[0])).read_text(
                encoding="utf-8")
    report = scan(index, pages)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "candidates"}
    summary["top_review_ids"] = [x["id"] for x in report["candidates"][:20]]
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
